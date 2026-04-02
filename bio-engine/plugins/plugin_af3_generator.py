# plugins/plugin_af3_generator.py
"""
AlphaFold3 批量任务生成器插件
支持读取包含 Job_Name 和 Sequence 的 CSV 文件，
并将其一键打包转换为 AlphaFold3 官方支持的批处理 JSON 格式。
"""

import os
import json
import csv
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, 
                             QStackedWidget, QMessageBox, QDialog)
from PyQt5.QtGui import QFont

from qfluentwidgets import (LineEdit, BodyLabel, PushButton, PrimaryPushButton, 
                            TextEdit, Pivot, FluentIcon as FIF, 
                            PrimaryPushSettingCard, ToolButton)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig


class AF3JsonGeneratorUI(BasePluginUI):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="af3_generator", plugin_name="AF3 批量任务生成器", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.csv_file_path = ""
        self.parsed_jobs = []  # 缓存从 CSV 解析出的任务数据
        self.generated_json_list = [] # 最终要导出的 AF3 JSON 列表
        
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        # ==========================================
        # 左侧：参数控制区
        # ==========================================
        grp_data, lyt_data = self.create_group("1. 数据源导入")
        
        self.input_csv = LineEdit()
        self.input_csv.setPlaceholderText("选择包含序列的 CSV 文件...")
        self.input_csv.setReadOnly(True)
        
        btn_load_csv = ToolButton(FIF.FOLDER)
        btn_load_csv.setFixedWidth(40)
        btn_load_csv.clicked.connect(self.load_csv)
        self.add_row(lyt_data, "CSV 路径:", self.input_csv, None, btn_load_csv)
        self.add_param_widget(grp_data)

        grp_actions, lyt_actions = self.create_group("2. 编译与导出")
        
        btn_generate = PrimaryPushButton("🚀 一键生成 AF3 批处理 JSON", icon=FIF.PLAY)
        btn_generate.setFixedHeight(45)
        btn_generate.clicked.connect(self.generate_json)
        lyt_actions.addWidget(btn_generate)
        
        self.add_param_widget(grp_actions)
        self.add_param_stretch()

        if self.is_setting_mode:
            btn_save_config = PrimaryPushButton("💾 保存为全局默认参数", icon=FIF.SAVE)
            btn_save_config.setFixedHeight(45)
            btn_save_config.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(btn_save_config)
            return

        # ==========================================
        # 右侧：画板区 (基于富文本渲染的预览报告)
        # ==========================================
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pivot = Pivot(self.canvas_panel)
        self.stacked_widget = QStackedWidget(self.canvas_panel)
        
        vbox = QVBoxLayout()
        vbox.addWidget(self.pivot)
        vbox.addWidget(self.stacked_widget)
        self.canvas_layout.addLayout(vbox)

        font_code = QFont("Consolas", 11)

        # Tab 1: CSV 解析预览
        self.csv_preview = TextEdit()
        self.csv_preview.setFont(font_code)
        self.csv_preview.setReadOnly(True)
        self.csv_preview.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: none; padding: 10px;")
        self.addSubInterface(self.csv_preview, 'csvInterface', '📊 CSV 解析预览')

        # Tab 2: JSON 结果预览
        self.json_preview = TextEdit()
        self.json_preview.setFont(font_code)
        self.json_preview.setReadOnly(True)
        self.json_preview.setStyleSheet("background-color: #f4f4f4; color: #333333; border: none; padding: 10px;")
        self.addSubInterface(self.json_preview, 'jsonInterface', '📦 最终 JSON 预览')

        self.stacked_widget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem('csvInterface')
        self._welcome_msg()

    def addSubInterface(self, widget, objectName, text):
        widget.setObjectName(objectName)
        self.stacked_widget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stacked_widget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stacked_widget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

    def _welcome_msg(self):
        self.csv_preview.setHtml(
            "<pre style='font-size: 14px;'>"
            "<b><span style='color: #569cd6;'>&gt;&gt;&gt; AF3 批量任务生成器就绪 &lt;&lt;&lt;</span></b><br><br>"
            "<span style='color: #808080;'>1. 请准备好一个 CSV 文件。</span><br>"
            "<span style='color: #808080;'>2. 文件必须包含两列表头：<span style='color: #c586c0;'>Job_Name</span> 和 <span style='color: #c586c0;'>Sequence</span>。</span><br>"
            "<span style='color: #808080;'>3. 在左侧点击文件夹图标导入，系统会自动清理非法字符。</span>"
            "</pre>"
        )

    def _load_config(self):
        config = GlobalConfig.get_all_plugin_settings(self.plugin_id)
        if config:
            self.input_csv.setText(config.get("last_csv_path", ""))

    def _save_config(self):
        config = {
            "last_csv_path": self.input_csv.text().strip()
        }
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def save_settings_and_close(self):
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog):
            parent_dlg.accept()

    def load_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择包含序列的 CSV 文件", "", "CSV Files (*.csv);;All Files (*.*)"
        )
        if not file_path: return

        self.input_csv.setText(file_path)
        self.csv_file_path = file_path
        self._save_config()
        
        self.parsed_jobs = []
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                if 'Job_Name' not in reader.fieldnames or 'Sequence' not in reader.fieldnames:
                    QMessageBox.showerror(self, "格式错误", "CSV 文件必须包含 'Job_Name' 和 'Sequence' 两列表头！")
                    return

                for row in reader:
                    job_name = row.get('Job_Name', '').strip()
                    sequence = row.get('Sequence', '').strip()
                    
                    if job_name and sequence:
                        # 清理非法字符，符合 AF3 命名规范
                        safe_job_name = "".join([c for c in job_name if c.isalpha() or c.isdigit() or c=='_']).rstrip()
                        self.parsed_jobs.append({
                            "original_name": job_name,
                            "safe_name": safe_job_name,
                            "sequence": sequence
                        })

            # 渲染预览
            html_lines = []
            html_lines.append('<pre style="font-family: Consolas, monospace; font-size: 13px;">')
            html_lines.append(f'<b><span style="color: #4ec9b0;">✅ 成功读取 CSV 文件，共解析出 {len(self.parsed_jobs)} 条有效任务。</span></b><br><br>')
            
            for i, job in enumerate(self.parsed_jobs):
                if i >= 50:  # 限制预览条数防止卡顿
                    html_lines.append(f'<br><span style="color: #808080;">... (隐藏后续 {len(self.parsed_jobs) - 50} 条数据以节省内存) ...</span>')
                    break
                    
                warn_msg = ""
                if job["original_name"] != job["safe_name"]:
                    warn_msg = f' <span style="color: #f44336;">[原名 {job["original_name"]} 含有非法字符，已自动净化]</span>'
                    
                html_lines.append(f'<b><span style="color: #569cd6;">[任务 {i+1}]</span></b> <b>Job_Name:</b> {job["safe_name"]}{warn_msg}<br>')
                html_lines.append(f'<b><span style="color: #c586c0;">Sequence:</span></b> <span style="color: #d4d4d4;">{job["sequence"][:60]}... (Len: {len(job["sequence"])})</span><br><br>')

            html_lines.append('</pre>')
            self.csv_preview.setHtml("".join(html_lines))
            self.stacked_widget.setCurrentWidget(self.csv_preview)
            self.pivot.setCurrentItem('csvInterface')

        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"无法解析 CSV 文件：\n{str(e)}")

    def generate_json(self):
        if not self.parsed_jobs:
            QMessageBox.warning(self, "提示", "请先正确导入包含有效任务的 CSV 文件！")
            return

        self.generated_json_list = []
        for job in self.parsed_jobs:
            single_job = {
                "name": job["safe_name"],
                "modelSeeds": [],
                "sequences": [
                    {
                        "proteinChain": {
                            "sequence": job["sequence"],
                            "count": 1
                        }
                    }
                ]
            }
            self.generated_json_list.append(single_job)

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存批量 AF3 JSON 文件", 
            "AF3_batch_jobs.json",
            "JSON Files (*.json)"
        )
        
        if save_path:
            try:
                # 写入 JSON
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(self.generated_json_list, f, indent=2)
                
                # 渲染 JSON 结果预览
                json_str = json.dumps(self.generated_json_list[:3], indent=2)
                hidden_msg = ""
                if len(self.generated_json_list) > 3:
                    hidden_msg = f"\n\n... (为了性能，仅在此处预览前 3 个任务的 JSON 结构，共生成 {len(self.generated_json_list)} 个任务) ..."
                
                self.json_preview.setPlainText(json_str + hidden_msg)
                self.stacked_widget.setCurrentWidget(self.json_preview)
                self.pivot.setCurrentItem('jsonInterface')

                QMessageBox.information(self, "生成完毕", f"🎉 成功将 {len(self.generated_json_list)} 个任务打包进 1 个 JSON 文件！\n\n文件已保存至:\n{save_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"写入 JSON 文件时发生错误：\n{str(e)}")


# ==========================================
# 后端：插件描述器
# ==========================================
class AF3JsonGeneratorPlugin(BasePlugin):
    plugin_id = "af3_generator"
    plugin_name = "AF3 批量任务生成器"
    icon = "🧬"
    trigger_tag = "蛋白设计"

    def get_ui(self, parent=None):
        return AF3JsonGeneratorUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        card = PrimaryPushSettingCard(
            "配置 AF3 生成器偏好", 
            FIF.SETTING, 
            "🧬 AF3 批量任务生成器", 
            "此工具将自动读取并清理 CSV，一键生成 AlphaFold3 支持的批处理 JSON。", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("AF3 批量任务生成器 - 全局预设")
            dlg.resize(800, 600)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }")
            layout = QVBoxLayout(dlg)
            settings_ui = AF3JsonGeneratorUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        """支持无界面后台调用：传入 CSV 路径，自动在同级目录生成 JSON"""
        if not os.path.isfile(file_path) or not file_path.lower().endswith(".csv"):
            return "", "【AF3 批量任务生成器】跳过：请选中一个 CSV 文件进行自动化处理。"
            
        af3_jobs_list = []
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                if 'Job_Name' not in reader.fieldnames or 'Sequence' not in reader.fieldnames:
                    return "", "【AF3 批量任务生成器】失败：CSV 文件缺少 'Job_Name' 或 'Sequence' 表头。"

                for row in reader:
                    job_name = row.get('Job_Name', '').strip()
                    sequence = row.get('Sequence', '').strip()
                    
                    if job_name and sequence:
                        safe_job_name = "".join([c for c in job_name if c.isalpha() or c.isdigit() or c=='_']).rstrip()
                        af3_jobs_list.append({
                            "name": safe_job_name,
                            "modelSeeds": [],
                            "sequences": [
                                {
                                    "proteinChain": {
                                        "sequence": sequence,
                                        "count": 1
                                    }
                                }
                            ]
                        })
                        
            if not af3_jobs_list:
                return "", "【AF3 批量任务生成器】警告：CSV 中没有找到有效序列。"
                
            save_name = f"Auto_AF3_Batch_{os.path.splitext(os.path.basename(file_path))[0]}.json"
            save_path = os.path.join(archive_dir, save_name)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(af3_jobs_list, f, indent=2)
                
            return save_path, f"🧬 【AF3 批量任务生成器】执行成功！已将 {len(af3_jobs_list)} 条任务转换为 JSON。"
            
        except Exception as e:
            return "", f"【AF3 批量任务生成器】解析失败: {str(e)}"