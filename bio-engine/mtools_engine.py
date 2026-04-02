import asyncio
import os
import sys
import subprocess
import datetime
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional, List
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
# 🌐 全局搜索引擎 (Omnibar Search Hook)
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
                
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "SciForge_Workspace", "SciForge_Data"))
    if os.path.exists(workspace_dir):
        for root, dirs, files in os.walk(workspace_dir):
            for file in files:
                if q_lower in file.lower():
                    ext = os.path.splitext(file)[1].lower()
                    icon = "📄"
                    if ext in ['.pdb', '.cif']: icon = "🧬"
                    elif ext in ['.fasta', '.fa', '.seq']: icon = "📜"
                    elif ext in ['.png', '.jpg', '.pdf']: icon = "📊"
                    
                    rel_path = os.path.relpath(os.path.join(root, file), workspace_dir)
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
class ContainerAddEntry(BaseModel): equip_id: str; name: str; type: str = "freeform"; rs: int = 1; cs: int = 1; layers: Optional[int] = 5; boxes: Optional[int] = 4
class ContainerMoveEntry(BaseModel): equip_id: str; cid: str; r: int; c: int
class ContainerResizeEntry(BaseModel): equip_id: str; cid: str; d_row: int; d_col: int
class SampleAddEntry(BaseModel): box_id: str; well_index: str; sample_name: str; sample_type: str; vol: float; unit: str; ft_count: int; owner: str; notes: Optional[str] = ""; x: float = 20.0; y: float = 20.0
class BulkSampleAddEntry(BaseModel): box_id: str; samples: List[SampleAddEntry]
class SampleCheckoutEntry(BaseModel): box_id: str; well_index: str; checkout_vol: float; operator: str; notes: Optional[str] = ""
class ItemMoveEntry(BaseModel): box_id: str; well_index: str; x: float; y: float

@app.get("/api/samples/topology")
async def get_sample_topology(): return {"code": 200, "data": sample_logic.equipments}

@app.get("/api/samples/{equip_id:path}")
async def get_box_samples(equip_id: str): return {"code": 200, "data": sample_logic.get_location_data(equip_id)}

@app.post("/api/samples/container/add")
async def add_container(entry: ContainerAddEntry):
    cont_info = {"name": entry.name, "type": entry.type, "r": 0, "c": 0, "rs": entry.rs, "cs": entry.cs}
    if entry.type == "rack": cont_info["layers"] = entry.layers; cont_info["boxes"] = entry.boxes
    cid = sample_logic.add_container(entry.equip_id, cont_info)
    if cid: return {"code": 200, "message": "划拨成功", "data": {"cid": cid}}
    return {"code": 400, "message": "划拨失败"}

@app.post("/api/samples/container/move")
async def move_container(entry: ContainerMoveEntry):
    eq = sample_logic.equipments.get(entry.equip_id)
    if eq and entry.cid in eq.get("containers", {}):
        eq["containers"][entry.cid]["r"] = entry.r; eq["containers"][entry.cid]["c"] = entry.c
        sample_logic.save_data()
        return {"code": 200}
    return {"code": 400}

@app.post("/api/samples/container/resize")
async def resize_container(entry: ContainerResizeEntry):
    eq = sample_logic.equipments.get(entry.equip_id)
    if eq and entry.cid in eq.get("containers", {}):
        cont = eq["containers"][entry.cid]
        new_rs = max(1, cont["rs"] + entry.d_row); new_cs = max(1, cont["cs"] + entry.d_col)
        if cont["r"] + new_rs <= eq["rows"] and cont["c"] + new_cs <= eq["cols"]:
            cont["rs"] = new_rs; cont["cs"] = new_cs
            sample_logic.save_data(); return {"code": 200}
    return {"code": 400}

@app.post("/api/samples/container/delete")
async def delete_container(equip_id: str, cid: str):
    success, msg = sample_logic.delete_container(equip_id, cid)
    return {"code": 200 if success else 400, "message": msg}

