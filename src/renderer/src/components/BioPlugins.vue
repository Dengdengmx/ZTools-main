<template>
  <div class="bio-plugins-hub">
    <div class="plugin-list card">
      <h3>🧬 核心算法库</h3>
      <div class="plugins">
        <div v-for="plugin in availablePlugins" :key="plugin.id" class="plugin-card" :class="{ active: currentPluginId === plugin.id }" @click="selectPlugin(plugin.id)">
          <div class="p-icon">{{ plugin.icon }}</div>
          <div class="p-info">
            <span class="p-name">{{ plugin.name }}</span>
            <span class="p-desc">{{ plugin.description }}</span>
          </div>
          <div class="p-status ready">就绪</div>
        </div>
      </div>
    </div>
    <div class="plugin-workspace">
      <div v-if="activePlugin" class="config-panel card fade-in">
        <div class="action-buttons" style="display: flex; gap: 10px;">
            <button class="btn-secondary" @click="savePreset" style="background: #313244; color: #cdd6f4; border: none; padding: 12px 15px; border-radius: 8px; cursor: pointer;">
              💾 保存预设
            </button>
            <button class="btn-launch" @click="runSimulation" :disabled="isRunning">
              {{ isRunning ? '🚀 引擎运算中...' : '▶ 启动生成任务' }}
            </button>
          </div>
        <div class="form-grid">
          <div v-for="param in activePlugin.parameters" :key="param.key" class="form-group" :class="{ 'full-width': param.width === 'full' }">
            <label>{{ param.label }}</label>
            <input v-if="['string', 'number'].includes(param.type)" :type="param.type === 'number' ? 'number' : 'text'" :placeholder="param.placeholder" class="input-dark" v-model="formData[param.key]" />
            <div v-else-if="param.type === 'boolean'" class="checkbox-group">
              <label class="check-label"><input type="checkbox" v-model="formData[param.key]" /> {{ param.checkboxLabel || '启用该选项' }}</label>
            </div>
          </div>
        </div>
      </div>
      <div class="terminal card">
        <div class="terminal-header"><span>极客终端 (Terminal) - 监听 8080 端口</span></div>
        <div class="terminal-body" ref="terminalBody">
          <div v-for="(log, idx) in terminalLogs" :key="idx" class="log-line" :class="log.type">
            <span class="log-time">[{{ log.time }}]</span> {{ log.text }}
          </div>
          <div v-if="isRunning" class="cursor-blink">_</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'

// 🚨 把原来写死的一长串数组删掉，变成一个空数组
const availablePlugins = ref<any[]>([]) 

const currentPluginId = ref('')
const formData = ref<Record<string, any>>({})
const isRunning = ref(false)
const terminalLogs = ref<{time: string, text: string, type: string}[]>([])
const terminalBody = ref<HTMLElement | null>(null)

// 🚨 新增：向 Python 引擎动态拉取插件列表
const fetchPlugins = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/plugins')
    const json = await res.json()
    if (json.code === 200 && json.data.length > 0) {
      availablePlugins.value = json.data
      addLog(`[System] 已成功从物理大脑加载 ${json.data.length} 个算法模块！`, 'success')
      // 默认选中第一个插件
      selectPlugin(json.data[0].id)
    }
  } catch (e) {
    addLog("❌ 无法获取算法列表，请检查 127.0.0.1:8080 是否已启动！", "warning")
  }
}

const activePlugin = computed(() => availablePlugins.value.find(p => p.id === currentPluginId.value))

const selectPlugin = (id: string) => {
  currentPluginId.value = id
  formData.value = {}
  const plugin = availablePlugins.value.find(p => p.id === id)
  if (plugin && plugin.parameters) {
    // 🚨 尝试从本地存储读取记忆，如果没有则用默认值
    const savedConfig = localStorage.getItem(`mtools-preset-${id}`)
    if (savedConfig) {
      formData.value = JSON.parse(savedConfig)
      addLog(`[System] 已恢复 ${plugin.name} 的本地预设参数。`, 'info')
    } else {
      plugin.parameters.forEach(param => formData.value[param.key] = param.default)
    }
  }
}

const savePreset = () => {
  if (!activePlugin.value) return
  localStorage.setItem(`mtools-preset-${activePlugin.value.id}`, JSON.stringify(formData.value))
  addLog(`[Success] ✅ ${activePlugin.value.name} 参数已成功保存到本地预设！`, 'success')
}

