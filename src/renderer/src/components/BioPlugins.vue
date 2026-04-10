<template>
  <div class="plugin-engine-view fade-in">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 class="active" style="cursor: default;">🚀 动态算力引擎</h2>
        <span class="separator">/</span>
        <select v-model="activePluginId" @change="onPluginChange" class="plugin-selector allow-select">
          <option value="" disabled>-- 请选择加载的算力模块 --</option>
          <option v-for="p in plugins" :key="p.id" :value="p.id">{{ p.icon }} {{ p.name }}</option>
        </select>
      </div>
      <div class="header-actions">
        <button class="btn-outline btn-small" @click="fetchPlugins" title="重新扫描并加载本地算法">
          <span style="margin-right:4px;">🔄</span> 刷新算法库
        </button>
      </div>
    </div>

    <div class="split-layout">
      <div class="plugin-workspace" v-if="activePlugin">
        <div class="lego-container" :style="{ flexDirection: currentLayout.direction || 'row' }">
          
          <div v-for="(block, bIdx) in currentLayout.blocks" :key="'root-'+bIdx" 
               class="lego-block card fade-in"
               :style="{ flex: block.flex || 'none', width: block.width || 'auto' }">
               
             <div v-if="block.type === 'tabs'" class="lego-tabs">
                <div class="tabs-header custom-scrollbar-hide">
                  <button v-for="(pane, pIdx) in block.panes" :key="pIdx"
                          class="tab-btn" :class="{ active: getActiveTab(bIdx) === pIdx }"
                          @click="setActiveTab(bIdx, pIdx)">
                    {{ pane.title }}
                  </button>
                </div>
                <div class="tabs-body">
                   <template v-for="(pane, pIdx) in block.panes" :key="'pane-'+pIdx">
                      <div v-show="getActiveTab(bIdx) === pIdx" class="tab-pane-content">
                        <div v-if="pane.type === 'form'" class="lego-inner-form">
                           <FormRenderer :schema="activePlugin.parameters" :formData="formData" :pluginLayout="currentLayout" :isRunning="isRunning" :autoRender="autoRender" @update:autoRender="autoRender = $event" @execute="executePlugin"/>
                        </div>
                        <div v-else-if="pane.type === 'terminal'" class="lego-inner-terminal">
                           <TerminalRenderer :logs="logs" :isRunning="isRunning"/>
                        </div>
                        <div v-else-if="pane.type === 'preview'" class="lego-inner-preview">
                           <PreviewRenderer :path="cleanOutputPath" :outputPaths="sessionOutputPaths" :is3DLoading="is3DLoading" :viewerInstance="viewerInstance" @init3D="init3DViewer"/>
                        </div>
                        <div v-else-if="pane.type === 'table'" class="lego-inner-table">
                           <TableRenderer :tableData="resultTable" :isLoading="isTableLoading"/>
                        </div>
                        <div v-else-if="pane.type === 'code'" class="lego-inner-code">
                           <CodeRenderer :code="resultCode" :isLoading="isCodeLoading" :path="currentCodePath"/>
                        </div>
                        <div v-else-if="pane.type === 'metrics'" class="lego-inner-metrics">
                           <MetricsRenderer :metrics="resultMetrics"/>
                        </div>
                        <div v-else-if="pane.type === 'export'" class="lego-inner-export">
                           <ExportRenderer :outputPaths="sessionOutputPaths" :pluginName="activePlugin.id" />
                        </div>
                      </div>
                   </template>
                </div>
             </div>

             <template v-else>
                <div v-if="block.type === 'form'" class="lego-inner-form">
                   <div class="zone-title" style="margin-bottom: 15px;">🎛️ 算法参数配置</div>
                   <FormRenderer :schema="activePlugin.parameters" :formData="formData" :pluginLayout="currentLayout" :isRunning="isRunning" :autoRender="autoRender" @update:autoRender="autoRender = $event" @execute="executePlugin"/>
                </div>
                <div v-else-if="block.type === 'export'" class="lego-inner-export">
                   <div class="zone-title" style="margin-bottom: 15px;">📤 多维结果归档</div>
                   <ExportRenderer :outputPaths="sessionOutputPaths" :pluginName="activePlugin.id"/>
                </div>
             </template>
          </div>

        </div>
      </div>
      
      <div v-else class="plugin-workspace card" style="align-items: center; justify-content: center; border-style: dashed;">
        <span style="font-size: 48px; opacity: 0.3;">🚀</span>
        <h3 style="color: #6c7086; margin-top: 20px;">请在顶部下拉框选择一个算力核心</h3>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch, onUnmounted } from 'vue'

const BASE_API = 'http://127.0.0.1:8080/api'

const plugins = ref<any[]>([])
const activePluginId = ref('')
const activePlugin = ref<any>(null)
const formData = ref<Record<string, any>>({})
const isRunning = ref(false)

const logs = ref<string[]>([])
const rawOutputMedia = ref('')
const resultTable = ref<string[][]>([])
const isTableLoading = ref(false)
const resultCode = ref('')
const isCodeLoading = ref(false)
const currentCodePath = ref('')
const resultMetrics = ref<Record<string, any>>({})
const sessionOutputPaths = ref<string[]>([]) 

const autoRender = ref(false)
let renderTimeout: any = null
let activeEventSource: any = null;

watch(formData, () => {
  if (autoRender.value && !isRunning.value) {
    if (renderTimeout) clearTimeout(renderTimeout)
    renderTimeout = setTimeout(() => { executePlugin() }, 300) 
  }
}, { deep: true })

