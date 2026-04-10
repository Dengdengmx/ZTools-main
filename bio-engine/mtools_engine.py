import asyncio
import os
import sys
import subprocess
import datetime
import json
import shutil
import importlib.util
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, List, Union
import uvicorn

# 🚨 导入 SciForge 真正的原生核心控制器
from controllers.ctrl_calendar_archive import CalendarArchiveLogic
from controllers.ctrl_data_hub import DataHubLogic
from controllers.ctrl_sample_hub import SampleHubLogic

app = FastAPI(title="SciForge 2.0 Global Hub")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

print("正在挂载 SciForge 2.0 核心物理控制器...")
eln_logic = CalendarArchiveLogic()
sample_logic = SampleHubLogic()
data_logic = DataHubLogic()
print("挂载完成，物理宇宙已建立！")

# ==========================================
# ⚙️ 全局配置管理 (动态物理挂载点)
# ==========================================
CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "sciforge_config.json"))

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"data_hub_path": os.path.abspath(os.path.join(os.path.dirname(__file__), "SciForge_Workspace", "SciForge_Data"))}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

config_store = load_config()

def get_base_dir():
    path = config_store.get("data_hub_path", "")
    if not path:
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "SciForge_Workspace", "SciForge_Data"))
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, "00_Inbox"), exist_ok=True)
    return path

@app.get("/api/utils/pick_folder")
async def pick_folder():
    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) 
        folder_path = filedialog.askdirectory(title="请选择新的数据存放根目录 (DataHub Mount Point)")
        root.destroy()
        return folder_path
    try:
        path = await run_in_threadpool(open_dialog)
        if path: return {"code": 200, "data": path}
        return {"code": 400, "message": "用户取消了选择"}
    except Exception as e:
        return {"code": 500, "message": f"无法唤起系统选择器: {str(e)}"}

@app.get("/api/config")
async def get_system_config():
    return {"code": 200, "data": {"data_hub_path": get_base_dir()}}

@app.post("/api/config/update")
async def update_system_config(request: Request):
    try:
        payload = await request.json()
        new_path = payload.get("data_hub_path")
        migrate_data = payload.get("migrate_data", False)
        
        if not new_path: return {"code": 400, "message": "路径不能为空"}
        old_path = get_base_dir()
        new_path = os.path.abspath(new_path)
        
        if migrate_data and os.path.exists(old_path) and old_path != new_path:
            def migrate():
                shutil.copytree(old_path, new_path, dirs_exist_ok=True)
            await run_in_threadpool(migrate)

        os.makedirs(new_path, exist_ok=True)
        config_store["data_hub_path"] = new_path
        save_config(config_store)
        os.makedirs(os.path.join(new_path, "00_Inbox"), exist_ok=True)
            
        return {"code": 200, "message": "物理挂载点转移成功"}
    except Exception as e:
        return {"code": 500, "message": f"迁移或挂载失败: {str(e)}"}

# ==========================================
# 🏷️ 数据中心全局标签系统 (Meta Dictionary)
# ==========================================
def get_data_meta_path():
    return os.path.join(get_base_dir(), ".sciforge_data_meta.json")

def load_data_meta():
    meta_path = get_data_meta_path()
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {
        "tags": {
            "projects": [
                {"id": "p_alpha", "label": "🧬 Alpha (靶点筛选)", "color": "#f9e2af"},
                {"id": "p_beta", "label": "🧪 Beta (蛋白设计)", "color": "#89b4fa"}
            ],
            "experiments": [
                {"id": "e_pcr", "label": "🧬 PCR 扩增", "color": "#a6e3a1"},
                {"id": "e_puri", "label": "🧪 蛋白纯化", "color": "#cba6f7"}
            ],
            "others": []
        },
        "file_tags": {}
    }

def save_data_meta(meta_data):
    with open(get_data_meta_path(), "w", encoding="utf-8") as f:
        json.dump(meta_data, f, ensure_ascii=False, indent=2)

