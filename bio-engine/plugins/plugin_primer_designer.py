# plugins/plugin_primer_designer.py
import os
import sys
import argparse
import json
import time

try:
    import primer3
    PRIMER3_AVAILABLE = True
except ImportError:
    PRIMER3_AVAILABLE = False

try:
    import snapgene_reader
    SNAPGENE_AVAILABLE = True
except ImportError:
    SNAPGENE_AVAILABLE = False

PLUGIN_ID = "primer_designer"
PLUGIN_NAME = "批量引物验证与出版级标注引擎"
PLUGIN_ICON = "🎯"
PLUGIN_DESC = "专注批量验证。支持最佳寻迹、智能序列折叠(省纸模式)、PCR片段居中大字标注及自定义排数(完美竖向A4)物理分页。"

# ==========================================
# 前端表单 UI Schema (纯净版)
# ==========================================
UI_SCHEMA = [
    {"key": "file_path", "label": "📁 导入模板 (支持 FASTA / SnapGene .dna)", "type": "file", "default": "", "span": 12},
    {"key": "template_seq", "label": "📄 或在此直接粘贴模板序列", "type": "textarea", "default": "", "span": 12},
    {"key": "check_primers", "label": "🧬 批量粘贴待验证引物 (支持 FASTA 格式或多行序列)", "type": "textarea", "default": "", "span": 12},
    
    # 🌟 按照要求：加入动态排数设置，并将宽度匀分为 4-4-4
    {"key": "out_format", "label": "可视化格式", "type": "select", "options": ["PDF (推荐)", "PNG", "全部格式打包"], "default": "PDF (推荐)", "span": 4},
    {"key": "chunk_size", "label": "每行排版字符数", "type": "select", "options": ["40", "60", "80", "100", "120"], "default": "80", "span": 4},
    {"key": "blocks_per_page", "label": "每页排版行数 (纵向A4)", "type": "number", "default": 10, "span": 4},
    
    {"key": "aa_offset", "label": "翻译起始偏移 (0,1,2)", "type": "number", "default": 0, "span": 6},
    {"key": "aa_start_idx", "label": "氨基酸起始编号", "type": "number", "default": 1, "span": 6},
]

UI_LAYOUT = {
    "direction": "row",
    "blocks": [
        {"type": "form", "width": "400px", "height": "100%"},
        {"type": "tabs", "flex": "1", "height": "100%", "panes": [
            {"title": "👁️ 轨道视图预览", "type": "preview"},
            {"title": "📋 引物比对详情", "type": "table"},
            {"title": "📊 核心评估指标", "type": "metrics"},
            {"title": "🎯 详细寻迹日志", "type": "terminal"}
        ]}
    ],
    "footer_actions": [
        {"id": "analyze", "label": "🧬 1. 执行批量寻迹与物理分析", "type": "default"},
        {"id": "plot_pub", "label": "📊 2. 渲染 A4 智能折叠版标注图", "type": "primary"}
    ]
}

CODON_TABLE = {
    'ATA':'I', 'ATC':'I', 'ATT':'I', 'ATG':'M', 'ACA':'T', 'ACC':'T', 'ACG':'T', 'ACT':'T',
    'AAC':'N', 'AAT':'N', 'AAA':'K', 'AAG':'K', 'AGC':'S', 'AGT':'S', 'AGA':'R', 'AGG':'R',
    'CTA':'L', 'CTC':'L', 'CTG':'L', 'CTT':'L', 'CCA':'P', 'CCC':'P', 'CCG':'P', 'CCT':'P',
    'CAC':'H', 'CAT':'H', 'CAA':'Q', 'CAG':'Q', 'CGA':'R', 'CGC':'R', 'CGG':'R', 'CGT':'R',
    'GTA':'V', 'GTC':'V', 'GTG':'V', 'GTT':'V', 'GCA':'A', 'GCC':'A', 'GCG':'A', 'GCT':'A',
    'GAC':'D', 'GAT':'D', 'GAA':'E', 'GAG':'E', 'GGA':'G', 'GGC':'G', 'GGG':'G', 'GGT':'G',
    'TCA':'S', 'TCC':'S', 'TCG':'S', 'TCT':'S', 'TTC':'F', 'TTT':'F', 'TTA':'L', 'TTG':'L',
    'TAC':'Y', 'TAT':'Y', 'TAA':'*', 'TAG':'*', 'TGC':'C', 'TGT':'C', 'TGA':'*', 'TGG':'W',
}

