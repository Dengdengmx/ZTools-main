import asyncio
import os
import sys
import subprocess
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 🚨 导入 SciForge 真正的原生核心控制器
from controllers.ctrl_calendar_archive import CalendarArchiveLogic
from controllers.ctrl_data_hub import DataHubLogic
from controllers.ctrl_sample_hub import SampleHubLogic
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Mtools BioEngine Hub")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 🚨 实例化三大物理核心
print("正在挂载 SciForge 核心物理控制器...")
eln_logic = CalendarArchiveLogic()
sample_logic = SampleHubLogic()
data_logic = DataHubLogic()
print("挂载完成，物理宇宙已建立！")

# ==========================================
# 📓 实验日历 (ELN) 真实中枢
# ==========================================
class LogEntry(BaseModel):
    title: str
    date: str
    status: str = "进行中"

@app.get("/api/eln/recent")
async def get_eln_logs():
    # 适配前端的列表格式，从原生 schedule_data 中提取
    logs = []
    for date_str, data in eln_logic.schedule_data.items():
        if isinstance(data, dict) and data.get("main"):
            logs.append({
                "id": f"ELN-{date_str.replace('-','')}",
                "title": data.get("main", "未命名记录")[:20] + "...", # 截取开头作为标题
                "date": date_str,
                "status": "已归档"
            })
    # 按日期倒序
    logs.sort(key=lambda x: x["date"], reverse=True)
    return {"code": 200, "data": logs}

@app.post("/api/eln/add")
async def add_eln_log(entry: LogEntry):
    # 调用你原生的强大存储逻辑
    eln_logic.update_day_data(entry.date, [], entry.title, "")
    return {"code": 200, "message": "原生归档成功"}

# ==========================================
# 🧪 样本中心 (Sample Hub) 真实中枢
# ==========================================
class SampleAddEntry(BaseModel):
    box_id: str
    well_index: str
    sample_name: str
    sample_type: str
    vol: float
    unit: str
    ft_count: int
    owner: str
    notes: Optional[str] = ""
    x: float = 20.0  # 🚨 新增：默认生成的 X 坐标
    y: float = 20.0  # 🚨 新增：默认生成的 Y 坐标

@app.post("/api/samples/add")
async def add_sample(entry: SampleAddEntry):
    import datetime
    sample_info = {
        "id": f"SPL-{entry.well_index}",
        "name": entry.sample_name,
        "type": entry.sample_type,
        "vol": entry.vol,
        "unit": entry.unit,
        "ft": entry.ft_count,
        "owner": entry.owner,
        "notes": entry.notes,
        "x": entry.x,  # 🚨 存入坐标
        "y": entry.y,  # 🚨 存入坐标
        "deposit_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    sample_logic.update_item(entry.box_id, entry.well_index, sample_info)
    return {"code": 200, "message": "物理入库成功"}

class ItemMoveEntry(BaseModel):
    box_id: str
    well_index: str
    x: float
    y: float

@app.post("/api/samples/move_item")
async def move_item(entry: ItemMoveEntry):
    if entry.box_id in sample_logic.items and entry.well_index in sample_logic.items[entry.box_id]:
        sample_logic.items[entry.box_id][entry.well_index]["x"] = entry.x
        sample_logic.items[entry.box_id][entry.well_index]["y"] = entry.y
        sample_logic.save_data()
        return {"code": 200}
    return {"code": 404}

# 🚨 新增：蓝图建造相关的 Pydantic 模型
class ContainerAddEntry(BaseModel):
    equip_id: str
    name: str
    type: str = "freeform"
    rs: int = 1
    cs: int = 1
    layers: Optional[int] = 5
    boxes: Optional[int] = 4

class ContainerMoveEntry(BaseModel):
    equip_id: str
    cid: str
    r: int
    c: int

class ContainerResizeEntry(BaseModel):
    equip_id: str
    cid: str
    d_row: int
    d_col: int

# --- 原有的 API 保持不变 ---
@app.get("/api/samples/topology")
async def get_sample_topology():
    return {"code": 200, "data": sample_logic.equipments}

@app.get("/api/samples/{equip_id:path}") # 🚨 致命修复：加上 :path
async def get_box_samples(equip_id: str):
    data = sample_logic.get_location_data(equip_id)
    return {"code": 200, "data": data}

@app.post("/api/samples/remove")
async def remove_sample(box_id: str, well_index: int):
    sample_logic.delete_item(box_id, str(well_index))
    return {"code": 200, "message": "物理出库成功"}

# --- 🚨 新增：蓝图编辑器 API ---
@app.post("/api/samples/container/add")
async def add_container(entry: ContainerAddEntry):
    cont_info = {
        "name": entry.name, 
        "type": entry.type,
        "r": 0, "c": 0, 
        "rs": entry.rs, "cs": entry.cs
    }
    # 如果是冻存架，附加层数和盒数属性
    if entry.type == "rack":
        cont_info["layers"] = entry.layers
        cont_info["boxes"] = entry.boxes

    cid = sample_logic.add_container(entry.equip_id, cont_info)
    if cid:
        return {"code": 200, "message": "容器已划拨", "data": {"cid": cid}}
    return {"code": 400, "message": "划拨失败"}

@app.post("/api/samples/container/move")
async def move_container(entry: ContainerMoveEntry):
    # 直接修改 JSON 中的坐标系并保存
    eq = sample_logic.equipments.get(entry.equip_id)
    if eq and entry.cid in eq.get("containers", {}):
        eq["containers"][entry.cid]["r"] = entry.r
        eq["containers"][entry.cid]["c"] = entry.c
        sample_logic.save_data()
        return {"code": 200, "message": "位移成功"}
    return {"code": 400, "message": "寻址失败"}

@app.post("/api/samples/container/resize")
async def resize_container(entry: ContainerResizeEntry):
    # 修改尺寸
    eq = sample_logic.equipments.get(entry.equip_id)
    if eq and entry.cid in eq.get("containers", {}):
        cont = eq["containers"][entry.cid]
        new_rs = max(1, cont["rs"] + entry.d_row)
        new_cs = max(1, cont["cs"] + entry.d_col)
        # 简单边界防护
        if cont["r"] + new_rs <= eq["rows"] and cont["c"] + new_cs <= eq["cols"]:
            cont["rs"] = new_rs
            cont["cs"] = new_cs
            sample_logic.save_data()
            return {"code": 200, "message": "形变成功"}
    return {"code": 400, "message": "形变越界或失败"}

@app.post("/api/samples/container/delete")
async def delete_container(equip_id: str, cid: str):
    success, msg = sample_logic.delete_container(equip_id, cid)
    return {"code": 200 if success else 400, "message": msg}

# ==========================================
# 📊 数据中心 (Data Hub) 真实中枢
# ==========================================
@app.get("/api/data/preview")
async def preview_data(file_path: str):
    # 调用原生的策略模式预览引擎
    result = data_logic.preview_engine.execute(file_path)
    return {"code": 200, "type": result.p_type, "content": str(result.content), "meta": result.meta_info}

# ... 这里可以保留你之前的 PLUGIN_REGISTRY 和 /api/plugins /api/run 算法引擎接口 ...

if __name__ == "__main__":
    print("🧬 Mtools 真实算力大脑与物理中枢已启动！监听 8080...")
    uvicorn.run(app, host="127.0.0.1", port=8080)