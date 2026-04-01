# controllers/ctrl_data_hub.py
"""
SciForge 数据中心底层控制器 (策略模式与异步防错优化版)
使用 Strategy 模式解耦各种格式的解析逻辑，提供统一的预览引擎输出。
"""

import os
import time
import platform
import subprocess
import html

class PreviewResult:
    """标准化的预览数据返回包"""
    def __init__(self, p_type, content, meta_info=""):
        self.p_type = p_type       # 'html', 'image', 'table'
        self.content = content     # HTML文本 或 DataFrame
        self.meta_info = meta_info # 附加给 UI 详情标签的文本

# ==========================================
# 🌟 预览策略矩阵 (Strategy Pattern)
# ==========================================
class BasePreviewStrategy:
    def preview(self, file_path: str, ext: str) -> PreviewResult:
        raise NotImplementedError

class DirPreviewStrategy(BasePreviewStrategy):
    def preview(self, dir_path: str, ext: str):
        try:
            fc, dc, ts = 0, 0, 0
            with os.scandir(dir_path) as it:
                for e in it:
                    if e.is_file(): fc += 1; ts += e.stat().st_size
                    elif e.is_dir(): dc += 1
            html_content = (f"<div style='text-align:center; font-family:sans-serif; color:#333;'><div style='font-size:50px;'>📁</div>"
                            f"<h2 style='color:#0078D7; margin-top:0;'>物理目录信息</h2>"
                            f"<p><b>子目录:</b> {dc} 个 | <b>文件:</b> {fc} 个 | <b>占用:</b> {ts/(1024*1024):.2f} MB</p></div>")
            return PreviewResult('html', html_content)
        except Exception as e:
            return PreviewResult('html', f"<div style='color:red;'>无法读取目录: {e}</div>")

class ImagePreviewStrategy(BasePreviewStrategy):
    def preview(self, file_path: str, ext: str):
        return PreviewResult('image', file_path) # UI层直接利用路径去加载

class TablePreviewStrategy(BasePreviewStrategy):
    def preview(self, file_path: str, ext: str):
        try:
            import pandas as pd
            # ✅ 核心修复：使用二进制流避开 Windows 底层 C 引擎读取中文路径失败的致命 Bug
            with open(file_path, 'rb') as f:
                if ext == '.csv':
                    try:
                        df = pd.read_csv(f)
                    except UnicodeDecodeError:
                        f.seek(0) # 如果 UTF-8 失败，指针归零，换国内常见 GBK 编码强读
                        df = pd.read_csv(f, encoding='gbk')
                else:
                    df = pd.read_excel(f)
                    
            if df.shape[0] > 500:
                meta = f" | ⚠️ 预览截断: 行数({df.shape[0]})过多，仅显示前500行"
                df = df.head(500)
            else:
                meta = f" | 矩阵规模: {df.shape[0]}行 × {df.shape[1]}列"
            return PreviewResult('table', df, meta)
        except ImportError:
            return PreviewResult('html', "<div style='padding:20px; color:red;'>请安装 pandas 与 openpyxl/xlrd 引擎。</div>")
        except Exception as e:
            return PreviewResult('html', f"<div style='color:red; padding:20px;'>表格解析失败: {e}</div>")

class MrcPreviewStrategy(BasePreviewStrategy):
    def preview(self, file_path: str, ext: str):
        try:
            import struct
            with open(file_path, 'rb') as f:
                header = f.read(1024)
                nx, ny, nz, mode = struct.unpack('<4i', header[:16])
                m_map = {0: "8-bit signed", 1: "16-bit signed", 2: "32-bit float"}
                html_c = (f"<div style='padding:20px; font-family:sans-serif;'>"
                          f"<h3 style='color:#107C10;'>🔬 冷冻电镜密度图</h3>"
                          f"<div style='background:#F3F9F4; padding:15px; border-radius:8px;'>"
                          f"<b>体素矩阵:</b> {nx} × {ny} × {nz}<br><b>编码:</b> {m_map.get(mode, mode)}</div></div>")
                return PreviewResult('html', html_c)
        except Exception as e:
            return PreviewResult('html', f"<div style='color:red; padding:20px;'>MRC失败: {e}</div>")

class TextPreviewStrategy(BasePreviewStrategy):
    def preview(self, file_path: str, ext: str):
        try:
            if os.stat(file_path).st_size > 5 * 1024 * 1024:
                return PreviewResult('html', "<div style='padding:20px;'>文本体积超 5MB，为防止内存溢出已拒绝预览。</div>")
            
            # ✅ 核心修复：兼容 GBK 编码，防止国标中文 txt 解析崩溃
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = html.escape(f.read(10000))
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = html.escape(f.read(10000))
                    
            html_c = f"<div style='padding:20px;'><h3 style='color:#555;'>📄 纯文本内容</h3><div style='background:#f4f4f4; padding:15px; font-family:Consolas; white-space:pre-wrap;'>{content}</div></div>"
            return PreviewResult('html', html_c)
        except Exception as e:
            return PreviewResult('html', f"<div style='padding:20px; color:red;'>读取失败: {e}</div>")

class DefaultPreviewStrategy(BasePreviewStrategy):
    def preview(self, file_path: str, ext: str):
        return PreviewResult('html', f"<div style='padding:20px; color:#666;'>不支持该格式 ({ext}) 的直接内嵌预览，请右键使用系统程序打开。</div>")

# ==========================================
# 🚀 智能引擎路由
# ==========================================
class PreviewEngine:
    def __init__(self):
        self.strategies = {}
        self._register_defaults()

    def _register(self, exts, strategy):
        for ext in exts: self.strategies[ext] = strategy

    def _register_defaults(self):
        self._register(['.png', '.jpg', '.jpeg', '.tif', '.gif', '.bmp', '.svg'], ImagePreviewStrategy())
        self._register(['.csv', '.xlsx', '.xls'], TablePreviewStrategy())
        self._register(['.mrc', '.map'], MrcPreviewStrategy())
        self._register(['.txt', '.md', '.json', '.py', '.pdb', '.cif', '.fasta'], TextPreviewStrategy())

    def execute(self, file_path: str) -> PreviewResult:
        if os.path.isdir(file_path):
            return DirPreviewStrategy().preview(file_path, "")
        ext = os.path.splitext(file_path)[1].lower()
        strategy = self.strategies.get(ext, DefaultPreviewStrategy())
        return strategy.preview(file_path, ext)


class DataHubLogic:
    def __init__(self):
        self.preview_engine = PreviewEngine()

    def get_file_meta(self, file_path):
        if not os.path.exists(file_path): return 0, "文件丢失"
        try:
            stats = os.stat(file_path)
            return stats.st_size / 1024, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats.st_mtime))
        except OSError: return 0, "拒绝访问"

    def open_in_explorer(self, file_path):
        if platform.system() == "Windows": subprocess.Popen(f'explorer /select,"{os.path.normpath(file_path)}"')
    def open_system_default(self, file_path):
        if platform.system() == "Windows": os.startfile(file_path)
    def rename_file(self, old_path, new_name):
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        os.rename(old_path, new_path); return True, new_path
    def delete_file(self, file_path):
        if os.path.isdir(file_path): import shutil; shutil.rmtree(file_path)
        else: os.remove(file_path)
        return True, ""
    def move_files(self, filepaths, target_dir):
        import shutil
        for src in filepaths: shutil.move(src, os.path.join(target_dir, os.path.basename(src)))
        return True, "转移成功"