def get_sync_workspace():
    try: base_dir = os.path.dirname(__file__)
    except: base_dir = os.getcwd()
    config_file = os.path.abspath(os.path.join(base_dir, "../sciforge_config.json"))
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f); return cfg.get("data_hub_path", base_dir)
        except: pass
    return os.path.abspath(os.path.join(base_dir, "../SciForge_Workspace/SciForge_Data"))

def clean_sequence(raw_seq):
    lines = raw_seq.strip().split('\n')
    if lines and lines[0].startswith('>'): lines = lines[1:]
    return "".join(filter(str.isalpha, "".join(lines))).upper()

def reverse_complement(seq):
    trans = str.maketrans('ATCGN', 'TAGCN')
    return seq.upper().translate(trans)[::-1]

# 🌟 全局悬垂寻迹引擎 v5.0
def sliding_window_match(template, query_seq, is_reverse=False):
    search_seq = reverse_complement(query_seq) if is_reverse else query_seq.upper()
    best_score = -1
    best_idx = -1
    best_mismatches = []
    q_len = len(search_seq)
    t_len = len(template)
    
    for i in range(-q_len + 1, t_len):
        start_t = max(0, i)
        end_t = min(t_len, i + q_len)
        start_q = start_t - i
        end_q = end_t - i
        
        window = template[start_t:end_t]
        query_window = search_seq[start_q:end_q]
        matches = sum(1 for a, b in zip(window, query_window) if a == b)
        
        if matches > best_score and matches >= 10:
            best_score = matches
            best_idx = i
            mismatches = []
            for j in range(q_len):
                if j < start_q or j >= end_q: mismatches.append(j)
                elif search_seq[j] != template[i + j]: mismatches.append(j)
            best_mismatches = mismatches
            
    if best_score < min(15, q_len * 0.5):
        return -1, search_seq, [], 0
    return best_idx, search_seq, best_mismatches, best_score