@app.get("/api/data/meta")
async def get_data_metadata():
    return {"code": 200, "data": load_data_meta()}

@app.post("/api/data/meta/tag/add")
async def add_meta_tag(request: Request):
    try:
        payload = await request.json()
        category = payload.get("category", "others")
        label = payload.get("label", "新标签").strip()
        color = payload.get("color", "#89b4fa")
        import uuid
        tag_id = f"t_{uuid.uuid4().hex[:6]}"
        meta = load_data_meta()
        if category not in meta["tags"]: meta["tags"][category] = []
        meta["tags"][category].append({"id": tag_id, "label": label, "color": color})
        save_data_meta(meta)
        return {"code": 200, "data": meta}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/data/meta/file/update")
async def update_file_tags(request: Request):
    try:
        payload = await request.json()
        path = payload.get("path")
        tags = payload.get("tags", [])
        meta = load_data_meta()
        if not path: return {"code": 400}
        meta["file_tags"][path] = tags
        save_data_meta(meta)
        return {"code": 200, "data": meta["file_tags"].get(path, [])}
    except Exception as e: return {"code": 500, "message": str(e)}

# ==========================================
# 💾 强力落盘兜底引擎
# ==========================================
def safe_save_sample_logic():
    try:
        if hasattr(sample_logic, 'save_data'):
            sample_logic.save_data()
    except Exception as e: pass
    try:
        data_dir = get_base_dir()
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "sciforge_sample_topology.json"), "w", encoding="utf-8") as f:
            json.dump(sample_logic.equipments, f, ensure_ascii=False, indent=2)
        with open(os.path.join(data_dir, "sciforge_sample_data.json"), "w", encoding="utf-8") as f:
            json.dump(sample_logic.items, f, ensure_ascii=False, indent=2)
    except Exception as e: pass

# ==========================================
# 🌐 全局搜索引擎
# ==========================================
@app.get("/api/search/omnibar")
async def global_search(q: str):
    results = []
    q_lower = q.lower()
    for path, box in sample_logic.items.items():
        for wid, item in box.items():
            if q_lower in item.get('name', '').lower() or q_lower in item.get('type', '').lower():
                results.append({
                    "module": "SampleHub",
                    "title": item.get('name'),
                    "desc": f"物理位置: {path} [孔位 {wid}] | 余量: {item.get('vol')}{item.get('unit')}",
                    "icon": "🧬" if "质粒" in item.get('type', '') else ("🧪" if "蛋白" in item.get('type', '') else "🧫"),
                    "action_path": f"/sample/{path}/{wid}"
                })
    base_dir = get_base_dir()
    if os.path.exists(base_dir):
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if q_lower in file.lower():
                    ext = os.path.splitext(file)[1].lower()
                    icon = "📄"
                    if ext in ['.pdb', '.cif']: icon = "🧬"
                    elif ext in ['.fasta', '.fa', '.seq']: icon = "📜"
                    elif ext in ['.png', '.jpg', '.pdf']: icon = "📊"
                    rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                    size_kb = os.path.getsize(os.path.join(root, file)) / 1024
                    results.append({
                        "module": "DataHub",
                        "title": file,
                        "desc": f"归档目录: /{os.path.dirname(rel_path)} | 大小: {size_kb:.1f} KB",
                        "icon": icon,
                        "action_path": f"/data/{rel_path}"
                    })
    return {"code": 200, "data": results, "message": f"全局命中 {len(results)} 条记录"}


# ==========================================
# 🧪 样本中心 (Sample Hub)
# ==========================================
@app.get("/api/samples/topology")
async def get_sample_topology(): return {"code": 200, "data": sample_logic.equipments}

@app.get("/api/samples/{equip_id:path}")
async def get_box_samples(equip_id: str): return {"code": 200, "data": sample_logic.get_location_data(equip_id)}

