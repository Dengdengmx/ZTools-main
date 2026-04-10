<template>
  <div class="data-hub-view" @click="hideContextMenu">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 @click="navigateTo('')" :class="{ active: currentPath === '' }">🗄️ 内部数据中心 (DataHub)</h2>
        <template v-if="currentPath">
          <span class="separator">/</span>
          <h2 class="active">{{ currentPath }}</h2>
        </template>
      </div>
      <div class="header-actions">
        <button class="btn-outline btn-upload" style="border-color: #a6e3a1; color: #a6e3a1;">
          <input type="file" style="display: none;" multiple @change="handleFileUpload">
          ⬆️ 上传数据至当前层级
        </button>
        <button class="btn-primary" @click="fetchDirectory(currentPath)">🔄 刷新物理目录</button>
      </div>
    </div>

    <div class="three-column-layout">
      
      <div class="column-left card">
        <h3 class="panel-title">数据归档与检索</h3>
        
        <button class="btn-cyan w-full" @click="changeMountPoint" title="更改底层数据的保存路径">🏠 挂载数据根目录...</button>
        
        <div class="filter-section">
          <div class="filter-label">物理挂载点:</div>
          <div class="filter-value path-text" style="color: #a6adc8;" :title="dataHubPath">{{ dataHubPath || '加载中...' }}</div>
        </div>

        <div class="filter-section">
          <div class="filter-label">当前相对路径:</div>
          <div class="filter-value path-text" style="color: #cba6f7;" :title="currentPath || 'Root'">/{{ currentPath || 'Root' }}</div>
        </div>

        <div class="filter-section" style="border-top: 1px dashed #313244; padding-top: 15px;">
          <div class="filter-label">核心数据域 (快速跳转):</div>
          <div class="quick-access-grid">
            <div class="qa-item" @click="navigateTo('01_Sequences')"><span class="bg-plasmid">📜</span> 序列</div>
            <div class="qa-item" @click="navigateTo('02_Structures')"><span class="bg-protein">🧬</span> 结构</div>
            <div class="qa-item" @click="navigateTo('03_Plugin_Outputs')"><span class="bg-cell">⚙️</span> 输出</div>
            <div class="qa-item" @click="navigateTo('04_Reports')"><span class="bg-default">📊</span> 报告</div>
          </div>
        </div>

        <div class="filter-section" style="border-top: 1px dashed #313244; padding-top: 15px;">
          <div class="filter-label">全局多维过滤:</div>
          <select class="native-select w-full allow-select" v-model="filters.project">
            <option value="">-- 全部课题项目 --</option>
            <option v-for="tag in globalMeta.tags.projects" :key="tag.id" :value="tag.id">{{ tag.label }}</option>
          </select>
          <select class="native-select w-full allow-select" style="margin-top: 10px;" v-model="filters.expType">
            <option value="">-- 全部实验类型 --</option>
            <option v-for="tag in globalMeta.tags.experiments" :key="tag.id" :value="tag.id">{{ tag.label }}</option>
          </select>
          <select class="native-select w-full allow-select" style="margin-top: 10px;" v-model="filters.otherType">
            <option value="">-- 其他自定义分类 --</option>
            <option v-for="tag in globalMeta.tags.others" :key="tag.id" :value="tag.id">{{ tag.label }}</option>
          </select>
        </div>

        <div class="filter-section" style="border-top: 1px dashed #313244; padding-top: 15px; margin-top: auto;">
          <div class="filter-label">文件载体类型:</div>
          <div class="checkbox-grid">
            <label class="checkbox-item"><input type="checkbox" v-model="filters.script"> <span>脚本 (.py/.sh)</span></label>
            <label class="checkbox-item"><input type="checkbox" v-model="filters.structure"> <span>结构 (.pdb/.cif)</span></label>
            <label class="checkbox-item"><input type="checkbox" v-model="filters.sequence"> <span>序列 (.fasta/.fa)</span></label>
            <label class="checkbox-item"><input type="checkbox" v-model="filters.image"> <span>图像 (.png/.jpg)</span></label>
            <label class="checkbox-item"><input type="checkbox" v-model="filters.table"> <span>表格 (.csv/.xlsx)</span></label>
            <label class="checkbox-item"><input type="checkbox" v-model="filters.document"> <span>文档 (.txt/.md)</span></label>
            <label class="checkbox-item"><input type="checkbox" v-model="filters.other"> <span>其他 (Others)</span></label>
          </div>
        </div>
      </div>

      <div class="column-middle card" @contextmenu.prevent="showWorkspaceMenu($event)">
        <div class="explorer-toolbar">
          <button class="icon-btn" @click="goUp" :disabled="!currentPath">⬆️ 返回上级</button>
          <div class="toolbar-actions" style="margin-left: auto;">
            <button class="btn-outline btn-small" @click="handleNewFolder">📁 新建文件夹</button>
          </div>
        </div>

        <div class="workspace-content list-mode" :class="{ 'drag-active': isDragging }" @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="handleDrop">
          <div class="list-header">
            <div class="col-name">数据名称</div>
            <div class="col-type">类型</div>
            <div class="col-size">大小</div>
            <div class="col-date">更新时间</div>
          </div>
          <div class="list-body">
            <div v-if="filteredFiles.length === 0" class="empty-state">
              <span style="font-size: 48px; opacity: 0.5;">📭</span>
              <p style="margin-top: 10px;">未找到匹配的文件或当前目录为空</p>
            </div>
            
            <div v-if="currentPath" class="list-item back-item" @dblclick="goUp">
              <div class="col-name"><span class="file-icon">↩️</span> 返回上一级</div>
            </div>

            <div 
              v-for="file in filteredFiles" :key="file.path" 
              class="list-item fade-in" 
              :class="{ selected: selectedFile?.path === file.path }"
              @click="selectFile(file)"
              @dblclick="handleDoubleClick(file)"
              @contextmenu.prevent.stop="showContextMenu(file, $event)"
            >
              <div class="col-name">
                <span class="file-icon">{{ getFileIcon(file) }}</span>
                <span class="f-name" :class="{'is-dir': file.is_dir}">{{ file.name }}</span>
              </div>
              <div class="col-type">{{ getFileTypeName(file) }}</div>
              <div class="col-size">{{ formatSize(file.size, file.is_dir) }}</div>
              <div class="col-date">{{ file.modified }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="column-right card preview-panel" :style="{ width: rightPanelWidth + 'px', flexBasis: rightPanelWidth + 'px' }">
        <h3 class="panel-title">文件预览与洞察 (Data Insights)</h3>
        <div class="resize-handle" @mousedown.prevent="startResize" :class="{ active: isResizing }"></div>
        
        <div v-if="!selectedFile" class="preview-empty">
          请选择左侧或中间数据条目查看详情。
        </div>
        
        <div v-else class="preview-content fade-in">
          <div class="preview-info-card">
            <div class="p-icon">{{ getFileIcon(selectedFile) }}</div>
            <div class="p-details">
              <div class="p-name" :title="selectedFile.name">{{ selectedFile.name }}</div>
              <div class="p-meta">{{ formatSize(selectedFile.size, selectedFile.is_dir) }} • {{ selectedFile.modified }}</div>
            </div>
          </div>

          <div class="tags-insight-section">
            <div class="tags-header">
               <span style="font-size: 12px; font-weight: bold; color: #bac2de;">🏷️ 资产专属标签</span>
               <button class="add-tag-btn" @click.stop="openTagModal">+ 添加映射</button>
            </div>
            <div class="tags-container">
               <div v-if="currentFileTags.length === 0" style="color: #6c7086; font-size: 11px;">尚未分配任何分类标签。</div>
               <div v-for="tag in currentFileTags" :key="tag.id" class="file-tag" :style="{ borderColor: tag.color, color: tag.color, background: `${tag.color}22` }">
                 {{ tag.label }}
                 <span class="tag-close" @click.stop="toggleFileTag(tag.id)">✖</span>
               </div>
            </div>
          </div>

          <div class="preview-render-area">
             <div v-if="isPreviewLoading" class="preview-status"><span class="spin-loader">⚙️</span> 加载数据流...</div>
             <div v-else-if="previewError" class="preview-status error">{{ previewError }}</div>
             
             <div v-else-if="selectedFile.is_dir" class="preview-status hint">
               📁 文件夹对象<br>
               <button class="btn-primary" style="margin-top:15px;" @click="handleDoubleClick(selectedFile)">双击进入目录</button>
             </div>
             
             <div v-else-if="isImage(selectedFile.ext)" class="media-render">
               <img :src="getStaticUrl(selectedFile.path)" alt="Preview" />
             </div>

             <div v-else-if="isPdf(selectedFile.ext)" class="media-render">
               <iframe :src="getStaticUrl(selectedFile.path)"></iframe>
             </div>

             <div v-else-if="is3DFile(selectedFile.ext)" class="media-render">
               <div v-if="is3DLoadingEngine" class="preview-status" style="position: absolute; width: 100%; height: 100%; z-index: 10; background: rgba(30,30,46,0.8);">
                 <span class="spin-loader">🧬</span> 挂载 WebGL 引擎...
               </div>
               <div id="viewer-3d-panel" class="viewer-3d"></div>
               <div class="viewer-tools" v-if="viewerInstancePanel">
                 <button class="tool-btn-mini" @click="set3DStylePanel('cartoon')">Cartoon</button>
                 <button class="tool-btn-mini" @click="set3DStylePanel('sphere')">Surface</button>
               </div>
             </div>

             <div v-else class="code-render allow-select">
               <pre><code :class="getHighlightClass(selectedFile.ext)">{{ previewTextContent }}</code></pre>
             </div>
          </div>

          <div class="preview-actions-bar" v-if="!selectedFile.is_dir">
             <button class="btn-primary w-full" @click="openFullscreenModal">🔍 放大全屏预览</button>
             <div style="display: flex; gap: 10px; margin-top: 10px;">
               <button class="btn-outline w-full" @click="handleDownload(selectedFile)">⬇️ 下载</button>
               <button class="btn-danger w-full" @click="handleDelete(selectedFile)">🗑️ 删除</button>
             </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="ctxMenu.visible" class="context-menu fade-in-scale" :style="{ top: ctxMenu.y + 'px', left: ctxMenu.x + 'px' }">
      <div class="ctx-header">{{ ctxMenu.file ? ctxMenu.file.name : '当前目录操作' }}</div>
      <template v-if="ctxMenu.file">
        <div class="ctx-item" @click="handleRename(ctxMenu.file)">✏️ 重命名</div>
        <div class="ctx-item" v-if="!ctxMenu.file.is_dir" @click="handleDownload(ctxMenu.file)">⬇️ 导出/下载到本地</div>
        <div class="ctx-divider"></div>
        <div class="ctx-item danger" @click="handleDelete(ctxMenu.file)">🗑️ 彻底删除</div>
      </template>
      <template v-else>
        <div class="ctx-item" @click="handleNewFolder">📁 新建子文件夹</div>
        <div class="ctx-item" @click="fetchDirectory(currentPath)">🔄 刷新目录</div>
      </template>
    </div>

    <div v-if="showTagModal" class="modal-overlay fade-in" @click.self="showTagModal = false; showNewTagForm = false;">
      <div class="modal-content fade-in-scale" style="width: 450px; height: auto;">
        
        <div v-if="!showNewTagForm">
           <div class="modal-header">
             <div class="modal-title">🏷️ 关联资产标签</div>
             <button class="btn-close" @click="showTagModal = false">✖</button>
           </div>
           <div class="modal-body" style="max-height: 400px; overflow-y: auto; padding: 20px;">
             <div class="tag-section-title">📂 项目课题 (Projects)</div>
             <div class="tag-pool">
                <div v-for="tag in globalMeta.tags.projects" :key="tag.id" class="pool-tag" 
                     :class="{ active: currentFileTagIds.includes(tag.id) }"
                     :style="{ borderColor: tag.color, color: currentFileTagIds.includes(tag.id) ? '#11111b' : tag.color, background: currentFileTagIds.includes(tag.id) ? tag.color : 'transparent' }"
                     @click="toggleFileTag(tag.id)">
                  {{ tag.label }}
                </div>
             </div>
             
             <div class="tag-section-title" style="margin-top: 15px;">🧪 实验类型 (Experiments)</div>
             <div class="tag-pool">
                <div v-for="tag in globalMeta.tags.experiments" :key="tag.id" class="pool-tag" 
                     :class="{ active: currentFileTagIds.includes(tag.id) }"
                     :style="{ borderColor: tag.color, color: currentFileTagIds.includes(tag.id) ? '#11111b' : tag.color, background: currentFileTagIds.includes(tag.id) ? tag.color : 'transparent' }"
                     @click="toggleFileTag(tag.id)">
                  {{ tag.label }}
                </div>
             </div>

             <div class="tag-section-title" style="margin-top: 15px;">🔖 自定义与其他 (Others)</div>
             <div class="tag-pool">
                <div v-for="tag in globalMeta.tags.others" :key="tag.id" class="pool-tag" 
                     :class="{ active: currentFileTagIds.includes(tag.id) }"
                     :style="{ borderColor: tag.color, color: currentFileTagIds.includes(tag.id) ? '#11111b' : tag.color, background: currentFileTagIds.includes(tag.id) ? tag.color : 'transparent' }"
                     @click="toggleFileTag(tag.id)">
                  {{ tag.label }}
                </div>
             </div>
           </div>
           <div class="modal-footer" style="justify-content: space-between; padding: 12px 20px;">
              <button class="btn-outline" style="border-style: dashed; padding: 6px 12px; font-size: 12px;" @click="showNewTagForm = true">➕ 新建全局标签</button>
              <button class="btn-primary" style="padding: 6px 15px; font-size: 12px;" @click="showTagModal = false">完成选择</button>
           </div>
        </div>

        <div v-else>
           <div class="modal-header">
             <div class="modal-title">➕ 扩充全局标签库</div>
             <button class="btn-close" @click="showNewTagForm = false; showTagModal = false;">✖</button>
           </div>
           <div class="modal-body" style="padding: 20px;">
              <div class="form-group">
                 <label>归属大类:</label>
                 <select v-model="newTag.category" class="input-dark allow-select">
                   <option value="projects">📂 项目课题 (Projects)</option>
                   <option value="experiments">🧪 实验类型 (Experiments)</option>
                   <option value="others">🔖 其他类别 (Others)</option>
                 </select>
              </div>
              <div class="form-group">
                 <label>标签名称 (支持带 Emoji):</label>
                 <input type="text" v-model="newTag.label" class="input-dark allow-select" placeholder="例如: 🧬 P53重组蛋白...">
              </div>
              <div class="form-group">
                 <label>主题配色:</label>
                 <div style="display: flex; gap: 10px; margin-top: 5px;">
                   <div v-for="c in colorPalette" :key="c" class="color-picker-dot" 
                        :style="{ background: c, border: newTag.color === c ? '2px solid #ffffff' : '2px solid transparent' }"
                        @click="newTag.color = c"></div>
                 </div>
              </div>
           </div>
           <div class="modal-footer" style="padding: 12px 20px;">
              <button class="btn-outline" style="padding: 6px 15px; font-size: 12px;" @click="showNewTagForm = false">返回上级</button>
              <button class="btn-primary" style="padding: 6px 15px; font-size: 12px;" @click="submitNewTag">💾 保存至全局字典</button>
           </div>
        </div>

      </div>
    </div>

    <div v-if="showMountModal" class="modal-overlay fade-in" @click.self="!isMigrating && (showMountModal = false)">
      <div class="modal-content fade-in-scale" style="width: 480px; border-color: #89b4fa; height: auto;">
        <div class="modal-header">
          <div class="modal-title">🏠 变更物理挂载点</div>
          <button class="btn-close" @click="showMountModal = false" :disabled="isMigrating">✖</button>
        </div>
        <div class="modal-body" style="padding: 20px;">
          <div class="form-group">
            <label>新的数据存放路径:</label>
            <div class="filter-value path-text" style="color: #a6e3a1; padding: 10px;">{{ newMountPath }}</div>
          </div>
          <p style="color: #bac2de; font-size: 13px; line-height: 1.5; margin-top: 10px;">
            您正在更改 DataHub 的底层物理存储位置。<br><br>
            是否需要将原路径 <b style="color: #f38ba8;">{{ dataHubPath }}</b> 下的所有现有文件和模型数据同步迁移到新位置？
          </p>

          <div v-if="isMigrating" class="preview-status" style="margin-top: 15px; color: #89b4fa; border: 1px dashed #89b4fa; padding: 10px; border-radius: 8px;">
            <span class="spin-loader" style="font-size: 16px; margin-bottom: 5px;">⚙️</span> 正在进行数据无损迁移，请勿关闭窗口...
          </div>
        </div>
        <div class="modal-footer" v-if="!isMigrating" style="padding: 12px 20px;">
          <button class="btn-outline" style="padding: 6px 15px; font-size: 12px;" @click="confirmMount(false)">仅更改路径</button>
          <button class="btn-primary" style="padding: 6px 15px; font-size: 12px;" @click="confirmMount(true)">🚀 全部迁移</button>
        </div>
      </div>
    </div>

    <div v-if="showFullscreenModal && selectedFile" class="modal-overlay fade-in" @click.self="showFullscreenModal = false">
      <div class="modal-content card fullscreen-modal">
        <div class="modal-header">
          <div class="modal-title">
            <span class="file-icon">{{ getFileIcon(selectedFile) }}</span> {{ selectedFile.name }}
          </div>
          <button class="icon-btn" style="background: transparent; font-size: 20px; color: #f38ba8;" @click="showFullscreenModal = false">✖</button>
        </div>
        <div class="modal-body" style="padding: 0; background: #1e1e2e; position: relative;">
           <div v-if="isImage(selectedFile.ext)" class="media-render"><img :src="getStaticUrl(selectedFile.path)" /></div>
           <div v-else-if="isPdf(selectedFile.ext)" class="media-render"><iframe :src="getStaticUrl(selectedFile.path)"></iframe></div>
           <div v-else-if="is3DFile(selectedFile.ext)" class="media-render">
             <div id="viewer-3d-fullscreen" class="viewer-3d"></div>
             <div class="viewer-tools" style="bottom: 20px;">
               <button class="tool-btn" @click="set3DStyleFullscreen('cartoon')">🌈 Cartoon</button>
               <button class="tool-btn" @click="set3DStyleFullscreen('sphere')">☁️ Surface</button>
               <button class="tool-btn" @click="set3DStyleFullscreen('stick')">🥢 Stick</button>
             </div>
           </div>
           <div v-else class="code-render allow-select" style="padding: 20px;">
             <pre><code :class="getHighlightClass(selectedFile.ext)">{{ previewTextContent }}</code></pre>
           </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onUnmounted } from 'vue'

