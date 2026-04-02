# plugins/plugin_mpnn_analyzer.py
"""
ProteinMPNN 智能阅卷器插件
支持批量解析 mpnn_out/seqs 文件夹中的所有 .fa 文件，
对分数进行排序，计算突变恢复率(NSR)，并以 HTML 富文本可视化比对野生型与设计序列。
"""

import os
import glob
import csv
from PyQt5.QtCore import Qt, pyqtSignal, QRunnable, QThreadPool, QObject
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QFileDialog, 
                             QMessageBox, QDialog)
from PyQt5.QtGui import QFont

from qfluentwidgets import (LineEdit, SpinBox, BodyLabel, PushButton, 
                            PrimaryPushButton, StrongBodyLabel, TextEdit,
                            PrimaryPushSettingCard, FluentIcon as FIF, ToolButton)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig


# 🌟 修复点 1：必须通过独立的 QObject 来装载信号
class WorkerSignals(QObject):
    finished = pyqtSignal(bool, str, list)

class MPNNAnalyzeWorker(QRunnable):
    """后台运行的多线程解析工人，防止大量 FASTA 导致界面卡死"""
    def __init__(self, seqs_dir, top_n):
        super().__init__()
        self.seqs_dir = seqs_dir
        self.top_n = top_n
        self.signals = WorkerSignals()

    def run(self):
        try:
            fasta_files = glob.glob(os.path.join(self.seqs_dir, "*.fa"))
            if not fasta_files:
                self.signals.finished.emit(False, "未找到任何 .fa 文件", [])
                return

            all_designs = []
            
            for file_path in fasta_files:
                base_filename = os.path.basename(file_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                wt_seq = ""
                current_seq = ""
                current_score = 999.0
                is_first_seq = True

                for line in lines:
                    line = line.strip()
                    if not line: continue

                    if line.startswith(">"):
                        if is_first_seq:
                            if current_seq:  
                                wt_seq = current_seq
                                current_seq = ""
                                is_first_seq = False
                        else:
                            if current_seq:  
                                all_designs.append({
                                    'filename': base_filename, 
                                    'score': current_score, 
                                    'wt_seq': wt_seq, 
                                    'des_seq': current_seq
                                })
                                current_seq = "" 
                        
                        if "score=" in line:
                            try: 
                                score_str = line.split("score=")[1].split(",")[0].strip()
                                current_score = float(score_str)
                            except: 
                                current_score = 999.0
                        else:
                            current_score = 999.0
                    else:
                        current_seq += line
                
                if not is_first_seq and current_seq:
                    all_designs.append({
                        'filename': base_filename, 
                        'score': current_score, 
                        'wt_seq': wt_seq, 
                        'des_seq': current_seq
                    })

            if not all_designs:
                self.signals.finished.emit(False, "文件格式错误，未能解析出设计序列", [])
                return

            all_designs.sort(key=lambda x: x['score'])
            top_designs = all_designs[:self.top_n]
            
            for design in top_designs:
                wt = design['wt_seq']
                des = design['des_seq']
                min_len = min(len(wt), len(des))
                
                mut_count = 0
                for i in range(min_len):
                    if wt[i] != des[i]:
                        mut_count += 1
                
                recovery_rate = ((min_len - mut_count) / min_len) * 100 if min_len > 0 else 0.0
                design['mut_count'] = mut_count
                design['recovery_rate'] = recovery_rate
                design['min_len'] = min_len

            self.signals.finished.emit(True, f"解析完成！共读取 {len(all_designs)} 条序列", top_designs)

        except Exception as e:
            self.signals.finished.emit(False, str(e), [])


class MPNNAnalyzerUI(BasePluginUI):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="mpnn_analyzer", plugin_name="MPNN 智能阅卷器", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.seqs_dir = ""
        self.top_designs_data = []
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        grp_data, lyt_data = self.create_group("1. 数据源选择")
        
        self.input_dir = LineEdit()
        self.input_dir.setPlaceholderText("mpnn_out/seqs...")
        # 🌟 修复点 2：纯图标按钮必须使用 ToolButton
        btn_load = ToolButton(FIF.FOLDER)
        btn_load.setFixedWidth(40)
        btn_load.clicked.connect(self.load_directory)
        self.add_row(lyt_data, "序列目录:", self.input_dir, None, btn_load)
        
        self.spin_top_n = SpinBox()
        self.spin_top_n.setRange(1, 1000)
        self.spin_top_n.setValue(10)
        self.add_row(lyt_data, "提取前 N 名:", self.spin_top_n)
        
        self.add_param_widget(grp_data)

        grp_actions, lyt_actions = self.create_group("2. 阅卷与报告生成")
        
        btn_analyze = PrimaryPushButton("🚀 1. 开始智能阅卷", icon=FIF.PLAY)
        btn_analyze.setFixedHeight(40)
        btn_analyze.clicked.connect(self.analyze_results)
        lyt_actions.addWidget(btn_analyze)
        
        lyt_actions.addSpacing(10)
        
        btn_export_fasta = PushButton("💾 2. 导出 TOP FASTA", icon=FIF.DOWNLOAD)
        btn_export_csv = PushButton("📊 3. 导出 CSV 报表", icon=FIF.DOCUMENT)
        btn_export_fasta.clicked.connect(self.export_top_fasta)
        btn_export_csv.clicked.connect(self.export_csv_report)
        
        lyt_actions.addWidget(btn_export_fasta)
        lyt_actions.addWidget(btn_export_csv)
        
        self.add_param_widget(grp_actions)
        self.add_param_stretch()

        if self.is_setting_mode:
            btn_save_config = PrimaryPushButton("💾 确认并保存为全局默认参数", icon=FIF.SAVE)
            btn_save_config.setFixedHeight(45)
            btn_save_config.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(btn_save_config)
            return

        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.result_display = TextEdit(self.canvas_panel)
        self.result_display.setFont(QFont("Consolas", 11))
        self.result_display.setReadOnly(True)
        self.result_display.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: none;")
        
        self.canvas_layout.addWidget(self.result_display)
        self._welcome_msg()

    def _welcome_msg(self):
        self.result_display.setHtml(
            "<pre style='font-size: 14px;'>"
            "<b><span style='color: #569cd6;'>&gt;&gt;&gt; ProteinMPNN 智能阅卷辅助系统就绪 &lt;&lt;&lt;</span></b><br><br>"
            "<span style='color: #808080;'>1. 在左侧选择包含生成序列的 .fa 文件夹。</span><br>"
            "<span style='color: #808080;'>2. 点击「开始智能阅卷」，系统将提取低分序列并建立比对高亮。</span>"
            "</pre>"
        )

    def _load_config(self):
        config = GlobalConfig.get_all_plugin_settings(self.plugin_id)
        if config:
            self.input_dir.setText(config.get("seqs_dir", ""))
            self.spin_top_n.setValue(config.get("top_n", 10))

    def _save_config(self):
        config = {
            "seqs_dir": self.input_dir.text().strip(),
            "top_n": self.spin_top_n.value()
        }
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def save_settings_and_close(self):
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog):
            parent_dlg.accept()

    def load_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择 MPNN 输出的 seqs 文件夹")
        if dir_path:
            self.input_dir.setText(dir_path)
            self._save_config()
            fasta_files = glob.glob(os.path.join(dir_path, "*.fa"))
            if fasta_files:
                QMessageBox.information(self, "挂载成功", f"在目标域检测到 {len(fasta_files)} 个序列档案。")
            else:
                QMessageBox.warning(self, "空域警告", "所选目录下不存在任何 .fa 文件！")

    def analyze_results(self):
        self._save_config()
        self.seqs_dir = self.input_dir.text().strip()
        if not self.seqs_dir or not os.path.exists(self.seqs_dir):
            QMessageBox.warning(self, "错误", "请先选择合法的 seqs 文件夹！")
            return
            
        self.result_display.setHtml("<pre><b><span style='color: #569cd6;'>&gt;&gt;&gt; 正在疯狂阅卷中，请稍候...</span></b></pre>")
        self.top_designs_data = []

        # 🌟 修复点 3：连接正确的信号回调
        worker = MPNNAnalyzeWorker(self.seqs_dir, self.spin_top_n.value())
        worker.signals.finished.connect(self.on_analyze_finished)
        QThreadPool.globalInstance().start(worker)

    def on_analyze_finished(self, success, message, data):
        if not success:
            self.result_display.setHtml(f"<pre><b><span style='color: #f44336;'>❌ 错误: {message}</span></b></pre>")
            return
            
        self.top_designs_data = data
        self._render_html_report(message)

    def _render_html_report(self, summary_msg):
        html_lines = []
        html_lines.append('<pre style="font-family: Consolas, monospace; font-size: 13px;">')
        html_lines.append(f'<b><span style="color: #569cd6;">👑 {summary_msg}</span></b><br>')
        html_lines.append(f'<b><span style="color: #4ec9b0;">排名前 {self.spin_top_n.value()} 的精英设计如下：</span></b><br>')
        html_lines.append('<span style="color: #808080;">================================================================================</span><br><br>')

        for idx, design in enumerate(self.top_designs_data):
            html_lines.append(f'<b><span style="color: #569cd6;">🏆 TOP {idx + 1} | 来源骨架: {design["filename"]} | MPNN Score: {design["score"]:.4f}</span></b><br>')
            html_lines.append(f'   <span style="color: #d4d4d4;">[统计] 总长 {design["min_len"]} AA | 突变 {design["mut_count"]} 处 | 序列恢复率(NSR) {design["recovery_rate"]:.2f}%</span><br><br>')

            wt = design['wt_seq'][:design['min_len']]
            des = design['des_seq'][:design['min_len']]
            mark_line = "".join(["*" if w != d else " " for w, d in zip(wt, des)])

            idx_str = ""
            for i in range(design['min_len']):
                mapping_idx = i + 1
                if mapping_idx % 10 == 0: idx_str += str(mapping_idx // 10)[-1]
                elif mapping_idx % 5 == 0: idx_str += "+"
                else: idx_str += "."

            for i in range(0, design['min_len'], 80):
                chunk_idx = idx_str[i:i+80]
                chunk_wt = wt[i:i+80]
                chunk_des = des[i:i+80]
                chunk_mark = mark_line[i:i+80]
                
                html_lines.append(f'<span style="color: #569cd6;">IDX : {chunk_idx}</span><br>')
                html_lines.append(f'<span style="color: #808080;">WT  : {chunk_wt}</span><br>')
                
                html_lines.append('DES : ')
                for j, char in enumerate(chunk_des):
                    if chunk_mark[j] == "*":
                        html_lines.append(f'<b><span style="color: #ffffff; background-color: #f44336;">{char}</span></b>')
                    else:
                        html_lines.append(f'<span style="color: #d4d4d4;">{char}</span>')
                html_lines.append('<br>')
                
                if "*" in chunk_mark:
                    formatted_mark = chunk_mark.replace('*', '<b><span style="color: #f44336;">*</span></b>')
                    html_lines.append(f'MRK : {formatted_mark}<br>')
                else:
                    html_lines.append(f'      {chunk_mark}<br>')
                    
                html_lines.append('<br>')
                
            html_lines.append('<span style="color: #808080;">--------------------------------------------------------------------------------</span><br><br>')

        html_lines.append('</pre>')
        self.result_display.setHtml("".join(html_lines))


    def export_top_fasta(self):
        if not self.top_designs_data:
            QMessageBox.warning(self, "提示", "请先点击【开始智能阅卷】解析数据！")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存 TOP 序列为 FASTA", 
            f"MPNN_top_{len(self.top_designs_data)}.fasta",
            "FASTA Files (*.fasta *.fa)"
        )
        
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    for i, design in enumerate(self.top_designs_data):
                        header = f">TOP_{i+1} | Score:{design['score']:.4f} | NSR:{design['recovery_rate']:.2f}% | Mut:{design['mut_count']} | Source:{design['filename']}\n"
                        f.write(header)
                        seq = design['des_seq']
                        for j in range(0, len(seq), 80):
                            f.write(seq[j:j+80] + "\n")
                QMessageBox.information(self, "成功", f"成功导出 {len(self.top_designs_data)} 条极品序列！")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))

    def export_csv_report(self):
        if not self.top_designs_data:
            QMessageBox.warning(self, "提示", "请先点击【开始智能阅卷】解析数据！")
            return
            
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存统计报表为 CSV", 
            f"MPNN_Report_top_{len(self.top_designs_data)}.csv",
            "CSV Files (*.csv)"
        )
        
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["排名", "骨架来源", "MPNN 分数", "突变数量", "序列恢复率(%)", "设计序列 (DES)"])
                    
                    for i, design in enumerate(self.top_designs_data):
                        writer.writerow([
                            i + 1,
                            design['filename'],
                            f"{design['score']:.4f}",
                            design['mut_count'],
                            f"{design['recovery_rate']:.2f}",
                            design['des_seq']
                        ])
                QMessageBox.information(self, "成功", "已成功导出 CSV 数据报表！\n您可以直接使用 Excel 加载它。")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))