@app.post("/api/samples/equipment/add")
async def add_equipment(request: Request):
    try:
        payload = await request.json()
        eq_id = payload.get("id")
        sample_logic.equipments[eq_id] = {
            "name": payload.get("name", "未命名设备"), "desc": payload.get("desc", ""), 
            "rows": int(payload.get("rows", 1)), "cols": int(payload.get("cols", 1)),
            "icon": payload.get("icon", "tiles"), "containers": {}
        }
        await run_in_threadpool(safe_save_sample_logic)
        return {"code": 200}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/equipment/resize")
async def resize_equipment(request: Request):
    try:
        payload = await request.json()
        eq_id = payload.get("id")
        if eq_id in sample_logic.equipments:
            sample_logic.equipments[eq_id]["rows"] = int(payload.get("rows", 1))
            sample_logic.equipments[eq_id]["cols"] = int(payload.get("cols", 1))
            await run_in_threadpool(safe_save_sample_logic)
            return {"code": 200}
        return {"code": 404}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/equipment/delete")
async def delete_equipment(request: Request):
    try:
        payload = await request.json()
        eq_id = payload.get("id")
        if eq_id in sample_logic.equipments:
            del sample_logic.equipments[eq_id]
            await run_in_threadpool(safe_save_sample_logic)
        return {"code": 200}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/container/add")
async def add_container(request: Request):
    try:
        payload = await request.json()
        equip_id = payload.get("equip_id")
        cont_type = payload.get("type", "freeform")
        import uuid
        cid = f"cont_{uuid.uuid4().hex[:8]}"
        cont_info = {
            "name": payload.get("name", "未命名分区"), "type": cont_type, 
            "r": 0, "c": 0, "rs": int(payload.get("rs", 1)), "cs": int(payload.get("cs", 1))
        }
        if cont_type == "rack":
            cont_info["layers"] = int(payload.get("layers", 5))
            cont_info["boxes"] = int(payload.get("boxes", 4))
            
        if equip_id in sample_logic.equipments:
            if "containers" not in sample_logic.equipments[equip_id]:
                sample_logic.equipments[equip_id]["containers"] = {}
            sample_logic.equipments[equip_id]["containers"][cid] = cont_info
            await run_in_threadpool(safe_save_sample_logic)
            return {"code": 200, "data": {"cid": cid}}
        return {"code": 404}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/container/move")
async def move_container(request: Request):
    try:
        payload = await request.json()
        equip_id = payload.get("equip_id")
        cid = payload.get("cid")
        eq = sample_logic.equipments.get(equip_id)
        if eq and cid in eq.get("containers", {}):
            eq["containers"][cid]["r"] = int(payload.get("r", 0))
            eq["containers"][cid]["c"] = int(payload.get("c", 0))
            await run_in_threadpool(safe_save_sample_logic)
            return {"code": 200}
        return {"code": 404}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/container/resize")
async def resize_container(request: Request):
    try:
        payload = await request.json()
        equip_id = payload.get("equip_id")
        cid = payload.get("cid")
        eq = sample_logic.equipments.get(equip_id)
        if eq and cid in eq.get("containers", {}):
            cont = eq["containers"][cid]
            new_rs = max(1, cont["rs"] + int(payload.get("d_row", 0)))
            new_cs = max(1, cont["cs"] + int(payload.get("d_col", 0)))
            if cont["r"] + new_rs <= eq["rows"] and cont["c"] + new_cs <= eq["cols"]:
                cont["rs"] = new_rs; cont["cs"] = new_cs
                await run_in_threadpool(safe_save_sample_logic)
                return {"code": 200}
        return {"code": 400}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/container/delete")
async def delete_container(request: Request):
    try:
        payload = await request.json()
        equip_id = payload.get("equip_id")
        cid = payload.get("cid")
        eq = sample_logic.equipments.get(equip_id)
        if eq and "containers" in eq and cid in eq["containers"]:
            del eq["containers"][cid]
            await run_in_threadpool(safe_save_sample_logic)
        return {"code": 200}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/add")
