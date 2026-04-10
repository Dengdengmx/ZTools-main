# plugins/plugin_sequence.py
import os
import sys
import argparse
import json
import time
from collections import Counter

try:
    import snapgene_reader
    SNAPGENE_AVAILABLE = True
except ImportError:
    SNAPGENE_AVAILABLE = False

PLUGIN_NAME = "多序列比对与分析引擎 (全功能典藏版)"
PLUGIN_ICON = "🧬"
PLUGIN_DESC = "样式与导出格式完美解耦！所有比对样式均已全量支持 PDF(矢量打印)、PNG(快速预览) 与 HTML(鼠标悬停互动 Web 页) 的自由选择与全打包输出！"

AA_MAP = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
    'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
    'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
    'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
}

# ==========================================
# 前端表单 UI Schema 描述 (最高自由度自定义)
# ==========================================
UI_SCHEMA = [
    {"key": "file_path", "label": "📁 导入序列文件 (FASTA/DNA/PDB，支持以逗号分隔多选)", "type": "file", "span": 12},
    
    {"key": "chk_reference", "label": "首行为 Reference (开启突变侦测)", "type": "boolean", "default": True, "span": 12},
    
    # 🌟 核心优化 1：样式与格式完美解耦
    {"key": "combo_style", "label": "绘图渲染预设", "type": "select", "options": [
        "方格阵列模式 (独立成格)",
        "双序列精准比对 (带双重坐标轴)",
        "ESPript (红底白字高保守·智能折行)",
        "ProDesigner (矩阵图·突变高亮)",
        "生化属性着色 (矩阵图·Clustal Style)"
    ], "default": "方格阵列模式 (独立成格)", "span": 6},
    
    {"key": "out_format", "label": "导出文件格式", "type": "select", "options": [
        "PDF (原生高清矢量，推荐)",
        "PNG (静态图片)",
        "HTML (交互式Web页)",
        "全部格式打包 (PDF+PNG+HTML)"
    ], "default": "PDF (原生高清矢量，推荐)", "span": 6},
    
    # 高级渲染排版自定义项
    {"key": "chunk_size", "label": "每行显示字符数", "type": "select", "options": ["40", "60", "80", "100", "120"], "default": "60", "span": 3},
    {"key": "match_symbol", "label": "匹配符 (双序列)", "type": "string", "default": "|", "span": 3},
    {"key": "mismatch_symbol", "label": "不匹配符", "type": "string", "default": ".", "span": 3},
    {"key": "espript_thresh", "label": "ESPript 强保守阈值", "type": "number", "default": 0.7, "span": 3},

    {"key": "match_score", "label": "NW: Match Score", "type": "number", "default": 2, "span": 4},
    {"key": "mismatch_score", "label": "NW: Mismatch", "type": "number", "default": -1, "span": 4},
    {"key": "gap_score", "label": "NW: Gap Penalty", "type": "number", "default": -2, "span": 4},
]

UI_LAYOUT = {
    "direction": "row",
    "blocks": [
        {"type": "form", "width": "420px", "height": "100%"},
        {"type": "tabs", "flex": "1", "height": "100%", "panes": [
            {"title": "👁️ 图像与Web预览区", "type": "preview"},
            {"title": "💻 ALN 文本对齐", "type": "code"},
            {"title": "📊 序列核心指标", "type": "metrics"},
            {"title": "🎯 终端日志流", "type": "terminal"}
        ]}
    ],
    "footer_actions": [
        {"id": "analyze", "label": "🧬 1. 序列特征分析", "type": "default"},
        {"id": "align_text", "label": "📝 2. 导出对齐文本", "type": "default"},
        {"id": "plot_pub", "label": "📊 3. 渲染可视化比对", "type": "primary"}
    ]
}

def get_sync_workspace():
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../sciforge_config.json"))
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("data_hub_path"): return cfg.get("data_hub_path")
        except: pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../SciForge_Workspace/SciForge_Data"))

# =====================================================================
# 逐字保留的原生数据摄取逻辑
# =====================================================================
def parse_pdb_sequence(file_path, base_header):
    seqs = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith("ATOM  ") and line[12:16].strip() == "CA":
                res_name = line[17:20].strip()
                chain_id = line[21].strip() or "A"
                if chain_id not in seqs: seqs[chain_id] = []
                seqs[chain_id].append(AA_MAP.get(res_name, 'X'))
    res = {}
    for chain, seq_list in seqs.items():
        header = f"{base_header}_Chain_{chain}"
        res[header] = "".join(seq_list)
    return res

def load_sequences(file_paths):
    sequences = {}
    for file_path in file_paths:
        if not os.path.exists(file_path): continue
        ext = os.path.splitext(file_path)[1].lower()
        current_header = os.path.basename(file_path)

        if ext == '.dna':
            if not SNAPGENE_AVAILABLE:
                print(f"⚠️ 跳过 .dna 文件 {current_header}，未安装 snapgene_reader。")
                continue
            try:
                seq_dict = snapgene_reader.snapgene_file_to_dict(file_path)
                base_header = current_header
                counter = 1
                while current_header in sequences:
                    current_header = f"{base_header}_{counter}"
                    counter += 1
                sequences[current_header] = seq_dict['seq'].upper()
            except Exception as e: print(f"⚠️ 解析失败: {e}")

        elif ext in ['.pdb', '.cif']:
            try:
                pdb_seqs = parse_pdb_sequence(file_path, current_header)
                for k, v in pdb_seqs.items():
                    temp_k = k
                    counter = 1
                    while temp_k in sequences:
                        temp_k = f"{k}_{counter}"
                        counter += 1
                    sequences[temp_k] = v
            except Exception as e: print(f"⚠️ PDB 解析失败: {e}")

        else:
            current_seq = []
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        if line.startswith(">"):
                            if current_seq:
                                temp_h = current_header
                                counter = 1
                                while temp_h in sequences:
                                    temp_h = f"{current_header}_{counter}"
                                    counter += 1
                                sequences[temp_h] = "".join(current_seq)
                                current_seq = []
                            current_header = line[1:]
                        else:
                            current_seq.append("".join(filter(str.isalpha, line)).upper())
                    if current_seq:
                        temp_h = current_header
                        counter = 1
                        while temp_h in sequences:
                            temp_h = f"{current_header}_{counter}"
                            counter += 1
                        sequences[temp_h] = "".join(current_seq)
            except Exception as e: print(f"⚠️ FASTA 解析失败: {e}")
    return sequences

# =====================================================================
# 逐字保留的 NW 比对核心算法
# =====================================================================
def needleman_wunsch(seq1, seq2, match=2, mismatch=-1, gap=-2):
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

