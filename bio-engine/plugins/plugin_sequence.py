# plugins/plugin_sequence.py
"""
多序列比对与分析插件
支持 FASTA、DNA、PDB 文件的序列读取、Needleman-Wunsch 比对、多种渲染样式、导出等功能。
(极致紧凑亮色 UI 优化版，核心算法保持纯净)
"""

import os
import json
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QFont, QPageLayout
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QFileDialog, QMessageBox, QListWidgetItem, QApplication,
                             QAbstractItemView, QDialog)
from PyQt5.QtPrintSupport import QPrinter

from qfluentwidgets import (PrimaryPushButton, PushButton, TextEdit, SubtitleLabel,
                            CardWidget, BodyLabel, StrongBodyLabel, ListWidget,
                            ComboBox, CheckBox, FluentIcon as FIF)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig

try:
    import snapgene_reader
    SNAPGENE_AVAILABLE = True
except ImportError:
    SNAPGENE_AVAILABLE = False


# ==========================================
# 前端：Sequence UI (极限紧凑与亮色美化)
# ==========================================
class SequenceUI(BasePluginUI):
    """序列比对工作台 UI"""

    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="seq_analyzer", plugin_name="多序列比对与分析", parent=parent)
        self.is_setting_mode = is_setting_mode
        self.sequences = {}
        self.aligned_sequences = {}
        self.pdb_metadata = {}
        self.setAcceptDrops(True)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """构建 UI 控件"""
        # ========== 左侧参数面板 ==========
        h_tools = QHBoxLayout()
        h_tools.setContentsMargins(0, 0, 0, 0)
        h_tools.setSpacing(4) # 【优化】紧凑间距
        btn_import_config = PushButton("📂 载入模板", icon=FIF.FOLDER)
        btn_export_config = PushButton("💾 保存模板", icon=FIF.SAVE)
        btn_import_config.clicked.connect(self.import_config)
        btn_export_config.clicked.connect(self.export_config)
        h_tools.addWidget(btn_import_config)
        h_tools.addWidget(btn_export_config)
        self.param_layout.insertLayout(0, h_tools)

        # 1. 序列数据池（仅工作台模式）
        if not self.is_setting_mode:
            group_data, layout_data = self.create_group("1. 序列队列 (支持拖拽/发至此)")
            layout_data.setSpacing(4) # 【优化】紧凑间距
            
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 0, 0, 0)
            btn_import = PrimaryPushButton("导入 FASTA/DNA/PDB...", icon=FIF.DOWNLOAD)
            btn_import.clicked.connect(self.open_file_dialog)
            btn_row.addWidget(btn_import)
            layout_data.addLayout(btn_row)

            self.list_seqs = ListWidget(self)
            self.list_seqs.setFixedHeight(130) # 【优化】稍微压榨高度留出呼吸空间
            self.list_seqs.setDragDropMode(QAbstractItemView.InternalMove)
            self.list_seqs.setDefaultDropAction(Qt.MoveAction)
            self.list_seqs.viewport().installEventFilter(self)
            layout_data.addWidget(self.list_seqs)

            btn_list_layout = QHBoxLayout()
            btn_list_layout.setContentsMargins(0, 0, 0, 0)
            btn_list_layout.setSpacing(4)
            btn_remove = PushButton("移除选中项", icon=FIF.REMOVE)
            btn_remove.clicked.connect(self.remove_selected_item)
            btn_clear = PushButton("清空", icon=FIF.DELETE)
            btn_clear.clicked.connect(self.clear_data)
            btn_list_layout.addWidget(btn_remove)
            btn_list_layout.addWidget(btn_clear)
            layout_data.addLayout(btn_list_layout)

            self.add_param_widget(group_data)

        # 2. 比对策略与输出样式（双模式共用）
        group_param, layout_param = self.create_group("2. 比对策略与输出样式")
        layout_param.setSpacing(4)
        
        self.chk_reference = CheckBox("首行为 Reference (开启突变侦测)")
        self.chk_reference.setChecked(True)
        if not self.is_setting_mode:
            self.chk_reference.stateChanged.connect(self.display_alignment)
        layout_param.addWidget(self.chk_reference)

        layout_param.addSpacing(4)
        layout_param.addWidget(StrongBodyLabel("结果渲染预设:"))
        self.combo_style = ComboBox()
        self.combo_style.addItems([
            "ProDesigner (突变高亮)",
            "独立方格标记 (自用格式)",
            "打点模式 (Dot Match)",
            "生化属性着色 (Clustal Style)",
            "ESPript (红底白字高保守)",
            "Jalview (全局属性色块)"
        ])
        self.combo_style.setFixedHeight(30)
        if not self.is_setting_mode:
            self.combo_style.currentIndexChanged.connect(self.display_alignment)
        layout_param.addWidget(self.combo_style)

        self.add_param_widget(group_param)

        # 3. 报告输出（仅工作台模式）
        if not self.is_setting_mode:
            group_export, layout_export = self.create_group("3. 报告输出")
            layout_export.setSpacing(4)
            export_layout = QHBoxLayout()
            export_layout.setContentsMargins(0, 0, 0, 0)
            export_layout.setSpacing(4)
            
            btn_export_aln = PushButton("导出 .aln")
            btn_export_pdf = PrimaryPushButton("📄 智能导出报告", icon=FIF.DOCUMENT)
            btn_export_plot = PushButton("📊 出版级图", icon=FIF.PHOTO)
            
            btn_export_aln.clicked.connect(self.export_aln)
            btn_export_pdf.clicked.connect(self.export_pdf)
            btn_export_plot.clicked.connect(self.export_publication_plot)
            
            export_layout.addWidget(btn_export_aln)
            export_layout.addWidget(btn_export_pdf)
            export_layout.addWidget(btn_export_plot)
            layout_export.addLayout(export_layout)
            self.add_param_widget(group_export)

        self.add_param_stretch()

        # 如果是设置模式，添加保存按钮并结束
        if self.is_setting_mode:
            self.btn_save_config = PrimaryPushButton("💾 确认并保存为全局默认参数", icon=FIF.SAVE)
            self.btn_save_config.setFixedHeight(45)
            self.btn_save_config.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(self.btn_save_config)
            return

        # 工作台模式：添加比对按钮
        self.btn_align = PrimaryPushButton("⚡ 执行多序列比对", icon=FIF.ALIGNMENT)
        self.btn_align.setFixedHeight(40)
        self.btn_align.clicked.connect(self.run_alignment)
        self.param_layout.addWidget(self.btn_align)

        # ========== 右侧画板 (富文本卡片化原生质感) ==========
        self.lbl_legend = BodyLabel("")
        # 【极致优化】图例卡片化
        self.lbl_legend.setStyleSheet("background-color: #FFFFFF; padding: 8px 12px; border-radius: 8px; font-size: 12px; border: 1px solid #EAEAEA;")
        self.lbl_legend.hide()
        self.get_canvas_layout().addWidget(self.lbl_legend)

        self.text_preview = TextEdit()
        self.text_preview.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.text_preview.setFont(font)
        # 【极致优化】赋予编辑器原生白纸卡片质感
        self.text_preview.setStyleSheet("QTextEdit { line-height: 1.6; background-color: #FFFFFF; border: 1px solid #EAEAEA; border-radius: 8px; padding: 10px; }")
        self.text_preview.setText("🧬 欢迎使用序列分析模块\n支持从 Data Hub 右键发送，或直接拖拽 .fasta / .dna / .pdb 文件至此。")
        self.get_canvas_layout().addWidget(self.text_preview)

    # ------------------------------------
    # 事件过滤（用于复选框点击）
    # ------------------------------------
    def eventFilter(self, source, event):
        if hasattr(self, 'list_seqs') and source == self.list_seqs.viewport() and event.type() == QEvent.MouseButtonRelease:
            item = self.list_seqs.itemAt(event.pos())
            if item:
                if event.pos().x() > 35:
                    current_state = item.checkState()
                    item.setCheckState(Qt.Unchecked if current_state == Qt.Checked else Qt.Checked)
        return super().eventFilter(source, event)

    # ------------------------------------
    # 数据摄取与 UI 交互
    # ------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.load_file(url.toLocalFile())

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择序列文件", "", "Supported Files (*.fasta *.fa *.seq *.txt *.dna *.pdb *.cif);;All Files (*)")
        for f in files:
            self.load_file(f)

    def load_file(self, file_path):
        if self.is_setting_mode or not os.path.exists(file_path):
            return
        ext = os.path.splitext(file_path)[1].lower()
        current_header = os.path.basename(file_path)

        if ext == '.dna':
            if not SNAPGENE_AVAILABLE:
                QMessageBox.warning(self, "缺少依赖", "解析 .dna 需要 snapgene_reader 库。\n请执行: pip install snapgene_reader")
                return
            try:
                seq_dict = snapgene_reader.snapgene_file_to_dict(file_path)
                self._add_sequence(current_header, seq_dict['seq'].upper())
            except Exception as e:
                QMessageBox.critical(self, "SnapGene 解析失败", str(e))
            return

        if ext in ['.pdb', '.cif']:
            try:
                self.parse_pdb_sequence(file_path, current_header)
            except Exception as e:
                QMessageBox.critical(self, "PDB 解析失败", str(e))
            return

        current_seq = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if line.startswith(">"):
                        if current_seq:
                            self._add_sequence(current_header, "".join(current_seq))
                            current_seq = []
                        current_header = line[1:]
                    else:
                        current_seq.append("".join(filter(str.isalpha, line)).upper())
                if current_seq:
                    self._add_sequence(current_header, "".join(current_seq))
        except Exception as e:
            QMessageBox.critical(self, "解析失败", f"{file_path}\n{str(e)}")

    def parse_pdb_sequence(self, file_path, base_header):
        d3to1 = {'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C', 'GLU': 'E', 'GLN': 'Q',
                 'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F',
                 'PRO': 'P', 'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'}
        seqs, nums = {}, {}
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("ATOM  ") and line[12:16].strip() == "CA":
                    res_name = line[17:20].strip()
                    chain_id = line[21].strip() or "A"
                    try: res_seq = int(line[22:26].strip())
                    except ValueError: res_seq = 0
                    if chain_id not in seqs:
                        seqs[chain_id] = []; nums[chain_id] = []
                    seqs[chain_id].append(d3to1.get(res_name, 'X'))
                    nums[chain_id].append(res_seq)

        if not seqs:
            raise ValueError("未在该文件中发现包含 CA 原子的有效多肽链。")
        for chain, seq_list in seqs.items():
            header = f"{base_header}_Chain_{chain}"
            self._add_sequence(header, "".join(seq_list), metadata=nums[chain])

    def _add_sequence(self, header, seq, metadata=None):
        base_header = header
        counter = 1
        while header in self.sequences:
            header = f"{base_header}_{counter}"
            counter += 1
        self.sequences[header] = seq
        if metadata: self.pdb_metadata[header] = metadata

        item = QListWidgetItem(header)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
        item.setCheckState(Qt.Checked)
        self.list_seqs.addItem(item)
        self.text_preview.setText(f"📥 成功载入序列: {header}\n序列长度: {len(seq)} bp/aa\n\n可继续拖拽导入，或勾选后执行比对。")

    def remove_selected_item(self):
        current_row = self.list_seqs.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先点击选中（文字背景变蓝）一条要移除的序列。")
            return
        item = self.list_seqs.takeItem(current_row)
        header = item.text()
        if header in self.sequences: del self.sequences[header]
        if header in self.aligned_sequences: del self.aligned_sequences[header]
        if header in self.pdb_metadata: del self.pdb_metadata[header]
        self.text_preview.clear()
        self.lbl_legend.hide()

    def clear_data(self):
        self.sequences.clear(); self.aligned_sequences.clear(); self.pdb_metadata.clear()
        self.list_seqs.clear(); self.text_preview.clear(); self.lbl_legend.hide()

    # ------------------------------------
    # 核心算法：NW 比对 (算法纯净，零干预)
    # ------------------------------------
    def needleman_wunsch(self, seq1, seq2, match=2, mismatch=-1, gap=-2):
        n, m = len(seq1), len(seq2)
        score_matrix = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(n + 1): score_matrix[i][0] = gap * i
        for j in range(m + 1): score_matrix[0][j] = gap * j
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                diag = score_matrix[i - 1][j - 1] + (match if seq1[i - 1] == seq2[j - 1] else mismatch)
                delete = score_matrix[i - 1][j] + gap
                insert = score_matrix[i][j - 1] + gap
                score_matrix[i][j] = max(diag, delete, insert)
        align1, align2 = "", ""
        i, j = n, m
        while i > 0 or j > 0:
            if i > 0 and j > 0 and score_matrix[i][j] == score_matrix[i - 1][j - 1] + (match if seq1[i - 1] == seq2[j - 1] else mismatch):
                align1 = seq1[i - 1] + align1; align2 = seq2[j - 1] + align2
                i -= 1; j -= 1
            elif i > 0 and score_matrix[i][j] == score_matrix[i - 1][j] + gap:
                align1 = seq1[i - 1] + align1; align2 = "-" + align2; i -= 1
            else:
                align1 = "-" + align1; align2 = seq2[j - 1] + align2; j -= 1
        return align1, align2

    def run_alignment(self):
        if self.is_setting_mode: return
        self._save_config()

        selected_headers = [self.list_seqs.item(i).text() for i in range(self.list_seqs.count()) if self.list_seqs.item(i).checkState() == Qt.Checked]
        if not selected_headers:
            self.text_preview.setText("请至少勾选 1 条序列进行操作。")
            return

        ref_header = selected_headers[0]
        ref_seq = self.sequences[ref_header]
        if len(selected_headers) == 1:
            self.aligned_sequences = {ref_header: ref_seq}
            self.display_alignment()
            return

        self.text_preview.setText("正在通过 Needleman-Wunsch 引擎进行专业联配......\n请稍候。")
        QApplication.processEvents()

        self.aligned_sequences = {ref_header: ref_seq}
        for target_header in selected_headers[1:]:
            target_seq = self.sequences[target_header]
            current_ref = self.aligned_sequences[ref_header]
            raw_ref = current_ref.replace("-", "")

            aligned_ref, aligned_target = self.needleman_wunsch(raw_ref, target_seq)
            new_msa = {k: "" for k in self.aligned_sequences.keys()}
            new_msa[target_header] = ""

            ptr_msa = 0
            for i in range(len(aligned_ref)):
                if aligned_ref[i] == "-":
                    for k in self.aligned_sequences.keys(): new_msa[k] += "-"
                    new_msa[target_header] += aligned_target[i]
                else:
                    while ptr_msa < len(current_ref) and current_ref[ptr_msa] == "-":
                        for k in self.aligned_sequences.keys(): new_msa[k] += self.aligned_sequences[k][ptr_msa]
                        new_msa[target_header] += "-"
                        ptr_msa += 1
                    for k in self.aligned_sequences.keys(): new_msa[k] += self.aligned_sequences[k][ptr_msa]
                    new_msa[target_header] += aligned_target[i]
                    ptr_msa += 1

            while ptr_msa < len(current_ref):
                for k in self.aligned_sequences.keys(): new_msa[k] += self.aligned_sequences[k][ptr_msa]
                new_msa[target_header] += "-"
                ptr_msa += 1
            self.aligned_sequences = new_msa

        self.display_alignment()

    # ------------------------------------
    # 配置管理
    # ------------------------------------
    def _load_config(self):
        config = GlobalConfig.get_all_plugin_settings(self.plugin_id)
        if config: self.apply_config_dict(config)

    def _save_config(self):
        config = self.get_config_dict()
        GlobalConfig.set_all_plugin_settings(self.plugin_id, config)

    def get_config_dict(self):
        return {
            "chk_reference": self.chk_reference.isChecked(),
            "combo_style": self.combo_style.currentText()
        }

    def apply_config_dict(self, data):
        self.chk_reference.setChecked(data.get("chk_reference", True))
        self.combo_style.setCurrentText(data.get("combo_style", "ProDesigner (突变高亮)"))

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存序列配置", "seq_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入序列配置", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f: self.apply_config_dict(json.load(f))
            if not self.is_setting_mode: self.display_alignment()

    def save_settings_and_close(self):
        self._save_config()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog): parent_dlg.accept()

    # ------------------------------------
    # HTML 富文本渲染引擎 (支持多种顶级着色方案)
    # ------------------------------------
    def update_legend(self):
        self.lbl_legend.show()
        style = self.combo_style.currentText()
        is_ref_mode = self.chk_reference.isChecked()

        if not is_ref_mode and style not in ["Jalview (全局属性色块)"]:
            self.lbl_legend.setText("<b>图例 (无基准):</b> 序列处于纯文本平行对比状态。生化属性将按自身着色。")
            return

        if style == "ProDesigner (突变高亮)":
            self.lbl_legend.setText("<b>图例:</b> <span style='color:#AAAAAA'>灰色: 与基准一致</span> | <span style='color:#D32F2F; background-color:#FFEBEE;'>浅红底红字: 发生突变</span>")
        elif style == "独立方格标记 (自用格式)":
            self.lbl_legend.setText("<b>图例:</b> 标尺每 10 位显示数字，每 5 位显示点(·)。<span style='color:#D32F2F; background-color:#FFEBEE;'>红框红字: 发生突变</span>")
        elif style == "打点模式 (Dot Match)":
            self.lbl_legend.setText("<b>图例:</b> <span style='color:#AAAAAA'>打点(.): 与基准一致</span> | <span style='color:#D32F2F; font-weight:bold;'>红色: 发生突变</span>")
        elif style == "ESPript (红底白字高保守)":
            self.lbl_legend.setText("<b>图例 (ESPript):</b> <span style='color:white; background-color:#D32F2F; padding:2px;'>红底白字: 100%完全保守列</span> | <span style='color:#D32F2F; border:1px solid #2196F3; padding:1px;'>蓝框红字: 发生突变</span>")
        elif style == "Jalview (全局属性色块)":
            self.lbl_legend.setText("<b>图例 (Jalview):</b> 依据氨基酸生化属性赋予全局背景色（马赛克瓷砖样式）。")
        else:
            self.lbl_legend.setText("<b>图例 (Clustal):</b> <span style='color:#E60A0A'>红:疏水</span> | <span style='color:#145AFF'>蓝:酸性</span> | <span style='color:#A0A000'>黄:碱性</span> | <span style='color:#14CC14'>绿:极性</span><br><i>* 突变位点显示为高亮反色底色。</i>")

    def get_clustal_color(self, aa):
        aa = aa.upper()
        if aa in ['A', 'V', 'F', 'P', 'M', 'I', 'L', 'W']: return "#E60A0A"
        if aa in ['D', 'E']: return "#145AFF"
        if aa in ['R', 'K']: return "#A0A000"
        if aa in ['S', 'T', 'Y', 'H', 'C', 'N', 'G', 'Q']: return "#14CC14"
        return "#666666"

    def display_alignment(self):
        if not self.aligned_sequences or self.is_setting_mode: return

        self.update_legend()
        style_mode = self.combo_style.currentText()
        is_ref_mode = self.chk_reference.isChecked()

        headers = list(self.aligned_sequences.keys())
        ref_header = headers[0]
        ref_seq = self.aligned_sequences[ref_header]
        align_length = len(ref_seq)
        
        # 🌟 核心修复：彻底解除 15 个字符的强行截断限制，动态计算最长序列名
        max_name_len = max([len(h) for h in headers])

        is_espript = (style_mode == "ESPript (红底白字高保守)")
        is_jalview = (style_mode == "Jalview (全局属性色块)")
        conservation = []
        if is_espript:
            for i in range(align_length):
                chars = [self.aligned_sequences[h][i] for h in headers]
                if all(c == chars[0] and c != '-' for c in chars): conservation.append(True)
                else: conservation.append(False)

        ref_meta = self.pdb_metadata.get(ref_header)
        ref_num_map = []
        real_idx = 0
        for char in ref_seq:
            if char != '-':
                if ref_meta and real_idx < len(ref_meta): ref_num_map.append(ref_meta[real_idx])
                else: ref_num_map.append(real_idx + 1)
                real_idx += 1
            else: ref_num_map.append("")

        html_output = "<div style='font-family: Consolas, monospace; font-size: 13px; line-height: 1.5;'>"
        chunk_size = 40 if style_mode == "独立方格标记 (自用格式)" else 60

        for i in range(0, align_length, chunk_size):
            chunk_end = min(i + chunk_size, align_length)
            chunk_len = chunk_end - i
            ref_chunk = ref_seq[i:chunk_end]

            if style_mode == "独立方格标记 (自用格式)":
                html_output += "<table cellspacing='0' cellpadding='0' style='border-collapse: collapse; margin-bottom: 25px;'>"
                html_output += "<tr><td style='border:none; width: 10px;'></td>"
                for j in range(chunk_len):
                    num = ref_num_map[i + j]
                    if num == "": marker = ""
                    elif isinstance(num, int): marker = str(num) if num % 10 == 0 else ("·" if num % 5 == 0 else "")
                    else: marker = ""
                    html_output += f"<td width='24' height='16' style='border:none; text-align:center; vertical-align:bottom; font-size:10px; color:#555;'>{marker}</td>"
                html_output += "</tr><tr>"

                # 🌟 核心修复：使用动态长度替换固定的 15 字符截断
                disp_ref_name = ref_header.rjust(max_name_len).replace(" ", "&nbsp;")
                html_output += f"<td style='border:none; text-align:right; padding-right:10px; color:#0078D7; white-space:nowrap;'><b>{disp_ref_name}</b></td>"

                for char in ref_chunk:
                    bg_color = "#E3F2FD" if char != "-" else "#FFFFFF"
                    html_output += f"<td width='24' height='24' style='border:1px solid #999; text-align:center; vertical-align:middle; background-color:{bg_color}; font-weight:bold; color:#0078D7;'>{char}</td>"
                html_output += "</tr>"

                for row_idx, h in enumerate(headers[1:]):
                    seq_chunk = self.aligned_sequences[h][i:chunk_end]
                    disp_name = h.rjust(max_name_len).replace(" ", "&nbsp;")
                    html_output += f"<tr><td style='border:none; text-align:right; padding-right:10px; white-space:nowrap;'>{disp_name}</td>"

                    for aa_idx, aa_target in enumerate(seq_chunk):
                        aa_ref = ref_chunk[aa_idx]
                        if aa_target == '-': html_output += f"<td width='24' height='24' style='border:1px solid #CCC; text-align:center; vertical-align:middle; color:#AAAAAA;'>-</td>"
                        else:
                            if not is_ref_mode or aa_ref == aa_target: html_output += f"<td width='24' height='24' style='border:1px solid #CCC; text-align:center; vertical-align:middle; color:#555555;'>{aa_target}</td>"
                            else: html_output += f"<td width='24' height='24' style='border:2px solid #D32F2F; text-align:center; vertical-align:middle; background-color:#FFEBEE; color:#D32F2F; font-weight:bold;'>{aa_target}</td>"
                    html_output += "</tr>"
                html_output += "</table>"
            else:
                html_output += "<pre style='margin: 0; font-family: Consolas, monospace; font-size: 13px; line-height: 1.5;'>"
                ruler_chars = [' '] * chunk_len
                for j in range(chunk_len):
                    num = ref_num_map[i + j]
                    if isinstance(num, int) and num % 10 == 0:
                        num_str = str(num)
                        start_idx = j - len(num_str) + 1
                        for k, digit in enumerate(num_str):
                            pos = start_idx + k
                            if 0 <= pos < chunk_len: ruler_chars[pos] = digit

                ruler_aligned = "".join(ruler_chars)
                padding_spaces = " " * (max_name_len + 2)
                html_output += f"<span style='color:#999999;'>{padding_spaces}{ruler_aligned}</span>\n"

                disp_ref_name = ref_header.ljust(max_name_len)
                if is_ref_mode: html_output += f"<b><span style='color:#0078D7;'>{disp_ref_name}  {ref_chunk}</span></b>\n"
                else: html_output += f"{disp_ref_name}  {ref_chunk}\n"

                for row_idx, h in enumerate(headers[1:]):
                    seq_chunk = self.aligned_sequences[h][i:chunk_end]
                    disp_name = h.ljust(max_name_len)
                    formatted_seq = ""

                    for aa_idx, aa_target in enumerate(seq_chunk):
                        global_col_idx = i + aa_idx
                        if aa_target == '-': formatted_seq += "<span style='color:#AAAAAA;'>-</span>"; continue
                        
                        if is_jalview:
                            color = self.get_clustal_color(aa_target)
                            formatted_seq += f"<span style='color:white; background-color:{color}; border-radius:1px;'>{aa_target}</span>"
                        elif is_espript:
                            aa_ref = ref_chunk[aa_idx]
                            if conservation[global_col_idx]: formatted_seq += f"<span style='color:white; background-color:#D32F2F; font-weight:bold;'>{aa_target}</span>"
                            elif is_ref_mode and aa_target != aa_ref: formatted_seq += f"<span style='color:#D32F2F; border:1px solid #2196F3;'>{aa_target}</span>"
                            else: formatted_seq += f"<span style='color:#333333;'>{aa_target}</span>"
                        elif not is_ref_mode:
                            if style_mode == "生化属性着色 (Clustal Style)":
                                color = self.get_clustal_color(aa_target)
                                formatted_seq += f"<span style='color:{color};'>{aa_target}</span>"
                            else: formatted_seq += f"<span style='color:#333333;'>{aa_target}</span>"
                        else:
                            aa_ref = ref_chunk[aa_idx]
                            if style_mode == "打点模式 (Dot Match)":
                                if aa_ref == aa_target: formatted_seq += "<span style='color:#AAAAAA;'>.</span>"
                                else: formatted_seq += f"<span style='color:#D32F2F; font-weight:bold;'>{aa_target}</span>"
                            elif style_mode == "生化属性着色 (Clustal Style)":
                                color = self.get_clustal_color(aa_target)
                                if aa_ref == aa_target: formatted_seq += f"<span style='color:{color};'>{aa_target}</span>"
                                else: formatted_seq += f"<span style='color:#FFFFFF; background-color:{color}; font-weight:bold; border-radius:2px;'>{aa_target}</span>"
                            else:
                                if aa_ref == aa_target: formatted_seq += f"<span style='color:#AAAAAA;'>{aa_target}</span>"
                                else: formatted_seq += f"<span style='color:#D32F2F; font-weight:bold; background-color:#FFEBEE;'>{aa_target}</span>"

                    html_output += f"{disp_name}  {formatted_seq}\n"
                html_output += "\n</pre>"
        html_output += "</div>"
        self.text_preview.setHtml(html_output)

    # ------------------------------------
    # 文件导出功能 (图表生成完全保持原生)
    # ------------------------------------
    def export_aln(self):
        if len(self.aligned_sequences) < 2: return
        file_path, _ = QFileDialog.getSaveFileName(self, "保存为 Clustal ALN", "alignment.aln", "ALN Files (*.aln)")
        if not file_path: return
        try:
            with open(file_path, 'w') as f:
                f.write("CLUSTAL W (ProDesigner) multiple sequence alignment\n\n")
                headers = list(self.aligned_sequences.keys())
                seq_len = len(self.aligned_sequences[headers[0]])
                max_name_len = max([len(h) for h in headers])
                for i in range(0, seq_len, 60):
                    for h in headers:
                        f.write(f"{h.ljust(max_name_len + 5)}{self.aligned_sequences[h][i:i + 60]}\n")
                    f.write("\n")
            QMessageBox.information(self, "成功", f"ALN 保存至:\n{file_path}")
        except Exception as e: QMessageBox.critical(self, "错误", str(e))

    def export_pdf(self):
        if not self.text_preview.toPlainText().strip():
            QMessageBox.warning(self, "提示", "当前没有可以导出的内容。")
            return
            
        # 智能升级：同时提供“动态 PDF”和“交互式 HTML”两种顶级格式
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, 
            "智能导出序列比对报告", 
            "Sequence_Alignment_Report.pdf", 
            "自适应无截断 PDF (*.pdf);;交互式网页报告 (*.html)"
        )
        if not file_path: return

        try:
            # ==========================================
            # 方案 A: 交互式网页报告 (生信排版最强推荐)
            # 现代浏览器具有世界上最完美的文字排版和打印引擎
            # ==========================================
            if file_path.endswith('.html'):
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>SciForge 序列比对报告</title>
                    <style>
                        body {{ background-color: #F9F9F9; padding: 30px; font-family: sans-serif; }}
                        .container {{ 
                            background-color: #FFFFFF; border: 1px solid #EAEAEA; 
                            border-radius: 8px; padding: 20px; 
                            box-shadow: 0 4px 10px rgba(0,0,0,0.05); 
                            display: inline-block; min-width: 100%; box-sizing: border-box; 
                        }}
                    </style>
                </head>
                <body>
                    <h2 style="color: #0078D7;">🧬 SciForge 多序列比对报告</h2>
                    <div class="container">
                        {self.text_preview.toHtml()}
                    </div>
                </body>
                </html>
                """
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                QMessageBox.information(self, "导出成功", f"交互式网页报告已生成！\n\n💡 推荐使用 Edge 或 Chrome 浏览器打开。您可以自由框选复制序列，或者按 Ctrl+P 利用浏览器的完美排版引擎将其打印为普通 PDF。\n\n保存路径:\n{file_path}")
                return

            # ==========================================
            # 方案 B: 动态无边框卷轴 PDF (彻底解决截断)
            # 核心黑魔法：取消标准纸张限制，让纸张大小动态适应内容！
            # ==========================================
            from PyQt5.QtCore import QSizeF
            from PyQt5.QtGui import QPageSize
            from PyQt5.QtPrintSupport import QPrinter

            # 使用 ScreenResolution 保证所见即所得，不会导致排版异变
            printer = QPrinter(QPrinter.ScreenResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_path)

            # 克隆文档进行后台计算
            doc = self.text_preview.document().clone()
            
            # 智能侦测 1：解除文档的换行限制，让其完全展开到底
            doc.setTextWidth(-1) 
            
            # 智能侦测 2：获取内容的真实最大物理像素长宽
            ideal_width = doc.idealWidth()
            ideal_height = doc.size().height()

            # 智能重塑：动态生成一张完全贴合内容的“自定义无限纸张”，加上少许白边留白
            page_size = QPageSize(QSizeF(ideal_width + 60, ideal_height + 60), QPageSize.Point)
            printer.setPageSize(page_size)
            printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)

            # 完美打印，绝对不会出现任何裁剪！
            doc.print_(printer)
            QMessageBox.information(self, "导出成功", f"自适应无截断 PDF 已保存至:\n{file_path}\n\n(系统已根据序列长度自动生成了最适配的画布尺寸)")

        except Exception as e: 
            QMessageBox.critical(self, "导出失败", f"报告生成引擎发生错误:\n{str(e)}")

    def export_publication_plot(self):
        if not self.aligned_sequences:
            QMessageBox.warning(self, "提示", "请先执行多序列比对！")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出出版级矩阵图", "msa_publication.pdf", "PDF Files (*.pdf);;PNG Images (*.png);;SVG Vector (*.svg)")
        if not file_path: return
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            from matplotlib.colors import ListedColormap
            from collections import Counter

            headers = list(self.aligned_sequences.keys())
            seqs = [self.aligned_sequences[h] for h in headers]
            n_seqs = len(seqs); seq_len = len(seqs[0])

            aa_colors = {
                'A': '#E60A0A', 'V': '#E60A0A', 'F': '#E60A0A', 'P': '#E60A0A', 'M': '#E60A0A', 'I': '#E60A0A', 'L': '#E60A0A', 'W': '#E60A0A',
                'D': '#145AFF', 'E': '#145AFF', 'R': '#A0A000', 'K': '#A0A000',
                'S': '#14CC14', 'T': '#14CC14', 'Y': '#14CC14', 'H': '#14CC14', 'C': '#14CC14', 'N': '#14CC14', 'G': '#14CC14', 'Q': '#14CC14',
                '-': '#FFFFFF', 'X': '#AAAAAA'
            }
            # 在某些深色背景上方需要使用白色字体以保证可读性
            dark_colors = ['#E60A0A', '#145AFF'] 

            unique_aas = list(aa_colors.keys())
            aa_to_idx = {aa: i for i, aa in enumerate(unique_aas)}
            cmap = ListedColormap([aa_colors[aa] for aa in unique_aas])

            matrix = np.zeros((n_seqs, seq_len))
            for i, seq in enumerate(seqs):
                for j, aa in enumerate(seq): matrix[i, j] = aa_to_idx.get(aa.upper(), aa_to_idx['-'])

            conservation = []
            for j in range(seq_len):
                col_chars = [s[j] for s in seqs if s[j] != '-']
                if not col_chars: conservation.append(0)
                else:
                    most_common_freq = Counter(col_chars).most_common(1)[0][1]
                    conservation.append(most_common_freq / n_seqs)

            # 动态计算出版级别的画板长宽，避免挤压
            fig_width = max(12, seq_len * 0.2)
            fig_height = max(4, n_seqs * 0.4 + 2)
            fig, (ax_bar, ax_mat) = plt.subplots(2, 1, figsize=(fig_width, fig_height), gridspec_kw={'height_ratios': [1, 4]})

            # 绘制顶部保守度直方图
            ax_bar.bar(range(seq_len), conservation, color='#34495e', width=1.0)
            ax_bar.set_xlim(-0.5, seq_len - 0.5); ax_bar.set_ylim(0, 1.05)
            ax_bar.axis('off')
            ax_bar.set_title("Conservation Score", loc='left', fontsize=14, fontweight='bold', color='#333')

            # 绘制主比对色块矩阵
            ax_mat.imshow(matrix, cmap=cmap, aspect='auto', interpolation='nearest')
            
            # 🌟 核心修复：解除序列名称截断限制，完整保留
            ax_mat.set_yticks(range(n_seqs))
            ax_mat.set_yticklabels(headers, fontsize=12, family='monospace', fontweight='bold')
            ax_mat.set_xticks(range(0, seq_len, max(1, seq_len // 20)))
            ax_mat.set_xticklabels(range(1, seq_len + 1, max(1, seq_len // 20)), fontsize=10)
            
            # 🌟 出版级格式重构：如果序列不是非常庞大（<200bp），直接把字母打在色块上（顶级期刊标配表现形式）
            if seq_len <= 200:
                for i in range(n_seqs):
                    for j in range(seq_len):
                        aa = seqs[i][j].upper()
                        if aa != '-':
                            txt_color = 'white' if aa_colors.get(aa, '#FFF') in dark_colors else 'black'
                            ax_mat.text(j, i, aa, ha='center', va='center', color=txt_color, fontsize=10, family='monospace', fontweight='bold')
            
            for spine in ax_mat.spines.values(): spine.set_visible(False)
            ax_mat.tick_params(axis='both', which='both', length=0)

            plt.tight_layout()
            plt.savefig(file_path, dpi=300, bbox_inches='tight', transparent=False)
            plt.close()
            QMessageBox.information(self, "导出成功", f"出版级高清图像已保存至:\n{file_path}\n(提示: 因长度适中，图中已自动内嵌氨基酸字母)")

        except ImportError: QMessageBox.critical(self, "缺少依赖", "生成出版级绘图需要安装 matplotlib 和 numpy。")
        except Exception as e: QMessageBox.critical(self, "绘图失败", f"绘图引擎发生错误:\n{str(e)}")


# ==========================================
# 后端：插件描述器
# ==========================================
class SequencePlugin(BasePlugin):
    plugin_id = "seq_analyzer"
    plugin_name = "多序列比对与分析"
    icon = "🧬"
    trigger_tag = "序列分析"

    def get_ui(self, parent=None): return SequenceUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout
        card = PrimaryPushSettingCard("配置全局默认参数", FIF.EDIT, "🧬 多序列比对与分析", "修改工作站中序列比对的默认参考模式与渲染着色风格", parent)

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("序列比对全局预设中心")
            dlg.resize(460, 200)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }") # 【优化】锁死亮色弹窗
            layout = QVBoxLayout(dlg)
            settings_ui = SequenceUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()
        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        """后台自动处理 (维持纯净)"""
        try:
            seqs = {}
            ext = os.path.splitext(file_path)[1].lower()

            if ext in ['.fasta', '.seq', '.txt']:
                with open(file_path, 'r', encoding='utf-8') as f: content = f.read().strip()
                if content.startswith('>'):
                    for block in content.split('>')[1:]:
                        lines = block.split('\n'); name = lines[0].strip()
                        seqs[name] = ''.join(lines[1:]).replace(' ', '').replace('\r', '')
                else: seqs['Sequence_1'] = content.replace('\n', '').replace(' ', '')

            elif ext == '.dna':
                try:
                    import snapgene_reader
                    dna = snapgene_reader.snapgene_file_to_dict(file_path)
                    seqs[os.path.basename(file_path)] = dna.get('seq', '').upper()
                except ImportError: return "", "【序列分析跳过】未能解析 .dna 文件，请检查是否安装了 snapgene_reader。"

            if not seqs: return "", "【序列分析跳过】文件中未提取到有效序列内容。"

            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt

            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False

            fig = Figure(figsize=(7, 4.5), dpi=150)
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)

            analysis_texts = []

            if len(seqs) == 1:
                name, seq = list(seqs.items())[0]
                seq = seq.upper()
                is_dna = set(seq).issubset(set('ATCGNU-')) and len(seq) > 10

                if is_dna:
                    counts = {'A': seq.count('A'), 'T': seq.count('T'), 'C': seq.count('C'), 'G': seq.count('G')}
                    other_cnt = len(seq) - sum(counts.values())
                    if other_cnt > 0: counts['Other (N/U/-)'] = other_cnt
                    counts = {k: v for k, v in counts.items() if v > 0}

                    ax.pie(counts.values(), labels=counts.keys(), autopct='%1.1f%%', colors=['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#c2c2f0'], startangle=140)
                    ax.set_title(f"DNA Composition: {name[:25]}...", fontweight='bold')

                    gc = (counts.get('C', 0) + counts.get('G', 0)) / len(seq) * 100 if len(seq) > 0 else 0
                    analysis_texts.append(f"📌 **{name}** (核酸) <br>总长度: {len(seq)} bp <br>GC含量: {gc:.2f}%")
                else:
                    hydrophobic = sum(seq.count(c) for c in 'AILMFVPGW')
                    polar = sum(seq.count(c) for c in 'STCYNQ')
                    charged = sum(seq.count(c) for c in 'DEKRH')
                    other = len(seq) - hydrophobic - polar - charged
                    counts = {'Hydrophobic': hydrophobic, 'Polar (Uncharged)': polar, 'Charged': charged, 'Other/Unknown': other}
                    counts = {k: v for k, v in counts.items() if v > 0}

                    ax.pie(counts.values(), labels=counts.keys(), autopct='%1.1f%%', colors=['#fbc531', '#4cd137', '#e84118', '#7f8fa6'], startangle=140)
                    ax.set_title(f"Amino Acid Propensity: {name[:25]}...", fontweight='bold')
                    analysis_texts.append(f"📌 **{name}** (蛋白质) <br>总长度: {len(seq)} aa")

            else:
                display_names = [n[:15] + "..." if len(n) > 15 else n for n in list(seqs.keys())[:12]]
                lengths = [len(seq) for seq in list(seqs.values())[:12]]

                ax.barh(display_names, lengths, color='#3498db', edgecolor='#2980b9')
                ax.set_xlabel("Sequence Length", fontweight='bold')
                ax.set_title(f"Sequence Length Distribution (Total: {len(seqs)} seqs)", fontweight='bold')

                for i, v in enumerate(lengths): ax.text(v, i, f" {v}", va='center', fontsize=9, color='#333333')

                ax.invert_yaxis()
                ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)

                analysis_texts.append(f"共提取到 **{len(seqs)}** 条序列。")
                for k, v in list(seqs.items())[:5]: analysis_texts.append(f"- {k[:30]}: {len(v)} 字符")
                if len(seqs) > 5: analysis_texts.append(f"... (其余省略)")

            fig.tight_layout()
            out_name = f"plot_SEQ_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150, transparent=True)
            fig.clf()

            res_text = "🧬 **【序列特征快速分析完成】**<br>" + "<br>".join(analysis_texts)
            return out_path, res_text

        except Exception as e:
            return "", f"序列分析引擎执行失败: {str(e)}"