const BASE_API = 'http://127.0.0.1:8080/api/data'
const STATIC_API = 'http://127.0.0.1:8080/api/data/static'

const rightPanelWidth = ref(340)
const isResizing = ref(false)

const startResize = (e: MouseEvent) => {
  isResizing.value = true
  document.body.style.userSelect = 'none' 
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
}

const handleResize = (e: MouseEvent) => {
  if (!isResizing.value) return
  let newWidth = window.innerWidth - e.clientX - 20
  if (newWidth < 250) newWidth = 250
  if (newWidth > 800) newWidth = 800
  rightPanelWidth.value = newWidth
}

const stopResize = () => {
  isResizing.value = false
  document.body.style.userSelect = ''
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
}

const dataHubPath = ref('')
const currentPath = ref('')
const files = ref<any[]>([])
const selectedFile = ref<any>(null)

const isDragging = ref(false)
const ctxMenu = ref({ visible: false, x: 0, y: 0, file: null as any })
const showFullscreenModal = ref(false)

const showMountModal = ref(false)
const newMountPath = ref('')
const isMigrating = ref(false)

const previewTextContent = ref('')
const isPreviewLoading = ref(false)
const previewError = ref('')
const viewerInstancePanel = ref<any>(null)
const viewerInstanceFS = ref<any>(null)