async def add_sample(request: Request):
    try:
        payload = await request.json()
        box_id = payload.get("box_id")
        well_index = payload.get("well_index")
        sample_info = {
            "id": f"SPL-{well_index}",
            "name": payload.get("sample_name", "未知资产"),
            "type": payload.get("sample_type", ""),
            "vol": float(payload.get("vol", 0.0)),
            "unit": payload.get("unit", ""),
            "ft": int(payload.get("ft_count", 0)),
            "owner": payload.get("owner", "Admin"),
            "notes": payload.get("notes", ""),
            "x": float(payload.get("x", 20.0)),
            "y": float(payload.get("y", 20.0)),
            "deposit_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if box_id not in sample_logic.items: sample_logic.items[box_id] = {}
        sample_logic.items[box_id][well_index] = sample_info
        await run_in_threadpool(safe_save_sample_logic)
        return {"code": 200}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/bulk_add")
async def bulk_add_samples(request: Request):
    try:
        payload = await request.json()
        box_id = payload.get("box_id")
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if box_id not in sample_logic.items: sample_logic.items[box_id] = {}
        for entry in payload.get("samples", []):
            idx = entry.get("well_index")
            sample_logic.items[box_id][idx] = {
                "id": f"SPL-{idx}", "name": entry.get("sample_name"), "type": entry.get("sample_type"), 
                "vol": entry.get("vol"), "unit": entry.get("unit"), "ft": entry.get("ft_count", 0), 
                "owner": entry.get("owner"), "notes": entry.get("notes"), "x": entry.get("x",0), "y": entry.get("y",0), "deposit_time": current_time
            }
        await run_in_threadpool(safe_save_sample_logic)
        return {"code": 200}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/checkout")
async def checkout_sample(request: Request):
    try:
        payload = await request.json()
        box_id = payload.get("box_id")
        well_index = payload.get("well_index")
        if box_id in sample_logic.items and well_index in sample_logic.items[box_id]:
            item = sample_logic.items[box_id][well_index]
            item["vol"] = max(0.0, float(item.get("vol", 0)) - float(payload.get("checkout_vol", 0.0)))
            item["ft"] = int(item.get("ft", 0)) + 1
            log_str = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 👤{payload.get('operator','Admin')} 取用。附言: {payload.get('notes','')}"
            item["notes"] = f"{log_str}\n{item.get('notes', '')}" if item.get("notes", "") else log_str
            await run_in_threadpool(safe_save_sample_logic)
            return {"code": 200, "data": item}
        return {"code": 404}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/remove")
async def remove_sample(request: Request):
    try:
        payload = await request.json()
        box_id = payload.get("box_id")
        well_index = payload.get("well_index")
        if box_id in sample_logic.items and well_index in sample_logic.items[box_id]:
            del sample_logic.items[box_id][well_index]
            await run_in_threadpool(safe_save_sample_logic)
        return {"code": 200}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/samples/move_item")
async def move_item(request: Request):
    try:
        payload = await request.json()
        box_id = payload.get("box_id")
        well_index = payload.get("well_index")
        if box_id in sample_logic.items and well_index in sample_logic.items[box_id]:
            sample_logic.items[box_id][well_index]["x"] = float(payload.get("x", 0))
            sample_logic.items[box_id][well_index]["y"] = float(payload.get("y", 0))
            await run_in_threadpool(safe_save_sample_logic)
            return {"code": 200}
        return {"code": 404}
    except Exception as e: return {"code": 500, "message": str(e)}


# ==========================================
# 📓 实验日历 (ELN) 
# ==========================================
class ElnSaveEntry(BaseModel): date: str; title: str; content: str

@app.get("/api/eln/recent")
async def get_eln_logs():
    logs = [{"title": t, "date": d, "status": "已记录"} for d, lst in eln_logic.schedule_data.items() if isinstance(lst, list) for t in lst]
    logs.sort(key=lambda x: x["date"], reverse=True)
    return {"code": 200, "data": logs[:15]}

@app.post("/api/eln/save")
async def save_eln_log(entry: ElnSaveEntry):
    target_date = entry.date if entry.date else datetime.datetime.now().strftime("%Y-%m-%d")
    if target_date not in eln_logic.schedule_data: eln_logic.schedule_data[target_date] = []
    eln_logic.schedule_data[target_date].insert(0, f"{entry.title}\n{entry.content}")
    await run_in_threadpool(eln_logic.save_data)
    return {"code": 200}


# ==========================================
# 📊 数据中心 (Data Hub)
# ==========================================
@app.get("/api/data/static/{file_path:path}")
async def serve_static_file(file_path: str):
    base_dir = get_base_dir()
    target = os.path.abspath(os.path.join(base_dir, file_path))
    if not target.startswith(base_dir) or not os.path.exists(target) or not os.path.isfile(target): return {"code": 404, "message": "File not found"}
    return FileResponse(target)

# 🚨 [修复核心Bug] 补全：拉取物理目录树接口
@app.get("/api/data/tree")
async def get_data_tree(path: str = ""):
    try:
        base_dir = get_base_dir()
        target_dir = os.path.abspath(os.path.join(base_dir, path))
        if not target_dir.startswith(base_dir): return {"code": 403, "message": "越权访问"}
        if not os.path.exists(target_dir): return {"code": 404, "message": "目录不存在"}
        
        files_list = []
        for f in os.listdir(target_dir):
            full_p = os.path.join(target_dir, f)
            is_dir = os.path.isdir(full_p)
            rel_p = os.path.relpath(full_p, base_dir).replace('\\', '/')
            size = os.path.getsize(full_p) if not is_dir else 0
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%Y-%m-%d %H:%M:%S")
            ext = os.path.splitext(f)[1].lower() if not is_dir else ""
            files_list.append({
                "name": f, "path": rel_p, "is_dir": is_dir, "size": size, "modified": mtime, "ext": ext
            })
        
        # 排序逻辑：文件夹排在最上面，然后按字母排序
        files_list.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"code": 200, "data": files_list, "current_path": path.replace('\\', '/').strip('/')}
    except Exception as e: 
        return {"code": 500, "message": str(e)}

