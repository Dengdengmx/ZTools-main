# plugins/plugin_elisa.py
import os
import sys
import argparse
import pandas as pd
import numpy as np
from io import StringIO
from scipy.optimize import curve_fit
import json
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt

PLUGIN_NAME = "ELISA 4PL 极速拟合"
PLUGIN_ICON = "📉"
PLUGIN_DESC = "读取或粘贴孔板数据，进行四参数逻辑斯蒂拟合、EC50 计算与高定图表渲染。"

UI_SCHEMA = [
    {"key": "file_path", "label": "📁 选择本地源文件 (.csv/.xlsx)", "type": "file", "span": 12},
    {"key": "raw_text", "label": "📝 粘贴孔板数据 (Excel直接复制)", "type": "textarea", "span": 12},
    
    {"key": "start", "label": "起始浓度", "type": "number", "default": 1000.0, "span": 4},
    {"key": "dil", "label": "稀释倍数", "type": "number", "default": 3.0, "span": 4},
    {"key": "unit", "label": "浓度单位", "type": "string", "default": "ng/mL", "span": 4},
    
    {"key": "merge", "label": "合并多板数据", "type": "boolean", "default": True, "span": 6},
    {"key": "log", "label": "X轴使用Log坐标", "type": "boolean", "default": True, "span": 6},
    
    {"key": "title", "label": "图表主标题", "type": "string", "default": "ELISA 4PL Fit", "span": 12},
    {"key": "xl", "label": "X 轴标签", "type": "string", "default": "Concentration", "span": 6},
    {"key": "yl", "label": "Y 轴标签", "type": "string", "default": "OD450", "span": 6},
    
    {"key": "spin_w", "label": "画板宽(inch)", "type": "number", "default": 7.0, "span": 4},
    {"key": "spin_h", "label": "画板高(inch)", "type": "number", "default": 5.0, "span": 4},
    {"key": "fs", "label": "基础字号", "type": "number", "default": 12, "span": 4},
    
    {"key": "ms", "label": "散点大小", "type": "number", "default": 30, "span": 6},
    {"key": "lw", "label": "拟合线宽", "type": "number", "default": 2.0, "span": 6},
    
    {"key": "ec50", "label": "标注 EC50", "type": "boolean", "default": True, "span": 4},
    {"key": "grid", "label": "显示网格", "type": "boolean", "default": False, "span": 4},
    {"key": "diff", "label": "区分形状", "type": "boolean", "default": True, "span": 4},
    
    {"key": "leg", "label": "显示图例", "type": "boolean", "default": True, "span": 3},
    {"key": "leg_loc", "label": "图例位置", "type": "select", "options": ["best", "upper right", "upper left", "lower right", "lower left", "outside"], "default": "best", "span": 5},
    {"key": "fmt", "label": "输出格式", "type": "select", "options": ["png", "pdf", "svg"], "default": "png", "span": 4},
    
    {"key": "b_title", "label": "加粗标题", "type": "boolean", "default": True, "span": 3},
    {"key": "b_label", "label": "加粗轴名", "type": "boolean", "default": True, "span": 3},
    {"key": "b_tick", "label": "加粗刻度", "type": "boolean", "default": False, "span": 3},
    {"key": "b_leg", "label": "加粗图例", "type": "boolean", "default": False, "span": 3},
    
    {"key": "transparent", "label": "透明背景", "type": "boolean", "default": False, "span": 12}
]

UI_LAYOUT = {
    "direction": "row",
    "blocks": [
        {"type": "form", "width": "380px", "height": "100%"},
        {"type": "tabs", "flex": "1", "height": "100%", "panes": [
            {"title": "👁️ 4PL 拟合图表", "type": "preview"},
            {"title": "📊 EC50 数据表", "type": "table"},
            {"title": "💻 算力引擎日志", "type": "terminal"},
            {"title": "📤 结果归档输出", "type": "export"}
        ]}
    ]
}

def fourPL(x, A, B, C, D): 
    return D + (A - D) / (1 + (x / (C + 1e-10))**B)

