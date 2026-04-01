# core/sync_worker.py
import os
import requests
from PyQt5.QtCore import QThread, pyqtSignal

class SyncWorker(QThread):
    """
    后台同步多线程工人 (策略分发 + 多领域独立同步引擎 - 流式防爆内存版)
    """
    sig_progress = pyqtSignal(int, str)  
    sig_finished = pyqtSignal(bool, str) 

    def __init__(self, server_url, username, token, targets, sync_mode):
        super().__init__()
        # 🌟 修复点 1：安全剥离末尾的斜杠，防止 URL 拼接变成 //api 导致 404
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.token = token
        self.targets = targets      # 列表结构: [{"category": "workspace", "local_dir": "..."}, ...]
        self.sync_mode = sync_mode  # "merge", "push", "pull"

    def run(self):
        try:
            total_tasks = len(self.targets)
            download_count = 0
            upload_count = 0

            # 遍历选中的独立模块进行隔离同步
            for idx, target in enumerate(self.targets):
                category = target["category"]
                local_dir = target["local_dir"]
                base_prog = int((idx / total_tasks) * 100)
                
                if not os.path.exists(local_dir):
                    os.makedirs(local_dir, exist_ok=True)

                self.sig_progress.emit(base_prog + 5, f"[{category}] 正在解析云端拓扑结构...")
                
                # ==============================
                # 第一段：获取服务器模块的专属文件列表
                # ==============================
                resp = requests.get(
                    f"{self.server_url}/api/sync/list",
                    params={"username": self.username, "token": self.token, "category": category},
                    timeout=8
                )
                if resp.status_code != 200:
                    # 🌟 修复点 2：如果服务器报错，精准捕获具体的 HTTP 错误码和后端抛出的详情透传给界面！
                    err_detail = resp.text
                    try: err_detail = resp.json().get("detail", resp.text)
                    except: pass
                    raise Exception(f"获取 {category} 列表失败 (HTTP {resp.status_code}): {err_detail}")
                    
                remote_files = resp.json().get("files", {})

                # ==============================
                # 第二段：扫描本地独立物理库
                # ==============================
                local_files = {}
                for root, dirs, files in os.walk(local_dir):
                    for f in files:
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, local_dir).replace("\\", "/")
                        stat = os.stat(full_path)
                        local_files[rel_path] = {"mtime": stat.st_mtime, "size": stat.st_size}

                # ==============================
                # 第三段：核心策略判决引擎 (Mode Engine)
                # ==============================
                to_download = []
                to_upload = []

                if self.sync_mode == "pull":
                    # ☁️ 以线上为准：下载所有线上文件，忽略本地修改
                    to_download = list(remote_files.keys())
                
                elif self.sync_mode == "push":
                    # 💻 以本地为准：强制上传所有本地文件，覆盖云端
                    to_upload = list(local_files.keys())
                
                else:
                    # 🔄 智能增量合并 (Merge)
                    for rp, r_info in remote_files.items():
                        if rp not in local_files:
                            to_download.append(rp)
                        elif r_info["mtime"] > local_files[rp]["mtime"] + 2:
                            to_download.append(rp)
                    
                    for rp, l_info in local_files.items():
                        if rp not in remote_files:
                            to_upload.append(rp)
                        elif rp in remote_files and l_info["mtime"] > remote_files[rp]["mtime"] + 2:
                            to_upload.append(rp)

                # ==============================
                # 第四段：执行网络 IO
                # ==============================
                total_io = len(to_download) + len(to_upload)
                current_io = 0

                # ⬇️ 执行下载
                for rel_path in to_download:
                    current_io += 1
                    prog = base_prog + 10 + int((current_io / (total_io or 1)) * (100 / total_tasks - 15))
                    self.sig_progress.emit(prog, f"[{category}] ⬇️ 下载: {os.path.basename(rel_path)}")
                    
                    # 🚀 开启 stream=True 进行流式挂载
                    d_resp = requests.get(
                        f"{self.server_url}/api/sync/download",
                        params={"username": self.username, "token": self.token, "category": category, "rel_path": rel_path},
                        timeout=60,
                        stream=True  
                    )
                    
                    if d_resp.status_code == 200:
                        local_path = os.path.join(local_dir, rel_path.replace("/", os.sep))
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        
                        # 🚀 引入分块落盘机制 (8KB/次)，彻底告别大文件导致的内存溢出崩溃
                        with open(local_path, "wb") as f:
                            for chunk in d_resp.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    
                        # 强制同步云端时间戳
                        remote_mtime = remote_files[rel_path]["mtime"]
                        os.utime(local_path, (remote_mtime, remote_mtime))
                        download_count += 1
                    else:
                        err_detail = d_resp.text
                        try: err_detail = d_resp.json().get("detail", d_resp.text)
                        except: pass
                        raise Exception(f"从云端下载 {rel_path} 失败 (HTTP {d_resp.status_code}): {err_detail}")

                # ⬆️ 执行上传
                for rel_path in to_upload:
                    current_io += 1
                    prog = base_prog + 10 + int((current_io / (total_io or 1)) * (100 / total_tasks - 15))
                    self.sig_progress.emit(prog, f"[{category}] ⬆️ 上传: {os.path.basename(rel_path)}")
                    
                    local_path = os.path.join(local_dir, rel_path.replace("/", os.sep))
                    with open(local_path, "rb") as f:
                        u_resp = requests.post(
                            f"{self.server_url}/api/sync/upload",
                            data={"username": self.username, "token": self.token, "category": category, "rel_path": rel_path},
                            files={"file": (os.path.basename(rel_path), f)},
                            timeout=120
                        )
                    if u_resp.status_code == 200:
                        upload_count += 1
                    else:
                        err_detail = u_resp.text
                        try: err_detail = u_resp.json().get("detail", u_resp.text)
                        except: pass
                        raise Exception(f"向云端上传 {rel_path} 被拒绝 (HTTP {u_resp.status_code}): {err_detail}")

            # ==============================
            # 收尾
            # ==============================
            self.sig_progress.emit(100, "🎉 多级路由深度同步完成！")
            report_msg = f"物理传输成功！\n\n⬇️ 共下载: {download_count} 个文件\n⬆️ 共上传: {upload_count} 个文件"
            self.sig_finished.emit(True, report_msg)

        except Exception as e:
            self.sig_finished.emit(False, str(e))