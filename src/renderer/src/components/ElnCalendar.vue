<template>
  <div class="eln-calendar-view">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 class="active">📓 ELN 实验记录与日程 (智能联动版)</h2>
      </div>
      <div class="header-actions">
        <button class="btn-outline" @click="createNewLog">📝 新建今日实验</button>
        <button class="btn-primary" @click="fetchLogs">🔄 从核心同步数据</button>
      </div>
    </div>

    <div class="split-layout">
      <div class="timeline-sidebar card">
        <div class="sidebar-header">
          <h3>📅 实验时间轴</h3>
          <span class="count-badge">{{ logs.length }} 条记录</span>
        </div>
        
        <div class="empty-state" v-if="logs.length === 0">
          <div class="empty-icon">📭</div>
          <div class="empty-text">暂无实验记录</div>
        </div>

        <div class="timeline-list" v-else>
          <div 
            v-for="(log, idx) in logs" 
            :key="idx" 
            class="timeline-item fade-in"
            :class="{ 'active': activeLogIndex === idx }"
            @click="selectLog(idx)"
          >
            <div class="timeline-date">
              <span class="date-dot"></span>
              {{ log.date }}
            </div>
            <div class="timeline-content">
              <h4 class="log-title">{{ extractTitle(log.title) }}</h4>
              <p class="log-preview">{{ extractPreview(log.title) }}</p>
              <div class="log-meta">
                <span class="tag" :class="log.status === '进行中' ? 'warning' : 'success'">{{ log.status || '已归档' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="editor-workspace card">
        <div v-if="activeLogIndex === null && !isCreatingNew" class="editor-empty">
          <div class="empty-icon" style="font-size: 64px; margin-bottom: 20px;">✍️</div>
          <h2>请在左侧选择一条实验记录，或新建实验</h2>
          <p style="color: #6c7086;">支持 Markdown 语法与 @ 样本智能关联</p>
        </div>

        <div v-else class="editor-container fade-in">
          <div class="editor-header">
            <input 
              type="text" 
              class="title-input" 
              v-model="currentTitle" 
              placeholder="无标题实验记录..."
            />
            <div class="editor-tools">
              <span style="font-size: 12px; color: #a6adc8; margin-right: 15px;">
                💡 提示: 在正文中输入 <b>@</b> 可直接检索并绑定物理样本
              </span>
              <button class="btn-primary" @click="saveLog">💾 永久落盘保存</button>
            </div>
          </div>

          <div class="editor-body">
            <textarea 
              ref="editorTextarea"
              class="markdown-textarea" 
              v-model="currentContent" 
              placeholder="开始编写实验步骤、观察结果或分析数据...\n\n支持 Markdown 语法。输入 @ 检索物理样本库..."
              @input="handleInput"
              @keydown="handleKeydown"
            ></textarea>

            <div 
              v-if="showMentionMenu" 
              class="mention-menu card fade-in"
              :style="{ top: mentionMenuPos.y + 'px', left: mentionMenuPos.x + 'px' }"
            >
              <div class="menu-header">🔍 检索物理样本: "{{ mentionQuery }}"</div>
              <div class="menu-list" v-if="mentionResults.length > 0">
                <div 
                  v-for="(res, idx) in mentionResults" 
                  :key="idx"
                  class="menu-item"
                  :class="{ 'selected': mentionSelectedIndex === idx }"
                  @click="insertMention(res)"
                  @mouseover="mentionSelectedIndex = idx"
                >
                  <span class="item-icon">{{ res.icon }}</span>
                  <div class="item-info">
                    <div class="item-title">{{ res.title }}</div>
                    <div class="item-desc">{{ res.desc }}</div>
                  </div>
                </div>
              </div>
              <div class="menu-empty" v-else>
                <span v-if="isSearching">正在跨维度搜索宇宙...</span>
                <span v-else>未找到名为 "{{ mentionQuery }}" 的样本</span>
              </div>
            </div>
          </div>
          
          <div class="editor-footer">
            <div class="attachment-bar">
              <span style="color: #6c7086; font-weight: bold; font-size: 12px;">📎 关联数据与图谱 (DataHub)</span>
              <button class="btn-outline btn-small">+ 挂载凝胶图/序列文件</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'

// ================= 基础状态 =================
const logs = ref<any[]>([])
const activeLogIndex = ref<number | null>(null)
const isCreatingNew = ref(false)

const currentTitle = ref('')
const currentContent = ref('')

// ================= @ 提及智能引擎状态 =================
const editorTextarea = ref<HTMLTextAreaElement | null>(null)
const showMentionMenu = ref(false)
const mentionQuery = ref('')
const mentionResults = ref<any[]>([])
const mentionMenuPos = ref({ x: 0, y: 0 })
const mentionSelectedIndex = ref(0)
const isSearching = ref(false)
const mentionStartIndex = ref(-1)

// ================= API 与数据获取 =================
const fetchLogs = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/eln/recent')
    const json = await res.json()
    if (json.code === 200) {
      logs.value = json.data
    }
  } catch (e) {
    console.error("ELN 同步失败", e)
  }
}