# 🚨 [修复核心Bug] 补全：新建文件夹接口
@app.post("/api/data/mkdir")
async def make_directory(request: Request):
    try:
        payload = await request.json()
        base_dir = get_base_dir()
        target_dir = os.path.abspath(os.path.join(base_dir, payload.get("path", ""), payload.get("dir_name", "")))
        if not target_dir.startswith(base_dir): return {"code": 403, "message": "越权访问"}
        os.makedirs(target_dir, exist_ok=True)
        return {"code": 200, "message": "创建成功"}
    except Exception as e: 
        return {"code": 500, "message": str(e)}

# 🚨 [修复核心Bug] 补全：删除文件/文件夹接口
@app.post("/api/data/delete")
async def delete_data_file(request: Request):
    try:
        payload = await request.json()
        base_dir = get_base_dir()
        path_key = payload.get("path", "")
        target_path = os.path.abspath(os.path.join(base_dir, path_key))
        
        if not target_path.startswith(base_dir): return {"code": 403, "message": "越权访问"}
        if os.path.exists(target_path):
            if os.path.isdir(target_path): 
                shutil.rmtree(target_path)
            else: 
                os.remove(target_path)
            
            # 同步删除数据中心元数据字典里记录的关联标签
            meta = load_data_meta()
            if path_key in meta["file_tags"]:
                del meta["file_tags"][path_key]
                save_data_meta(meta)
                
        return {"code": 200, "message": "删除成功"}
    except Exception as e: 
        return {"code": 500, "message": str(e)}