const globalMeta = ref({
  tags: { projects: [], experiments: [], others: [] },
  file_tags: {}
})

const showTagModal = ref(false)
const showNewTagForm = ref(false)
const newTag = ref({ category: 'projects', label: '', color: '#89b4fa' })
const colorPalette = ['#f9e2af', '#a6e3a1', '#89b4fa', '#cba6f7', '#f38ba8', '#94e2d5']

const currentFileTagIds = computed(() => {
  if (!selectedFile.value) return []
  return globalMeta.value.file_tags[selectedFile.value.path] || []
})

const currentFileTags = computed(() => {
  const ids = currentFileTagIds.value
  const allTags = [...globalMeta.value.tags.projects, ...globalMeta.value.tags.experiments, ...globalMeta.value.tags.others]
  return ids.map((id: string) => allTags.find(t => t.id === id)).filter(Boolean)
})

const fetchMeta = async () => {
  try {
    const res = await fetch(`${BASE_API}/meta`)
    const json = await res.json()
    if (json.code === 200) globalMeta.value = json.data
  } catch (e) { console.error("无法加载元数据字典") }
}

const openTagModal = () => { showTagModal.value = true; showNewTagForm.value = false; }

const toggleFileTag = async (tagId: string) => {
  if (!selectedFile.value) return
  const path = selectedFile.value.path
  let currentTags = [...(globalMeta.value.file_tags[path] || [])]
  
  if (currentTags.includes(tagId)) currentTags = currentTags.filter(t => t !== tagId)
  else currentTags.push(tagId)

  globalMeta.value.file_tags[path] = currentTags
  
  try {
    await fetch(`${BASE_API}/meta/file/update`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, tags: currentTags })
    })
  } catch (e) { console.error("标签同步失败") }
}