class MPNNAnalyzerPlugin(BasePlugin):
    plugin_id = "mpnn_analyzer"
    plugin_name = "MPNN 智能阅卷器"
    icon = "📉"
    trigger_tag = "序列评估"

    def get_ui(self, parent=None):
        return MPNNAnalyzerUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        card = PrimaryPushSettingCard(
            "配置 MPNN 阅卷预设值", 
            FIF.SETTING, 
            "📉 MPNN 智能阅卷器", 
            "设置默认提取的 TOP 排名数量及源文件路径", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("MPNN 阅卷器 全局默认参数")
            dlg.resize(400, 250)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }")
            layout = QVBoxLayout(dlg)
            settings_ui = MPNNAnalyzerUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        if not os.path.isdir(file_path):
            return "", "【MPNN 智能阅卷】跳过：请选中一个包含 .fa 文件的序列文件夹（如 seqs）"
            
        fasta_files = glob.glob(os.path.join(file_path, "*.fa"))
        if not fasta_files:
            return "", "【MPNN 智能阅卷】跳过：未在目录中检测到 FASTA 文件。"

        config = GlobalConfig.get_all_plugin_settings("mpnn_analyzer")
        top_n = config.get("top_n", 10) if config else 10

        all_designs = []
        for fp in fasta_files:
            base_filename = os.path.basename(fp)
            with open(fp, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            wt_seq, current_seq = "", ""
            current_score = 999.0
            is_first_seq = True
            for line in lines:
                line = line.strip()
                if not line: continue
                if line.startswith(">"):
                    if is_first_seq:
                        if current_seq:  
                            wt_seq = current_seq
                            current_seq = ""
                            is_first_seq = False
                    else:
                        if current_seq:  
                            all_designs.append({'filename': base_filename, 'score': current_score, 'wt_seq': wt_seq, 'des_seq': current_seq})
                            current_seq = "" 
                    if "score=" in line:
                        try: current_score = float(line.split("score=")[1].split(",")[0].strip())
                        except: current_score = 999.0
                    else: current_score = 999.0
                else: current_seq += line
            if not is_first_seq and current_seq:
                all_designs.append({'filename': base_filename, 'score': current_score, 'wt_seq': wt_seq, 'des_seq': current_seq})

        if not all_designs: return "", "【MPNN 智能阅卷】跳过：文件格式未能正确解析。"

        all_designs.sort(key=lambda x: x['score'])
        top_designs = all_designs[:top_n]
        
        report_path = os.path.join(archive_dir, f"Auto_MPNN_Report_Top{top_n}.csv")
        with open(report_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["排名", "骨架来源", "MPNN 分数", "突变数量", "序列恢复率(%)", "设计序列 (DES)"])
            for i, design in enumerate(top_designs):
                wt = design['wt_seq']
                des = design['des_seq']
                min_len = min(len(wt), len(des))
                mut_count = sum([1 for w, d in zip(wt[:min_len], des[:min_len]) if w != d])
                recovery_rate = ((min_len - mut_count) / min_len) * 100 if min_len > 0 else 0.0
                writer.writerow([i + 1, design['filename'], f"{design['score']:.4f}", mut_count, f"{recovery_rate:.2f}", design['des_seq']])

        return report_path, f"👑 【MPNN 智能阅卷完毕】已从 {len(all_designs)} 条序列中筛选出 TOP {len(top_designs)} 写入系统归档库。"