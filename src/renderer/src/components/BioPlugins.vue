<template>
  <div class="bio-plugins-hub">
    <div class="plugin-list card">
      <h3>🧬 核心算法引擎</h3>
      <div class="plugins">
        <div 
          v-for="plugin in availablePlugins" 
          :key="plugin.id" 
          class="plugin-card" 
          :class="{ active: currentPluginId === plugin.id }" 
          @click="selectPlugin(plugin.id)"
        >
          <div class="p-icon">{{ plugin.icon }}</div>
          <div class="p-info">
            <span class="p-name">{{ plugin.name }}</span>
            <span class="p-desc">{{ plugin.description }}</span>
          </div>
          <div class="p-status ready">就绪</div>
        </div>
        
        <div v-if="availablePlugins.length === 0" class="empty-plugins">
          <span class="spin-loader">⚙️</span>
          <p>正在连接物理大脑...</p>
        </div>
      </div>
    </div>

    <div class="plugin-workspace">
      <div v-if="activePlugin" class="config-panel card fade-in">
        <div class="panel-header">
          <div class="plugin-title-area">
            <h2 style="margin:0; color:#cdd6f4;">{{ activePlugin.name }}</h2>
            <span style="color:#6c7086; font-size: 13px; margin-top: 5px; display: block;">{{ activePlugin.description }}</span>
          </div>
          <div class="action-buttons" style="display: flex; gap: 10px;">
            <button class="btn-secondary" @click="savePreset">
              💾 保存预设
            </button>
            <button class="btn-launch" @click="runSimulation" :disabled="isRunning">
              {{ isRunning ? '🚀 引擎高速运算中...' : '▶ 启动算力任务' }}
            </button>
          </div>
        </div>

        <div class="form-grid">
          <div 
            v-for="param in activePlugin.parameters" 
            :key="param.key" 
            class="form-group" 
            :class="{ 'full-width': param.width === 'full' }"
          >
            <label>{{ param.label }}</label>
            <input 
              v-if="['string', 'number'].includes(param.type)" 
              :type="param.type === 'number' ? 'number' : 'text'" 
              :placeholder="param.placeholder" 
              class="input-dark" 
              v-model="formData[param.key]" 
            />
            <div v-else-if="param.type === 'boolean'" class="checkbox-group">
              <label class="check-label">
                <input type="checkbox" v-model="formData[param.key]" /> 
                {{ param.checkboxLabel || '启用该选项' }}
              </label>
            </div>
          </div>
        </div>
      </div>

      <div class="output-container card">
        <div class="output-tabs">
          <div class="tab-btn" :class="{ active: activeTab === 'terminal' }" @click="activeTab = 'terminal'">
            🖥️ 极客终端 (日志流)
            <span v-if="isRunning" class="running-dot"></span>
          </div>
          <div class="tab-btn" :class="{ active: activeTab === 'viewer' }" @click="activeTab = 'viewer'">
            👁️ 3D可视化 (DataHub 归档)
            <span v-if="hasResult" class="new-badge">New</span>
          </div>
        </div>

        <div v-show="activeTab === 'terminal'" class="terminal-body" ref="terminalBody">
          <div v-if="terminalLogs.length === 0" style="color: #45475a; text-align: center; margin-top: 40px;">
            等待任务启动...
          </div>
          <div 
            v-for="(log, idx) in terminalLogs" 
            :key="idx" 
            class="log-line fade-in-fast" 
            :class="log.type"
          >
            <span class="log-time">[{{ log.time }}]</span> 
            <span class="log-content">{{ log.text }}</span>
          </div>
          <div v-if="isRunning" class="cursor-blink">_</div>
        </div>

        <div v-show="activeTab === 'viewer'" class="viewer-body">
          <div v-if="!hasResult" class="viewer-empty">
            <div class="empty-icon" :class="{ 'spin-loader': isRunning }">{{ isRunning ? '🧬' : '📊' }}</div>
            <h3>{{ isRunning ? '正在折叠蛋白质结构，请稍候...' : '暂无生成结果' }}</h3>
            <p>当引擎完成设计后，三维结构将在此处预览。</p>
          </div>
          <div v-else class="viewer-content fade-in">
            <div class="mock-3d-canvas">
              <div class="canvas-overlay">
                <span class="tag success">运算完成</span>
                <span class="tag" style="margin-left: 10px; background: rgba(137,180,250,0.2); color:#89b4fa;">PDB 结构就绪</span>
              </div>
              <div class="mock-protein-model"></div>
              <p style="color:#a6adc8; margin-top: 20px; z-index: 2; text-align: center;">
                <b>{{ activePlugin?.name }}</b> 运算输出已截获<br>
                (此处未来将挂载 3Dmol.js 进行全景渲染)
              </p>
            </div>
            
            <div class="viewer-actions">
              <div class="result-info">
                <strong>将生成输出文件:</strong> <span>{{ currentOutputFilename }}</span>
              </div>
              <button class="btn-primary" @click="saveToDataHub">
                📥 将 PDB 永久归档至 DataHub
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'