def r_squared(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    return 1 - (ss_res / ss_tot)

def scan_for_plate_blocks(df_raw):
    valid_blocks = []
    rows, cols = df_raw.shape
    if rows >= 8:
        for c in range(cols):
            col_data = df_raw.iloc[:, c].astype(str).str.strip().str.upper().values
            for r in range(rows - 7):
                if col_data[r] == 'A' and all(col_data[r+1+i]==char for i,char in enumerate(['B','C','D','E','F','G','H'])):
                    if r > 0:
                        end_col = min(c + 13, cols)
                        block = df_raw.iloc[r:r+8, c+1:end_col].copy()
                        block.columns = df_raw.iloc[r-1, c+1:end_col].values
                        block = block.apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='any')
                        if not block.empty: valid_blocks.append(block)
    
    if not valid_blocks:
        df_num = df_raw.apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='all').dropna(axis=0, how='all')
        if not df_num.empty:
            df_num.columns = [f"Sample_{i+1}" for i in range(df_num.shape[1])]
            valid_blocks.append(df_num)
            print(f"👉 成功触发兜底矩阵提取机制: 获取了 {df_num.shape[0]}行 x {df_num.shape[1]}列 纯数字阵列。")
    return valid_blocks

def parse_text_to_df(txt_content):
    lines = txt_content.strip().split('\n')
    data = []
    max_cols = 0
    for line in lines:
        line = line.strip('\r\n').strip()
        if not line: continue
        parts = []
        if '\t' in line: parts = line.split('\t')
        elif ',' in line: parts = line.split(',')
        else: parts = line.split()
        data.append(parts)
        max_cols = max(max_cols, len(parts))
    
    for row in data:
        if len(row) < max_cols:
            row.extend([np.nan] * (max_cols - len(row)))
            
    return pd.DataFrame(data)

def get_sync_workspace():
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../sciforge_config.json"))
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("data_hub_path"): return cfg.get("data_hub_path")
        except: pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../SciForge_Workspace/SciForge_Data"))