@app.post("/api/samples/add")
async def add_sample(entry: SampleAddEntry):
    sample_info = {"id": f"SPL-{entry.well_index}", "name": entry.sample_name, "type": entry.sample_type, "vol": entry.vol, "unit": entry.unit, "ft": entry.ft_count, "owner": entry.owner, "notes": entry.notes, "x": entry.x, "y": entry.y, "deposit_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    sample_logic.update_item(entry.box_id, entry.well_index, sample_info); return {"code": 200}

@app.post("/api/samples/bulk_add")
async def bulk_add_samples(payload: BulkSampleAddEntry):
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for entry in payload.samples:
        if payload.box_id not in sample_logic.items: sample_logic.items[payload.box_id] = {}
        sample_logic.items[payload.box_id][entry.well_index] = {"id": f"SPL-{entry.well_index}", "name": entry.sample_name, "type": entry.sample_type, "vol": entry.vol, "unit": entry.unit, "ft": entry.ft_count, "owner": entry.owner, "notes": entry.notes, "x": entry.x, "y": entry.y, "deposit_time": current_time}
    sample_logic.save_data(); return {"code": 200}

@app.post("/api/samples/checkout")
async def checkout_sample(entry: SampleCheckoutEntry):
    if entry.box_id in sample_logic.items and entry.well_index in sample_logic.items[entry.box_id]:
        item = sample_logic.items[entry.box_id][entry.well_index]
        item["vol"] = max(0.0, float(item.get("vol", 0)) - entry.checkout_vol)
        item["ft"] = int(item.get("ft", 0)) + 1
        log_str = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 👤{entry.operator} 取用 {entry.checkout_vol}{item.get('unit', 'μL')}。附言: {entry.notes}"
        item["notes"] = f"{log_str}\n{item.get('notes', '')}" if item.get("notes", "") else log_str
        sample_logic.save_data(); return {"code": 200, "data": item}
    return {"code": 404}

@app.post("/api/samples/remove")
async def remove_sample(box_id: str, well_index: str):
    sample_logic.delete_item(box_id, well_index); return {"code": 200}

@app.post("/api/samples/move_item")
async def move_item(entry: ItemMoveEntry):
    if entry.box_id in sample_logic.items and entry.well_index in sample_logic.items[entry.box_id]:
        sample_logic.items[entry.box_id][entry.well_index]["x"] = entry.x
        sample_logic.items[entry.box_id][entry.well_index]["y"] = entry.y
        sample_logic.save_data(); return {"code": 200}
    return {"code": 404}


# ==========================================
# 📓 实验日历 (ELN) 
# ==========================================
class ElnSaveEntry(BaseModel): date: str; title: str; content: str

@app.get("/api/eln/recent")
async def get_eln_logs():
    logs = [{"title": t, "date": d, "status": "已记录"} for d, lst in eln_logic.schedule_data.items() if isinstance(lst, list) for t in lst]
    logs.sort(key=lambda x: x["date"], reverse=True); return {"code": 200, "data": logs[:15]}

@app.post("/api/eln/save")
async def save_eln_log(entry: ElnSaveEntry):
    target_date = entry.date if entry.date else datetime.datetime.now().strftime("%Y-%m-%d")
    if target_date not in eln_logic.schedule_data: eln_logic.schedule_data[target_date] = []
    eln_logic.schedule_data[target_date].insert(0, f"{entry.title}\n{entry.content}")
    eln_logic.save_data(); return {"code": 200}


# ==========================================
# 📊 数据中心 (Data Hub)
# ==========================================
class DataHubFileEntry(BaseModel): path: str; filename: str; content: str

@app.get("/api/data/tree")
async def get_data_tree(path: str = ""):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "SciForge_Workspace", "SciForge_Data"))
    target_dir = os.path.join(base_dir, path)
    if not os.path.exists(target_dir):
        if path == "":
            for d in ["01_Sequences", "02_Structures", "03_Plugin_Outputs", "04_Reports"]: os.makedirs(os.path.join(base_dir, d), exist_ok=True)
        else: return {"code": 404, "message": "目录不存在"}

    items = []
    try:
        for entry in os.scandir(target_dir):
            stat = entry.stat(); is_dir = entry.is_dir()
            items.append({
                "name": entry.name, "is_dir": is_dir, "path": os.path.relpath(entry.path, base_dir).replace('\\', '/'),
                "size": stat.st_size if not is_dir else 0, "ext": os.path.splitext(entry.name)[1].lower() if not is_dir else "",
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            })
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"code": 200, "data": items, "current_path": path}
    except Exception as e: return {"code": 500, "message": str(e)}

@app.post("/api/data/save_file")
async def save_data_file(entry: DataHubFileEntry):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "SciForge_Workspace", "SciForge_Data"))
    target_dir = os.path.join(base_dir, entry.path)
    os.makedirs(target_dir, exist_ok=True)
    with open(os.path.join(target_dir, entry.filename), "w", encoding="utf-8") as f: f.write(entry.content)
    return {"code": 200}

# 🚨 新增：读取本地文件内容的接口
@app.get("/api/data/read_file")
async def read_data_file(path: str):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "SciForge_Workspace", "SciForge_Data"))
    target_file = os.path.join(base_dir, path)
    if not os.path.exists(target_file) or not os.path.isfile(target_file):
        return {"code": 404, "message": "文件不存在"}
    try:
        # 只允许读取文本文件，如果是图片等二进制文件返回提示
        ext = os.path.splitext(target_file)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.pdf', '.zip']:
            return {"code": 400, "message": "二进制/图片文件暂不支持纯文本预览，请调用系统默认程序打开。"}
        
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
        return {"code": 200, "data": content}
    except Exception as e:
        return {"code": 500, "message": str(e)}


