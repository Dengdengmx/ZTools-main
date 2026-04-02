<template>
  <div class="data-hub-view">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 @click="navigateTo('')" :class="{ active: currentPath === '' }">🗄️ 内部数据中心 (DataHub)</h2>
        <template v-if="currentPath">
          <span class="separator">/</span>
          <h2 class="active">{{ currentPath }}</h2>
        </template>
      </div>
      <div class="header-actions">
        <button class="btn-outline" style="color: #cba6f7; border-color: #cba6f7;" @click="triggerGlobalSearch">🔍 全局智能检索</button>
        <button class="btn-primary" @click="fetchDirectory(currentPath)">🔄 刷新物理目录</button>
      </div>
    </div>

    <div class="split-layout">
      <div class="sidebar card">
        <h3 style="margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 15px; color: #89b4fa;">📊 数据分布</h3>
        <div class="stat-list">
          <div class="stat-item" @click="navigateTo('02_Structures')">
            <span class="s-icon bg-protein">🧬</span>
            <div class="s-info"><div class="s-name">PDB 结构文件</div><div class="s-desc">3D 坐标与构象</div></div>
          </div>
          <div class="stat-item" @click="navigateTo('01_Sequences')">
            <span class="s-icon bg-plasmid">📜</span>
            <div class="s-info"><div class="s-name">Fasta 序列</div><div class="s-desc">DNA / 蛋白原序列</div></div>
          </div>
          <div class="stat-item" @click="navigateTo('03_Plugin_Outputs')">
            <span class="s-icon bg-cell">⚙️</span>
            <div class="s-info"><div class="s-name">引擎演算结果</div><div class="s-desc">RFdiffusion 等产出</div></div>
          </div>
          <div class="stat-item" @click="navigateTo('04_Reports')">
            <span class="s-icon bg-default">📊</span>
            <div class="s-info"><div class="s-name">实验报告与图表</div><div class="s-desc">PDF / PNG 等归档</div></div>
          </div>
        </div>
        
        <div class="storage-info">
          <span>物理挂载点:</span>
          <span style="color: #a6adc8; font-family: monospace; font-size: 11px;">/SciForge_Workspace/SciForge_Data</span>
        </div>
      </div>

      <div class="explorer-workspace card">
        <div class="explorer-toolbar">
          <button class="icon-btn" @click="goUp" :disabled="!currentPath">⬆️ 返回上级</button>
          <div class="path-bar">{{ currentPath || '根目录 (Root)' }}</div>
          <button class="btn-outline btn-small" @click="alert('请直接在系统文件夹中粘贴文件，DataHub会自动识别')">+ 导入外部文件</button>
        </div>

        <div class="file-list-header">
          <div class="col-name">名称</div>
          <div class="col-date">修改日期</div>
          <div class="col-size">大小</div>
        </div>

        <div class="file-list-body">
          <div v-if="files.length === 0" class="empty-state">
            <div style="font-size: 48px; opacity: 0.5;">📭</div>
            <p>该目录下暂无文件，您可以跑一次 RFdiffusion 试试看！</p>
          </div>
          
          <div 
            v-for="(file, idx) in files" 
            :key="idx" 
            class="file-item fade-in"
            @dblclick="handleDoubleClick(file)"
          >
            <div class="col-name">
              <span class="file-icon">{{ getFileIcon(file) }}</span>
              <span class="file-name" :class="{ 'is-dir': file.is_dir }">{{ file.name }}</span>
            </div>
            <div class="col-date">{{ file.modified }}</div>
            <div class="col-size">{{ formatSize(file.size, file.is_dir) }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="previewFile" class="modal-overlay fade-in">
      <div class="modal-content card preview-modal">
        <div class="preview-header">
          <div class="preview-title">
            <span class="file-icon">{{ getFileIcon(previewFile) }}</span>
            <div style="display: flex; flex-direction: column;">
              <span style="font-size: 16px; font-weight: bold; color: #cdd6f4;">{{ previewFile.name }}</span>
              <span style="font-size: 12px; color: #a6adc8;">{{ currentPath }}/{{ previewFile.name }} • {{ formatSize(previewFile.size, false) }}</span>
            </div>
          </div>
          <div class="preview-actions">
            <button class="btn-primary" v-if="['.pdb', '.cif'].includes(previewFile.ext) && !is3DMode" @click="init3DViewer">
              👁️ 启动 3D 渲染器
            </button>
            <button class="btn-outline" style="border-color: #89b4fa; color: #89b4fa;" v-if="is3DMode" @click="is3DMode = false">
              📄 退出 3D 回到源代码
            </button>
            <button class="icon-btn" style="background: transparent; font-size: 20px;" @click="closePreview">✖</button>
          </div>
        </div>

        <div class="preview-body">
          <div v-if="isPreviewLoading" class="loading-state">
            <span class="spin-loader">⚙️</span> 正在从物理硬盘加载数据...
          </div>
          
          <div v-else-if="previewError" class="error-state">
            <span style="font-size: 32px; margin-bottom: 15px; display: block;">⚠️</span>
            {{ previewError }}
          </div>

          <div v-else-if="is3DMode" class="viewer-3d-wrapper fade-in">
             <div v-if="is3DLoadingEngine" class="loading-state" style="position: absolute; width: 100%; height: 100%; z-index: 10;">
               <span class="spin-loader">🧬</span> 正在动态挂载 3Dmol.js WebGL 引擎...
             </div>
             
             <div id="viewer-3d" style="width: 100%; height: 100%; position: relative;"></div>
             
             <div class="viewer-3d-tools" v-if="viewerInstance">
                <button class="tool-btn" @click="set3DStyle('cartoon')">🌈 Cartoon (卡通模型)</button>
                <button class="tool-btn" @click="set3DStyle('sphere')">☁️ Surface (表面电荷)</button>
                <button class="tool-btn" @click="set3DStyle('stick')">🥢 Stick (球棍残基)</button>
             </div>
          </div>

          <div v-else class="code-editor-container fade-in">
            <div class="line-numbers">
              <div v-for="n in lineCount" :key="n" class="line-number">{{ n }}</div>
            </div>
            <pre class="code-content"><code :class="getHighlightClass(previewFile.ext)">{{ previewContent }}</code></pre>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'

const currentPath = ref('')
const files = ref<any[]>([])

// 预览状态
const previewFile = ref<any>(null)
const previewContent = ref('')
const isPreviewLoading = ref(false)
const previewError = ref('')

// 🚨 3D 渲染器核心状态
const is3DMode = ref(false)
const is3DLoadingEngine = ref(false)
const viewerInstance = ref<any>(null)

// 拉取文件列表
const fetchDirectory = async (path: string = "") => {
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/data/tree?path=${encodeURIComponent(path)}`)
    const json = await res.json()
    if (json.code === 200) {
      files.value = json.data
      currentPath.value = json.current_path
    }
  } catch (e) {
    console.error("无法读取 DataHub 目录", e)
  }
}

const navigateTo = (path: string) => { fetchDirectory(path) }

const goUp = () => {
  if (!currentPath.value) return
  const parts = currentPath.value.split('/')
  parts.pop()
  fetchDirectory(parts.join('/'))
}

// 双击文件读取内容
const handleDoubleClick = async (file: any) => {
  if (file.is_dir) {
    fetchDirectory(file.path)
    return
  }
  
  previewFile.value = file
  previewContent.value = ''
  previewError.value = ''
  isPreviewLoading.value = true
  is3DMode.value = false // 默认先打开纯文本

  try {
    const res = await fetch(`http://127.0.0.1:8080/api/data/read_file?path=${encodeURIComponent(file.path)}`)
    const json = await res.json()
    
    if (json.code === 200) {
      previewContent.value = json.data
    } else {
      previewError.value = json.message || "文件无法以纯文本方式解析。"
    }
  } catch (e) {
    previewError.value = "后端引擎连接断开，无法读取文件。"
  } finally {
    isPreviewLoading.value = false
  }
}

