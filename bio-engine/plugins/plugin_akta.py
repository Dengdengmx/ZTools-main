# plugins/plugin_akta.py
"""
AKTA 层析分析插件
提供 AKTA 数据的可视化与拟合功能，支持工作台交互和后台自动处理。
"""

import os
# 【新增】：强制声明使用 PyQt5，防止 Matplotlib 擅自调用 PySide6 导致类型冲突
os.environ["QT_API"] = "pyqt5" 
import matplotlib
matplotlib.use('Qt5Agg') 
import json
import pandas as pd
import numpy as np
from matplotlib.ticker import AutoMinorLocator, MultipleLocator, MaxNLocator, NullLocator
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDialog, QScrollArea,
                             QMessageBox, QFileDialog, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt

from qfluentwidgets import (LineEdit, SpinBox, DoubleSpinBox, CheckBox, ComboBox,
                            BodyLabel, PushButton, PrimaryPushButton,
                            StrongBodyLabel, CardWidget, ListWidget, FluentIcon as FIF)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig


# ==========================================
# 核心算法区 (原生算法，保持纯净)
# ==========================================
def safe_load_array(filepath, skiprows=0):
    """安全加载数值数组，支持 CSV/Excel 等多种格式"""
    if filepath.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(filepath, header=None, skiprows=skiprows, engine='openpyxl')
        return df.apply(pd.to_numeric, errors='coerce').values

    for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "latin1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.readlines()
            break
        except:
            continue

    data_rows = []
    max_cols = 0
    for i, line in enumerate(content):
        if i < skiprows:
            continue
        line = line.strip()
        if not line:
            continue

        if '\t' in line:
            parts = line.split('\t')
        elif ',' in line:
            parts = line.split(',')
        elif ';' in line:
            parts = line.split(';')
        else:
            parts = line.split()

        row = []
        for p in parts:
            p = p.strip()
            try:
                row.append(float(p))
            except ValueError:
                row.append(np.nan)

        if row and not all(np.isnan(x) for x in row):
            data_rows.append(row)
            max_cols = max(max_cols, len(row))

    if not data_rows:
        return np.array([])
    return np.array([r + [np.nan] * (max_cols - len(r)) for r in data_rows], dtype=float)