const defaultLayout = {
  direction: 'row',
  blocks: [
    { type: 'form', width: '380px', height: '100%' },
    { type: 'tabs', flex: '1', height: '100%', panes: [
        { title: '👁️ 预览区', type: 'preview' },
        { title: '💻 终端', type: 'terminal' }
    ]}
  ]
}

const currentLayout = computed(() => {
  if (activePlugin.value && activePlugin.value.layout) return activePlugin.value.layout
  return defaultLayout
})

const tabStates = ref<Record<number, number>>({})
const getActiveTab = (blockIndex: number) => tabStates.value[blockIndex] || 0
const setActiveTab = (blockIndex: number, paneIndex: number) => { tabStates.value[blockIndex] = paneIndex }

const fetchPlugins = async () => {
  try {
    const res = await fetch(`${BASE_API}/plugins`)
    const json = await res.json()
    if (json.code === 200) {
      plugins.value = json.data
      if (plugins.value.length > 0 && !activePlugin.value) {
        activePluginId.value = plugins.value[0].id
        onPluginChange()
      }
    }
  } catch (e) { console.error(e) }
}

const onPluginChange = () => {
  const p = plugins.value.find(x => x.id === activePluginId.value)
  if (p) selectPlugin(p)
}

const selectPlugin = (plugin: any) => {
  if (isRunning.value) return alert("有任务正在运行！")
  activePlugin.value = plugin
  tabStates.value = {}
  resetDataPonds()
  
  const defaultData: Record<string, any> = {}
  plugin.parameters.forEach((p: any) => { defaultData[p.key] = p.default !== undefined ? p.default : '' })
  formData.value = defaultData
}

const resetDataPonds = () => {
  logs.value = []
  rawOutputMedia.value = ''
  resultTable.value = []
  resultCode.value = ''
  currentCodePath.value = ''
  resultMetrics.value = {}
  sessionOutputPaths.value = []
  if (viewerInstance.value) { viewerInstance.value.clear(); viewerInstance.value = null }
}

const handleGlobalKeyDown = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd') {
    e.preventDefault();
    try {
      if ((window as any).electron?.ipcRenderer) {
        (window as any).electron.ipcRenderer.send('window-action', 'detach');
      }
    } catch (err) {
      console.error("分离窗口唤起失败:", err);
    }
  }
}

const executePlugin = async (actionId?: any) => {
  if (actionId === 'abort') {
      if (activeEventSource) {
          activeEventSource.close()
          activeEventSource = null
      }
      isRunning.value = false;
      logs.value.push("🛑 正在强行切断本地推流监听，并向远端下发 kill 狙击指令...");
  } else {
      if (isRunning.value) return; 
      isRunning.value = true;
  }
  
  if (typeof actionId !== 'string' || actionId === 'compile' || actionId === 'check_gpu') {
      logs.value = []
      if (actionId === 'compile') resultCode.value = ''
  }
  
  let finalFormData = { ...formData.value }

  if (typeof actionId === 'string') {
      finalFormData['action'] = actionId
  }

  for (const param of activePlugin.value.parameters) {
     if (param.type === 'textarea' && finalFormData[param.key]) {
         const content = finalFormData[param.key].trim()
         if (content && !content.startsWith('.cache/')) {
             const tempFilename = `temp_matrix_${Date.now()}.txt`
             try {
                const res = await fetch(`${BASE_API}/data/save_file`, {
                   method: 'POST', headers: { 'Content-Type': 'application/json' },
                   body: JSON.stringify({ path: '.cache', filename: tempFilename, content: content })
                });
                if (!res.ok) throw new Error(`后端落盘接口失效`);
                finalFormData[param.key] = `.cache/${tempFilename}`
             } catch(e:any) { 
                 logs.value.push(`❌ 前端缓存失败: ${e.message}`);
                 isRunning.value = false; return;
             }
         }
     }
  }
  
  const params = new URLSearchParams()
  for (const [key, val] of Object.entries(finalFormData)) { params.append(key, String(val)) }

  const es = new EventSource(`${BASE_API}/run/${activePlugin.value.id}?${params.toString()}`)
  activeEventSource = es 

  es.onmessage = async (event) => {
    const data = event.data
    if (data.includes('[OutputFile]')) {
      const p = data.split('[OutputFile]')[1].trim()
      rawOutputMedia.value = p
      if(!sessionOutputPaths.value.includes(p)) sessionOutputPaths.value.push(p)
      if (is3DFile(cleanOutputPath.value)) await init3DViewer()
    } 
    else if (data.includes('[OutputTable]')) {
      const p = data.split('[OutputTable]')[1].trim()
      if(!sessionOutputPaths.value.includes(p)) sessionOutputPaths.value.push(p)
      fetchTableData(p)
    }
    else if (data.includes('[OutputCode]')) {
      fetchCodeData(data.split('[OutputCode]')[1].trim())
    }
    else if (data.includes('[OutputMetrics]')) {
      try { 
          const newMetrics = JSON.parse(data.split('[OutputMetrics]')[1].trim());
          resultMetrics.value = { ...resultMetrics.value, ...newMetrics };
      } catch(e){}
    }
    else if (data === '[End] DONE') {
      if (activeEventSource === es) {
          isRunning.value = false;
          activeEventSource = null;
      }
      es.close()
    } 
    else {
      logs.value.push(data)
      nextTick(() => {
        const terminal = document.getElementById('terminal-output')
        if (terminal) terminal.scrollTop = terminal.scrollHeight
      })
    }
  }
  es.onerror = () => { 
      logs.value.push("❌ [Network] 算力引擎连接中断")
      if (activeEventSource === es) {
          isRunning.value = false;
          activeEventSource = null;
      }
      es.close() 
  }
}

