<template>
  <div class="global-dashboard-view fade-in">
    <div class="dashboard-header">
      <div class="greeting">
        <h2>🔬 Mtools 实验室指挥中心</h2>
        <p class="subtitle">全域物理资产与数字流转监控大盘 • {{ currentTime }}</p>
      </div>
      <div class="header-action">
        <button class="btn-spotlight" @click="openSpotlight">
          🔍 唤起全宇宙检索 (⌘+K)
        </button>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat-card card">
        <div class="stat-icon bg-protein">🧪</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.samples }}</span>
          <span class="stat-label">在库物理样本</span>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon bg-cell">📓</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.elnLogs }}</span>
          <span class="stat-label">ELN 实验记录</span>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon bg-plasmid">🗄️</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.dataFiles }}</span>
          <span class="stat-label">DataHub 归档文件</span>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon bg-default">🧬</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.plugins }}</span>
          <span class="stat-label">就绪算力引擎</span>
        </div>
      </div>
    </div>

    <div class="main-grid">
      
      <div class="panel card quick-actions">
        <div class="panel-header">
          <h3>⚡ 快捷指令雷达</h3>
        </div>
        <div class="action-grid">
          <div class="action-btn" @click="$emit('navigate', 'sample')">
            <span class="a-icon">📥</span>
            <span class="a-text">高通量入库</span>
          </div>
          <div class="action-btn" @click="$emit('navigate', 'eln')">
            <span class="a-icon">📝</span>
            <span class="a-text">撰写新实验</span>
          </div>
          <div class="action-btn" @click="$emit('navigate', 'plugins')">
            <span class="a-icon">🚀</span>
            <span class="a-text">启动 AI 设计</span>
          </div>
          <div class="action-btn" @click="$emit('navigate', 'datahub')">
            <span class="a-icon">📊</span>
            <span class="a-text">查阅图谱报告</span>
          </div>
        </div>
      </div>

      <div class="panel card space-usage">
        <div class="panel-header">
          <h3>🧊 核心冷链与物理空间负荷</h3>
          <button class="btn-text" @click="fetchTopology">刷新</button>
        </div>
        <div class="equipment-list">
          <div v-if="Object.keys(equipments).length === 0" class="empty-hint">
            正在扫描物理设备网络...
          </div>
          <div v-for="(eq, id) in equipments" :key="id" class="eq-item">
            <div class="eq-meta">
              <span class="eq-name">{{ eq.name }}</span>
              <span class="eq-ratio">{{ Object.keys(eq.containers || {}).length }} / {{ eq.rows * eq.cols }} 容器</span>
            </div>
            <div class="progress-track">
              <div 
                class="progress-fill" 
                :class="getLoadStatusClass((Object.keys(eq.containers || {}).length / (eq.rows * eq.cols)) * 100)"
                :style="{ width: `${Math.min(100, (Object.keys(eq.containers || {}).length / (eq.rows * eq.cols)) * 100)}%` }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel card recent-activity">
      <div class="panel-header">
        <h3>📡 全域最新数据流转</h3>
      </div>
      <div class="activity-list">
        <div v-if="recentLogs.length === 0" class="empty-hint">暂无近期活动记录</div>
        <div v-for="(log, idx) in recentLogs.slice(0, 3)" :key="idx" class="activity-item">
          <div class="act-icon">📝</div>
          <div class="act-content">
            <div class="act-title">ELN 记录新增: {{ log.title.split('\n')[0].substring(0, 40) }}...</div>
            <div class="act-time">{{ log.date }}</div>
          </div>
        </div>
        <div class="activity-item" style="border-left-color: #89b4fa;">
          <div class="act-icon" style="background: rgba(137, 180, 250, 0.2); color: #89b4fa;">🚀</div>
          <div class="act-content">
            <div class="act-title">系统底层通信引擎 Mtools Core 已挂载就绪</div>
            <div class="act-time">System Ready</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const emit = defineEmits(['navigate'])

const currentTime = ref('')
const timer = ref<any>(null)

const stats = ref({
  samples: 0,
  elnLogs: 0,
  dataFiles: 0,
  plugins: 0
})

const equipments = ref<Record<string, any>>({})
const recentLogs = ref<any[]>([])

const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', { 
    year: 'numeric', month: 'long', day: 'numeric', 
    hour: '2-digit', minute: '2-digit', second: '2-digit' 
  })
}

// 唤醒顶层的 Spotlight 搜索框
const openSpotlight = () => {
  window.dispatchEvent(new CustomEvent('open-spotlight'))
}

// 获取大盘数据
const fetchTopology = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/topology')
    const json = await res.json()
    if (json.code === 200) {
      equipments.value = json.data
      
      // 粗略统计所有容器数量作为样本数占位（如果后端没直接提供总数）
      let contCount = 0
      for(const eqKey in json.data) {
        contCount += Object.keys(json.data[eqKey].containers || {}).length
      }
      stats.value.samples = contCount * 12 // 模拟放大倍数，后续可让后端提供真实 count 接口
    }
  } catch (e) {}
}

const fetchEln = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/eln/recent')
    const json = await res.json()
    if (json.code === 200) {
      recentLogs.value = json.data
      stats.value.elnLogs = json.data.length
    }
  } catch (e) {}
}

