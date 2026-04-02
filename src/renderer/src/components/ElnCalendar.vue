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
              <button class="btn-toggle" :class="{ 'active': isSplitView }" @click="isSplitView = !isSplitView">
                {{ isSplitView ? '📖 关闭双屏' : '📖 开启双屏渲染' }}
              </button>
              <button class="btn-primary" @click="saveLog">💾 永久落盘保存</button>
            </div>
          </div>

          <div class="editor-body" :class="{ 'is-split': isSplitView }">
            
            <div class="textarea-wrapper">
              <textarea 
                ref="editorTextarea"
                class="markdown-textarea" 
                v-model="currentContent" 
                placeholder="开始编写实验步骤、观察结果或分析数据...\n\n支持 Markdown 语法 (如 # 标题, **加粗**)。\n\n输入 @ 检索物理样本库..."
                @input="handleInput"
                @keydown="handleKeydown"
                @scroll="syncScroll"
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

            <div 
              v-if="isSplitView" 
              class="markdown-preview" 
              ref="previewDiv"
              v-html="compiledMarkdown"
            ></div>

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
import { ref, computed, onMounted, nextTick } from 'vue'

const logs = ref<any[]>([])
const activeLogIndex = ref<number | null>(null)
const isCreatingNew = ref(false)

const currentTitle = ref('')
const currentContent = ref('')

// ================= Markdown 渲染状态 =================
const isSplitView = ref(false) // 是否开启双栏渲染模式
const previewDiv = ref<HTMLElement | null>(null)
const isMarkedLoaded = ref(false)

const compiledMarkdown = computed(() => {
  if (!currentContent.value) return '<div class="empty-hint" style="text-align:center; padding-top: 50px; color:#45475a;">暂无正文内容...</div>'
  if (isMarkedLoaded.value && (window as any).marked) {
    // 开启 Markdown 中的换行支持
    (window as any).marked.setOptions({ breaks: true, gfm: true })
    return (window as any).marked.parse(currentContent.value)
  }
  return '<div style="color: #cdd6f4;">正在加载 Markdown 渲染引擎...</div>'
})

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
    if (json.code === 200) logs.value = json.data
  } catch (e) { console.error("ELN 同步失败", e) }
}

const selectLog = (idx: number) => {
  activeLogIndex.value = idx; isCreatingNew.value = false
  const rawText = logs.value[idx].title || ''; const lines = rawText.split('\n')
  currentTitle.value = extractTitle(rawText)
  currentContent.value = lines.slice(1).join('\n').trim() || rawText
}

const createNewLog = () => { activeLogIndex.value = null; isCreatingNew.value = true; currentTitle.value = ''; currentContent.value = '' }

const saveLog = async () => {
  if (!currentTitle.value.trim() && !currentContent.value.trim()) return alert("请输入实验记录内容！")
  const payload = {
    date: new Date().toISOString().split('T')[0],
    title: currentTitle.value || '无标题实验记录',
    content: currentContent.value
  }
  try {
    const res = await fetch('http://127.0.0.1:8080/api/eln/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if ((await res.json()).code === 200) { await fetchLogs(); selectLog(0); alert("✅ 实验记录已成功永久归档！") }
  } catch (e) { alert("网络请求失败，请检查底层引擎。") }
}

const extractTitle = (text: string) => { if (!text) return '无标题记录'; const firstLine = text.split('\n')[0].trim(); return firstLine.length > 30 ? firstLine.substring(0, 30) + '...' : firstLine }
const extractPreview = (text: string) => { if (!text) return ''; const lines = text.split('\n'); if (lines.length > 1) { const preview = lines[1].trim(); return preview.length > 40 ? preview.substring(0, 40) + '...' : preview } return '无正文预览' }

// ================= 智能联动与渲染逻辑 =================
let searchTimeout: any = null

const handleInput = (e: Event) => {
  const textarea = editorTextarea.value; if (!textarea) return
  const cursorPosition = textarea.selectionStart
  const textBeforeCursor = currentContent.value.substring(0, cursorPosition)
  const match = textBeforeCursor.match(/@([^\s]*)$/)
  
  if (match) {
    mentionQuery.value = match[1]
    mentionStartIndex.value = cursorPosition - match[1].length - 1
    updateMentionPosition()
    showMentionMenu.value = true
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => { executeGlobalSearch(mentionQuery.value) }, 300)
  } else { showMentionMenu.value = false }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!showMentionMenu.value) return
  if (e.key === 'ArrowDown') { e.preventDefault(); mentionSelectedIndex.value = (mentionSelectedIndex.value + 1) % (mentionResults.value.length || 1) } 
  else if (e.key === 'ArrowUp') { e.preventDefault(); mentionSelectedIndex.value = (mentionSelectedIndex.value - 1 + mentionResults.value.length) % (mentionResults.value.length || 1) } 
  else if (e.key === 'Enter') { e.preventDefault(); if (mentionResults.value.length > 0) insertMention(mentionResults.value[mentionSelectedIndex.value]) } 
  else if (e.key === 'Escape') { showMentionMenu.value = false }
}