const submitNewTag = async () => {
  if (!newTag.value.label.trim()) return alert("请输入标签名称！")
  try {
    const res = await fetch(`${BASE_API}/meta/tag/add`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newTag.value)
    })
    const json = await res.json()
    if (res.ok && json.code === 200) {
      globalMeta.value = json.data
      showNewTagForm.value = false
      newTag.value = { category: 'projects', label: '', color: '#89b4fa' } 
    }
  } catch (e) { alert("标签创建失败") }
}

const filters = ref({ project: '', expType: '', otherType: '', script: true, structure: true, sequence: true, image: true, table: true, document: true, other: true })

const filteredFiles = computed(() => {
  return files.value.filter(f => {
    const fTags = globalMeta.value.file_tags[f.path] || [];
    
    if (filters.value.project) {
      const tagObj = globalMeta.value.tags.projects.find((t:any) => t.id === filters.value.project);
      const inPath = tagObj ? (f.name + f.path).toLowerCase().includes(tagObj.label.toLowerCase()) : false;
      if (!fTags.includes(filters.value.project) && !inPath) return false;
    }
    
    if (filters.value.expType) {
      const tagObj = globalMeta.value.tags.experiments.find((t:any) => t.id === filters.value.expType);
      const inPath = tagObj ? (f.name + f.path).toLowerCase().includes(tagObj.label.toLowerCase()) : false;
      if (!fTags.includes(filters.value.expType) && !inPath) return false;
    }

    if (filters.value.otherType) {
      const tagObj = globalMeta.value.tags.others.find((t:any) => t.id === filters.value.otherType);
      const inPath = tagObj ? (f.name + f.path).toLowerCase().includes(tagObj.label.toLowerCase()) : false;
      if (!fTags.includes(filters.value.otherType) && !inPath) return false;
    }

    if (f.is_dir) return true;

    const ext = f.ext.toLowerCase();
    if (filters.value.script && ['.py', '.sh', '.js'].includes(ext)) return true;
    if (filters.value.structure && ['.pdb', '.cif'].includes(ext)) return true;
    if (filters.value.sequence && ['.fasta', '.fa', '.seq'].includes(ext)) return true;
    if (filters.value.image && ['.png', '.jpg', '.jpeg', '.gif', '.svg'].includes(ext)) return true;
    if (filters.value.table && ['.csv', '.xlsx'].includes(ext)) return true;
    if (filters.value.document && ['.txt', '.md', '.pdf', '.docx'].includes(ext)) return true;
    
    const knownExts = ['.py','.sh','.js','.pdb','.cif','.fasta','.fa','.seq','.png','.jpg','.jpeg','.gif','.svg','.csv','.xlsx','.txt','.md','.pdf','.docx'];
    if (filters.value.other && !knownExts.includes(ext)) return true;

    return false;
  })
})

