# core/ui_base.py
"""
SciForge UI 基础模块 (自由拖拽分屏升级版)
提供插件 UI 的基类 BasePluginUI，以及通用的 Fluent 风格辅助组件构建方法。
所有插件的 UI 类继承此模块，实现界面结构统一与分割器的无缝联动。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter
from qfluentwidgets import SimpleCardWidget, SubtitleLabel, ScrollArea, BodyLabel


class FluentHelper:
    """为插件 UI 提供通用 Fluent 风格组件构建方法，避免重复代码"""

    def create_group(self, title_text):
        """
        创建一个带标题和分割线的分组容器
        返回 (group_widget, group_layout)
        """
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)
        
        title = BodyLabel(title_text)
        title.setStyleSheet("font-weight: bold; color: #0078D7; font-size: 13px;")
        layout.addWidget(title)
        
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #E0E0E0;")
        layout.addWidget(line)
        
        return w, layout

    def add_param_widget(self, widget):
        self.scroll_layout.addWidget(widget)

    def add_param_stretch(self):
        self.scroll_layout.addStretch(1)

    def get_canvas_layout(self):
        return self.canvas_layout

    def add_row(self, layout, label1_text, widget1, label2_text=None, widget2=None):
        """极其紧凑的双列布局生成器，专为压缩空间设计"""
        h = QHBoxLayout()
        h.setSpacing(4) 
        
        if label1_text: h.addWidget(BodyLabel(label1_text))
        h.addWidget(widget1, 1)
        
        if widget2:
            if label2_text: h.addWidget(BodyLabel(label2_text))
            h.addWidget(widget2, 1)
            
        layout.addLayout(h)


class BasePluginUI(QWidget, FluentHelper):
    """
    所有分析引擎 UI 的基类。
    提供统一的分屏布局（QSplitter）、参数滚动区和画板渲染区。
    """
    def __init__(self, plugin_id, plugin_name, parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self._setup_base_ui()

    def _setup_base_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # 🚀 核心升级：引入 QSplitter 替代原来的水平布局，实现自由拖拽
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
                width: 6px;
                margin: 0px 2px;
            }
            QSplitter::handle:hover {
                background-color: #0078D7;
                border-radius: 3px;
            }
        """)

        # ---------- 左侧：参数控制区 ----------
        self.param_panel = SimpleCardWidget(self)
        
        # 🚨 核心修改：移除原先的 setFixedWidth(360)，改为弹性的最小/最大宽度
        self.param_panel.setMinimumWidth(280)
        self.param_panel.setMaximumWidth(800)
        
        self.param_layout = QVBoxLayout(self.param_panel)
        self.param_layout.setContentsMargins(8, 10, 8, 10)

        self.title_label = SubtitleLabel(f"{self.plugin_name} 参数")
        self.param_layout.addWidget(self.title_label)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 5, 0, 0)
        self.scroll_layout.setSpacing(8)
        self.scroll_area.setWidget(self.scroll_widget)

        self.param_layout.addWidget(self.scroll_area)

        # ---------- 右侧：渲染画板区 ----------
        self.canvas_panel = SimpleCardWidget(self)
        self.canvas_layout = QVBoxLayout(self.canvas_panel)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)

        # 将左右两个面板装进 Splitter
        self.splitter.addWidget(self.param_panel)
        self.splitter.addWidget(self.canvas_panel)

        # 设置初始默认宽度比例（左侧初始分配 360px，剩下的全给右边）
        self.splitter.setSizes([360, 840])
        # 让右侧在窗口拉伸时吸收更多多余空间
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        self.main_layout.addWidget(self.splitter)