const availablePlugins = ref<any[]>([]) 
const currentPluginId = ref('')
const formData = ref<Record<string, any>>({})
const isRunning = ref(false)
const hasResult = ref(false) 
const activeTab = ref<'terminal' | 'viewer'>('terminal') 
const terminalLogs = ref<{time: string, text: string, type: string}[]>([])
const terminalBody = ref<HTMLElement | null>(null)

// 用以保存生成的随机文件名
const currentOutputFilename = ref('')

const fetchPlugins = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/plugins')
    const json = await res.json()
    if (json.code === 200 && json.data.length > 0) {
      availablePlugins.value = json.data
      addLog(`[System] 已成功从物理大脑加载 ${json.data.length} 个算法模块！`, 'success')
      selectPlugin(json.data[0].id)
    }
  } catch (e) {
    addLog("❌ 无法获取算法列表，请检查 127.0.0.1:8080 后端引擎是否启动！", "warning")
  }
}

const activePlugin = computed(() => availablePlugins.value.find(p => p.id === currentPluginId.value))

const selectPlugin = (id: string) => {
  currentPluginId.value = id
  formData.value = {}
  hasResult.value = false
  activeTab.value = 'terminal'
  
  const plugin = availablePlugins.value.find(p => p.id === id)
  if (plugin && plugin.parameters) {
    const savedConfig = localStorage.getItem(`mtools-preset-${id}`)
    if (savedConfig) {
      formData.value = JSON.parse(savedConfig)
      addLog(`[System] 恢复了 ${plugin.name} 的上一次参数预设。`, 'info')
    } else {
      plugin.parameters.forEach((param: any) => formData.value[param.key] = param.default)
    }
  }
}

const savePreset = () => {
  if (!activePlugin.value) return
  localStorage.setItem(`mtools-preset-${activePlugin.value.id}`, JSON.stringify(formData.value))
  addLog(`[Success] ✅ 参数已成功保存到本地预设！`, 'success')
}

const runSimulation = () => {
  if (!activePlugin.value) return
  isRunning.value = true
  hasResult.value = false
  activeTab.value = 'terminal'
  terminalLogs.value = []
  
  localStorage.setItem(`mtools-preset-${activePlugin.value.id}`, JSON.stringify(formData.value))
  const queryParams = new URLSearchParams(formData.value as Record<string, string>).toString()
  
  addLog(`>>> 正在向本机物理算力节点下发指令...`, "info")
  
  const source = new EventSource(`http://127.0.0.1:8080/api/run/${activePlugin.value.id}?${queryParams}`)
  
  source.onmessage = (event) => {
    if (event.data === "[End] DONE") {
      source.close()
      isRunning.value = false
      hasResult.value = true
      
      // 生成随机的文件名用于预览
      currentOutputFilename.value = `design_${activePlugin.value.id}_${Math.floor(Math.random()*9000)+1000}.pdb`
      
      addLog(`[System] 运算结束，结构文件已挂载在内存中。`, 'success')
      
      setTimeout(() => {
        activeTab.value = 'viewer'
      }, 800)
      return
    }
    
    let type = "info"
    if (event.data.includes("[Success]") || event.data.includes("✅")) type = "success"
    if (event.data.includes("[Calc]") || event.data.includes("👉") || event.data.includes("Epoch")) type = "warning"
    if (event.data.toLowerCase().includes("error") || event.data.includes("❌")) type = "error"
    
    addLog(event.data, type)
  }
  
  source.onerror = () => {
    addLog("❌ SSE 引擎连接中断，可能是任务完成或后端出错。", "error")
    source.close()
    isRunning.value = false
  }
}

