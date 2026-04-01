# core/config.py
"""
SciForge 全局配置管理模块
提供最高自由度的环境与插件参数管理，强制锁定亮色体验。
所有配置统一存储在 sciforge_global.json 文件中。
"""

import os
import json

class GlobalConfig:
    """全局配置单例引擎：管理软件中所有的标签、模板、插件独立沙盒"""
    _file = os.path.join(os.getcwd(), "sciforge_global.json")
    _data = {}

    @classmethod
    def load(cls):
        """从 JSON 文件加载配置，若无则创建默认结构"""
        if os.path.exists(cls._file):
            try:
                with open(cls._file, 'r', encoding='utf-8') as f:
                    cls._data = json.load(f)
            except Exception as e:
                print(f"[GlobalConfig] 配置文件解析异常: {e}，将启用安全回退模式。")
                cls._data = {}

        # 核心骨架兜底，暴露出最多的可自定义项，不含任何主题外观配置
        default_structure = {
            "environment": {
                "archive_root": os.path.join(os.getcwd(), "SciForge_Archive"),
                "auto_backup": True,
                "log_level": "INFO"
            },
            "categorization": {
                "archive_tags": ["🧬 课题: SciForge Main", "🧪 课题: SFTSV-Gc", "🔬 常规实验"],
                "sample_types": ["🧬 质粒", "🧪 蛋白", "🧫 细胞", "🦠 菌种", "💧 核酸", "📦 耗材"]
            },
            "eln_templates": {},
            "plugin_settings": {} # 各大分析引擎的独立沙盒
        }

        # 智能合并结构
        for key, default_val in default_structure.items():
            if key not in cls._data:
                cls._data[key] = default_val

        cls._merge_preset_templates()
        cls.save()

    @classmethod
    def _merge_preset_templates(cls):
        """支持自定义的强大生化实验记录模板库（只增不减原则）"""
        preset_templates = {
            "📦 寄快递": "【寄快递】\n物品内容：\n快递单号：\n收件方：\n",
            "📥 收快递": "【收快递】\n物品内容：\n存放位置：\n存储条件：\n",
            "🧬 分子构建": "【分子构建】\n目的基因：\n载体名称：\n酶切位点：\n预期大小：\n",
            "💧 质粒提取": "【质粒提取】\n菌株/质粒：\n浓度(ng/uL)：\nA260/280：\n",
            "🧪 蛋白纯化": "【蛋白纯化】\n目标蛋白：\n层析柱(Ni/SEC)：\n洗脱条件：\n预估浓度：\n",
            "🧫 挑单克隆": "【挑单克隆】\n平板抗性：\n挑选克隆数：\n培养条件：\n",
            "✉️ 送测序": "【送测序】\n测序公司：\n样本数量：\n使用引物：\n",
            "🦠 接种菌": "【接种菌】\n菌株/质粒：\n培养基(LB/TB)：\n抗生素：\n",
            "⚡ 转化": "【转化】\n感受态细胞：\n质粒/连接产物：\n涂布板抗性：\n",
            "🔬 细胞传代": "【细胞传代/铺板】\n细胞系：\n代数：\n接种密度：\n培养基：\n",
            "📊 ELISA": "【ELISA 检测】\n检测靶标：\n包被浓度：\n一抗稀释：\n二抗稀释：\n",
            "📝 组会汇报": "【组会/汇报】\n汇报主题：\n核心文献：\n需准备数据：\n",
            "🐁 小鼠解剖": "【小鼠解剖】\n品系/日龄：\n毛色/体重：\n提取器官：\n",
            "📈 SPR 亲和力分析": "【SPR】\n实验目的：测定蛋白与配体的结合动力学\n配体(Ligand)：\n分析物(Analyte)：\n缓冲液(Buffer)：\n流速(μL/min)：\n",
            "📉 AKTA 蛋白纯化": "【AKTA】\n层析柱型号：\n样品名称：\n缓冲液A (平衡)：\n缓冲液B (洗脱)：\n洗脱梯度：\n",
            "🔥 BLI 表位聚类/热图": "【BLI 热图】\n实验目的：抗体表位竞争分析\n参考基准(Ref)：PBST\n样本数量：\n",
            "🧬 核酸/蛋白 序列分析": "【序列分析】\n实验目的：序列核对与特征分析\n目标基因/蛋白：\n测序引物：\n分析结论：\n",
            "🖼️ 科研大图拼板组装": "【科研拼板】\n实验目的：组装多组结果图\n包含子图说明：\n",
            "🧊 蛋白质 3D 结构分析": "【3D 结构】\n目标蛋白：\nPDB ID / 来源：\n突变位点/核心表位：\n"
        }

        if "eln_templates" not in cls._data:
            cls._data["eln_templates"] = {}

        needs_save = False
        for k, v in preset_templates.items():
            if k not in cls._data["eln_templates"]:
                cls._data["eln_templates"][k] = v
                needs_save = True

        if needs_save:
            cls.save()

    @classmethod
    def save(cls):
        """将当前配置保存到 JSON 文件"""
        try:
            with open(cls._file, 'w', encoding='utf-8') as f:
                json.dump(cls._data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[GlobalConfig] IO 保存失败: {e}")

    @classmethod
    def get(cls, key, default=None):
        return cls._data.get(key, default)

    @classmethod
    def set(cls, key, val):
        cls._data[key] = val
        cls.save()

    @classmethod
    def get_env(cls, key, default=None):
        """获取系统环境级配置"""
        return cls._data.get("environment", {}).get(key, default)

    # ----- 插件配置独立沙盒 API -----
    @classmethod
    def get_plugin_setting(cls, plugin_id, key, default=None):
        return cls._data.get("plugin_settings", {}).get(plugin_id, {}).get(key, default)

    @classmethod
    def set_plugin_setting(cls, plugin_id, key, value):
        plugin_settings = cls._data.setdefault("plugin_settings", {})
        if plugin_id not in plugin_settings:
            plugin_settings[plugin_id] = {}
        plugin_settings[plugin_id][key] = value
        cls.save()

    @classmethod
    def get_all_plugin_settings(cls, plugin_id):
        return cls._data.setdefault("plugin_settings", {}).get(plugin_id, {})

    @classmethod
    def set_all_plugin_settings(cls, plugin_id, settings_dict):
        cls._data.setdefault("plugin_settings", {})[plugin_id] = settings_dict
        cls.save()

# 模块被导入时自动执行一次加载
GlobalConfig.load()