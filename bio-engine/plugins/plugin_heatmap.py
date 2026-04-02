# plugins/plugin_heatmap.py
"""
BLI 热图与聚类分析插件
支持热图绘制、层级聚类、K-Means 聚类、PCA 降维等功能。
(极致紧凑亮色 UI 优化版，核心算法保持纯净)
"""

import os
import json
from io import StringIO
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDialog, QScrollArea,
                             QMessageBox, QFileDialog, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt

from qfluentwidgets import (LineEdit, SpinBox, DoubleSpinBox, CheckBox, ComboBox,
                            BodyLabel, PushButton, PlainTextEdit, PrimaryPushButton,
                            SubtitleLabel, StrongBodyLabel, CardWidget, ListWidget, FluentIcon as FIF)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig

try:
    from scipy.spatial.distance import pdist
    from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.patheffects
    HAS_SCI_LIBS = True
except ImportError:
    HAS_SCI_LIBS = False


# ==========================================
# 核心算法区 (原生算法，保持纯净，零修改)
# ==========================================
def safe_read_bli_file(path):
    try:
        if str(path).lower().endswith('.csv'):
            df = pd.read_csv(path, sep=None, engine='python', index_col=0)
        else:
            df = pd.read_excel(path, index_col=0)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df = df.apply(pd.to_numeric, errors='coerce')
        return df
    except Exception:
        return None

def calculate_inhibition(df, ref_name="PBST"):
    if df is None or df.empty:
        return None
    ref_name = str(ref_name).strip().lower()

    ref_row = None
    for idx in df.index:
        if str(idx).lower() == ref_name:
            ref_row = df.loc[idx]
            break

    if ref_row is None:
        return df

    ref_safe = ref_row.replace(0, 1e-9)
    ratio = df.div(ref_safe, axis=1)
    inhibition = 1.0 - ratio

    inhibition = inhibition.replace([np.inf, -np.inf], 0).fillna(0)
    inhibition = inhibition.clip(0, 1)

    cols_to_drop = [c for c in inhibition.columns if str(c).lower() == ref_name]
    if cols_to_drop:
        inhibition.drop(columns=cols_to_drop, inplace=True)
    rows_to_drop = [r for r in inhibition.index if str(r).lower() == ref_name]
    if rows_to_drop:
        inhibition.drop(index=rows_to_drop, inplace=True)

    return inhibition

def process_bli_data(df, calc_mode="inhibition", ref_name="PBST"):
    if df is None or df.empty:
        return None
    if "1 -" in calc_mode:
        df = calculate_inhibition(df, ref_name)
    df.fillna(0, inplace=True)
    df.replace([np.inf, -np.inf], 0, inplace=True)
    return df


