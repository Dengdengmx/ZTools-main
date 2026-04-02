# plugins/plugin_dynamic_matcher.py
"""
RFdiffusion & ProteinMPNN 变长设计与动态匹配器插件
用于在 SciForge 中进行结构设计的多链约束、拓扑规划、批处理脚本生成与动态对齐。
"""

import os
import json
import glob
import html
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, 
                             QStackedWidget, QMessageBox, QDialog)
from PyQt5.QtGui import QFont

from qfluentwidgets import (LineEdit, SpinBox, CheckBox, ComboBox,
                            BodyLabel, PushButton, PrimaryPushButton,
                            StrongBodyLabel, TextEdit, PlainTextEdit, 
                            Pivot, FluentIcon as FIF, PrimaryPushSettingCard, ToolButton)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig

AA_MAP = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
    'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
    'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
    'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
}


class DynamicMatcherUI(BasePluginUI):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="dynamic_matcher", plugin_name="变长设计与动态匹配引擎", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.orig_pdb_path = ""
        self.pdb_data_dict = {}
        self.generated_fixed_data = {}
        self.generated_bias_data = {}
        self.generated_omit_data = {}
        
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        action_layout = QVBoxLayout()
        btn_rfd = PushButton("⚙️ 1. 验证约束并编译 RF")
        btn_mpnn = PushButton("🚀 2. 匹配并编译 MPNN")
        btn_export = PrimaryPushButton("💾 3. 智能按需导出所有配置")
        
        btn_rfd.clicked.connect(self.compile_rfd_step)
        btn_mpnn.clicked.connect(self.compile_mpnn_step)
        btn_export.clicked.connect(self.export_all)
        
        action_layout.addWidget(btn_rfd)
        action_layout.addWidget(btn_mpnn)
        action_layout.addWidget(btn_export)
        self.param_layout.insertLayout(0, action_layout)
        self.param_layout.insertSpacing(1, 15)

        grp_io, lyt_io = self.create_group("1. 模式与本地数据交互")
        self.combo_mode = ComboBox()
        self.combo_mode.addItems(["Partial Diffusion (仅限严格定长微调)", 
                                  "Motif Scaffolding (变长与搭桥推荐)", 
                                  "Binder Design (蛋白结合子设计)", 
                                  "Unconditional (De novo)"])
        self.combo_mode.setCurrentText("Motif Scaffolding (变长与搭桥推荐)")
        self.add_row(lyt_io, "设计模式:", self.combo_mode)
        
        self.input_orig_pdb = LineEdit()
        # 🌟 修复点 2：必须使用 ToolButton
        btn_load_pdb = ToolButton(FIF.FOLDER)
        btn_load_pdb.setFixedWidth(40)
        btn_load_pdb.clicked.connect(self.load_orig_pdb)
        self.add_row(lyt_io, "原始 PDB:", self.input_orig_pdb, None, btn_load_pdb)
        
        self.input_rf_dir = LineEdit()
        btn_load_rf = ToolButton(FIF.FOLDER)
        btn_load_rf.setFixedWidth(40)
        btn_load_rf.clicked.connect(self.select_rf_dir)
        self.add_row(lyt_io, "RF 输出目录:", self.input_rf_dir, None, btn_load_rf)
        self.add_param_widget(grp_io)

        grp_topo, lyt_topo = self.create_group("2. 拓扑与约束 (基于原始 PDB 编号)")
        self.input_contig = LineEdit()
        self.input_contig.setText("[A1-150/0 B1-200/10-10/B211-452]")
        self.add_row(lyt_topo, "Contig:", self.input_contig)
        
        self.input_bias = LineEdit()
        self.input_bias.setText("B771:P, A150:C")
        self.add_row(lyt_topo, "偏好突变:", self.input_bias)
        
        self.input_fixed = LineEdit()
        self.input_fixed.setText("A, B53-63, B80-120")
        self.add_row(lyt_topo, "锁定不变:", self.input_fixed)
        self.add_param_widget(grp_topo)

        grp_rfd, lyt_rfd = self.create_group("3. RFdiffusion 引擎参数")
        self.input_hotspot = LineEdit()
        self.add_row(lyt_rfd, "靶点热区:", self.input_hotspot)
        
        self.input_partial_t = LineEdit()
        self.input_partial_t.setText("15")
        self.add_row(lyt_rfd, "扰动强度:", self.input_partial_t)
        
        self.input_ss_bias = LineEdit()
        self.add_row(lyt_rfd, "SS 约束:", self.input_ss_bias)
        
        self.input_num_designs = LineEdit()
        self.input_num_designs.setText("50")
        self.add_row(lyt_rfd, "生成批次:", self.input_num_designs)
        self.add_param_widget(grp_rfd)

        grp_mpnn, lyt_mpnn = self.create_group("4. ProteinMPNN 引擎参数")
        self.input_omit_aa = LineEdit()
        self.input_omit_aa.setText("C")
        self.add_row(lyt_mpnn, "禁用氨基酸:", self.input_omit_aa)
        
        self.input_seq_per_target = LineEdit()
        self.input_seq_per_target.setText("10")
        self.add_row(lyt_mpnn, "骨架生成数:", self.input_seq_per_target)
        
        self.chk_ss_enhance = CheckBox("🛡️ 启用二级结构保护 (禁止在螺旋/折叠区产生P/G)")
        self.chk_ss_enhance.setChecked(True)
        lyt_mpnn.addWidget(self.chk_ss_enhance)
        self.add_param_widget(grp_mpnn)

        grp_env, lyt_env = self.create_group("5. 服务器运行环境设定")
        self.input_conda_sh = LineEdit()
        self.input_conda_sh.setText("~/.bashrc")
        self.add_row(lyt_env, "Conda:", self.input_conda_sh)
        
        self.input_rfd_env = LineEdit(); self.input_rfd_env.setText("SE3nv")
        self.input_mpnn_env = LineEdit(); self.input_mpnn_env.setText("mlfold")
        self.add_row(lyt_env, "RF Env:", self.input_rfd_env, "MP Env:", self.input_mpnn_env)
        
        self.input_rfd_path = LineEdit()
        self.input_rfd_path.setText("/home/user/RFdiffusion/scripts/run_inference.py")
        self.add_row(lyt_env, "RF 脚本:", self.input_rfd_path)
        
        self.input_mpnn_path = LineEdit()
        self.input_mpnn_path.setText("/home/user/ProteinMPNN/protein_mpnn_run.py")
        self.add_row(lyt_env, "MP 脚本:", self.input_mpnn_path)
        
        self.input_server_dir = LineEdit()
        self.input_server_dir.setText("/home/user/my_project/")
        self.add_row(lyt_env, "工作主目录:", self.input_server_dir)
        
        self.input_gpu_id = LineEdit()
        self.input_gpu_id.setText("0")
        self.add_row(lyt_env, "GPU ID:", self.input_gpu_id)
        
        self.add_param_widget(grp_env)
        self.add_param_stretch()

        if self.is_setting_mode:
            btn_save_config = PrimaryPushButton("💾 保存为全局默认参数", icon=FIF.SAVE)
            btn_save_config.setFixedHeight(45)
            btn_save_config.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(btn_save_config)
            return

        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pivot = Pivot(self.canvas_panel)
        self.stacked_widget = QStackedWidget(self.canvas_panel)
        
        vbox = QVBoxLayout()
        vbox.addWidget(self.pivot)
        vbox.addWidget(self.stacked_widget)
        self.canvas_layout.addLayout(vbox)

        font_code = QFont("Consolas", 11)
        font_log = QFont("Consolas", 10)

        self.align_display = TextEdit()
        self.align_display.setFont(font_code)
        self.align_display.setReadOnly(True)
        self.align_display.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: none;")
        self.addSubInterface(self.align_display, 'alignInterface', '📊 多链结构验证图')

        self.rfd_display = PlainTextEdit()
        self.rfd_display.setFont(font_code)
        self.rfd_display.setStyleSheet("background-color: #1e1e1e; color: #ce9178; border: none;")
        self.addSubInterface(self.rfd_display, 'rfdInterface', '📜 1_run_rfd.sh')

        self.log_display = TextEdit()
        self.log_display.setFont(font_log)
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: none;")
        self.addSubInterface(self.log_display, 'logInterface', '🔍 顺序寻迹日志')

        self.mpnn_display = PlainTextEdit()
        self.mpnn_display.setFont(font_code)
        self.mpnn_display.setStyleSheet("background-color: #1e1e1e; color: #c586c0; border: none;")
        self.addSubInterface(self.mpnn_display, 'mpnnInterface', '📜 2_run_mpnn.sh')

        self.json_display = PlainTextEdit()
        self.json_display.setFont(font_log)
        self.json_display.setStyleSheet("background-color: #f4f4f4; color: #333333; border: none;")
        self.addSubInterface(self.json_display, 'jsonInterface', '📦 聚合 JSONL')

        self.stacked_widget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem('alignInterface')

    def addSubInterface(self, widget, objectName, text):
        widget.setObjectName(objectName)
        self.stacked_widget.addWidget(widget)
        self.pivot.addItem(routeKey=objectName, text=text, onClick=lambda: self.stacked_widget.setCurrentWidget(widget))

    def onCurrentIndexChanged(self, index):
        widget = self.stacked_widget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

    def _load_config(self):
        config = GlobalConfig.get_all_plugin_settings(self.plugin_id)
        if config:
            self.combo_mode.setCurrentText(config.get("mode", self.combo_mode.currentText()))
            self.input_contig.setText(config.get("contig", self.input_contig.text()))
            self.input_bias.setText(config.get("bias", self.input_bias.text()))
            self.input_fixed.setText(config.get("fixed", self.input_fixed.text()))
            self.input_hotspot.setText(config.get("hotspot", self.input_hotspot.text()))
            self.input_partial_t.setText(config.get("partial_t", self.input_partial_t.text()))
            self.input_ss_bias.setText(config.get("ss_bias", self.input_ss_bias.text()))
            self.input_num_designs.setText(config.get("num_designs", self.input_num_designs.text()))
            self.input_omit_aa.setText(config.get("omit_aa", self.input_omit_aa.text()))
            self.input_seq_per_target.setText(config.get("seq_per_target", self.input_seq_per_target.text()))
            self.chk_ss_enhance.setChecked(config.get("ss_enhance", self.chk_ss_enhance.isChecked()))
            self.input_conda_sh.setText(config.get("conda_sh", self.input_conda_sh.text()))
            self.input_rfd_env.setText(config.get("rfd_env", self.input_rfd_env.text()))
            self.input_mpnn_env.setText(config.get("mpnn_env", self.input_mpnn_env.text()))
            self.input_rfd_path.setText(config.get("rfd_path", self.input_rfd_path.text()))
            self.input_mpnn_path.setText(config.get("mpnn_path", self.input_mpnn_path.text()))
            self.input_server_dir.setText(config.get("server_dir", self.input_server_dir.text()))
            self.input_gpu_id.setText(config.get("gpu_id", self.input_gpu_id.text()))
            self.input_orig_pdb.setText(config.get("orig_pdb", ""))
            self.input_rf_dir.setText(config.get("rf_dir", ""))

    def _save_config(self):
        config = {
            "mode": self.combo_mode.currentText(),
            "contig": self.input_contig.text(),
            "bias": self.input_bias.text(),
            "fixed": self.input_fixed.text(),
            "hotspot": self.input_hotspot.text(),
            "partial_t": self.input_partial_t.text(),
            "ss_bias": self.input_ss_bias.text(),
            "num_designs": self.input_num_designs.text(),
            "omit_aa": self.input_omit_aa.text(),
            "seq_per_target": self.input_seq_per_target.text(),
            "ss_enhance": self.chk_ss_enhance.isChecked(),
            "conda_sh": self.input_conda_sh.text(),
            "rfd_env": self.input_rfd_env.text(),
            "mpnn_env": self.input_mpnn_env.text(),
            "rfd_path": self.input_rfd_path.text(),
            "mpnn_path": self.input_mpnn_path.text(),
            "server_dir": self.input_server_dir.text(),
            "gpu_id": self.input_gpu_id.text(),
            "orig_pdb": self.input_orig_pdb.text(),
            "rf_dir": self.input_rf_dir.text()
        }
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def save_settings_and_close(self):
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog):
            parent_dlg.accept()

    def parse_pdb_atoms(self, filepath):
        pdb_data = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    if line.startswith("HELIX "):
                        chain = line[19].strip()
                        pdb_data.setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                        pdb_data[chain]['helices'].append((int(line[21:25].strip()), int(line[33:37].strip())))
                    elif line.startswith("SHEET "):
                        chain = line[21].strip()
                        pdb_data.setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                        pdb_data[chain]['sheets'].append((int(line[22:26].strip()), int(line[33:37].strip())))
                    elif (line.startswith("ATOM  ") or line.startswith("HETATM")) and line[13:16].strip() == "CA":
                        chain = line[21].strip()
                        res_name = line[17:20].strip()
                        if res_name in AA_MAP:
                            pdb_data.setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                            res_num_raw = line[22:27].strip()
                            res_num_str = "".join([c for c in res_num_raw if c.isdigit() or c == '-'])
                            if res_num_str:
                                pdb_data[chain]['seq'][int(res_num_str)] = AA_MAP[res_name]
                except Exception:
                    pass 
        return pdb_data

    def load_orig_pdb(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "选择原始 PDB", "", "PDB Files (*.pdb)")
        if filepath:
            self.input_orig_pdb.setText(filepath)
            self.orig_pdb_path = filepath
            self.pdb_data_dict.clear()
            pdb_name = os.path.splitext(os.path.basename(filepath))[0]
            self.pdb_data_dict[pdb_name] = self.parse_pdb_atoms(filepath)
            QMessageBox.information(self, "成功", "原始 PDB 载入成功！(已滤除潜在插入码)")
            self._save_config()

    def select_rf_dir(self):
        dirpath = QFileDialog.getExistingDirectory(self, "选择 RF 输出目录")
        if dirpath: 
            self.input_rf_dir.setText(dirpath)
            self._save_config()

    def log(self, text, level="info"):
        color_map = {
            "info": "#569cd6",
            "success": "#4ec9b0",
            "warn": "#f44336"
        }
        color = color_map.get(level, "#d4d4d4")
        bold = 'font-weight: bold;' if level in ['success', 'warn'] else ''
        html_text = f'<span style="color: {color}; {bold}">{html.escape(text)}</span><br>'
        
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.End)
        self.log_display.setTextCursor(cursor)
        self.log_display.insertHtml(html_text)
        self.log_display.ensureCursorVisible()

    def _ensure_pdb_loaded(self):
        if not self.pdb_data_dict:
            path = self.input_orig_pdb.text().strip()
            if path and os.path.exists(path):
                self.orig_pdb_path = path
                pdb_name = os.path.splitext(os.path.basename(path))[0]
                self.pdb_data_dict[pdb_name] = self.parse_pdb_atoms(path)
                return True
            return False
        return True

    def compile_rfd_step(self):
        self._save_config()
        if not self._ensure_pdb_loaded():
            QMessageBox.warning(self, "警告", "请先正确填写或导入【本地原始 PDB】！")
            return

        global_bias, global_fixed = {}, {}
        
        if self.input_bias.text().strip():
            for p in [x.strip() for x in self.input_bias.text().split(',')]:
                if ':' in p:
                    loc, aa = p.split(':')
                    try: global_bias.setdefault(loc[0], {})[int(loc[1:])] = aa.upper()
                    except ValueError: pass

        if self.input_fixed.text().strip():
            for item in self.input_fixed.text().split(','):
                item = item.strip()
                if not item: continue
                chain = item[0]
                if chain not in global_fixed: global_fixed[chain] = []
                if len(item) == 1: global_fixed[chain].extend(list(range(-1000, 10000)))
                elif '-' in item[1:]:
                    s, e = map(int, item[1:].split('-'))
                    global_fixed[chain].extend(list(range(s, e+1)))
                else: global_fixed[chain].append(int(item[1:]))

        has_bias = len(global_bias) > 0

        html_lines = []
        html_lines.append('<pre style="font-family: Consolas, monospace; font-size: 13px;">')
        html_lines.append('<b><span style="color: #569cd6;">&gt;&gt;&gt; 多链突变设计与二级结构校验图 &lt;&lt;&lt;</span></b><br><br>')
        html_lines.append('<b><span style="color: #f44336;">[说明] 这里的 IDX 仅代表原 WT 样本中的连续顺序，不代表生成后的变长编号。</span></b><br>')
        html_lines.append('       二级结构: H (螺旋) E (折叠) C (卷曲)<br>')
        html_lines.append('       约束: F (锁定区) | ')
        if has_bias: html_lines.append('B (偏好突变) | ')
        html_lines.append('- (自由扩散)<br><br>')

        pdb_name = list(self.pdb_data_dict.keys())[0]
        data = self.pdb_data_dict[pdb_name]
        
        for chain, cdata in data.items():
            html_lines.append(f'<b><span style="color: #569cd6;">========== Chain {chain} ==========</span></b><br>')
            seq_dict = cdata['seq']
            if not seq_dict: continue
            
            sorted_res = sorted(list(seq_dict.keys()))
            seq_str = "".join([seq_dict[r] for r in sorted_res])
            fix_str = "".join(["F" if (chain in global_fixed and r in global_fixed[chain]) else "-" for r in sorted_res])
            bia_str = "".join([global_bias[chain][r] if (chain in global_bias and r in global_bias[chain]) else "-" for r in sorted_res])
            
            ss_str = ""
            idx_str = ""
            for i, r in enumerate(sorted_res):
                is_h = any(start <= r <= end for start, end in cdata.get('helices', []))
                is_e = any(start <= r <= end for start, end in cdata.get('sheets', []))
                if is_h: ss_str += "H"
                elif is_e: ss_str += "E"
                else: ss_str += "C"
                
                mapping_idx = i + 1
                if mapping_idx % 10 == 0: idx_str += str(mapping_idx // 10)[-1]
                elif mapping_idx % 5 == 0: idx_str += "+"
                else: idx_str += "."
            
            for i in range(0, len(seq_str), 60):
                chunk_ss = ss_str[i:i+60]
                chunk_seq = seq_str[i:i+60]
                chunk_fix = fix_str[i:i+60]
                chunk_bia = bia_str[i:i+60]
                chunk_idx = idx_str[i:i+60]
                res_start = sorted_res[i] 
                renum_start = i + 1 
                
                html_lines.append(f'<span style="color: #569cd6;">IDX [{renum_start:4d}] : {chunk_idx}</span><br>')
                
                html_lines.append(f'SS  [{res_start:4d}] : ')
                for char in chunk_ss:
                    if char == 'H': html_lines.append(f'<b><span style="color: #4ec9b0;">{char}</span></b>')
                    elif char == 'E': html_lines.append(f'<b><span style="color: #c586c0;">{char}</span></b>')
                    else: html_lines.append(f'<span style="color: #808080;">{char}</span>')
                html_lines.append('<br>')
                
                html_lines.append(f'SEQ [{res_start:4d}] : {chunk_seq}<br>')
                
                html_lines.append('FIX        : ')
                for char in chunk_fix:
                    if char == 'F': html_lines.append(f'<b><span style="color: #ffffff; background-color: #4ec9b0;">{char}</span></b>')
                    else: html_lines.append(char)
                html_lines.append('<br>')
                
                if has_bias:
                    html_lines.append('BIA        : ')
                    for char in chunk_bia:
                        if char != '-': html_lines.append(f'<b><span style="color: #ffffff; background-color: #f44336;">{char}</span></b>')
                        else: html_lines.append(char)
                    html_lines.append('<br>')
                html_lines.append('<br>')

        html_lines.append('</pre>')
        self.align_display.setHtml("".join(html_lines))

        mode = self.combo_mode.currentText()
        server_dir = self.input_server_dir.text().strip()
        if server_dir and not server_dir.endswith('/'): server_dir += '/'
        
        rfd_extras = ""
        if "Binder" in mode and self.input_hotspot.text(): rfd_extras += f" \\\n            ppi.hotspot_res=[{self.input_hotspot.text()}]"
        if "Partial" in mode: rfd_extras += f" \\\n            diffuser.partial_T={self.input_partial_t.text()}"
        
        ss_input = self.input_ss_bias.text().strip()
        if ss_input:
            rfd_extras += f" \\\n            scaffoldguided.scaffoldguided=True scaffoldguided.target_ss=\"{ss_input}\""

        rfd_bash = f"""#!/bin/bash
# ==========================================
# 步骤 1: 运行 RFdiffusion
# ==========================================
set -e
export CUDA_VISIBLE_DEVICES="{self.input_gpu_id.text().strip()}"
source {self.input_conda_sh.text().strip()}
conda activate {self.input_rfd_env.text().strip()}

INPUT_DIR="{server_dir}input_pdbs"
OUT_DIR="{server_dir}rfd_out"
mkdir -p $OUT_DIR

echo ">> 开始批量扩散..."
for INPUT_PDB in $INPUT_DIR/*.pdb; do
    if [ -f "$INPUT_PDB" ]; then
        BASENAME=$(basename "$INPUT_PDB" .pdb)
        python {self.input_rfd_path.text().strip()} \\
            inference.input_pdb="$INPUT_PDB" \\
            inference.output_prefix=$OUT_DIR/${{BASENAME}} \\
            contigmap.contigs="{self.input_contig.text()}" \\
            inference.num_designs={self.input_num_designs.text()}{rfd_extras} \\
            >> {server_dir}rfdiffusion.log 2>&1
    fi
done
echo "RFdiffusion 完成！请将生成的 PDB 下载至本地运行【第 2 步：动态匹配】。"
"""
        self.rfd_display.setPlainText(rfd_bash)
        self.stacked_widget.setCurrentWidget(self.rfd_display)
        self.pivot.setCurrentItem('rfdInterface')
        QMessageBox.information(self, "成功", "多链验证图已渲染完毕，RF 脚本就绪！")


    def compile_mpnn_step(self):
        self._save_config()
        if not self._ensure_pdb_loaded():
            QMessageBox.warning(self, "提示", "请确保已输入【原始 PDB】！")
            return
            
        orig_pdb = self.input_orig_pdb.text().strip()
        rf_dir = self.input_rf_dir.text().strip()
        
        if not orig_pdb or not rf_dir:
            QMessageBox.warning(self, "提示", "匹配前请选择【下载的 rfd_out 目录】！")
            return

        self.log_display.clear()
        self.log(">>> 启动 [固定区块顺序寻迹] 防弹追踪引擎...", "info")
        
        try:
            orig_data = self.parse_pdb_atoms(orig_pdb)
            global_fixed, global_bias, global_omit = {}, {}, {}
            
            if self.input_fixed.text().strip():
                for item in self.input_fixed.text().split(','):
                    item = item.strip()
                    if not item: continue
                    chain = item[0]
                    if len(item) == 1: global_fixed.setdefault(chain, []).extend(list(range(-1000, 10000)))
                    elif '-' in item[1:]:
                        s, e = map(int, item[1:].split('-'))
                        global_fixed.setdefault(chain, []).extend(list(range(s, e+1)))
                    else: global_fixed.setdefault(chain, []).append(int(item[1:]))

            if self.input_bias.text().strip():
                for p in [x.strip() for x in self.input_bias.text().split(',')]:
                    if ':' in p:
                        loc, aa = p.split(':')
                        try: global_bias.setdefault(loc[0], {})[int(loc[1:])] = aa.upper()
                        except ValueError: pass

            if self.chk_ss_enhance.isChecked():
                for chain, data in orig_data.items():
                    ss_res_list = set()
                    for start, end in data['helices'] + data['sheets']:
                        ss_res_list.update(list(range(start, end + 1)))
                    valid_ss = [r for r in ss_res_list if r in data['seq']]
                    if valid_ss: global_omit[chain] = valid_ss
            
            has_fixed, has_bias, has_omit = len(global_fixed)>0, len(global_bias)>0, len(global_omit)>0
            rf_pdbs = glob.glob(os.path.join(rf_dir, "*.pdb"))
            self.log(f"找到 {len(rf_pdbs)} 个新骨架，执行安全处理...", "info")
            
            self.generated_fixed_data, self.generated_bias_data, self.generated_omit_data = {}, {}, {}
            success_count = 0
            fail_count = 0

            for rf_path in rf_pdbs:
                rf_name = os.path.splitext(os.path.basename(rf_path))[0]
                
                try:
                    rf_data = self.parse_pdb_atoms(rf_path)
                    rf_fixed, rf_bias, rf_omit = {}, {}, {}
                    orig_to_rf_map = {}
                    
                    for orig_chain in global_fixed:
                        if orig_chain not in orig_data: continue
                        orig_to_rf_map.setdefault(orig_chain, {})
                        
                        req_nums = sorted(list(set(global_fixed[orig_chain])))
                        if not req_nums: continue
                        
                        blocks = []
                        current_block = [req_nums[0]]
                        for i in range(1, len(req_nums)):
                            if req_nums[i] == req_nums[i-1] + 1:
                                current_block.append(req_nums[i])
                            else:
                                blocks.append(current_block)
                                current_block = [req_nums[i]]
                        blocks.append(current_block)

                        for rf_chain, rf_cdata in rf_data.items():
                            rf_nums = sorted(list(rf_cdata['seq'].keys()))
                            rf_seq = "".join([rf_cdata['seq'][r] for r in rf_nums])
                            
                            search_start_idx = 0
                            temp_map = {}
                            matched_all_blocks = True
                            
                            for block in blocks:
                                valid_block = [r for r in block if r in orig_data[orig_chain]['seq']]
                                if not valid_block: continue
                                probe_seq = "".join([orig_data[orig_chain]['seq'][r] for r in valid_block])
                                
                                found_idx = rf_seq.find(probe_seq, search_start_idx)
                                
                                if found_idx != -1:
                                    for i, orig_res_num in enumerate(valid_block):
                                        rf_mapped_idx = found_idx + i + 1  
                                        temp_map[orig_res_num] = (rf_chain, str(rf_mapped_idx))
                                    search_start_idx = found_idx + len(probe_seq)
                                else:
                                    matched_all_blocks = False
                                    break 
                                    
                            if matched_all_blocks and temp_map:
                                orig_to_rf_map[orig_chain].update(temp_map)
                                break 

                    def get_mapped(orig_chain, req_num):
                        if orig_chain in orig_to_rf_map and req_num in orig_to_rf_map[orig_chain]:
                            return orig_to_rf_map[orig_chain][req_num]
                        return None, None

                    for orig_chain in global_fixed:
                        if orig_chain not in orig_data: continue
                        for req_num in global_fixed[orig_chain]:
                            rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                            if rf_chain: rf_fixed.setdefault(rf_chain, []).append(int(mapped_idx))

                    for orig_chain in global_bias:
                        if orig_chain not in orig_data: continue
                        for req_num, mut_aa in global_bias[orig_chain].items():
                            rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                            if rf_chain: rf_bias.setdefault(rf_chain, {})[mapped_idx] = {mut_aa: 10000.0}

                    for orig_chain in global_omit:
                        if orig_chain not in orig_data: continue
                        for req_num in global_omit[orig_chain]:
                            rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                            if rf_chain: rf_omit.setdefault(rf_chain, {})[mapped_idx] = "PG"

                    for c in rf_fixed: rf_fixed[c] = list(set(rf_fixed[c]))
                    
                    if has_fixed: self.generated_fixed_data[rf_name] = rf_fixed
                    if has_bias: self.generated_bias_data[rf_name] = rf_bias
                    if has_omit: self.generated_omit_data[rf_name] = rf_omit
                    success_count += 1
                    
                except Exception as inner_e:
                    self.log(f"⚠️ 跳过受损文件 {rf_name}.pdb: {str(inner_e)}", "warn")
                    fail_count += 1
                
                finally:
                    if has_fixed and rf_name not in self.generated_fixed_data:
                        self.generated_fixed_data[rf_name] = {chain: [] for chain in orig_data.keys()}
                    if has_bias and rf_name not in self.generated_bias_data:
                        self.generated_bias_data[rf_name] = {chain: {} for chain in orig_data.keys()}
                    if has_omit and rf_name not in self.generated_omit_data:
                        self.generated_omit_data[rf_name] = {chain: {} for chain in orig_data.keys()}
                
            self.log(f"\n✅ 处理圆满结束！成功解算 {success_count} 个，拦截废片 {fail_count} 个。\n(已为所有废片填入空壳约束，确保 MPNN 不会崩溃)", "success")

            json_text = ""
            if self.generated_fixed_data:
                json_text += "=== 聚合 Fixed JSONL 预览 (展示首个样本) ===\n"
                sample_item = list(self.generated_fixed_data.items())[0]
                json_text += json.dumps({sample_item[0]: sample_item[1]}, indent=2) + "\n\n"
            if self.generated_bias_data:
                json_text += "=== 聚合 Bias JSONL 预览 (展示首个样本) ===\n"
                sample_item = list(self.generated_bias_data.items())[0]
                json_text += json.dumps({sample_item[0]: sample_item[1]}, indent=2) + "\n\n"
            if self.generated_omit_data:
                json_text += "=== 二级结构保护 Omit (禁用 P/G) 预览 (展示首个样本) ===\n"
                sample_item = list(self.generated_omit_data.items())[0]
                json_text += json.dumps({sample_item[0]: sample_item[1]}, indent=2) + "\n\n"
            self.json_display.setPlainText(json_text)

            server_dir = self.input_server_dir.text().strip()
            if server_dir and not server_dir.endswith('/'): server_dir += '/'
            
            mpnn_flags = ""
            if has_fixed: mpnn_flags += f" \\\n    --fixed_positions_jsonl {server_dir}dynamic_fixed.jsonl"
            if has_bias: mpnn_flags += f" \\\n    --bias_AA_jsonl {server_dir}dynamic_bias.jsonl"
            if has_omit: mpnn_flags += f" \\\n    --omit_AA_jsonl {server_dir}dynamic_omit.jsonl"

            mpnn_bash = f"""#!/bin/bash
# ==========================================
# 步骤 2: 运行 ProteinMPNN 
# ==========================================
set -e
export CUDA_VISIBLE_DEVICES="{self.input_gpu_id.text().strip()}"
source {self.input_conda_sh.text().strip()}
conda activate {self.input_mpnn_env.text().strip()}

RFD_OUT="{server_dir}rfd_out"
MPNN_OUT="{server_dir}mpnn_out"
mkdir -p $MPNN_OUT

echo ">> 开始逐个读取 RF 骨架并进行序列设计..."
for PDB_FILE in $RFD_OUT/*.pdb; do
    if [ -f "$PDB_FILE" ]; then
        BASENAME=$(basename "$PDB_FILE" .pdb)
        
        echo "   正在为 $BASENAME 设计序列..."
        python {self.input_mpnn_path.text().strip()} \\
            --pdb_path "$PDB_FILE" \\
            --out_folder $MPNN_OUT \\
            --num_seq_per_target {self.input_seq_per_target.text()} \\
            --sampling_temp 0.1 \\
            --omit_AAs "{self.input_omit_aa.text()}" \\
            --batch_size 1 {mpnn_flags} \\
            >> {server_dir}proteinmpnn.log 2>&1
    fi
done

echo "✅ ProteinMPNN 序列设计圆满结束！请前往 $MPNN_OUT/seqs 查看结果。"
"""
            self.mpnn_display.setPlainText(mpnn_bash)
            self.stacked_widget.setCurrentWidget(self.mpnn_display)
            self.pivot.setCurrentItem('mpnnInterface')

        except Exception as e:
            self.log(f"❌ 发生致命错误 (可能 PDB 完全不存在): {str(e)}", "warn")

    def export_all(self):
        rfd_content = self.rfd_display.toPlainText().strip()
        mpnn_content = self.mpnn_display.toPlainText().strip()
        
        if not rfd_content and not mpnn_content:
            QMessageBox.warning(self, "警告", "没有可导出的内容！")
            return
            
        raw_export_dir = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if not raw_export_dir: return
            
        try:
            export_dir = os.path.abspath(raw_export_dir)
            if not os.path.exists(export_dir):
                os.makedirs(export_dir, exist_ok=True)
                
            exported_files = []
            
            if rfd_content:
                sh_path = os.path.join(export_dir, "1_run_rfd.sh")
                with open(sh_path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(rfd_content + "\n")
                exported_files.append("📜 1_run_rfd.sh")
                
            if mpnn_content:
                sh_path = os.path.join(export_dir, "2_run_mpnn.sh")
                with open(sh_path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(mpnn_content + "\n")
                exported_files.append("📜 2_run_mpnn.sh")
            
                if self.generated_fixed_data:
                    json_path = os.path.join(export_dir, "dynamic_fixed.jsonl")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(self.generated_fixed_data) + "\n")
                    exported_files.append("📦 dynamic_fixed.jsonl (单行防覆盖版)")
                    
                if self.generated_bias_data:
                    json_path = os.path.join(export_dir, "dynamic_bias.jsonl")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(self.generated_bias_data) + "\n")
                    exported_files.append("📦 dynamic_bias.jsonl (单行防覆盖版)")
                    
                if self.generated_omit_data:
                    json_path = os.path.join(export_dir, "dynamic_omit.jsonl")
                    with open(json_path, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(self.generated_omit_data) + "\n")
                    exported_files.append("📦 dynamic_omit.jsonl (单行防覆盖版)")
                        
            QMessageBox.information(self, "导出成功", f"✅ 成功导出以下文件：\n\n" + "\n".join(exported_files))
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"系统原话：{str(e)}")


class DynamicMatcherPlugin(BasePlugin):
    plugin_id = "dynamic_matcher"
    plugin_name = "变长设计与动态匹配引擎"
    icon = "🧬"
    trigger_tag = "蛋白设计"

    def get_ui(self, parent=None):
        return DynamicMatcherUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        card = PrimaryPushSettingCard(
            "配置默认服务器路径参数", 
            FIF.SETTING, 
            "🧬 变长设计与动态匹配引擎", 
            "修改默认的 Conda 环境、脚本路径和工作目录等偏好设置", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("变长设计 全局默认参数预设中心")
            dlg.resize(600, 800)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }")
            layout = QVBoxLayout(dlg)
            settings_ui = DynamicMatcherUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        return "", "【变长设计与动态匹配引擎】这是一个高度交互式插件，请在 UI 界面中完成配置与生成。"