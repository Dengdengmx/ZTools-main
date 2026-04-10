# plugins/plugin_heatmap.py
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
import matplotlib.cm as cm
import uuid

try:
    from scipy.spatial.distance import pdist
    from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.patheffects
    HAS_SCI_LIBS = True
except ImportError:
    HAS_SCI_LIBS = False

PLUGIN_NAME = "BLI 热图与聚类引擎"
PLUGIN_ICON = "🔥"
PLUGIN_DESC = "读取或粘贴矩阵数据，进行层级聚类、K-Means 聚类、PCA 降维散点图及高定热图渲染。"

# ==========================================
# 前端表单 UI Schema 描述
# ==========================================
UI_SCHEMA = [
    {"key": "file_path", "label": "📁 选择本地矩阵数据 (.csv/.xlsx)", "type": "file", "span": 12},
    {"key": "raw_text", "label": "📝 粘贴文本矩阵 (包含表头侧边)", "type": "textarea", "span": 12},
    
    {"key": "mode", "label": "分析模式", "type": "select", "options": ["Heatmap (热图与层级聚类)", "K-Means (PCA降维散点图)"], "default": "Heatmap (热图与层级聚类)", "span": 6},
    {"key": "calc", "label": "数据计算", "type": "select", "options": ["自动计算: 1 - (Row / Ref)", "使用原始数据"], "default": "自动计算: 1 - (Row / Ref)", "span": 6},
    
    {"key": "ref", "label": "参比行(Ref)名称", "type": "string", "default": "PBST", "span": 4},
    {"key": "trans", "label": "转置数据", "type": "boolean", "default": True, "span": 4},
    {"key": "annot", "label": "显示数值", "type": "boolean", "default": True, "span": 4},

    {"key": "title", "label": "图表主标题", "type": "string", "default": "BLI Heatmap Analysis", "span": 12},

    {"key": "cmap", "label": "色带", "type": "select", "options": ["Default (Soft RdBu)", "RdBu_r", "viridis", "coolwarm", "magma", "Blues", "YlGnBu"], "default": "Default (Soft RdBu)", "span": 4},
    {"key": "do_cluster", "label": "执行层级聚类", "type": "boolean", "default": True, "span": 4},
    {"key": "cutoff", "label": "树状图Cutoff", "type": "number", "default": 0.4, "span": 4},

    {"key": "metric", "label": "距离度量", "type": "select", "options": ["cosine", "euclidean", "correlation"], "default": "cosine", "span": 4},
    {"key": "method", "label": "聚类方法", "type": "select", "options": ["average", "single", "complete", "ward"], "default": "average", "span": 4},
    {"key": "k", "label": "K-means K值", "type": "number", "default": 4, "span": 4},

    {"key": "auto_size", "label": "自适应画布", "type": "boolean", "default": True, "span": 4},
    {"key": "square", "label": "强制正方形", "type": "boolean", "default": False, "span": 4},
    {"key": "grid", "label": "切割网格", "type": "boolean", "default": True, "span": 4},
    
    {"key": "spin_w", "label": "画板宽(inch)", "type": "number", "default": 8.0, "span": 4},
    {"key": "spin_h", "label": "画板高(inch)", "type": "number", "default": 6.0, "span": 4},
    {"key": "ms", "label": "PCA散点大小", "type": "number", "default": 120, "span": 4},

    {"key": "fs_title", "label": "标题字号", "type": "number", "default": 14, "span": 4},
    {"key": "fs_label", "label": "轴名字号", "type": "number", "default": 12, "span": 4},
    {"key": "fs_tick", "label": "刻度字号", "type": "number", "default": 9, "span": 4},

    {"key": "b_title", "label": "加粗标题", "type": "boolean", "default": True, "span": 3},
    {"key": "b_label", "label": "加粗轴名", "type": "boolean", "default": True, "span": 3},
    {"key": "b_tick", "label": "加粗刻度", "type": "boolean", "default": True, "span": 3},
    {"key": "b_annot", "label": "加粗标注", "type": "boolean", "default": False, "span": 3},

    {"key": "fmt", "label": "输出格式", "type": "select", "options": ["png", "pdf", "svg"], "default": "png", "span": 6},
    {"key": "transparent", "label": "透明背景", "type": "boolean", "default": False, "span": 6}
]

