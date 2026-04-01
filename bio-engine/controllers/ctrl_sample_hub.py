# controllers/ctrl_sample_hub.py
"""
SciForge 物理样本库底层控制器 (四大设备常驻防护版 + 自动画布坐标系版)
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from core.config import GlobalConfig  

# 🌟 系统核心常驻四大物理设备（不可被意外清除）
PERMANENT_EQUIPMENTS = {
    "equip_drawer": {
        "name": "常温抽屉 / 储藏柜", "layout": "Grid", "rows": 5, "cols": 6,
        "desc": "常温存放区。用于存放常规离心管、枪头、室温保存的试剂与常温样本盒等。",
        "icon": "folder"
    },
    "equip_chromatography": {
        "name": "4℃ 层析柜", "layout": "Grid", "rows": 5, "cols": 6,
        "desc": "冷藏层析区。用于放置 AKTA 纯化设备、层析柱、大体积蛋白缓冲液等。",
        "icon": "tiles"
    },
    "equip_fridge_4_20": {
        "name": "4℃ / -20℃ 冰箱", "layout": "Grid", "rows": 5, "cols": 6,
        "desc": "日常冷藏冷冻区。用于存放抗体、酶类、日常实验试剂及短期周转样本。",
        "icon": "calendar"
    },
    "equip_fridge_80": {
        "name": "-80℃ 超低温冰箱", "layout": "Grid", "rows": 5, "cols": 6,
        "desc": "核心资产区。用于长期冻存甘油菌、质粒、细胞株、珍贵蛋白样本等。",
        "icon": "snowflake"
    }
}

class SampleHubLogic:
    """样本库核心逻辑引擎"""

    @property
    def sample_dir(self):
        ws = GlobalConfig.get("workspace_dir", os.path.abspath("./SciForge_Workspace"))
        d = os.path.join(ws, "SciForge_Samples")
        if not os.path.exists(d): os.makedirs(d, exist_ok=True)
        return d

    @property
    def config_file(self): return os.path.join(self.sample_dir, "sciforge_physical_map.json")
    
    @property
    def data_file(self): return os.path.join(self.sample_dir, "sciforge_sample_items.json")
    
    @property
    def web_db_file(self): return os.path.join(self.sample_dir, "sample_database.json")
    
    @property
    def canvas_file(self): return os.path.join(self.sample_dir, "sciforge_canvas_positions.json")

    def __init__(self):
        old_config = os.path.join(os.getcwd(), "sciforge_physical_map.json")
        old_data = os.path.join(os.getcwd(), "sciforge_sample_items.json")
        
        if os.path.exists(old_config) and not os.path.exists(self.config_file):
            try: shutil.move(old_config, self.config_file)
            except: pass
        if os.path.exists(old_data) and not os.path.exists(self.data_file):
            try: shutil.move(old_data, self.data_file)
            except: pass

        self.equipments = {}
        self.aliases = {}
        self.items = {}
        self.canvas_positions = {}
        
        self._load_positions()
        self._load_data()
        self.save_data()

    def _load_positions(self):
        if os.path.exists(self.canvas_file):
            try:
                with open(self.canvas_file, 'r', encoding='utf-8') as f:
                    self.canvas_positions = json.load(f)
            except Exception:
                self.canvas_positions = {}
        else:
            self.canvas_positions = {}

    def save_positions(self):
        try:
            with open(self.canvas_file, 'w', encoding='utf-8') as f:
                json.dump(self.canvas_positions, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def update_canvas_position(self, path, item_id, x, y):
        key = f"{path}/{item_id}"
        self.canvas_positions[key] = {"x": x, "y": y}
        self.save_positions()

    def get_canvas_positions(self, path):
        prefix = f"{path}/"
        res = {}
        for k, v in self.canvas_positions.items():
            if k.startswith(prefix):
                wid = k.replace(prefix, "")
                if "/" not in wid:
                    res[wid] = v
        return res

    def _load_data(self):
        # 加载基础映射配置
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "equipments" in data:
                        self.equipments = data.get("equipments", {})
                        self.aliases = data.get("aliases", {})
                    else:
                        self.equipments = {k: v for k, v in data.items() if k != "aliases"}
                        self.aliases = data.get("aliases", {})
            except Exception: pass

        # 🌟 核心拦截：不管 JSON 里有没有，强制将四大常驻设备合并进去
        for pid, pdata in PERMANENT_EQUIPMENTS.items():
            if pid not in self.equipments:
                self.equipments[pid] = {**pdata, "containers": {}, "inner_boxes": {}}
            else:
                # 即使存在，也强制纠正它们的描述和图标，保持系统的规范性
                self.equipments[pid]["desc"] = pdata["desc"]
                self.equipments[pid]["icon"] = pdata["icon"]
                if "name" not in self.equipments[pid]: 
                    self.equipments[pid]["name"] = pdata["name"]

        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.items = json.load(f)
            except Exception:
                self.items = {}

    def save_data(self):
        data_to_save = {"equipments": self.equipments, "aliases": self.aliases}
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.items, f, ensure_ascii=False, indent=4)
            
        self._update_web_database()

    def _update_web_database(self):
        web_items = []
        for path, wells in self.items.items():
            if not wells: continue
            human_readable_loc = self.get_full_alias_path(path)

            for well_id, info in wells.items():
                is_freeform = str(well_id).startswith("item_")
                loc_display = f"{human_readable_loc} [散装]" if is_freeform else f"{human_readable_loc} [孔位: {well_id}]"

                web_items.append({
                    "name": info.get("name", "未命名"), 
                    "type": info.get("type", "未知"),
                    "location_str": loc_display, 
                    "vol": info.get("vol", 0), 
                    "unit": info.get("unit", "μL"), 
                    "ft_count": info.get("ft", 0),
                    "owner": info.get("owner", ""), 
                    "notes": info.get("notes", ""),
                    "deposit_time": info.get("deposit_time", "-")
                })
        
        web_items = sorted(web_items, key=lambda x: x["location_str"])
        
        try:
            with open(self.web_db_file, 'w', encoding='utf-8') as f:
                json.dump({"samples": web_items}, f, ensure_ascii=False, indent=4)
        except Exception: pass

    def get_aliases(self): return self.aliases
    def set_alias(self, path: str, new_name: str):
        if new_name.strip(): self.aliases[path] = new_name.strip()
        else: self.aliases.pop(path, None)
        self.save_data()

    def add_equipment(self, name, layout, config):
        eid = f"equip_{uuid.uuid4().hex[:6]}"
        eq = {"name": name, "layout": layout, "containers": {}, "inner_boxes": {}}
        eq.update(config)
        self.equipments[eid] = eq
        self.save_data()
        return eid
    
    def delete_equipment(self, equip_id):
        """🌟 新增：彻底拆除物理设备 (受控版)"""
        # 1. 核心防护：拦截对四大常驻设备的拆除尝试
        if equip_id in PERMANENT_EQUIPMENTS:
            return False, "系统常驻核心设备受底层协议保护，禁止拆除！"

        # 2. 资产防丢防护：如果内部还有样本，禁止拆除
        prefix = f"{equip_id}/"
        for path, items in self.items.items():
            if (path == equip_id or path.startswith(prefix)) and items:
                return False, "该设备（或其子容器中）仍登记有未出库的物理样本资产，请先清空/转移样本后再拆除。"

        # 3. 授权执行拆除
        if equip_id in self.equipments:
            del self.equipments[equip_id]
            self.save_data()
            
            # 顺手清理关联的画布废弃坐标数据，保持系统整洁
            keys_to_delete = [k for k in self.canvas_positions.keys() if k.startswith(prefix) or k == equip_id]
            if keys_to_delete:
                for k in keys_to_delete:
                    del self.canvas_positions[k]
                self.save_positions()
                
            return True, "设备拆除成功"
        return False, "设备档案不存在"

    def resize_equipment_grid(self, equip_id, delta_row, delta_col):
        eq = self.equipments.get(equip_id)
        if not eq or eq.get("layout") != "Grid": return False, "非网格架构"
        new_rows, new_cols = eq["rows"] + delta_row, eq["cols"] + delta_col
        if new_rows < 1 or new_cols < 1: return False, "空间坍缩拦截"
        if delta_row < 0 or delta_col < 0:
            for cid, cont in eq["containers"].items():
                if cont["r"] + cont["rs"] > new_rows or cont["c"] + cont["cs"] > new_cols:
                    return False, "边界碰撞"
        eq["rows"], eq["cols"] = new_rows, new_cols
        self.save_data()
        return True, "重塑成功"

    def check_grid_space(self, equip_id, r, c, rs, cs, ignore_cid=None):
        eq = self.equipments.get(equip_id)
        if not eq or eq["layout"] != "Grid": return False, "非网格架构"
        if r < 0 or c < 0 or r + rs > eq["rows"] or c + cs > eq["cols"]: return False, "越界"
        for cid, cont in eq["containers"].items():
            if cid == ignore_cid: continue
            cr, cc, crs, ccs = cont["r"], cont["c"], cont["rs"], cont["cs"]
            if not (c + cs <= cc or c >= cc + ccs or r + rs <= cr or r >= cr + crs): return False, "碰撞"
        return True, "可用"

    def add_container(self, equip_id, container_info):
        eq = self.equipments.get(equip_id)
        if eq:
            cid = f"cont_{uuid.uuid4().hex[:6]}"
            container_info["id"] = cid
            eq["containers"][cid] = container_info
            self.save_data()
            return cid

    def delete_container(self, equip_id, cid):
        prefix = f"{equip_id}/{cid}"
        for path, items in self.items.items():
            if path.startswith(prefix) and items: return False, "内部仍存在样本资产"
        eq = self.equipments.get(equip_id)
        if eq and cid in eq["containers"]:
            del eq["containers"][cid]
            self.save_data()
            return True, "拆除完毕"
        return False, "失败"

    def get_inner_boxes(self, equip_id, zone_path): return self.equipments.get(equip_id, {}).get("inner_boxes", {}).get(zone_path, {})
    
    def add_inner_box(self, equip_id, zone_path, box_info):
        eq = self.equipments.get(equip_id)
        if eq:
            eq.setdefault("inner_boxes", {}).setdefault(zone_path, {})
            bid = f"ibox_{uuid.uuid4().hex[:6]}"
            box_info["id"] = bid
            eq["inner_boxes"][zone_path][bid] = box_info
            self.save_data()
            return bid

    def delete_inner_box(self, equip_id, zone_path, box_id):
        prefix = f"{zone_path}/{box_id}"
        if prefix in self.items and self.items[prefix]: return False, "内部仍存在样本资产"
        eq = self.equipments.get(equip_id)
        if eq and zone_path in eq.get("inner_boxes", {}) and box_id in eq["inner_boxes"][zone_path]:
            del eq["inner_boxes"][zone_path][box_id]
            self.save_data()
            pos_key = f"{zone_path}/{box_id}"
            if pos_key in self.canvas_positions:
                del self.canvas_positions[pos_key]
                self.save_positions()
            return True, "移出成功"
        return False, "失败"

    def get_location_data(self, path: str): return self.items.get(path, {})
    
    def update_item(self, path: str, item_id: str, item_info: dict):
        if not item_info.get("deposit_time"):
            existing_item = self.items.get(path, {}).get(item_id, {})
            item_info["deposit_time"] = existing_item.get("deposit_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        self.items.setdefault(path, {})[item_id] = item_info
        self.save_data()

    def add_freeform_item(self, path: str, item_info: dict):
        uid = f"item_{uuid.uuid4().hex[:8]}"
        self.update_item(path, uid, item_info)

    def delete_item(self, path: str, item_id: str):
        if path in self.items and item_id in self.items[path]:
            del self.items[path][item_id]
            self.save_data()
            
        key = f"{path}/{item_id}"
        if key in self.canvas_positions:
            del self.canvas_positions[key]
            self.save_positions()

    def batch_add_items(self, path: str, well_ids: list, base_info: dict):
        self.items.setdefault(path, {})
        sorted_wells = sorted(well_ids, key=lambda w: (w[0], int(w[1:])))
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i, well_id in enumerate(sorted_wells):
            import copy
            info = copy.deepcopy(base_info)
            info["name"] = f"{base_info['name']}-{i+1}"
            info["deposit_time"] = current_time 
            self.items[path][well_id] = info
        self.save_data()

    def get_full_alias_path(self, raw_path: str) -> str:
        parts = raw_path.split('/')
        aliased_parts = []
        acc = ""
        for p in parts:
            acc = f"{acc}/{p}" if acc else p
            if p in self.equipments:
                aliased_parts.append(self.aliases.get(acc, self.equipments[p]["name"]))
            elif len(parts) > 0 and parts[0] in self.equipments and p in self.equipments[parts[0]].get("containers", {}):
                aliased_parts.append(self.aliases.get(acc, self.equipments[parts[0]]["containers"][p]["name"]))
            elif len(parts) > 1 and parts[0] in self.equipments and p in self.equipments[parts[0]].get("inner_boxes", {}).get("/".join(parts[:-1]), {}):
                aliased_parts.append(self.aliases.get(acc, self.equipments[parts[0]]["inner_boxes"]["/".join(parts[:-1])][p]["name"]))
            else:
                if p not in ["top", "bottom", "left", "right"]: aliased_parts.append(self.aliases.get(acc, p))
        return " > ".join(aliased_parts)