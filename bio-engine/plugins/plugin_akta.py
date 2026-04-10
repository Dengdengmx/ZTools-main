# plugins/plugin_akta.py
import os
import sys
import argparse
import json
import pandas as pd
import numpy as np
from io import StringIO
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MultipleLocator, MaxNLocator, NullLocator

trapz_func = getattr(np, 'trapezoid', np.trapz)

PLUGIN_NAME = "AKTA 层析智能分析"
PLUGIN_ICON = "⚗️"
PLUGIN_DESC = "自动识别 UNICORN 复杂表头，支持收集管(Fraction)贴底映射、靶向回收管无缝高亮与积分。"

UI_SCHEMA = [
    {"key": "file_path", "label": "📁 选择本地层析数据 (.csv/.txt/.xlsx)", "type": "file", "span": 12},
    
    {"key": "auto_col", "label": "🤖 开启智能表头嗅探 (勾选此项将无视下方【手动】列号)", "type": "boolean", "default": True, "span": 12},
    {"key": "c1_name", "label": "[自动] 主波长特征", "type": "string", "default": "280", "span": 4},
    {"key": "c2_name", "label": "[自动] 次波长特征", "type": "string", "default": "260", "span": 4},
    {"key": "frac_name", "label": "[自动] 收集管特征", "type": "string", "default": "Fraction", "span": 4},

    {"key": "c1x", "label": "[手动] 主波X列", "type": "number", "default": 0, "span": 3},
    {"key": "c1y", "label": "[手动] 主波Y列", "type": "number", "default": 1, "span": 3},
    {"key": "c2x", "label": "[手动] 次波X列", "type": "number", "default": 2, "span": 3},
    {"key": "c2y", "label": "[手动] 次波Y列", "type": "number", "default": 3, "span": 3},

    {"key": "show_frac", "label": "🧪 底部绘制收集管刻度", "type": "boolean", "default": True, "span": 5},
    {"key": "target_fracs", "label": "🎯 积分并高亮回收管 (例: 15-19, B2)", "type": "string", "default": "", "span": 7},

    {"key": "title", "label": "图表主标题", "type": "string", "default": "AKTA Chromatography", "span": 12},
    {"key": "xl", "label": "X 轴标签", "type": "string", "default": "Elution volume (mL)", "span": 6},
    {"key": "yl", "label": "Y 轴标签", "type": "string", "default": "Absorbance (mAU)", "span": 6},
    
    {"key": "x1", "label": "X起点(留空自动)", "type": "string", "default": "", "span": 3},
    {"key": "x2", "label": "X终点(留空自动)", "type": "string", "default": "", "span": 3},
    {"key": "y1", "label": "Y起点(留空自动)", "type": "string", "default": "", "span": 3},
    {"key": "y2", "label": "Y终点(留空自动)", "type": "string", "default": "", "span": 3},

    {"key": "xt_step", "label": "X主间隔", "type": "number", "default": 0, "span": 3},
    {"key": "xt_n", "label": "X主刻度数", "type": "number", "default": 0, "span": 3},
    {"key": "yt_step", "label": "Y主间隔", "type": "number", "default": 0, "span": 3},
    {"key": "yt_n", "label": "Y主刻度数", "type": "number", "default": 0, "span": 3},
    
    {"key": "tk_len", "label": "刻度长", "type": "number", "default": 6, "span": 4},
    {"key": "tk_dir", "label": "刻度朝向", "type": "select", "options": ["in", "out"], "default": "in", "span": 4},
    {"key": "min_n", "label": "次级分段数", "type": "number", "default": 2, "span": 4},

    {"key": "spin_w", "label": "画板宽(inch)", "type": "number", "default": 7.0, "span": 3},
    {"key": "spin_h", "label": "画板高(inch)", "type": "number", "default": 5.0, "span": 3},
    {"key": "fs", "label": "基础字号", "type": "number", "default": 12, "span": 3},
    {"key": "lw", "label": "曲线线宽", "type": "number", "default": 1.5, "span": 3},
    
    {"key": "peak", "label": "自动寻主峰", "type": "boolean", "default": True, "span": 3},
    {"key": "leg", "label": "显示图例", "type": "boolean", "default": True, "span": 3},
    {"key": "grid", "label": "显示网格", "type": "boolean", "default": False, "span": 3},
    {"key": "fmt", "label": "图表格式", "type": "select", "options": ["png", "pdf", "svg"], "default": "png", "span": 3},
    
    {"key": "b_title", "label": "加粗标题", "type": "boolean", "default": True, "span": 3},
    {"key": "b_label", "label": "加粗轴名", "type": "boolean", "default": True, "span": 3},
    {"key": "b_tick", "label": "加粗刻度", "type": "boolean", "default": False, "span": 3},
    {"key": "b_leg", "label": "加粗图例", "type": "boolean", "default": False, "span": 3},
    
    {"key": "transparent", "label": "透明背景", "type": "boolean", "default": False, "span": 12}
]