UI_LAYOUT = {
    "direction": "row",
    "blocks": [
        {"type": "form", "width": "380px", "height": "100%"},
        {"type": "tabs", "flex": "1", "height": "100%", "panes": [
            {"title": "👁️ 聚类图表预览", "type": "preview"},
            {"title": "📊 计算指标矩阵", "type": "table"},
            {"title": "💻 算力引擎日志", "type": "terminal"},
            {"title": "📤 结果归档输出", "type": "export"}
        ]}
    ]
}

# ==========================================
# 核心算法区 (保留原生计算逻辑)
# ==========================================
def safe_read_bli_file(path):
    try:
        path_lower = str(path).lower()
        # 兼容 .csv 以及 前端粘贴文本生成的 .txt 缓存文件
        if path_lower.endswith('.csv') or path_lower.endswith('.txt'):
            # 先尝试用引擎自动嗅探分隔符（逗号或Tab）
            df = pd.read_csv(path, sep=None, engine='python', index_col=0)
            # 如果嗅探失败（比如直接从 Excel 复制出来的全是空格，导致没拆分开）
            if df.shape[1] < 1: 
                df = pd.read_csv(path, sep=r'\s+', engine='python', index_col=0)
        else:
            # 只有明确是表格时，才走 Excel 解析
            df = pd.read_excel(path, index_col=0)
            
        # 清洗数据：去掉无效表头，转为数字
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df = df.apply(pd.to_numeric, errors='coerce')
        return df
    except Exception as e:
        print(f"⚠️ 解析跳过: {path} -> {e}")
        return None

def calculate_inhibition(df, ref_name="PBST"):
    if df is None or df.empty: return None
    ref_name = str(ref_name).strip().lower()

    ref_row = None
    for idx in df.index:
        if str(idx).lower() == ref_name:
            ref_row = df.loc[idx]
            break

    if ref_row is None: return df

    ref_safe = ref_row.replace(0, 1e-9)
    ratio = df.div(ref_safe, axis=1)
    inhibition = 1.0 - ratio

    inhibition = inhibition.replace([np.inf, -np.inf], 0).fillna(0)
    inhibition = inhibition.clip(0, 1)

    cols_to_drop = [c for c in inhibition.columns if str(c).lower() == ref_name]
    if cols_to_drop: inhibition.drop(columns=cols_to_drop, inplace=True)
    rows_to_drop = [r for r in inhibition.index if str(r).lower() == ref_name]
    if rows_to_drop: inhibition.drop(index=rows_to_drop, inplace=True)

    return inhibition

def process_bli_data(df, calc_mode="inhibition", ref_name="PBST"):
    if df is None or df.empty: return None
    if "1 -" in calc_mode: df = calculate_inhibition(df, ref_name)
    df.fillna(0, inplace=True)
    df.replace([np.inf, -np.inf], 0, inplace=True)
    return df

def get_sync_workspace():
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../sciforge_config.json"))
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("data_hub_path"): return cfg.get("data_hub_path")
        except: pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../SciForge_Workspace/SciForge_Data"))