const cleanOutputPath = computed(() => {
  if (!rawOutputMedia.value) return ''
  let p = rawOutputMedia.value.replace(/\\/g, '/')
  const marker = 'SciForge_Data/'
  const idx = p.indexOf(marker)
  if (idx !== -1) p = p.substring(idx + marker.length)
  if (p.startsWith('./')) p = p.substring(2)
  return p
})

const fetchTableData = async (relPath: string) => {
  isTableLoading.value = true
  try {
    const res = await fetch(`${BASE_API}/data/read_file?path=${encodeURIComponent(relPath)}`)
    const json = await res.json()
    if (json.code === 200) {
      const rows = json.data.trim().split('\n')
      resultTable.value = rows.map((r: string) => r.split(/[\t,]/)) 
    }
  } catch (e) {} finally { isTableLoading.value = false }
}

const fetchCodeData = async (relPath: string) => {
  isCodeLoading.value = true
  currentCodePath.value = relPath
  try {
    const res = await fetch(`${BASE_API}/data/read_file?path=${encodeURIComponent(relPath)}`)
    const json = await res.json()
    if (json.code === 200) resultCode.value = json.data
  } catch (e) {} finally { isCodeLoading.value = false }
}

const is3DFile = (path: string) => ['.pdb', '.cif'].some(ext => path.toLowerCase().endsWith(ext))
const is3DLoading = ref(false)
const viewerInstance = ref<any>(null)
const init3DViewer = async () => { /* 略 */ }

onMounted(() => { 
  fetchPlugins();
  window.addEventListener('keydown', handleGlobalKeyDown);
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeyDown);
})
</script>

<script lang="ts">
import { defineComponent, PropType } from 'vue'

export const FormRenderer = defineComponent({
  props: { schema: Array as PropType<any[]>, formData: Object as PropType<any>, pluginLayout: Object as PropType<any>, isRunning: Boolean, autoRender: Boolean },
  data() { return { isDragOver: {} as Record<string, boolean> } },
  methods: {
    async handleDrop(e: DragEvent, key: string) {
      this.isDragOver[key] = false;
      const files = e.dataTransfer?.files;
      if (files && files.length > 0) await this.uploadFiles(files, key);
    },
    async handleSelect(e: Event, key: string) {
      const target = e.target as HTMLInputElement;
      const files = target?.files;
      if (files && files.length > 0) await this.uploadFiles(files, key);
    },
    async uploadFiles(files: FileList | any[], key: string) {
       const uploadedPaths: string[] = [];
       for(let i=0; i<files.length; i++) {
           const fd = new FormData();
           fd.append('path', '.cache'); 
           fd.append('file', files[i]);
           try {
             await fetch('http://127.0.0.1:8080/api/data/upload', { method: 'POST', body: fd });
             uploadedPaths.push('.cache/' + files[i].name);
           } catch(err) { alert(`文件 ${files[i].name} 上传失败！`); }
       }
       const existing = this.formData[key] ? this.formData[key].split(',').filter(x=>x) : [];
       this.formData[key] = [...existing, ...uploadedPaths].join(',');
    },
    clearFiles(key: string) {
       this.formData[key] = ''; 
       const inputRef = this.$refs['file_' + key] as any;
       if (inputRef && inputRef[0]) {
           inputRef[0].value = ''; 
       }
    }
  },
  template: `
    <div style="position:relative; height:100%; width:100%; display:flex; flex-direction:column; overflow:hidden;">
      <div class="custom-scrollbar" style="flex:1; overflow-y:auto; padding-right:10px;">
        <div style="display:grid; grid-template-columns:repeat(12, 1fr); gap:12px; padding-bottom:15px; align-content:start;">
          <div v-for="param in schema" :key="param.key" :style="{ gridColumn: 'span ' + (param.span || 12) }" style="display:flex; flex-direction:column; justify-content: center;">
            <label v-if="param.type === 'boolean'" style="display:flex; align-items:center; gap:8px; cursor:pointer; height:100%; padding-top:20px;">
              <input type="checkbox" v-model="formData[param.key]" style="width:14px; height:14px; accent-color:#89b4fa; cursor:pointer; margin:0; flex-shrink:0;">
              <span style="font-size:12px; color:#bac2de; font-weight:bold; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" :title="'--'+param.key">{{ param.label }}</span>
            </label>
            <template v-else>
               <label style="font-size:12px; color:#bac2de; font-weight:bold; margin-bottom:6px;" :title="'--'+param.key">{{ param.label }}</label>
               
               <div v-if="param.type === 'file'"
                    @dragover.prevent="isDragOver[param.key] = true"
                    @dragleave.prevent="isDragOver[param.key] = false"
                    @drop.prevent="handleDrop($event, param.key)"
                    :style="{ border: isDragOver[param.key] ? '1px dashed #89b4fa' : '1px dashed #45475a', background: isDragOver[param.key] ? 'rgba(137,180,250,0.1)' : '#11111b' }"
                    style="position:relative; padding:15px; text-align:center; border-radius:8px; cursor:pointer; color:#a6adc8; font-size:11px; transition:0.2s;"
                    @click="$refs['file_'+param.key][0].click()">
                  
                  <span v-if="formData[param.key] && formData[param.key].includes(',')" style="color:#a6e3a1; font-weight:bold;">
                    ✅ 已加入 {{ formData[param.key].split(',').filter(x=>x).length }} 个待处理文件
                  </span>
                  <span v-else-if="formData[param.key]" style="color:#a6e3a1; font-weight:bold;">✅ {{ formData[param.key].split('/').pop() }}</span>
                  <span v-else>📁 框选或拖拽多个文件到此处</span>
                  
                  <input type="file" :ref="'file_'+param.key" style="display:none" multiple @change="handleSelect($event, param.key)" />

                  <button v-if="formData[param.key]" 
                          @click.stop="clearFiles(param.key)"
                          style="position:absolute; right:8px; top:8px; background:rgba(243,139,168,0.1); border:1px solid #f38ba8; border-radius:4px; color:#f38ba8; cursor:pointer; font-size:10px; padding:2px 8px; transition:0.2s;"
                          title="清空已选择的文件">清空</button>
               </div>
               
               <textarea v-else-if="param.type === 'textarea'" v-model="formData[param.key]" class="input-dark custom-scrollbar allow-select" :placeholder="param.placeholder || '在此粘贴...'" style="resize:vertical; min-height:80px; font-family:monospace; line-height:1.4;"></textarea>
               <input v-else-if="param.type === 'string' || param.type === 'number'" :type="param.type === 'number' ? 'number' : 'text'" v-model="formData[param.key]" class="input-dark allow-select" />
               <select v-else-if="param.type === 'select'" v-model="formData[param.key]" class="input-dark allow-select">
                 <option v-for="opt in param.options" :key="opt" :value="opt">{{ opt }}</option>
               </select>
            </template>
          </div>
        </div>
      </div>
      
      <div style="flex:none; padding-top:15px; border-top:1px dashed #313244; margin-top:5px; background: transparent; display:flex; flex-wrap:wrap; align-items:center; gap:8px;">
        <template v-if="pluginLayout && pluginLayout.footer_actions">
            <button v-for="btn in pluginLayout.footer_actions" :key="btn.id"
                    :class="btn.type === 'primary' ? 'btn-primary' : (btn.type === 'danger' ? 'btn-danger' : 'btn-default')" 
                    style="flex: 1 1 calc(33.33% - 8px); min-width: 90px; padding:10px 5px; font-size:12px; border-radius:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" 
                    @click="$emit('execute', btn.id)" 
                    :disabled="isRunning && btn.id !== 'abort'" 
                    :title="btn.label">
              {{ (isRunning && btn.id !== 'abort') ? '⚡...' : btn.label }}
            </button>
        </template>
        <template v-else>
            <button class="btn-primary" style="flex:1; padding:10px; font-size:13px; border-radius:8px; letter-spacing: 1px;" @click="$emit('execute')" :disabled="isRunning">
              {{ isRunning ? '⚡ 计算渲染中...' : '▶ 渲染计算结果' }}
            </button>
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer; flex-shrink:0; margin:0; padding-right:5px;">
              <input type="checkbox" :checked="autoRender" @change="$emit('update:autoRender', $event.target.checked)" style="width:14px; height:14px; accent-color:#a6e3a1; margin:0;">
              <span style="font-size:12px; color:#a6e3a1; font-weight:bold;">实时显示</span>
            </label>
        </template>
      </div>
    </div>
  `
})