def read_if_file(text_input, ws):
    if not text_input or len(text_input) > 2000 or '\n' in text_input or '>' in text_input: return text_input
    try:
        p1 = os.path.join(ws, text_input)
        if os.path.exists(p1):
            with open(p1, 'r', encoding='utf-8') as f: return f.read().strip()
    except: pass
    return text_input

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', type=str, default='analyze')
    for item in UI_SCHEMA:
        if item["type"] == "number": parser.add_argument(f"--{item['key']}", type=float, default=item.get("default", 0.0))
        else: parser.add_argument(f"--{item['key']}", type=str, default=str(item.get("default", "")))
    args = parser.parse_args()
    
    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)

    template_raw = read_if_file(args.template_seq.strip(), workspace)
    f_path_str = args.file_path.strip()
    dna_extracted_primers = []

    print(f"\n🚀 [Workflow] 启动批量寻迹验证引擎 | 模板长度: {len(template_raw) if template_raw else 0} bp")
    
    if f_path_str:
        file_paths = [os.path.join(workspace, p.strip()) for p in f_path_str.split(',') if p.strip()]
        if file_paths and os.path.exists(file_paths[0]):
            if file_paths[0].lower().endswith('.dna') and SNAPGENE_AVAILABLE:
                try:
                    seq_dict = snapgene_reader.snapgene_file_to_dict(file_paths[0])
                    template_raw = seq_dict['seq'].upper()
                    for feat in seq_dict.get('features', []):
                        if feat.get('type') == 'primer_bind':
                            s, e, d = int(feat.get('start', 0)), int(feat.get('end', 0)), feat.get('strand', '+')
                            p_seq = template_raw[s:e+1] if d == '+' else reverse_complement(template_raw[s:e+1])
                            dna_extracted_primers.append((feat.get('name', 'DNA_Primer'), p_seq.upper()))
                    print(f"📦 [Parser] 从 .dna 文件中提取到 {len(dna_extracted_primers)} 条引物。")
                except: print("⚠️ [Error] SnapGene 解析失败。")
            else:
                with open(file_paths[0], 'r', encoding='utf-8') as f: template_raw = f.read().strip()
                    
    if not template_raw: sys.exit(1)
    template = clean_sequence(template_raw)
    valid_primers_cache = []

    check_raw = read_if_file(args.check_primers.strip(), workspace)
    primer_list = []
    if check_raw:
        lines, curr_name, curr_seq = check_raw.split('\n'), "", []
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith(">"):
                if curr_seq: primer_list.append((curr_name if curr_name else f"P_{len(primer_list)}", "".join(curr_seq)))
                curr_name, curr_seq = line[1:], []
            else: curr_seq.append("".join(filter(str.isalpha, line)))
        if curr_seq: primer_list.append((curr_name if curr_name else f"P_{len(primer_list)}", "".join(curr_seq)))
    primer_list.extend(dna_extracted_primers)

    table_lines = ["引物名称,结合方向,全长,最佳位置,Tm(℃),错配或悬垂数"]
    metrics_data = {}

    print("\n" + "="*50 + "\n🎯 详细寻迹工作流日志\n" + "="*50)
    for name, p_seq in primer_list:
        p_seq = p_seq.upper()
        
        fi, fs, fm, f_score = sliding_window_match(template, p_seq, False)
        ri, rs, rm, r_score = sliding_window_match(template, p_seq, True)
        
        print(f"🔹 正在验证引物: {name}")
        print(f"   [正向匹配] 连续结合点得分: {f_score}/{len(p_seq)} | 错配/悬垂: {len(fm)}")
        print(f"   [反向匹配] 连续结合点得分: {r_score}/{len(p_seq)} | 错配/悬垂: {len(rm)}")

        if fi != -1 and (ri == -1 or f_score >= r_score):
            d, idx, s, m = "Forward", fi, fs, fm
            print(f"   ✅ 智能靶向: 正向结合 (Forward) @物理坐标 {idx+1}")
        elif ri != -1:
            d, idx, s, m = "Reverse", ri, rs, rm
            print(f"   ✅ 智能靶向: 反向结合 (Reverse) @物理坐标 {idx+1}")
        else:
            print(f"   ❌ 寻迹失败: 该引物在模板上无法形成足够强度的结合。")
            continue
            
        tm = round(primer3.calc_tm(p_seq), 2)
        valid_primers_cache.append({"name": name, "seq": p_seq, "direction": d, "start": idx, "len": len(p_seq), "mismatches": m, "search_seq": s, "tm": tm})
        table_lines.append(f"{name},{d},{len(p_seq)},{idx+1},{tm},{len(m)}")
        metrics_data[name] = f"Tm: {tm}℃ | GC: {round(sum(1 for b in p_seq if b in 'GC')/len(p_seq)*100,1)}% | 错配: {len(m)}"
    print("="*50 + "\n")

    print("\n" + "="*50 + "\n🧬 自动计算 PCR 产物长度\n" + "="*50)
    pcr_pairs = []
    fwd_list = sorted([p for p in valid_primers_cache if p['direction'] == 'Forward'], key=lambda x: x['start'])
    rev_list = sorted([p for p in valid_primers_cache if p['direction'] == 'Reverse'], key=lambda x: x['start'])

    for fp in fwd_list:
        downstream_rps = [rp for rp in rev_list if rp['start'] > fp['start']]
        if downstream_rps:
            closest_rp = min(downstream_rps, key=lambda x: x['start'])
            size = (closest_rp['start'] + closest_rp['len']) - fp['start']
            mid_point = fp['start'] + size / 2.0 
            pcr_pairs.append({
                'fwd': fp, 'rev': closest_rp, 'size': size, 
                'mid': mid_point
            })
            print(f"   ✨ 锁定有效扩增配对: [{fp['name']}] + [{closest_rp['name']}] => {size} bp")

    pcr_display_text = " | ".join([f"[{p['fwd']['name']}]➔[{p['rev']['name']}]: {p['size']}bp" for p in pcr_pairs]) if pcr_pairs else "未检测到有效对"
    metrics_data["🌟 预测PCR片段"] = pcr_display_text
    print("="*50 + "\n")

    with open(os.path.join(temp_dir, "Primer_Validation.csv"), 'w', encoding='utf-8-sig') as f: f.write("\n".join(table_lines))
    if args.action == 'analyze':
        print(f"[OutputTable] .cache/Primer_Validation.csv")
        print(f"[OutputMetrics] {json.dumps(metrics_data)}")
        sys.exit(0)

    # --- 绘图流程 ---
    if args.action == 'plot_pub':
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.backends.backend_pdf import PdfPages
        
        if not valid_primers_cache: sys.exit(1)
        
        render_primers = valid_primers_cache
        min_s, max_e = min([p['start'] for p in render_primers]), max([p['start']+p['len'] for p in render_primers])
        plot_s, plot_e = max(0, min_s-25), min(len(template), max_e+25)
        sub_t, sub_rc = template[plot_s:plot_e], reverse_complement(template[plot_s:plot_e])
        
        aa_map = {}
        aa_cnt = int(args.aa_start_idx)
        for i in range(int(args.aa_offset), len(sub_t)-2, 3):
            aa_map[i+1] = (CODON_TABLE.get(sub_t[i:i+3], 'X'), aa_cnt); aa_cnt += 1
        
        chunk = int(args.chunk_size)
        n_blocks = (len(sub_t)+chunk-1)//chunk
        
        raw_blocks = []
        for b in range(n_blocks):
            si = b * chunk
            ei = min((b + 1) * chunk, len(sub_t))
            has_fwd = any(p['start'] - plot_s + p['len'] > si and p['start'] - plot_s < ei for p in render_primers if p['direction'] == 'Forward')
            has_rev = any(p['start'] - plot_s + p['len'] > si and p['start'] - plot_s < ei for p in render_primers if p['direction'] == 'Reverse')
            raw_blocks.append({'type': 'seq', 'b': b, 'si': si, 'ei': ei, 'has_fwd': has_fwd, 'has_rev': has_rev, 'h': 7.5})

        render_blocks = []
        i = 0
        while i < len(raw_blocks):
            if not raw_blocks[i]['has_fwd'] and not raw_blocks[i]['has_rev']:
                j = i
                while j < len(raw_blocks) and not raw_blocks[j]['has_fwd'] and not raw_blocks[j]['has_rev']:
                    j += 1
                empty_count = j - i
                
                if empty_count >= 3: 
                    omit_si = raw_blocks[i]['si']
                    omit_ei = raw_blocks[j-1]['ei']
                    bp_omitted = omit_ei - omit_si
                    render_blocks.append({
                        'type': 'omitted', 'si': omit_si, 'ei': omit_ei, 'bp': bp_omitted, 'h': 2.5
                    })
                else:
                    for k in range(i, j): render_blocks.append(raw_blocks[k])
                i = j
            else:
                render_blocks.append(raw_blocks[i])
                i += 1

        blocks_per_page = int(getattr(args, 'blocks_per_page', 10))
        if blocks_per_page <= 0: blocks_per_page = 10
        target_page_h = 7.5 * blocks_per_page
        
        pages = []
        current_page = []
        curr_h = 0
        for rb in render_blocks:
            if curr_h + rb['h'] > target_page_h and current_page:
                pages.append(current_page)
                current_page = []
                curr_h = 0
            current_page.append(rb)
            curr_h += rb['h']
        if current_page: pages.append(current_page)

        unit_x, unit_y = 0.16, 0.22 
        fig_w = (chunk+6)*unit_x
        
        ts = int(time.time()*1000)
        pdf_name = f"Snap_{ts}.pdf"
        pdf_path = os.path.join(temp_dir, pdf_name)
        pdf_pages = PdfPages(pdf_path) if ("PDF" in args.out_format or "全部" in args.out_format) else None
        png_paths = []

        for page_idx, page_blocks in enumerate(pages):
            fig_h = sum(rb['h'] for rb in page_blocks) * unit_y + 0.8
            fig, axes = plt.subplots(len(page_blocks), 1, figsize=(fig_w, fig_h), 
                                     gridspec_kw={'height_ratios': [rb['h'] for rb in page_blocks]})
            if len(page_blocks) == 1: axes = [axes]
            fig.patch.set_facecolor('white')

            for ax, rb in zip(axes, page_blocks):
                ax.set_xlim(-5, chunk+1)
                ax.set_ylim(-0.5, rb['h'] - 0.5) 
                ax.invert_yaxis()
                ax.axis('off')
                
                if rb['type'] == 'omitted':
                    ax.plot([-2, chunk+2], [0.8, 0.8], color='#BDC3C7', linestyle='--', lw=1.5, zorder=1)
                    ax.text(chunk/2, 0.8, f" ... [ {rb['bp']} bp Sequence Omitted ] ... ", 
                            ha='center', va='center', color='#7F8C8D', fontsize=10, style='italic',
                            bbox=dict(facecolor='white', edgecolor='none', pad=3), zorder=2)
                    
                    for pair in pcr_pairs:
                        if plot_s + rb['si'] <= pair['mid'] < plot_s + rb['ei']:
                            pcr_str = f"<- [{pair['fwd']['name']}] PCR: {pair['size']} bp [{pair['rev']['name']}] ->"
                            ax.text(chunk/2, 1.8, pcr_str, 
                                    color='#C0392B', fontsize=15, fontweight='bold', ha='center', va='center')
                    continue

                si, ei = rb['si'], rb['ei']
                cl = ei - si
                fm, fr = {'family': 'Courier New', 'size': 11, 'weight': 'bold'}, {'family': 'Courier New', 'size': 9}

                for p in [p for p in render_primers if p['direction'] == 'Forward']:
                    rel_s = p['start'] - plot_s
                    if rel_s+p['len'] > si and rel_s < ei:
                        xs, xe = max(0, rel_s-si), min(cl, rel_s+p['len']-si)
                        ish, ist = (rel_s+p['len'] <= ei), (rel_s >= si)
                        yc, h = 0.8, 0.85
                        xl, xr = xs-0.45 if ist else xs-0.5, xe-0.55
                        pts = [[xl, yc-h/2]]
                        if ish: pts += [[xr, yc-h/2], [xr+0.45, yc], [xr, yc+h/2]]
                        else: pts += [[xe-0.5, yc-h/2], [xe-0.5, yc+h/2]]
                        pts += [[xl, yc+h/2]]
                        ax.add_patch(patches.Polygon(pts, closed=True, fill=False, edgecolor='#9B59B6', lw=1.5))
                        
                        if ist: ax.text(xs, yc - 0.75, f"{p['name']} ->", fontsize=9, color='#8E44AD', weight='bold', va='bottom', ha='left')
                        for j in range(xs, xe):
                            p_idx = si+j-rel_s
                            char = p['seq'][p_idx]
                            color = '#E74C3C' if p_idx in p['mismatches'] else '#8E44AD'
                            ax.text(j, yc, char, ha='center', va='center', color=color, **fm)
                            
                        mutated_codons = {}
                        aa_off = int(getattr(args, 'aa_offset', 0))
                        for m_idx in p['mismatches']:
                            global_pos = p['start'] + m_idx
                            local_pos = global_pos - plot_s
                            if local_pos >= aa_off:
                                local_codon_start = local_pos - ((local_pos - aa_off) % 3)
                                global_codon_start = plot_s + local_codon_start
                                if global_codon_start not in mutated_codons:
                                    mutated_codons[global_codon_start] = {}
                                mutated_codons[global_codon_start][local_pos - local_codon_start] = p['search_seq'][m_idx]
                                
                        for g_c_start, muts in mutated_codons.items():
                            if g_c_start + 3 <= len(template):
                                orig_codon = template[g_c_start:g_c_start+3]
                                mut_codon_list = list(orig_codon)
                                for offset, mut_base in muts.items():
                                    mut_codon_list[offset] = mut_base
                                mut_codon = "".join(mut_codon_list)
                                orig_aa = CODON_TABLE.get(orig_codon, 'X')
                                mut_aa = CODON_TABLE.get(mut_codon, 'X')
                                if orig_aa != mut_aa and mut_aa != 'X':
                                    local_codon_start = g_c_start - plot_s
                                    center_j = local_codon_start + 1 - si
                                    if 0 <= center_j < cl:
                                        # 🌟 修改点 1：将正向突变氨基酸的 Y 轴对齐到引物名称的高度 (yc - 0.75)
                                        ax.text(center_j, yc - 0.75, f"{mut_aa}", ha='center', va='center', color='#C0392B', **fm)

                for j in range(cl):
                    abs_p = plot_s+si+j+1
                    if abs_p % 10 == 0 or abs_p == 1:
                        ax.text(j, 1.9, str(abs_p), ha='center', va='bottom', color='#34495E', **fr)
                        ax.plot([j, j], [2.1, 2.25], color='#7F8C8D', lw=1.2)

                ax.plot([-0.5, cl-0.5], [2.6, 2.6], color='#7F8C8D', lw=1.2) 
                for j in range(cl):
                    ax.text(j, 2.3, sub_t[si+j], ha='center', va='center', color='#2C3E50', **fm)
                    abs_p = plot_s+si+j+1
                    if abs_p % 10 == 0 or abs_p == 1: ax.plot([j, j], [2.45, 2.75], color='#7F8C8D', lw=1.2)
                    else: ax.plot([j, j], [2.55, 2.65], color='#BDC3C7', lw=1)
                    ax.text(j, 2.9, sub_rc[len(sub_t)-1-(si+j)], ha='center', va='center', color='#7F8C8D', **fm)

                ax.add_patch(patches.Rectangle((-0.5, 3.7-0.35), cl, 0.7, lw=0, fc='#900C3F', alpha=0.9))
                for j in range(cl):
                    if si+j in aa_map:
                        ac, an = aa_map[si+j]
                        ax.text(j, 3.7, ac, ha='center', va='center', color='white', **fm)
                        ax.text(j, 4.4, str(an), ha='center', va='top', fontsize=8, color='#900C3F', weight='bold', family='monospace')

                for pair in pcr_pairs:
                    if plot_s + si <= pair['mid'] < plot_s + ei:
                        local_mid = pair['mid'] - (plot_s + si)
                        pcr_str = f"<- [{pair['fwd']['name']}] PCR: {pair['size']} bp [{pair['rev']['name']}] ->"
                        ax.text(local_mid, 5.4, pcr_str, 
                                color='#C0392B', fontsize=15, fontweight='bold', ha='center', va='center')

                for p in [p for p in render_primers if p['direction'] == 'Reverse']:
                    rel_s = p['start'] - plot_s
                    if rel_s+p['len'] > si and rel_s < ei:
                        xs, xe = max(0, rel_s-si), min(cl, rel_s+p['len']-si)
                        ish, ist = (rel_s >= si), (rel_s+p['len'] <= ei)
                        yc, h = 6.4, 0.85
                        xl, xr = xs-0.45 if ish else xs-0.5, xe-0.55 if ist else xe-0.5
                        
                        pts = [[xr, yc-h/2]] 
                        if ish: pts.extend([[xl+0.45, yc-h/2], [xl, yc], [xl+0.45, yc+h/2]]) 
                        else: pts.extend([[xl, yc-h/2], [xl, yc+h/2]]) 
                        pts.append([xr, yc+h/2]) 
                        
                        ax.add_patch(patches.Polygon(pts, closed=True, fill=False, edgecolor='#9B59B6', lw=1.5))
                        if ish: ax.text(xs, yc + 0.75, f"<- {p['name']}", fontsize=9, color='#8E44AD', weight='bold', va='top', ha='left')
                        
                        rev_print_seq = p['seq'][::-1]
                        for j in range(xs, xe):
                            p_idx = si+j-rel_s
                            char = rev_print_seq[p_idx]
                            color = '#E74C3C' if p_idx in p['mismatches'] else '#8E44AD'
                            ax.text(j, yc, char, ha='center', va='center', color=color, **fm)
                            
                        mutated_codons = {}
                        aa_off = int(getattr(args, 'aa_offset', 0))
                        for m_idx in p['mismatches']:
                            global_pos = p['start'] + m_idx
                            local_pos = global_pos - plot_s
                            if local_pos >= aa_off:
                                local_codon_start = local_pos - ((local_pos - aa_off) % 3)
                                global_codon_start = plot_s + local_codon_start
                                if global_codon_start not in mutated_codons:
                                    mutated_codons[global_codon_start] = {}
                                mutated_codons[global_codon_start][local_pos - local_codon_start] = p['search_seq'][m_idx]
                                
                        for g_c_start, muts in mutated_codons.items():
                            if g_c_start + 3 <= len(template):
                                orig_codon = template[g_c_start:g_c_start+3]
                                mut_codon_list = list(orig_codon)
                                for offset, mut_base in muts.items():
                                    mut_codon_list[offset] = mut_base
                                mut_codon = "".join(mut_codon_list)
                                orig_aa = CODON_TABLE.get(orig_codon, 'X')
                                mut_aa = CODON_TABLE.get(mut_codon, 'X')
                                if orig_aa != mut_aa and mut_aa != 'X':
                                    local_codon_start = g_c_start - plot_s
                                    center_j = local_codon_start + 1 - si
                                    if 0 <= center_j < cl:
                                        # 🌟 修改点 2：将反向突变氨基酸的 Y 轴对齐到引物名称的高度 (yc + 0.75)
                                        ax.text(center_j, yc + 0.75, f"{mut_aa}", ha='center', va='center', color='#C0392B', **fm)

            plt.tight_layout()
            plt.subplots_adjust(hspace=0.25)
            
            if pdf_pages: pdf_pages.savefig(fig, bbox_inches='tight')
            if "PNG" in args.out_format or "全部" in args.out_format:
                png_name = f"Snap_{ts}_p{page+1}.png" if len(pages) > 1 else f"Snap_{ts}.png"
                png_path = os.path.join(temp_dir, png_name)
                plt.savefig(png_path, dpi=300, bbox_inches='tight')
                png_paths.append(png_name)
            plt.close(fig)

        if pdf_pages:
            pdf_pages.close()
            print(f"[OutputFile] .cache/{pdf_name}")
            
        for p_name in png_paths:
            print(f"[OutputFile] .cache/{p_name}")
            
        print(f"✅ 渲染成功！支持动态控制排数的高清出版级图谱已生成。")
        sys.exit(0)