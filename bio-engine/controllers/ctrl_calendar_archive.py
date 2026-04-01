# controllers/ctrl_calendar_archive.py
"""
SciForge 日历归档模块控制器 (云端互联同步版)
承载着整个系统的最高级指令调度，包括 QRunnable 并发后台插件计算，以及优美的科研 PDF 导出引擎。
"""

import os
import json
import re
import shutil
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal

from core.config import GlobalConfig
from core.plugin_manager import PluginManager

# ==========================================
# 🛠️ 系统级静默滚动日志配置 (防爆盘设计)
# ==========================================
log_file_path = os.path.join(os.getcwd(), "SciForge_System_Event.log")
logger = logging.getLogger("SciForge_System_Logger")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # 限制单个日志最大 2MB，仅保留最新 1 份备份，拒绝侵占科研电脑存储
    handler = RotatingFileHandler(log_file_path, maxBytes=2*1024*1024, backupCount=1, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ==========================================
# 🚀 并发任务队列核心：QRunnable 降维打击
# ==========================================
class WorkerSignals(QObject):
    """通信对讲机：桥接底层的计算 Runnable 与主线程 UI"""
    sig_process_done = pyqtSignal(str, str, str)  # (original_file, image_path, analysis_text)


class AutoProcessWorker(QRunnable):
    """
    【架构亮点】自动化分析挂载点。
    以轻量级任务形式被丢入全局线程池执行，完美拦截插件的耗时运算，保证主界面帧率。
    """
    def __init__(self, file_path, archive_dir, exp_tags):
        super().__init__()
        self.file_path = file_path
        self.archive_dir = archive_dir
        self.exp_tags = exp_tags
        self.signals = WorkerSignals()

    def run(self):
        output_image_path = ""
        analysis_text = ""

        try:
            all_plugins = PluginManager.get_plugins()
            matched_plugin = None

            for plugin in all_plugins:
                if hasattr(plugin, 'trigger_tag') and plugin.trigger_tag in self.exp_tags:
                    matched_plugin = plugin
                    break

            if matched_plugin:
                # 鸭子类型后缀过滤
                if self.file_path.lower().endswith(('.csv', '.xlsx', '.xls', '.txt', '.dat')):
                    output_image_path, analysis_text = matched_plugin.run(self.file_path, self.archive_dir)
                else:
                    analysis_text = f"【引擎避让】文件流格式非纯量数据，[{matched_plugin.plugin_name}] 引擎已主动挂起。"
            else:
                analysis_text = "【落盘完成】物理介质归档完毕 (当前流水线未订阅挂载该实验特征)。"

        except Exception as e:
            analysis_text = f"【致命异常】自动化运算沙盒崩溃: {str(e)}"

        if analysis_text:
            clean_text = re.sub(r'<[^>]+>', '', analysis_text).strip()
            logger.info(f"后台线程释放 | 标的物: {os.path.basename(self.file_path)} | 结论: {clean_text}")

        self.signals.sig_process_done.emit(self.file_path, output_image_path, analysis_text)


# ==========================================
# 🗄️ LIMS 级记录与文件归档中枢 (云端迁移版)
# ==========================================
class CalendarArchiveLogic:
    @property
    def workspace_dir(self):
        return GlobalConfig.get("workspace_dir", os.path.abspath("./SciForge_Workspace"))

    @property
    def data_file(self):
        """日历数据严格存入 SciForge_Calendar"""
        cal_dir = os.path.join(self.workspace_dir, "SciForge_Calendar")
        if not os.path.exists(cal_dir): os.makedirs(cal_dir, exist_ok=True)
        return os.path.join(cal_dir, "sciforge_eln_data.json")
        
    @property
    def archive_root(self):
        """物理文件严格存入 SciForge_Archive"""
        arc_dir = os.path.join(self.workspace_dir, "SciForge_Archive")
        if not os.path.exists(arc_dir): os.makedirs(arc_dir, exist_ok=True)
        return arc_dir

    def __init__(self):
        # 残留历史数据迁移
        old_data = os.path.join(os.getcwd(), "sciforge_eln_data.json")
        if not os.path.exists(self.data_file) and os.path.exists(old_data):
            import shutil
            try: shutil.move(old_data, self.data_file)
            except: pass
            
        self.schedule_data = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.schedule_data = json.load(f)
            except Exception as e:
                logger.error(f"ELN 实验台数据解析断崖: {e}")
                self.schedule_data = {}

    def save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedule_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"ELN 数据持久化失败: {e}")

    def get_day_data(self, date_str):
        data = self.schedule_data.get(date_str, {})
        if not isinstance(data, dict): data = {"main": str(data)}  # 兼容 V1 的烂数据
        return {
            "todo": data.get("todo", []),
            "main": data.get("main", ""),
            "extra": data.get("extra", "")
        }

    def update_day_data(self, date_str, todo_list, main_text, extra_text):
        if date_str not in self.schedule_data or not isinstance(self.schedule_data[date_str], dict):
            self.schedule_data[date_str] = {}
        self.schedule_data[date_str]["todo"] = todo_list
        self.schedule_data[date_str]["main"] = main_text
        self.schedule_data[date_str]["extra"] = extra_text
        self.save_data()

    def archive_raw_file(self, source_path, project, date_str, exp_type, item_name, operator):
        # 1. 正则安全过滤：抹杀所有可能导致 Windows 路径系统崩溃的非法字符 (这一段必须保留)
        import re
        safe_proj = re.sub(r'[\\/*?:"<>|]', "", project).strip() if project else "未归类资产"
        safe_exp = re.sub(r'[\\/*?:"<>|]', "", exp_type).strip() if exp_type else "通用处理流"
        safe_name = re.sub(r'[\\/*?:"<>|]', "", item_name).strip() if item_name else "未定名节点"
        safe_op = re.sub(r'[\\/*?:"<>|]', "", operator).strip() if operator else ""

        # 2. 🚀 使用动态属性 self.archive_root 拼接目标路径
        target_dir = os.path.join(self.archive_root, safe_proj, date_str, safe_exp, safe_name)
        os.makedirs(target_dir, exist_ok=True)

        ext = os.path.splitext(source_path)[1]
        name_parts = [date_str, safe_proj]
        if safe_name != "未定名节点": name_parts.append(safe_name)
        if safe_exp != "通用处理流": name_parts.append(safe_exp)
        if safe_op: name_parts.append(safe_op)

        base_new_filename = "_".join(name_parts)
        new_filename = f"{base_new_filename}{ext}"
        dest_path = os.path.join(target_dir, new_filename)

        counter = 1
        while os.path.exists(dest_path):
            new_filename = f"{base_new_filename}({counter}){ext}"
            dest_path = os.path.join(target_dir, new_filename)
            counter += 1

        import shutil
        shutil.copy2(source_path, dest_path)
        logger.info(f"档案已入库 | 课题系: {safe_proj} | 标的物: {safe_name}")
        return target_dir, dest_path
    # ==========================================
    # 💡 核心升级：强效适配亮色主题的 PDF 渲染 HTML 骨架
    # ==========================================
    def export_report(self, start_date_str, end_date_str, save_path):
        """
        导出指定日期范围内的报告。
        【样式更新】：全面弃用可能因媒体查询变为深色的默认样式，
        采用高颜值、轻量级、绝对锁定浅色模式的科研工业排版规范。
        """
        sorted_dates = sorted(self.schedule_data.keys())
        valid_dates = [d for d in sorted_dates if start_date_str <= d <= end_date_str]

        html_content = f"""
        <html><head><meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; padding: 30px; background-color: #F9F9F9; color: #202020; }}
            .container {{ max-width: 950px; margin: auto; background-color: #FFFFFF; padding: 40px; border: 1px solid #EAEAEA; border-radius: 6px; }}
            h1 {{ text-align: center; color: #0078D7; border-bottom: 3px solid #0078D7; padding-bottom: 12px; font-size: 28px; letter-spacing: 2px; }}
            .sub-title {{ text-align: center; color: #666666; font-size: 14px; margin-bottom: 40px; }}
            .day-card {{ border-left: 6px solid #107C10; background-color: #F3F9F4; padding: 20px; margin-bottom: 30px; border-radius: 0 4px 4px 0; }}
            .day-title {{ font-size: 22px; font-weight: bold; color: #107C10; margin-top: 0; margin-bottom: 15px; border-bottom: 1px dashed #C8E6C9; padding-bottom: 8px; }}
            .section-title {{ font-weight: bold; color: #444444; margin-top: 20px; font-size: 16px; margin-bottom: 10px; display: inline-block; background-color: #E0E0E0; padding: 4px 10px; border-radius: 4px; }}
            .content {{ font-size: 14px; margin-top: 5px; line-height: 1.8; overflow-wrap: break-word; color: #333333; }}
            .content img {{ max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #CCCCCC; margin-top: 10px; margin-bottom: 10px; }}
            .badge {{ display: inline-block; background-color: #E0F2FE; color: #0078D7; padding: 3px 10px; border-radius: 12px; font-size: 12px; margin-right: 8px; font-weight: bold; border: 1px solid #B3D4FC; }}
        </style></head><body>
        <div class="container">
        <h1>SciForge 数字化实验室溯源汇总</h1>
        <p class="sub-title">报告涵盖区间：{start_date_str} 至 {end_date_str}</p>
        """

        if not valid_dates:
            html_content += "<p style='text-align:center; color: #999; margin-top: 50px;'>系统未在设定域值内检索到落盘记录。</p>"
        else:
            for d in valid_dates:
                data = self.get_day_data(d)
                if not data["todo"] and not data["main"]: continue

                clean_text = re.sub(r'<[^>]+>', '', data["main"])
                tags = re.findall(r'【(.*?)】', clean_text)
                tag_html = "".join([f"<span class='badge'>{t}</span>" for t in set(tags)])

                html_content += f"<div class='day-card'><p class='day-title'>📅 时标：{d}</p>"
                if tag_html: html_content += f"<div style='margin-bottom:15px;'>捕获到关键流：{tag_html}</div>"

                if data["main"]:
                    html_content += f"<div class='section-title'>📝 核心操作溯源</div><div class='content'>{data['main']}</div>"
                html_content += "</div>"

        html_content += "</div></body></html>"

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)