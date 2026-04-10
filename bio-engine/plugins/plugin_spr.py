# plugins/plugin_spr.py
import os
import sys
import argparse
import json
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MultipleLocator, MaxNLocator, NullLocator
import uuid

PLUGIN_NAME = "SPR 动力学批量极速拟合"
PLUGIN_ICON = "📈"
PLUGIN_DESC = "自动识别 Biacore/Octet 表头，支持一键批量导入数十个文件，并自动生成多维图表画廊与全套指标。"

UI_SCHEMA = [
    {"key": "file_path", "label": "📁 框选本地 SPR 原始数据 (.csv/.txt/.xlsx)", "type": "file", "span": 12},

    {"key": "auto_col", "label": "🤖 开启智能表头嗅探 (勾选此项将无视下方【手动】列号)", "type": "boolean", "default": True, "span": 12},
    {"key": "k_raw_x", "label": "[自动] Raw X", "type": "string", "default": "nM_X", "span": 3},
    {"key": "k_raw_y", "label": "[自动] Raw Y", "type": "string", "default": "nM_Y", "span": 3},
    {"key": "k_fit_x", "label": "[自动] Fit X", "type": "string", "default": "Fit_X", "span": 3},
    {"key": "k_fit_y", "label": "[自动] Fit Y", "type": "string", "default": "Fit_Y", "span": 3},

    {"key": "c_rx", "label": "[手动] Raw X列", "type": "number", "default": 0, "span": 3},
    {"key": "c_ry", "label": "[手动] Raw Y列", "type": "number", "default": 1, "span": 3},
    {"key": "c_fx", "label": "[手动] Fit X列", "type": "number", "default": 2, "span": 3},
    {"key": "c_fy", "label": "[手动] Fit Y列", "type": "number", "default": 3, "span": 3},

    {"key": "conc", "label": "最高浓度(M)", "type": "string", "default": "1e-7", "span": 3},
    {"key": "ton", "label": "结合点(s) [-1自动]", "type": "number", "default": -1.0, "span": 3},
    {"key": "toff", "label": "解离点(s) [-1自动]", "type": "number", "default": -1.0, "span": 3},
    {"key": "skip", "label": "跳过波动(s)", "type": "number", "default": 1.5, "span": 3},

    {"key": "title", "label": "图表主标题", "type": "string", "default": "SPR Kinetics", "span": 12},
    {"key": "xl", "label": "X 轴标签", "type": "string", "default": "Time (s)", "span": 6},
    {"key": "yl", "label": "Y 轴标签", "type": "string", "default": "Response (RU)", "span": 6},
    
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

    {"key": "craw", "label": "Raw 颜色", "type": "string", "default": "#1f77b4", "span": 3},
    {"key": "ls_raw", "label": "Raw 线型", "type": "select", "options": ["-", "--", "-.", ":"], "default": "-", "span": 3},
    {"key": "cfit", "label": "Fit 颜色", "type": "string", "default": "#d62728", "span": 3},
    {"key": "ls_fit", "label": "Fit 线型", "type": "select", "options": ["-", "--", "-.", ":"], "default": "-", "span": 3},

    {"key": "spin_w", "label": "画板宽(inch)", "type": "number", "default": 7.0, "span": 3},
    {"key": "spin_h", "label": "画板高(inch)", "type": "number", "default": 5.0, "span": 3},
    {"key": "fs", "label": "基础字号", "type": "number", "default": 12, "span": 3},
    {"key": "lw", "label": "曲线线宽", "type": "number", "default": 1.5, "span": 3},
    
    {"key": "show_txt", "label": "绘制常数", "type": "boolean", "default": True, "span": 3},
    {"key": "grid", "label": "显示网格", "type": "boolean", "default": False, "span": 3},
    {"key": "leg", "label": "显示图例", "type": "boolean", "default": True, "span": 3},
    {"key": "fmt", "label": "输出格式", "type": "select", "options": ["png", "pdf", "svg"], "default": "png", "span": 3},
    
    {"key": "b_title", "label": "加粗标题", "type": "boolean", "default": True, "span": 3},
    {"key": "b_label", "label": "加粗轴名", "type": "boolean", "default": True, "span": 3},
    {"key": "b_tick", "label": "加粗刻度", "type": "boolean", "default": False, "span": 3},
    {"key": "b_text", "label": "加粗公式", "type": "boolean", "default": False, "span": 3},
    
    {"key": "transparent", "label": "透明背景", "type": "boolean", "default": False, "span": 12}
]