UI_LAYOUT = {
    "direction": "row",
    "blocks": [
        {"type": "form", "width": "420px", "height": "100%"},
        {"type": "tabs", "flex": "1", "height": "100%", "panes": [
            {"title": "👁️ 层析积分图", "type": "preview"},
            {"title": "🎯 核心分析指标", "type": "metrics"},
            {"title": "💻 算力引擎日志", "type": "terminal"},
            {"title": "📤 多维归档输出", "type": "export"}
        ]}
    ]
}

def parse_unicorn_text(txt_content):
    txt_content = txt_content.replace('\x00', '')
    lines = txt_content.strip().split('\n')
    raw_rows = []
    for line in lines:
        line = line.strip('\r\n').strip()
        if not line: continue
        parts = []
        if '\t' in line: parts = line.split('\t')
        elif ',' in line: parts = line.split(',')
        elif ';' in line: parts = line.split(';')
        else: parts = line.split()
        raw_rows.append([p.strip() for p in parts])
        
    if not raw_rows: return pd.DataFrame()
    def is_float(s):
        try: float(s); return True
        except: return False

    data_start_idx = 0
    for i, row in enumerate(raw_rows):
        num_c = sum(1 for x in row if is_float(x))
        if len(row) > 0 and num_c / len(row) > 0.4:
            data_start_idx = i
            break

    max_cols = max(len(r) for r in raw_rows)
    headers = [f"Col_{i}" for i in range(max_cols)]
    if data_start_idx > 0:
        header_rows = raw_rows[:data_start_idx]
        main_names = []
        curr = ""
        if len(header_rows) >= 2:
            for i in range(max_cols):
                v = header_rows[-2][i] if i < len(header_rows[-2]) else ""
                if v: curr = v
                main_names.append(curr)
        unit_row = header_rows[-1] if len(header_rows) >= 1 else []
        for i in range(max_cols):
            m = main_names[i] if main_names else f"Col_{i}"
            u = unit_row[i] if i < len(unit_row) else ""
            headers[i] = f"{m}_{u}" if u else m

    data_body = []
    for row in raw_rows[data_start_idx:]:
        r = row + [""] * (max_cols - len(row))
        data_body.append(r[:max_cols])

    return pd.DataFrame(data_body, columns=headers)

def expand_targets(target_str):
    targets = set()
    target_str = target_str.replace('"', '').replace("'", "")
    parts = [p.strip() for p in target_str.split(',')]
    for p in parts:
        if not p: continue
        if '-' in p and p.count('-') == 1:
            s, e = p.split('-')
            s, e = s.strip(), e.strip()
            if s.isdigit() and e.isdigit():
                targets.update([str(i) for i in range(int(s), int(e)+1)])
            elif len(s)>0 and len(e)>0 and s[0].isalpha() and e[0].isalpha() and s[0].upper() == e[0].upper():
                try:
                    n_s, n_e = int(s[1:]), int(e[1:])
                    targets.update([f"{s[0].upper()}{i}" for i in range(min(n_s, n_e), max(n_s, n_e)+1)])
                except: targets.add(p)
            else: targets.add(p)
        else: targets.add(p)
    return [t.upper() for t in targets]