export const PreviewRenderer = defineComponent({
  props: { path: String, outputPaths: { type: Array as PropType<string[]>, default: () => [] }, is3DLoading: Boolean, viewerInstance: Object },
  data() {
    return { scale: 1, panX: 0, panY: 0, isDragging: false, startX: 0, startY: 0, currentIndex: 0 }
  },
  computed: {
    imagePaths() {
      // 🚨 核心修复：将 .html 视同于图像，允许其加入右上角的轮播图序列池中进行切换
      return this.outputPaths.filter(p => ['.png', '.jpg', '.svg', '.html'].some(ext => p.toLowerCase().endsWith(ext)));
    },
    currentPath() {
      if (this.imagePaths.length > 0) {
        if (this.currentIndex >= this.imagePaths.length) this.currentIndex = this.imagePaths.length - 1;
        return this.imagePaths[this.currentIndex];
      }
      return this.path;
    },
    url() { return this.currentPath ? 'http://127.0.0.1:8080/api/data/static/' + this.currentPath.replace(/\\/g, '/') : '' },
    isImage() { return ['.png', '.jpg', '.svg'].some(e => (this.currentPath||'').toLowerCase().endsWith(e)) },
    // 🚨 核心修复：当后缀是 .pdf 或 .html 时，都启用内置的 iframe 沙盒进行顶级渲染
    isPdf() { return ['.pdf', '.html'].some(e => (this.currentPath||'').toLowerCase().endsWith(e)) },
    is3D() { return ['.pdb', '.cif'].some(e => (this.currentPath||'').toLowerCase().endsWith(e)) },
    fileName() { return (this.currentPath||'').split('/').pop() || 'Result_Plot' }
  },
  watch: { currentPath() { this.resetZoom(); } },
  methods: {
    prevImage() { if (this.currentIndex > 0) this.currentIndex--; },
    nextImage() { if (this.currentIndex < this.imagePaths.length - 1) this.currentIndex++; },
    handleWheel(e: WheelEvent) {
      if (!this.isImage) return;
      e.preventDefault();
      const zoomFactor = 0.1;
      if (e.deltaY < 0) this.scale = Math.min(this.scale + zoomFactor, 8); 
      else this.scale = Math.max(this.scale - zoomFactor, 0.2); 
    },
    handleMouseDown(e: MouseEvent) {
      if (!this.isImage) return;
      e.preventDefault();
      this.isDragging = true;
      this.startX = e.clientX - this.panX;
      this.startY = e.clientY - this.panY;
    },
    handleMouseMove(e: MouseEvent) {
      if (!this.isDragging || !this.isImage) return;
      this.panX = e.clientX - this.startX;
      this.panY = e.clientY - this.startY;
    },
    handleMouseUp() { this.isDragging = false; },
    resetZoom() { this.scale = 1; this.panX = 0; this.panY = 0; },
    async downloadLocal() {
      if (!this.currentPath) return;
      try {
        const response = await fetch(this.url);
        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl; a.download = this.fileName; 
        document.body.appendChild(a); a.click(); document.body.removeChild(a); window.URL.revokeObjectURL(blobUrl);
      } catch(e) { alert('下载失败，请检查网络设置！'); }
    }
  },
  template: `
    <div style="width:100%; height:100%; box-sizing:border-box; display:flex; align-items:center; justify-content:center; background:#181825; border-radius:6px; border:1px solid #313244; overflow:hidden; position:relative;"
         @wheel="handleWheel" @mousedown="handleMouseDown" @mousemove="handleMouseMove" @mouseup="handleMouseUp" @mouseleave="handleMouseUp">
      
      <div v-if="currentPath" style="position:absolute; top:15px; right:15px; z-index:20; display:flex; gap:10px; align-items:center; background:rgba(30,30,46,0.8); padding:5px 10px; border-radius:8px; border:1px solid #45475a;">
         <div v-if="imagePaths.length > 1" style="display:flex; align-items:center; gap:8px; margin-right:5px;">
             <button @click="prevImage" :disabled="currentIndex === 0" style="background:transparent; border:none; color:#a6e3a1; cursor:pointer; font-size:16px;">◀</button>
             <span style="color:#a6e3a1; font-weight:bold; font-size:12px; font-family:monospace;">{{ currentIndex + 1 }} / {{ imagePaths.length }}</span>
             <button @click="nextImage" :disabled="currentIndex === imagePaths.length - 1" style="background:transparent; border:none; color:#a6e3a1; cursor:pointer; font-size:16px;">▶</button>
         </div>
         <button v-if="isImage" @click="resetZoom" style="background:transparent; border:none; color:#a6adc8; cursor:pointer; font-size:12px; font-weight:bold;">🔍 1:1视角</button>
         <button @click="downloadLocal" style="background:#89b4fa; border:none; color:#11111b; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:12px; font-weight:bold; box-shadow:0 4px 6px rgba(0,0,0,0.3);">💾 下载</button>
      </div>

      <div v-if="!currentPath" style="color:#6c7086; font-size:13px; font-style:italic;">[ 等待算力引擎输出图像或模型... ]</div>
      <img v-else-if="isImage" :src="url" :style="{ transform: 'translate(' + panX + 'px, ' + panY + 'px) scale(' + scale + ')', transition: isDragging ? 'none' : 'transform 0.1s', cursor: isDragging ? 'grabbing' : 'grab' }" style="width:100%; height:100%; object-fit:contain; transform-origin:center center; max-width:100%; max-height:100%;" draggable="false" />
      
      <iframe v-else-if="isPdf" :src="url" style="width:100%; height:100%; border:none; background:#fff; z-index:10;"></iframe>
      
      <div v-else style="color:#a6adc8; font-size:12px; text-align:center;">
         <div style="font-size:40px; margin-bottom:10px;">📄</div><span style="color:#f9e2af; font-family:monospace;">{{ currentPath }}</span>
      </div>
    </div>
  `
})