# ==========================================
# 前端：Heatmap UI (极限紧凑与亮色美化)
# ==========================================
class HeatmapUI(BasePluginUI):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="heatmap_analyzer", plugin_name="BLI 热图与聚类分析", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.file_list = []
        self.export_df = None
        self.setAcceptDrops(True)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        # ========== 左侧参数面板 ==========
        h_tools = QHBoxLayout()
        btn_import_config = PushButton("📂 载入模板", icon=FIF.FOLDER)
        btn_export_config = PushButton("💾 保存模板", icon=FIF.SAVE)
        btn_import_config.clicked.connect(self.import_config)
        btn_export_config.clicked.connect(self.export_config)
        h_tools.addWidget(btn_import_config); h_tools.addWidget(btn_export_config)
        self.param_layout.insertLayout(0, h_tools)

        if not self.is_setting_mode:
            group_data, layout_data = self.create_group("1. 数据池 (支持拖拽/右键发送)")
            btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 0, 0, 0)
            btn_add = PrimaryPushButton("导入...", icon=FIF.DOWNLOAD)
            btn_add.clicked.connect(self.open_files)
            btn_clear = PushButton("清空", icon=FIF.DELETE)
            btn_clear.clicked.connect(self.clear_files)
            btn_row.addWidget(btn_add); btn_row.addWidget(btn_clear)
            layout_data.addLayout(btn_row)

            self.list_widget = ListWidget()
            self.list_widget.setFixedHeight(65)
            self.list_widget.itemClicked.connect(self.trigger_render)
            layout_data.addWidget(self.list_widget)
            self.add_param_widget(group_data)

        group_wh, layout_wh = self.create_group("2. 全局画板尺寸 (英寸)")
        h_wh = QHBoxLayout(); h_wh.setContentsMargins(0, 0, 0, 0)
        self.spin_w = DoubleSpinBox(); self.spin_w.setRange(1.0, 50.0); self.spin_w.setValue(8.0); self.spin_w.setSingleStep(0.5)
        self.spin_h = DoubleSpinBox(); self.spin_h.setRange(1.0, 50.0); self.spin_h.setValue(6.0); self.spin_h.setSingleStep(0.5)
        h_wh.addWidget(BodyLabel("W:")); h_wh.addWidget(self.spin_w, 1)
        h_wh.addSpacing(5)
        h_wh.addWidget(BodyLabel("H:")); h_wh.addWidget(self.spin_h, 1)
        layout_wh.addLayout(h_wh)
        self.add_param_widget(group_wh)

        group_param, layout_param = self.create_group("3. 聚类算法与样式参数")
        self.add_param_widget(group_param)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(4) # 【优化】极限压榨间距

        self.text_data = PlainTextEdit()
        self.text_data.setPlaceholderText("覆盖数据：可直接粘贴包含表头与侧边的文本矩阵...")
        self.text_data.setFixedHeight(50) # 【优化】压榨高度
        if not self.is_setting_mode:
            scroll_layout.addWidget(self.text_data)

        scroll_layout.addSpacing(8) # 逻辑块分隔
        scroll_layout.addWidget(StrongBodyLabel("模式与计算逻辑"))

        self.mode = ComboBox(); self.mode.addItems(["Heatmap (热图与层级聚类)", "K-Means (PCA降维散点图)"])
        self.add_row(scroll_layout, "当前模式:", self.mode)

        self.ref = LineEdit(); self.ref.setText("PBST")
        self.add_row(scroll_layout, "参比行:", self.ref)

        self.calc = ComboBox(); self.calc.addItems(["自动计算: 1 - (Row / Ref)", "使用原始数据"])
        self.add_row(scroll_layout, "计算方式:", self.calc)

        h_chk1 = QHBoxLayout(); h_chk1.setSpacing(4)
        self.trans = CheckBox("转置数据"); self.trans.setChecked(True)
        self.merge = CheckBox("合并多文件"); self.merge.setChecked(True)
        h_chk1.addWidget(self.trans); h_chk1.addWidget(self.merge)
        scroll_layout.addLayout(h_chk1)

        scroll_layout.addSpacing(8)
        scroll_layout.addWidget(StrongBodyLabel("外观与文字控制"))

        lbl_bold = BodyLabel("独立加粗:"); lbl_bold.setStyleSheet("color:#666; font-size:11px;")
        scroll_layout.addWidget(lbl_bold)

        h_bold = QHBoxLayout(); h_bold.setSpacing(4)
        self.b_title = CheckBox("标题"); self.b_title.setChecked(True)
        self.b_label = CheckBox("轴名"); self.b_label.setChecked(True)
        self.b_tick = CheckBox("刻度"); self.b_annot = CheckBox("点/注")
        h_bold.addWidget(self.b_title); h_bold.addWidget(self.b_label); h_bold.addWidget(self.b_tick); h_bold.addWidget(self.b_annot)
        scroll_layout.addLayout(h_bold)

        lbl_fs = BodyLabel("字号矩阵:"); lbl_fs.setStyleSheet("color:#666; font-size:11px; margin-top:4px;")
        scroll_layout.addWidget(lbl_fs)

        self.fs_title = SpinBox(); self.fs_title.setRange(6, 40); self.fs_title.setValue(14)
        self.fs_label = SpinBox(); self.fs_label.setRange(6, 40); self.fs_label.setValue(12)
        self.fs_tick = SpinBox(); self.fs_tick.setRange(6, 40); self.fs_tick.setValue(9)

        h_fs = QHBoxLayout(); h_fs.setSpacing(4)
        h_fs.addWidget(BodyLabel("标题:")); h_fs.addWidget(self.fs_title, 1)
        h_fs.addWidget(BodyLabel("轴名:")); h_fs.addWidget(self.fs_label, 1)
        h_fs.addWidget(BodyLabel("刻度:")); h_fs.addWidget(self.fs_tick, 1)
        scroll_layout.addLayout(h_fs)

        self.cmap = ComboBox(); self.cmap.addItems(["Default (Soft RdBu)", "RdBu_r", "viridis", "coolwarm", "magma", "Blues", "YlGnBu"])
        self.annot = CheckBox("显示数值"); self.annot.setChecked(True)
        self.add_row(scroll_layout, "色带:", self.cmap, "", self.annot)

        self.auto_size = CheckBox("自适应画布"); self.auto_size.setChecked(True)
        self.square = CheckBox("强制正方形"); self.square.setChecked(False)
        self.add_row(scroll_layout, "", self.auto_size, "", self.square)

        self.grid = CheckBox("切割网格"); self.grid.setChecked(True)
        self.ms = SpinBox(); self.ms.setRange(10, 500); self.ms.setValue(120)
        self.add_row(scroll_layout, "PCA点大小:", self.ms, "", self.grid)

        scroll_layout.addSpacing(8)
        scroll_layout.addWidget(StrongBodyLabel("聚类算法参数"))

        self.do_cluster = CheckBox("执行层级聚类 (绘树状图)"); self.do_cluster.setChecked(True)
        scroll_layout.addWidget(self.do_cluster)

        self.cutoff = LineEdit(); self.cutoff.setText("0.4")
        self.add_row(scroll_layout, "Cutoff:", self.cutoff)

        self.metric = ComboBox(); self.metric.addItems(["cosine", "euclidean", "correlation"])
        self.method = ComboBox(); self.method.addItems(["average", "single", "complete", "ward"])
        self.add_row(scroll_layout, "距离:", self.metric, "方法:", self.method)

        self.k = SpinBox(); self.k.setRange(2, 50); self.k.setValue(4)
        self.add_row(scroll_layout, "K-means K:", self.k)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout_param.addWidget(scroll)

        if self.is_setting_mode:
            self.btn_save_config = PrimaryPushButton("💾 确认并保存为全局默认参数", icon=FIF.SAVE)
            self.btn_save_config.setFixedHeight(45)
            self.btn_save_config.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(self.btn_save_config)
            return

        self.btn_plot = PrimaryPushButton("⚡ 执行聚类与渲染", icon=FIF.PLAY)
        self.btn_plot.setFixedHeight(35)
        self.btn_plot.clicked.connect(self.trigger_render)
        self.param_layout.addWidget(self.btn_plot)

        # ========== 右侧画板 (极致优化为原生白色悬浮质感) ==========
        self.fig = Figure(dpi=120)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.canvas_container = QWidget()
        # 【极致优化】抛弃粗糙的灰底，赋予白纸卡片质感
        self.canvas_container.setStyleSheet("background-color: #FFFFFF; border: 1px solid #EAEAEA; border-radius: 8px;")
        canvas_layout = QVBoxLayout(self.canvas_container)
        canvas_layout.setContentsMargins(10, 10, 10, 10)
        canvas_layout.setAlignment(Qt.AlignCenter)
        canvas_layout.addWidget(self.canvas)

        self.scroll_canvas = QScrollArea()
        self.scroll_canvas.setWidgetResizable(True)
        self.scroll_canvas.setFrameShape(QScrollArea.NoFrame)
        # 【极致优化】外层透明融入系统
        self.scroll_canvas.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.scroll_canvas.setWidget(self.canvas_container)

        self.toolbar = NavigationToolbar(self.canvas, self)

        export_layout = QHBoxLayout()
        export_layout.addStretch()
        self.chk_trans = CheckBox("透明背景")
        export_layout.addWidget(self.chk_trans)
        export_layout.addSpacing(15)
        self.combo_fmt = ComboBox(); self.combo_fmt.addItems(["pdf", "png", "svg"])
        export_layout.addWidget(StrongBodyLabel("导出格式:"))
        export_layout.addWidget(self.combo_fmt)
        btn_export = PushButton("保存图表", icon=FIF.SAVE)
        btn_export.clicked.connect(self.export_plot)
        export_layout.addWidget(btn_export)

        btn_csv = PushButton("💾 导出矩阵 (.csv)")
        btn_csv.clicked.connect(self.save_csv)
        export_layout.addWidget(btn_csv)

        self.get_canvas_layout().addWidget(self.toolbar)
        self.get_canvas_layout().addWidget(self.scroll_canvas)
        self.get_canvas_layout().addLayout(export_layout)

    # ------------------------------------
    # 数据交互、配置与文件管理 (维持原有逻辑)
    # ------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.load_file(url.toLocalFile())

    def load_file(self, filepath):
        if not os.path.exists(filepath): return
        if filepath.lower().endswith(('.csv', '.xlsx', '.xls', '.txt')):
            if filepath not in self.file_list:
                self.file_list.append(filepath)
                if not self.is_setting_mode: self.list_widget.addItem(os.path.basename(filepath))
        if self.file_list and not self.is_setting_mode and not self.list_widget.currentItem():
            self.list_widget.setCurrentRow(0)
            self.trigger_render()

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择数据文件", "", "Data Files (*.csv *.xlsx *.xls *.txt);;All Files (*)")
        for fp in files: self.load_file(fp)

    def clear_files(self):
        self.file_list.clear()
        if not self.is_setting_mode:
            self.list_widget.clear(); self.fig.clear(); self.canvas.draw(); self.text_data.clear()

    def get_float(self, line_edit, default=0.0):
        try: return float(line_edit.text())
        except: return default

    def _load_config(self):
        config = GlobalConfig.get_all_plugin_settings(self.plugin_id)
        if config: self.apply_config_dict(config)

    def _save_config(self):
        config = self.get_config_dict()
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def get_config_dict(self):
        return {
            "mode": self.mode.currentText(), "ref": self.ref.text(), "calc": self.calc.currentText(),
            "trans": self.trans.isChecked(), "merge": self.merge.isChecked(),
            "spin_w": self.spin_w.value(), "spin_h": self.spin_h.value(),
            "b_title": self.b_title.isChecked(), "b_label": self.b_label.isChecked(), "b_tick": self.b_tick.isChecked(), "b_annot": self.b_annot.isChecked(),
            "fs_title": self.fs_title.value(), "fs_label": self.fs_label.value(), "fs_tick": self.fs_tick.value(),
            "cmap": self.cmap.currentText(), "annot": self.annot.isChecked(), "auto_size": self.auto_size.isChecked(),
            "square": self.square.isChecked(), "grid": self.grid.isChecked(), "ms": self.ms.value(),
            "do_cluster": self.do_cluster.isChecked(), "cutoff": self.cutoff.text(),
            "metric": self.metric.currentText(), "method": self.method.currentText(), "k": self.k.value()
        }

    def apply_config_dict(self, data):
        self.mode.setCurrentText(data.get("mode", "Heatmap (热图与层级聚类)"))
        self.ref.setText(data.get("ref", "PBST")); self.calc.setCurrentText(data.get("calc", "自动计算: 1 - (Row / Ref)"))
        self.trans.setChecked(data.get("trans", True)); self.merge.setChecked(data.get("merge", True))
        self.spin_w.setValue(data.get("spin_w", 8.0)); self.spin_h.setValue(data.get("spin_h", 6.0))
        self.b_title.setChecked(data.get("b_title", True)); self.b_label.setChecked(data.get("b_label", True)); self.b_tick.setChecked(data.get("b_tick", True)); self.b_annot.setChecked(data.get("b_annot", False))
        self.fs_title.setValue(data.get("fs_title", 14)); self.fs_label.setValue(data.get("fs_label", 12)); self.fs_tick.setValue(data.get("fs_tick", 9))
        self.cmap.setCurrentText(data.get("cmap", "Default (Soft RdBu)")); self.annot.setChecked(data.get("annot", True))
        self.auto_size.setChecked(data.get("auto_size", True)); self.square.setChecked(data.get("square", False))
        self.grid.setChecked(data.get("grid", True)); self.ms.setValue(data.get("ms", 120))
        self.do_cluster.setChecked(data.get("do_cluster", True)); self.cutoff.setText(data.get("cutoff", "0.4"))
        self.metric.setCurrentText(data.get("metric", "cosine")); self.method.setCurrentText(data.get("method", "average")); self.k.setValue(data.get("k", 4))

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 Heatmap 模板", "heatmap_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入 Heatmap 模板", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f: self.apply_config_dict(json.load(f))
            if not self.is_setting_mode: self.trigger_render()

    def save_settings_and_close(self):
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog): parent_dlg.accept()

    def get_heatmap_df(self):
        mode, ref_name, processed_dfs = self.calc.currentText(), self.ref.text(), []
        raw_text = self.text_data.toPlainText().strip()
        if raw_text:
            try:
                df = pd.read_csv(StringIO(raw_text), sep='\t', index_col=0)
                if df.shape[1] < 2: df = pd.read_csv(StringIO(raw_text), sep=r'\s+', index_col=0)
                df = df.loc[:, ~df.columns.str.contains('^Unnamed')].apply(pd.to_numeric, errors='coerce')
                processed_dfs.append(process_bli_data(df, mode, ref_name))
            except Exception as e: raise ValueError(f"粘贴数据解析失败:\n{str(e)}")
        else:
            if not self.file_list: raise ValueError("请先粘贴数据，或在上方添加文件！")
            target_paths = self.file_list if self.merge.isChecked() else [self.file_list[self.list_widget.currentRow()]] if self.list_widget.currentRow() >= 0 else []
            for fp in target_paths:
                df_raw = safe_read_bli_file(fp)
                if df_raw is not None: processed_dfs.append(process_bli_data(df_raw, mode, ref_name))

        if not processed_dfs: raise ValueError("未能提取出有效数据！")
        final_df = pd.DataFrame()
        global_idx_counts = {}
        for df in processed_dfs:
            if df is None or df.empty: continue
            new_indices = []
            for idx in df.index:
                s_idx = str(idx)
                if s_idx not in global_idx_counts:
                    global_idx_counts[s_idx] = 1; new_indices.append(s_idx)
                else:
                    global_idx_counts[s_idx] += 1; new_indices.append(f"{s_idx}_{global_idx_counts[s_idx]}")
            df.index = new_indices
            final_df = df if final_df.empty else pd.concat([final_df, df], axis=0, join='outer')
        final_df.fillna(0, inplace=True)
        if self.trans.isChecked(): final_df = final_df.T
        return final_df

    # ------------------------------------
    # 绘图核心
    # ------------------------------------
    def trigger_render(self, *args):
        if self.is_setting_mode: return
        self._save_config()
        self.render_plot()
        dpi = self.fig.dpi
        w_px = int(self.spin_w.value() * dpi)
        h_px = int(self.spin_h.value() * dpi)
        self.canvas.setFixedSize(w_px, h_px)
        self.canvas_container.updateGeometry()

    def export_plot(self):
        if self.is_setting_mode: return
        fmt = self.combo_fmt.currentText(); is_transparent = self.chk_trans.isChecked(); row = self.list_widget.currentRow()
        default_name = os.path.splitext(self.list_widget.item(max(0, row)).text())[0] + f"_Heatmap.{fmt}" if self.list_widget.count() > 0 else f"Heatmap_Plot.{fmt}"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出图表", default_name, f"Images (*.{fmt})")
        if file_path:
            try:
                self.fig.savefig(file_path, dpi=600, bbox_inches="tight", transparent=is_transparent)
                QMessageBox.information(self, "成功", f"图表已导出:\n{file_path}")
            except Exception as e: QMessageBox.critical(self, "导出失败", str(e))

    def save_csv(self):
        if self.export_df is None or self.export_df.empty:
            QMessageBox.warning(self, "提示", "目前没有可导出的数据，请先渲染图表！")
            return
        default_name = "Heatmap_CalcResult.csv"
        row = self.list_widget.currentRow()
        if row >= 0 and row < len(self.file_list) and not self.text_data.toPlainText().strip() and not self.merge.isChecked():
            default_name = os.path.splitext(self.list_widget.item(row).text())[0] + "_CalcResult.csv"
        path, _ = QFileDialog.getSaveFileName(self, "导出计算结果", default_name, "CSV Files (*.csv)")
        if path:
            try:
                self.export_df.to_csv(path)
                QMessageBox.information(self, "成功", f"数据已成功导出至:\n{path}")
            except Exception as e: QMessageBox.critical(self, "导出失败", str(e))

    def render_plot(self):
        if self.is_setting_mode: return
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.export_df = None

        if not HAS_SCI_LIBS:
            self.ax.text(0.5, 0.5, "缺少 scipy/sklearn 库，无法聚类计算", ha='center')
            self.canvas.draw()
            return

        try: df = self.get_heatmap_df()
        except Exception as e:
            self.ax.text(0.5, 0.5, f"获取数据失败:\n{str(e)}", ha='center', va='center')
            self.canvas.draw()
            return

        self.export_df = df.copy()

        if self.auto_size.isChecked():
            cell_size = 0.55 if self.square.isChecked() else 0.45
            min_w = max(5.0, df.shape[1] * cell_size + 3.0)
            min_h = max(4.0, df.shape[0] * cell_size + 2.0)
            self.spin_w.setValue(min_w); self.spin_h.setValue(min_h)
        self.fig.set_size_inches(self.spin_w.value(), self.spin_h.value())

        fw_title = 'bold' if self.b_title.isChecked() else 'normal'
        fw_label = 'bold' if self.b_label.isChecked() else 'normal'
        fw_tick = 'bold' if self.b_tick.isChecked() else 'normal'
        fw_annot = 'bold' if self.b_annot.isChecked() else 'normal'

        fs_title = self.fs_title.value()
        fs_label = self.fs_label.value()
        fs_tick = self.fs_tick.value()
        is_inhib = "1 -" in self.calc.currentText()

        # ================== Heatmap 模式 ==================
        if "Heatmap" in self.mode.currentText():
            do_cluster = self.do_cluster.isChecked()
            divider = make_axes_locatable(self.ax)

            if do_cluster and df.shape[1] >= 2:
                dist = np.nan_to_num(pdist(df.T + 1e-9, metric=self.metric.currentText()))
                Z = linkage(dist, method=self.method.currentText())

                cutoff_val = self.get_float(self.cutoff, 0.4)
                color_threshold = cutoff_val * max(Z[:, 2]) if len(Z) > 0 else 0

                ax_cbar_cluster = divider.append_axes("top", size="4%", pad=0.01)
                ax_tree = divider.append_axes("top", size="15%", pad=0.0)

                dendro = dendrogram(Z, ax=ax_tree, no_labels=True, color_threshold=color_threshold, above_threshold_color='#555555')
                ax_tree.axis('off')

                leaves_order = dendro['leaves']
                df_plot = df.iloc[:, leaves_order]

                clusters = fcluster(Z, t=color_threshold, criterion='distance')
                clusters_ordered = clusters[leaves_order]
                try: cmap_cluster = matplotlib.colormaps["tab10"]
                except: cmap_cluster = cm.get_cmap("tab10")
                ax_cbar_cluster.imshow([clusters_ordered], aspect='auto', cmap=cmap_cluster, interpolation='nearest')
                ax_cbar_cluster.axis('off')
            else:
                df_plot = df; do_cluster = False

            cmap_sel = self.cmap.currentText()
            if cmap_sel == "Default (Soft RdBu)":
                colors = ["#63aaff", "#ffffff", "#ff6b6b"]
                cmap = LinearSegmentedColormap.from_list("soft_rdbu", colors)
            else: cmap = cmap_sel

            aspect_val = 'equal' if self.square.isChecked() else 'auto'
            im = self.ax.imshow(df_plot, aspect=aspect_val, cmap=cmap, interpolation='nearest')

            if self.annot.isChecked():
                for i in range(len(df_plot.index)):
                    for j in range(len(df_plot.columns)):
                        val = df_plot.iloc[i, j]
                        txt_val = f"{val * 100:.0f}" if is_inhib else f"{val:.1f}"
                        self.ax.text(j, i, txt_val, ha="center", va="center", color="black", fontsize=fs_tick, fontweight=fw_annot, path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground="white")])

            self.ax.set_xticks(range(len(df_plot.columns)))
            self.ax.set_yticks(range(len(df_plot.index)))
            self.ax.set_xticklabels(df_plot.columns, rotation=90, fontsize=fs_tick, fontweight=fw_tick)
            self.ax.set_yticklabels(df_plot.index, fontsize=fs_tick, fontweight=fw_tick)

            if self.grid.isChecked():
                self.ax.set_xticks(np.arange(df_plot.shape[1] + 1) - 0.5, minor=True)
                self.ax.set_yticks(np.arange(df_plot.shape[0] + 1) - 0.5, minor=True)
                self.ax.grid(which="minor", color="white", linestyle='-', linewidth=2)
                self.ax.tick_params(which="minor", bottom=False, left=False)

            self.ax.set_title("")
            cbar = plt.colorbar(im, cax=divider.append_axes("right", size="3%", pad=0.1))
            cbar_label = "Inhibition Rate" if is_inhib else "Value"
            cbar.set_label(cbar_label, fontsize=fs_label, fontweight=fw_label, labelpad=10)

        # ================== K-Means 模式 ==================
        else:
            k = self.k.value()
            if len(df) < k: return
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            clusters = kmeans.fit_predict(df)
            coords = PCA(n_components=2).fit_transform(df)

            self.export_df['Cluster'] = clusters

            try: cmap_km = matplotlib.colormaps["tab10"]
            except: cmap_km = cm.get_cmap("tab10")

            self.ax.scatter(coords[:, 0], coords[:, 1], c=clusters, cmap=cmap_km, s=self.ms.value(), edgecolors='white', alpha=0.9)
            for i, txt in enumerate(df.index):
                self.ax.annotate(txt, (coords[i, 0], coords[i, 1]), xytext=(6, 6), textcoords='offset points', fontsize=fs_tick, fontweight=fw_annot)

            self.ax.set_title(f"K-Means PCA Scatter (K={k})", fontweight=fw_title, fontsize=fs_title)
            if self.grid.isChecked(): self.ax.grid(True, ls='--', alpha=0.5)

        self.fig.tight_layout()
        self.canvas.draw()