# ==========================================
# 前端：工作台 UI
# ==========================================
class AktaUI(BasePluginUI):
    """AKTA 分析工作台 UI"""

    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="akta_analyzer", plugin_name="AKTA 层析分析", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.file_list = []
        self.setAcceptDrops(True)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """构建 UI 控件"""
        # ========== 左侧参数面板 ==========
        # 工具栏（导入/导出模板）
        h_tools = QHBoxLayout()
        btn_import_config = PushButton("📂 载入模板", icon=FIF.FOLDER)
        btn_export_config = PushButton("💾 保存模板", icon=FIF.SAVE)
        btn_import_config.clicked.connect(self.import_config)
        btn_export_config.clicked.connect(self.export_config)
        h_tools.addWidget(btn_import_config)
        h_tools.addWidget(btn_export_config)
        # 将工具栏添加到 param_layout 顶部（需要先获取 param_layout）
        self.param_layout.insertLayout(0, h_tools)

        # 1. 数据池（仅工作台模式）
        if not self.is_setting_mode:
            group_data, layout_data = self.create_group("1. 数据池 (支持拖拽/右键发送)")
            btn_row = QHBoxLayout()
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

        # 2. 画板尺寸
        group_wh, layout_wh = self.create_group("2. 全局画板尺寸 (英寸)")
        h_wh = QHBoxLayout()
        self.spin_w = DoubleSpinBox()
        self.spin_w.setRange(1.0, 50.0)
        self.spin_w.setValue(7.0)
        self.spin_w.setSingleStep(0.5)
        self.spin_h = DoubleSpinBox()
        self.spin_h.setRange(1.0, 50.0)
        self.spin_h.setValue(5.0)
        self.spin_h.setSingleStep(0.5)
        h_wh.addWidget(BodyLabel("W:"))
        h_wh.addWidget(self.spin_w, 1)
        h_wh.addSpacing(5)
        h_wh.addWidget(BodyLabel("H:"))
        h_wh.addWidget(self.spin_h, 1)
        layout_wh.addLayout(h_wh)
        self.add_param_widget(group_wh)

        # 3. 专属参数配置（使用滚动区域）
        group_param, layout_param = self.create_group("3. 专属参数配置")
        self.add_param_widget(group_param)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(2)

        # ---- 曲线通道设置 ----
        scroll_layout.addWidget(StrongBodyLabel("曲线通道设置"))
        self.c1x = SpinBox()
        self.c1x.setRange(0, 999)
        self.c1x.setValue(0)
        self.c1y = SpinBox()
        self.c1y.setRange(0, 999)
        self.c1y.setValue(1)
        self.l1 = LineEdit()
        self.l1.setText("UV_280")
        self.ls1 = ComboBox()
        self.ls1.addItems(["-", "--", "-.", ":"])
        h1 = QHBoxLayout()
        h1.addWidget(BodyLabel("蓝线(X/Y):"))
        h1.addWidget(self.c1x)
        h1.addWidget(self.c1y)
        h1.addWidget(BodyLabel("名:"))
        h1.addWidget(self.l1, 1)
        h1.addWidget(self.ls1)
        scroll_layout.addLayout(h1)

        self.c2x = SpinBox()
        self.c2x.setRange(0, 999)
        self.c2x.setValue(2)
        self.c2y = SpinBox()
        self.c2y.setRange(0, 999)
        self.c2y.setValue(3)
        self.l2 = LineEdit()
        self.l2.setText("UV_260")
        self.ls2 = ComboBox()
        self.ls2.addItems(["-", "--", "-.", ":"])
        h2 = QHBoxLayout()
        h2.addWidget(BodyLabel("红线(X/Y):"))
        h2.addWidget(self.c2x)
        h2.addWidget(self.c2y)
        h2.addWidget(BodyLabel("名:"))
        h2.addWidget(self.l2, 1)
        h2.addWidget(self.ls2)
        scroll_layout.addLayout(h2)

        scroll_layout.addSpacing(5)

        # ---- 坐标轴与范围 ----
        scroll_layout.addWidget(StrongBodyLabel("坐标轴与范围"))
        self.title = LineEdit()
        self.title.setText("AKTA Plot")
        self.add_row(scroll_layout, "图表标题:", self.title)

        self.xl = LineEdit()
        self.xl.setText("Elution volume (mL)")
        scroll_layout.addWidget(self.xl)

        self.x1 = LineEdit()
        self.x2 = LineEdit()
        self.add_row(scroll_layout, "X范围 起:", self.x1, "止:", self.x2)

        self.xt_step = LineEdit()
        self.xt_n = LineEdit()
        self.add_row(scroll_layout, "X主间隔:", self.xt_step, "主刻度数:", self.xt_n)

        self.yl = LineEdit()
        self.yl.setText("Absorbance (mAU)")
        scroll_layout.addWidget(self.yl)

        self.y1 = LineEdit()
        self.y2 = LineEdit()
        self.add_row(scroll_layout, "Y范围 起:", self.y1, "止:", self.y2)

        self.yt_step = LineEdit()
        self.yt_n = LineEdit()
        self.add_row(scroll_layout, "Y主间隔:", self.yt_step, "主刻度数:", self.yt_n)

        scroll_layout.addSpacing(5)

        # ---- 外观与辅助刻度 ----
        scroll_layout.addWidget(StrongBodyLabel("外观与辅助刻度"))
        lbl_bold = BodyLabel("独立加粗控制:")
        lbl_bold.setStyleSheet("color:#666; font-size:11px;")
        scroll_layout.addWidget(lbl_bold)

        h_bold = QHBoxLayout()
        self.b_title = CheckBox("标题")
        self.b_title.setChecked(True)
        self.b_label = CheckBox("轴名")
        self.b_label.setChecked(True)
        self.b_tick = CheckBox("刻度")
        self.b_leg = CheckBox("图例")
        h_bold.addWidget(self.b_title)
        h_bold.addWidget(self.b_label)
        h_bold.addWidget(self.b_tick)
        h_bold.addWidget(self.b_leg)
        scroll_layout.addLayout(h_bold)

        self.lw = DoubleSpinBox()
        self.lw.setRange(0.5, 10.0)
        self.lw.setValue(1.5)
        self.fs = SpinBox()
        self.fs.setRange(6, 40)
        self.fs.setValue(12)
        self.add_row(scroll_layout, "全局线宽:", self.lw, "全局字号:", self.fs)

        self.tk_len = SpinBox()
        self.tk_len.setRange(1, 20)
        self.tk_len.setValue(6)
        self.tk_dir = ComboBox()
        self.tk_dir.addItems(["in", "out"])
        self.min_n = SpinBox()
        self.min_n.setRange(0, 10)
        self.min_n.setValue(2)
        h_tk = QHBoxLayout()
        h_tk.addWidget(BodyLabel("刻度长:"))
        h_tk.addWidget(self.tk_len)
        h_tk.addWidget(BodyLabel("朝向:"))
        h_tk.addWidget(self.tk_dir)
        h_tk.addWidget(BodyLabel("次分段:"))
        h_tk.addWidget(self.min_n)
        scroll_layout.addLayout(h_tk)

        h_leg = QHBoxLayout()
        self.grid = CheckBox("网格线")
        h_leg.addWidget(self.grid)
        self.leg_loc = ComboBox()
        self.leg_loc.addItems(["best", "outside", "upper right", "upper left", "lower right", "lower left", "center right", "center left"])
        h_leg.addWidget(BodyLabel("图例位置:"))
        h_leg.addWidget(self.leg_loc, 1)
        scroll_layout.addLayout(h_leg)

        scroll_layout.addSpacing(5)

        # ---- 智能分析 ----
        scroll_layout.addWidget(StrongBodyLabel("智能分析"))
        h_ana = QHBoxLayout()
        self.peak = CheckBox("自动寻峰")
        self.peak.setChecked(True)
        self.auc = CheckBox("计算AUC比例")
        self.auc.setChecked(True)
        self.leg = CheckBox("显示图例")
        self.leg.setChecked(True)
        h_ana.addWidget(self.peak)
        h_ana.addWidget(self.auc)
        h_ana.addWidget(self.leg)
        scroll_layout.addLayout(h_ana)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout_param.addWidget(scroll)

        # 如果是设置模式，添加保存按钮并结束
        if self.is_setting_mode:
            self.btn_save_config = PrimaryPushButton("💾 确认并保存为全局默认参数", icon=FIF.SAVE)
            self.btn_save_config.setFixedHeight(45)
            self.btn_save_config.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(self.btn_save_config)
            # 设置模式不添加右侧画板
            return

        # 工作台模式：添加渲染按钮
        self.btn_plot = PrimaryPushButton("⚡ 渲染层析图谱", icon=FIF.PLAY)
        self.btn_plot.setFixedHeight(35)
        self.btn_plot.clicked.connect(self.trigger_render)
        self.param_layout.addWidget(self.btn_plot)

        # ========== 右侧画板 (全新白色原生质感) ==========
        self.fig = Figure(dpi=120)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.canvas_container = QWidget()
        # ✨ 赋予纯白圆角悬浮纸张质感
        self.canvas_container.setStyleSheet("background-color: #FFFFFF; border: 1px solid #EAEAEA; border-radius: 8px;")
        
        # 🚨 局部变量，不覆盖基类布局
        canvas_layout = QVBoxLayout(self.canvas_container) 
        canvas_layout.setContentsMargins(10, 10, 10, 10)
        canvas_layout.setAlignment(Qt.AlignCenter)
        canvas_layout.addWidget(self.canvas)

        self.scroll_canvas = QScrollArea()
        self.scroll_canvas.setWidgetResizable(True)
        self.scroll_canvas.setFrameShape(QScrollArea.NoFrame)
        # ✨ 外层容器透明，完美融入系统背景
        self.scroll_canvas.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scroll_canvas.setWidget(self.canvas_container)

        self.toolbar = NavigationToolbar(self.canvas, self)

        # 导出控件 (✅ 修复变量名：恢复使用 self)
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

        # 将右侧内容放入基类真正安全的 canvas_panel 布局中
        self.get_canvas_layout().addWidget(self.toolbar)
        self.get_canvas_layout().addWidget(self.scroll_canvas)
        self.get_canvas_layout().addLayout(export_layout)

    # ------------------------------------
    # 数据摄取与 UI 交互
    # ------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.load_file(url.toLocalFile())

    def load_file(self, filepath):
        if not os.path.exists(filepath):
            return
        if filepath.lower().endswith(('.csv', '.xlsx', '.xls', '.txt')):
            if filepath not in self.file_list:
                self.file_list.append(filepath)
                if not self.is_setting_mode:
                    self.list_widget.addItem(os.path.basename(filepath))
        if self.file_list and not self.is_setting_mode and not self.list_widget.currentItem():
            self.list_widget.setCurrentRow(0)
            self.trigger_render()

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择数据文件", "", "Data Files (*.csv *.xlsx *.xls *.txt);;All Files (*)")
        for fp in files:
            self.load_file(fp)

    def clear_files(self):
        self.file_list.clear()
        if not self.is_setting_mode:
            self.list_widget.clear()
            self.fig.clear()
            self.canvas.draw()

    def get_float(self, line_edit, default=0.0):
        try:
            return float(line_edit.text())
        except:
            return default

    # ------------------------------------
    # 配置管理
    # ------------------------------------
    def _load_config(self):
        """从 GlobalConfig 加载参数"""
        config = GlobalConfig.get_all_plugin_settings(self.plugin_id)
        if config:
            self.apply_config_dict(config)

    def _save_config(self):
        """保存参数到 GlobalConfig"""
        config = self.get_config_dict()
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def get_config_dict(self):
        """收集当前 UI 控件的值，返回字典"""
        return {
            "c1x": self.c1x.value(),
            "c1y": self.c1y.value(),
            "l1": self.l1.text(),
            "ls1": self.ls1.currentText(),
            "c2x": self.c2x.value(),
            "c2y": self.c2y.value(),
            "l2": self.l2.text(),
            "ls2": self.ls2.currentText(),
            "title": self.title.text(),
            "xl": self.xl.text(),
            "yl": self.yl.text(),
            "x1": self.x1.text(),
            "x2": self.x2.text(),
            "xt_step": self.xt_step.text(),
            "xt_n": self.xt_n.text(),
            "y1": self.y1.text(),
            "y2": self.y2.text(),
            "yt_step": self.yt_step.text(),
            "yt_n": self.yt_n.text(),
            "spin_w": self.spin_w.value(),
            "spin_h": self.spin_h.value(),
            "b_title": self.b_title.isChecked(),
            "b_label": self.b_label.isChecked(),
            "b_tick": self.b_tick.isChecked(),
            "b_leg": self.b_leg.isChecked(),
            "lw": self.lw.value(),
            "fs": self.fs.value(),
            "tk_len": self.tk_len.value(),
            "tk_dir": self.tk_dir.currentText(),
            "min_n": self.min_n.value(),
            "grid": self.grid.isChecked(),
            "leg_loc": self.leg_loc.currentText(),
            "peak": self.peak.isChecked(),
            "auc": self.auc.isChecked(),
            "leg": self.leg.isChecked()
        }

    def apply_config_dict(self, data):
        """将字典值应用到 UI 控件"""
        self.c1x.setValue(data.get("c1x", 0))
        self.c1y.setValue(data.get("c1y", 1))
        self.l1.setText(data.get("l1", "UV_280"))
        self.ls1.setCurrentText(data.get("ls1", "-"))
        self.c2x.setValue(data.get("c2x", 2))
        self.c2y.setValue(data.get("c2y", 3))
        self.l2.setText(data.get("l2", "UV_260"))
        self.ls2.setCurrentText(data.get("ls2", "-"))
        self.title.setText(data.get("title", "AKTA Plot"))
        self.xl.setText(data.get("xl", "Elution volume (mL)"))
        self.yl.setText(data.get("yl", "Absorbance (mAU)"))
        self.x1.setText(data.get("x1", ""))
        self.x2.setText(data.get("x2", ""))
        self.xt_step.setText(data.get("xt_step", ""))
        self.xt_n.setText(data.get("xt_n", ""))
        self.y1.setText(data.get("y1", ""))
        self.y2.setText(data.get("y2", ""))
        self.yt_step.setText(data.get("yt_step", ""))
        self.yt_n.setText(data.get("yt_n", ""))
        self.spin_w.setValue(data.get("spin_w", 7.0))
        self.spin_h.setValue(data.get("spin_h", 5.0))
        self.b_title.setChecked(data.get("b_title", True))
        self.b_label.setChecked(data.get("b_label", True))
        self.b_tick.setChecked(data.get("b_tick", False))
        self.b_leg.setChecked(data.get("b_leg", False))
        self.lw.setValue(data.get("lw", 1.5))
        self.fs.setValue(data.get("fs", 12))
        self.tk_len.setValue(data.get("tk_len", 6))
        self.tk_dir.setCurrentText(data.get("tk_dir", "in"))
        self.min_n.setValue(data.get("min_n", 2))
        self.grid.setChecked(data.get("grid", False))
        self.leg_loc.setCurrentText(data.get("leg_loc", "best"))
        self.peak.setChecked(data.get("peak", True))
        self.auc.setChecked(data.get("auc", True))
        self.leg.setChecked(data.get("leg", True))

    def export_config(self):
        """导出参数模板到文件"""
        path, _ = QFileDialog.getSaveFileName(self, "保存 AKTA 参数模板", "akta_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        """从文件导入参数模板"""
        path, _ = QFileDialog.getOpenFileName(self, "载入 AKTA 参数模板", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                self.apply_config_dict(json.load(f))
            if not self.is_setting_mode:
                self.trigger_render()

    def save_settings_and_close(self):
        """保存设置并关闭对话框（设置模式专用）"""
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog):
            parent_dlg.accept()

    # ------------------------------------
    # 绘图核心
    # ------------------------------------
    def trigger_render(self, *args):
        if self.is_setting_mode:
            return
        self._save_config()
        self.render_plot()
        dpi = self.fig.dpi
        w_px = int(self.spin_w.value() * dpi)
        h_px = int(self.spin_h.value() * dpi)
        self.canvas.setFixedSize(w_px, h_px)
        self.canvas_container.updateGeometry()

    def export_plot(self):
        if self.is_setting_mode:
            return
        fmt = self.combo_fmt.currentText()
        is_transparent = self.chk_trans.isChecked()
        row = self.list_widget.currentRow()
        default_name = os.path.splitext(self.list_widget.item(max(0, row)).text())[0] + f"_AKTA.{fmt}" if self.list_widget.count() > 0 else f"AKTA_Plot.{fmt}"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出图表", default_name, f"Images (*.{fmt})")
        if file_path:
            try:
                self.fig.savefig(file_path, dpi=600, bbox_inches="tight", transparent=is_transparent)
                QMessageBox.information(self, "成功", f"图表已导出:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def render_plot(self):
        if self.is_setting_mode:
            return
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.file_list):
            return

        fp = self.file_list[row]
        title_text = os.path.splitext(os.path.basename(fp))[0]

        self.fig.clear()
        self.fig.set_size_inches(self.spin_w.value(), self.spin_h.value())
        self.ax = self.fig.add_subplot(111)

        data = safe_load_array(fp)
        if data.size == 0:
            return

        c1x, c1y = self.c1x.value(), self.c1y.value()
        c2x, c2y = self.c2x.value(), self.c2y.value()
        if data.shape[1] <= max(c1x, c1y, c2x, c2y):
            return

        x1, y1 = data[:, c1x], data[:, c1y]
        x2, y2 = data[:, c2x], data[:, c2y]
        m1 = ~np.isnan(x1) & ~np.isnan(y1)
        m2 = ~np.isnan(x2) & ~np.isnan(y2)
        x1, y1 = x1[m1], y1[m1]
        x2, y2 = x2[m2], y2[m2]

        lw = self.lw.value()
        fs = self.fs.value()

        fw_title = 'bold' if self.b_title.isChecked() else 'normal'
        fw_label = 'bold' if self.b_label.isChecked() else 'normal'
        fw_tick = 'bold' if self.b_tick.isChecked() else 'normal'
        fw_leg = 'bold' if self.b_leg.isChecked() else 'normal'

        name1 = self.l1.text() or "UV_280"
        name2 = self.l2.text() or "UV_260"

        self.ax.plot(x1, y1, color="royalblue", lw=lw, ls=self.ls1.currentText(), label=name1, zorder=2)
        self.ax.plot(x2, y2, color="firebrick", lw=lw, ls=self.ls2.currentText(), label=name2, zorder=2)

        self.ax.set_title(self.title.text() if self.title.text() else title_text,
                          fontsize=fs + 2, fontweight=fw_title, pad=10)
        self.ax.set_xlabel(self.xl.text(), fontsize=fs, fontweight=fw_label)
        self.ax.set_ylabel(self.yl.text(), fontsize=fs, fontweight=fw_label)

        if self.x1.text():
            self.ax.set_xlim(left=self.get_float(self.x1))
        if self.x2.text():
            self.ax.set_xlim(right=self.get_float(self.x2))
        if self.y1.text():
            self.ax.set_ylim(bottom=self.get_float(self.y1))
        if self.y2.text():
            self.ax.set_ylim(top=self.get_float(self.y2))

        try:
            xt_step, xt_n = self.get_float(self.xt_step), self.get_float(self.xt_n)
            if xt_step > 0:
                self.ax.xaxis.set_major_locator(MultipleLocator(xt_step))
            elif xt_n > 0:
                self.ax.xaxis.set_major_locator(MaxNLocator(int(xt_n)))

            yt_step, yt_n = self.get_float(self.yt_step), self.get_float(self.yt_n)
            if yt_step > 0:
                self.ax.yaxis.set_major_locator(MultipleLocator(yt_step))
            elif yt_n > 0:
                self.ax.yaxis.set_major_locator(MaxNLocator(int(yt_n)))
        except:
            pass

        tk_len = self.tk_len.value()
        tk_dir = self.tk_dir.currentText()
        min_n = self.min_n.value()

        self.ax.tick_params(which='major', width=lw, length=tk_len, labelsize=fs - 1, direction=tk_dir)
        self.ax.tick_params(which='minor', width=lw * 0.7, length=tk_len * 0.6, direction=tk_dir)

        if min_n > 0:
            self.ax.xaxis.set_minor_locator(AutoMinorLocator(min_n))
            self.ax.yaxis.set_minor_locator(AutoMinorLocator(min_n))
        else:
            self.ax.xaxis.set_minor_locator(NullLocator())
            self.ax.yaxis.set_minor_locator(NullLocator())

        for label in self.ax.get_xticklabels() + self.ax.get_yticklabels():
            label.set_fontweight(fw_tick)

        for sp in self.ax.spines.values():
            sp.set_linewidth(lw)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

        if self.grid.isChecked():
            self.ax.grid(True, which='major', ls='--', alpha=0.5)
            self.ax.grid(True, which='minor', ls=':', alpha=0.2)

        if self.leg.isChecked():
            loc = self.leg_loc.currentText()
            if loc == 'outside':
                leg = self.ax.legend(frameon=False, fontsize=fs - 1, bbox_to_anchor=(1.02, 1), loc='upper left')
            else:
                leg = self.ax.legend(frameon=False, fontsize=fs - 1, loc=loc)
            for text in leg.get_texts():
                text.set_fontweight(fw_leg)

        txts = []
        if self.peak.isChecked() and len(y1) > 5:
            cx1, cx2 = self.ax.get_xlim()
            mask = (x1 >= cx1) & (x1 <= cx2)
            if np.any(mask):
                y_sm = np.convolve(y1, np.ones(5) / 5, mode='same')
                sub_idx = np.where(mask)[0]
                idx = sub_idx[np.argmax(y_sm[mask])]
                px, py = x1[idx], y1[idx]
                self.ax.axvline(px, color='gray', ls='--', alpha=0.5, zorder=1)
                self.ax.text(px, py, f"{px:.2f}", fontsize=fs - 2, fontweight='bold', va='bottom')
                try:
                    txts.append(f"Ratio(Peak): {np.interp(px, x2, y2) / py:.2f}")
                except:
                    pass

        if self.auc.isChecked() and len(y1) > 2:
            a1 = np.trapz(np.maximum(y1, 0), x1)
            a2 = np.trapz(np.maximum(y2, 0), x2)
            txts.append(f"Ratio(AUC): {a2 / a1 if a1 != 0 else 0:.2f}")

        if txts:
            self.ax.text(0.02, 0.95, "\n".join(txts), transform=self.ax.transAxes,
                         fontsize=fs - 2, fontweight='bold', va='top',
                         bbox=dict(boxstyle="round", fc="white", alpha=0.8))

        self.fig.tight_layout()
        self.canvas.draw()


# ==========================================
# 插件描述器
# ==========================================
class AKTAPlugin(BasePlugin):
    plugin_id = "akta_analyzer"
    plugin_name = "AKTA 层析分析"
    icon = "📉"
    trigger_tag = "AKTA"

    def get_ui(self, parent=None):
        return AktaUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        card = PrimaryPushSettingCard(
            "配置全局默认参数",
            FIF.EDIT,
            "📉 AKTA 层析分析",
            "修改工作站中 AKTA 图谱的全局默认线型、坐标轴与寻峰偏好",
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("AKTA 全局默认参数预设中心")
            dlg.resize(460, 750)
            layout = QVBoxLayout(dlg)
            settings_ui = AktaUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        """后台自动处理"""
        try:
            # 从 GlobalConfig 读取配置
            config = GlobalConfig.get_all_plugin_settings("akta_analyzer")
            u = config if config else {}

            data = safe_load_array(file_path)
            c1x, c1y = u.get('c1x', 0), u.get('c1y', 1)
            c2x, c2y = u.get('c2x', 2), u.get('c2y', 3)

            if data.size == 0 or data.shape[1] <= max(c1x, c1y, c2x, c2y):
                return "", "【AKTA分析跳过】数据为空或列数不足（请检查全局默认参数中的 Index 映射）。"

            x1, y1 = data[:, c1x], data[:, c1y]
            x2, y2 = data[:, c2x], data[:, c2y]
            m1 = ~np.isnan(x1) & ~np.isnan(y1)
            m2 = ~np.isnan(x2) & ~np.isnan(y2)
            x1, y1 = x1[m1], y1[m1]
            x2, y2 = x2[m2], y2[m2]

            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt

            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False

            fig = Figure(figsize=(u.get("spin_w", 7.0), u.get("spin_h", 5.0)), dpi=150)
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)

            lw = u.get('lw', 1.5)
            fs = u.get('fs', 12)
            fw_title = 'bold' if u.get('b_title', True) else 'normal'
            fw_label = 'bold' if u.get('b_label', True) else 'normal'
            fw_tick = 'bold' if u.get('b_tick', False) else 'normal'
            fw_leg = 'bold' if u.get('b_leg', False) else 'normal'

            name1 = u.get('l1', "UV_280")
            name2 = u.get('l2', "UV_260")

            ax.plot(x1, y1, color="royalblue", lw=lw, ls=u.get('ls1', '-'), label=name1, zorder=2)
            ax.plot(x2, y2, color="firebrick", lw=lw, ls=u.get('ls2', '-'), label=name2, zorder=2)

            title_text = os.path.splitext(os.path.basename(file_path))[0]
            ax.set_title(u.get('title', "AKTA Plot") if u.get('title', "") else title_text,
                         fontsize=fs + 2, fontweight=fw_title, pad=10)
            ax.set_xlabel(u.get('xl', "Elution volume (mL)"), fontsize=fs, fontweight=fw_label)
            ax.set_ylabel(u.get('yl', "Absorbance (mAU)"), fontsize=fs, fontweight=fw_label)

            if u.get('x1', ""):
                ax.set_xlim(left=float(u['x1']))
            if u.get('x2', ""):
                ax.set_xlim(right=float(u['x2']))
            if u.get('y1', ""):
                ax.set_ylim(bottom=float(u['y1']))
            if u.get('y2', ""):
                ax.set_ylim(top=float(u['y2']))

            try:
                xt_step, xt_n = float(u.get('xt_step', 0)), float(u.get('xt_n', 0))
                if xt_step > 0:
                    ax.xaxis.set_major_locator(MultipleLocator(xt_step))
                elif xt_n > 0:
                    ax.xaxis.set_major_locator(MaxNLocator(int(xt_n)))

                yt_step, yt_n = float(u.get('yt_step', 0)), float(u.get('yt_n', 0))
                if yt_step > 0:
                    ax.yaxis.set_major_locator(MultipleLocator(yt_step))
                elif yt_n > 0:
                    ax.yaxis.set_major_locator(MaxNLocator(int(yt_n)))
            except:
                pass

            tk_len = u.get('tk_len', 6)
            tk_dir = u.get('tk_dir', "in")
            min_n = u.get('min_n', 2)

            ax.tick_params(which='major', width=lw, length=tk_len, labelsize=fs - 1, direction=tk_dir)
            ax.tick_params(which='minor', width=lw * 0.7, length=tk_len * 0.6, direction=tk_dir)

            if min_n > 0:
                ax.xaxis.set_minor_locator(AutoMinorLocator(min_n))
                ax.yaxis.set_minor_locator(AutoMinorLocator(min_n))
            else:
                ax.xaxis.set_minor_locator(NullLocator())
                ax.yaxis.set_minor_locator(NullLocator())

            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_fontweight(fw_tick)

            for sp in ax.spines.values():
                sp.set_linewidth(lw)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            if u.get('grid', False):
                ax.grid(True, which='major', ls='--', alpha=0.5)
                ax.grid(True, which='minor', ls=':', alpha=0.2)

            if u.get('leg', True):
                loc = u.get('leg_loc', "best")
                if loc == 'outside':
                    leg = ax.legend(frameon=False, fontsize=fs - 1, bbox_to_anchor=(1.02, 1), loc='upper left')
                else:
                    leg = ax.legend(frameon=False, fontsize=fs - 1, loc=loc)
                for text in leg.get_texts():
                    text.set_fontweight(fw_leg)

            txts = []
            peak_x, peak_y, auc_ratio = None, None, None

            if u.get('peak', True) and len(y1) > 5:
                cx1, cx2 = ax.get_xlim()
                mask = (x1 >= cx1) & (x1 <= cx2)
                if np.any(mask):
                    y_sm = np.convolve(y1, np.ones(5) / 5, mode='same')
                    sub_idx = np.where(mask)[0]
                    idx = sub_idx[np.argmax(y_sm[mask])]
                    px, py = x1[idx], y1[idx]
                    ax.axvline(px, color='gray', ls='--', alpha=0.5, zorder=1)
                    ax.text(px, py, f"{px:.2f}", fontsize=fs - 2, fontweight='bold', va='bottom')
                    peak_x, peak_y = px, py
                    try:
                        ratio_peak = np.interp(px, x2, y2) / py
                        txts.append(f"Ratio(Peak): {ratio_peak:.2f}")
                    except:
                        pass

            if u.get('auc', True) and len(y1) > 2:
                a1 = np.trapz(np.maximum(y1, 0), x1)
                a2 = np.trapz(np.maximum(y2, 0), x2)
                if a1 != 0:
                    auc_ratio = a2 / a1
                    txts.append(f"Ratio(AUC): {auc_ratio:.2f}")

            if txts:
                ax.text(0.02, 0.95, "\n".join(txts), transform=ax.transAxes,
                        fontsize=fs - 2, fontweight='bold', va='top',
                        bbox=dict(boxstyle="round", fc="white", alpha=0.8))

            fig.tight_layout()

            out_name = f"plot_AKTA_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150)
            fig.clf()

            res_text = "📉 【AKTA 层析分析完毕】<br>"
            if peak_x is not None:
                res_text += f"主峰洗脱位置: {peak_x:.2f} mL (吸光度: {peak_y:.2f})<br>"
            if auc_ratio is not None:
                res_text += f"积分面积纯度比 (UV260/280): {auc_ratio:.2f}"

            return out_path, res_text

        except Exception as e:
            return "", f"AKTA 自动作图引擎执行失败: {str(e)}"