def get_elisa_df(args, workspace):
    raw_t = str(getattr(args, 'raw_text', '')).strip()
    f_path = str(getattr(args, 'file_path', '')).strip()

    if raw_t.startswith(".cache/") and raw_t.endswith(".txt"):
        print("👉 拦截到前端内存流缓存，重定向至文件读取...")
        f_path = raw_t
        raw_t = ""

    if raw_t:
        print("👉 检测到内存文本矩阵，正在解析...")
        return parse_text_to_df(raw_t)

    if f_path:
        in_file = os.path.join(workspace, f_path)
        print(f"👉 读取底层数据流: {f_path}")
        if not os.path.exists(in_file): raise Exception(f"找不到文件: {in_file}")
        if in_file.lower().endswith(('.xlsx', '.xls')): return pd.read_excel(in_file, header=None)
        for enc in ["utf-8-sig", "utf-8", "gbk", "latin1"]:
            try:
                with open(in_file, 'r', encoding=enc, errors='ignore') as f:
                    content = f.read()
                return parse_text_to_df(content)
            except: continue
        raise Exception("未知的文件数据格式")
        
    raise Exception("没有提供任何数据！请粘贴文本或选择文件。")


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

    print(">>> 启动 ELISA 4PL 极速拟合...")
    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)

    try: 
        df_raw = get_elisa_df(args, workspace)
    except Exception as e: 
        print(f"❌ [Fatal] 数据读取异常: {e}"); sys.exit(1)

    blocks = scan_for_plate_blocks(df_raw)
    if not blocks: 
        print("❌ [Fatal] 矩阵中没有任何有效的纯数字数据块！请检查粘贴的数据格式。"); sys.exit(1)

    df_data = pd.concat(blocks, axis=1) if args.merge else blocks[-1]
    x_arr = np.array([args.start / (args.dil ** i) for i in range(len(df_data))])

    plt.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    fs = args.fs
    fw_title = 'bold' if args.b_title else 'normal'
    fw_label = 'bold' if args.b_label else 'normal'
    fw_tick  = 'bold' if args.b_tick else 'normal'
    fw_leg   = 'bold' if args.b_leg else 'normal'

    fig = plt.figure(figsize=(args.spin_w, args.spin_h), dpi=150)
    ax = fig.add_subplot(111)

    cmap = plt.get_cmap('tab10')
    markers = ['o','s','^','v','D','p']
    results_list = []

    print(f"开始并行拟合 {len(df_data.columns)} 个靶点...")

    for i, col_name in enumerate(df_data.columns):
        y_raw = df_data.iloc[:, i].values
        curr_x = x_arr[:len(y_raw)] if len(y_raw)<len(x_arr) else x_arr
        mask = ~np.isnan(y_raw[:len(curr_x)])
        x_fit, y_fit = curr_x[mask], y_raw[:len(curr_x)][mask]

        if len(x_fit) == 0:
            continue

        c, m = cmap(i%10), markers[i%len(markers)] if args.diff else 'o'
        ax.scatter(x_fit, y_fit, color=c, marker=m, s=args.ms, edgecolors='white', zorder=3)
        lbl = str(col_name)

        if len(x_fit) >= 4:
            try:
                p0 = [min(y_fit), 1.0, np.median(x_fit), max(y_fit)]
                params, _ = curve_fit(fourPL, x_fit, y_fit, p0=p0, maxfev=5000)
                x_sm = np.logspace(np.log10(min(x_fit)/2), np.log10(max(x_fit)*2), 100) if args.log else np.linspace(0, max(x_fit)*1.1, 100)
                if args.ec50: lbl += f" (EC50={params[2]:.2f})"
                ax.plot(x_sm, fourPL(x_sm, *params), color=c, lw=args.lw, label=lbl, zorder=2)
                r2 = r_squared(y_fit, fourPL(x_fit, *params))
                results_list.append({"Sample": col_name, "EC50": round(params[2], 3), "R2": round(r2, 4), "Status": "Success"})
                print(f"✅ {col_name}: 拟合成功 (EC50 = {params[2]:.2f})")
            except Exception as fit_err:
                ax.plot(x_fit, y_fit, color=c, ls='--', lw=1, label=lbl+" (Fail)")
                results_list.append({"Sample": col_name, "EC50": "-", "R2": "-", "Status": "Fail"})
                print(f"⚠️ {col_name}: 拟合未收敛")
        else:
            results_list.append({"Sample": col_name, "EC50": "-", "R2": "-", "Status": "Skip"})

    f_path_str = str(getattr(args, 'file_path', '')).strip()
    raw_t_str = str(getattr(args, 'raw_text', '')).strip()

    if f_path_str and not raw_t_str.startswith(".cache/"):
        base_name = os.path.splitext(os.path.basename(f_path_str))[0]
        plot_title = base_name if args.title == "ELISA 4PL Fit" else f"{base_name} - {args.title}"
    else:
        plot_title = args.title

    ax.set_title(plot_title, fontsize=fs+2, fontweight=fw_title, pad=10)

    xlabel_full = f"{args.xl} ({args.unit})" if args.unit else args.xl
    ax.set_xlabel(xlabel_full, fontsize=fs, fontweight=fw_label)
    ax.set_ylabel(args.yl, fontsize=fs, fontweight=fw_label)
    
    if args.log: ax.set_xscale('log')
    
    ax.tick_params(which='both', direction='in', top=False, right=False, labelsize=fs-2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for sp in ax.spines.values(): sp.set_linewidth(1.2)
    for label in ax.get_xticklabels() + ax.get_yticklabels(): label.set_fontweight(fw_tick)

    if args.grid:
        ax.grid(True, which='major', ls='--', alpha=0.5)
        if args.log: ax.grid(True, which='minor', ls=':', alpha=0.2)

    if args.leg and len(results_list) > 0:
        loc = args.leg_loc
        if loc == 'outside':
            leg = ax.legend(frameon=False, fontsize=fs-2, bbox_to_anchor=(1.02, 1), loc='upper left')
        else:
            leg = ax.legend(frameon=False, fontsize=fs-2, loc=loc)
        for text in leg.get_texts(): text.set_fontweight(fw_leg)

    fig.tight_layout()

    import uuid
    uid = uuid.uuid4().hex[:6]
    
    ext = args.fmt 
    img_path = os.path.join(temp_dir, f"Temp_ELISA_{uid}.{ext}")
    csv_path = os.path.join(temp_dir, f"Temp_ELISA_{uid}.csv")
    
    # --- 保存时带上透明选项 ---
    is_transparent = getattr(args, 'transparent', False)
    fig.savefig(img_path, dpi=300, bbox_inches='tight', transparent=is_transparent)
    
    pd.DataFrame(results_list).to_csv(csv_path, index=False)

    print(f"[OutputFile] .cache/Temp_ELISA_{uid}.{ext}")
    print(f"[OutputTable] .cache/Temp_ELISA_{uid}.csv")
    sys.exit(0)