export const ExportRenderer = defineComponent({
  props: { outputPaths: Array as PropType<string[]>, pluginName: String },
  data() { 
    return { 
      project: '', 
      dateStr: new Date().toISOString().split('T')[0],
      expType: '', 
      domain: '📊 04_Reports (正式报告)', 
      prefix: '', 
      suffix: '',
      preserveStructure: true,
      selectedFiles: [] as string[],
      selectAll: true,
      projectList: [] as any[],
      experimentList: [] as any[],
      domainList: [
         { id: 'seq', label: '🧬 01_Sequences (序列数据)' },
         { id: 'struct', label: '🧊 02_Structures (结构模型)' },
         { id: 'plugin', label: '⚙️ 03_Plugin_Outputs (算力杂项)' },
         { id: 'report', label: '📊 04_Reports (正式报告)' },
      ]
    } 
  },
  watch: {
    outputPaths: {
      handler(newVal) {
        if (newVal) {
            this.selectedFiles = [...newVal];
            this.selectAll = true;
        }
      },
      immediate: true,
      deep: true
    }
  },
  async mounted() {
    try {
      const res = await fetch('http://127.0.0.1:8080/api/data/meta');
      const json = await res.json();
      if (json.code === 200 && json.data.tags) {
         this.projectList = json.data.tags.projects || [];
         this.experimentList = json.data.tags.experiments || [];
      }
    } catch(e) {}
  },
  methods: {
    toggleSelectAll() {
        if (this.selectAll) {
            this.selectedFiles = [...(this.outputPaths || [])];
        } else {
            this.selectedFiles = [];
        }
    },
    async doExport() {
      if (!this.selectedFiles || this.selectedFiles.length === 0) return alert("当前未勾选任何要输出的产物！")
      let successCount = 0;
      const projFolder = this.project ? `${this.project}/` : '00_Inbox/'; 
      const dateFolder = this.dateStr ? `${this.dateStr}/` : '';
      const expFolder = this.expType ? `${this.expType}/` : '';
      const basePath = `${projFolder}${dateFolder}${expFolder}`;
      
      for (const p of this.selectedFiles) {
         const oldPath = p.replace(/\\/g, '/');
         const ext = oldPath.split('.').pop() || 'dat';
         
         let baseFileName = 'Result';
         const match = oldPath.match(/Out_[^_]+_(.+)_[^_]+\.[^.]+$/);
         if (match) baseFileName = match[1];
         else baseFileName = oldPath.split('/').pop()?.split('.')[0] || 'Result';
         
         let subDir = '';
         if (this.preserveStructure) {
             const parts = oldPath.split('/');
             parts.pop(); 
             if (parts.length > 0 && parts[0] === '.cache') parts.shift();
             if (parts.length > 0) subDir = parts.join('/') + '/';
         }

         const finalName = `${this.prefix}${baseFileName}${this.suffix}.${ext}`;
         const newPathClean = `${basePath}${subDir}${finalName}`.replace(/\/\//g, '/');
         
         let finalOld = oldPath;
         const marker = 'SciForge_Data/';
         const idx = finalOld.indexOf(marker);
         if (idx !== -1) finalOld = finalOld.substring(idx + marker.length);
         if (finalOld.startsWith('./')) finalOld = finalOld.substring(2);

         try {
            const res = await fetch('http://127.0.0.1:8080/api/data/rename', {
               method: 'POST', headers: { 'Content-Type': 'application/json' },
               body: JSON.stringify({ old_path: finalOld, new_path: newPathClean })
            });
            if (res.ok) {
               await fetch('http://127.0.0.1:8080/api/data/meta/file/update', {
                   method: 'POST', headers: { 'Content-Type': 'application/json' },
                   body: JSON.stringify({ path: newPathClean, tags: [this.domain, this.project, this.expType].filter(Boolean) })
               });
               successCount++;
            }
         } catch(e) {}
      }
      alert(`✅ 成功将 ${successCount} 份资产批量归档！\n最终物理根路径: ${basePath}`);
    }
  },
  template: `
    <div style="width:100%; height:100%; display:flex; flex-direction:column; background:#11111b; border:1px solid #313244; border-radius:8px; padding:20px; box-sizing:border-box;">
      <h3 style="margin:0 0 15px 0; color:#cba6f7; font-size:16px;">💾 多维结构化归档</h3>
      <div v-if="!outputPaths || outputPaths.length === 0" style="color:#6c7086; text-align:center; padding:30px 0; border:1px dashed #45475a; border-radius:8px;">
        <span style="font-size:30px;">⏳</span><br>请先在参数表单页点击运行产生临时数据...
      </div>
      <div v-else style="display:flex; gap:15px; height:100%; min-height:0;">
        
        <div style="flex:1; display:flex; flex-direction:column; border:1px solid #313244; border-radius:8px; background:#181825; overflow:hidden;">
            <div style="padding:10px; border-bottom:1px solid #313244; background:#1e1e2e; display:flex; justify-content:space-between; align-items:center;">
                <label style="display:flex; align-items:center; gap:8px; color:#bac2de; font-size:12px; font-weight:bold; cursor:pointer;">
                    <input type="checkbox" v-model="selectAll" @change="toggleSelectAll" style="accent-color:#89b4fa; width: 14px; height: 14px;">
                    全选 / 产物列表 ({{ selectedFiles.length }}/{{ outputPaths.length }})
                </label>
            </div>
            <div class="custom-scrollbar" style="flex:1; overflow-y:auto; padding:10px;">
                <div v-for="p in outputPaths" :key="p" style="display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom: 1px dashed #313244;">
                    <input type="checkbox" :value="p" v-model="selectedFiles" style="accent-color:#89b4fa; width: 14px; height: 14px;">
                    <div style="display: flex; flex-direction: column; overflow: hidden;">
                       <span style="color:#cdd6f4; font-size:12px; font-family:monospace; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" :title="p">{{ p.split('/').pop() }}</span>
                       <span style="color:#6c7086; font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" :title="p">{{ p }}</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="custom-scrollbar" style="width:260px; display:flex; flex-direction:column; gap:12px; overflow-y:auto; padding-right:5px;">
            <div style="display:flex; flex-direction:column; gap:6px;">
              <label style="font-size:12px; color:#bac2de; font-weight:bold;">1. 归档课题 (Project):</label>
              <select v-model="project" class="input-dark allow-select">
                 <option value="">📥 00_Inbox</option>
                 <option v-for="p in projectList" :key="p.id" :value="p.label">{{ p.label }}</option>
              </select>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
              <label style="font-size:12px; color:#bac2de; font-weight:bold;">2. 发生日期 (Date):</label>
              <input type="date" v-model="dateStr" class="input-dark allow-select" />
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
              <label style="font-size:12px; color:#bac2de; font-weight:bold;">3. 实验类型 (Experiment):</label>
              <select v-model="expType" class="input-dark allow-select">
                 <option value="">--- 独立归档 ---</option>
                 <option v-for="e in experimentList" :key="e.id" :value="e.label">{{ e.label }}</option>
              </select>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; margin-top: 5px; padding-top: 10px; border-top: 1px dashed #313244;">
              <label style="font-size:12px; color:#f9e2af; font-weight:bold;">🏷️ 附加核心数据域标签:</label>
              <select v-model="domain" class="input-dark allow-select">
                 <option v-for="d in domainList" :key="d.id" :value="d.label">{{ d.label }}</option>
              </select>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
              <label style="font-size:12px; color:#bac2de; font-weight:bold;">4. 批量命名前/后缀:</label>
              <div style="display:flex; gap:10px;">
                  <input v-model="prefix" type="text" class="input-dark allow-select" placeholder="前缀" style="flex:1;" />
                  <input v-model="suffix" type="text" class="input-dark allow-select" placeholder="后缀" style="flex:1;" />
              </div>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; margin-top: 5px; padding-top: 10px; border-top: 1px dashed #313244;">
              <label style="display:flex; align-items:center; gap:8px; color:#a6e3a1; font-size:12px; font-weight:bold; cursor:pointer;">
                  <input type="checkbox" v-model="preserveStructure" style="accent-color:#a6e3a1; width: 14px; height: 14px;">
                  保留原始子目录结构
              </label>
              <span style="color:#6c7086; font-size:10px; line-height:1.4;">勾选后自动为您创建诸如 rfd_out 等多级物理目录</span>
            </div>

            <button class="btn-primary" style="margin-top:auto; padding:12px; flex-shrink: 0;" @click="doExport">📥 确认勾选产物批量入库</button>
        </div>
      </div>
    </div>
  `
})

export const TerminalRenderer = defineComponent({
  props: { logs: Array as PropType<string[]>, isRunning: Boolean },
  methods: {
    getLogClass(log:string) {
      if (log.includes('❌') || log.includes('Error')) return 'color:#f38ba8; font-weight:bold;'
      if (log.includes('✅') || log.includes('Success')) return 'color:#a6e3a1; font-weight:bold;'
      if (log.includes('👉') || log.includes('🚀') || log.includes('👁️')) return 'color:#89b4fa;'
      if (log.includes('🛑')) return 'color:#eba0ac; font-weight:bold;'
      return 'color:#bac2de;'
    }
  },
  template: `
    <div style="display:flex; flex-direction:column; height:100%; box-sizing:border-box;">
      <div style="display:flex; justify-content:space-between; margin-bottom:10px; flex-shrink:0;">
        <h3 style="margin:0; font-size:14px; color:#f9e2af;">💻 终端监控流</h3>
        <span :style="{color: isRunning ? '#a6e3a1' : '#6c7086'}">{{ isRunning ? 'Active' : 'Standby' }}</span>
      </div>
      <div id="terminal-output" class="custom-scrollbar" style="flex:1; min-height:0; background:#000000; padding:15px; border-radius:6px; font-family:monospace; font-size:12px; overflow-y:auto; display:flex; flex-direction:column; gap:4px; border:1px solid #313244; box-shadow:inset 0 0 20px rgba(0,0,0,0.5);">
        <div v-if="logs.length === 0" style="color:#45475a; font-style:italic;">[等待系统调度指令...]</div>
        <div v-for="(log, idx) in logs" :key="idx" :style="getLogClass(log)" style="word-break:break-all;">{{ log }}</div>
      </div>
    </div>
  `
})

export const TableRenderer = defineComponent({
  props: { tableData: Array as PropType<string[][]>, isLoading: Boolean },
  template: `
    <div style="width:100%; height:100%; box-sizing:border-box; display:flex; flex-direction:column; background:#11111b; border:1px solid #313244; border-radius:6px; overflow:hidden;">
       <div v-if="isLoading" style="padding:20px; color:#a6adc8; text-align:center;">拉取并解析表格流...</div>
       <div v-else-if="!tableData.length" style="padding:20px; color:#6c7086; text-align:center; font-style:italic;">尚无结构化表格数据抛出。</div>
       <div v-else style="flex:1; min-height:0; overflow:auto;" class="custom-scrollbar">
         <table style="width:100%; border-collapse:collapse; text-align:left; font-size:12px; color:#cdd6f4;">
           <thead style="background:#181825; position:sticky; top:0; z-index:2;">
             <tr><th v-for="(col, i) in tableData[0]" :key="i" style="padding:12px; border-bottom:2px solid #313244; color:#89b4fa; white-space:nowrap;">{{ col }}</th></tr>
           </thead>
           <tbody>
             <tr v-for="(row, i) in tableData.slice(1)" :key="i" style="border-bottom:1px solid #1e1e2e; transition:0.2s;" onmouseover="this.style.backgroundColor='rgba(137,180,250,0.1)'" onmouseout="this.style.backgroundColor='transparent'">
               <td v-for="(cell, j) in row" :key="j" style="padding:10px 12px; white-space:nowrap;">{{ cell }}</td>
             </tr>
           </tbody>
         </table>
       </div>
    </div>
  `
})

export const MetricsRenderer = defineComponent({
  props: { metrics: Object as PropType<Record<string, any>> },
  template: `
    <div class="custom-scrollbar" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:15px; width:100%; height:100%; box-sizing:border-box; align-content:start; overflow-y:auto; padding-right:5px;">
       <div v-if="!Object.keys(metrics).length" style="color:#6c7086; font-size:12px; grid-column:1/-1; text-align:center; padding-top:20px;">引擎暂未计算出核心指标。</div>
       <div v-for="(val, key) in metrics" :key="key" style="background:#11111b; border:1px solid #45475a; padding:15px; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center; box-shadow:0 4px 6px rgba(0,0,0,0.2);">
          <div style="font-size:11px; color:#a6adc8; font-weight:bold; margin-bottom:8px; text-transform:uppercase;">{{ key }}</div>
          <div style="font-size:22px; color:#f9e2af; font-family:monospace; font-weight:bold; text-align:center;">{{ val }}</div>
       </div>
    </div>
  `
})

export const CodeRenderer = defineComponent({
  props: { code: String, isLoading: Boolean, path: String },
  data() { return { localCode: '' } },
  watch: { code(val) { this.localCode = val } },
  methods: {
     async saveCode() {
        if(!this.path) return;
        try {
           await fetch('http://127.0.0.1:8080/api/data/save_file', {
              method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ path: '.cache', filename: this.path.split('/').pop(), content: this.localCode })
           });
           alert('✅ 脚本修改已落盘！接下来云端引擎将使用你编辑后的脚本执行。');
        } catch(e) { alert('保存失败: ' + e); }
     }
  },
  template: `
    <div class="custom-scrollbar" style="width:100%; height:100%; box-sizing:border-box; background:#11111b; border:1px solid #313244; border-radius:6px; overflow:hidden; display:flex; flex-direction:column;">
      <div v-if="isLoading" style="color:#a6adc8; padding:15px;">获取代码流...</div>
      <div v-else-if="!code" style="color:#6c7086; text-align:center; padding-top:20px;">无代码产物抛出。</div>
      <template v-else>
          <div style="background:#181825; padding:8px 15px; border-bottom:1px solid #313244; display:flex; justify-content:space-between; align-items:center;">
             <span style="color:#a6adc8; font-size:12px; font-family:monospace;">📄 {{ path ? path.split('/').pop() : 'Code' }}</span>
             <button @click="saveCode" style="background:rgba(166,227,161,0.2); color:#a6e3a1; border:1px solid #a6e3a1; border-radius:4px; font-size:11px; padding:4px 12px; cursor:pointer; font-weight:bold; transition:0.2s;" onmouseover="this.style.background='rgba(166,227,161,0.4)'" onmouseout="this.style.background='rgba(166,227,161,0.2)'">💾 保存修改</button>
          </div>
          <textarea v-model="localCode" class="custom-scrollbar" spellcheck="false" style="flex:1; width:100%; background:transparent; color:#a6e3a1; font-family:monospace; font-size:13px; line-height:1.5; border:none; outline:none; padding:15px; resize:none;"></textarea>
      </template>
    </div>
  `
})
</script>

