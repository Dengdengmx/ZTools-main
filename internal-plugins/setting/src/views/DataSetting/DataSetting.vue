<template>
  <div class="data-hub-view">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2>📊 智能数据中心 (Data Hub)</h2>
      </div>
      <div class="header-actions">
        <button class="btn-outline">📁 打开本地工作区</button>
        <button class="btn-primary" @click="fetchFileList">🔄 同步工作区</button>
      </div>
    </div>

    <div class="split-layout">
      <div class="file-explorer card">
        <div class="explorer-header">
          <h3>SciForge_Workspace</h3>
          <span class="file-count">{{ fileList.length }} 个文件</span>
        </div>
        
        <div class="file-list">
          <div 
            v-for="file in fileList" 
            :key="file.path"
            class="file-item"
            :class="{ active: currentFile?.path === file.path }"
            @click="previewFile(file)"
          >
            <span class="file-icon">{{ getFileIcon(file.name) }}</span>
            <div class="file-info">
              <span class="file-name">{{ file.name }}</span>
              <span class="file-meta">{{ file.size }} • {{ file.date }}</span>
            </div>
          </div>
          
          <div v-if="fileList.length === 0" class="empty-state">
            <div class="empty-hint">工作区空空如也</div>
          </div>
        </div>
      </div>

      <div class="preview-panel card">
        <div class="preview-header" v-if="currentFile">
          <div class="preview-title">
            <span class="file-icon">{{ getFileIcon(currentFile.name) }}</span>
            <h3>{{ currentFile.name }}</h3>
          </div>
          <div class="preview-actions">
            <span class="tag">类型解析: {{ previewType }}</span>
            <button class="icon-btn" title="调用外部程序打开">↗️</button>
          </div>
        </div>

        <div class="preview-content" v-if="currentFile">
          
          <div v-if="isPreviewLoading" class="loading-state">
            <div class="spinner"></div>
            <p>后端策略引擎正在解析文件格式...</p>
          </div>

          <pre v-else-if="previewType === 'text' || previewType === 'sequence'" class="code-preview">{{ previewContent }}</pre>

          <div v-else-if="previewType === 'table'" class="table-preview">
             <div class="table-placeholder">
               <div class="i-z-database" style="font-size: 40px; margin-bottom: 10px; color: #89b4fa;"></div>
               <p>数据表已解析，共 {{ previewMeta?.rows || 0 }} 行数据</p>
               <button class="btn-primary" style="margin-top: 10px;">📊 在独立表格视图中打开</button>
             </div>
          </div>

          <div v-else-if="previewType === 'structure'" class="3d-preview">
             <div class="structure-placeholder">
               <div class="i-z-box" style="font-size: 50px; margin-bottom: 15px; color: #a6e3a1;"></div>
               <p>🧬 检测到大分子结构文件 (PDB/CIF)</p>
               <div class="meta-tags" style="margin-top: 10px;">
                 <span class="tag">原子数: {{ previewMeta?.atoms || '未知' }}</span>
                 <span class="tag">残基数: {{ previewMeta?.residues || '未知' }}</span>
               </div>
               <button class="btn-outline" style="margin-top: 20px;">调用 PyMOL/3Dmol.js 渲染</button>
             </div>
          </div>

          <div v-else-if="previewType === 'image'" class="image-preview">
             <img :src="previewContent" alt="预览图" />
          </div>

          <div v-else class="unsupported-preview">
            <p>该文件格式暂不支持内置预览</p>
            <p class="sub-text">你可以配置 SciForge_2 后端的策略解析器来支持它</p>
          </div>

        </div>

        <div v-else class="empty-state" style="height: 100%; display: flex; flex-direction: column; justify-content: center;">
          <div class="i-z-file empty-icon" style="font-size: 64px;"></div>
          <div class="empty-text">选择左侧文件以进行智能解析预览</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const fileList = ref<any[]>([])
const currentFile = ref<any>(null)
const isPreviewLoading = ref(false)

// 预览引擎状态
const previewType = ref('text') 
const previewContent = ref('')
const previewMeta = ref<any>({})

const getFileIcon = (filename: string) => {
  if (filename.endsWith('.fasta') || filename.endsWith('.seq')) return '🔤'
  if (filename.endsWith('.pdb') || filename.endsWith('.cif')) return '🧬'
  if (filename.endsWith('.csv') || filename.endsWith('.xlsx')) return '📊'
  if (filename.endsWith('.py') || filename.endsWith('.json')) return '🧑‍💻'
  if (filename.endsWith('.png') || filename.endsWith('.jpg')) return '🖼️'
  if (filename.endsWith('.ab1')) return '📈'
  return '📄'
}

// 模拟向 FastAPI 获取工作区文件列表
const fetchFileList = async () => {
  // TODO: 这里未来接 FastAPI 的 /api/data/list 接口
  // 先用假数据让你看看前端效果
  fileList.value = [
    { name: 'AF3_prediction_result.pdb', path: '/workspace/AF3_prediction_result.pdb', size: '2.4 MB', date: '2026-03-30' },
    { name: 'wildtype_sequence.fasta', path: '/workspace/wildtype_sequence.fasta', size: '12 KB', date: '2026-03-29' },
    { name: 'SPR_binding_kinetics.csv', path: '/workspace/SPR_binding_kinetics.csv', size: '450 KB', date: '2026-03-31' },
    { name: 'AKTA_purification_run.txt', path: '/workspace/AKTA_purification_run.txt', size: '1.2 MB', date: '2026-03-31' },
    { name: 'sanger_sequencing_01.ab1', path: '/workspace/sanger_sequencing_01.ab1', size: '210 KB', date: '2026-03-28' },
  ]
}