// ================= 列表与落盘交互 =================
const selectLog = (idx: number) => {
  activeLogIndex.value = idx
  isCreatingNew.value = false
  const rawText = logs.value[idx].title || ''
  const lines = rawText.split('\n')
  currentTitle.value = extractTitle(rawText)
  currentContent.value = lines.slice(1).join('\n').trim() || rawText
}

const createNewLog = () => {
  activeLogIndex.value = null
  isCreatingNew.value = true
  currentTitle.value = ''
  currentContent.value = ''
}

// 🚨 真正的持久化落盘逻辑
const saveLog = async () => {
  if (!currentTitle.value.trim() && !currentContent.value.trim()) {
    alert("请输入实验记录内容！")
    return
  }

  const payload = {
    date: new Date().toISOString().split('T')[0], // 默认存入今日
    title: currentTitle.value || '无标题实验记录',
    content: currentContent.value
  }

  try {
    const res = await fetch('http://127.0.0.1:8080/api/eln/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const json = await res.json()
    if (json.code === 200) {
      // 保存成功后刷新左侧列表，并定位到第一条
      await fetchLogs()
      selectLog(0) 
      alert("✅ 实验记录已成功永久归档！")
    } else {
      alert("❌ 保存失败：" + json.message)
    }
  } catch (e) {
    console.error("保存失败", e)
    alert("网络请求失败，请检查底层引擎是否在线。")
  }
}

// 辅助函数
const extractTitle = (text: string) => {
  if (!text) return '无标题记录'
  const firstLine = text.split('\n')[0].trim()
  return firstLine.length > 30 ? firstLine.substring(0, 30) + '...' : firstLine
}
const extractPreview = (text: string) => {
  if (!text) return ''
  const lines = text.split('\n')
  if (lines.length > 1) {
    const preview = lines[1].trim()
    return preview.length > 40 ? preview.substring(0, 40) + '...' : preview
  }
  return '无正文预览'
}

// ================= @ 智能唤醒引擎 =================
let searchTimeout: any = null

const handleInput = (e: Event) => {
  const textarea = editorTextarea.value
  if (!textarea) return
  
  const cursorPosition = textarea.selectionStart
  const textBeforeCursor = currentContent.value.substring(0, cursorPosition)
  const match = textBeforeCursor.match(/@([^\s]*)$/)
  
  if (match) {
    mentionQuery.value = match[1]
    mentionStartIndex.value = cursorPosition - match[1].length - 1
    updateMentionPosition()
    showMentionMenu.value = true
    
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
      executeGlobalSearch(mentionQuery.value)
    }, 300)
  } else {
    showMentionMenu.value = false
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!showMentionMenu.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault(); mentionSelectedIndex.value = (mentionSelectedIndex.value + 1) % mentionResults.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault(); mentionSelectedIndex.value = (mentionSelectedIndex.value - 1 + mentionResults.value.length) % mentionResults.value.length
  } else if (e.key === 'Enter') {
    e.preventDefault(); if (mentionResults.value.length > 0) insertMention(mentionResults.value[mentionSelectedIndex.value])
  } else if (e.key === 'Escape') {
    showMentionMenu.value = false
  }
}

const updateMentionPosition = () => {
  if (!editorTextarea.value) return
  const textBefore = currentContent.value.substring(0, mentionStartIndex.value)
  const lines = textBefore.split('\n')
  const currentLineIndex = lines.length
  const lineHeight = 24 
  mentionMenuPos.value = {
    x: 20 + (lines[lines.length - 1].length * 8), 
    y: 80 + (currentLineIndex * lineHeight)       
  }
}

