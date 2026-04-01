# core/plugin_manager.py
"""
SciForge 插件管理引擎 (异步计算与热重载终极定制版)
负责扫描 plugins 目录、动态加载/热重载插件、管理插件生命周期。
内嵌 QThreadPool 标准异步运算池，彻底杜绝 UI 假死。
"""

import os
import sys
import importlib
import traceback
import inspect

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

# 绝对路径锁定：确保无论从哪里运行，引擎都能正确锁定到 core 模块
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ==========================================
# 🚀 异步计算池引擎 (QThreadPool Integration)
# ==========================================
class WorkerSignals(QObject):
    """
    异步运算通信兵
    负责在后台计算线程和主 GUI 线程之间安全地无缝传递数据
    """
    finished = pyqtSignal(object)  # 计算成功完成，传回结果
    error = pyqtSignal(tuple)      # 发生异常，传回 (ExceptionType, ExceptionValue, Traceback)
    progress = pyqtSignal(int)     # 进度条回传 (0-100)
    log = pyqtSignal(str)          # 实时计算日志回传


class PluginWorker(QRunnable):
    """
    标准化的科研计算异步容器
    将计算密集型的任务（如 K-means, NW序列比对, 曲线拟合）包装在此处，抛入全局线程池执行。
    """
    def __init__(self, fn, *args, **kwargs):
        super(PluginWorker, self).__init__()
        self.fn = fn            # 实际要执行的计算函数
        self.args = args        # 位置参数
        self.kwargs = kwargs    # 关键字参数
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """线程池分配资源后自动在后台执行该函数"""
        try:
            # 智能探测：如果目标函数需要回调信号，则自动注入
            sig = inspect.signature(self.fn)
            if 'progress_callback' in sig.parameters:
                self.kwargs['progress_callback'] = self.signals.progress
            if 'log_callback' in sig.parameters:
                self.kwargs['log_callback'] = self.signals.log

            # 执行耗时的算法核心
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            # 将崩溃抛回主界面
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # 计算完美收官，将数据抛回前端渲染
            self.signals.finished.emit(result)


# ==========================================
# 🧩 插件抽象基类
# ==========================================
class BasePlugin:
    """所有分析引擎必须继承的核心基类"""
    plugin_id = "base"
    plugin_name = "未命名引擎"
    description = "这是一个基础分析引擎模板"
    icon = "🧩"
    trigger_tag = ""

    def get_ui(self, parent=None):
        return None

    def get_setting_card(self, parent=None):
        return None

    def run(self, file_path, archive_dir, **kwargs):
        raise NotImplementedError("插件必须实现标准的 run 处理流协议！")


# ==========================================
# 🧠 插件生命周期与热插拔核心
# ==========================================
class PluginManager:
    """插件生命周期管理器（单例路由中心）"""
    _plugins = []
    _modules_cache = {}  # 记录已加载的模块，服务于 Hot Reload

    @classmethod
    def _setup_plugin_env(cls):
        """将 plugins 目录注册到系统的环境变量中，打通标准 import 机制"""
        plugins_dir = os.path.join(PROJECT_ROOT, "plugins")
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            
        # 核心防弹修复：将插件目录加入 sys.path
        # 这样底层的 importlib 就能像导普通库一样导插件，完美支持 reload
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)
            
        return plugins_dir

    @classmethod
    def load_all_plugins(cls):
        """首次冷启动扫描并加载所有插件"""
        cls._plugins = []
        cls._modules_cache = {}
        plugins_dir = cls._setup_plugin_env()

        for file in os.listdir(plugins_dir):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]  # 去掉 .py 后缀，例如 'plugin_akta'
                try:
                    # 使用标准导入，极其安全稳定
                    module = importlib.import_module(module_name)
                    
                    # 严格继承链校验
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                            cls._plugins.append(attr())
                            cls._modules_cache[module_name] = module
                            print(f"[Plugin Engine] ✅ 成功挂载引擎: {getattr(attr, 'plugin_name', module_name)}")
                            break
                except Exception as e:
                    print(f"\n[Plugin Engine] ❌ 引擎 {module_name} 挂载失败!")
                    traceback.print_exc()

    @classmethod
    def reload_plugins(cls):
        """
        【热重载引擎】Hot Reloading
        不重启软件，直接在内存中刷新所有已挂载插件的算法代码！
        """
        print("\n[Plugin Engine] 🔄 正在触发全局插件热重载...")
        cls._plugins = []
        plugins_dir = cls._setup_plugin_env()
        
        for file in os.listdir(plugins_dir):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]
                try:
                    # 核心机制：如果在缓存中说明已加载，直接 reload；否则重新 import
                    if module_name in cls._modules_cache:
                        module = importlib.reload(cls._modules_cache[module_name])
                    else:
                        module = importlib.import_module(module_name)
                        
                    cls._modules_cache[module_name] = module
                    
                    # 重新实例化新代码中的插件类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                            cls._plugins.append(attr())
                            print(f"[Hot Reload] ⚡ 引擎已热更新: {getattr(attr, 'plugin_name', module_name)}")
                            break
                except Exception as e:
                    print(f"[Hot Reload] ❌ 引擎 {module_name} 热更新失败: {e}")
                    
        print("[Plugin Engine] 🔄 热重载完毕！前端界面可立即使用新算法。\n")

    @classmethod
    def get_plugins(cls):
        if not cls._plugins:
            cls.load_all_plugins()
        return cls._plugins

    @classmethod
    def get_plugin_by_id(cls, plugin_id):
        for p in cls.get_plugins():
            if p.plugin_id == plugin_id:
                return p
        return None

    @classmethod
    def get_plugins_by_tag(cls, tag):
        return [p for p in cls.get_plugins() if p.trigger_tag == tag]