const closePreview = () => {
  previewFile.value = null
  previewContent.value = ''
  is3DMode.value = false
  if (viewerInstance.value) {
    viewerInstance.value.clear()
    viewerInstance.value = null
  }
}

// ==========================================
// 🚨 核心：3Dmol.js 引擎加载与渲染逻辑
// ==========================================
const init3DViewer = async () => {
  is3DMode.value = true
  is3DLoadingEngine.value = true
  
  // 1. 动态注入 3Dmol.js CDN 脚本 (如果还未加载)
  if (!(window as any).$3Dmol) {
    await new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.0.4/3Dmol-min.js'
      script.onload = resolve
      script.onerror = reject
      document.head.appendChild(script)
    })
  }
  
  is3DLoadingEngine.value = false

  // 2. 初始化 WebGL 画布并渲染结构
  nextTick(() => {
    const element = document.getElementById('viewer-3d')
    const $3Dmol = (window as any).$3Dmol
    
    if (element && $3Dmol) {
      // 创建 Viewer，背景设为契合我们 UI 的暗色
      viewerInstance.value = $3Dmol.createViewer(element, {
        backgroundColor: '#1e1e2e'
      })
      
      // 去除后缀的点（例如 .pdb -> pdb）
      const format = previewFile.value.ext.replace('.', '')
      viewerInstance.value.addModel(previewContent.value, format)
      
      // 默认设置为基于残基性质光谱着色的卡通模型
      viewerInstance.value.setStyle({}, { cartoon: { color: 'spectrum' } })
      viewerInstance.value.zoomTo()
      viewerInstance.value.render()
    }
  })
}