const updateMentionPosition = () => {
  if (!editorTextarea.value) return
  const textBefore = currentContent.value.substring(0, mentionStartIndex.value)
  const lines = textBefore.split('\n')
  mentionMenuPos.value = { x: 20 + (lines[lines.length - 1].length * 8), y: 40 + (lines.length * 24) - editorTextarea.value.scrollTop }
}

const executeGlobalSearch = async (query: string) => {
  if (!query) { mentionResults.value = []; return }
  isSearching.value = true
  try {
    const json = await (await fetch(`http://127.0.0.1:8080/api/search/omnibar?q=${encodeURIComponent(query)}`)).json()
    if (json.code === 200) { mentionResults.value = json.data; mentionSelectedIndex.value = 0 }
  } catch (e) {} finally { isSearching.value = false }
}

const insertMention = (item: any) => {
  const textarea = editorTextarea.value; if (!textarea) return
  const before = currentContent.value.substring(0, mentionStartIndex.value)
  const after = currentContent.value.substring(textarea.selectionStart)
  // 插入 Markdown 超链接格式，这将在右侧渲染为漂亮的标签
  const mentionText = `[@${item.title}](${item.action_path}) `
  currentContent.value = before + mentionText + after
  showMentionMenu.value = false
  nextTick(() => { textarea.focus(); const newCursorPos = before.length + mentionText.length; textarea.setSelectionRange(newCursorPos, newCursorPos) })
}

// 同步滚动效果：左边代码滚动时，右边预览也跟着滚动
const syncScroll = () => {
  if (isSplitView.value && editorTextarea.value && previewDiv.value) {
    const percentage = editorTextarea.value.scrollTop / (editorTextarea.value.scrollHeight - editorTextarea.value.clientHeight)
    previewDiv.value.scrollTop = percentage * (previewDiv.value.scrollHeight - previewDiv.value.clientHeight)
  }
}

onMounted(() => {
  fetchLogs()
  // 动态挂载 Marked.js 渲染引擎
  if (!(window as any).marked) {
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js'
    script.onload = () => { isMarkedLoaded.value = true }
    document.head.appendChild(script)
  } else {
    isMarkedLoaded.value = true
  }
})
</script>