@app.get("/api/data/read_file")
async def read_data_file(path: str):
    base_dir = get_base_dir()
    target_file = os.path.abspath(os.path.join(base_dir, path))
    if not target_file.startswith(base_dir): return {"code": 403, "message": "越权访问"}
    if not os.path.exists(target_file) or not os.path.isfile(target_file): return {"code": 404, "message": "文件不存在"}
    try:
        def read_content():
            with open(target_file, "r", encoding="utf-8", errors='ignore') as f: return f.read()
        content = await run_in_threadpool(read_content)
        return {"code": 200, "data": content}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/data/upload")
async def upload_data_file(path: str = Form(...), file: UploadFile = File(...)):
    try:
        base_dir = get_base_dir()
        target_dir = os.path.abspath(os.path.join(base_dir, path))
        if not target_dir.startswith(base_dir): return {"code": 403, "message": "越权访问"}
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"code": 200, "message": "上传成功"}
    except Exception as e:
        return {"code": 500, "message": f"上传失败: {str(e)}"}

@app.post("/api/data/save_file")
async def save_data_file(request: Request):
    try:
        payload = await request.json()
        base_dir = get_base_dir()
        target_dir = os.path.abspath(os.path.join(base_dir, payload.get("path", "")))
        if not target_dir.startswith(base_dir): return {"code": 403, "message": "越权访问"}
        os.makedirs(target_dir, exist_ok=True)
        def write_file():
            with open(os.path.join(target_dir, payload.get("filename")), "w", encoding="utf-8") as f:
                f.write(payload.get("content", ""))
        await run_in_threadpool(write_file)
        return {"code": 200, "message": "文件生成成功"}
    except Exception as e: return {"code": 500, "message": f"保存文件失败: {str(e)}"}

@app.post("/api/data/rename")
async def rename_data_file(request: Request):
    try:
        payload = await request.json()
        base_dir = get_base_dir()
        old_path_str = payload.get("old_path", "")
        new_path_str = payload.get("new_path", "")
        old_target = os.path.abspath(os.path.join(base_dir, old_path_str))
        new_target = os.path.abspath(os.path.join(base_dir, new_path_str))
        
        if not old_target.startswith(base_dir) or not new_target.startswith(base_dir): return {"code": 403, "message": "越权访问"}
        if os.path.exists(old_target):
            os.makedirs(os.path.dirname(new_target), exist_ok=True)
            
            shutil.copy2(old_target, new_target)
            try:
                os.remove(old_target) 
            except Exception:
                pass
            
            meta = load_data_meta()
            if old_path_str in meta["file_tags"]:
                meta["file_tags"][new_path_str] = meta["file_tags"].pop(old_path_str)
                save_data_meta(meta)
            return {"code": 200, "message": "重命名并归档成功"}
        return {"code": 404, "message": "原文件/目录不存在"}
    except Exception as e: return {"code": 500, "message": f"归档失败: {str(e)}"}

