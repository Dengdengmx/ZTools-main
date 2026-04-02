# plugins/plugin_elisa.py
"""
ELISA 4PL 拟合分析插件
支持 ELISA 数据的四参数拟合、EC50 计算、图表渲染等功能。
(极致紧凑亮色 UI 优化版，核心算法保持纯净)
"""

import os
import json
from io import StringIO
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.cm as cm
import matplotlib
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator, MaxNLocator, LogLocator, NullLocator
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDialog, QScrollArea,
                             QColorDialog, QMessageBox, QFileDialog, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt

from qfluentwidgets import (LineEdit, SpinBox, DoubleSpinBox, CheckBox, ComboBox,
                            BodyLabel, PushButton, PlainTextEdit, PrimaryPushButton,
                            StrongBodyLabel, CardWidget, ListWidget, FluentIcon as FIF)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig


# ==========================================
# 核心算法区 (原生算法，保持纯净，零修改)
# ==========================================
def safe_load_dataframe(filepath):
    if filepath.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath, header=None, engine='openpyxl')
    for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "latin1"]:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                first_line = f.readline()
            sep = '\t' if '\t' in first_line else ','
            return pd.read_csv(filepath, header=None, encoding=enc, sep=sep)
        except:
            continue
    return pd.read_csv(filepath, header=None, encoding='utf-8', errors='replace')

def fourPL(x, A, B, C, D):
    return D + (A - D) / (1 + (x / (C + 1e-10))**B)

def r_squared(y_true, y_pred):
    residuals = y_true - y_pred
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    return 1 - (ss_res / ss_tot)

def scan_for_plate_blocks(df_raw):
    valid_blocks = []
    rows, cols = df_raw.shape
    if rows < 8:
        return []
    for c in range(cols):
        col_data = df_raw.iloc[:, c].astype(str).str.strip().str.upper().values
        for r in range(rows - 7):
            if col_data[r] == 'A':
                if all(col_data[r + 1 + i] == char for i, char in enumerate(['B', 'C', 'D', 'E', 'F', 'G', 'H'])):
                    if r > 0:
                        end_col = min(c + 13, cols)
                        headers = df_raw.iloc[r - 1, c + 1: end_col].values
                        block = df_raw.iloc[r: r + 8, c + 1: end_col].copy()
                        block.columns = headers
                        block = block.apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='any')
                        if not block.empty:
                            valid_blocks.append(block)
    return valid_blocks