<style scoped>
/* 基础与宏观布局 */
.eln-calendar-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4;}
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086;}
.breadcrumbs h2.active { color: #cba6f7; font-weight: bold;} 
.btn-primary { background: #cba6f7; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(203, 166, 247, 0.3); }
.btn-outline { background: transparent; color: #cba6f7; border: 1px dashed #cba6f7; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; margin-right: 10px;}
.btn-outline:hover { background: rgba(203, 166, 247, 0.1); }
.btn-toggle { background: #313244; color: #cdd6f4; border: 1px solid #45475a; padding: 10px 15px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; margin-right: 10px;}
.btn-toggle:hover { background: #45475a; }
.btn-toggle.active { background: rgba(203, 166, 247, 0.2); color: #cba6f7; border-color: #cba6f7; }
.btn-small { padding: 6px 12px; font-size: 12px; }

.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}
.card { background: #181825; border: 1px solid #313244; border-radius: 12px;}

/* 侧边时间轴 */
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

/* 编辑器工作区 */
.editor-workspace { flex: 3; display: flex; flex-direction: column; overflow: hidden; background: #11111b;}
.editor-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #bac2de;}
.editor-container { flex: 1; display: flex; flex-direction: column; height: 100%; position: relative;}
.editor-header { padding: 20px 30px; border-bottom: 1px dashed #313244; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;}
.title-input { flex: 1; background: transparent; border: none; font-size: 24px; font-weight: bold; color: #cdd6f4; outline: none;}
.title-input::placeholder { color: #45475a;}
.editor-tools { display: flex; align-items: center; flex-shrink: 0;}

/* 🚨 双栏模式核心布局 */
.editor-body { flex: 1; display: flex; overflow: hidden; position: relative;}
.textarea-wrapper { flex: 1; position: relative; display: flex; flex-direction: column; }
.markdown-textarea { 
  flex: 1; width: 100%; padding: 30px; background: transparent; border: none; 
  color: #bac2de; font-size: 15px; line-height: 1.8; font-family: 'Consolas', 'Courier New', monospace;
  outline: none; resize: none;
}
.markdown-textarea::placeholder { color: #45475a;}

/* 🚨 优美的 Markdown 渲染区样式 */
.is-split .textarea-wrapper { border-right: 1px solid #313244; }
.markdown-preview {
  flex: 1; padding: 30px; overflow-y: auto; color: #cdd6f4; font-size: 15px; line-height: 1.8; background: #181825;
}
/* 渲染 Markdown 各种标签 */
.markdown-preview :deep(h1), .markdown-preview :deep(h2), .markdown-preview :deep(h3) { margin-top: 1.5em; margin-bottom: 0.5em; color: #89b4fa; }
.markdown-preview :deep(h1) { font-size: 24px; border-bottom: 1px dashed #313244; padding-bottom: 10px; }
.markdown-preview :deep(h2) { font-size: 20px; }
.markdown-preview :deep(p) { margin-bottom: 1em; }
.markdown-preview :deep(ul), .markdown-preview :deep(ol) { margin-bottom: 1em; padding-left: 20px; }
.markdown-preview :deep(code) { background: #11111b; padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #f9e2af; border: 1px solid #313244; }
.markdown-preview :deep(blockquote) { border-left: 4px solid #cba6f7; padding-left: 15px; margin: 1em 0; color: #a6adc8; font-style: italic; background: rgba(203, 166, 247, 0.05); padding: 10px 15px; }

/* 🚨 高亮 @关联的物理样本链接 -> 变成科技胶囊 */
.markdown-preview :deep(a) {
  display: inline-block;
  background: rgba(203, 166, 247, 0.2);
  color: #cba6f7;
  padding: 2px 10px;
  border-radius: 12px;
  text-decoration: none;
  font-weight: bold;
  font-size: 13px;
  border: 1px solid rgba(203, 166, 247, 0.5);
  transition: 0.2s;
  margin: 0 2px;
}
.markdown-preview :deep(a:hover) {
  background: rgba(203, 166, 247, 0.4);
  box-shadow: 0 0 10px rgba(203, 166, 247, 0.3);
}

.editor-footer { padding: 15px 30px; border-top: 1px solid #313244; background: #181825; border-radius: 0 0 12px 12px; flex-shrink: 0;}
.attachment-bar { display: flex; justify-content: space-between; align-items: center;}

/* @悬浮菜单 */
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