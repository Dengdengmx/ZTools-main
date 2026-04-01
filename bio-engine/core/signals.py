# core/signals.py
"""
SciForge 全局事件总线 (终极定制版)
定义所有跨模块通信的信号，通过单例 global_bus 实例在全域无障碍穿梭。
"""

from PyQt5.QtCore import QObject, pyqtSignal

class GlobalEventBus(QObject):
    """
    全局事件总线 (Singleton)
    彻底解耦 UI 和业务逻辑，任何模块只需监听或发射这里的信号即可联动。
    """
    # 🎯 定向投送至绘图引擎（参数：绝对文件路径, 目标引擎 ID）
    send_file_to_plot = pyqtSignal(str, str)

    # 📝 发送文件到今日实验记录（参数：绝对文件路径）
    send_file_to_eln = pyqtSignal(str)

    # 🧭 强制切换主导航栏选项卡（参数：选项卡名称，如 "workspace" 或 "sample_hub"）
    switch_main_tab = pyqtSignal(str)

    # 🚀 空间瞬移：跳转到实体样本库的指定孔位（参数：所在容器路径, 具体孔位 ID）
    jump_to_sample = pyqtSignal(str, str)

    # 🌟 新增：全局同步完成的广播信号
    sync_completed = pyqtSignal() 

# 全局唯一实例，其他文件直接 from core.signals import global_bus 即可
global_bus = GlobalEventBus()