def get_sync_workspace():
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../sciforge_config.json"))
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("data_hub_path"): return cfg.get("data_hub_path")
        except: pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../SciForge_Workspace/SciForge_Data"))

def get_akta_df(args, workspace):
    f_path = str(getattr(args, 'file_path', '')).strip()
    if not f_path: raise Exception("未选择任何文件！请先在上方选中包含层析数据的源文件。")

    in_file = os.path.join(workspace, f_path)
    if not os.path.exists(in_file): raise Exception(f"找不到文件: {in_file}")
    
    if in_file.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(in_file, header=None).apply(pd.to_numeric, errors='coerce').dropna(axis=0, how='all')
        
    for enc in ["utf-16", "utf-8-sig", "utf-8", "gbk", "latin1"]:
        try:
            with open(in_file, 'r', encoding=enc) as f:
                content = f.read()
            df = parse_unicorn_text(content)
            if not df.empty: return df
        except: continue
    raise Exception("数据清洗后未发现任何有效数字矩阵！请检查输入的层析文件。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for item in UI_SCHEMA:
        if item["type"] == "boolean": 
            parser.add_argument(f"--{item['key']}", action="store_true")
        elif item["type"] == "number": 
            parser.add_argument(f"--{item['key']}", type=float, default=item.get("default", 0.0))
        else: 
            parser.add_argument(f"--{item['key']}", type=str, default=str(item.get("default", "")))
            
    args = parser.parse_args()

    print(">>> 启动 AKTA 层析极速分析引擎...")
    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)

    try: 
        df = get_akta_df(args, workspace)
    except Exception as e: 
        print(f"❌ [Fatal] 数据摄取失败: {e}"); sys.exit(1)

    if df.empty:
        print("❌ [Fatal] 数据清洗后为空！"); sys.exit(1)

    c1x_idx, c1y_idx = int(args.c1x), int(args.c1y)
    c2x_idx, c2y_idx = int(args.c2x), int(args.c2y)
    fx_idx, fy_idx = -1, -1

    if args.auto_col:
        c1x_name, c1y_name, c2x_name, c2y_name, fx_name, fy_name = None, None, None, None, None, None
        for col in df.columns:
            cl = str(col).lower()
            if args.c1_name.lower() in cl:
                if 'ml' in cl or 'vol' in cl: c1x_name = col
                elif 'mau' in cl or 'abs' in cl or 'uv' in cl: c1y_name = col
            if args.c2_name.lower() in cl:
                if 'ml' in cl or 'vol' in cl: c2x_name = col
                elif 'mau' in cl or 'abs' in cl or 'uv' in cl: c2y_name = col
            if args.frac_name.lower() in cl:
                if 'ml' in cl or 'vol' in cl: fx_name = col
                else: fy_name = col

        if c1x_name and c1y_name: c1x_idx, c1y_idx = df.columns.get_loc(c1x_name), df.columns.get_loc(c1y_name)
        if c2x_name and c2y_name: c2x_idx, c2y_idx = df.columns.get_loc(c2x_name), df.columns.get_loc(c2y_name)
        if fx_name and fy_name: fx_idx, fy_idx = df.columns.get_loc(fx_name), df.columns.get_loc(fy_name)

    def extract_float_pair(df, idx_x, idx_y):
        if idx_x >= len(df.columns) or idx_y >= len(df.columns) or idx_x < 0 or idx_y < 0:
            return np.array([]), np.array([])
        vx = pd.to_numeric(df.iloc[:, idx_x], errors='coerce').values
        vy = pd.to_numeric(df.iloc[:, idx_y], errors='coerce').values
        valid = ~np.isnan(vx) & ~np.isnan(vy)
        return vx[valid], vy[valid]

    x1, y1 = extract_float_pair(df, c1x_idx, c1y_idx)
    x2, y2 = extract_float_pair(df, c2x_idx, c2y_idx)

    plt.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fs, lw = args.fs, args.lw
    
    fw_title = 'bold' if getattr(args, 'b_title', True) else 'normal'
    fw_label = 'bold' if getattr(args, 'b_label', True) else 'normal'
    fw_tick  = 'bold' if getattr(args, 'b_tick', False) else 'normal'
    fw_leg   = 'bold' if getattr(args, 'b_leg', False) else 'normal'

    fig = plt.figure(figsize=(args.spin_w, args.spin_h), dpi=150)
    ax = fig.add_subplot(111)

    if len(x1) > 0: ax.plot(x1, y1, color="royalblue", lw=lw, label=f"UV_{args.c1_name}", zorder=3)
    if len(x2) > 0: ax.plot(x2, y2, color="firebrick", lw=lw, label=f"UV_{args.c2_name}", zorder=2)

    f_path_str = str(getattr(args, 'file_path', '')).strip()
    base_name = os.path.splitext(os.path.basename(f_path_str))[0] if f_path_str else "AKTA_Data"
    plot_title = base_name if args.title == "AKTA Chromatography" else f"{base_name} - {args.title}"

    ax.set_title(plot_title, fontsize=fs+2, fontweight=fw_title, pad=10)
    ax.set_xlabel(args.xl, fontsize=fs, fontweight=fw_label)
    ax.set_ylabel(args.yl, fontsize=fs, fontweight=fw_label)

    if args.x1 != "": ax.set_xlim(left=float(args.x1))
    if args.x2 != "": ax.set_xlim(right=float(args.x2))
    if args.y1 != "": ax.set_ylim(bottom=float(args.y1))
    if args.y2 != "": ax.set_ylim(top=float(args.y2))

    try:
        xt_step, xt_n = float(getattr(args, 'xt_step', 0)), float(getattr(args, 'xt_n', 0))
        if xt_step > 0: ax.xaxis.set_major_locator(MultipleLocator(xt_step))
        elif xt_n > 0: ax.xaxis.set_major_locator(MaxNLocator(int(xt_n)))

        yt_step, yt_n = float(getattr(args, 'yt_step', 0)), float(getattr(args, 'yt_n', 0))
        if yt_step > 0: ax.yaxis.set_major_locator(MultipleLocator(yt_step))
        elif yt_n > 0: ax.yaxis.set_major_locator(MaxNLocator(int(yt_n)))
    except: pass

    tk_len = int(getattr(args, 'tk_len', 6))
    tk_dir = getattr(args, 'tk_dir', "in")
    min_n = int(getattr(args, 'min_n', 2))

    ax.tick_params(which='major', width=lw, length=tk_len, labelsize=fs-1, direction=tk_dir)
    ax.tick_params(which='minor', width=lw*0.7, length=tk_len*0.6, direction=tk_dir)

    if min_n > 0:
        ax.xaxis.set_minor_locator(AutoMinorLocator(min_n))
        ax.yaxis.set_minor_locator(AutoMinorLocator(min_n))
    else:
        ax.xaxis.set_minor_locator(NullLocator())
        ax.yaxis.set_minor_locator(NullLocator())

    for label in ax.get_xticklabels() + ax.get_yticklabels(): label.set_fontweight(fw_tick)
    for sp in ax.spines.values(): sp.set_linewidth(lw)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)

    if getattr(args, 'grid', False):
        ax.grid(True, which='major', ls='--', alpha=0.5)
        ax.grid(True, which='minor', ls=':', alpha=0.2)

    ymin, ymax = ax.get_ylim()
    ax.set_ylim(ymin, ymax)

    metrics_data = {}
    frac_intervals = []

    if fx_idx != -1 and fy_idx != -1:
        f_vols = pd.to_numeric(df.iloc[:, fx_idx], errors='coerce').values
        f_names_raw = df.iloc[:, fy_idx].fillna("").astype(str).values
        
        clean_names = []
        for n in f_names_raw:
            n_str = str(n).strip(' \'"').upper()
            if n_str.endswith('.0'): n_str = n_str[:-2]
            clean_names.append(n_str)
        clean_names = np.array(clean_names)

        valid_f = ~np.isnan(f_vols) & (clean_names != "")
        vols, names = f_vols[valid_f], clean_names[valid_f]

        for i in range(len(names)):
            start = vols[i]
            end = vols[i+1] if i+1 < len(vols) else vols[i] + (vols[i] - vols[i-1] if i>0 else 1.0)
            frac_intervals.append((names[i], start, end))

    if getattr(args, 'show_frac', True) and frac_intervals:
        trans = ax.get_xaxis_transform()
        for fname, start, end in frac_intervals:
            ax.plot([start, start], [0, 0.03], transform=trans, color='gray', lw=1.2, zorder=4, clip_on=False)
            ax.text(start + (end-start)/2, 0.035, fname, transform=trans, rotation=90, va='bottom', ha='center', fontsize=fs-4, color='#333333', zorder=5, clip_on=False)

    target_list = expand_targets(getattr(args, 'target_fracs', ''))
    if target_list and frac_intervals and len(x1) > 0:
        total_auc = trapz_func(np.maximum(y1, 0), x1)
        target_auc = 0.0
        highlighted_tubes = []
        
        global_mask = np.zeros_like(x1, dtype=bool)

        for fname, start, end in frac_intervals:
            if fname in target_list:
                mask = (x1 >= start) & (x1 <= end)
                if np.any(mask):
                    global_mask |= mask
                    target_auc += trapz_func(np.maximum(y1[mask], 0), x1[mask])
                    highlighted_tubes.append(fname)
        
        if highlighted_tubes:
            ax.fill_between(x1, ymin, y1, where=global_mask, color='royalblue', alpha=0.4, zorder=1, linewidth=0)
            
            if total_auc > 0:
                ratio = (target_auc / total_auc) * 100
                metrics_data["目标收集管"] = f"{len(highlighted_tubes)} 管"
                metrics_data["靶向回收积分量 (AUC)"] = f"{target_auc:.2f}"
                metrics_data["占总图谱面积比率"] = f"{ratio:.2f} %"

    if getattr(args, 'leg', True) and (len(x1)>0 or len(x2)>0):
        loc = getattr(args, 'leg_loc', 'best') 
        leg = ax.legend(frameon=False, fontsize=fs-1, bbox_to_anchor=(1.02, 1) if loc=='outside' else None, loc='upper left' if loc=='outside' else loc)
        for text in leg.get_texts(): text.set_fontweight(fw_leg)

    if getattr(args, 'peak', True) and len(y1) > 5:
        cx1, cx2 = ax.get_xlim()
        mask = (x1 >= cx1) & (x1 <= cx2)
        if np.any(mask):
            y_sm = np.convolve(y1, np.ones(5)/5, mode='same')
            sub_idx = np.where(mask)[0]
            idx = sub_idx[np.argmax(y_sm[mask])]
            px, py = x1[idx], y1[idx]
            ax.plot([px, px], [ymin, py], color='gray', ls='--', alpha=0.6, zorder=1)
            ax.text(px, py, f"{px:.2f}", fontsize=fs-2, fontweight='bold', va='bottom', ha='center')
            metrics_data["全图主峰洗脱位置 (mL)"] = f"{px:.2f}"
            if len(x2) > 0:
                try:
                    ratio_peak = np.interp(px, x2, y2) / py
                    metrics_data[f"主峰波长纯度比 ({args.c2_name}/{args.c1_name})"] = f"{ratio_peak:.3f}"
                except: pass

    fig.tight_layout()

    import uuid
    uid = uuid.uuid4().hex[:6]
    ext = getattr(args, 'fmt', 'png')
    img_path = os.path.join(temp_dir, f"Temp_AKTA_{uid}.{ext}")
    
    # --- 保存时带上透明选项 ---
    is_transparent = getattr(args, 'transparent', False)
    fig.savefig(img_path, dpi=300, bbox_inches='tight', transparent=is_transparent)

    print("\n✅ [Success] 核心推演完成，图谱与仪表盘指标已就绪！")
    print(f"[OutputFile] .cache/Temp_AKTA_{uid}.{ext}")
    if metrics_data:
        print(f"[OutputMetrics] {json.dumps(metrics_data, ensure_ascii=False)}")
        
    sys.exit(0)