# ==========================================
# 🧬 算力引擎 (BioPlugins) 真实打通版
# ==========================================
import importlib.util

# 1. 动态扫描并加载真实的算法插件配置
def get_real_plugins():
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir, exist_ok=True)
        
    real_plugins = []
    # 遍历 plugins 目录下的所有 python 文件
    for filename in os.listdir(plugins_dir):
        if filename.startswith("plugin_") and filename.endswith(".py"):
            plugin_id = filename.replace("plugin_", "").replace(".py", "")
            script_path = os.path.join(plugins_dir, filename)
            
            # 这里我们提供一个默认的配置骨架。
            # 如果你的原生插件有特定的 Config 类，也可以在这里通过 importlib 动态提取
            plugin_info = {
                "id": plugin_id,
                "name": f"{plugin_id.capitalize()} 算法",
                "icon": "🧬" if "af3" in plugin_id else "🔠",
                "description": f"已挂载本地物理算法: {filename}",
                "parameters": [
                    {"key": "input_file", "label": "输入文件参数", "type": "string", "default": "", "width": "full"},
                    {"key": "iterations", "label": "迭代次数", "type": "number", "default": 100},
                    {"key": "verbose", "label": "开启详细日志", "type": "boolean", "default": True}
                ]
            }
            real_plugins.append(plugin_info)
            
    # 如果没扫描到物理插件，提供降级占位符
    if not real_plugins:
        real_plugins = [{
            "id": "demo_algorithm", "name": "演示算法 (未扫描到物理文件)", "icon": "⚠️",
            "description": "请在 bio-engine/plugins 目录下放入 plugin_xxx.py 脚本",
            "parameters": []
        }]
    return real_plugins

@app.get("/api/plugins")
async def get_plugins():
    """向前端下发真实的物理插件列表"""
    return {"code": 200, "data": get_real_plugins()}


@app.get("/api/run/{plugin_id}")
async def run_plugin(plugin_id: str, request: Request):
    """
    🚨 核心引擎：使用 asyncio 子进程调用真实的 Python 脚本，
    并将标准输出 (stdout) 实时截获，推送到前端终端！
    """
    async def event_generator():
        yield f"data: [System] 正在初始化本地算力节点...\n\n"
        
        # 1. 提取前端发来的表单参数
        params = dict(request.query_params)
        script_name = f"plugin_{plugin_id}.py"
        script_path = os.path.join(os.path.dirname(__file__), "plugins", script_name)
        
        if not os.path.exists(script_path):
            yield f"data: ❌ 致命错误: 物理硬盘中未找到算法脚本: {script_name}\n\n"
            yield "data: [End] DONE\n\n"
            return
            
        # 2. 组装控制台运行命令 (例如: python plugins/plugin_af3.py --iterations 100)
        cmd = [sys.executable, script_path]
        for key, value in params.items():
            # 过滤掉布尔值为 false 的选项
            if value.lower() == 'false':
                continue
            cmd.append(f"--{key}")
            if value.lower() != 'true':  # 如果不是布尔开关，则带上参数值
                cmd.append(str(value))
                
        cmd_str = " ".join(cmd)
        yield f"data: [Info] 执行原生底层命令: {cmd_str}\n\n"
        await asyncio.sleep(0.5)
        
        try:
            # 3. 🚨 启动异步子进程，不阻塞主线程
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, # 将错误流重定向到标准输出一并捕获
                cwd=os.path.dirname(__file__) # 设置工作目录
            )
            
            # 4. 实时循环读取进程输出，推给前端 SSE
            while True:
                line = await process.stdout.readline()
                if not line:
                    break # 进程结束，无更多输出
                    
                # 解码并在前端终端打出
                decoded_line = line.decode('utf-8', errors='replace').strip()
                if decoded_line:
                    # 简单判断是否包含 error 关键字以便前端染红
                    if "error" in decoded_line.lower() or "exception" in decoded_line.lower():
                        yield f"data: ❌ {decoded_line}\n\n"
                    else:
                        yield f"data: 👉 {decoded_line}\n\n"
                        
            # 等待进程彻底收尾
            await process.wait()
            
            if process.returncode == 0:
                yield f"data: [Success] 🎉 进程 {script_name} 运行圆满结束！\n\n"
            else:
                yield f"data: ❌ [Error] 进程异常退出，退出码 (Return Code): {process.returncode}\n\n"
                
        except Exception as e:
            yield f"data: ❌ [Fatal] 无法拉起子进程: {str(e)}\n\n"

        # 通知前端关闭通信流
        yield "data: [End] DONE\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    print("🚀 Mtools BioEngine Backend 启动中...")
    uvicorn.run(app, host="127.0.0.1", port=8080)