def get_index_mapping(seq):
    """提取序列在排除 Gap 后的真实生物学氨基酸/核酸位置索引"""
    mapping = []
    idx = 1
    for char in seq:
        if char != '-':
            mapping.append(idx)
            idx += 1
        else:
            mapping.append(None)
    return mapping


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', type=str, default='analyze')
    for item in UI_SCHEMA:
        if item["type"] == "boolean": parser.add_argument(f"--{item['key']}", action="store_true")
        elif item["type"] == "number": parser.add_argument(f"--{item['key']}", type=float, default=item.get("default", 0.0))
        else: parser.add_argument(f"--{item['key']}", type=str, default=str(item.get("default", "")))
            
    args = parser.parse_args()
    
    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)

    f_path_str = str(getattr(args, 'file_path', '')).strip()
    if not f_path_str:
        print("❌ [Error] 请先在左侧拖入或选择需要比对的序列/PDB文件！")
        sys.exit(1)

    file_paths = [os.path.join(workspace, p.strip()) for p in f_path_str.split(',') if p.strip()]
    
    print(">>> 正在拉取并解析底层格式...")
    sequences = load_sequences(file_paths)
    if not sequences:
        print("❌ [Error] 未能从文件中提取到有效序列内容！")
        sys.exit(1)

    headers = list(sequences.keys())
    ref_header = headers[0]
    print(f"👉 成功解析 {len(sequences)} 条序列。")

    # =====================================================================
    # 行动 1：序列特征分析 (完全复刻原版 run 方法)
    # =====================================================================
    if args.action == 'analyze':
        try:
            import matplotlib.pyplot as plt
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
            plt.rcParams['axes.unicode_minus'] = False

            fig = plt.figure(figsize=(7, 4.5), dpi=150)
            ax = fig.add_subplot(111)

            metrics_out = {}

            if len(sequences) == 1:
                name, seq = list(sequences.items())[0]
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
                    
                    metrics_out["序列类型"] = "核酸 (DNA/RNA)"
                    metrics_out["总长度"] = f"{len(seq)} bp"
                    metrics_out["GC 含量"] = f"{gc:.2f}%"
                    print("✅ DNA 成分饼图渲染完成！")
                else:
                    hydrophobic = sum(seq.count(c) for c in 'AILMFVPGW')
                    polar = sum(seq.count(c) for c in 'STCYNQ')
                    charged = sum(seq.count(c) for c in 'DEKRH')
                    other = len(seq) - hydrophobic - polar - charged
                    counts = {'Hydrophobic': hydrophobic, 'Polar (Uncharged)': polar, 'Charged': charged, 'Other/Unknown': other}
                    counts = {k: v for k, v in counts.items() if v > 0}

                    ax.pie(counts.values(), labels=counts.keys(), autopct='%1.1f%%', colors=['#fbc531', '#4cd137', '#e84118', '#7f8fa6'], startangle=140)
                    ax.set_title(f"Amino Acid Propensity: {name[:25]}...", fontweight='bold')
                    
                    metrics_out["序列类型"] = "蛋白质 (Protein)"
                    metrics_out["总长度"] = f"{len(seq)} aa"
                    metrics_out["疏水残基"] = f"{hydrophobic} aa"
                    print("✅ 氨基酸属性饼图渲染完成！")
            else:
                display_names = [n[:15] + "..." if len(n) > 15 else n for n in list(sequences.keys())[:12]]
                lengths = [len(seq) for seq in list(sequences.values())[:12]]

                ax.barh(display_names, lengths, color='#3498db', edgecolor='#2980b9')
                ax.set_xlabel("Sequence Length", fontweight='bold')
                ax.set_title(f"Sequence Length Distribution (Total: {len(sequences)} seqs)", fontweight='bold')

                for i, v in enumerate(lengths): ax.text(v, i, f" {v}", va='center', fontsize=9, color='#333333')

                ax.invert_yaxis()
                ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
                
                metrics_out["总序列数"] = f"{len(sequences)} 条"
                metrics_out["最大长度"] = f"{max(lengths)} 字符"
                metrics_out["最小长度"] = f"{min(lengths)} 字符"
                print(f"✅ 序列长度分布柱状图渲染完成！")

            fig.tight_layout()
            
            ts = int(time.time() * 1000)
            out_path = os.path.join(temp_dir, f"Sequence_Analysis_Plot_{ts}.png")
            fig.savefig(out_path, dpi=150, transparent=False, facecolor='white')
            plt.close(fig)

            print(f"[OutputFile] .cache/Sequence_Analysis_Plot_{ts}.png")
            print(f"[OutputMetrics] {json.dumps(metrics_out)}")
            sys.exit(0)
            
        except ImportError:
            print("❌ 缺少 matplotlib 绘图库。")
            sys.exit(1)


    # =========================================================
    # NW 多序列对齐引擎 (供后两个 Action 调用)
    # =========================================================
    if len(headers) < 2:
        print("❌ [Error] 序列对齐至少需要 2 条以上的序列！")
        sys.exit(1)
        
    print(f">>> 正在启动 Needleman-Wunsch 动态对齐引擎，基准 = {ref_header}...")
    aligned_sequences = {ref_header: sequences[ref_header]}
    
    for target_header in headers[1:]:
        target_seq = sequences[target_header]
        current_ref = aligned_sequences[ref_header]
        raw_ref = current_ref.replace("-", "")

        aligned_ref, aligned_target = needleman_wunsch(
            raw_ref, target_seq, 
            match=args.match_score, 
            mismatch=args.mismatch_score, 
            gap=args.gap_score
        )
        new_msa = {k: "" for k in aligned_sequences.keys()}
        new_msa[target_header] = ""

        ptr_msa = 0
        for i in range(len(aligned_ref)):
            if aligned_ref[i] == "-":
                for k in aligned_sequences.keys(): new_msa[k] += "-"
                new_msa[target_header] += aligned_target[i]
            else:
                while ptr_msa < len(current_ref) and current_ref[ptr_msa] == "-":
                    for k in aligned_sequences.keys(): new_msa[k] += aligned_sequences[k][ptr_msa]
                    new_msa[target_header] += "-"
                    ptr_msa += 1
                for k in aligned_sequences.keys(): new_msa[k] += aligned_sequences[k][ptr_msa]
                new_msa[target_header] += aligned_target[i]
                ptr_msa += 1

        while ptr_msa < len(current_ref):
            for k in aligned_sequences.keys(): new_msa[k] += aligned_sequences[k][ptr_msa]
            new_msa[target_header] += "-"
            ptr_msa += 1
        aligned_sequences = new_msa

    print(f"✅ NW 对齐解算完毕！延伸后总列数: {len(aligned_sequences[ref_header])}")
    chunk_size = int(args.chunk_size)

    # =====================================================================
    # 行动 2：生成 结构化对齐文本 (支持双序列与 ALN)
    # =====================================================================
    if args.action == 'align_text':
        out_aln = os.path.join(temp_dir, "alignment_result.aln")
        
        if "双序列精准比对" in args.combo_style:
            lines = []
            for h in headers[1:]:
                lines.append(f"Pairwise Alignment: {ref_header}  vs  {h}")
                lines.append("="*85)
                
                ref_seq = aligned_sequences[ref_header]
                tgt_seq = aligned_sequences[h]
                ref_map = get_index_mapping(ref_seq)
                tgt_map = get_index_mapping(tgt_seq)
                seq_len = len(ref_seq)
                
                for b in range((seq_len + chunk_size - 1) // chunk_size):
                    start_idx = b * chunk_size
                    end_idx = min((b + 1) * chunk_size, seq_len)
                    
                    # Ref 顶轴
                    ref_idx_str = [" "] * chunk_size
                    for j in range(end_idx - start_idx):
                        idx = ref_map[start_idx + j]
                        if idx is not None and (idx % 10 == 0 or idx == 1):
                            idx_s = str(idx)
                            for k, char in enumerate(idx_s):
                                if j + k < chunk_size: ref_idx_str[j + k] = char
                    
                    ref_seq_str = ref_seq[start_idx:end_idx]
                    
                    # 匹配连线
                    match_str = ""
                    for j in range(end_idx - start_idx):
                        if ref_seq[start_idx+j] == tgt_seq[start_idx+j] and ref_seq[start_idx+j] != '-':
                            match_str += args.match_symbol
                        elif ref_seq[start_idx+j] == '-' or tgt_seq[start_idx+j] == '-':
                            match_str += " "
                        else:
                            match_str += args.mismatch_symbol
                            
                    tgt_seq_str = tgt_seq[start_idx:end_idx]
                    
                    # Tgt 底轴
                    tgt_idx_str = [" "] * chunk_size
                    for j in range(end_idx - start_idx):
                        idx = tgt_map[start_idx + j]
                        if idx is not None and (idx % 10 == 0 or idx == 1):
                            idx_s = str(idx)
                            for k, char in enumerate(idx_s):
                                if j + k < chunk_size: tgt_idx_str[j + k] = char
                    
                    lines.append("".join(ref_idx_str))
                    lines.append(ref_seq_str)
                    lines.append(match_str)
                    lines.append(tgt_seq_str)
                    lines.append("".join(tgt_idx_str))
                    lines.append("")
                lines.append("\n")
                
            with open(out_aln, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
        
        else:
            aln_lines = ["CLUSTAL W (SciForge) multiple sequence alignment\n"]
            seq_len = len(aligned_sequences[ref_header])
            max_name_len = max([len(h) for h in headers])
            for i in range(0, seq_len, chunk_size):
                for h in headers:
                    aln_lines.append(f"{h.ljust(max_name_len + 5)}{aligned_sequences[h][i:i + chunk_size]}")
                aln_lines.append("")
            with open(out_aln, 'w', encoding='utf-8') as f:
                f.write("\n".join(aln_lines))
                
        print(f"[OutputFile] .cache/alignment_result.aln")
        print(f"[OutputCode] .cache/alignment_result.aln")
        print("✨ 对齐文本已生成，请前往【💻 ALN 文本对齐】选项卡查看！")
        sys.exit(0)

    # =====================================================================
    # 行动 3：渲染比对图 (样式与格式深度解耦版)
    # =====================================================================
    elif args.action == 'plot_pub':
        print(f">>> 正在拉起渲染引擎，当前选择预设: {args.combo_style}")
        
        seqs = [aligned_sequences[h] for h in headers]
        n_seqs = len(seqs)
        seq_len = len(seqs[0])
        ts = int(time.time() * 1000)
        
        fmt = getattr(args, 'out_format', "PDF")
        gen_pdf = "PDF" in fmt or "全部" in fmt
        gen_png = "PNG" in fmt or "全部" in fmt
        gen_html = "HTML" in fmt or "全部" in fmt

        ref_map = get_index_mapping(aligned_sequences[ref_header])

        # -------------------------------------------------------------
        # 风格 1: 方格阵列模式 (独立成格)
        # -------------------------------------------------------------
        if "方格阵列" in args.combo_style:
            
            # --- 渲染 HTML 格式 ---
            if gen_html:
                html_lines = [
                    "<!DOCTYPE html><html><head><meta charset='utf-8'><title>SciForge 交互式序列比对</title>",
                    "<style>",
                    "body { font-family: 'Consolas', 'Courier New', monospace; background: #ffffff; padding: 20px; margin: 0; }",
                    ".msa-block { margin-bottom: 35px; display: table; }",
                    ".msa-row { display: flex; align-items: center; margin-bottom: 3px; }",
                    ".seq-name { width: 220px; text-align: right; padding-right: 15px; font-weight: bold; color: #2c3e50; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }",
                    ".aa-box { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; margin-right: 2px; border-radius: 4px; box-sizing: border-box; cursor: pointer; transition: 0.1s; }",
                    ".aa-box:hover { transform: scale(1.1); box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10; }",
                    ".aa-box.ref { border: 1px solid #bdc3c7; background: #f8f9fa; color: #34495e; }",
                    ".aa-box.match { border: 1px solid #bdc3c7; background: #ffffff; color: #95a5a6; }",
                    ".aa-box.mismatch { border: 2px solid #e74c3c; background: #fdedec; color: #c0392b; }",
                    ".aa-box.gap { border: 1px dashed #ecf0f1; background: transparent; color: #bdc3c7; }",
                    ".ruler-row { display: flex; align-items: flex-end; margin-bottom: 4px; }",
                    ".ruler-box { width: 24px; height: 18px; display: flex; align-items: flex-end; justify-content: center; font-size: 11px; color: #7f8c8d; margin-right: 2px; box-sizing: border-box; }",
                    ".legend { display: flex; gap: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px; margin-bottom: 20px; border: 1px solid #e9ecef; align-items: center; font-size: 13px; }",
                    ".legend-item { display: flex; align-items: center; gap: 8px; }",
                    "</style></head><body>",
                    "<h2 style='color: #2980b9; margin-top: 0;'>🧬 交互式方格阵列序列比对</h2>",
                    "<div class='legend'>",
                    "<div class='legend-item'><div class='aa-box ref'>A</div> 基准 (Reference)</div>",
                    "<div class='legend-item'><div class='aa-box match'>A</div> 一致 (Match)</div>",
                    "<div class='legend-item'><div class='aa-box mismatch'>W</div> 突变 (Mismatch)</div>",
                    "<div class='legend-item'><div class='aa-box gap'>-</div> 缺失 (Gap)</div>",
                    "</div>"
                ]

                for b in range((seq_len + chunk_size - 1) // chunk_size):
                    start_idx = b * chunk_size
                    end_idx = min((b + 1) * chunk_size, seq_len)
                    chunk_len_current = end_idx - start_idx

                    html_lines.append("<div class='msa-block'>")

                    html_lines.append("<div class='ruler-row'><div class='seq-name'></div>")
                    for j in range(chunk_len_current):
                        idx = ref_map[start_idx + j]
                        marker = str(idx) if idx is not None and (idx % 10 == 0 or idx == 1) else ("·" if idx is not None and idx % 5 == 0 else "")
                        html_lines.append(f"<div class='ruler-box'>{marker}</div>")
                    html_lines.append("</div>")

                    ref_seq = aligned_sequences[ref_header]
                    html_lines.append(f"<div class='msa-row'><div class='seq-name' title='{ref_header}'>{ref_header}</div>")
                    for j in range(chunk_len_current):
                        char = ref_seq[start_idx + j]
                        css_class = "ref" if char != '-' else "gap"
                        html_lines.append(f"<div class='aa-box {css_class}' title='Pos: {ref_map[start_idx+j]}'>{char}</div>")
                    html_lines.append("</div>")

                    for tgt_header in headers[1:]:
                        tgt_seq = aligned_sequences[tgt_header]
                        html_lines.append(f"<div class='msa-row'><div class='seq-name' title='{tgt_header}'>{tgt_header}</div>")
                        for j in range(chunk_len_current):
                            char_tgt = tgt_seq[start_idx + j]
                            char_ref = ref_seq[start_idx + j]
                            if char_tgt == '-': css_class = "gap"
                            elif args.chk_reference and char_tgt == char_ref: css_class = "match"
                            else: css_class = "mismatch"
                            pos_info = f"Ref Pos: {ref_map[start_idx+j]} | {char_ref} -> {char_tgt}"
                            html_lines.append(f"<div class='aa-box {css_class}' title='{pos_info}'>{char_tgt}</div>")
                        html_lines.append("</div>")

                    html_lines.append("</div>")
                html_lines.append("</body></html>")

                out_html = os.path.join(temp_dir, f"Grid_Alignment_{ts}.html")
                with open(out_html, 'w', encoding='utf-8') as f:
                    f.write("\n".join(html_lines))
                
                if not gen_png and not gen_pdf:
                    print(f"[OutputFile] .cache/Grid_Alignment_{ts}.html")

            # --- 渲染 Matplotlib 格式 (PDF / PNG) ---
            if gen_pdf or gen_png:
                import matplotlib.pyplot as plt
                import matplotlib.patches as patches
                
                n_targets = len(headers) - 1
                n_blocks = (seq_len + chunk_size - 1) // chunk_size
                unit_size = 0.25 
                fig_width = (chunk_size + 3) * unit_size + 3 
                rows_per_block = n_targets + 2.5 
                fig_height = n_blocks * rows_per_block * unit_size + 1
                
                fig, axes = plt.subplots(n_blocks, 1, figsize=(fig_width, fig_height))
                if n_blocks == 1: axes = [axes]
                fig.patch.set_facecolor('white')

                for block_idx in range(n_blocks):
                    ax = axes[block_idx]
                    start_idx = block_idx * chunk_size
                    end_idx = min((block_idx + 1) * chunk_size, seq_len)
                    chunk_len_current = end_idx - start_idx

                    ax.set_xlim(-2, chunk_size + 0.5)
                    ax.set_ylim(-0.5, n_targets + 1.5)
                    ax.invert_yaxis()
                    ax.axis('off')

                    for j in range(chunk_len_current):
                        idx = ref_map[start_idx + j]
                        if idx is not None and (idx % 10 == 0 or idx == 1):
                            ax.text(j, 0, str(idx), ha='center', va='center', fontsize=10, color='#7F8C8D', family='monospace')
                        elif idx is not None and idx % 5 == 0:
                            ax.text(j, 0, "·", ha='center', va='center', fontsize=10, color='#7F8C8D', family='monospace')

                    disp_ref = ref_header[:18] + ".." if len(ref_header) > 20 else ref_header
                    ax.text(-1, 1, disp_ref, ha='right', va='center', fontweight='bold', color='#2C3E50', family='monospace')
                    
                    ref_seq = aligned_sequences[ref_header]
                    for j in range(chunk_len_current):
                        char = ref_seq[start_idx + j]
                        if char != '-':
                            rect = patches.Rectangle((j - 0.45, 1 - 0.45), 0.9, 0.9, linewidth=1, edgecolor='#BDC3C7', facecolor='#F8F9FA')
                            ax.add_patch(rect)
                            ax.text(j, 1, char, ha='center', va='center', fontsize=12, fontweight='bold', color='#34495E', family='monospace')
                        else:
                            rect = patches.Rectangle((j - 0.45, 1 - 0.45), 0.9, 0.9, linewidth=1, edgecolor='#ECF0F1', facecolor='none', linestyle='--')
                            ax.add_patch(rect)
                            ax.text(j, 1, '-', ha='center', va='center', color='#BDC3C7', fontsize=12, family='monospace')

                    for tgt_idx, tgt_header in enumerate(headers[1:]):
                        row_y = 2 + tgt_idx
                        tgt_seq = aligned_sequences[tgt_header]
                        disp_tgt = tgt_header[:18] + ".." if len(tgt_header) > 20 else tgt_header
                        ax.text(-1, row_y, disp_tgt, ha='right', va='center', fontweight='bold', color='#2C3E50', family='monospace')
                        
                        for j in range(chunk_len_current):
                            char_tgt = tgt_seq[start_idx + j]
                            char_ref = ref_seq[start_idx + j]
                            
                            if char_tgt == '-':
                                rect = patches.Rectangle((j - 0.45, row_y - 0.45), 0.9, 0.9, linewidth=1, edgecolor='#ECF0F1', facecolor='none', linestyle='--')
                                ax.add_patch(rect)
                                ax.text(j, row_y, '-', ha='center', va='center', color='#BDC3C7', fontsize=12, family='monospace')
                            elif args.chk_reference and char_tgt == char_ref:
                                rect = patches.Rectangle((j - 0.45, row_y - 0.45), 0.9, 0.9, linewidth=1, edgecolor='#BDC3C7', facecolor='white')
                                ax.add_patch(rect)
                                ax.text(j, row_y, char_tgt, ha='center', va='center', fontsize=12, color='#95A5A6', family='monospace')
                            else:
                                rect = patches.Rectangle((j - 0.45, row_y - 0.45), 0.9, 0.9, linewidth=2, edgecolor='#E74C3C', facecolor='#FDEDEC')
                                ax.add_patch(rect)
                                ax.text(j, row_y, char_tgt, ha='center', va='center', fontsize=12, fontweight='bold', color='#C0392B', family='monospace')

                plt.tight_layout()
                
                out_pdf = os.path.join(temp_dir, f"Grid_Alignment_{ts}.pdf")
                out_png = os.path.join(temp_dir, f"Grid_Alignment_{ts}.png")
                
                if gen_pdf: plt.savefig(out_pdf, dpi=300, bbox_inches='tight', transparent=False)
                if gen_png: plt.savefig(out_png, dpi=300, bbox_inches='tight', transparent=False)
                plt.close()

            if gen_pdf: print(f"[OutputFile] .cache/Grid_Alignment_{ts}.pdf")
            if gen_png: print(f"[OutputFile] .cache/Grid_Alignment_{ts}.png")
            if gen_html: print(f"[OutputFile] .cache/Grid_Alignment_{ts}.html")
            print(f"✨ 方格阵列图已渲染完毕 ({fmt})！")

        # -------------------------------------------------------------
        # 风格 2: 双序列精准比对 (带双重坐标轴)
        # -------------------------------------------------------------
        elif "双序列精准比对" in args.combo_style:
            
            # --- 渲染 HTML 格式 ---
            if gen_html:
                html_lines = [
                    "<!DOCTYPE html><html><head><meta charset='utf-8'><title>SciForge 交互式序列比对</title>",
                    "<style>",
                    "body { font-family: 'Consolas', 'Courier New', monospace; background: #ffffff; padding: 20px; margin: 0; }",
                    ".align-block { margin-bottom: 20px; font-size: 14px; line-height: 1.2; }",
                    ".axis { color: #7f8c8d; font-size: 12px; white-space: pre; }",
                    ".seq { font-weight: bold; color: #2c3e50; white-space: pre; }",
                    ".match { white-space: pre; }",
                    ".match-symbol { color: #2ecc71; }",
                    ".mismatch-symbol { color: #e74c3c; font-weight: bold; }",
                    ".mismatch-aa { color: #c0392b; background-color: #fdedec; font-weight: bold; }",
                    ".tgt-name { color: #27ae60; font-weight: bold; }",
                    ".ref-name { color: #2980b9; font-weight: bold; }",
                    "</style></head><body>",
                    "<h2 style='color: #2980b9; margin-top: 0;'>🧬 交互式双重坐标轴双序列比对</h2>"
                ]
                
                for tgt_header in headers[1:]:
                    html_lines.append(f"<div style='margin-bottom: 40px;'><h3 style='border-bottom: 1px solid #ecf0f1; padding-bottom: 5px;'>Pairwise: <span class='ref-name'>{ref_header}</span> vs <span class='tgt-name'>{tgt_header}</span></h3>")
                    ref_seq = aligned_sequences[ref_header]
                    tgt_seq = aligned_sequences[tgt_header]
                    tgt_map = get_index_mapping(tgt_seq)
                    
                    for b in range((seq_len + chunk_size - 1) // chunk_size):
                        start_idx = b * chunk_size
                        end_idx = min((b + 1) * chunk_size, seq_len)
                        chunk_len_current = end_idx - start_idx
                        html_lines.append("<div class='align-block'>")
                        
                        ref_idx_str = list(" " * chunk_size)
                        for j in range(chunk_len_current):
                            idx = ref_map[start_idx + j]
                            if idx is not None and (idx % 10 == 0 or idx == 1):
                                for k, char in enumerate(str(idx)):
                                    if j + k < chunk_size: ref_idx_str[j + k] = char
                        html_lines.append(f"<div class='axis'>{''.join(ref_idx_str[:chunk_len_current])}</div>")
                        
                        html_lines.append(f"<div class='seq'>{ref_seq[start_idx:end_idx]}</div>")
                        
                        match_html = ""
                        for j in range(chunk_len_current):
                            c1 = ref_seq[start_idx+j]
                            c2 = tgt_seq[start_idx+j]
                            if c1 == c2 and c1 != '-': match_html += f"<span class='match-symbol'>{args.match_symbol}</span>"
                            elif c1 != '-' and c2 != '-': match_html += f"<span class='mismatch-symbol'>{args.mismatch_symbol}</span>"
                            else: match_html += " "
                        html_lines.append(f"<div class='match'>{match_html}</div>")
                        
                        tgt_html = ""
                        for j in range(chunk_len_current):
                            c1 = ref_seq[start_idx+j]
                            c2 = tgt_seq[start_idx+j]
                            if c2 != '-' and c1 != c2 and c1 != '-': tgt_html += f"<span class='mismatch-aa'>{c2}</span>"
                            else: tgt_html += c2
                        html_lines.append(f"<div class='seq'>{tgt_html}</div>")
                        
                        tgt_idx_str = list(" " * chunk_size)
                        for j in range(chunk_len_current):
                            idx = tgt_map[start_idx + j]
                            if idx is not None and (idx % 10 == 0 or idx == 1):
                                for k, char in enumerate(str(idx)):
                                    if j + k < chunk_size: tgt_idx_str[j + k] = char
                        html_lines.append(f"<div class='axis'>{''.join(tgt_idx_str[:chunk_len_current])}</div>")
                        html_lines.append("</div>")
                    html_lines.append("</div>")
                html_lines.append("</body></html>")
                
                out_html = os.path.join(temp_dir, f"Pairwise_Alignment_{ts}.html")
                with open(out_html, 'w', encoding='utf-8') as f:
                    f.write("\n".join(html_lines))
                
                if not gen_png and not gen_pdf:
                    print(f"[OutputFile] .cache/Pairwise_Alignment_{ts}.html")

            # --- 渲染 Matplotlib 格式 (PDF / PNG) ---
            if gen_pdf or gen_png:
                import matplotlib.pyplot as plt
                import matplotlib.patches as patches
                
                n_targets = len(headers) - 1
                n_blocks_per_target = (seq_len + chunk_size - 1) // chunk_size
                total_blocks = n_targets * n_blocks_per_target
                unit_size = 0.25
                fig_width = (chunk_size + 3) * unit_size + 3
                fig_height = total_blocks * 5.5 * unit_size + 1
                
                fig, axes = plt.subplots(total_blocks, 1, figsize=(fig_width, fig_height))
                if total_blocks == 1: axes = [axes]
                fig.patch.set_facecolor('white')
                
                block_counter = 0
                for tgt_header in headers[1:]:
                    ref_seq = aligned_sequences[ref_header]
                    tgt_seq = aligned_sequences[tgt_header]
                    tgt_map = get_index_mapping(tgt_seq)
                    
                    for b in range(n_blocks_per_target):
                        ax = axes[block_counter]
                        start_idx = b * chunk_size
                        end_idx = min((b + 1) * chunk_size, seq_len)
                        chunk_len = end_idx - start_idx
                        
                        ax.set_xlim(-2, chunk_size + 0.5)
                        ax.set_ylim(-0.5, 4.5)
                        ax.invert_yaxis()
                        ax.axis('off')
                        
                        disp_ref = ref_header[:15] + ".." if len(ref_header) > 17 else ref_header
                        disp_tgt = tgt_header[:15] + ".." if len(tgt_header) > 17 else tgt_header
                        
                        ax.text(-1, 1, disp_ref, ha='right', va='center', fontweight='bold', color='#2980B9', family='monospace')
                        ax.text(-1, 3, disp_tgt, ha='right', va='center', fontweight='bold', color='#27AE60', family='monospace')
                        
                        for j in range(chunk_len):
                            idx = ref_map[start_idx + j]
                            if idx is not None and (idx % 10 == 0 or idx == 1):
                                ax.text(j, 0, str(idx), ha='center', va='center', fontsize=9, color='#7F8C8D', family='monospace')
                                
                        for j in range(chunk_len):
                            char = ref_seq[start_idx + j]
                            color = 'black' if char != '-' else '#BDC3C7'
                            ax.text(j, 1, char, ha='center', va='center', fontsize=11, fontweight='bold', color=color, family='monospace')
                            
                        for j in range(chunk_len):
                            char1 = ref_seq[start_idx + j]
                            char2 = tgt_seq[start_idx + j]
                            
                            if char1 == char2 and char1 != '-':
                                ax.text(j, 2, args.match_symbol, ha='center', va='center', fontsize=11, color='#2ECC71', family='monospace')
                            elif char1 != '-' and char2 != '-':
                                ax.text(j, 2, args.mismatch_symbol, ha='center', va='center', fontsize=11, color='#E74C3C', family='monospace')
                                rect = patches.Rectangle((j - 0.4, 3 - 0.4), 0.8, 0.8, linewidth=1, edgecolor='#E74C3C', facecolor='#FDEDEC', zorder=1)
                                ax.add_patch(rect)
                            
                            color_tgt = 'black' if char2 != '-' else '#BDC3C7'
                            if char2 != '-' and char1 != char2 and char1 != '-':
                                color_tgt = '#C0392B'
                            ax.text(j, 3, char2, ha='center', va='center', fontsize=11, fontweight='bold', color=color_tgt, family='monospace', zorder=2)
                            
                        for j in range(chunk_len):
                            idx = tgt_map[start_idx + j]
                            if idx is not None and (idx % 10 == 0 or idx == 1):
                                ax.text(j, 4, str(idx), ha='center', va='center', fontsize=9, color='#7F8C8D', family='monospace')
                                
                        block_counter += 1

                plt.tight_layout()
                plt.subplots_adjust(hspace=0.4)
                
                out_png = os.path.join(temp_dir, f"MSA_Pairwise_Axes_{ts}.png")
                out_pdf = os.path.join(temp_dir, f"MSA_Pairwise_Axes_{ts}.pdf")
                if gen_pdf: plt.savefig(out_pdf, dpi=300, bbox_inches='tight', transparent=False)
                if gen_png: plt.savefig(out_png, dpi=300, bbox_inches='tight', transparent=False)
                plt.close()
                
            if gen_pdf: print(f"[OutputFile] .cache/MSA_Pairwise_Axes_{ts}.pdf")
            if gen_png: print(f"[OutputFile] .cache/MSA_Pairwise_Axes_{ts}.png")
            if gen_html: print(f"[OutputFile] .cache/Pairwise_Alignment_{ts}.html")
            print(f"✨ 双重坐标轴精准比对图已渲染完毕 ({fmt})！")

        # -------------------------------------------------------------
        # 风格 3: ESPript 顶级出版折行图
        # -------------------------------------------------------------
        elif "ESPript" in args.combo_style:
            consensus = []
            freqs = []
            for j in range(seq_len):
                col_chars = [s[j] for s in seqs]
                counter = Counter(col_chars)
                most_common, count = counter.most_common(1)[0]
                if most_common == '-':
                    consensus.append('-')
                    freqs.append(count / n_seqs)
                else:
                    consensus.append(most_common)
                    freqs.append(count / n_seqs)

            # --- 渲染 HTML 格式 ---
            if gen_html:
                html_lines = [
                    "<!DOCTYPE html><html><head><meta charset='utf-8'><title>SciForge 交互式序列比对</title>",
                    "<style>",
                    "body { font-family: 'Consolas', 'Courier New', monospace; background: #ffffff; padding: 20px; margin: 0; }",
                    ".msa-block { margin-bottom: 35px; display: table; }",
                    ".msa-row { display: flex; align-items: center; margin-bottom: 3px; }",
                    ".seq-name { width: 220px; text-align: right; padding-right: 15px; font-weight: bold; color: #2c3e50; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }",
                    ".aa-box { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 13px; margin-right: 2px; border-radius: 4px; box-sizing: border-box; cursor: pointer; transition: 0.1s; }",
                    ".aa-box:hover { transform: scale(1.1); box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10; }",
                    ".aa-100 { background: #c00000; color: #ffffff; font-weight: bold; }",
                    ".aa-strong { background: #ffffff; color: #c00000; border: 1px solid #3498db; font-weight: bold; }",
                    ".aa-weak { background: #ffffff; color: #c00000; font-weight: bold; }",
                    ".aa-normal { background: #ffffff; color: #000000; }",
                    ".aa-gap { background: transparent; color: #bdc3c7; }",
                    ".ruler-row { display: flex; align-items: flex-end; margin-bottom: 4px; }",
                    ".ruler-box { width: 24px; height: 18px; display: flex; align-items: flex-end; justify-content: center; font-size: 11px; color: #7f8c8d; margin-right: 2px; box-sizing: border-box; }",
                    ".legend { display: flex; gap: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px; margin-bottom: 20px; border: 1px solid #e9ecef; align-items: center; font-size: 13px; }",
                    ".legend-item { display: flex; align-items: center; gap: 8px; }",
                    "</style></head><body>",
                    "<h2 style='color: #2980b9; margin-top: 0;'>🧬 ESPript 交互式序列比对神图</h2>",
                    "<div class='legend'>",
                    "<div class='legend-item'><div class='aa-box aa-100'>A</div> 100%绝对保守</div>",
                    f"<div class='legend-item'><div class='aa-box aa-strong'>A</div> &ge;{int(args.espript_thresh*100)}% 强保守</div>",
                    "<div class='legend-item'><div class='aa-box aa-weak'>A</div> &ge;50% 弱保守</div>",
                    "</div>"
                ]
                
                for b in range((seq_len + chunk_size - 1) // chunk_size):
                    start_idx = b * chunk_size
                    end_idx = min((b + 1) * chunk_size, seq_len)
                    chunk_len_current = end_idx - start_idx
                    
                    html_lines.append("<div class='msa-block'>")
                    
                    html_lines.append("<div class='ruler-row'><div class='seq-name'></div>")
                    for j in range(chunk_len_current):
                        idx = ref_map[start_idx + j]
                        marker = str(idx) if idx is not None and (idx % 10 == 0 or idx == 1) else ("·" if idx is not None and idx % 5 == 0 else "")
                        html_lines.append(f"<div class='ruler-box'>{marker}</div>")
                    html_lines.append("</div>")
                    
                    for i, header in enumerate(headers):
                        seq = aligned_sequences[header]
                        html_lines.append(f"<div class='msa-row'><div class='seq-name' title='{header}'>{header}</div>")
                        
                        for j in range(chunk_len_current):
                            global_j = start_idx + j
                            aa = seq[global_j]
                            freq = freqs[global_j]
                            cons_aa = consensus[global_j]
                            
                            css_class = "aa-normal"
                            if aa == '-': css_class = "aa-gap"
                            else:
                                if freq == 1.0 and cons_aa != '-': css_class = "aa-100"
                                elif freq >= args.espript_thresh and aa == cons_aa and cons_aa != '-': css_class = "aa-strong"
                                elif freq >= 0.5 and aa == cons_aa and cons_aa != '-': css_class = "aa-weak"
                                
                            html_lines.append(f"<div class='aa-box {css_class}' title='Pos: {global_j+1} | {aa}'>{aa}</div>")
                        html_lines.append("</div>")
                    html_lines.append("</div>")
                html_lines.append("</body></html>")
                
                out_html = os.path.join(temp_dir, f"MSA_ESPript_{ts}.html")
                with open(out_html, 'w', encoding='utf-8') as f:
                    f.write("\n".join(html_lines))
                    
                if not gen_png and not gen_pdf:
                    print(f"[OutputFile] .cache/MSA_ESPript_{ts}.html")

            # --- 渲染 Matplotlib 格式 (PDF / PNG) ---
            if gen_pdf or gen_png:
                import matplotlib.pyplot as plt
                import matplotlib.patches as patches
                
                n_blocks = (seq_len + chunk_size - 1) // chunk_size
                unit_size = 0.25
                fig_width = (chunk_size + 3) * unit_size + 3
                fig_height = n_blocks * (n_seqs + 3) * unit_size + 1 

                fig, axes = plt.subplots(n_blocks, 1, figsize=(fig_width, fig_height))
                if n_blocks == 1: axes = [axes]
                fig.patch.set_facecolor('white')

                for block_idx in range(n_blocks):
                    ax = axes[block_idx]
                    start_idx = block_idx * chunk_size
                    end_idx = min((block_idx + 1) * chunk_size, seq_len)
                    chunk_len_current = end_idx - start_idx

                    ax.set_xlim(-0.5, chunk_size + 0.5)
                    ax.set_ylim(-2.0, n_seqs + 1.5) 
                    ax.invert_yaxis()
                    ax.axis('off')

                    for j in range(chunk_len_current):
                        global_j = start_idx + j
                        if (global_j + 1) % 10 == 0:
                            ax.text(j, -0.8, str(global_j + 1), ha='center', va='bottom', fontsize=9, color='#555555', family='monospace')
                        elif (global_j + 1) % 5 == 0:
                            ax.text(j, -0.5, "·", ha='center', va='bottom', fontsize=9, color='#888888', family='monospace')

                    for i, (header, seq) in enumerate(zip(headers, seqs)):
                        disp_header = header[:25] + ".." if len(header) > 27 else header
                        ax.text(-1, i, disp_header, ha='right', va='center', fontsize=10, fontweight='bold', color='#2C3E50', family='monospace')

                        chunk_seq = seq[start_idx:end_idx]
                        for j, aa in enumerate(chunk_seq):
                            global_j = start_idx + j
                            freq = freqs[global_j]
                            cons_aa = consensus[global_j]

                            bg_color = 'white'
                            text_color = 'black'
                            weight = 'normal'
                            draw_box = False

                            if aa != '-':
                                if freq == 1.0 and cons_aa != '-':
                                    bg_color = '#C00000' 
                                    text_color = 'white'
                                    weight = 'bold'
                                elif freq >= args.espript_thresh and aa == cons_aa and cons_aa != '-':
                                    text_color = '#C00000'
                                    weight = 'bold'
                                    draw_box = True
                                elif freq >= 0.5 and aa == cons_aa and cons_aa != '-':
                                    text_color = '#C00000' 

                            if bg_color != 'white':
                                rect = patches.Rectangle((j - 0.5, i - 0.5), 1, 1, linewidth=0, facecolor=bg_color, zorder=1)
                                ax.add_patch(rect)
                            if draw_box:
                                rect = patches.Rectangle((j - 0.5, i - 0.5), 1, 1, linewidth=1, edgecolor='#3498DB', facecolor='none', zorder=2)
                                ax.add_patch(rect)
                            if aa != '-':
                                ax.text(j, i, aa, ha='center', va='center', color=text_color, fontsize=11, fontweight=weight, family='monospace', zorder=3)
                            else:
                                ax.text(j, i, '-', ha='center', va='center', color='#BDC3C7', fontsize=11, family='monospace', zorder=3)

                    bar_y = n_seqs + 0.5
                    ax.text(-1, bar_y, "Conservation", ha='right', va='center', fontsize=9, fontstyle='italic', color='#7F8C8D', family='monospace')
                    for j in range(chunk_len_current):
                        global_j = start_idx + j
                        freq = freqs[global_j]
                        if consensus[global_j] == '-': continue 
                        bar_h = freq * 0.8
                        color = '#E74C3C' if freq == 1.0 else ('#F39C12' if freq >= args.espript_thresh else '#95A5A6')
                        rect = patches.Rectangle((j - 0.4, bar_y + 0.4 - bar_h), 0.8, bar_h, linewidth=0, facecolor=color)
                        ax.add_patch(rect)

                plt.tight_layout()
                plt.subplots_adjust(hspace=0.4)
                
                out_png = os.path.join(temp_dir, f"MSA_ESPript_Publication_{ts}.png")
                out_pdf = os.path.join(temp_dir, f"MSA_ESPript_Publication_{ts}.pdf")
                if gen_pdf: plt.savefig(out_pdf, dpi=300, bbox_inches='tight', transparent=False)
                if gen_png: plt.savefig(out_png, dpi=300, bbox_inches='tight', transparent=False)
                plt.close()
                
            if gen_pdf: print(f"[OutputFile] .cache/MSA_ESPript_Publication_{ts}.pdf")
            if gen_png: print(f"[OutputFile] .cache/MSA_ESPript_Publication_{ts}.png")
            if gen_html: print(f"[OutputFile] .cache/MSA_ESPript_{ts}.html")
            print(f"✨ ESPript 智能折行神图已渲染完毕 ({fmt})！")

        # -------------------------------------------------------------
        # 风格 4 & 5: 经典色块矩阵图 (智能折行架构)
        # -------------------------------------------------------------
        else:
            is_clustal = "Clustal" in args.combo_style
            
            aa_colors = {
                'A': '#E60A0A', 'V': '#E60A0A', 'F': '#E60A0A', 'P': '#E60A0A', 'M': '#E60A0A', 'I': '#E60A0A', 'L': '#E60A0A', 'W': '#E60A0A',
                'D': '#145AFF', 'E': '#145AFF', 'R': '#A0A000', 'K': '#A0A000',
                'S': '#14CC14', 'T': '#14CC14', 'Y': '#14CC14', 'H': '#14CC14', 'C': '#14CC14', 'N': '#14CC14', 'G': '#14CC14', 'Q': '#14CC14',
                '-': '#FFFFFF', 'X': '#AAAAAA'
            }
            if not is_clustal:
                aa_colors = {k: '#FFEBEE' for k in aa_colors}
                aa_colors['-'] = '#FFFFFF'

            dark_colors = ['#E60A0A', '#145AFF'] 

            conservation = []
            for j in range(seq_len):
                col_chars = [s[j] for s in seqs if s[j] != '-']
                if not col_chars: conservation.append(0)
                else:
                    most_common_freq = Counter(col_chars).most_common(1)[0][1]
                    conservation.append(most_common_freq / n_seqs)

            # --- 渲染 HTML 格式 ---
            if gen_html:
                html_lines = [
                    "<!DOCTYPE html><html><head><meta charset='utf-8'><title>SciForge 交互式序列比对</title>",
                    "<style>",
                    "body { font-family: 'Consolas', 'Courier New', monospace; background: #ffffff; padding: 20px; margin: 0; }",
                    ".msa-block { margin-bottom: 35px; display: table; }",
                    ".msa-row { display: flex; align-items: center; margin-bottom: 0px; }",
                    ".seq-name { width: 220px; text-align: right; padding-right: 15px; font-weight: bold; color: #2c3e50; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }",
                    ".aa-box { width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-sizing: border-box; cursor: pointer; transition: 0.1s; }",
                    ".aa-box:hover { transform: scale(1.3); box-shadow: 0 2px 5px rgba(0,0,0,0.4); z-index: 10; border: 1px solid black !important; }",
                    ".ruler-row { display: flex; align-items: flex-end; margin-bottom: 4px; }",
                    ".ruler-box { width: 18px; height: 18px; display: flex; align-items: flex-end; justify-content: center; font-size: 10px; color: #7f8c8d; box-sizing: border-box; }",
                    "</style></head><body>",
                    "<h2 style='color: #2980b9; margin-top: 0;'>🧬 经典色块矩阵渲染 (Interactive)</h2>"
                ]
                
                for b in range((seq_len + chunk_size - 1) // chunk_size):
                    start_idx = b * chunk_size
                    end_idx = min((b + 1) * chunk_size, seq_len)
                    chunk_len_current = end_idx - start_idx
                    
                    html_lines.append("<div class='msa-block'>")
                    
                    html_lines.append("<div class='ruler-row'><div class='seq-name'></div>")
                    for j in range(chunk_len_current):
                        idx = ref_map[start_idx + j]
                        marker = str(idx) if idx is not None and (idx % 10 == 0 or idx == 1) else ("·" if idx is not None and idx % 5 == 0 else "")
                        html_lines.append(f"<div class='ruler-box'>{marker}</div>")
                    html_lines.append("</div>")
                    
                    for i, header in enumerate(headers):
                        seq = aligned_sequences[header]
                        html_lines.append(f"<div class='msa-row'><div class='seq-name' title='{header}'>{header}</div>")
                        
                        for j in range(chunk_len_current):
                            global_j = start_idx + j
                            aa = seq[global_j]
                            aa_upper = aa.upper()
                            
                            bg_color = aa_colors.get(aa_upper, aa_colors['-'])
                            txt_color = 'black'
                            
                            if not is_clustal and i > 0 and args.chk_reference:
                                ref_aa = aligned_sequences[ref_header][global_j].upper()
                                if aa_upper == ref_aa and aa_upper != '-': bg_color = '#AAAAAA'
                                elif aa_upper != ref_aa and aa_upper != '-': txt_color = '#D32F2F'
                            
                            if is_clustal and aa_colors.get(aa_upper, '#FFF') in dark_colors:
                                txt_color = 'white'
                                
                            if aa == '-':
                                txt_color = 'transparent'
                                
                            border = 'border: 1px solid white;' if not is_clustal else ''
                            html_lines.append(f"<div class='aa-box' style='background-color: {bg_color}; color: {txt_color}; {border}' title='Pos: {global_j+1} | {aa}'>{aa if aa != '-' else ''}</div>")
                        html_lines.append("</div>")
                    html_lines.append("</div>")
                html_lines.append("</body></html>")
                
                out_html = os.path.join(temp_dir, f"Matrix_Alignment_{ts}.html")
                with open(out_html, 'w', encoding='utf-8') as f:
                    f.write("\n".join(html_lines))
                    
                if not gen_png and not gen_pdf:
                    print(f"[OutputFile] .cache/Matrix_Alignment_{ts}.html")

            # --- 渲染 Matplotlib 格式 (PDF / PNG) ---
            if gen_pdf or gen_png:
                import matplotlib.pyplot as plt
                import matplotlib.patches as patches
                import numpy as np
                
                n_blocks = (seq_len + chunk_size - 1) // chunk_size
                unit_size = 0.25
                fig_width = (chunk_size + 3) * unit_size + 3
                rows_per_block = n_seqs + 2.5
                fig_height = n_blocks * rows_per_block * unit_size + 1
                
                fig, axes = plt.subplots(n_blocks, 1, figsize=(fig_width, fig_height))
                if n_blocks == 1: axes = [axes]
                fig.patch.set_facecolor('white')

                for block_idx in range(n_blocks):
                    ax = axes[block_idx]
                    start_idx = block_idx * chunk_size
                    end_idx = min((block_idx + 1) * chunk_size, seq_len)
                    chunk_len_current = end_idx - start_idx

                    ax.set_xlim(-2, chunk_size + 0.5)
                    ax.set_ylim(-0.5, n_seqs + 2.5) 
                    ax.invert_yaxis()
                    ax.axis('off')

                    bar_y_base = 0.8
                    ax.text(-1, 0.4, "Conservation", ha='right', va='center', fontsize=10, fontweight='bold', color='#333', family='sans-serif')
                    for j in range(chunk_len_current):
                        global_j = start_idx + j
                        if (global_j + 1) % 10 == 0 or (global_j + 1) == 1:
                            ax.text(j, 1.2, str(global_j + 1), ha='center', va='center', fontsize=9, color='#7F8C8D', family='monospace')
                        elif (global_j + 1) % 5 == 0:
                            ax.text(j, 1.2, "·", ha='center', va='center', fontsize=9, color='#7F8C8D', family='monospace')
                        
                        freq = conservation[global_j]
                        bar_h = freq * 0.8
                        rect = patches.Rectangle((j - 0.4, bar_y_base - bar_h), 0.8, bar_h, linewidth=0, facecolor='#34495e')
                        ax.add_patch(rect)

                    for i, (header, seq) in enumerate(zip(headers, seqs)):
                        row_y = 2 + i
                        disp_name = header[:18] + ".." if len(header) > 20 else header
                        ax.text(-1, row_y, disp_name, ha='right', va='center', fontweight='bold', color='#333', family='monospace')
                        
                        chunk_seq = seq[start_idx:end_idx]
                        for j, aa in enumerate(chunk_seq):
                            global_j = start_idx + j
                            aa_upper = aa.upper()
                            
                            bg_color = aa_colors.get(aa_upper, aa_colors['-'])
                            txt_color = 'black'
                            
                            if not is_clustal and i > 0 and args.chk_reference:
                                ref_aa = seqs[0][global_j].upper()
                                if aa_upper == ref_aa and aa_upper != '-':
                                    bg_color = '#AAAAAA'
                                elif aa_upper != ref_aa and aa_upper != '-':
                                    txt_color = '#D32F2F'
                            
                            if is_clustal and aa_colors.get(aa_upper, '#FFF') in dark_colors:
                                txt_color = 'white'
                                
                            rect = patches.Rectangle((j - 0.5, row_y - 0.5), 1, 1, linewidth=0.5, edgecolor='white', facecolor=bg_color)
                            ax.add_patch(rect)
                            
                            if aa != '-':
                                ax.text(j, row_y, aa, ha='center', va='center', color=txt_color, fontsize=10, family='monospace', fontweight='bold')

                plt.tight_layout()
                plt.subplots_adjust(hspace=0.4)
                
                out_png = os.path.join(temp_dir, f"MSA_Matrix_Publication_{ts}.png")
                out_pdf = os.path.join(temp_dir, f"MSA_Matrix_Publication_{ts}.pdf")
                if gen_pdf: plt.savefig(out_pdf, dpi=300, bbox_inches='tight', transparent=False)
                if gen_png: plt.savefig(out_png, dpi=300, bbox_inches='tight', transparent=False)
                plt.close()
                
            if gen_pdf: print(f"[OutputFile] .cache/MSA_Matrix_Publication_{ts}.pdf")
            if gen_png: print(f"[OutputFile] .cache/MSA_Matrix_Publication_{ts}.png")
            if gen_html: print(f"[OutputFile] .cache/Matrix_Alignment_{ts}.html")
            print(f"✨ 矩阵色块比对图已渲染完毕 ({fmt})！")

        print("\n👉 【提示】渲染产物已自动加入您的右侧预览图库，您可以在图库中随意切换查看，或者在【📤多维结果归档】中挑选打包并入库！")

    sys.exit(0)