<style scoped>
* { box-sizing: border-box; }
.plugin-engine-view { height: 100%; display: flex; flex-direction: column; padding: 20px; color: #cdd6f4; user-select: none; }
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: center;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086;}
.breadcrumbs h2.active { color: #89b4fa; font-weight: bold;}
.separator { color: #45475a; font-weight: bold;}
.plugin-selector { background: #11111b; border: 1px solid #89b4fa; color: #cdd6f4; padding: 6px 15px; border-radius: 8px; outline: none; font-size: 14px; font-weight: bold; cursor: pointer;}
.btn-primary { background: #89b4fa; color: #11111b; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0;}
.btn-outline { background: transparent; color: #bac2de; border: 1px dashed #6c7086; padding: 6px 12px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0; font-size: 12px;}
.btn-outline:hover { color: #89b4fa; border-color: #89b4fa; background: rgba(137, 180, 250, 0.1); }
.btn-default { background: #313244; color: #cdd6f4; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0;}
.btn-default:hover { background: #45475a; }
.btn-danger { background: #f38ba8; color: #11111b; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0;}
.btn-danger:hover { background: #eba0ac; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.card { background: #181825; border: 1px solid #313244; border-radius: 12px;}
.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0; height: 100%; overflow: hidden;}
.plugin-workspace { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0; height: 100%; overflow: hidden;}
.lego-container { display: flex; gap: 20px; flex: 1; min-height: 0; width: 100%; height: 100%; overflow: hidden;}
.lego-block { padding: 20px; display: flex; flex-direction: column; min-height: 0; height: 100%; overflow: hidden; background: #1e1e2e; }
.lego-tabs { width: 100%; height: 100%; display: flex; flex-direction: column; min-height: 0; overflow: hidden;}
.tabs-header { display: flex; flex-shrink: 0; gap: 5px; border-bottom: 1px solid #313244; margin-bottom: 15px; padding-bottom: 5px; flex-wrap: wrap;}
.tab-btn { flex: 1 1 auto; text-align: center; background: transparent; border: none; color: #a6adc8; padding: 6px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; cursor: pointer; transition: 0.2s;}
.tab-btn.active { background: #89b4fa; color: #11111b; }
.tabs-body { flex: 1; display: flex; flex-direction: column; min-height: 0; position: relative;}
.tab-pane-content { flex: 1; display: flex; flex-direction: column; min-height: 0; width: 100%; height: 100%;}
.lego-inner-form, .lego-inner-terminal, .lego-inner-preview, .lego-inner-table, .lego-inner-code, .lego-inner-metrics, .lego-inner-export { flex: 1; display: flex; flex-direction: column; min-height: 0; width: 100%; height: 100%; }
.zone-title { margin: 0; font-size: 14px; font-weight: bold; color: #f9e2af; padding-bottom: 10px; border-bottom: 1px dashed #313244;}
.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
:deep(.input-dark) { background-color: #11111b !important; color: #cdd6f4 !important; border: 1px solid #45475a !important; padding: 8px 12px !important; border-radius: 6px !important; outline: none !important; font-size: 12px !important; box-sizing: border-box !important; width: 100% !important; transition: all 0.2s ease !important; }
:deep(.input-dark:focus) { border-color: #89b4fa !important; box-shadow: 0 0 0 2px rgba(137, 180, 250, 0.2) !important;}
:deep(select.input-dark option) { background-color: #11111b !important; color: #cdd6f4 !important; }
:deep(.custom-scrollbar::-webkit-scrollbar) { width: 6px; height: 6px; }
:deep(.custom-scrollbar::-webkit-scrollbar-track) { background: transparent; }
:deep(.custom-scrollbar::-webkit-scrollbar-thumb) { background: #45475a; border-radius: 3px; }
:deep(.custom-scrollbar::-webkit-scrollbar-thumb:hover) { background: #6c7086; }
</style>