const fetchConfig = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/config')
    const json = await res.json()
    if (json.code === 200 && json.data) dataHubPath.value = json.data.data_hub_path
  } catch (e) {}
}

const changeMountPoint = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/utils/pick_folder')
    const json = await res.json()
    if (json.code === 200 && json.data) {
      newMountPath.value = json.data
      showMountModal.value = true
    } else if (json.code !== 400) alert(`无法唤起系统对话框: ${json.message}`)
  } catch (e) {
    const path = prompt("无法唤起系统选择器，请手动输入目标绝对路径:", dataHubPath.value)
    if (path) { newMountPath.value = path; showMountModal.value = true }
  }
}

const confirmMount = async (migrate: boolean) => {
  isMigrating.value = true
  try {
    const res = await fetch('http://127.0.0.1:8080/api/config/update', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data_hub_path: newMountPath.value, migrate_data: migrate })
    })
    const json = await res.json()
    if (res.ok && json.code === 200) {
      showMountModal.value = false; await fetchConfig(); navigateTo(''); fetchMeta();
    } else alert(`挂载失败: ${json.message}`)
  } catch (e) { alert("网络异常") } finally { isMigrating.value = false }
}

const fetchDirectory = async (path: string = "") => {
  try {
    const res = await fetch(`${BASE_API}/tree?path=${encodeURIComponent(path)}`)
    const json = await res.json()
    if (json.code === 200) { files.value = json.data; currentPath.value = json.current_path; selectedFile.value = null; }
  } catch (e) {}
}

const navigateTo = (path: string) => { fetchDirectory(path) }
const goUp = () => { if (!currentPath.value) return; const parts = currentPath.value.split('/'); parts.pop(); fetchDirectory(parts.join('/')) }

const uploadFiles = async (fileList: FileList | File[]) => {
  if (!fileList || fileList.length === 0) return
  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i]
    const formData = new FormData()
    formData.append('path', currentPath.value)
    formData.append('file', file)
    try { await fetch(`${BASE_API}/upload`, { method: 'POST', body: formData }) } catch (e) {}
  }
  fetchDirectory(currentPath.value)
}
const handleFileUpload = (e: Event) => { const target = e.target as HTMLInputElement; if (target.files) uploadFiles(target.files) }
const handleDrop = (e: DragEvent) => { isDragging.value = false; if (e.dataTransfer && e.dataTransfer.files) uploadFiles(e.dataTransfer.files) }

const showContextMenu = (file: any, e: MouseEvent) => { ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, file: file } }
const showWorkspaceMenu = (e: MouseEvent) => {
  if ((e.target as HTMLElement).closest('.list-item')) return 
  ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, file: null }
}
const hideContextMenu = () => { ctxMenu.value.visible = false }

const handleNewFolder = async () => {
  const folderName = prompt("请输入新文件夹名称:")
  if (!folderName || folderName.trim() === '') return
  try {
    const res = await fetch(`${BASE_API}/mkdir`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: currentPath.value, dir_name: folderName.trim() })
    })
    if (res.ok) fetchDirectory(currentPath.value)
  } catch (e) {}
}

const handleRename = async (file: any) => {
  const newName = prompt(`将 ${file.name} 重命名为:`, file.name)
  if (!newName || newName === file.name) return
  const oldPath = file.path
  const newPath = currentPath.value ? `${currentPath.value}/${newName}` : newName
  try {
    const res = await fetch(`${BASE_API}/rename`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_path: oldPath, new_path: newPath })
    })
    if (res.ok) { fetchDirectory(currentPath.value); fetchMeta(); ctxMenu.value.visible = false; }
  } catch (e) {}
}

const handleDelete = async (file: any) => {
  const msg = file.is_dir ? `确定要删除文件夹 "${file.name}" 及其所有内容吗？` : `确定彻底删除文件 "${file.name}" 吗？`
  if (!confirm(msg)) return
  try {
    const res = await fetch(`${BASE_API}/delete`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: file.path })
    })
    if (res.ok) { 
      fetchDirectory(currentPath.value); 
      if(selectedFile.value?.path === file.path) selectedFile.value = null;
      fetchMeta(); ctxMenu.value.visible = false; 
    }
  } catch (e) {}
}

const handleDownload = (file: any) => {
  const url = getStaticUrl(file.path)
  const a = document.createElement('a')
  a.href = url; a.download = file.name
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
}

const getStaticUrl = (path: string) => `${STATIC_API}/${path.replace(/\\/g, '/')}`
const isImage = (ext: string) => ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].includes(ext.toLowerCase())
const isPdf = (ext: string) => ['.pdf'].includes(ext.toLowerCase())
const is3DFile = (ext: string) => ['.pdb', '.cif'].includes(ext.toLowerCase())

const selectFile = async (file: any) => {
  selectedFile.value = file
  if (file.is_dir) return
  
  previewTextContent.value = ''
  previewError.value = ''
  
  if (isImage(file.ext) || isPdf(file.ext)) return
  if (is3DFile(file.ext)) { await fetchTextContent(file); init3DViewerPanel(); return }
  await fetchTextContent(file)
}