# ==========================================
# 前端：ELISA UI (极限紧凑与亮色美化)
# ==========================================
class ElisaUI(BasePluginUI):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="elisa_analyzer", plugin_name="ELISA 4PL 拟合分析", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.file_list = []
        self.custom_styles = {}
        self.fit_results = []
        self.setAcceptDrops(True)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        h_tools = QHBoxLayout()
        btn_import_config = PushButton("📂 载入模板", icon=FIF.FOLDER)
        btn_export_config = PushButton("💾 保存模板", icon=FIF.SAVE)
        btn_import_config.clicked.connect(self.import_config)
        btn_export_config.clicked.connect(self.export_config)
        h_tools.addWidget(btn_import_config)
        h_tools.addWidget(btn_export_config)
        self.param_layout.insertLayout(0, h_tools)

        if not self.is_setting_mode:
            group_data, layout_data = self.create_group("1. 数据池 (支持批量拖拽与发送)")
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_add = PrimaryPushButton("导入...", icon=FIF.DOWNLOAD)
            btn_add.clicked.connect(self.open_files)
            btn_clear = PushButton("清空", icon=FIF.DELETE)
            btn_clear.clicked.connect(self.clear_files)
            btn_row.addWidget(btn_add)
            btn_row.addWidget(btn_clear)
            layout_data.addLayout(btn_row)

            self.list_widget = ListWidget()
            self.list_widget.setFixedHeight(65)
            self.list_widget.itemClicked.connect(self.trigger_render)
            layout_data.addWidget(self.list_widget)
            self.add_param_widget(group_data)

        group_wh, layout_wh = self.create_group("2. 全局画板尺寸 (英寸)")
        h_wh = QHBoxLayout()
        h_wh.setContentsMargins(0, 0, 0, 0)
        self.spin_w = DoubleSpinBox()
        self.spin_w.setRange(1.0, 50.0); self.spin_w.setValue(7.0); self.spin_w.setSingleStep(0.5)
        self.spin_h = DoubleSpinBox()
        self.spin_h.setRange(1.0, 50.0); self.spin_h.setValue(5.0); self.spin_h.setSingleStep(0.5)
        h_wh.addWidget(BodyLabel("W:")); h_wh.addWidget(self.spin_w, 1)
        h_wh.addSpacing(5)
        h_wh.addWidget(BodyLabel("H:")); h_wh.addWidget(self.spin_h, 1)
        layout_wh.addLayout(h_wh)
        self.add_param_widget(group_wh)

        group_param, layout_param = self.create_group("3. 专属参数配置")
        self.add_param_widget(group_param)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(4) # 【优化】紧凑间距

        self.text_data = PlainTextEdit()
        self.text_data.setPlaceholderText("覆盖数据：可直接粘贴文本矩阵...")
        self.text_data.setFixedHeight(50) # 【优化】压榨高度
        self.parse_lbl = BodyLabel("状态: 未解析")
        self.parse_lbl.setStyleSheet("color: #666; font-size: 11px;")
        if not self.is_setting_mode:
            scroll_layout.addWidget(self.text_data)
            scroll_layout.addWidget(self.parse_lbl)

        self.start = LineEdit(); self.start.setText("1000"); self.start.setFixedWidth(55)
        self.dil = LineEdit(); self.dil.setText("3"); self.dil.setFixedWidth(40)
        self.unit = LineEdit(); self.unit.setText("ng/mL"); self.unit.setFixedWidth(60)
        h1 = QHBoxLayout(); h1.setSpacing(4)
        h1.addWidget(BodyLabel("起始:")); h1.addWidget(self.start)
        h1.addWidget(BodyLabel("倍数:")); h1.addWidget(self.dil)
        h1.addWidget(BodyLabel("单位:")); h1.addWidget(self.unit); h1.addStretch(1)
        scroll_layout.addLayout(h1)

        self.merge = CheckBox("合并文件列表中的所有孔板")
        self.merge.setChecked(True)
        scroll_layout.addWidget(self.merge)

        scroll_layout.addSpacing(8) # 【优化】层级分隔
        scroll_layout.addWidget(StrongBodyLabel("坐标轴设置"))

        self.title = LineEdit(); self.title.setText("ELISA 4PL Fit")
        self.add_row(scroll_layout, "主标题:", self.title)

        self.xl = LineEdit(); self.xl.setText("Concentration")
        self.yl = LineEdit(); self.yl.setText("OD450")
        self.add_row(scroll_layout, "X轴名:", self.xl, "Y轴名:", self.yl)

        self.x1 = LineEdit(); self.x2 = LineEdit()
        self.add_row(scroll_layout, "X范围起:", self.x1, "止:", self.x2)

        self.y1 = LineEdit(); self.y2 = LineEdit()
        self.add_row(scroll_layout, "Y范围起:", self.y1, "止:", self.y2)

        scroll_layout.addSpacing(8) # 【优化】层级分隔
        scroll_layout.addWidget(StrongBodyLabel("外观与高级自定义"))

        h_chk1 = QHBoxLayout(); h_chk1.setSpacing(4)
        self.log = CheckBox("Log X"); self.log.setChecked(True)
        self.leg = CheckBox("图例"); self.leg.setChecked(True)
        self.ec50 = CheckBox("EC50"); self.ec50.setChecked(True)
        self.grid = CheckBox("网格")
        h_chk1.addWidget(self.log); h_chk1.addWidget(self.leg); h_chk1.addWidget(self.ec50); h_chk1.addWidget(self.grid)
        scroll_layout.addLayout(h_chk1)

        self.diff = CheckBox("自动分配不同散点形状")
        self.diff.setChecked(True)
        scroll_layout.addWidget(self.diff)

        lbl_bold = BodyLabel("独立加粗控制:"); lbl_bold.setStyleSheet("color:#666; font-size:11px;")
        scroll_layout.addWidget(lbl_bold)

        h_bold = QHBoxLayout(); h_bold.setSpacing(4)
        self.b_title = CheckBox("标题"); self.b_title.setChecked(True)
        self.b_label = CheckBox("轴名"); self.b_label.setChecked(True)
        self.b_tick = CheckBox("刻度")
        self.b_leg = CheckBox("图例")
        h_bold.addWidget(self.b_title); h_bold.addWidget(self.b_label); h_bold.addWidget(self.b_tick); h_bold.addWidget(self.b_leg)
        scroll_layout.addLayout(h_bold)

        self.ms = SpinBox(); self.ms.setRange(10, 200); self.ms.setValue(30)
        self.lw = DoubleSpinBox(); self.lw.setRange(0.5, 5.0); self.lw.setValue(2.0)
        self.add_row(scroll_layout, "点大小:", self.ms, "线宽:", self.lw)

        self.ls = ComboBox(); self.ls.addItems(["-", "--", "-.", ":"])
        self.leg_loc = ComboBox(); self.leg_loc.addItems(["best", "outside", "upper right", "upper left", "lower right", "lower left", "center right", "center left"])
        h_ls = QHBoxLayout(); h_ls.setSpacing(4)
        h_ls.addWidget(BodyLabel("线型:")); h_ls.addWidget(self.ls, 1)
        h_ls.addWidget(BodyLabel("图例位:")); h_ls.addWidget(self.leg_loc, 2)
        scroll_layout.addLayout(h_ls)

        btn_custom = PushButton("🎨 自定义各个样品颜色与形状")
        btn_custom.clicked.connect(self.open_style_customizer)
        scroll_layout.addWidget(btn_custom)

        lbl_fs = BodyLabel("字号控制:"); lbl_fs.setStyleSheet("color:#666; font-size:11px; margin-top:5px;")
        scroll_layout.addWidget(lbl_fs)

        self.fs_title = SpinBox(); self.fs_title.setRange(8, 30); self.fs_title.setValue(14)
        self.fs_label = SpinBox(); self.fs_label.setRange(6, 24); self.fs_label.setValue(12)
        self.fs_tick = SpinBox(); self.fs_tick.setRange(6, 24); self.fs_tick.setValue(10)
        self.fs_leg = SpinBox(); self.fs_leg.setRange(6, 24); self.fs_leg.setValue(9)

        h_fs1 = QHBoxLayout(); h_fs1.setSpacing(4)
        h_fs1.addWidget(BodyLabel("标题:")); h_fs1.addWidget(self.fs_title)
        h_fs1.addWidget(BodyLabel("轴名:")); h_fs1.addWidget(self.fs_label)
        scroll_layout.addLayout(h_fs1)

        h_fs2 = QHBoxLayout(); h_fs2.setSpacing(4)
        h_fs2.addWidget(BodyLabel("刻度:")); h_fs2.addWidget(self.fs_tick)
        h_fs2.addWidget(BodyLabel("图例:")); h_fs2.addWidget(self.fs_leg)
        scroll_layout.addLayout(h_fs2)

        lbl_tk = BodyLabel("刻度与边框控制:"); lbl_tk.setStyleSheet("color:#666; font-size:11px; margin-top:5px;")
        scroll_layout.addWidget(lbl_tk)

        h_border = QHBoxLayout(); h_border.setSpacing(4)
        self.tk_dir = ComboBox(); self.tk_dir.addItems(["in", "out"])
        self.top = CheckBox("上边框"); self.top.setChecked(True)
        self.right = CheckBox("右边框"); self.right.setChecked(True)
        h_border.addWidget(BodyLabel("朝向:")); h_border.addWidget(self.tk_dir)
        h_border.addWidget(self.top); h_border.addWidget(self.right)
        scroll_layout.addLayout(h_border)

        self.x_maj = SpinBox(); self.x_maj.setRange(2, 20); self.x_maj.setValue(6)
        self.x_min = SpinBox(); self.x_min.setRange(0, 10); self.x_min.setValue(0)
        self.y_maj = SpinBox(); self.y_maj.setRange(2, 20); self.y_maj.setValue(5)
        self.y_min = SpinBox(); self.y_min.setRange(0, 10); self.y_min.setValue(2)

        h_tk1 = QHBoxLayout(); h_tk1.setSpacing(4)
        h_tk1.addWidget(BodyLabel("X(主/次):")); h_tk1.addWidget(self.x_maj); h_tk1.addWidget(self.x_min)
        scroll_layout.addLayout(h_tk1)

        h_tk2 = QHBoxLayout(); h_tk2.setSpacing(4)
        h_tk2.addWidget(BodyLabel("Y(主/次):")); h_tk2.addWidget(self.y_maj); h_tk2.addWidget(self.y_min)
        scroll_layout.addLayout(h_tk2)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout_param.addWidget(scroll)

        if self.is_setting_mode:
            self.btn_save_config = PrimaryPushButton("💾 确认并保存为全局默认参数", icon=FIF.SAVE)
            self.btn_save_config.setFixedHeight(45)
            self.btn_save_config.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(self.btn_save_config)
            return

        self.btn_plot = PrimaryPushButton("⚡ 渲染图表", icon=FIF.PLAY)
        self.btn_plot.setFixedHeight(35)
        self.btn_plot.clicked.connect(self.trigger_render)
        self.param_layout.addWidget(self.btn_plot)

        # ========== 右侧画板 (纯白卡片式原生质感) ==========
        self.fig = Figure(dpi=120)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.canvas_container = QWidget()
        # 【极致优化】抛弃粗糙的 #f0f0f0，赋予画布阴影边框质感
        self.canvas_container.setStyleSheet("background-color: #FFFFFF; border: 1px solid #EAEAEA; border-radius: 8px;")
        canvas_layout = QVBoxLayout(self.canvas_container)
        canvas_layout.setContentsMargins(10, 10, 10, 10)
        canvas_layout.setAlignment(Qt.AlignCenter)
        canvas_layout.addWidget(self.canvas)

        self.scroll_canvas = QScrollArea()
        self.scroll_canvas.setWidgetResizable(True)
        self.scroll_canvas.setFrameShape(QScrollArea.NoFrame)
        # 【极致优化】外层容器融入 Fluent 亮色环境
        self.scroll_canvas.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.scroll_canvas.setWidget(self.canvas_container)

        self.toolbar = NavigationToolbar(self.canvas, self)

        export_layout = QHBoxLayout()
        export_layout.addStretch()
        self.chk_trans = CheckBox("透明背景")
        export_layout.addWidget(self.chk_trans)
        export_layout.addSpacing(15)
        self.combo_fmt = ComboBox()
        self.combo_fmt.addItems(["pdf", "png", "svg"])
        export_layout.addWidget(StrongBodyLabel("导出格式:"))
        export_layout.addWidget(self.combo_fmt)
        btn_export = PushButton("保存图表", icon=FIF.SAVE)
        btn_export.clicked.connect(self.export_plot)
        export_layout.addWidget(btn_export)

        btn_csv = PushButton("💾 导出 EC50 (.csv)")
        btn_csv.clicked.connect(self.save_csv)
        export_layout.addWidget(btn_csv)

        self.get_canvas_layout().addWidget(self.toolbar)
        self.get_canvas_layout().addWidget(self.scroll_canvas)
        self.get_canvas_layout().addLayout(export_layout)

    # ------------------------------------
    # 数据摄取与配置 (保持原有逻辑)
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
            self.list_widget.clear()
            self.fig.clear()
            self.canvas.draw()
            self.text_data.clear()
            self.parse_lbl.setText("状态: 数据已清空")

    def get_float(self, widget, default=0.0):
        try: return float(widget.text())
        except: return default

    def _load_config(self):
        config = GlobalConfig.get_all_plugin_settings(self.plugin_id)
        if config: self.apply_config_dict(config)
        self.custom_styles = config.get("custom_styles", {}) if config else {}

    def _save_config(self):
        config = self.get_config_dict()
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def get_config_dict(self):
        return {
            "start": self.start.text(), "dil": self.dil.text(), "unit": self.unit.text(), "merge": self.merge.isChecked(),
            "title": self.title.text(), "xl": self.xl.text(), "yl": self.yl.text(), "x1": self.x1.text(), "x2": self.x2.text(), "y1": self.y1.text(), "y2": self.y2.text(),
            "spin_w": self.spin_w.value(), "spin_h": self.spin_h.value(), "log": self.log.isChecked(), "leg": self.leg.isChecked(),
            "ec50": self.ec50.isChecked(), "grid": self.grid.isChecked(), "diff": self.diff.isChecked(),
            "b_title": self.b_title.isChecked(), "b_label": self.b_label.isChecked(), "b_tick": self.b_tick.isChecked(), "b_leg": self.b_leg.isChecked(),
            "ms": self.ms.value(), "lw": self.lw.value(), "ls": self.ls.currentText(), "leg_loc": self.leg_loc.currentText(),
            "fs_title": self.fs_title.value(), "fs_label": self.fs_label.value(), "fs_tick": self.fs_tick.value(), "fs_leg": self.fs_leg.value(),
            "tk_dir": self.tk_dir.currentText(), "top": self.top.isChecked(), "right": self.right.isChecked(),
            "x_maj": self.x_maj.value(), "x_min": self.x_min.value(), "y_maj": self.y_maj.value(), "y_min": self.y_min.value(),
            "custom_styles": self.custom_styles
        }

    def apply_config_dict(self, data):
        self.start.setText(data.get("start", "1000")); self.dil.setText(data.get("dil", "3")); self.unit.setText(data.get("unit", "ng/mL")); self.merge.setChecked(data.get("merge", True))
        self.title.setText(data.get("title", "ELISA 4PL Fit")); self.xl.setText(data.get("xl", "Concentration")); self.yl.setText(data.get("yl", "OD450"))
        self.x1.setText(data.get("x1", "")); self.x2.setText(data.get("x2", "")); self.y1.setText(data.get("y1", "")); self.y2.setText(data.get("y2", ""))
        self.spin_w.setValue(data.get("spin_w", 7.0)); self.spin_h.setValue(data.get("spin_h", 5.0))
        self.log.setChecked(data.get("log", True)); self.leg.setChecked(data.get("leg", True)); self.ec50.setChecked(data.get("ec50", True)); self.grid.setChecked(data.get("grid", False)); self.diff.setChecked(data.get("diff", True))
        self.b_title.setChecked(data.get("b_title", True)); self.b_label.setChecked(data.get("b_label", True)); self.b_tick.setChecked(data.get("b_tick", False)); self.b_leg.setChecked(data.get("b_leg", False))
        self.ms.setValue(data.get("ms", 30)); self.lw.setValue(data.get("lw", 2.0)); self.ls.setCurrentText(data.get("ls", "-")); self.leg_loc.setCurrentText(data.get("leg_loc", "best"))
        self.fs_title.setValue(data.get("fs_title", 14)); self.fs_label.setValue(data.get("fs_label", 12)); self.fs_tick.setValue(data.get("fs_tick", 10)); self.fs_leg.setValue(data.get("fs_leg", 9))
        self.tk_dir.setCurrentText(data.get("tk_dir", "in")); self.top.setChecked(data.get("top", True)); self.right.setChecked(data.get("right", True))
        self.x_maj.setValue(data.get("x_maj", 6)); self.x_min.setValue(data.get("x_min", 0)); self.y_maj.setValue(data.get("y_maj", 5)); self.y_min.setValue(data.get("y_min", 2))
        self.custom_styles = data.get("custom_styles", {})

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 ELISA 参数模板", "elisa_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入 ELISA 参数模板", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f: self.apply_config_dict(json.load(f))
            if not self.is_setting_mode: self.trigger_render()

    def save_settings_and_close(self):
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog): parent_dlg.accept()

    def get_elisa_df(self):
        raw_text = self.text_data.toPlainText().strip()
        if raw_text:
            try:
                df_raw = pd.read_csv(StringIO(raw_text), sep='\t', header=None, engine='python')
                if df_raw.shape[1] < 2: df_raw = pd.read_csv(StringIO(raw_text), sep=r'\s+', header=None, engine='python')
            except: df_raw = pd.read_csv(StringIO(raw_text), sep=',', header=None, engine='python')
            blocks = scan_for_plate_blocks(df_raw)
            if blocks: return pd.concat(blocks, axis=1) if self.merge.isChecked() else blocks[-1]
            header_idx = 0
            for idx, row in df_raw.head(30).iterrows():
                if any(k in str(row.values).lower() for k in ['conc', 'concentration']):
                    header_idx = idx; break
            df_data = df_raw.iloc[header_idx + 1:].copy()
            df_data.columns = df_raw.iloc[header_idx]
            if len(df_data.columns) > 0: df_data.set_index(df_data.columns[0], inplace=True)
            df_data = df_data.apply(pd.to_numeric, errors='coerce').dropna(how='all', axis=1)
            if df_data.empty: raise ValueError("粘贴的数据未能提取出有效数值！")
            return df_data
        else:
            if not self.file_list: raise ValueError("请先粘贴数据，或在上方添加文件！")
            all_dfs = []
            for fp in self.file_list:
                blocks = scan_for_plate_blocks(safe_load_dataframe(fp))
                if blocks: all_dfs.extend(blocks)
            if not all_dfs: raise ValueError("所有文件均未检测到标准的 96孔板格式！")
            if self.merge.isChecked(): return pd.concat(all_dfs, axis=1)
            else:
                row = self.list_widget.currentRow()
                if row >= 0:
                    blocks = scan_for_plate_blocks(safe_load_dataframe(self.file_list[row]))
                    if blocks: return blocks[-1]
                return all_dfs[-1]

    # ------------------------------------
    # 绘图核心与弹窗
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
        fmt = self.combo_fmt.currentText()
        is_transparent = self.chk_trans.isChecked()
        row = self.list_widget.currentRow()
        default_name = os.path.splitext(self.list_widget.item(max(0, row)).text())[0] + f"_ELISA.{fmt}" if self.list_widget.count() > 0 else f"ELISA_Plot.{fmt}"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出高清图表", default_name, f"Images (*.{fmt})")
        if file_path:
            try:
                self.fig.savefig(file_path, dpi=600, bbox_inches="tight", transparent=is_transparent)
                QMessageBox.information(self, "成功", f"图表已成功导出为:\n{file_path}")
            except Exception as e: QMessageBox.critical(self, "导出失败", str(e))

    def save_csv(self):
        if not self.fit_results: return
        path, _ = QFileDialog.getSaveFileName(self, "导出 EC50 数据", "ELISA_FitResult.csv", "CSV Files (*.csv)")
        if path: pd.DataFrame(self.fit_results).to_csv(path, index=False)

    def render_plot(self):
        if self.is_setting_mode: return
        self.fig.clear()
        self.fig.set_size_inches(self.spin_w.value(), self.spin_h.value())
        self.ax = self.fig.add_subplot(111)
        self.fit_results = []

        try:
            df_data = self.get_elisa_df()
            self.parse_lbl.setText(f"✔ 解析成功: 检测到 {df_data.shape[1]} 列数据")
            self.parse_lbl.setStyleSheet("color: #107C10; font-weight: bold;")
        except Exception as e:
            self.parse_lbl.setText(f"❌ 解析失败: {str(e)}")
            self.parse_lbl.setStyleSheet("color: red; font-weight: bold;")
            self.ax.text(0.5, 0.5, f"数据错误:\n{str(e)}", ha='center', va='center')
            self.canvas.draw()
            return

        title_text = "ELISA_4PL_Fit"
        if not self.text_data.toPlainText().strip():
            row = self.list_widget.currentRow()
            if 0 <= row < len(self.file_list): title_text = os.path.splitext(os.path.basename(self.file_list[row]))[0]

        start, dil = self.get_float(self.start, 1000), self.get_float(self.dil, 3)
        x_arr = np.array([start / (dil ** i) for i in range(len(df_data))])

        is_log = self.log.isChecked()
        fw_title = 'bold' if self.b_title.isChecked() else 'normal'
        fw_label = 'bold' if self.b_label.isChecked() else 'normal'
        fw_tick = 'bold' if self.b_tick.isChecked() else 'normal'
        fw_leg = 'bold' if self.b_leg.isChecked() else 'normal'

        try: colors = matplotlib.colormaps['tab10']
        except: colors = cm.get_cmap('tab10')
        default_markers = ['o', 's', '^', 'v', 'D', 'p', '*', 'h', '<', '>']

        for i, col_name in enumerate(df_data.columns):
            y_raw = df_data.iloc[:, i].values
            curr_x = x_arr[:len(y_raw)] if len(y_raw) < len(x_arr) else x_arr
            mask = ~np.isnan(y_raw[:len(curr_x)])
            x_fit, y_fit = curr_x[mask], y_raw[:len(curr_x)][mask]

            col_c = self.custom_styles.get(col_name, {}).get('color', matplotlib.colors.to_hex(colors(i % 10)))
            col_m = self.custom_styles.get(col_name, {}).get('marker', default_markers[i % len(default_markers)] if self.diff.isChecked() else 'o')

            self.ax.scatter(x_fit, y_fit, color=col_c, marker=col_m, s=self.ms.value(), edgecolors='white', zorder=3)
            res_dict = {'Sample': col_name, 'R2': '-', 'EC50': '-', 'A': '-', 'B': '-', 'C': '-', 'D': '-'}
            lbl = str(col_name)

            if len(x_fit) >= 4:
                try:
                    p0 = [min(y_fit), 1.0, np.median(x_fit), max(y_fit)]
                    params, _ = curve_fit(fourPL, x_fit, y_fit, p0=p0, maxfev=5000)
                    x_sm = np.logspace(np.log10(min(x_fit) / 2), np.log10(max(x_fit) * 2), 100) if is_log else np.linspace(0, max(x_fit) * 1.1, 100)
                    if self.ec50.isChecked(): lbl += f" ($\\mathbf{{EC_{{50}}={params[2]:.2f}}}$)" if fw_leg == 'bold' else f" ($EC_{{50}}={params[2]:.2f}$)"
                    self.ax.plot(x_sm, fourPL(x_sm, *params), color=col_c, lw=self.lw.value(), ls=self.ls.currentText(), label=lbl, zorder=2)
                    res_dict.update({'R2': r_squared(y_fit, fourPL(x_fit, *params)), 'EC50': params[2]})
                except:
                    self.ax.plot(x_fit, y_fit, color=col_c, ls='--', lw=1, label=lbl + " (Fit Fail)")
            else:
                self.ax.plot(x_fit, y_fit, color=col_c, ls=':', lw=1, label=lbl + " (<4 pts)")
            self.fit_results.append(res_dict)

        self.ax.set_title(self.title.text() if self.title.text() else title_text, fontsize=self.fs_title.value(), fontweight=fw_title, pad=10)
        self.ax.set_xlabel(self.xl.text(), fontsize=self.fs_label.value(), fontweight=fw_label)
        self.ax.set_ylabel(self.yl.text(), fontsize=self.fs_label.value(), fontweight=fw_label)

        if self.x1.text(): self.ax.set_xlim(left=self.get_float(self.x1))
        if self.x2.text(): self.ax.set_xlim(right=self.get_float(self.x2))
        if self.y1.text(): self.ax.set_ylim(bottom=self.get_float(self.y1))
        if self.y2.text(): self.ax.set_ylim(top=self.get_float(self.y2))

        if is_log:
            self.ax.set_xscale('log')
            self.ax.xaxis.set_major_formatter(ScalarFormatter())
            self.ax.ticklabel_format(style='plain', axis='x')

        try:
            nx_maj, nx_min = self.x_maj.value(), self.x_min.value()
            ny_maj, ny_min = self.y_maj.value(), self.y_min.value()
            self.ax.yaxis.set_major_locator(MaxNLocator(nbins=ny_maj))
            self.ax.yaxis.set_minor_locator(NullLocator() if ny_min == 0 else AutoMinorLocator(ny_min))
            if not is_log:
                self.ax.xaxis.set_major_locator(MaxNLocator(nbins=nx_maj))
                self.ax.xaxis.set_minor_locator(NullLocator() if nx_min == 0 else AutoMinorLocator(nx_min))
            else:
                self.ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=nx_maj + 2))
                self.ax.xaxis.set_minor_locator(NullLocator() if nx_min == 0 else LogLocator(base=10.0, subs='auto'))
        except: pass

        top_on, right_on = self.top.isChecked(), self.right.isChecked()
        self.ax.tick_params(which='both', direction=self.tk_dir.currentText(), top=top_on, right=right_on, labelsize=self.fs_tick.value())
        self.ax.spines['top'].set_visible(top_on); self.ax.spines['right'].set_visible(right_on)
        for sp in self.ax.spines.values(): sp.set_linewidth(1.2)
        for label in self.ax.get_xticklabels() + self.ax.get_yticklabels(): label.set_fontweight(fw_tick)

        if self.leg.isChecked():
            loc = self.leg_loc.currentText()
            leg = self.ax.legend(frameon=False, fontsize=self.fs_leg.value(), bbox_to_anchor=(1.02, 1) if loc == 'outside' else None, loc='upper left' if loc == 'outside' else loc)
            for text in leg.get_texts(): text.set_fontweight(fw_leg)

        if self.grid.isChecked():
            self.ax.grid(True, which='major', ls='--', alpha=0.5)
            if is_log: self.ax.grid(True, which='minor', ls=':', alpha=0.2)

        self.fig.tight_layout()
        self.canvas.draw()

    def open_style_customizer(self):
        if self.is_setting_mode:
            QMessageBox.information(self, "提示", "请在工作站中导入数据后再配置独立样品颜色。")
            return
        try: df_data = self.get_elisa_df()
        except Exception as e:
            QMessageBox.warning(self, "提示", f"获取失败:\n{e}")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("个性化配置")
        dlg.resize(400, 500)
        dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }") # 【优化】弹窗背景锁定亮色
        dlg_layout = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        content = QWidget()
        vbox = QVBoxLayout(content)
        marker_opts = ['o', 's', '^', 'v', 'D', 'p', '*', 'h', '<', '>', 'x', '+']
        self.temp_vars = {}
        try: colors = matplotlib.colormaps['tab10']
        except: colors = cm.get_cmap('tab10')

        for i, col_name in enumerate(df_data.columns):
            row_l = QHBoxLayout()
            lbl = BodyLabel(str(col_name))
            lbl.setFixedWidth(120)
            row_l.addWidget(lbl)

            current_color = self.custom_styles.get(col_name, {}).get('color', matplotlib.colors.to_hex(colors(i % 10)))
            btn_color = PushButton("")
            btn_color.setFixedWidth(50)
            btn_color.setStyleSheet(f"background-color: {current_color}; border: 1px solid #ccc;")
            btn_color.property_color = current_color

            def make_color_picker(btn):
                def pick():
                    color = QColorDialog.getColor()
                    if color.isValid():
                        btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #ccc;")
                        btn.property_color = color.name()
                return pick

            btn_color.clicked.connect(make_color_picker(btn_color))
            row_l.addWidget(btn_color)

            cb_marker = ComboBox()
            cb_marker.addItems(marker_opts)
            cb_marker.setCurrentText(self.custom_styles.get(col_name, {}).get('marker', marker_opts[i % len(marker_opts)]))
            row_l.addWidget(cb_marker)

            row_w = QWidget()
            row_w.setLayout(row_l)
            vbox.addWidget(row_w)
            self.temp_vars[col_name] = {'btn': btn_color, 'cb': cb_marker}

        vbox.addStretch(1)
        scroll.setWidget(content)
        dlg_layout.addWidget(scroll)

        btn_apply = PushButton("✅ 应用并刷新")
        def apply_styles():
            for name, w in self.temp_vars.items():
                self.custom_styles.setdefault(name, {})
                self.custom_styles[name]['color'] = w['btn'].property_color
                self.custom_styles[name]['marker'] = w['cb'].currentText()
            dlg.accept()
            self.trigger_render()
        btn_apply.clicked.connect(apply_styles)
        dlg_layout.addWidget(btn_apply)
        dlg.exec_()