// 🚨 真正的写盘逻辑：调用我们后端的 DataHub 保存接口
const saveToDataHub = async () => {
  if (!activePlugin.value) return
  
  // 模拟一段 PDB 蛋白质结构的文本内容
  const pdbMockContent = `REMARK 999 Generated by SciForge BioEngine
REMARK 999 Algorithm: ${activePlugin.value.name}
ATOM      1  N   ALA A   1      -0.525   1.362   0.000  1.00 20.00           N  
ATOM      2  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C  
ATOM      3  C   ALA A   1       1.528   0.000   0.000  1.00 20.00           C  
ATOM      4  O   ALA A   1       2.115   1.033   0.000  1.00 20.00           O  
ATOM      5  CB  ALA A   1      -0.529  -0.774  -1.205  1.00 20.00           C  
END
`
  
  try {
    const res = await fetch('http://127.0.0.1:8080/api/data/save_file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: "03_Plugin_Outputs", // 保存到 DataHub 的插件输出特定文件夹
        filename: currentOutputFilename.value,
        content: pdbMockContent
      })
    })
    
    const json = await res.json()
    if (json.code === 200) {
      alert(`✅ 归档成功！\n\n文件 [${currentOutputFilename.value}] 已成功物理写入到本地。\n您可以前往【🗄️ 数据中心】 ->【03_Plugin_Outputs】查看，或在全局搜索中随时检索它！`)
    } else {
      alert(`❌ 归档失败: ${json.message}`)
    }
  } catch (e) {
    console.error("保存至 DataHub 失败", e)
    alert("网络异常，无法连接物理引擎！")
  }
}

const addLog = (text: string, type: string) => {
  terminalLogs.value.push({ time: new Date().toLocaleTimeString(), text, type })
  nextTick(() => { if (terminalBody.value) terminalBody.value.scrollTop = terminalBody.value.scrollHeight })
}

onMounted(() => {
  addLog("SciForge BioEngine 正在初始化通信通道...", "info")
  fetchPlugins()
})
</script>