// 动态切换 3D 显示样式
const set3DStyle = (styleType: 'cartoon' | 'sphere' | 'stick') => {
  if (!viewerInstance.value) return
  
  viewerInstance.value.setStyle({}, {}) // 先清除样式
  
  if (styleType === 'cartoon') {
    viewerInstance.value.setStyle({}, { cartoon: { color: 'spectrum' } })
  } else if (styleType === 'sphere') {
    // 表面电荷/实体球状模型
    viewerInstance.value.setStyle({}, { sphere: { color: 'chain' } }) 
  } else if (styleType === 'stick') {
    // 细致的原子球棍模型
    viewerInstance.value.setStyle({}, { stick: {} })
  }
  
  viewerInstance.value.render()
}
// ==========================================

const lineCount = computed(() => {
  if (!previewContent.value) return 0
  return previewContent.value.split('\n').length
})

const getHighlightClass = (ext: string) => {
  ext = ext.toLowerCase()
  if (ext === '.pdb' || ext === '.cif') return 'lang-pdb'
  if (ext === '.fasta' || ext === '.fa') return 'lang-fasta'
  if (ext === '.json') return 'lang-json'
  return 'lang-plaintext'
}

const triggerGlobalSearch = async () => {
  const keyword = prompt("全局搜索 (支持搜 样本名 或 DataHub文件名):")
  if(!keyword) return
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/search/omnibar?q=${keyword}`)
    const json = await res.json()
    let msg = json.message + "\n\n"
    json.data.forEach((d:any) => msg += `[${d.module}] ${d.icon} ${d.title}\n${d.desc}\n\n`)
    alert(msg)
  } catch (e) {}
}

const getFileIcon = (file: any) => {
  if (file.is_dir) return "📁"
  const ext = file.ext.toLowerCase()
  if (['.pdb', '.cif'].includes(ext)) return "🧬"
  if (['.fasta', '.fa', '.seq'].includes(ext)) return "📜"
  if (['.png', '.jpg', '.pdf'].includes(ext)) return "📊"
  if (['.json', '.csv', '.txt'].includes(ext)) return "📋"
  return "📄"
}

const formatSize = (bytes: number, isDir: boolean) => {
  if (isDir) return "--"
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

onMounted(() => {
  fetchDirectory("")
})
</script>

<style scoped>
/* 基础样式 (继承) */
.data-hub-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4;}
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086; cursor: pointer; transition: 0.2s;}
.breadcrumbs h2:hover { color: #b4befe;}
.breadcrumbs h2.active { color: #89b4fa; font-weight: bold;}
.separator { color: #45475a; font-weight: bold;}

.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.btn-primary:hover { background: #b4befe; }
.btn-outline { background: transparent; border: 1px dashed; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; margin-right: 10px;}
.btn-small { padding: 6px 12px; font-size: 12px; color: #a6adc8; border-color: #45475a;}

.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}
.card { background: #181825; border: 1px solid #313244; border-radius: 12px;}

/* 左侧边栏 */
.sidebar { flex: 1; max-width: 280px; display: flex; flex-direction: column; padding: 20px; }
.stat-list { display: flex; flex-direction: column; gap: 15px; flex: 1;}
.stat-item { display: flex; align-items: center; gap: 15px; padding: 12px; background: #11111b; border-radius: 8px; border: 1px solid transparent; cursor: pointer; transition: 0.2s;}
.stat-item:hover { border-color: #89b4fa; background: #1e1e2e;}
.s-icon { font-size: 20px; width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center;}
.bg-protein { background: rgba(166, 227, 161, 0.2); border: 1px solid #a6e3a1; }
.bg-plasmid { background: rgba(249, 226, 175, 0.2); border: 1px solid #f9e2af; }
.bg-cell { background: rgba(203, 166, 247, 0.2); border: 1px solid #cba6f7; }
.bg-default { background: rgba(137, 180, 250, 0.2); border: 1px solid #89b4fa; }
.s-info { display: flex; flex-direction: column; }
.s-name { font-weight: bold; font-size: 14px; color: #cdd6f4;}
.s-desc { font-size: 11px; color: #6c7086; margin-top: 4px;}
.storage-info { margin-top: auto; padding-top: 15px; border-top: 1px dashed #313244; font-size: 12px; color: #6c7086; display: flex; flex-direction: column; gap: 5px;}

/* 右侧资源管理器 */
.explorer-workspace { flex: 3; display: flex; flex-direction: column; overflow: hidden; background: #11111b;}
.explorer-toolbar { padding: 15px 20px; border-bottom: 1px solid #313244; display: flex; align-items: center; gap: 15px; background: #181825;}
.icon-btn { background: #313244; border: none; color: #cdd6f4; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px;}
.icon-btn:disabled { opacity: 0.5; cursor: not-allowed;}
.path-bar { flex: 1; background: #11111b; border: 1px solid #313244; padding: 6px 12px; border-radius: 6px; font-family: monospace; font-size: 13px; color: #a6adc8;}

.file-list-header { display: flex; padding: 10px 20px; font-size: 12px; font-weight: bold; color: #6c7086; border-bottom: 1px solid #313244; background: #181825;}
.col-name { flex: 3; }
.col-date { flex: 1; }
.col-size { flex: 1; text-align: right; }

.file-list-body { flex: 1; overflow-y: auto;}
.file-item { display: flex; align-items: center; padding: 12px 20px; border-bottom: 1px solid #1e1e2e; cursor: pointer; transition: 0.1s;}
.file-item:hover { background: rgba(137, 180, 250, 0.1);}
.file-icon { margin-right: 10px; font-size: 18px;}
.file-name { font-size: 14px; color: #bac2de;}
.file-name.is-dir { color: #89b4fa; font-weight: bold;}
.empty-state { text-align: center; padding: 60px 20px; color: #6c7086;}

/* ================= 🚨 预览弹窗核心样式 ================= */
.modal-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(17, 17, 27, 0.8); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.preview-modal { width: 85%; height: 85%; max-width: 1200px; display: flex; flex-direction: column; overflow: hidden; border: 1px solid #89b4fa; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
.preview-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: #11111b; border-bottom: 1px solid #313244; flex-shrink: 0;}
.preview-title { display: flex; align-items: center; gap: 15px;}
.preview-actions { display: flex; align-items: center; gap: 15px;}

.preview-body { flex: 1; background: #1e1e2e; position: relative; display: flex; overflow: hidden; }
.loading-state, .error-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #6c7086; font-size: 16px; }
.error-state { color: #f38ba8; }

/* 🚨 3D Viewer 专属样式 */
.viewer-3d-wrapper { flex: 1; width: 100%; height: 100%; position: relative; background: #1e1e2e; }
.viewer-3d-tools {
  position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
  display: flex; gap: 10px; background: rgba(17, 17, 27, 0.8); padding: 10px; border-radius: 12px; border: 1px solid #45475a; z-index: 100;
}
.tool-btn {
  background: transparent; color: #cdd6f4; border: 1px solid #45475a; padding: 8px 15px; border-radius: 6px; cursor: pointer; transition: 0.2s; font-size: 13px; font-weight: bold;
}
.tool-btn:hover { background: #89b4fa; color: #11111b; border-color: #89b4fa;}

.code-editor-container { flex: 1; display: flex; overflow: auto; background: #1e1e2e; }
.line-numbers { padding: 20px 10px; background: #11111b; border-right: 1px solid #313244; text-align: right; color: #45475a; font-family: 'Consolas', monospace; font-size: 13px; user-select: none;}
.line-number { line-height: 1.5; }
.code-content { margin: 0; padding: 20px; color: #cdd6f4; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; line-height: 1.5; white-space: pre; flex: 1;}

.lang-pdb { color: #f9e2af; }   
.lang-fasta { color: #a6e3a1; } 
.lang-json { color: #89b4fa; }  

.spin-loader { display: inline-block; animation: spin 2s linear infinite; font-size: 24px; margin-bottom: 15px;}
@keyframes spin { 100% { transform: rotate(360deg); } }
.fade-in { animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
</style>