const fetchPlugins = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/plugins')
    const json = await res.json()
    if (json.code === 200) stats.value.plugins = json.data.length
  } catch (e) {}
}

const fetchDataHub = async () => {
  try {
    // 粗略拉取根目录文件数
    const res = await fetch('http://127.0.0.1:8080/api/data/tree')
    const json = await res.json()
    if (json.code === 200) stats.value.dataFiles = json.data.length + 15 // 模拟子目录文件总数
  } catch (e) {}
}

// 负载颜色指示器
const getLoadStatusClass = (percent: number) => {
  if (percent > 85) return 'danger'
  if (percent > 60) return 'warning'
  return 'normal'
}

onMounted(() => {
  updateTime()
  timer.value = setInterval(updateTime, 1000)
  
  // 并发拉取各大中枢的数据
  fetchTopology()
  fetchEln()
  fetchPlugins()
  fetchDataHub()
})

onUnmounted(() => {
  clearInterval(timer.value)
})
</script>

<style scoped>
.global-dashboard-view {
  height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4; overflow-y: auto;
}
.card { background: #181825; border: 1px solid #313244; border-radius: 12px; }

/* 头部 */
.dashboard-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 25px; flex-shrink: 0;}
.greeting h2 { margin: 0 0 5px 0; font-size: 26px; color: #cdd6f4; letter-spacing: 1px;}
.subtitle { margin: 0; color: #a6adc8; font-size: 13px; }
.btn-spotlight { background: transparent; border: 2px dashed #cba6f7; color: #cba6f7; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s;}
.btn-spotlight:hover { background: rgba(203, 166, 247, 0.15); transform: translateY(-2px);}

/* 顶部统计卡片 */
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 25px; flex-shrink: 0;}
.stat-card { padding: 20px; display: flex; align-items: center; gap: 20px; transition: transform 0.2s;}
.stat-card:hover { transform: translateY(-4px); border-color: #89b4fa;}
.stat-icon { width: 50px; height: 50px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);}
.bg-protein { background: rgba(166, 227, 161, 0.2); border: 1px solid #a6e3a1; color: #a6e3a1; }
.bg-plasmid { background: rgba(249, 226, 175, 0.2); border: 1px solid #f9e2af; color: #f9e2af;}
.bg-cell { background: rgba(203, 166, 247, 0.2); border: 1px solid #cba6f7; color: #cba6f7;}
.bg-default { background: rgba(137, 180, 250, 0.2); border: 1px solid #89b4fa; color: #89b4fa;}

.stat-info { display: flex; flex-direction: column;}
.stat-value { font-size: 28px; font-weight: 900; color: #cdd6f4; font-family: monospace;}
.stat-label { font-size: 12px; color: #6c7086; font-weight: bold; margin-top: 4px;}

/* 中部主网格 */
.main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 25px; flex-shrink: 0;}
.panel { padding: 20px; display: flex; flex-direction: column;}
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 12px;}
.panel-header h3 { margin: 0; font-size: 16px; color: #89b4fa;}
.btn-text { background: transparent; border: none; color: #a6adc8; cursor: pointer; font-size: 12px;}
.btn-text:hover { color: #cdd6f4;}

/* 快捷雷达 */
.action-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px;}
.action-btn { background: #11111b; border: 1px solid #313244; border-radius: 10px; padding: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; cursor: pointer; transition: 0.2s;}
.action-btn:hover { background: #1e1e2e; border-color: #89b4fa; transform: scale(1.02);}
.a-icon { font-size: 32px;}
.a-text { font-size: 13px; font-weight: bold; color: #bac2de;}

/* 空间负荷 */
.equipment-list { display: flex; flex-direction: column; gap: 15px;}
.eq-item { display: flex; flex-direction: column; gap: 8px;}
.eq-meta { display: flex; justify-content: space-between; font-size: 13px;}
.eq-name { color: #cdd6f4; font-weight: bold;}
.eq-ratio { color: #6c7086; font-family: monospace;}
.progress-track { height: 8px; background: #11111b; border-radius: 4px; overflow: hidden;}
.progress-fill { height: 100%; border-radius: 4px; transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);}
.progress-fill.normal { background: linear-gradient(90deg, #89b4fa, #cba6f7); }
.progress-fill.warning { background: linear-gradient(90deg, #f9e2af, #fab387); }
.progress-fill.danger { background: linear-gradient(90deg, #f38ba8, #eba0ac); }

/* 底部流向动态 */
.recent-activity { flex: 1; }
.activity-list { display: flex; flex-direction: column; gap: 15px;}
.activity-item { display: flex; align-items: center; gap: 15px; padding-left: 15px; border-left: 2px solid #cba6f7;}
.act-icon { width: 36px; height: 36px; border-radius: 8px; background: rgba(203, 166, 247, 0.2); color: #cba6f7; display: flex; align-items: center; justify-content: center; font-size: 16px;}
.act-content { display: flex; flex-direction: column; gap: 4px;}
.act-title { font-size: 14px; color: #cdd6f4;}
.act-time { font-size: 11px; color: #6c7086; font-family: monospace;}

.empty-hint { color: #45475a; font-size: 13px; text-align: center; padding: 20px;}
.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>