UI_LAYOUT = {
    "direction": "row",
    "blocks": [
        {"type": "form", "width": "420px", "height": "100%"},
        {"type": "tabs", "flex": "1", "height": "100%", "panes": [
            {"title": "👁️ 批量传感拟合画廊", "type": "preview"},
            {"title": "🎯 核心动力学组学指标", "type": "metrics"},
            {"title": "💻 算力引擎监控", "type": "terminal"},
            {"title": "📤 自动化多维归档", "type": "export"}
        ]}
    ]
}

def parse_spr_text(txt_content, k_rx, k_ry, k_fx, k_fy):
    txt_content = txt_content.replace('\x00', '')
    lines = txt_content.strip().split('\n')
    header_idx = -1
    for i, line in enumerate(lines):
        l_lower = line.lower()
        if k_rx.lower() in l_lower or k_ry.lower() in l_lower or k_fx.lower() in l_lower or k_fy.lower() in l_lower:
            header_idx = i; break
            
    raw_rows, headers = [], []
    if header_idx != -1 and header_idx < len(lines):
        sep_line = lines[header_idx]
        if '\t' in sep_line: headers = [x.strip() for x in sep_line.split('\t')]
        elif ',' in sep_line: headers = [x.strip() for x in sep_line.split(',')]
        else: headers = [x.strip() for x in sep_line.split()]
        
        for line in lines[header_idx+1:]:
            line = line.strip('\r\n').strip()
            if not line: continue
            if '\t' in sep_line: parts = line.split('\t')
            elif ',' in sep_line: parts = line.split(',')
            else: parts = line.split()
            raw_rows.append([p.strip() for p in parts])
            
        if raw_rows:
            max_cols = max(len(headers), max(len(r) for r in raw_rows))
            if len(headers) < max_cols: headers.extend([f"Col_{i}" for i in range(len(headers), max_cols)])
            data_body = []
            for r in raw_rows:
                r_ext = r + [""] * (max_cols - len(r))
                data_body.append(r_ext[:max_cols])
            return pd.DataFrame(data_body, columns=headers)
    return pd.DataFrame()

def get_sync_workspace():
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../sciforge_config.json"))
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("data_hub_path"): return cfg.get("data_hub_path")
        except: pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../SciForge_Workspace/SciForge_Data"))

def guess_kinetics_times(t, fit):
    idx_max = np.argmax(fit)
    t_off_guess = t[idx_max]
    t_on_guess = max(0, t_off_guess - 60.0)
    mask = (t > t_off_guess - 150) & (t < t_off_guess - 10)
    if np.any(mask):
        dt = np.diff(t); dy = np.diff(fit); dt[dt==0] = 1e-9
        deriv = np.zeros_like(fit); deriv[1:] = dy/dt
        idx = np.where(mask)[0]
        if len(idx) > 0: t_on_guess = t[idx[np.argmax(deriv[idx])]]
    return t_on_guess, t_off_guess

def fit_sck_model(t, y_fit, conc, t_on, t_off, skip=1.5):
    mask_a = (t >= t_on + skip) & (t <= t_off)
    mask_d = (t >= t_off + skip)
    t_a, y_a = t[mask_a], y_fit[mask_a]
    t_d, y_d = t[mask_d], y_fit[mask_d]
    if len(t_a) < 10 or len(t_d) < 10: raise ValueError("有效数据点不足")
    
    def m_diss(t_arr, kb, R0, off): return R0 * np.exp(-kb * (t_arr - t_off)) + off
    popt_d, _ = curve_fit(m_diss, t_d, y_d, p0=[1e-3, y_d[0], 0], bounds=([1e-6, 0, -np.inf], [1.0, np.inf, np.inf]), maxfev=10000)
    kb_opt = popt_d[0]
    
    def m_assoc(t_arr, ka, Rmax, Rstart):
        kobs = ka * conc + kb_opt
        Req = (ka * conc * Rmax) / kobs
        return Req + (Rstart - Req) * np.exp(-kobs * (t_arr - t_on))
    popt_a, _ = curve_fit(m_assoc, t_a, y_a, p0=[1e5, np.max(y_a), y_a[0]], bounds=([100, np.max(y_a)*0.1, -np.inf], [1e8, np.max(y_a)*10, np.inf]), maxfev=10000)
    return popt_a[0], kb_opt, kb_opt / popt_a[0]