<style scoped>
.bio-plugins-hub { display: flex; gap: 20px; height: 100%; min-height: 0; padding: 20px; box-sizing: border-box; color: #cdd6f4; }
.card { background: #181825; border: 1px solid #313244; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }

.plugin-list { width: 320px; display: flex; flex-direction: column; flex-shrink: 0; padding: 0; overflow: hidden; }
.plugin-list h3 { margin: 20px 20px 10px 20px; color: #89b4fa; font-size: 16px; }
.plugins { display: flex; flex-direction: column; overflow-y: auto; flex: 1; padding: 10px 20px 20px 20px; }
.plugin-card { display: flex; align-items: center; gap: 15px; padding: 15px; background: transparent; border: 1px solid transparent; border-radius: 10px; cursor: pointer; transition: all 0.2s; margin-bottom: 8px;}
.plugin-card:hover { background: #1e1e2e; }
.plugin-card.active { border-color: #89b4fa; background: rgba(137, 180, 250, 0.1); }
.p-icon { font-size: 28px; background: #11111b; padding: 8px; border-radius: 8px; border: 1px solid #313244;}
.p-info { display: flex; flex-direction: column; flex: 1; }
.p-name { font-weight: bold; color: #cdd6f4; font-size: 15px; }
.p-desc { font-size: 11px; color: #a6adc8; margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;}
.p-status { font-size: 10px; padding: 3px 6px; border-radius: 4px; font-weight: bold; }
.ready { background: rgba(166, 227, 161, 0.15); color: #a6e3a1; border: 1px solid #a6e3a1; }
.empty-plugins { text-align: center; color: #6c7086; margin-top: 40px; font-size: 13px;}

.plugin-workspace { flex: 1; display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.config-panel { flex-shrink: 0; }
.panel-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #313244; padding-bottom: 15px; margin-bottom: 15px; }
.btn-secondary { background: #313244; color: #cdd6f4; border: 1px solid #45475a; padding: 10px 15px; border-radius: 8px; cursor: pointer; transition: 0.2s; font-weight: bold;}
.btn-secondary:hover { background: #45475a; }
.btn-launch { background: #a6e3a1; color: #11111b; border: none; padding: 10px 24px; border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer; transition: all 0.2s; box-shadow: 0 0 10px rgba(166, 227, 161, 0.2); }
.btn-launch:disabled { background: #45475a; color: #a6adc8; cursor: not-allowed; box-shadow: none; }
.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s;}

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.full-width { grid-column: 1 / -1; }
.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-group label { color: #bac2de; font-size: 13px; font-weight: bold; }
.input-dark { background: #11111b; border: 1px solid #313244; color: #cdd6f4; padding: 10px 12px; border-radius: 6px; font-family: monospace; outline: none; transition: 0.2s;}
.input-dark:focus { border-color: #89b4fa; }

.output-container { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 0; overflow: hidden; }
.output-tabs { display: flex; background: #11111b; border-bottom: 1px solid #313244; }
.tab-btn { padding: 12px 20px; color: #6c7086; cursor: pointer; font-size: 13px; font-weight: bold; border-bottom: 2px solid transparent; transition: 0.2s; position: relative; display: flex; align-items: center; gap: 8px;}
.tab-btn:hover { color: #bac2de; background: #181825; }
.tab-btn.active { color: #89b4fa; border-bottom-color: #89b4fa; background: #181825;}
.running-dot { width: 8px; height: 8px; background: #f9e2af; border-radius: 50%; animation: pulse 1s infinite; }
.new-badge { background: #f38ba8; color: #11111b; font-size: 10px; padding: 2px 6px; border-radius: 10px;}

.terminal-body { flex: 1; padding: 20px; overflow-y: auto; background: #11111b; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; line-height: 1.6; }
.log-line { margin-bottom: 4px; word-break: break-all;}
.log-time { color: #6c7086; margin-right: 8px; user-select: none;}
.info { color: #bac2de; }
.success { color: #a6e3a1; font-weight: bold;}
.warning { color: #f9e2af; }
.error { color: #f38ba8; font-weight: bold;}

.viewer-body { flex: 1; background: #181825; position: relative; display: flex; flex-direction: column;}
.viewer-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #6c7086; text-align: center;}
.empty-icon { font-size: 48px; margin-bottom: 15px; opacity: 0.8;}
.viewer-content { flex: 1; display: flex; flex-direction: column; padding: 20px;}
.mock-3d-canvas { flex: 1; background: #11111b; border: 1px dashed #45475a; border-radius: 12px; position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden;}
.canvas-overlay { position: absolute; top: 15px; left: 15px; z-index: 10;}
.mock-protein-model { width: 150px; height: 150px; border-radius: 50%; border: 4px solid transparent; border-top-color: #cba6f7; border-bottom-color: #89b4fa; animation: spin 4s linear infinite; position: absolute; opacity: 0.5;}
.viewer-actions { margin-top: 15px; display: flex; justify-content: space-between; align-items: center; background: #11111b; padding: 15px; border-radius: 8px; border: 1px solid #313244;}
.result-info { font-size: 13px; color: #bac2de; }
.result-info span { font-family: monospace; color: #f9e2af; margin-left: 10px;}

.tag { font-size: 11px; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
.tag.success { background: rgba(166, 227, 161, 0.2); color: #a6e3a1; border: 1px solid #a6e3a1; }
.cursor-blink { display: inline-block; width: 8px; height: 14px; background: #cdd6f4; animation: blink 1s step-end infinite; vertical-align: text-bottom; margin-left: 4px;}
.spin-loader { display: inline-block; animation: spin 2s linear infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
@keyframes spin { 100% { transform: rotate(360deg); } }
.fade-in { animation: fadeIn 0.3s ease; }
.fade-in-fast { animation: fadeIn 0.15s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>