def get_heatmap_df(args, workspace):
    raw_t = str(getattr(args, 'raw_text', '')).strip()
    f_path = str(getattr(args, 'file_path', '')).strip()

    if raw_t.startswith(".cache/") and raw_t.endswith(".txt"):
        print("👉 拦截到前端内存流缓存，重定向至文件读取...")
        f_path = raw_t
        raw_t = ""

    processed_dfs = []
    
    if raw_t:
        print("👉 检测到内存文本矩阵，正在解析...")
        try:
            df = pd.read_csv(StringIO(raw_t), sep='\t', index_col=0)
            if df.shape[1] < 2: df = pd.read_csv(StringIO(raw_t), sep=r'\s+', index_col=0)
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')].apply(pd.to_numeric, errors='coerce')
            processed_dfs.append(process_bli_data(df, args.calc, args.ref))
        except Exception as e:
            raise Exception(f"粘贴数据解析失败:\n{str(e)}")
    elif f_path:
        files = [f.strip() for f in f_path.split(',') if f.strip()]
        for f in files:
            in_file = os.path.join(workspace, f)
            print(f"👉 读取底层数据流: {f}")
            df_raw = safe_read_bli_file(in_file)
            if df_raw is not None:
                processed_dfs.append(process_bli_data(df_raw, args.calc, args.ref))

    if not processed_dfs:
        raise Exception("未能提取出有效数据！请检查输入格式。")

    final_df = pd.DataFrame()
    global_idx_counts = {}
    for df in processed_dfs:
        if df is None or df.empty: continue
        new_indices = []
        for idx in df.index:
            s_idx = str(idx)
            if s_idx not in global_idx_counts:
                global_idx_counts[s_idx] = 1; new_indices.append(s_idx)
            else:
                global_idx_counts[s_idx] += 1; new_indices.append(f"{s_idx}_{global_idx_counts[s_idx]}")
        df.index = new_indices
        final_df = df if final_df.empty else pd.concat([final_df, df], axis=0, join='outer')
        
    final_df.fillna(0, inplace=True)
    if args.trans: final_df = final_df.T
    return final_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for item in UI_SCHEMA:
        if item["type"] == "boolean": parser.add_argument(f"--{item['key']}", action="store_true")
        elif item["type"] == "number": parser.add_argument(f"--{item['key']}", type=float, default=item.get("default", 0.0))
        else: parser.add_argument(f"--{item['key']}", type=str, default=str(item.get("default", "")))
            
    args = parser.parse_args()

    print(">>> 启动 BLI 热图与聚类引擎...")
    if not HAS_SCI_LIBS:
        print("❌ [Fatal] 当前环境缺少 scipy / sklearn 库，无法进行聚类计算！请先 pip install scipy scikit-learn"); sys.exit(1)

    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)

    try: 
        df = get_heatmap_df(args, workspace)
    except Exception as e: 
        print(f"❌ [Fatal] 数据读取异常: {e}"); sys.exit(1)

    export_df = df.copy()
    metrics_data = {
        "分析模式": args.mode,
        "矩阵维度": f"{df.shape[0]} 行 x {df.shape[1]} 列",
        "参比行归一化": "已应用" if "1 -" in args.calc else "未应用"
    }

    plt.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    fw_title = 'bold' if args.b_title else 'normal'
    fw_label = 'bold' if args.b_label else 'normal'
    fw_tick  = 'bold' if args.b_tick else 'normal'
    fw_annot = 'bold' if args.b_annot else 'normal'
    is_inhib = "1 -" in args.calc

    w, h = args.spin_w, args.spin_h
    if args.auto_size:
        cell_size = 0.55 if args.square else 0.45
        w = max(5.0, df.shape[1] * cell_size + 3.0)
        h = max(4.0, df.shape[0] * cell_size + 2.0)

    fig = plt.figure(figsize=(w, h), dpi=150)
    ax = fig.add_subplot(111)

    # ================== 智能标题渲染逻辑 ==================
    f_path_str = str(getattr(args, 'file_path', '')).strip()
    raw_t_str = str(getattr(args, 'raw_text', '')).strip()

    if f_path_str and not raw_t_str.startswith(".cache/"):
        # 取第一个文件的文件名
        first_file = f_path_str.split(',')[0].strip()
        base_name = os.path.splitext(os.path.basename(first_file))[0]
        plot_title = base_name if args.title == "BLI Heatmap Analysis" else f"{base_name} - {args.title}"
    else:
        plot_title = args.title

    # ================== Heatmap 模式 ==================
    if "Heatmap" in args.mode:
        do_cluster = args.do_cluster
        divider = make_axes_locatable(ax)

        if do_cluster and df.shape[1] >= 2:
            print(f"执行层级聚类... (Metric: {args.metric}, Method: {args.method})")
            dist = np.nan_to_num(pdist(df.T + 1e-9, metric=args.metric))
            Z = linkage(dist, method=args.method)

            cutoff_val = float(args.cutoff)
            color_threshold = cutoff_val * max(Z[:, 2]) if len(Z) > 0 else 0

            ax_cbar_cluster = divider.append_axes("top", size="4%", pad=0.01)
            ax_tree = divider.append_axes("top", size="15%", pad=0.0)

            dendro = dendrogram(Z, ax=ax_tree, no_labels=True, color_threshold=color_threshold, above_threshold_color='#555555')
            ax_tree.axis('off')

            leaves_order = dendro['leaves']
            df_plot = df.iloc[:, leaves_order]

            clusters = fcluster(Z, t=color_threshold, criterion='distance')
            clusters_ordered = clusters[leaves_order]
            try: cmap_cluster = matplotlib.colormaps["tab10"]
            except: cmap_cluster = cm.get_cmap("tab10")
            ax_cbar_cluster.imshow([clusters_ordered], aspect='auto', cmap=cmap_cluster, interpolation='nearest')
            ax_cbar_cluster.axis('off')
            
            unique_clusters = len(np.unique(clusters))
            metrics_data["聚类簇数"] = f"{unique_clusters} 组 (Cutoff: {cutoff_val})"
            
            # 给最顶部的 Dendrogram 加上主标题
            ax_tree.set_title(plot_title, fontsize=args.fs_title, fontweight=fw_title, pad=10)
        else:
            df_plot = df
            ax.set_title(plot_title, fontsize=args.fs_title, fontweight=fw_title, pad=10)

        cmap_sel = args.cmap
        if cmap_sel == "Default (Soft RdBu)":
            colors = ["#63aaff", "#ffffff", "#ff6b6b"]
            cmap = LinearSegmentedColormap.from_list("soft_rdbu", colors)
        else: 
            cmap = cmap_sel

        aspect_val = 'equal' if args.square else 'auto'
        im = ax.imshow(df_plot, aspect=aspect_val, cmap=cmap, interpolation='nearest')

        if args.annot:
            for i in range(len(df_plot.index)):
                for j in range(len(df_plot.columns)):
                    val = df_plot.iloc[i, j]
                    txt_val = f"{val * 100:.0f}" if is_inhib else f"{val:.1f}"
                    ax.text(j, i, txt_val, ha="center", va="center", color="black", fontsize=args.fs_tick, fontweight=fw_annot, path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground="white")])

        ax.set_xticks(range(len(df_plot.columns)))
        ax.set_yticks(range(len(df_plot.index)))
        ax.set_xticklabels(df_plot.columns, rotation=90, fontsize=args.fs_tick, fontweight=fw_tick)
        ax.set_yticklabels(df_plot.index, fontsize=args.fs_tick, fontweight=fw_tick)

        if args.grid:
            ax.set_xticks(np.arange(df_plot.shape[1] + 1) - 0.5, minor=True)
            ax.set_yticks(np.arange(df_plot.shape[0] + 1) - 0.5, minor=True)
            ax.grid(which="minor", color="white", linestyle='-', linewidth=2)
            ax.tick_params(which="minor", bottom=False, left=False)

        cbar = plt.colorbar(im, cax=divider.append_axes("right", size="3%", pad=0.1))
        cbar_label = "Inhibition Rate" if is_inhib else "Value"
        cbar.set_label(cbar_label, fontsize=args.fs_label, fontweight=fw_label, labelpad=10)

    # ================== K-Means 模式 ==================
    else:
        k = int(args.k)
        if len(df) < k:
            print(f"❌ [Fatal] 数据样本量({len(df)})小于设定的 K 值({k})！"); sys.exit(1)
            
        print(f"执行 K-Means 聚类降维 (K={k})...")
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(df)
        coords = PCA(n_components=2).fit_transform(df)

        export_df['K-Means Cluster'] = clusters
        export_df['PCA_Dim1'] = coords[:, 0]
        export_df['PCA_Dim2'] = coords[:, 1]
        
        metrics_data["聚类中心 (K)"] = f"{k} 个"

        try: cmap_km = matplotlib.colormaps["tab10"]
        except: cmap_km = cm.get_cmap("tab10")

        ax.scatter(coords[:, 0], coords[:, 1], c=clusters, cmap=cmap_km, s=args.ms, edgecolors='white', alpha=0.9)
        for i, txt in enumerate(df.index):
            ax.annotate(txt, (coords[i, 0], coords[i, 1]), xytext=(6, 6), textcoords='offset points', fontsize=args.fs_tick, fontweight=fw_annot)

        ax.set_title(plot_title, fontweight=fw_title, fontsize=args.fs_title, pad=10)
        if args.grid: ax.grid(True, ls='--', alpha=0.5)

    fig.tight_layout()

    import uuid
    uid = uuid.uuid4().hex[:6]
    
    ext = args.fmt 
    img_path = os.path.join(temp_dir, f"Temp_Heatmap_{uid}.{ext}")
    csv_path = os.path.join(temp_dir, f"Temp_Heatmap_{uid}.csv")
    
    # --- 保存时带上透明选项 ---
    fig.savefig(img_path, dpi=300, bbox_inches='tight', transparent=args.transparent)
    
    # 导出计算后的数据到 csv
    export_df.to_csv(csv_path)

    print(f"[OutputFile] .cache/Temp_Heatmap_{uid}.{ext}")
    print(f"[OutputTable] .cache/Temp_Heatmap_{uid}.csv")
    print(f"[OutputMetrics] {json.dumps(metrics_data, ensure_ascii=False)}")
    print("\n✅ [Success] 核心推演完成，图谱与仪表盘指标已就绪！")
    sys.exit(0)