const runSimulation = () => {
  if (!activePlugin.value) return
  isRunning.value = true
  terminalLogs.value = []
  
  // 顺手自动保存一下当前参数
  localStorage.setItem(`mtools-preset-${activePlugin.value.id}`, JSON.stringify(formData.value))
  
  // 🚨 核心：把 formData 转成 URL 查询字符串 (例如 ?contigs=200&num_designs=5)
  const queryParams = new URLSearchParams(formData.value as Record<string, string>).toString()
  
  addLog(`>>> 正在向本地物理大脑提交运算指令...`, "info")
  
  // 🚨 带着参数建立连接！
  const source = new EventSource(`http://127.0.0.1:8080/api/run/${activePlugin.value.id}?${queryParams}`)
  
  source.onmessage = (event) => {
    if (event.data === "[End] DONE") {
      source.close()
      isRunning.value = false
      return
    }
    let type = "info"
    if (event.data.includes("[Success]") || event.data.includes("✅")) type = "success"
    if (event.data.includes("[Calc]") || event.data.includes("👉")) type = "warning"
    if (event.data.includes("[Error]")) type = "error" // 如果有 error 样式的话
    addLog(event.data, type)
  }
  
  source.onerror = () => {
    addLog("❌ 引擎连接中断或执行出错！请检查 8080 端口。", "warning")
    source.close()
    isRunning.value = false
  }
}

const addLog = (text: string, type: string) => {
  terminalLogs.value.push({ time: new Date().toLocaleTimeString(), text, type })
  nextTick(() => { if (terminalBody.value) terminalBody.value.scrollTop = terminalBody.value.scrollHeight })
}

onMounted(() => {
  addLog("Mtools BioEngine v1.0 初始化中...", "info")
  fetchPlugins() // 触发动态拉取
})
</script>

<style scoped>
.bio-plugins-hub { display: flex; gap: 20px; height: 100%; min-height: 0; }
.card { background: #181825; border: 1px solid #313244; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
h2 { margin: 0 0 20px 0; color: #f5e0dc; display: flex; align-items: center; gap: 10px; }
h3 { margin-top: 0; color: #89b4fa; font-size: 16px; margin-bottom: 20px; }
.plugin-list { width: 320px; display: flex; flex-direction: column; flex-shrink: 0; }
.plugins { display: flex; flex-direction: column; gap: 12px; overflow-y: auto; flex: 1; }
.plugin-card { display: flex; align-items: center; gap: 15px; padding: 15px; background: #1e1e2e; border: 1px solid transparent; border-radius: 10px; cursor: pointer; transition: all 0.2s; }
.plugin-card.active { border-color: #89b4fa; background: rgba(137, 180, 250, 0.1); }
.p-icon { font-size: 28px; }
.p-info { display: flex; flex-direction: column; flex: 1; }
.p-name { font-weight: bold; color: #cdd6f4; font-size: 15px; }
.p-desc { font-size: 12px; color: #a6adc8; margin-top: 4px; }
.p-status { font-size: 12px; padding: 3px 8px; border-radius: 4px; font-weight: bold; }
.ready { background: rgba(166, 227, 161, 0.2); color: #a6e3a1; }
.plugin-workspace { flex: 1; display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.config-panel { flex-shrink: 0; }
.panel-header { display: flex; justify-content: space-between; align-items: flex-start; }
.btn-launch { background: #a6e3a1; color: #11111b; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; transition: all 0.2s; box-shadow: 0 0 15px rgba(166, 227, 161, 0.3); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 10px; }
.full-width { grid-column: 1 / -1; }
.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-group label { color: #bac2de; font-size: 14px; font-weight: 500; }
.input-dark { background: #11111b; border: 1px solid #313244; color: #cdd6f4; padding: 10px 15px; border-radius: 6px; font-family: monospace; outline: none; }
.terminal { flex: 1; display: flex; flex-direction: column; min-height: 0; background: #11111b; padding: 0; overflow: hidden; }
.terminal-header { background: #181825; padding: 10px 20px; border-bottom: 1px solid #313244; display: flex; justify-content: space-between; align-items: center; color: #6c7086; font-size: 13px; font-weight: bold; }
.terminal-body { flex: 1; padding: 20px; overflow-y: auto; font-family: 'Consolas', 'Courier New', monospace; font-size: 14px; line-height: 1.5; }
.log-time { color: #6c7086; margin-right: 10px; }
.log-line { margin-bottom: 6px; }
.info { color: #cdd6f4; }
.success { color: #a6e3a1; }
.warning { color: #f9e2af; }
.cursor-blink { display: inline-block; width: 10px; background: #cdd6f4; color: transparent; animation: blink 1s step-end infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
</style>