# ==========================================
# 🧬 算力引擎 (BioPlugins)
# ==========================================
def get_real_plugins():
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    if not os.path.exists(plugins_dir): os.makedirs(plugins_dir, exist_ok=True)
    real_plugins = []
    
    for filename in os.listdir(plugins_dir):
        if filename.startswith("plugin_") and filename.endswith(".py"):
            plugin_id = filename.replace("plugin_", "").replace(".py", "")
            script_path = os.path.join(plugins_dir, filename)
            
            p_name = f"{plugin_id.capitalize()} 算法"
            p_icon = "⚙️"
            p_desc = f"本地算力核心: {filename}"
            p_schema = [{"key": "input_file", "label": "输入参数", "type": "string", "default": ""}]
            p_layout = None  
            
            try:
                spec = importlib.util.spec_from_file_location(plugin_id, script_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                
                p_name = getattr(mod, 'PLUGIN_NAME', p_name)
                p_icon = getattr(mod, 'PLUGIN_ICON', p_icon)
                p_desc = getattr(mod, 'PLUGIN_DESC', p_desc)
                p_schema = getattr(mod, 'UI_SCHEMA', p_schema)
                p_layout = getattr(mod, 'UI_LAYOUT', None) 
            except Exception as e: pass
                
            real_plugins.append({
                "id": plugin_id, "name": p_name, "icon": p_icon, 
                "description": p_desc, "parameters": p_schema, "layout": p_layout
            })
            
    if not real_plugins: 
        real_plugins = [{"id": "demo", "name": "无脚本", "icon": "⚠️", "description": "无脚本", "parameters": []}]
    return real_plugins

@app.get("/api/plugins")
async def get_plugins(): return {"code": 200, "data": get_real_plugins()}

@app.get("/api/run/{plugin_id}")
async def run_plugin(plugin_id: str, request: Request):
    async def event_generator():
        yield f"data: [System] 正在初始化积木式算力流...\n\n"
        params = dict(request.query_params)
        script_name = f"plugin_{plugin_id}.py"
        plugins_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "plugins"))
        script_path = os.path.abspath(os.path.join(plugins_dir, script_name))
        
        if not os.path.exists(script_path):
            yield f"data: ❌ 致命错误: 未找到脚本 {script_name}\n\n"; yield "data: [End] DONE\n\n"; return
            
        python_exe = sys.executable
        if python_exe.endswith("pythonw.exe"):
            python_exe = python_exe.replace("pythonw.exe", "python.exe")

        cmd = [python_exe, "-u", script_path]
        
        # 🚨 终极防空洞：空参数直接被无情过滤，绝不进入命令导致 Python 解析崩溃
        for key, value in params.items():
            if value is None: continue
            str_val = str(value).strip()
            if not str_val or str_val == 'undefined' or str_val == 'null': continue
            
            if str_val.lower() == 'false': continue
            elif str_val.lower() == 'true': cmd.append(f"--{key}") 
            else: 
                cmd.append(f"--{key}")
                cmd.append(str_val)
            
        yield f"data: [Info] 唤起进程: {' '.join(cmd)}\n\n"
        await asyncio.sleep(0.2)
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.STDOUT, 
                cwd=os.path.dirname(__file__),
                env=env
            )
            
            while True:
                if await request.is_disconnected(): process.terminate(); break
                try: line = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
                except asyncio.TimeoutError: continue
                if not line: break
                
                try:
                    decoded_line = line.decode('utf-8').strip()
                except UnicodeDecodeError:
                    decoded_line = line.decode('gbk', errors='replace').strip()
                
                if decoded_line:
                    if "[OutputFile]" in decoded_line:
                        yield f"data: [OutputFile] {decoded_line.split('[OutputFile]')[1].strip()}\n\n"
                    elif "[OutputTable]" in decoded_line:
                        yield f"data: [OutputTable] {decoded_line.split('[OutputTable]')[1].strip()}\n\n"
                    elif "[OutputMetrics]" in decoded_line:
                        yield f"data: [OutputMetrics] {decoded_line.split('[OutputMetrics]')[1].strip()}\n\n"
                    elif "[OutputCode]" in decoded_line:
                        yield f"data: [OutputCode] {decoded_line.split('[OutputCode]')[1].strip()}\n\n"
                    else:
                        yield f"data: 👉 {decoded_line}\n\n"
                
            if not await request.is_disconnected():
                await process.wait()
                if process.returncode == 0: yield f"data: [Success] 核心计算正常结束！\n\n"
                else: yield f"data: ❌ [Error] 引擎异常中断，退出码: {process.returncode}\n\n"
        except Exception as e: yield f"data: ❌ [Fatal] 引擎崩溃: {str(e)}\n\n"
        finally:
            if process and process.returncode is None:
                try: process.terminate()
                except Exception: pass
        yield "data: [End] DONE\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    print("🚀 Mtools BioEngine Backend 启动中...")
    port = int(os.getenv("MTOOLS_PORT", 8080))
    uvicorn.run(app, host="127.0.0.1", port=port)