const executeGlobalSearch = async (query: string) => {
  if (!query) { mentionResults.value = []; return }
  isSearching.value = true
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/search/omnibar?q=${encodeURIComponent(query)}`)
    const json = await res.json()
    if (json.code === 200) { mentionResults.value = json.data; mentionSelectedIndex.value = 0 }
  } catch (e) { console.error("跨域检索失败", e) } finally { isSearching.value = false }
}

const insertMention = (item: any) => {
  const textarea = editorTextarea.value
  if (!textarea) return
  const before = currentContent.value.substring(0, mentionStartIndex.value)
  const after = currentContent.value.substring(textarea.selectionStart)
  const mentionText = `[@${item.title}](${item.action_path}) `
  currentContent.value = before + mentionText + after
  showMentionMenu.value = false
  nextTick(() => {
    textarea.focus()
    const newCursorPos = before.length + mentionText.length
    textarea.setSelectionRange(newCursorPos, newCursorPos)
  })
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.eln-calendar-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4;}
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086;}
.breadcrumbs h2.active { color: #cba6f7; font-weight: bold;} 
.btn-primary { background: #cba6f7; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(203, 166, 247, 0.3); }
.btn-outline { background: transparent; color: #cba6f7; border: 1px dashed #cba6f7; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; margin-right: 10px;}
.btn-outline:hover { background: rgba(203, 166, 247, 0.1); }
.btn-small { padding: 6px 12px; font-size: 12px; }

.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}
.card { background: #181825; border: 1px solid #313244; border-radius: 12px;}

.timeline-sidebar { flex: 1; max-width: 320px; display: flex; flex-direction: column; overflow: hidden; }
.sidebar-header { padding: 20px; border-bottom: 1px solid #313244; display: flex; justify-content: space-between; align-items: center; background: #11111b; border-radius: 12px 12px 0 0;}
.sidebar-header h3 { margin: 0; color: #cdd6f4; font-size: 16px;}
.count-badge { background: #313244; color: #bac2de; padding: 2px 8px; border-radius: 12px; font-size: 12px;}
.timeline-list { flex: 1; overflow-y: auto; padding: 15px;}
.timeline-item { padding: 15px; border-left: 2px solid #313244; position: relative; cursor: pointer; transition: 0.2s; margin-left: 10px; margin-bottom: 15px;}
.timeline-item:hover { background: #1e1e2e; border-radius: 0 8px 8px 0;}
.timeline-item.active { background: rgba(203, 166, 247, 0.1); border-left-color: #cba6f7; border-radius: 0 8px 8px 0;}
.timeline-date { font-size: 12px; color: #a6adc8; margin-bottom: 8px; position: relative;}
.date-dot { position: absolute; width: 10px; height: 10px; background: #181825; border: 2px solid #6c7086; border-radius: 50%; left: -21px; top: 2px; transition: 0.2s;}
.timeline-item.active .date-dot { border-color: #cba6f7; background: #cba6f7; box-shadow: 0 0 8px rgba(203, 166, 247, 0.5);}
.log-title { margin: 0 0 5px 0; font-size: 14px; color: #cdd6f4; font-weight: bold;}
.timeline-item.active .log-title { color: #cba6f7;}
.log-preview { margin: 0 0 10px 0; font-size: 12px; color: #6c7086; line-height: 1.4;}
.log-meta .tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: #313244; color: #bac2de;}
.log-meta .tag.warning { background: rgba(249, 226, 175, 0.15); color: #f9e2af;}
.log-meta .tag.success { background: rgba(166, 227, 161, 0.15); color: #a6e3a1;}

.editor-workspace { flex: 3; display: flex; flex-direction: column; overflow: hidden; background: #11111b;}
.editor-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #bac2de;}
.editor-container { flex: 1; display: flex; flex-direction: column; height: 100%; position: relative;}
.editor-header { padding: 20px 30px; border-bottom: 1px dashed #313244; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;}
.title-input { flex: 1; background: transparent; border: none; font-size: 24px; font-weight: bold; color: #cdd6f4; outline: none;}
.title-input::placeholder { color: #45475a;}
.editor-tools { display: flex; align-items: center; flex-shrink: 0;}
.editor-body { flex: 1; position: relative; display: flex;}
.markdown-textarea { flex: 1; width: 100%; padding: 30px; background: transparent; border: none; color: #bac2de; font-size: 15px; line-height: 1.8; font-family: 'Consolas', 'Courier New', monospace; outline: none; resize: none;}
.markdown-textarea::placeholder { color: #45475a;}
.editor-footer { padding: 15px 30px; border-top: 1px solid #313244; background: #181825; border-radius: 0 0 12px 12px; flex-shrink: 0;}
.attachment-bar { display: flex; justify-content: space-between; align-items: center;}

.mention-menu { position: absolute; width: 350px; background: #1e1e2e; border: 1px solid #cba6f7; box-shadow: 0 10px 30px rgba(0,0,0,0.5); z-index: 100; overflow: hidden;}
.menu-header { padding: 10px 15px; background: #11111b; color: #cba6f7; font-size: 12px; font-weight: bold; border-bottom: 1px solid #313244;}
.menu-list { max-height: 300px; overflow-y: auto;}
.menu-item { display: flex; align-items: center; padding: 10px 15px; cursor: pointer; border-bottom: 1px dashed #313244; transition: 0.1s;}
.menu-item:last-child { border-bottom: none;}
.menu-item.selected { background: rgba(203, 166, 247, 0.15);}
.item-icon { font-size: 24px; margin-right: 15px; background: #11111b; padding: 8px; border-radius: 8px;}
.item-title { font-weight: bold; color: #cdd6f4; font-size: 14px; margin-bottom: 4px;}
.item-desc { font-size: 11px; color: #a6adc8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.menu-empty { padding: 20px; text-align: center; color: #6c7086; font-size: 13px;}

.empty-state { text-align: center; padding: 60px 20px;}
.empty-icon { font-size: 48px; margin-bottom: 15px; opacity: 0.5;}
.empty-text { color: #6c7086; font-size: 14px; font-weight: bold;}
.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>