def get_spr_texts(ka, kb, kd, is_bold):
    def fmt(v):
        if v == 0 or np.isnan(v): return "0"
        exp = int(np.floor(np.log10(abs(v)))); c = v / (10**exp)
        return r"{0:.2f}\ \times\ 10^{{{1}}}".format(c, exp) if is_bold else r"{0:.2f} \times 10^{{{1}}}".format(c, exp)
    if is_bold:
        t1 = r"$\mathbf{k_a\ =\ " + fmt(ka) + r"\ M^{-1}s^{-1}}$" + "\n" + r"$\mathbf{k_d\ =\ " + fmt(kb) + r"\ s^{-1}}$"
        if kd == 0 or np.isnan(kd): kd_s = r"0\ M"
        elif kd < 1e-7: kd_s = f"{kd * 1e9:.2f}\\ \\mathrm{{nM}}"
        elif kd < 1e-4: kd_s = f"{kd * 1e6:.2f}\\ \\boldsymbol{{\\mu}}\\mathrm{{M}}"
        elif kd < 1e-1: kd_s = f"{kd * 1e3:.2f}\\ \\mathrm{{mM}}"
        else: kd_s = fmt(kd) + r"\ M"
        return t1, r"$\mathbf{K_D\ =\ " + kd_s + r"}$"
    else:
        t1 = r"$k_a = " + fmt(ka) + r"\ \mathrm{M^{-1}s^{-1}}$" + "\n" + r"$k_d = " + fmt(kb) + r"\ \mathrm{s^{-1}}$"
        if kd == 0 or np.isnan(kd): kd_s = r"0\ \mathrm{M}"
        elif kd < 1e-7: kd_s = f"{kd * 1e9:.2f}\\ \\mathrm{{nM}}"
        elif kd < 1e-4: kd_s = f"{kd * 1e6:.2f}\\ \\mu \\mathrm{{M}}"
        elif kd < 1e-1: kd_s = f"{kd * 1e3:.2f}\\ \\mathrm{{mM}}"
        else: kd_s = fmt(kd) + r"\ \mathrm{M}"
        return t1, r"$K_D = " + kd_s + r"$"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for item in UI_SCHEMA:
        if item["type"] == "boolean": parser.add_argument(f"--{item['key']}", action="store_true")
        elif item["type"] == "number": parser.add_argument(f"--{item['key']}", type=float, default=item.get("default", 0.0))
        else: parser.add_argument(f"--{item['key']}", type=str, default=str(item.get("default", "")))
            
    args = parser.parse_args()

    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)

    file_paths_str = str(getattr(args, 'file_path', '')).strip()
    file_list = [f.strip() for f in file_paths_str.split(',') if f.strip()]

    if not file_list:
        print("❌ [Fatal] 未选中任何文件！"); sys.exit(1)

    print(f">>> 启动 SPR 动力学极速分析引擎，检测到 {len(file_list)} 个任务！")
    metrics_data = {}

    for f_idx, f_path in enumerate(file_list):
        print(f"\n--- [Task {f_idx+1}/{len(file_list)}] 处理文件: {f_path} ---")
        base_name = os.path.splitext(os.path.basename(f_path))[0]
        
        try:
            in_file = os.path.join(workspace, f_path)
            if not os.path.exists(in_file): raise Exception("找不到文件")
            
            df = pd.DataFrame()
            if in_file.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(in_file).apply(pd.to_numeric, errors='coerce').dropna(axis=0, how='all')
            else:
                for enc in ["utf-16", "utf-8-sig", "utf-8", "gbk", "latin1"]:
                    try:
                        with open(in_file, 'r', encoding=enc, errors='ignore') as f: content = f.read()
                        df = parse_spr_text(content, args.k_raw_x, args.k_raw_y, args.k_fit_x, args.k_fit_y)
                        if not df.empty: break
                    except: continue

            if df.empty: raise Exception("智能嗅探失败，未发现包含特征关键词的数字矩阵")

            rx_idx, ry_idx = int(args.c_rx), int(args.c_ry)
            fx_idx, fy_idx = int(args.c_fx), int(args.c_fy)

            if args.auto_col:
                found_rx = found_ry = found_fx = found_fy = False
                for i, col in enumerate(df.columns):
                    c_str = str(col).strip().lower()
                    if not found_rx and args.k_raw_x.lower() in c_str: rx_idx = i; found_rx = True
                    elif not found_ry and args.k_raw_y.lower() in c_str: ry_idx = i; found_ry = True
                    elif not found_fx and args.k_fit_x.lower() in c_str: fx_idx = i; found_fx = True
                    elif not found_fy and args.k_fit_y.lower() in c_str: fy_idx = i; found_fy = True

            def extract_float_pair(d, idx_x, idx_y):
                if idx_x >= len(d.columns) or idx_y >= len(d.columns) or idx_x < 0 or idx_y < 0:
                    return np.array([]), np.array([])
                vx = pd.to_numeric(d.iloc[:, idx_x], errors='coerce').values
                vy = pd.to_numeric(d.iloc[:, idx_y], errors='coerce').values
                valid = ~np.isnan(vx) & ~np.isnan(vy)
                return vx[valid], vy[valid]

            t_raw, y_raw = extract_float_pair(df, rx_idx, ry_idx)
            t_fit, y_fit = extract_float_pair(df, fx_idx, fy_idx)
            if len(t_raw) == 0: raise Exception("未能提取到有效的 Raw 数据")

            fit_t = t_fit if len(t_fit) > 0 else t_raw
            fit_y = y_fit if len(y_fit) > 0 else y_raw

            try: conc = float(args.conc)
            except: conc = 1e-7
            
            t_on, t_off = args.ton, args.toff
            if t_on < 0 or t_off < 0: t_on, t_off = guess_kinetics_times(fit_t, fit_y)

            ka, kb, kd = 0, 0, 0
            try: 
                ka, kb, kd = fit_sck_model(fit_t, fit_y, conc, t_on, t_off, skip=args.skip)
                metrics_data[f"[{base_name}] ka"] = f"{ka:.2e} M⁻¹s⁻¹"
                metrics_data[f"[{base_name}] kd"] = f"{kb:.2e} s⁻¹"
                metrics_data[f"[{base_name}] KD"] = f"{kd:.2e} M"
            except Exception as fit_err: pass

            plt.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            fs, lw = args.fs, args.lw
            fw_title = 'bold' if getattr(args, 'b_title', True) else 'normal'
            fw_label = 'bold' if getattr(args, 'b_label', True) else 'normal'
            fw_tick  = 'bold' if getattr(args, 'b_tick', False) else 'normal'
            fw_text  = 'bold' if getattr(args, 'b_text', False) else 'normal'

            fig = plt.figure(figsize=(args.spin_w, args.spin_h), dpi=150)
            ax = fig.add_subplot(111)

            ax.plot(t_raw, y_raw, color=args.craw, lw=lw, ls=args.ls_raw, label="Raw Data", zorder=2)
            if len(t_fit) > 0: ax.plot(t_fit, y_fit, color=args.cfit, lw=lw+0.5, ls=args.ls_fit, label="Fitted Curve", zorder=3)

            if getattr(args, 'show_txt', True) and ka > 0:
                txt_1, txt_2 = get_spr_texts(ka, kb, kd, is_bold=getattr(args, 'b_text', False))
                ax.text(0.05, 0.95, txt_1, transform=ax.transAxes, fontsize=fs-1, va='top', fontweight=fw_text, zorder=4)
                ax.text(0.95, 0.05, txt_2, transform=ax.transAxes, fontsize=fs-1, va='bottom', ha='right', fontweight=fw_text, zorder=4)

            plot_title = base_name if args.title == "SPR Kinetics" else f"{base_name} - {args.title}"
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
            for sp in ax.spines.values(): sp.set_linewidth(1.5)
            ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
            if getattr(args, 'grid', False): ax.grid(True, which='major', ls='--', alpha=0.5)
            if getattr(args, 'leg', True): ax.legend(frameon=False, fontsize=fs-1, loc='best')
            fig.tight_layout()

            uid = uuid.uuid4().hex[:4]
            ext = getattr(args, 'fmt', 'png') 
            img_name = f"Out_SPR_{base_name}_{uid}.{ext}"
            csv_name = f"Out_SPR_{base_name}_{uid}.csv"
            
            img_path = os.path.join(temp_dir, img_name)
            csv_path = os.path.join(temp_dir, csv_name)
            
            # --- 保存时带上透明选项 ---
            is_transparent = getattr(args, 'transparent', False)
            fig.savefig(img_path, dpi=300, bbox_inches='tight', transparent=is_transparent)
            plt.close(fig)
            
            df_export = pd.DataFrame({"Time (s)": t_raw, "Raw Response": y_raw})
            if len(t_fit) > 0: 
                min_len = min(len(t_raw), len(t_fit))
                df_export = df_export.iloc[:min_len].copy()
                df_export["Fitted Response"] = y_fit[:min_len]

            df_export.to_csv(csv_path, index=False)

            print(f"[OutputFile] .cache/{img_name}")
            print(f"[OutputTable] .cache/{csv_name}")
            print(f"✅ {base_name} 处理成功！")
            
        except Exception as proc_err:
            print(f"❌ {base_name} 崩溃跳过: {proc_err}")

    if metrics_data:
        print(f"[OutputMetrics] {json.dumps(metrics_data, ensure_ascii=False)}")
        
    print("\n[Success] 批量分析流水线全部执行完毕！")
    sys.exit(0)