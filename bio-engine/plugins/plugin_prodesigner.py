# plugins/plugin_prodesigner.py
"""
ProDesigner 静态架构师插件
支持生成 RFdiffusion 和 ProteinMPNN 级联运行的流水线 Shell 脚本及 JSONL 约束文件，
具备 PDB 二级结构扫描、多链对齐可视化与一键导出功能。
"""

import os
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, 
                             QStackedWidget, QMessageBox, QDialog)
from PyQt5.QtGui import QFont

from qfluentwidgets import (LineEdit, CheckBox, ComboBox, BodyLabel, 
                            PushButton, PrimaryPushButton, TextEdit, 
                            PlainTextEdit, Pivot, FluentIcon as FIF, 
                            PrimaryPushSettingCard, ToolButton)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig

AA_MAP = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
    'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
    'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
    'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
}

class ProDesignerUI(BasePluginUI):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="pro_designer", plugin_name="静态架构师引擎", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.pdb_filepaths = []
        self.pdb_data_dict = {}
        self.jsonl_files_content = {}
        
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        action_layout = QVBoxLayout()
        btn_compile = PushButton("⚙️ 1. 编译生成流水线")
        btn_export = PrimaryPushButton("💾 2. 导出批量配置及脚本")
        
        btn_compile.clicked.connect(self.compile_pipeline)
        btn_export.clicked.connect(self.export_all)
        
        action_layout.addWidget(btn_compile)
        action_layout.addWidget(btn_export)
        self.param_layout.insertLayout(0, action_layout)
        self.param_layout.insertSpacing(1, 15)

        grp_mode, lyt_mode = self.create_group("0. 模式与数据源")
        self.combo_mode = ComboBox()
        self.combo_mode.addItems([
            "Partial Diffusion (局部微调/构象锁定)", 
            "Binder Design (蛋白结合子设计)", 
            "Motif Scaffolding", 
            "Unconditional (De novo)"
        ])
        self.add_row(lyt_mode, "设计模式:", self.combo_mode)

        chk_layout = QHBoxLayout()
        self.chk_run_rfd = CheckBox("☑️ 跑 RFdiffusion")
        self.chk_run_mpnn = CheckBox("☑️ 跑 MPNN(定长)")
        self.chk_run_rfd.setChecked(True)
        self.chk_run_mpnn.setChecked(True)
        chk_layout.addWidget(self.chk_run_rfd)
        chk_layout.addWidget(self.chk_run_mpnn)
        lyt_mode.addLayout(chk_layout)

        self.input_pdb_status = LineEdit()
        self.input_pdb_status.setPlaceholderText("尚未导入 PDB...")
        self.input_pdb_status.setReadOnly(True)
        
        # 🌟 修复点 2：必须使用 ToolButton
        btn_load_pdb = ToolButton(FIF.FOLDER)
        btn_load_pdb.setFixedWidth(40)
        btn_load_pdb.clicked.connect(self.load_pdb)
        self.add_row(lyt_mode, "导入PDB:", self.input_pdb_status, None, btn_load_pdb)
        self.add_param_widget(grp_mode)

        grp_topo, lyt_topo = self.create_group("1. 拓扑与约束 (基于原始 PDB 链名)")
        self.input_contig = LineEdit()
        self.input_contig.setText("[A1-150/0 B1-200/10-10/B211-452]")
        self.add_row(lyt_topo, "Contig:", self.input_contig)
        
        self.input_bias = LineEdit()
        self.add_row(lyt_topo, "偏好突变:", self.input_bias)
        
        self.input_fixed = LineEdit()
        self.input_fixed.setText("A, B1-770")
        self.add_row(lyt_topo, "锁定不变:", self.input_fixed)
        self.add_param_widget(grp_topo)

        grp_rfd, lyt_rfd = self.create_group("2. RFdiffusion 扩散引擎")
        self.input_hotspot = LineEdit()
        self.add_row(lyt_rfd, "靶点热区:", self.input_hotspot)
        
        self.input_partial_t = LineEdit(); self.input_partial_t.setText("15")
        self.add_row(lyt_rfd, "扰动强度:", self.input_partial_t)
        
        self.input_ss_bias = LineEdit()
        self.add_row(lyt_rfd, "SS 约束:", self.input_ss_bias)
        
        self.input_num_designs = LineEdit(); self.input_num_designs.setText("50")
        self.add_row(lyt_rfd, "生成批次:", self.input_num_designs)
        self.add_param_widget(grp_rfd)

        grp_mpnn, lyt_mpnn = self.create_group("3. ProteinMPNN 序列引擎")
        self.input_omit_aa = LineEdit(); self.input_omit_aa.setText("C")
        self.add_row(lyt_mpnn, "禁用氨基:", self.input_omit_aa)
        
        self.input_seq_per_target = LineEdit(); self.input_seq_per_target.setText("10")
        self.add_row(lyt_mpnn, "生成数量:", self.input_seq_per_target)
        
        self.chk_ss_enhance = CheckBox("🛡️ 启用二级结构保护 (禁止出P/G)")
        self.chk_ss_enhance.setChecked(True)
        lyt_mpnn.addWidget(self.chk_ss_enhance)
        self.add_param_widget(grp_mpnn)

        grp_env, lyt_env = self.create_group("4. 服务器运行环境")
        self.input_conda_sh = LineEdit(); self.input_conda_sh.setText("~/.bashrc")
        self.add_row(lyt_env, "Conda:", self.input_conda_sh)
        
        self.input_rfd_env = LineEdit(); self.input_rfd_env.setText("SE3nv")
        self.input_mpnn_env = LineEdit(); self.input_mpnn_env.setText("mlfold")
        self.add_row(lyt_env, "RF Env:", self.input_rfd_env, "MP Env:", self.input_mpnn_env)
        
        self.input_rfd_path = LineEdit()
        self.input_rfd_path.setText("/home/user/RFdiffusion/scripts/run_inference.py")
        self.add_row(lyt_env, "RF脚本:", self.input_rfd_path)
        
        self.input_mpnn_path = LineEdit()
        self.input_mpnn_path.setText("/home/user/ProteinMPNN/protein_mpnn_run.py")
        self.add_row(lyt_env, "MP脚本:", self.input_mpnn_path)
        
        self.input_server_dir = LineEdit()
        self.input_server_dir.setText("./")
        self.add_row(lyt_env, "PDB目录:", self.input_server_dir)
        
        self.input_gpu_id = LineEdit(); self.input_gpu_id.setText("0")
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

        self.align_display = TextEdit()
        self.align_display.setFont(font_code)
        self.align_display.setReadOnly(True)
        self.align_display.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; border: none;")
        self.addSubInterface(self.align_display, 'alignInterface', '1. 静态约束与结构图')

        self.bash_display = PlainTextEdit()
        self.bash_display.setFont(font_code)
        self.bash_display.setStyleSheet("background-color: #1e1e1e; color: #ce9178; border: none;")
        self.addSubInterface(self.bash_display, 'bashInterface', '2. Linux 运行脚本')

        self.json_display = TextEdit()
        self.json_display.setFont(QFont("Consolas", 10))
        self.json_display.setStyleSheet("background-color: #f4f4f4; color: #333333; border: none;")
        self.addSubInterface(self.json_display, 'jsonInterface', '3. 定长模板预览')

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
            self.chk_run_rfd.setChecked(config.get("run_rfd", self.chk_run_rfd.isChecked()))
            self.chk_run_mpnn.setChecked(config.get("run_mpnn", self.chk_run_mpnn.isChecked()))
            self.input_conda_sh.setText(config.get("conda_sh", self.input_conda_sh.text()))
            self.input_rfd_env.setText(config.get("rfd_env", self.input_rfd_env.text()))
            self.input_mpnn_env.setText(config.get("mpnn_env", self.input_mpnn_env.text()))
            self.input_rfd_path.setText(config.get("rfd_path", self.input_rfd_path.text()))
            self.input_mpnn_path.setText(config.get("mpnn_path", self.input_mpnn_path.text()))
            self.input_server_dir.setText(config.get("server_dir", self.input_server_dir.text()))
            self.input_gpu_id.setText(config.get("gpu_id", self.input_gpu_id.text()))

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
            "run_rfd": self.chk_run_rfd.isChecked(),
            "run_mpnn": self.chk_run_mpnn.isChecked(),
            "conda_sh": self.input_conda_sh.text(),
            "rfd_env": self.input_rfd_env.text(),
            "mpnn_env": self.input_mpnn_env.text(),
            "rfd_path": self.input_rfd_path.text(),
            "mpnn_path": self.input_mpnn_path.text(),
            "server_dir": self.input_server_dir.text(),
            "gpu_id": self.input_gpu_id.text()
        }
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def save_settings_and_close(self):
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog):
            parent_dlg.accept()

    def load_pdb(self):
        filepaths, _ = QFileDialog.getOpenFileNames(self, "选择 PDB", "", "PDB Files (*.pdb)")
        if not filepaths: return
        self.pdb_filepaths = filepaths
        self.pdb_data_dict = {}

        try:
            for filepath in filepaths:
                pdb_name = os.path.splitext(os.path.basename(filepath))[0]
                self.pdb_data_dict[pdb_name] = {}
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith("HELIX "):
                            chain = line[19].strip()
                            self.pdb_data_dict[pdb_name].setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                            try: self.pdb_data_dict[pdb_name][chain]['helices'].append((int(line[21:25].strip()), int(line[33:37].strip())))
                            except ValueError: pass
                        elif line.startswith("SHEET "):
                            chain = line[21].strip()
                            self.pdb_data_dict[pdb_name].setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                            try: self.pdb_data_dict[pdb_name][chain]['sheets'].append((int(line[22:26].strip()), int(line[33:37].strip())))
                            except ValueError: pass
                        elif (line.startswith("ATOM  ") or line.startswith("HETATM")) and line[13:16].strip() == "CA":
                            chain = line[21].strip()
                            res_name = line[17:20].strip()
                            if res_name in AA_MAP:
                                self.pdb_data_dict[pdb_name].setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                                self.pdb_data_dict[pdb_name][chain]['seq'][int(line[22:26].strip())] = AA_MAP[res_name]
                
                for chain, data in self.pdb_data_dict[pdb_name].items():
                    sorted_res = sorted(list(data['seq'].keys()))
                    data['mapping'] = {res: i+1 for i, res in enumerate(sorted_res)}

            self.input_pdb_status.setText(f"已载入 {len(filepaths)} 个 PDB")
            QMessageBox.information(self, "成功", f"成功载入并解析了 {len(filepaths)} 个 PDB 文件 (含二级结构)！")
        except Exception as e:
            QMessageBox.critical(self, "解析错误", str(e))

    def compile_pipeline(self):
        self._save_config()
        mode = self.combo_mode.currentText()
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
                if len(item) == 1:
                    global_fixed[chain].extend(list(range(-1000, 10000)))
                elif '-' in item[1:]:
                    start, end = map(int, item[1:].split('-'))
                    global_fixed[chain].extend(list(range(start, end+1)))
                else:
                    global_fixed[chain].append(int(item[1:]))

        has_bias = len(global_bias) > 0
        has_fixed = len(global_fixed) > 0

        html_lines = []
        if self.pdb_filepaths:
            first_pdb = list(self.pdb_data_dict.keys())[0]
            data = self.pdb_data_dict[first_pdb]
            original_chains = list(data.keys())
            chain_map = {old_c: chr(65 + i) for i, old_c in enumerate(original_chains)}

            html_lines.append('<pre style="font-family: Consolas, monospace; font-size: 13px;">')
            html_lines.append(f'<span style="color: #d4d4d4;">=== 约束验证 (基于首个样本: {first_pdb}) ===</span><br>')
            html_lines.append('<span style="color: #d4d4d4;">[图例] 二级结构: H (Helix 螺旋) | E (Sheet 折叠) | C (Coil 卷曲)</span><br>')
            html_lines.append('<span style="color: #d4d4d4;">       操作约束: F (锁定区) | ')
            if has_bias: html_lines.append('B (偏好突变) | ')
            html_lines.append('- (自由扩散)</span><br><br>')
            
            for chain, cdata in data.items():
                html_lines.append(f'<b><span style="color: #569cd6;">&gt;&gt; 原链名 {chain} </span></b>')
                html_lines.append(f'<b><span style="color: #c586c0;">(RF/MPNN 中将强制重映射为 {chain_map[chain]} 链)</span></b><br>')
                
                seq_dict = cdata['seq']
                if not seq_dict: continue
                
                sorted_res = sorted(list(seq_dict.keys()))
                seq_str = "".join([seq_dict[r] for r in sorted_res])
                fix_str = "".join(["F" if (chain in global_fixed and r in global_fixed[chain]) else "-" for r in sorted_res])
                bia_str = "".join([global_bias[chain][r] if (chain in global_bias and r in global_bias[chain]) else "-" for r in sorted_res])
                
                ss_str = ""
                for r in sorted_res:
                    is_h = any(start <= r <= end for start, end in cdata.get('helices', []))
                    is_e = any(start <= r <= end for start, end in cdata.get('sheets', []))
                    if is_h: ss_str += "H"
                    elif is_e: ss_str += "E"
                    else: ss_str += "C"

                for i in range(0, len(seq_str), 60):
                    chunk_ss = ss_str[i:i+60]
                    chunk_seq = seq_str[i:i+60]
                    chunk_fix = fix_str[i:i+60]
                    chunk_bia = bia_str[i:i+60]
                    res_start = sorted_res[i]
                    
                    html_lines.append(f'<span style="color: #d4d4d4;">SS  [{res_start:4d}] : </span>')
                    for char in chunk_ss:
                        if char == 'H': html_lines.append(f'<b><span style="color: #4ec9b0;">{char}</span></b>')
                        elif char == 'E': html_lines.append(f'<b><span style="color: #c586c0;">{char}</span></b>')
                        else: html_lines.append(f'<span style="color: #808080;">{char}</span>')
                    html_lines.append('<br>')
                    
                    html_lines.append(f'<span style="color: #d4d4d4;">SEQ [{res_start:4d}] : {chunk_seq}</span><br>')
                    
                    html_lines.append('<span style="color: #d4d4d4;">FIX        : </span>')
                    for char in chunk_fix:
                        if char == 'F': html_lines.append(f'<b><span style="color: #ffffff; background-color: #4ec9b0;">{char}</span></b>')
                        else: html_lines.append(f'<span style="color: #d4d4d4;">{char}</span>')
                    html_lines.append('<br>')
                    
                    if has_bias:
                        html_lines.append('<span style="color: #d4d4d4;">BIA        : </span>')
                        for char in chunk_bia:
                            if char != '-': html_lines.append(f'<b><span style="color: #ffffff; background-color: #f44336;">{char}</span></b>')
                            else: html_lines.append(f'<span style="color: #d4d4d4;">{char}</span>')
                        html_lines.append('<br>')
                    html_lines.append('<br>')
            html_lines.append('</pre>')
            self.align_display.setHtml("".join(html_lines))
        else:
            self.align_display.setHtml("<pre><span style='color: #f44336;'>⚠️ 未载入 PDB 文件，无法生成可视化图。<br>请点击左侧【导入 PDB】按钮。</span></pre>")
        
        self.jsonl_files_content = {}
        json_html = []
        json_html.append("<pre style='font-size: 13px; color: #333333;'>")
        json_html.append("<b><span style='color: #f44336;'>💡【占位符说明】: 定长模板中的 '__PDB_NAME__' 是故意保留的！<br>因为 RF 会生成多个变体，运行 Shell 脚本时会自动用真实文件名替换它，请放心导出！</span></b><br><br>")

        if not self.pdb_filepaths:
            if has_bias:
                dummy_bias = {c: {str(res): {aa: 10000.0} for res, aa in rd.items()} for c, rd in global_bias.items()}
                self.jsonl_files_content['Target_bias_template.jsonl'] = json.dumps({"__PDB_NAME__": dummy_bias})
            if has_fixed:
                dummy_fixed = {c: [res for res in rl] for c, rl in global_fixed.items()}
                self.jsonl_files_content['Target_fixed_template.jsonl'] = json.dumps({"__PDB_NAME__": dummy_fixed})
        else:
            for pdb_name, data in self.pdb_data_dict.items():
                local_bias, local_fixed, local_omit = {}, {}, {}
                chain_map = {old_c: chr(65 + i) for i, old_c in enumerate(data.keys())}
                
                if has_bias:
                    for chain, res_dict in global_bias.items():
                        if chain in data:
                            mapped_chain = chain_map[chain]
                            local_bias[mapped_chain] = {}
                            for res_num, aa in res_dict.items():
                                if res_num in data[chain]['mapping']:
                                    local_bias[mapped_chain][str(data[chain]['mapping'][res_num])] = {aa: 10000.0}
                    self.jsonl_files_content[f'{pdb_name}_bias_template.jsonl'] = json.dumps({"__PDB_NAME__": local_bias})
                
                if has_fixed:
                    for chain, res_list in global_fixed.items():
                        if chain in data:
                            mapped_chain = chain_map[chain]
                            local_fixed[mapped_chain] = []
                            for res_num in res_list:
                                if res_num in data[chain]['mapping']:
                                    local_fixed[mapped_chain].append(data[chain]['mapping'][res_num])
                    self.jsonl_files_content[f'{pdb_name}_fixed_template.jsonl'] = json.dumps({"__PDB_NAME__": local_fixed})

                if self.chk_ss_enhance.isChecked():
                    for chain, cdata in data.items():
                        mapped_chain = chain_map[chain]
                        ss_res_list = set()
                        for start, end in cdata.get('helices', []) + cdata.get('sheets', []):
                            ss_res_list.update(list(range(start, end + 1)))
                        valid_ss = [r for r in ss_res_list if r in cdata['seq']]
                        if valid_ss:
                            local_omit[mapped_chain] = {}
                            for res_num in valid_ss:
                                if res_num in cdata['mapping']:
                                    local_omit[mapped_chain][str(cdata['mapping'][res_num])] = "PG"
                    if local_omit:
                        self.jsonl_files_content[f'{pdb_name}_omit_template.jsonl'] = json.dumps({"__PDB_NAME__": local_omit})
            
            display_pdb = list(self.pdb_data_dict.keys())[0]
            if has_fixed: json_html.append(f"<b>Fixed:</b><br>{self.jsonl_files_content.get(f'{display_pdb}_fixed_template.jsonl', '{}')}<br><br>")
            if has_bias: json_html.append(f"<b>Bias:</b><br>{self.jsonl_files_content.get(f'{display_pdb}_bias_template.jsonl', '{}')}<br><br>")
            if self.chk_ss_enhance.isChecked() and f'{display_pdb}_omit_template.jsonl' in self.jsonl_files_content:
                json_html.append(f"<b>Omit (PG拦截):</b><br>{self.jsonl_files_content.get(f'{display_pdb}_omit_template.jsonl', '{}')}<br><br>")
        
        json_html.append("</pre>")
        self.json_display.setHtml("".join(json_html))

        server_dir = self.input_server_dir.text().strip()
        if server_dir and not server_dir.endswith('/'): server_dir += '/'
        
        rfd_extras = ""
        if "Binder" in mode and self.input_hotspot.text(): rfd_extras += f" \\\n            ppi.hotspot_res=[{self.input_hotspot.text()}]"
        if "Partial" in mode: rfd_extras += f" \\\n            diffuser.partial_T={self.input_partial_t.text()}"
        
        ss_input = self.input_ss_bias.text().strip()
        if ss_input: rfd_extras += f" \\\n            scaffoldguided.scaffoldguided=True scaffoldguided.target_ss=\"{ss_input}\""
        
        rfd_block = ""
        if self.chk_run_rfd.isChecked():
            rfd_block = f"""
echo "[Step 1/2] 批量运行 RFdiffusion..."
conda activate {self.input_rfd_env.text().strip()}
for INPUT_PDB in {server_dir}*.pdb; do
    if [ -f "$INPUT_PDB" ]; then
        BASENAME=$(basename "$INPUT_PDB" .pdb)
        echo ">> 正在扩散: $BASENAME"
        python $RFD_SCRIPT \\
            inference.input_pdb="$INPUT_PDB" \\
            inference.output_prefix=$OUT_DIR/rfd_out/${{BASENAME}} \\
            contigmap.contigs="{self.input_contig.text()}" \\
            inference.num_designs={self.input_num_designs.text()}{rfd_extras} \\
            >> $OUT_DIR/logs/rfdiffusion.log 2>&1
    fi
done
"""

        sed_commands = ""
        mpnn_flags = ""

        if has_fixed:
            sed_commands += f"""
        FIXED_TPL="{server_dir}${{ORIG_NAME}}_fixed_template.jsonl"
        if [ ! -f "$FIXED_TPL" ]; then FIXED_TPL="{server_dir}Target_fixed_template.jsonl"; fi
        if [ -f "$FIXED_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$FIXED_TPL" > $OUT_DIR/current_fixed.jsonl
        fi"""
            mpnn_flags += f" \\\n            --fixed_positions_jsonl $OUT_DIR/current_fixed.jsonl"

        if has_bias:
            sed_commands += f"""
        BIAS_TPL="{server_dir}${{ORIG_NAME}}_bias_template.jsonl"
        if [ ! -f "$BIAS_TPL" ]; then BIAS_TPL="{server_dir}Target_bias_template.jsonl"; fi
        if [ -f "$BIAS_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$BIAS_TPL" > $OUT_DIR/current_bias.jsonl
        fi"""
            mpnn_flags += f" \\\n            --bias_AA_jsonl $OUT_DIR/current_bias.jsonl"

        if self.chk_ss_enhance.isChecked():
            sed_commands += f"""
        OMIT_TPL="{server_dir}${{ORIG_NAME}}_omit_template.jsonl"
        if [ -f "$OMIT_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$OMIT_TPL" > $OUT_DIR/current_omit.jsonl
        fi"""
            mpnn_flags += f" \\\n            --omit_AA_jsonl $OUT_DIR/current_omit.jsonl"

        mpnn_block = ""
        if self.chk_run_mpnn.isChecked():
            mpnn_block = f"""
echo "[Step 2/2] 批量运行 ProteinMPNN..."
echo "=========================================================="
echo "⚠️ 警告: 若你在 RF 中使用了变长 contig，请立即中断脚本！"
echo "请先使用 GUI 的【变长动态匹配】生成 JSONL 后，单独运行 MPNN！"
echo "=========================================================="

if ! ls $OUT_DIR/rfd_out/*.pdb 1> /dev/null 2>&1; then
    echo "❌ 致命错误: 在 $OUT_DIR/rfd_out/ 目录中未找到任何 .pdb 文件！"
    exit 1
fi

conda activate {self.input_mpnn_env.text().strip()}

for PDB_FILE in $OUT_DIR/rfd_out/*.pdb; do
    if [ -f "$PDB_FILE" ]; then
        FILENAME=$(basename "$PDB_FILE" .pdb)
        ORIG_NAME="${{FILENAME%_*}}"
        {sed_commands}

        python $MPNN_SCRIPT \\
            --pdb_path "$PDB_FILE" \\
            --num_seq_per_target {self.input_seq_per_target.text()} \\
            --sampling_temp 0.1 \\
            --omit_AAs "{self.input_omit_aa.text()}" \\
            --batch_size 1 \\
            --out_folder $OUT_DIR/mpnn_out/{mpnn_flags} \\
            >> $OUT_DIR/logs/proteinmpnn.log 2>&1
    fi
done
"""

        bash_script = f"""#!/bin/bash
# ============================================================================
# ProDesigner Pipeline (自动生成)
# ============================================================================
set -e
export CUDA_VISIBLE_DEVICES="{self.input_gpu_id.text().strip()}"
source {self.input_conda_sh.text().strip()}
RFD_SCRIPT="{self.input_rfd_path.text().strip()}"
MPNN_SCRIPT="{self.input_mpnn_path.text().strip()}"
OUT_DIR="{server_dir}design_output_batch"

mkdir -p $OUT_DIR/rfd_out $OUT_DIR/logs $OUT_DIR/mpnn_out
{rfd_block}{mpnn_block}
echo "任务圆满结束！"
"""
        self.bash_display.setPlainText(bash_script)
        self.stacked_widget.setCurrentWidget(self.bash_display)
        self.pivot.setCurrentItem('bashInterface')

    def export_all(self):
        if not self.bash_display.toPlainText().strip():
            QMessageBox.warning(self, "警告", "请先点击【编译生成流水线】！")
            return
        export_dir = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if export_dir:
            try:
                with open(os.path.join(export_dir, "run_pipeline.sh"), 'w', encoding='utf-8', newline='\n') as f:
                    f.write(self.bash_display.toPlainText().strip() + "\n")
                
                for filename, content in self.jsonl_files_content.items():
                    with open(os.path.join(export_dir, filename), 'w', encoding='utf-8') as f:
                        f.write(content + "\n")
                        
                QMessageBox.information(self, "成功", f"流水线脚本和 {len(self.jsonl_files_content)} 个约束模板已成功导出！\n(占位符将在服务器运行时自动替换)")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", str(e))

class ProDesignerPlugin(BasePlugin):
    plugin_id = "pro_designer"
    plugin_name = "静态架构师引擎"
    icon = "🏗️"
    trigger_tag = "蛋白设计"

    def get_ui(self, parent=None):
        return ProDesignerUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        card = PrimaryPushSettingCard(
            "配置默认服务器路径参数", 
            FIF.SETTING, 
            "🏗️ 静态架构师引擎", 
            "修改默认的 Conda 环境、脚本路径和工作目录等偏好设置", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("静态架构师 全局默认参数预设中心")
            dlg.resize(600, 800)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }")
            layout = QVBoxLayout(dlg)
            settings_ui = ProDesignerUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        return "", "【ProDesigner 静态架构师引擎】这是一个高度交互式插件，请在 UI 界面中完成配置与生成。"