# ==========================================
# 后端：插件描述器
# ==========================================
class HeatmapPlugin(BasePlugin):
    plugin_id = "heatmap_analyzer"
    plugin_name = "BLI 热图与聚类分析"
    icon = "🔥"
    trigger_tag = "BLI 热图"

    def get_ui(self, parent=None):
        return HeatmapUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        card = PrimaryPushSettingCard("配置全局默认参数", FIF.EDIT, "🔥 BLI 热图与聚类分析", "修改工作站中热图的默认聚类算法、色带模板与外观偏好", parent)

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("Heatmap 全局默认参数预设中心")
            dlg.resize(460, 750)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }") # 【优化】锁死亮色弹窗
            layout = QVBoxLayout(dlg)
            settings_ui = HeatmapUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        """后台自动处理逻辑 (完全保持原生架构，极度稳定)"""
        try:
            config = GlobalConfig.get_all_plugin_settings("heatmap_analyzer")
            u = config if config else {}

            if not HAS_SCI_LIBS: return "", "【BLI 热图分析跳过】当前环境缺少 scipy/sklearn 依赖库，无法执行聚类计算。"

            df_raw = safe_read_bli_file(file_path)
            if df_raw is None or df_raw.empty: return "", "【BLI 热图分析跳过】数据文件读取失败或格式不支持。"

            calc_mode = u.get("calc", "自动计算: 1 - (Row / Ref)")
            ref_name = u.get("ref", "PBST")
            df = process_bli_data(df_raw, calc_mode, ref_name)
            if df is None or df.empty: return "", "【BLI 热图分析跳过】数据处理后为空矩阵。"
            if u.get("trans", True): df = df.T

            w, h = float(u.get("spin_w", 8.0)), float(u.get("spin_h", 6.0))
            if u.get("auto_size", True):
                cell_size = 0.55 if u.get("square", False) else 0.45
                w, h = max(5.0, df.shape[1] * cell_size + 3.0), max(4.0, df.shape[0] * cell_size + 2.0)

            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt
            from mpl_toolkits.axes_grid1 import make_axes_locatable
            from matplotlib.colors import LinearSegmentedColormap
            import matplotlib.patheffects

            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False

            fig = Figure(figsize=(w, h), dpi=150)
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)

            fw_title = 'bold' if u.get('b_title', True) else 'normal'
            fw_label = 'bold' if u.get('b_label', True) else 'normal'
            fw_tick = 'bold' if u.get('b_tick', True) else 'normal'
            fw_annot = 'bold' if u.get('b_annot', False) else 'normal'

            fs_title, fs_label, fs_tick = u.get('fs_title', 14), u.get('fs_label', 12), u.get('fs_tick', 9)
            is_inhib = "1 -" in calc_mode
            mode_str = u.get('mode', "Heatmap (热图与层级聚类)")

            if "Heatmap" in mode_str:
                do_cluster = u.get('do_cluster', True)
                divider = make_axes_locatable(ax)

                if do_cluster and df.shape[1] >= 2:
                    dist = np.nan_to_num(pdist(df.T + 1e-9, metric=u.get('metric', 'cosine')))
                    Z = linkage(dist, method=u.get('method', 'average'))
                    color_threshold = float(u.get('cutoff', 0.4)) * max(Z[:, 2]) if len(Z) > 0 else 0

                    ax_cbar_cluster = divider.append_axes("top", size="4%", pad=0.01)
                    ax_tree = divider.append_axes("top", size="15%", pad=0.0)

                    dendro = dendrogram(Z, ax=ax_tree, no_labels=True, color_threshold=color_threshold, above_threshold_color='#555555')
                    ax_tree.axis('off')

                    leaves_order = dendro['leaves']
                    df_plot = df.iloc[:, leaves_order]
                    clusters = fcluster(Z, t=color_threshold, criterion='distance')
                    try: cmap_cluster = matplotlib.colormaps["tab10"]
                    except: cmap_cluster = cm.get_cmap("tab10")
                    ax_cbar_cluster.imshow([clusters[leaves_order]], aspect='auto', cmap=cmap_cluster, interpolation='nearest')
                    ax_cbar_cluster.axis('off')
                else: df_plot = df

                cmap_sel = u.get('cmap', "Default (Soft RdBu)")
                if cmap_sel == "Default (Soft RdBu)": cmap = LinearSegmentedColormap.from_list("soft_rdbu", ["#63aaff", "#ffffff", "#ff6b6b"])
                else: cmap = cmap_sel

                aspect_val = 'equal' if u.get('square', False) else 'auto'
                im = ax.imshow(df_plot, aspect=aspect_val, cmap=cmap, interpolation='nearest')

                if u.get('annot', True):
                    for i in range(len(df_plot.index)):
                        for j in range(len(df_plot.columns)):
                            val = df_plot.iloc[i, j]
                            txt_val = f"{val * 100:.0f}" if is_inhib else f"{val:.1f}"
                            ax.text(j, i, txt_val, ha="center", va="center", color="black", fontsize=fs_tick, fontweight=fw_annot, path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground="white")])

                ax.set_xticks(range(len(df_plot.columns))); ax.set_yticks(range(len(df_plot.index)))
                ax.set_xticklabels(df_plot.columns, rotation=90, fontsize=fs_tick, fontweight=fw_tick)
                ax.set_yticklabels(df_plot.index, fontsize=fs_tick, fontweight=fw_tick)

                if u.get('grid', True):
                    ax.set_xticks(np.arange(df_plot.shape[1] + 1) - 0.5, minor=True)
                    ax.set_yticks(np.arange(df_plot.shape[0] + 1) - 0.5, minor=True)
                    ax.grid(which="minor", color="white", linestyle='-', linewidth=2)
                    ax.tick_params(which="minor", bottom=False, left=False)

                ax.set_title("")
                cbar = plt.colorbar(im, cax=divider.append_axes("right", size="3%", pad=0.1))
                cbar.set_label("Inhibition Rate" if is_inhib else "Value", fontsize=fs_label, fontweight=fw_label, labelpad=10)

            else:
                k = int(u.get('k', 4))
                if len(df) >= k:
                    clusters = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(df)
                    coords = PCA(n_components=2).fit_transform(df)
                    try: cmap_km = matplotlib.colormaps["tab10"]
                    except: cmap_km = cm.get_cmap("tab10")

                    ax.scatter(coords[:, 0], coords[:, 1], c=clusters, cmap=cmap_km, s=u.get('ms', 120), edgecolors='white', alpha=0.9)
                    for i, txt in enumerate(df.index): ax.annotate(txt, (coords[i, 0], coords[i, 1]), xytext=(6, 6), textcoords='offset points', fontsize=fs_tick, fontweight=fw_annot)
                    ax.set_title(f"K-Means PCA Scatter (K={k})", fontweight=fw_title, fontsize=fs_title)
                    if u.get('grid', True): ax.grid(True, ls='--', alpha=0.5)

            fig.tight_layout()
            out_name = f"plot_Heatmap_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150)
            fig.clf()

            return out_path, "🔥 【BLI 表位聚类/热图分析完毕】<br>已根据全局参数完成绘图。"

        except Exception as e:
            return "", f"热图生成引擎执行失败: {str(e)}"