# ==========================================
# 后端：插件描述器
# ==========================================
class ElisaPlugin(BasePlugin):
    plugin_id = "elisa_analyzer"
    plugin_name = "ELISA 4PL 拟合分析"
    icon = "📊"
    trigger_tag = "ELISA 检测"

    def get_ui(self, parent=None):
        return ElisaUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        card = PrimaryPushSettingCard("配置全局默认参数", FIF.EDIT, "📊 ELISA 4PL 拟合分析", "修改工作站中 ELISA 图谱的全局默认线宽、字号与外观偏好", parent)

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("ELISA 全局默认参数预设中心")
            dlg.resize(460, 750)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }") # 【优化】弹窗背景锁定亮色
            layout = QVBoxLayout(dlg)
            settings_ui = ElisaUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        """后台自动处理 (逻辑保持绝对纯净)"""
        try:
            config = GlobalConfig.get_all_plugin_settings("elisa_analyzer")
            u = config if config else {}

            df_raw = safe_load_dataframe(file_path)
            blocks = scan_for_plate_blocks(df_raw)
            if not blocks: return "", "【ELISA 分析跳过】未能从文件中检测到标准的 96孔板格式 (A-H行)。"

            df_data = pd.concat(blocks, axis=1) if u.get("merge", True) else blocks[-1]
            start, dil = float(u.get('start', 1000)), float(u.get('dil', 3))
            x_arr = np.array([start / (dil ** i) for i in range(len(df_data))])

            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt

            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False

            fig = Figure(figsize=(u.get("spin_w", 7.0), u.get("spin_h", 5.0)), dpi=150)
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)

            is_log = u.get('log', True)
            fw_title = 'bold' if u.get('b_title', True) else 'normal'
            fw_label = 'bold' if u.get('b_label', True) else 'normal'
            fw_tick = 'bold' if u.get('b_tick', False) else 'normal'
            fw_leg = 'bold' if u.get('b_leg', False) else 'normal'

            try: colors = matplotlib.colormaps['tab10']
            except: colors = cm.get_cmap('tab10')
            default_markers = ['o', 's', '^', 'v', 'D', 'p', '*', 'h', '<', '>']
            custom_styles = u.get("custom_styles", {})

            fit_texts = []

            for i, col_name in enumerate(df_data.columns):
                y_raw = df_data.iloc[:, i].values
                curr_x = x_arr[:len(y_raw)] if len(y_raw) < len(x_arr) else x_arr
                mask = ~np.isnan(y_raw[:len(curr_x)])
                x_fit, y_fit = curr_x[mask], y_raw[:len(curr_x)][mask]

                col_c = custom_styles.get(str(col_name), {}).get('color', matplotlib.colors.to_hex(colors(i % 10)))
                col_m = custom_styles.get(str(col_name), {}).get('marker', default_markers[i % len(default_markers)] if u.get('diff', True) else 'o')

                ax.scatter(x_fit, y_fit, color=col_c, marker=col_m, s=u.get('ms', 30), edgecolors='white', zorder=3)
                lbl = str(col_name)

                if len(x_fit) >= 4:
                    try:
                        p0 = [min(y_fit), 1.0, np.median(x_fit), max(y_fit)]
                        params, _ = curve_fit(fourPL, x_fit, y_fit, p0=p0, maxfev=5000)
                        x_sm = np.logspace(np.log10(min(x_fit) / 2), np.log10(max(x_fit) * 2), 100) if is_log else np.linspace(0, max(x_fit) * 1.1, 100)
                        if u.get('ec50', True): lbl += f" ($\\mathbf{{EC_{{50}}={params[2]:.2f}}}$)" if fw_leg == 'bold' else f" ($EC_{{50}}={params[2]:.2f}$)"
                        ax.plot(x_sm, fourPL(x_sm, *params), color=col_c, lw=u.get('lw', 2.0), ls=u.get('ls', '-'), label=lbl, zorder=2)
                        r2 = r_squared(y_fit, fourPL(x_fit, *params))
                        fit_texts.append(f"[{col_name}] EC50: {params[2]:.2f}, R²: {r2:.3f}")
                    except Exception:
                        ax.plot(x_fit, y_fit, color=col_c, ls='--', lw=1, label=lbl + " (Fit Fail)")
                        fit_texts.append(f"[{col_name}] 拟合失败")
                else:
                    ax.plot(x_fit, y_fit, color=col_c, ls=':', lw=1, label=lbl + " (<4 pts)")
                    fit_texts.append(f"[{col_name}] 数据点不足")

            title_text = os.path.splitext(os.path.basename(file_path))[0]
            ax.set_title(u.get('title', "ELISA 4PL Fit") if u.get('title', "") else title_text, fontsize=u.get('fs_title', 14), fontweight=fw_title, pad=10)
            ax.set_xlabel(u.get('xl', "Concentration"), fontsize=u.get('fs_label', 12), fontweight=fw_label)
            ax.set_ylabel(u.get('yl', "OD450"), fontsize=u.get('fs_label', 12), fontweight=fw_label)

            if u.get('x1', ""): ax.set_xlim(left=float(u['x1']))
            if u.get('x2', ""): ax.set_xlim(right=float(u['x2']))
            if u.get('y1', ""): ax.set_ylim(bottom=float(u['y1']))
            if u.get('y2', ""): ax.set_ylim(top=float(u['y2']))

            if is_log:
                ax.set_xscale('log')
                ax.xaxis.set_major_formatter(ScalarFormatter())
                ax.ticklabel_format(style='plain', axis='x')

            try:
                nx_maj, nx_min = u.get('x_maj', 6), u.get('x_min', 0)
                ny_maj, ny_min = u.get('y_maj', 5), u.get('y_min', 2)
                ax.yaxis.set_major_locator(MaxNLocator(nbins=ny_maj))
                ax.yaxis.set_minor_locator(NullLocator() if ny_min == 0 else AutoMinorLocator(ny_min))
                if not is_log:
                    ax.xaxis.set_major_locator(MaxNLocator(nbins=nx_maj))
                    ax.xaxis.set_minor_locator(NullLocator() if nx_min == 0 else AutoMinorLocator(nx_min))
                else:
                    ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=nx_maj + 2))
                    ax.xaxis.set_minor_locator(NullLocator() if nx_min == 0 else LogLocator(base=10.0, subs='auto'))
            except: pass

            top_on, right_on = u.get('top', True), u.get('right', True)
            ax.tick_params(which='both', direction=u.get('tk_dir', 'in'), top=top_on, right=right_on, labelsize=u.get('fs_tick', 10))
            ax.spines['top'].set_visible(top_on); ax.spines['right'].set_visible(right_on)
            for sp in ax.spines.values(): sp.set_linewidth(1.2)
            for label in ax.get_xticklabels() + ax.get_yticklabels(): label.set_fontweight(fw_tick)

            if u.get('leg', True):
                loc = u.get('leg_loc', "best")
                leg = ax.legend(frameon=False, fontsize=u.get('fs_leg', 9), bbox_to_anchor=(1.02, 1) if loc == 'outside' else None, loc='upper left' if loc == 'outside' else loc)
                for text in leg.get_texts(): text.set_fontweight(fw_leg)

            if u.get('grid', False):
                ax.grid(True, which='major', ls='--', alpha=0.5)
                if is_log: ax.grid(True, which='minor', ls=':', alpha=0.2)

            fig.tight_layout()
            out_name = f"plot_ELISA_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150)
            fig.clf()

            res_text = "📊 【ELISA 4PL 拟合分析完毕】<br>" + "<br>".join(fit_texts) if fit_texts else "📊 【ELISA 4PL 拟合分析完毕】"
            return out_path, res_text

        except Exception as e:
            return "", f"ELISA 自动作图引擎执行失败: {str(e)}"