// 调用后端的策略预览引擎
const previewFile = async (file: any) => {
  currentFile.value = file
  isPreviewLoading.value = true
  
  try {
    // 真实情况：请求我们在 Python 里写的 preview_engine 接口
    // const res = await fetch(`http://127.0.0.1:8080/api/data/preview?file_path=${encodeURIComponent(file.path)}`)
    // const json = await res.json()
    // previewType.value = json.type
    // previewContent.value = json.content
    // previewMeta.value = json.meta
    
    // 模拟后端根据不同文件类型返回的解析结果
    setTimeout(() => {
      if (file.name.endsWith('.pdb')) {
        previewType.value = 'structure'
        previewMeta.value = { atoms: 4521, residues: 350 }
      } else if (file.name.endsWith('.fasta')) {
        previewType.value = 'sequence'
        previewContent.value = ">protein_sequence\nMVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHG..."
      } else if (file.name.endsWith('.csv')) {
        previewType.value = 'table'
        previewMeta.value = { rows: 2450 }
      } else {
        previewType.value = 'text'
        previewContent.value = "Date: 2026-03-31\nLog: Process started successfully.\n..."
      }
      isPreviewLoading.value = false
    }, 400) // 模拟网络延迟
    
  } catch (e) {
    console.error("预览失败", e)
    isPreviewLoading.value = false
  }
}

onMounted(() => {
  fetchFileList()
})
</script>

<style scoped>
.data-hub-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4;}
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #cba6f7; font-weight: bold;}
.header-actions { display: flex; gap: 10px;}

.btn-primary { background: #cba6f7; color: #11111b; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.btn-primary:hover { background: #b4befe;}
.btn-outline { background: transparent; color: #a6adc8; border: 1px dashed #45475a; padding: 8px 15px; border-radius: 8px; cursor: pointer; transition: 0.2s;}
.btn-outline:hover { border-color: #cba6f7; color: #cba6f7;}
.icon-btn { background: #313244; color: #cdd6f4; border: none; padding: 6px 10px; border-radius: 6px; cursor: pointer; transition: 0.2s;}
.icon-btn:hover { background: #45475a;}

.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}

/* 左侧文件列表 */
.file-explorer { flex: 1; max-width: 350px; background: #181825; border: 1px solid #313244; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden;}
.explorer-header { padding: 15px 20px; border-bottom: 1px solid #313244; display: flex; justify-content: space-between; align-items: center; background: #11111b;}
.explorer-header h3 { margin: 0; font-size: 15px; color: #bac2de;}
.file-count { font-size: 12px; color: #6c7086; background: #313244; padding: 2px 8px; border-radius: 10px;}

.file-list { flex: 1; overflow-y: auto; padding: 10px;}
.file-item { display: flex; align-items: center; padding: 12px 15px; border-radius: 8px; cursor: pointer; transition: 0.2s; border: 1px solid transparent;}
.file-item:hover { background: #1e1e2e; border-color: #313244;}
.file-item.active { background: rgba(203, 166, 247, 0.1); border-color: #cba6f7;}
.file-icon { font-size: 20px; margin-right: 12px;}
.file-info { display: flex; flex-direction: column; overflow: hidden;}
.file-name { font-size: 14px; color: #cdd6f4; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px;}
.file-meta { font-size: 11px; color: #6c7086;}

/* 右侧预览面板 */
.preview-panel { flex: 2; background: #181825; border: 1px solid #313244; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden;}
.preview-header { padding: 15px 20px; border-bottom: 1px solid #313244; display: flex; justify-content: space-between; align-items: center; background: #1e1e2e;}
.preview-title { display: flex; align-items: center; gap: 10px;}
.preview-title h3 { margin: 0; font-size: 16px; color: #cdd6f4;}
.preview-actions { display: flex; align-items: center; gap: 10px;}
.tag { font-size: 11px; background: #313244; padding: 4px 10px; border-radius: 6px; color: #bac2de; border: 1px solid #45475a;}

.preview-content { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column;}

/* 各种预览器专属样式 */
.code-preview { margin: 0; background: #11111b; padding: 20px; border-radius: 8px; border: 1px solid #313244; color: #a6e3a1; font-family: 'Fira Code', monospace; font-size: 13px; line-height: 1.6; overflow-x: auto; flex: 1;}

.table-placeholder, .structure-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; background: #11111b; border-radius: 8px; border: 1px dashed #45475a; color: #a6adc8;}
.meta-tags { display: flex; gap: 10px;}

.unsupported-preview { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #f38ba8;}
.sub-text { color: #6c7086; font-size: 13px; margin-top: 5px;}

/* 状态提示 */
.empty-state { text-align: center; color: #6c7086;}
.empty-text { font-size: 18px; font-weight: bold; color: #bac2de; margin-top: 15px;}
.loading-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #cba6f7;}
.spinner { width: 30px; height: 30px; border: 3px solid rgba(203, 166, 247, 0.3); border-top-color: #cba6f7; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 15px;}
@keyframes spin { to { transform: rotate(360deg); } }
</style>