const fetchTextContent = async (file: any) => {
  isPreviewLoading.value = true
  try {
    const res = await fetch(`${BASE_API}/read_file?path=${encodeURIComponent(file.path)}`)
    const json = await res.json()
    if (json.code === 200) previewTextContent.value = json.data
    else previewError.value = "暂不支持内联解析二进制数据流。"
  } catch (e) { previewError.value = "后端底层读取中断。" } 
  finally { isPreviewLoading.value = false }
}

const handleDoubleClick = (file: any) => {
  if (file.is_dir) { fetchDirectory(file.path) } 
  else { openFullscreenModal() }
}

const is3DLoadingEngine = ref(false)

const load3DmolEngine = async () => {
  if (!(window as any).$3Dmol) {
    is3DLoadingEngine.value = true
    await new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.0.4/3Dmol-min.js'
      script.onload = resolve
      script.onerror = reject
      document.head.appendChild(script)
    })
    is3DLoadingEngine.value = false
  }
}

const init3DViewerPanel = async () => {
  if (!previewTextContent.value) return
  await load3DmolEngine()
  nextTick(() => {
    const element = document.getElementById('viewer-3d-panel')
    const $3Dmol = (window as any).$3Dmol
    if (element && $3Dmol) {
      if (viewerInstancePanel.value) viewerInstancePanel.value.clear()
      viewerInstancePanel.value = $3Dmol.createViewer(element, { backgroundColor: '#181825' })
      const format = selectedFile.value.ext.replace('.', '')
      viewerInstancePanel.value.addModel(previewTextContent.value, format)
      viewerInstancePanel.value.setStyle({}, { cartoon: { color: 'spectrum' } })
      viewerInstancePanel.value.zoomTo()
      viewerInstancePanel.value.render()
    }
  })
}

const set3DStylePanel = (styleType: string) => {
  if (!viewerInstancePanel.value) return
  viewerInstancePanel.value.setStyle({}, {}) 
  if (styleType === 'cartoon') viewerInstancePanel.value.setStyle({}, { cartoon: { color: 'spectrum' } })
  else if (styleType === 'sphere') viewerInstancePanel.value.setStyle({}, { sphere: { color: 'chain' } }) 
  viewerInstancePanel.value.render()
}

const openFullscreenModal = async () => {
  showFullscreenModal.value = true
  if (is3DFile(selectedFile.value.ext)) {
    await load3DmolEngine()
    nextTick(() => {
      const element = document.getElementById('viewer-3d-fullscreen')
      const $3Dmol = (window as any).$3Dmol
      if (element && $3Dmol) {
        if (viewerInstanceFS.value) viewerInstanceFS.value.clear()
        viewerInstanceFS.value = $3Dmol.createViewer(element, { backgroundColor: '#1e1e2e' })
        const format = selectedFile.value.ext.replace('.', '')
        viewerInstanceFS.value.addModel(previewTextContent.value, format)
        viewerInstanceFS.value.setStyle({}, { cartoon: { color: 'spectrum' } })
        viewerInstanceFS.value.zoomTo()
        viewerInstanceFS.value.render()
      }
    })
  }
}

const set3DStyleFullscreen = (styleType: string) => {
  if (!viewerInstanceFS.value) return
  viewerInstanceFS.value.setStyle({}, {}) 
  if (styleType === 'cartoon') viewerInstanceFS.value.setStyle({}, { cartoon: { color: 'spectrum' } })
  else if (styleType === 'sphere') viewerInstanceFS.value.setStyle({}, { sphere: { color: 'chain' } }) 
  else if (styleType === 'stick') viewerInstanceFS.value.setStyle({}, { stick: {} }) 
  viewerInstanceFS.value.render()
}

const getHighlightClass = (ext: string) => {
  ext = ext.toLowerCase()
  if (ext === '.pdb' || ext === '.cif') return 'lang-pdb'
  if (ext === '.fasta' || ext === '.fa') return 'lang-fasta'
  if (ext === '.json') return 'lang-json'
  return 'lang-plaintext'
}

const getFileIcon = (file: any) => {
  if (file.is_dir) return "📁"
  const ext = file.ext.toLowerCase()
  if (['.pdb', '.cif'].includes(ext)) return "🧬"
  if (['.fasta', '.fa', '.seq'].includes(ext)) return "📜"
  if (['.png', '.jpg', '.pdf'].includes(ext)) return "📊"
  if (['.json', '.csv', '.txt', '.md'].includes(ext)) return "📋"
  if (['.py', '.sh', '.js'].includes(ext)) return "⚙️"
  return "📄"
}

const getFileTypeName = (file: any) => {
  if (file.is_dir) return "文件夹"
  const ext = file.ext.toLowerCase()
  if (['.pdb', '.cif'].includes(ext)) return "3D 结构模型"
  if (['.fasta', '.fa', '.seq'].includes(ext)) return "核酸/蛋白序列"
  if (['.png', '.jpg', '.pdf'].includes(ext)) return "报告与多媒体"
  if (['.py', '.sh', '.js'].includes(ext)) return "算力脚本"
  return "数据文件"
}

