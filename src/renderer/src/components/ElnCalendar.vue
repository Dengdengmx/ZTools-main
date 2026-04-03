<template>
  <div class="eln-calendar-view fade-in">
    <header class="app-header">
      <div class="header-left">
        <h2>📓 实验日历 (ELN)</h2>
        <div class="month-nav">
          <button class="btn-icon" @click="changeMonth(-1)">◀</button>
          <span class="month-display">{{ currentMonthDisplay }}</span>
          <button class="btn-icon" @click="changeMonth(1)">▶</button>
        </div>
      </div>
      <div class="header-right">
        <button class="btn-primary" @click="batchExportZIP" title="将本月报告打包为 ZIP">📦 本月打包 ZIP</button>
      </div>
    </header>

    <div class="calendar-layout">
      <div class="calendar-grid-container">
        <div class="weekdays">
          <div class="weekday">周一</div><div class="weekday">周二</div><div class="weekday">周三</div>
          <div class="weekday">周四</div><div class="weekday">周五</div><div class="weekday">周六</div>
          <div class="weekday">周日</div>
        </div>
        
        <div class="calendar-track-wrapper">
          <div class="calendar-track">
            <div 
              v-for="day in calendarDays" 
              :key="day.dateStr"
              class="day-cell"
              :class="{ 'other-month': day.isOtherMonth, 'selected': day.dateStr === selectedDateStr, 'today': day.isToday }"
              @click="selectDate(day.dateStr)"
            >
              <div class="day-header"><span class="date-num">{{ day.date.getDate() }}</span></div>
              <div class="day-items">
                <div 
                  v-for="item in day.items" 
                  :key="item.id"
                  class="day-item-block"
                  :style="{ backgroundColor: getHashColor(item.type) }"
                  @dblclick.stop="openReportModal(day.dateStr, item.id)"
                  :title="'双击查看: ' + getTemplateName(item.type) + (item.sample ? ' - ' + item.sample : '')"
                >
                  <span class="item-text">{{ getTemplateShortName(item.type) }} {{ item.sample ? item.sample : '' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="sidebar">
        <div class="sidebar-header">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
            <h3>📝 当日实验日程</h3>
            <button v-if="!isBatchDeleteMode" class="btn-text btn-batch-del" @click="toggleBatchDeleteMode">🗑️ 批量删除</button>
            <div v-else style="display: flex; gap: 5px;">
              <button class="btn-text btn-batch-confirm" @click="confirmBatchDelete">✔ 删除({{ selectedForBatchDelete.length }})</button>
              <button class="btn-text btn-batch-cancel" @click="toggleBatchDeleteMode">取消</button>
            </div>
          </div>
          <div class="selected-date-highlight">{{ selectedDateStr || '请选择日期' }}</div>
        </div>
        
        <div class="workflow-actions">
          <div class="add-dropdown">
            <select v-model="selectedTemplateToAdd" class="native-select flex-1">
              <option value="free">📝 自由便签</option>
              <option disabled>--- 实验模板 ---</option>
              <option v-for="(tpl, id) in customTemplates" :key="id" :value="id">
                {{ tpl.name }}
              </option>
            </select>
            <button class="btn-primary" @click="addExperimentBlock">➕ 添加</button>
          </div>
          <div class="hook-row">
            <button class="btn-outline hook-btn" @click="openTemplateEditor">🛠️ 模板制作器</button>
            <button class="btn-outline hook-btn" @click="triggerPluginHook">⚡ 联动算力</button>
          </div>
          <div class="save-status" :class="{ 'saving': isSaving }">{{ saveStatusText }}</div>
        </div>

        <div class="compact-list-container">
          <div v-if="(schedules[selectedDateStr] || []).length === 0" class="empty-hint">
            今日暂无实验计划，请在上方添加。
          </div>
          
          <div 
            v-for="item in schedules[selectedDateStr] || []" 
            :key="item.id" 
            class="compact-item"
            :class="[item.status, { 'is-batching': isBatchDeleteMode }]"
            :style="{ borderLeftColor: getHashColor(item.type) }"
            @click="isBatchDeleteMode ? toggleSelection(item.id) : null"
          >
            <input 
              v-if="isBatchDeleteMode" 
              type="checkbox" 
              class="batch-checkbox"
              :checked="selectedForBatchDelete.includes(item.id)"
              @change.stop="toggleSelection(item.id)"
            />

            <div class="item-tpl-tag" :style="{ backgroundColor: getHashColor(item.type) }" :title="getTemplateShortName(item.type)">
              {{ getTemplateShortName(item.type) }}
            </div>
            
            <textarea 
              v-model="item.sample" 
              class="item-sample-textarea allow-select" 
              placeholder="样本或编号 (@ 唤起引用)..." 
              @input="(e) => handleSampleInput(e, item)"
              @blur="hideMentionDelay"
              @click.stop
              rows="1"
              :disabled="isBatchDeleteMode"
            ></textarea>
            
            <div v-if="activeMentionItemId === item.id" class="mention-popover fade-in-scale">
              <div class="mention-header">智能全局引用</div>
              <div class="mention-list">
                <div 
                  class="mention-item" 
                  v-for="opt in filteredMentions" 
                  :key="opt.val" 
                  @mousedown.prevent="insertMention(item, opt)"
                >
                  {{ opt.label }}
                </div>
                <div v-if="filteredMentions.length === 0" class="empty-hint" style="margin: 10px;">未找到匹配项</div>
              </div>
            </div>

            <div class="item-actions" v-if="!isBatchDeleteMode">
              <button v-if="item.status === 'planned' && item.type !== 'free'" class="act-btn btn-add" @click.stop="openParamInputModal(item)" title="录入参数">➕</button>
              <button v-if="item.status === 'completed' || item.type === 'free'" class="act-btn btn-doc" @click.stop="openReportModal(selectedDateStr, item.id)" title="详细报告">📄</button>
              <button class="act-btn btn-del" @click.stop="deleteItem(item.id)" title="删除此条">✖</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showParamModal" class="eln-modal-overlay" @click.self="showParamModal = false">
      <div class="param-modal-content fade-in-scale">
        <div class="modal-header">
          <div class="modal-title">✍️ 录入参数：{{ getTemplateName(activeParamItem?.type || '') }}</div>
          <button class="btn-close" @click="showParamModal = false">✖</button>
        </div>
        <div class="modal-body param-form-body">
          <p class="form-hint">填写下方挖空的变量，系统将自动生成完整的 Markdown 实验报告。</p>
          <div class="param-grid">
            <div class="param-field" v-for="field in extractedFields" :key="field">
              <label>{{ field }}</label>
              <input v-model="paramFormData[field]" type="text" class="native-input allow-select" :placeholder="'输入 ' + field" />
            </div>
          </div>
          <div v-if="extractedFields.length === 0" class="empty-hint">
            该模板未设置任何变量(挖空)。请直接生成报告或去模板制作器中添加 <span v-pre>{{变量}}</span>。
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-primary" @click="generateReportFromParams">🚀 生成最终报告</button>
        </div>
      </div>
    </div>

    <div v-if="showTemplateModal" class="eln-modal-overlay" @click.self="showTemplateModal = false">
      <div class="template-modal-content fade-in-scale">
        <div class="modal-header">
          <div class="modal-title">🛠️ 原生模板制作器</div>
          <div class="modal-actions">
            <button class="btn-primary" @click="saveTemplates">💾 永久保存库</button>
            <button class="btn-close" @click="showTemplateModal = false">✖</button>
          </div>
        </div>
        
        <div class="template-modal-body">
          <div class="template-sidebar">
            <div 
              v-for="(tpl, id) in customTemplates" 
              :key="id" 
              class="tpl-list-item"
              :class="{ 'active': editingTemplateId === id }"
              @click="editingTemplateId = id"
              :title="tpl.name"
            >
              {{ tpl.name }}
            </div>
            <button class="btn-outline add-tpl-btn" @click="addNewTemplate">+ 新建模板</button>
          </div>
          
          <div class="template-main" v-if="editingTemplateId && customTemplates[editingTemplateId]">
            <div class="tpl-toolbar-top">
              <input 
                v-model="customTemplates[editingTemplateId].name" 
                class="tpl-input-field flex-2 allow-select" 
                placeholder="模板全称 (如: 蛋白表达与纯化)" 
              />
              <input 
                v-model="customTemplates[editingTemplateId].shortName" 
                class="tpl-input-field flex-1 allow-select" 
                placeholder="日历简写 (如: 纯化)" 
              />
              <button class="btn-outline tool-btn" @click="makeVariable" title="在下方选中文字后点击">✂️ 挖空变量</button>
              <button class="btn-outline btn-delete-tpl" @click="deleteTemplate(editingTemplateId)" title="删除此模板">🗑️</button>
            </div>

            <div class="tpl-hint-bar">
              💡 提示：在下方编辑器中选中任意文字，点击上方「✂️ 挖空变量」即可生成对应的填空项。
            </div>

            <textarea 
              ref="tplTextareaRef"
              v-model="customTemplates[editingTemplateId].content" 
              class="tpl-content-input allow-select" 
              placeholder="在这里输入 Markdown 格式的实验报告模板内容..."
            ></textarea>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showModal" class="eln-modal-overlay" @click.self="closeModal">
      <div class="eln-modal-content fade-in-scale">
        <div class="modal-header">
          <div class="modal-title">
            <span class="tag-date">{{ activeDate }}</span> {{ activeItemTitle }}
          </div>
          <div class="modal-actions">
            <button class="btn-text" @click="exportPDF">📄 导出 PDF</button>
            <button class="btn-primary" @click="saveModalContent">✔ 封存记录</button>
            <button class="btn-close" @click="closeModal">✖</button>
          </div>
        </div>
        <div class="modal-body">
          <textarea ref="mdeTextarea" class="allow-select"></textarea>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import EasyMDE from 'easymde'
import 'easymde/dist/easymde.min.css'
import html2pdf from 'html2pdf.js'
import JSZip from 'jszip'

interface ExperimentItem {
  id: string; title: string; sample: string; type: string; 
  status: 'planned' | 'completed'; parameters: Record<string, string>; content: string;
}
interface TemplateDef { name: string; shortName: string; content: string; }

const schedules = ref<Record<string, ExperimentItem[]>>({})
const currentDate = ref(new Date())
const selectedDateStr = ref('')
const isSaving = ref(false)
const saveStatusText = ref('')
let saveTimer: any = null

// --- @ 智能引用系统 ---
const activeMentionItemId = ref<string | null>(null)
const mentionQuery = ref('')

const globalAssets = [
  { type: 'sample', label: '🧪 pET-28a 空载质粒', val: '[@pET-28a]' },
  { type: 'sample', label: '🧫 HEK293T 表达株', val: '[@HEK293T]' },
  { type: 'sample', label: '🧪 蛋白 Marker (大分子)', val: '[@Marker-L]' },
  { type: 'plugin', label: '🚀 AlphaFold 3 预测引擎', val: '[@AlphaFold3]' },
  { type: 'plugin', label: '🚀 Rosetta 序列设计', val: '[@RFdiffusion]' },
  { type: 'data', label: '📊 NGS_测序结果.ab1', val: '[@测序结果]' }
]

const filteredMentions = computed(() => {
  if (!mentionQuery.value) return globalAssets;
  const q = mentionQuery.value.toLowerCase();
  return globalAssets.filter(o => o.label.toLowerCase().includes(q) || o.val.toLowerCase().includes(q))
})

const handleSampleInput = (e: Event, item: ExperimentItem) => {
  const target = e.target as HTMLTextAreaElement;
  target.style.height = 'auto';
  target.style.height = (target.scrollHeight) + 'px';

  const val = target.value;
  const cursor = target.selectionStart;
  const textBeforeCursor = val.substring(0, cursor);
  
  const match = textBeforeCursor.match(/@([^\s]*)$/);

  if (match) {
    activeMentionItemId.value = item.id;
    mentionQuery.value = match[1];
  } else {
    activeMentionItemId.value = null;
  }

  clearTimeout(saveTimer);
  saveStatusText.value = '输入中...';
  saveTimer = setTimeout(() => { autoSave(); }, 1000);
}

const insertMention = (item: ExperimentItem, opt: any) => {
  const match = item.sample.match(/@([^\s]*)$/);
  if (match) {
    item.sample = item.sample.substring(0, match.index) + opt.val + ' ' + item.sample.substring(match.index + match[0].length);
  } else {
    item.sample += opt.val + ' ';
  }
  activeMentionItemId.value = null;
  autoSave();
}

const hideMentionDelay = () => { setTimeout(() => { activeMentionItemId.value = null; }, 200); }

// --- 批量删除管理模式 ---
const isBatchDeleteMode = ref(false)
const selectedForBatchDelete = ref<string[]>([])

const toggleBatchDeleteMode = () => { isBatchDeleteMode.value = !isBatchDeleteMode.value; selectedForBatchDelete.value = [] }

const toggleSelection = (id: string) => {
  const idx = selectedForBatchDelete.value.indexOf(id)
  if (idx > -1) selectedForBatchDelete.value.splice(idx, 1)
  else selectedForBatchDelete.value.push(id)
}

const confirmBatchDelete = () => {
  if (selectedForBatchDelete.value.length === 0) return alert("请先选中需要删除的条目")
  if (confirm(`⚠️ 确定要删除选中的 ${selectedForBatchDelete.value.length} 个实验条目吗？`)) {
    schedules.value[selectedDateStr.value] = schedules.value[selectedDateStr.value].filter(i => !selectedForBatchDelete.value.includes(i.id))
    autoSave(); isBatchDeleteMode.value = false; selectedForBatchDelete.value = []
  }
}

// --- 模板制作器系统 ---
const showTemplateModal = ref(false)
const editingTemplateId = ref('')
const tplTextareaRef = ref<HTMLTextAreaElement | null>(null)

const defaultTemplates: Record<string, TemplateDef> = {
  'tpl_pcr': { 
    name: '🧬 PCR 扩增体系', shortName: 'PCR',
    content: '### 🧬 PCR 扩增记录\n**样本:** {{样本编号}}\n**引物:** F: {{正向引物}} / R: {{反向引物}}\n\n**反应体系 (25 μL):**\n- Mix: 12.5 μL\n- Primer: 各 1 μL\n- 模板: {{模板体积}} μL\n- ddH2O: 补齐\n\n**退火温度:** {{退火温度}}℃' 
  },
  'tpl_protein': { 
    name: '🧪 蛋白表达与纯化', shortName: '纯化',
    content: '### 🧪 蛋白表达与纯化\n**目标蛋白:** {{蛋白名称}}\n**宿主菌:** {{宿主菌株}}\n**诱导条件:** {{诱导浓度}}mM IPTG, {{诱导温度}}℃\n**纯化策略:** Ni-NTA\n**洗脱液:** {{洗脱浓度}}mM Imidazole' 
  }
}

const loadTemplates = (): Record<string, TemplateDef> => {
  const local = JSON.parse(localStorage.getItem('mtools_eln_templates') || '{}')
  if (Object.keys(local).length === 0) return JSON.parse(JSON.stringify(defaultTemplates))
  for (const k in local) { if (!local[k].shortName) local[k].shortName = local[k].name.substring(0, 4) }
  return local
}
const customTemplates = ref<Record<string, TemplateDef>>(loadTemplates())

const openTemplateEditor = () => { showTemplateModal.value = true; editingTemplateId.value = Object.keys(customTemplates.value)[0] || '' }

const addNewTemplate = () => {
  const newId = 'tpl_' + Date.now()
  customTemplates.value[newId] = { name: '新建模板', shortName: '未命名', content: '变量演示：{{变量名}}' }
  editingTemplateId.value = newId
}

const deleteTemplate = (id: string) => {
  if (Object.keys(customTemplates.value).length <= 1) return alert('至少需要保留一个模板！')
  if (confirm('确定永久删除该模板吗？(已生成的报告不受影响)')) {
    delete customTemplates.value[id]
    editingTemplateId.value = Object.keys(customTemplates.value)[0] || ''
    localStorage.setItem('mtools_eln_templates', JSON.stringify(customTemplates.value))
  }
}

const saveTemplates = () => { localStorage.setItem('mtools_eln_templates', JSON.stringify(customTemplates.value)); showTemplateModal.value = false; autoSave() }

const makeVariable = () => {
  const el = tplTextareaRef.value
  if (!el) return
  const start = el.selectionStart; const end = el.selectionEnd; const val = el.value
  let varName = "新变量"
  if (start !== end) varName = val.substring(start, end)
  const newText = val.substring(0, start) + `{{${varName}}}` + val.substring(end)
  customTemplates.value[editingTemplateId.value].content = newText
}

// --- 右侧工作流卡片系统 ---
const selectedTemplateToAdd = ref('free')

const addExperimentBlock = () => {
  if (!selectedDateStr.value) return
  if (!schedules.value[selectedDateStr.value]) schedules.value[selectedDateStr.value] = []
  
  const type = selectedTemplateToAdd.value
  schedules.value[selectedDateStr.value].push({
    id: 'id_' + Math.random().toString(36).substr(2, 9), title: '', sample: '', type: type,
    status: type === 'free' ? 'completed' : 'planned', parameters: {}, content: ''
  })
  autoSave()
}

const deleteItem = (id: string) => { if (confirm("确定要删除这个实验块吗？")) { schedules.value[selectedDateStr.value] = schedules.value[selectedDateStr.value].filter(i => i.id !== id); autoSave() } }

const getTemplateName = (type: string) => { return type === 'free' || !type ? '📝 便签' : (customTemplates.value[type]?.name || '未知模板') }
const getTemplateShortName = (type: string) => { return type === 'free' || !type ? '便签' : (customTemplates.value[type]?.shortName || customTemplates.value[type]?.name.substring(0, 4) || '未知') }

// --- 录入参数引擎 ---
const showParamModal = ref(false)
const activeParamItem = ref<ExperimentItem | null>(null)
const extractedFields = ref<string[]>([])
const paramFormData = ref<Record<string, string>>({})

const extractFieldsFromTemplate = (content: string) => {
  const regex = /\{\{([^}]+)\}\}/g; const fields: string[] = []; let match;
  while ((match = regex.exec(content)) !== null) { if (!fields.includes(match[1])) fields.push(match[1]) }
  return fields
}

const openParamInputModal = (item: ExperimentItem) => {
  activeParamItem.value = item; const tplContent = customTemplates.value[item.type]?.content || ''
  extractedFields.value = extractFieldsFromTemplate(tplContent); paramFormData.value = {}
  extractedFields.value.forEach(f => { paramFormData.value[f] = item.parameters?.[f] || '' })
  showParamModal.value = true
}

const generateReportFromParams = () => {
  if (!activeParamItem.value) return
  let generatedMarkdown = customTemplates.value[activeParamItem.value.type]?.content || ''
  extractedFields.value.forEach(field => {
    const val = paramFormData.value[field] || '____'
    generatedMarkdown = generatedMarkdown.replace(new RegExp(`\\{\\{${field}\\}\\}`, 'g'), val)
  })
  
  activeParamItem.value.parameters = { ...paramFormData.value }; activeParamItem.value.content = generatedMarkdown; activeParamItem.value.status = 'completed'
  showParamModal.value = false; autoSave(); openReportModal(selectedDateStr.value, activeParamItem.value.id)
}

// --- 完整报告 Modal 引擎 ---
const showModal = ref(false); const activeDate = ref(''); const activeEditId = ref(''); const activeItemTitle = ref('')
const mdeTextarea = ref<HTMLTextAreaElement | null>(null)
let mdeInstance: any = null

const openReportModal = (dateStr: string, id: string) => {
  activeDate.value = dateStr; activeEditId.value = id; const item = schedules.value[dateStr].find(i => i.id === id)
  if (!item) return
  
  activeItemTitle.value = getTemplateName(item.type) + (item.sample ? ` - ${item.sample}` : '')
  showModal.value = true
  
  nextTick(() => {
    if (!mdeInstance) {
      mdeInstance = new EasyMDE({
        element: mdeTextarea.value!, spellChecker: false, placeholder: "支持 Markdown 语法，详细实验报告...",
        toolbar: ["bold", "italic", "heading", "|", "quote", "unordered-list", "ordered-list", "|", "link", "image", "table", "|", "preview", "side-by-side", "fullscreen", "guide"]
      })
    }
    mdeInstance.value(item.content || ''); setTimeout(() => { mdeInstance.codemirror.refresh() }, 100)
  })
}

const closeModal = () => {
  if (mdeInstance) { mdeInstance.toTextArea(); mdeInstance = null; }
  showModal.value = false;
}

const saveModalContent = async () => {
  const item = schedules.value[activeDate.value].find(i => i.id === activeEditId.value)
  if (item && mdeInstance) { item.content = mdeInstance.value(); await saveDataToBackend(); closeModal() }
}

onMounted(async () => {
  const today = new Date(); const dStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`
  selectedDateStr.value = dStr; await loadData()
})

onUnmounted(() => { if (mdeInstance) { mdeInstance.toTextArea(); mdeInstance = null } })

const loadData = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/data/read_file?path=04_Reports/sciforge_eln_data.json')
    const json = await res.json()
    if (json.code === 200 && json.data) {
      const rawData = JSON.parse(json.data)
      for (const date in rawData) {
        rawData[date] = rawData[date].map((i: any) => ({ ...i, type: i.type || 'free', sample: i.sample || '', status: i.status || (i.content ? 'completed' : 'planned'), parameters: i.parameters || {} }))
      }
      schedules.value = rawData
    }
  } catch (e) { console.error("读取失败", e) }
}

const autoSave = () => { saveDataToBackend() }
const saveDataToBackend = async () => {
  try {
    isSaving.value = true; saveStatusText.value = '同步中...'
    await fetch('http://127.0.0.1:8080/api/data/save_file', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: '04_Reports', filename: 'sciforge_eln_data.json', content: JSON.stringify(schedules.value, null, 2) }) })
    saveStatusText.value = '✔ 已同步'; setTimeout(() => { saveStatusText.value = '' }, 2000)
  } catch (e) { saveStatusText.value = '❌ 同步失败' } finally { isSaving.value = false }
}

const currentMonthDisplay = computed(() => `${currentDate.value.getFullYear()}年 ${currentDate.value.getMonth() + 1}月`)
const changeMonth = (delta: number) => { currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() + delta, 1) }

const calendarDays = computed(() => {
  const y = currentDate.value.getFullYear(), m = currentDate.value.getMonth()
  const firstDay = new Date(y, m, 1); let startOff = (firstDay.getDay() || 7) - 1
  const todayStr = `${new Date().getFullYear()}-${String(new Date().getMonth()+1).padStart(2,'0')}-${String(new Date().getDate()).padStart(2,'0')}`; const days: any[] = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(y, m, 1); d.setDate(i - startOff + 1)
    const dStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
    days.push({ date: d, dateStr: dStr, isOtherMonth: d.getMonth() !== m, isToday: dStr === todayStr, items: schedules.value[dStr] || [] })
  }
  return days
})

const selectDate = (dStr: string) => { 
  selectedDateStr.value = dStr
  isBatchDeleteMode.value = false 
  selectedForBatchDelete.value = []
}
const hashString = (str: string) => { let h = 0; for (let i = 0; i < str.length; i++) h = str.charCodeAt(i) + ((h << 5) - h); return h; }
const getHashColor = (seed: string) => { if (seed === 'free') return '#45475a'; return `hsl(${Math.abs(hashString(seed) % 360)}, 65%, 45%)` }

const triggerPluginHook = () => alert('⚡ 底层算力挂钩已触发：将自动识别参数推流至 BioPlugins。')

const exportPDF = () => {
  if (!mdeInstance || !mdeInstance.value().trim()) return alert("内容为空，无法导出！")
  const htmlContent = mdeInstance.options.previewRender(mdeInstance.value())
  const printContainer = document.createElement('div')
  printContainer.innerHTML = `<div style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.6; padding: 20px;"><h2 style="border-bottom: 2px solid #333; padding-bottom: 10px;">[${activeDate.value}] ${activeItemTitle.value}</h2>${htmlContent}</div>`
  html2pdf().set({ margin: [15, 15, 15, 15], filename: `${activeDate.value}_${activeItemTitle.value.replace(/[:\/\\]/g, '_')}.pdf`, image: { type: 'jpeg', quality: 0.98 }, html2canvas: { scale: 2, useCORS: true }, jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' } }).from(printContainer).save()
}

const batchExportZIP = async () => {
  const y = currentDate.value.getFullYear(), m = currentDate.value.getMonth() + 1
  const monthPrefix = `${y}-${String(m).padStart(2, '0')}`; const zip = new JSZip(); let pdfCount = 0
  isSaving.value = true; saveStatusText.value = `🚀 打包中...`
  for (let dateStr in schedules.value) {
    if (dateStr.startsWith(monthPrefix)) {
      for (let item of schedules.value[dateStr]) {
        if (item.content && item.content.trim() !== "") {
          const htmlContent = EasyMDE.prototype.markdown(item.content)
          const printContainer = document.createElement('div')
          printContainer.innerHTML = `<div style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.6; padding: 20px;"><h2 style="border-bottom: 2px solid #333; padding-bottom: 10px;">[${dateStr}] ${getTemplateName(item.type)}</h2>${htmlContent}</div>`
          const pdfBlob = await html2pdf().set({ margin: [15, 15, 15, 15], filename: `temp.pdf`, image: { type: 'jpeg', quality: 0.98 }, html2canvas: { scale: 2, useCORS: true }, jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' } }).from(printContainer).output('blob')
          zip.file(`${dateStr}_${getTemplateName(item.type)}.pdf`, pdfBlob); pdfCount++
        }
      }
    }
  }
  if (pdfCount === 0) { isSaving.value = false; saveStatusText.value = ""; return alert(`抱歉，本月无内容可打包！`) }
  const content = await zip.generateAsync({ type: "blob" }); const a = document.createElement("a"); a.href = URL.createObjectURL(content); a.download = `SciForge_Archive.zip`; a.click()
  isSaving.value = false; saveStatusText.value = `✔ 完成`; setTimeout(() => saveStatusText.value = "", 4000)
}
</script>

<style scoped>
/* 🚨 核心拦截防线：确保所有可输入元素和 .allow-select 类不受外层 user-select: none 的干扰 */
:deep(input:not([type="checkbox"])), :deep(textarea), :deep(select), .allow-select {
  user-select: auto !important;
  -webkit-user-select: auto !important;
  cursor: text !important;
}

.eln-calendar-view { height: 100%; display: flex; flex-direction: column; color: #cdd6f4; overflow: hidden; padding: 0 20px 20px 20px; user-select: none; }

/* 导航 */
.app-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-shrink: 0;}
.header-left { display: flex; align-items: center; gap: 20px;}
.app-header h2 { margin: 0; font-size: 24px; color: #cdd6f4; }
.month-nav { display: flex; align-items: center; background: #181825; border: 1px solid #313244; border-radius: 8px; padding: 4px; }
.btn-icon { background: transparent; border: none; color: #a6adc8; padding: 5px 15px; cursor: pointer; border-radius: 4px; font-size: 16px;}
.btn-icon:hover { background: #313244; color: #89b4fa; }
.month-display { font-size: 16px; font-weight: bold; margin: 0 15px; width: 100px; text-align: center; color: #89b4fa;}

.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; transition: 0.2s;}
.btn-primary:hover { background: #b4befe; }
.btn-outline { background: transparent; color: #a6adc8; border: 1px solid #45475a; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px;}
.btn-outline:hover { background: #313244; color: #cdd6f4;}

.calendar-layout { display: flex; gap: 20px; flex: 1; min-height: 0; }

/* 🚨 左侧网格：绝对等宽与极端防爆处理 */
.calendar-grid-container { flex: 1; display: flex; flex-direction: column; background: #181825; border: 1px solid #313244; border-radius: 12px; overflow: hidden; }
.weekdays { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); background: #11111b; border-bottom: 1px solid #313244; flex-shrink: 0;}
.weekday { padding: 12px; text-align: center; font-weight: bold; color: #a6adc8; font-size: 13px; }
.calendar-track-wrapper { flex: 1; overflow-y: auto; background: #313244; }
.calendar-track { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); grid-auto-rows: minmax(130px, max-content); gap: 1px; }

/* 防止网格被撑开的绝对锁定 */
.day-cell { background: #181825; padding: 8px; display: flex; flex-direction: column; cursor: pointer; height: 100%; min-width: 0; overflow: hidden;}
.day-cell:hover { background: #1e1e2e; }
.day-cell.other-month { opacity: 0.4; }
.day-cell.selected { background: rgba(137, 180, 250, 0.1); box-shadow: inset 0 0 0 1px #89b4fa; }
.day-cell.today .date-num { background: #f38ba8; color: #11111b; padding: 2px 6px; border-radius: 4px; font-weight: bold;}

.day-header { text-align: right; margin-bottom: 5px; }
.date-num { font-size: 13px; color: #bac2de; }

/* 日历中的小色块防爆处理 */
.day-items { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0; overflow-x: hidden; overflow-y: auto; }
.day-item-block { 
  display: block; /* 强制块级以支持 ellipsis */
  padding: 4px 6px; border-radius: 4px; color: #ffffff; font-size: 11px; font-weight: bold; 
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; box-sizing: border-box; width: 100%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3); transition: transform 0.1s;
}
.day-item-block:hover { transform: scale(1.02); }

/* 右侧边栏 */
.sidebar { width: 340px; display: flex; flex-direction: column; background: #181825; border: 1px solid #313244; border-radius: 12px; padding: 20px; flex-shrink: 0; overflow-x: hidden;}
.sidebar-header h3 { margin: 0; font-size: 16px; color: #89b4fa; }

/* 批量删除控制区 */
.btn-batch-del { background: rgba(243, 139, 168, 0.1); color: #f38ba8; padding: 4px 8px; border-radius: 6px; font-size: 12px; border: none; cursor: pointer; transition: 0.2s;}
.btn-batch-del:hover { background: #f38ba8; color: #11111b; }
.btn-batch-confirm { background: rgba(243, 139, 168, 0.1); color: #f38ba8; padding: 4px 8px; border-radius: 6px; font-size: 12px; border: none; cursor: pointer; transition: 0.2s;}
.btn-batch-confirm:hover { background: #f38ba8; color: #11111b; }
.btn-batch-cancel { background: transparent; color: #a6adc8; padding: 4px 8px; border-radius: 6px; font-size: 12px; border: none; cursor: pointer; transition: 0.2s;}
.btn-batch-cancel:hover { background: #313244; color: #cdd6f4; }
.batch-checkbox { width: 16px; height: 16px; cursor: pointer !important; margin-right: 2px; flex-shrink: 0; accent-color: #f38ba8;}

.selected-date-highlight { font-size: 20px; font-weight: 900; color: #cdd6f4; font-family: monospace; margin-bottom: 15px; word-break: break-all;}

.workflow-actions { display: flex; flex-direction: column; gap: 10px; margin-bottom: 15px; border-bottom: 1px solid #313244; padding-bottom: 15px;}
.add-dropdown { display: flex; gap: 10px; }
.native-select { background: #11111b; border: 1px solid #45475a; color: #cdd6f4; padding: 8px 10px; border-radius: 6px; outline: none; flex: 1; font-size: 13px; font-weight: bold; text-overflow: ellipsis;}
.native-select:focus { border-color: #89b4fa; }
.hook-row { display: flex; gap: 10px;}
.hook-btn { flex: 1; padding: 6px 0; font-size: 12px; border-color: #45475a; cursor: pointer;}
.save-status { font-size: 12px; color: #a6e3a1; font-weight: bold;}

/* 极简卡片列表 */
.compact-list-container { flex: 1; overflow-y: auto; overflow-x: hidden; display: flex; flex-direction: column; gap: 8px; padding-right: 5px; }
.compact-list-container::-webkit-scrollbar { width: 6px; }
.compact-list-container::-webkit-scrollbar-thumb { background: #45475a; border-radius: 3px; }
.empty-hint { color: #6c7086; font-size: 12px; text-align: center; margin-top: 20px;}

/* 🚨 卡片防爆处理 */
.compact-item { position: relative; display: flex; align-items: flex-start; background: #11111b; border: 1px solid #313244; border-left-width: 4px; border-radius: 6px; padding: 8px; gap: 8px; transition: 0.2s; width: 100%; box-sizing: border-box; overflow: hidden;}
.compact-item:hover { border-color: #45475a; background: #181825; }
.compact-item.is-batching { cursor: pointer; }
.compact-item.is-batching:hover { background: rgba(243, 139, 168, 0.05); border-color: #f38ba8; }

.item-tpl-tag { font-size: 11px; padding: 2px 6px; border-radius: 4px; color: #fff; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 80px; margin-top: 2px;}

/* 🚨 悬浮菜单防爆 */
.mention-popover { position: absolute; top: 100%; left: 10px; width: 250px; max-width: 90%; background: #1e1e2e; border: 1px solid #89b4fa; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); overflow: hidden; z-index: 100; margin-top: 4px;}
.mention-header { background: rgba(137, 180, 250, 0.2); padding: 8px 12px; font-size: 11px; font-weight: bold; color: #89b4fa; border-bottom: 1px solid #313244;}
.mention-list { max-height: 180px; overflow-y: auto; overflow-x: hidden; }
.mention-item { padding: 10px 12px; font-size: 12px; color: #cdd6f4; cursor: pointer; transition: 0.1s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.mention-item:hover { background: #313244; color: #89b4fa; font-weight: bold;}

/* 🚨 textarea 终极强制换行 */
.item-sample-textarea { 
  flex: 1; background: transparent; border: none; color: #cdd6f4; font-size: 13px; outline: none; min-width: 0; padding: 2px; resize: none; overflow: hidden; min-height: 20px; line-height: 1.4; font-family: inherit;
  word-break: break-all; /* 核心换行属性 */
  overflow-wrap: break-word;
}
.item-sample-textarea::placeholder { color: #6c7086; font-size: 12px;}

.item-actions { display: flex; gap: 4px; margin-top: 2px; flex-shrink: 0;}
.act-btn { background: transparent; border: none; border-radius: 4px; padding: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 14px; transition: 0.2s;}
.act-btn:hover { background: #313244; transform: scale(1.1);}
.btn-add { color: #a6e3a1; }
.btn-doc { color: #89b4fa; }
.btn-del { color: #f38ba8; font-size: 12px; opacity: 0.6;}
.btn-del:hover { opacity: 1; }

/* 参数录入 Modal */
.param-modal-content { width: 500px; max-width: 90vw; background: #1e1e2e; border: 1px solid #45475a; border-radius: 12px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); display: flex; flex-direction: column;}
.param-form-body { padding: 25px; display: flex; flex-direction: column; gap: 20px;}
.form-hint { color: #bac2de; font-size: 13px; margin: 0;}
.param-grid { display: flex; flex-direction: column; gap: 15px; max-height: 400px; overflow-y: auto; overflow-x: hidden; padding-right: 10px;}
.param-field { display: flex; flex-direction: column; gap: 5px;}
.param-field label { font-size: 12px; color: #89b4fa; font-weight: bold;}
.native-input { background: #11111b; border: 1px solid #45475a; color: #cdd6f4; padding: 10px; border-radius: 6px; outline: none; font-size: 14px; text-overflow: ellipsis;}
.native-input:focus { border-color: #a6e3a1; }
.modal-footer { padding: 15px 25px; background: #11111b; border-top: 1px solid #313244; display: flex; justify-content: flex-end;}

/* 原生模板编辑器 */
.template-modal-body { flex: 1; display: flex; flex-direction: row !important; background: #181825; min-height: 0; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; overflow: hidden;}
.template-modal-content { width: 900px; height: 75vh; min-height: 500px; background: #1e1e2e; border: 1px solid #45475a; border-radius: 12px; display: flex; flex-direction: column; box-shadow: 0 20px 50px rgba(0,0,0,0.5); }

.template-sidebar { width: 220px; background: #11111b; border-right: 1px solid #313244; padding: 15px; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; overflow-x: hidden; flex-shrink: 0;}
.tpl-list-item { padding: 10px; background: #1e1e2e; border: 1px solid #313244; border-radius: 8px; color: #a6adc8; font-size: 13px; cursor: pointer; transition: 0.2s; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.tpl-list-item:hover { border-color: #89b4fa; color: #cdd6f4; }
.tpl-list-item.active { background: rgba(137, 180, 250, 0.1); border-color: #89b4fa; color: #89b4fa; font-weight: bold;}
.add-tpl-btn { border-style: dashed; text-align: center; }

.template-main { flex: 1; display: flex; flex-direction: column; padding: 20px; gap: 10px; min-width: 0; min-height: 0; overflow: hidden;}
.tpl-toolbar-top { display: flex; gap: 10px; align-items: center; flex-shrink: 0;}
.tpl-input-field { background: #11111b; border: 1px solid #45475a; padding: 8px 12px; border-radius: 6px; color: #cdd6f4; font-weight: bold; font-size: 14px; outline: none; text-overflow: ellipsis;}
.tpl-input-field:focus { border-color: #89b4fa; }
.flex-1 { flex: 1; }
.flex-2 { flex: 2; }
.tool-btn { border-color: #f9e2af; color: #f9e2af; padding: 8px 12px; white-space: nowrap; flex-shrink: 0;}
.tool-btn:hover { background: #f9e2af; color: #11111b;}
.btn-delete-tpl { border-color: #f38ba8; color: #f38ba8; padding: 8px 12px; flex-shrink: 0;}
.btn-delete-tpl:hover { background: #f38ba8; color: #11111b; }

.tpl-hint-bar { font-size: 12px; color: #6c7086; background: #11111b; padding: 8px 12px; border-radius: 6px; border: 1px dashed #313244; flex-shrink: 0;}
.tpl-content-input { 
  flex: 1; background: #11111b; border: 1px solid #45475a; padding: 15px; border-radius: 8px; color: #cdd6f4; font-family: monospace; font-size: 14px; outline: none; resize: none; line-height: 1.6; min-height: 0;
  word-break: break-all; overflow-wrap: break-word;
}
.tpl-content-input:focus { border-color: #89b4fa; }

/* 全局模态框 */
.eln-modal-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(17, 17, 27, 0.85); backdrop-filter: blur(5px); display: flex; justify-content: center; align-items: center; z-index: 9999;}
.eln-modal-content { width: 90%; max-width: 1200px; height: 85vh; background: #1e1e2e; border: 1px solid #45475a; border-radius: 12px; display: flex; flex-direction: column; box-shadow: 0 20px 50px rgba(0,0,0,0.5);}
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 25px; background: #11111b; border-bottom: 1px solid #313244; flex-shrink: 0;}
.modal-title { font-size: 18px; font-weight: bold; color: #cdd6f4; }
.tag-date { background: #313244; color: #89b4fa; padding: 4px 8px; border-radius: 6px; font-size: 14px; font-family: monospace;}
.modal-actions { display: flex; gap: 10px; align-items: center;}
.btn-text { background: transparent; border: none; color: #a6adc8; cursor: pointer; font-weight: bold;}
.btn-close { background: transparent; border: none; color: #f38ba8; font-size: 20px; cursor: pointer;}
.modal-body { flex: 1; background: #1e1e2e; display: flex; flex-direction: column; min-height: 0; overflow: hidden;}

.fade-in-scale { animation: fadeInScale 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes fadeInScale { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }

/* EasyMDE 暗黑化覆盖 */
:deep(.EasyMDEContainer) { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
:deep(.EasyMDEContainer .editor-toolbar) { background: #181825; border: none; border-bottom: 1px solid #313244; color: #cdd6f4; flex-shrink: 0;}
:deep(.EasyMDEContainer .editor-toolbar > button) { color: #a6adc8; }
:deep(.EasyMDEContainer .editor-toolbar > button:hover), :deep(.EasyMDEContainer .editor-toolbar > button.active) { background: #313244; color: #89b4fa; border-color: transparent;}
:deep(.EasyMDEContainer .editor-toolbar i.separator) { border-color: #45475a;}
:deep(.EasyMDEContainer .CodeMirror) { flex: 1; background: #1e1e2e; color: #cdd6f4; border: none; font-family: 'Consolas', monospace; font-size: 15px; line-height: 1.6; height: 100% !important; min-height: 0 !important;}
:deep(.EasyMDEContainer .CodeMirror-scroll) { min-height: 0 !important; height: 100% !important; overflow-y: auto !important;}
:deep(.EasyMDEContainer .editor-preview-side), :deep(.EasyMDEContainer .editor-preview) { background-color: #1e1e2e !important; color: #cdd6f4 !important; border-left: 1px solid #45475a !important; padding: 20px;}
:deep(.EasyMDEContainer .editor-statusbar) { background: #11111b; border-top: 1px solid #313244; color: #6c7086; flex-shrink: 0;}
</style>