const formatSize = (bytes: number, isDir: boolean) => {
  if (isDir) return "--"
  if (bytes === 0) return "0 B"
  const k = 1024; const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

onMounted(async () => {
  await fetchConfig()
  fetchDirectory("")
  fetchMeta()
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<style scoped>
/* 🚨 高亮对比度与防拖拽屏蔽 */
:deep(input:not([type="checkbox"])), :deep(textarea), :deep(select), .allow-select { user-select: auto !important; -webkit-user-select: auto !important; cursor: text !important; -webkit-app-region: no-drag !important; }

.data-hub-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4; user-select: none;}

/* Header */
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086; cursor: pointer; transition: 0.2s;}
.breadcrumbs h2:hover { color: #b4befe;}
.breadcrumbs h2.active { color: #89b4fa; font-weight: bold;}
.separator { color: #45475a; font-weight: bold;}

.header-actions { display: flex; gap: 15px;}
.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.btn-primary:hover { background: #b4befe; }

/* 🚨 修复 btn-outline 的明亮文字对比度 */
.btn-outline { 
  background: transparent; 
  color: #bac2de; 
  border: 1px dashed #6c7086; 
  padding: 8px 15px; 
  border-radius: 8px; 
  cursor: pointer; 
  font-weight: bold; 
  transition: 0.2s;
  flex-shrink: 0;
}
.btn-outline:hover { 
  color: #89b4fa; 
  border-color: #89b4fa; 
  background: rgba(137, 180, 250, 0.1);
}

.btn-cyan { background: #94e2d5; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.btn-cyan:hover { background: #74c7ec;}
.btn-danger { background: rgba(243, 139, 168, 0.1); color: #f38ba8; border: 1px solid #f38ba8; padding: 8px 15px; border-radius: 6px; cursor: pointer; transition: 0.2s; font-weight: bold;}
.btn-danger:hover { background: #f38ba8; color: #11111b;}
.btn-upload { cursor: pointer; display: flex; align-items: center;}
.btn-small { padding: 6px 12px; font-size: 12px;}
.icon-btn { background: #313244; border: none; color: #cdd6f4; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px;}
.icon-btn:hover:not(:disabled) { background: #45475a; }
.icon-btn:disabled { opacity: 0.5; cursor: not-allowed;}
.w-full { width: 100%; }
.card { background: #181825; border: 1px solid #313244; border-radius: 12px;}

/* === 左栏 === */
.three-column-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}
.column-left { width: 260px; flex-shrink: 0; padding: 20px; display: flex; flex-direction: column; gap: 20px; overflow-y: auto;}
.panel-title { margin: 0; font-size: 16px; color: #89b4fa; padding-bottom: 10px; border-bottom: 1px solid #313244;}
.filter-section { display: flex; flex-direction: column; gap: 8px;}
.filter-label { font-size: 12px; font-weight: bold; color: #a6adc8;}
.filter-value { font-size: 13px; color: #cdd6f4; padding: 8px 12px; background: #11111b; border-radius: 6px; border: 1px solid #45475a;}
.path-text { font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}

.quick-access-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px;}
.qa-item { background: #11111b; border: 1px solid #313244; border-radius: 6px; padding: 8px; font-size: 12px; color: #cdd6f4; display: flex; align-items: center; gap: 8px; cursor: pointer; transition: 0.2s;}
.qa-item:hover { border-color: #89b4fa; background: #1e1e2e;}
.qa-item span { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 4px; font-size: 14px;}

.native-select { background: #11111b; border: 1px solid #45475a; color: #cdd6f4; padding: 8px 10px; border-radius: 6px; outline: none; font-size: 13px;}
.native-select:focus { border-color: #89b4fa;}
.native-select option { background: #181825; color: #cdd6f4; }
.native-select:disabled { opacity: 0.6; cursor: not-allowed; }

.checkbox-grid { display: flex; flex-direction: column; gap: 8px; margin-top: 5px;}
.checkbox-item { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #bac2de; cursor: pointer;}
.checkbox-item input[type="checkbox"] { width: 16px; height: 16px; accent-color: #89b4fa; cursor: pointer;}

.bg-protein { background: rgba(166, 227, 161, 0.2); border: 1px solid #a6e3a1; }
.bg-plasmid { background: rgba(249, 226, 175, 0.2); border: 1px solid #f9e2af; }
.bg-cell { background: rgba(203, 166, 247, 0.2); border: 1px solid #cba6f7; }
.bg-default { background: rgba(137, 180, 250, 0.2); border: 1px solid #89b4fa; }

/* === 中栏 === */
.column-middle { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; position: relative;}
.explorer-toolbar { padding: 15px 20px; border-bottom: 1px solid #313244; display: flex; align-items: center; gap: 15px; background: #11111b; flex-shrink: 0; border-top-left-radius: 12px; border-top-right-radius: 12px;}

.workspace-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; transition: background 0.3s;}
.workspace-content.drag-active { background: rgba(137, 180, 250, 0.05); box-shadow: inset 0 0 0 2px #89b4fa; }

.list-header { display: flex; padding: 10px 20px; font-size: 12px; font-weight: bold; color: #6c7086; border-bottom: 1px solid #313244; background: #181825;}
.col-name { flex: 3; display: flex; align-items: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.col-type { flex: 1.5; color: #bac2de;}
.col-size { flex: 1; text-align: right; color: #bac2de; font-family: monospace;}
.col-date { flex: 1.5; text-align: right; color: #6c7086; font-family: monospace;}

.list-body { flex: 1; overflow-y: auto;}
.list-item { display: flex; align-items: center; padding: 12px 20px; border-bottom: 1px solid #1e1e2e; cursor: pointer; transition: 0.1s;}
.list-item:hover { background: rgba(137, 180, 250, 0.1);}
.list-item.selected { background: rgba(249, 226, 175, 0.15); border-left: 3px solid #f9e2af; padding-left: 17px;}
.file-icon { margin-right: 10px; font-size: 18px;}
.f-name { font-size: 13px; color: #cdd6f4;}
.f-name.is-dir { color: #89b4fa; font-weight: bold;}
.back-item { color: #89b4fa; font-weight: bold; background: rgba(17,17,27,0.5);}
.empty-state { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; color: #a6adc8; pointer-events: none; display: flex; flex-direction: column; align-items: center;}

/* 🚨 无极拖拽面板把手 (Resizer) */
.resize-handle { width: 8px; margin: 0 -4px; cursor: col-resize; z-index: 10; transition: background 0.2s; border-radius: 4px; }
.resize-handle:hover, .resize-handle.active { background: #89b4fa; }

/* === 3. 右侧预览 === */
.column-right { flex-shrink: 0; display: flex; flex-direction: column; overflow: hidden; background: #11111b; padding: 20px; min-width: 250px;}
.preview-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #a6adc8; font-size: 13px; text-align: center; padding: 20px; border: 1px dashed #313244; border-radius: 8px; margin-top: 15px;}
.preview-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; gap: 15px; padding-top: 15px;}
.preview-info-card { display: flex; align-items: center; gap: 15px; padding: 15px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; flex-shrink: 0;}
.p-icon { font-size: 32px;}
.p-details { display: flex; flex-direction: column; overflow: hidden;}
.p-name { font-size: 14px; font-weight: bold; color: #cdd6f4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.p-meta { font-size: 11px; color: #6c7086; margin-top: 5px; font-family: monospace;}

/* 🚨 紧凑版资产标签区 (Tags Insight) */
.tags-insight-section { display: flex; flex-direction: column; gap: 8px; background: #181825; border: 1px solid #313244; border-radius: 8px; padding: 10px; flex-shrink: 0; margin-top: 10px;}
.tags-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed #313244; padding-bottom: 6px;}
.add-tag-btn { background: transparent; border: 1px dashed #45475a; color: #a6adc8; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 10px; font-weight: bold; transition: 0.2s;}
.add-tag-btn:hover { border-color: #89b4fa; color: #89b4fa;}
.tags-container { display: flex; flex-wrap: wrap; gap: 4px; }
.file-tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 6px; border-radius: 4px; border: 1px solid; font-size: 10px; font-weight: bold; }
.tag-close { cursor: pointer; opacity: 0.6; transition: 0.2s; font-size: 10px;}
.tag-close:hover { opacity: 1; color: #f38ba8 !important;}

/* 渲染区域 */
.preview-render-area { flex: 1; background: #181825; border: 1px solid #313244; border-radius: 8px; position: relative; display: flex; flex-direction: column; overflow: hidden;}
.preview-status { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #bac2de; font-size: 13px; text-align: center;}
.preview-status.error { color: #f38ba8; padding: 20px;}
.preview-status.hint { color: #89b4fa; font-weight: bold;}

.media-render { flex: 1; width: 100%; height: 100%; position: relative; display: flex;}
.media-render img { max-width: 100%; max-height: 100%; object-fit: contain; margin: auto;}
.media-render iframe { width: 100%; height: 100%; border: none; background: #fff;}

.code-render { flex: 1; overflow: auto; padding: 10px; background: #1e1e2e;}
.code-render pre { margin: 0; font-family: 'Consolas', monospace; font-size: 11px; color: #cdd6f4; line-height: 1.4;}

/* 3Dmol 右侧小视窗 */
.viewer-3d { width: 100%; height: 100%; }
.viewer-tools { position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%); display: flex; gap: 5px; background: rgba(17, 17, 27, 0.8); padding: 5px; border-radius: 6px; border: 1px solid #45475a;}
.tool-btn-mini { background: transparent; color: #cdd6f4; border: 1px solid #45475a; padding: 4px 8px; border-radius: 4px; cursor: pointer; transition: 0.2s; font-size: 10px;}
.tool-btn-mini:hover { background: #89b4fa; color: #11111b; border-color: #89b4fa;}

.preview-actions-bar { flex-shrink: 0; display: flex; flex-direction: column; margin-top: auto;}

/* 右键菜单 */
.context-menu { position: fixed; background: #181825; border: 1px solid #45475a; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); width: 200px; z-index: 9999; overflow: hidden;}
.ctx-header { padding: 10px 15px; font-size: 11px; color: #89b4fa; font-weight: bold; background: #11111b; border-bottom: 1px solid #313244; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.ctx-item { padding: 10px 15px; font-size: 13px; color: #cdd6f4; cursor: pointer; transition: 0.1s;}
.ctx-item:hover { background: #313244; color: #89b4fa;}
.ctx-item.danger { color: #f38ba8; }
.ctx-item.danger:hover { background: rgba(243, 139, 168, 0.1); }
.ctx-divider { height: 1px; background: #313244; margin: 4px 0;}

/* 🚨 紧凑化标签选择器模态框 */
.tag-section-title { font-size: 12px; font-weight: bold; color: #a6adc8; margin-bottom: 8px;}
.tag-pool { display: flex; flex-wrap: wrap; gap: 6px; padding-bottom: 10px; border-bottom: 1px dashed #313244;}
.pool-tag { padding: 4px 8px; border-radius: 4px; border: 1px solid; font-size: 11px; font-weight: bold; cursor: pointer; transition: 0.2s;}
.pool-tag:hover { transform: scale(1.05); }

.color-picker-dot { width: 24px; height: 24px; border-radius: 50%; cursor: pointer; transition: 0.2s; box-sizing: border-box;}
.color-picker-dot:hover { transform: scale(1.2); }

/* 放大与弹窗 */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(17, 17, 27, 0.85); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; z-index: 10000; }
.fullscreen-modal { width: 90%; height: 90%; max-width: 1400px; display: flex; flex-direction: column; overflow: hidden; border: 1px solid #89b4fa; box-shadow: 0 20px 50px rgba(0,0,0,0.8); }
.modal-content { background: #1e1e2e; border: 1px solid #45475a; border-radius: 12px; display: flex; flex-direction: column; box-shadow: 0 20px 50px rgba(0,0,0,0.5); overflow: hidden;}
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; background: #11111b; border-bottom: 1px solid #313244; flex-shrink: 0;}
.modal-title { font-size: 16px; font-weight: bold; color: #cdd6f4; display: flex; align-items: center; gap: 10px;}
.btn-close { background: transparent; border: none; color: #f38ba8; font-size: 20px; cursor: pointer; transition: 0.2s;}
.btn-close:hover { transform: scale(1.2); }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 15px;}
.modal-footer { padding: 12px 20px; background: #11111b; border-top: 1px solid #313244; display: flex; justify-content: flex-end; gap: 10px;}
.form-group { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.form-group label { font-size: 12px; color: #89b4fa; font-weight: bold;}

.tool-btn { background: transparent; color: #cdd6f4; border: 1px solid #45475a; padding: 8px 15px; border-radius: 6px; cursor: pointer; transition: 0.2s; font-size: 13px; font-weight: bold; }
.tool-btn:hover { background: #89b4fa; color: #11111b; border-color: #89b4fa;}

.spin-loader { display: inline-block; animation: spin 2s linear infinite; font-size: 24px; margin-bottom: 15px;}
@keyframes spin { 100% { transform: rotate(360deg); } }
.fade-in { animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.fade-in-scale { animation: fadeInScale 0.15s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes fadeInScale { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
</style>