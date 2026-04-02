<template>
  <div class="app-container" :class="{ 'app-container__plugin': currentView === ViewMode.Plugin }">
    
    <div v-if="showSpotlight" class="spotlight-overlay" @click.self="showSpotlight = false">
      <div class="spotlight-modal fade-in-scale">
        <div class="spotlight-input-wrapper">
          <span class="spotlight-icon" :class="{ 'spin-loader': isSpotlightSearching }">
            {{ isSpotlightSearching ? '⚙️' : '🔍' }}
          </span>
          <input 
            ref="spotlightInputRef"
            type="text" 
            class="spotlight-input" 
            placeholder="搜索全宇宙... (支持物理样本、DataHub文件)"
            v-model="spotlightQuery"
            @input="handleSpotlightInput"
            @keydown="handleSpotlightKeydown"
          />
          <span class="esc-hint">Esc 取消</span>
        </div>

        <div class="spotlight-results" v-if="spotlightResults.length > 0">
          <div 
            v-for="(item, idx) in spotlightResults" 
            :key="idx" 
            class="spotlight-item"
            :class="{ 'active': spotlightIndex === idx }"
            @click="selectSpotlightItem(item)"
            @mouseover="spotlightIndex = idx"
          >
            <div class="spotlight-item-icon">{{ item.icon }}</div>
            <div class="spotlight-item-info">
              <div class="spotlight-item-title">{{ item.title }}</div>
              <div class="spotlight-item-desc"><span class="module-tag">{{ item.module }}</span> {{ item.desc }}</div>
            </div>
            <div class="spotlight-item-action">↵ 穿梭</div>
          </div>
        </div>

        <div class="spotlight-empty" v-else-if="spotlightQuery && !isSpotlightSearching">
          未在系统中找到名为 "{{ spotlightQuery }}" 的资产。
        </div>

        <div class="spotlight-footer" v-if="spotlightResults.length > 0">
          <span><span class="key-hint">↑</span> <span class="key-hint">↓</span> 导航</span>
          <span><span class="key-hint">Enter</span> 确认穿梭</span>
        </div>
      </div>
    </div>
    <div v-if="isDashboardMode" class="mtools-dashboard fade-in">
      <aside class="sidebar" :class="{ 'collapsed': isSidebarCollapsed }">
        <div class="logo" @click="toggleSidebar" title="点击展开/收缩侧边栏">
          <span class="icon">🧬</span>
          <span class="text">Mtools</span> 
        </div>
        
        <nav class="nav-menu">
          <div class="nav-item" :class="{ active: currentDashboardTab === 'dashboard' }" @click="currentDashboardTab = 'dashboard'">
            <span class="icon">📊</span>
            <span class="text" v-show="!isSidebarCollapsed">全局大盘</span>
          </div>
          <div class="nav-item" :class="{ active: currentDashboardTab === 'eln' }" @click="currentDashboardTab = 'eln'">
            <span class="icon">📓</span>
            <span class="text" v-show="!isSidebarCollapsed">实验日历 (ELN)</span>
          </div>
          <div class="nav-item" :class="{ active: currentDashboardTab === 'sample' }" @click="currentDashboardTab = 'sample'">
            <span class="icon">🧪</span>
            <span class="text" v-show="!isSidebarCollapsed">样本中心</span>
          </div>
          <div class="nav-item" :class="{ active: currentDashboardTab === 'datahub' }" @click="currentDashboardTab = 'datahub'">
            <span class="icon">🗄️</span>
            <span class="text" v-show="!isSidebarCollapsed">数据中心</span>
          </div>
          <div class="nav-item" :class="{ active: currentDashboardTab === 'plugins' }" @click="currentDashboardTab = 'plugins'">
            <span class="icon">🧬</span>
            <span class="text" v-show="!isSidebarCollapsed">算力引擎</span>
          </div>
        </nav>
        
        <div class="bottom-tools">
          <div class="nav-item" @click="toggleSpotlight(true)" title="Cmd+K / Ctrl+K">
            <span class="icon">🔍</span>
            <span class="text" v-show="!isSidebarCollapsed">全局检索 (⌘+K)</span>
          </div>
          <div class="nav-item" :class="{ 'pinned-active': isPinned }" @click="togglePin">
            <span class="icon">{{ isPinned ? '📌' : '📍' }}</span>
            <span class="text" v-show="!isSidebarCollapsed">{{ isPinned ? '已固定 (常驻)' : '点击固定窗口' }}</span>
          </div>
          <div class="nav-item" @click="toggleDashboard(false)">
            <span class="icon">🚪</span>
            <span class="text" v-show="!isSidebarCollapsed">返回极速框 (Esc)</span>
          </div>
        </div>
      </aside>
      
      <main class="workspace">
        <GlobalDashboard 
          v-if="currentDashboardTab === 'dashboard'" 
          class="workspace-full fade-in"
          @navigate="currentDashboardTab = $event" 
        />

        <ElnCalendar v-if="currentDashboardTab === 'eln'" class="workspace-full fade-in" />
        <SampleHub v-if="currentDashboardTab === 'sample'" class="workspace-full fade-in" />
        <DataHub v-if="currentDashboardTab === 'datahub'" class="workspace-full fade-in" />
        <BioPlugins v-if="currentDashboardTab === 'plugins'" class="workspace-full fade-in" />
      </main>
    </div>

    <div v-show="!isDashboardMode" class="search-window">
      <div :class="['search-box-wrapper', { 'with-divider': currentView === ViewMode.Plugin }]">
        <SearchBox
          ref="searchBoxRef"
          v-model:pasted-image="pastedImageData"
          v-model:pasted-files="pastedFilesData"
          v-model:pasted-text="pastedTextData"
          :model-value="searchQuery"
          :current-view="currentView"
          @update:model-value="handleSearchQueryChange"
          @composing="handleComposing"
          @arrow-keydown="handleArrowKeydown"
          @close-plugin="handleClosePlugin"
        />
        
        <div class="mtools-entry-btn" @click="toggleDashboard(true)" title="展开 Mtools 工作站">
          🧬 实验室
        </div>
      </div>

      <SearchResults
        v-if="currentView === ViewMode.Search"
        ref="searchResultsRef"
        :search-query="searchQuery"
        :pasted-image="pastedImageData"
        :pasted-files="pastedFilesData"
        :pasted-text="pastedTextData"
        @height-changed="updateWindowHeight"
        @focus-input="handleFocusInput"
        @restore-match="handleRestoreMatch"
      />

      <div v-if="currentView === ViewMode.Plugin" class="plugin-placeholder"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import SearchBox from './components/search/SearchBox.vue'
import SearchResults from './components/search/SearchResults.vue'
import { useCommandDataStore } from './stores/commandDataStore'
import { useWindowStore } from './stores/windowStore'

// 引入模块
import ElnCalendar from './components/ElnCalendar.vue'
import SampleHub from './components/SampleHub.vue'
import DataHub from './components/DataHub.vue'
import BioPlugins from './components/BioPlugins.vue'
import GlobalDashboard from './components/GlobalDashboard.vue'

interface FileItem {
  path: string
  name: string
  isDirectory: boolean
}

enum ViewMode {
  Search = 'search',
  Plugin = 'plugin'
}

const windowStore = useWindowStore()
const commandDataStore = useCommandDataStore()

const searchQuery = ref('')
const isComposing = ref(false)
const currentView = ref<ViewMode>(ViewMode.Search)
const searchBoxRef = ref<{ focus: () => void; selectAll: () => void } | null>(null)
const searchResultsRef = ref<{
  handleKeydown: (e: KeyboardEvent) => void
  resetSelection: () => void
  resetCollapseState: () => void
} | null>(null)
const pastedImageData = ref<string | null>(null)
const pastedFilesData = ref<FileItem[] | null>(null)
const pastedTextData = ref<string | null>(null)

// Mtools 工作站模式开关与侧边栏状态
const isDashboardMode = ref(false)
const currentDashboardTab = ref('dashboard')
const isSidebarCollapsed = ref(false)
const isPinned = ref(false)

function toggleSidebar() { isSidebarCollapsed.value = !isSidebarCollapsed.value }
function togglePin() {
  isPinned.value = !isPinned.value
  window.ztools.setWindowPinned(isPinned.value) 
}

function toggleDashboard(show: boolean) {
  isDashboardMode.value = show
  if (show) {
    nextTick(() => { window.ztools.resizeWindow(800) })
  } else {
    if (isPinned.value) togglePin()
    updateWindowHeight()
    nextTick(() => { searchBoxRef.value?.focus() })
  }
}

// ==============================================================
// 🚨 Spotlight 级全局搜索逻辑
// ==============================================================
const showSpotlight = ref(false)
const spotlightQuery = ref('')
const spotlightResults = ref<any[]>([])
const spotlightIndex = ref(0)
const isSpotlightSearching = ref(false)
let spotlightTimeout: any = null
const spotlightInputRef = ref<HTMLInputElement | null>(null)

const toggleSpotlight = (forceShow?: boolean) => {
  showSpotlight.value = forceShow !== undefined ? forceShow : !showSpotlight.value
  if (showSpotlight.value) {
    spotlightQuery.value = ''
    spotlightResults.value = []
    nextTick(() => spotlightInputRef.value?.focus())
  }
}

const fetchSpotlightResults = async (query: string) => {
  if (!query.trim()) { spotlightResults.value = []; return }
  isSpotlightSearching.value = true
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/search/omnibar?q=${encodeURIComponent(query)}`)
    const json = await res.json()
    if (json.code === 200) {
      spotlightResults.value = json.data
      spotlightIndex.value = 0
    }
  } catch (e) {
    console.error("Spotlight 检索失败", e)
  } finally {
    isSpotlightSearching.value = false
  }
}

const handleSpotlightInput = () => {
  clearTimeout(spotlightTimeout)
  spotlightTimeout = setTimeout(() => { fetchSpotlightResults(spotlightQuery.value) }, 300)
}

const handleSpotlightKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    spotlightIndex.value = (spotlightIndex.value + 1) % (spotlightResults.value.length || 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    spotlightIndex.value = (spotlightIndex.value - 1 + spotlightResults.value.length) % (spotlightResults.value.length || 1)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (spotlightResults.value.length > 0) {
      selectSpotlightItem(spotlightResults.value[spotlightIndex.value])
    }
  } else if (e.key === 'Escape') {
    e.preventDefault()
    e.stopPropagation() // 🚨 核心修复：阻止事件继续向上冒泡给全局 Window！
    showSpotlight.value = false
  }
}

const selectSpotlightItem = (item: any) => {
  showSpotlight.value = false
  // 确保母舰展开
  if (!isDashboardMode.value) toggleDashboard(true)
  
  // 智能路由到对应模块
  if (item.module === 'SampleHub') {
    currentDashboardTab.value = 'sample'
  } else if (item.module === 'DataHub') {
    currentDashboardTab.value = 'datahub'
  } else if (item.module === 'ELN') {
    currentDashboardTab.value = 'eln'
  }
  
  // 发送全局总线事件，子组件内部如果需要解析路径可以监听此事件（例如直接跳到某个盒子）
  window.dispatchEvent(new CustomEvent('spotlight-nav-event', { detail: item }))
}
// ==============================================================


function handleSearchQueryChange(value: string): void {
  searchQuery.value = value
  if (currentView.value === ViewMode.Plugin && windowStore.currentPlugin) {
    window.ztools.notifySubInputChange(value)
  }
}

watch(pastedImageData, (newValue) => { if (newValue) { pastedFilesData.value = null; pastedTextData.value = null } })
watch(pastedFilesData, (newValue) => { if (newValue) { pastedImageData.value = null; pastedTextData.value = null } })
watch(pastedTextData, (newValue) => { if (newValue) { pastedImageData.value = null; pastedFilesData.value = null } })

function updateWindowHeight(): Promise<void> {
  return nextTick(() => {
    const container = document.querySelector('.app-container')
    if (container) { window.ztools.resizeWindow(container.scrollHeight + 1) }
  })
}

function handleFocusInput(): void { searchBoxRef.value?.focus() }

function handleRestoreMatch(state: any): void {
  searchQuery.value = state.searchQuery || ''
  pastedImageData.value = state.pastedImage || null
  pastedFilesData.value = state.pastedFiles || null
  pastedTextData.value = state.pastedText || null
  nextTick(() => { searchBoxRef.value?.focus() })
}

function handleComposing(composing: boolean): void { isComposing.value = composing }

function handleClosePlugin(): void {
  exitPluginToSearch()
  nextTick(() => { searchBoxRef.value?.focus() })
}

function exitPluginToSearch(): void {
  currentView.value = ViewMode.Search
  searchQuery.value = ''
  window.ztools.hidePlugin()
}

function handlePluginStepExit(): void {
  if (searchQuery.value.trim()) { searchQuery.value = ''; window.ztools.notifySubInputChange(''); return }
  if (pastedImageData.value || pastedFilesData.value || pastedTextData.value) { pastedImageData.value = null; pastedFilesData.value = null; pastedTextData.value = null; return }
  exitPluginToSearch()
}

function convertToElectronKeyboardEvent(direction: 'left' | 'right' | 'up' | 'down' | 'enter', type: 'keyDown' | 'keyUp' = 'keyDown'): { type: 'keyDown' | 'keyUp'; keyCode: string } {
  const keyCodeMap: Record<string, string> = { left: 'Left', right: 'Right', up: 'Up', down: 'Down', enter: 'Return' }
  return { type, keyCode: keyCodeMap[direction] }
}

async function handleArrowKeydown(event: KeyboardEvent, direction: 'left' | 'right' | 'up' | 'down' | 'enter'): Promise<void> {
  if (currentView.value !== ViewMode.Plugin || !windowStore.currentPlugin) return
  if (direction === 'up' || direction === 'down') { event.preventDefault(); event.stopPropagation() }
  const keyDownEvent = convertToElectronKeyboardEvent(direction, 'keyDown')
  const keyUpEvent = convertToElectronKeyboardEvent(direction, 'keyUp')
  try {
    await window.ztools.sendInputEvent(keyDownEvent)
    await new Promise((resolve) => setTimeout(resolve, 10))
    await window.ztools.sendInputEvent(keyUpEvent)
  } catch (error) { console.error('发送方向键事件失败:', error) }
}

function launchTabTarget(target: string, text: string): void {
  const commands = [...commandDataStore.regexCommands, ...commandDataStore.commands]
  let matchedCommand: (typeof commands)[number] | null = null
  const parts = target.split('/')
  if (parts.length === 2) {
    const [pluginDesc, cmdName] = parts
    matchedCommand = commands.find(c => c.type === 'plugin' && (c.pluginName === pluginDesc || c.pluginTitle === pluginDesc) && c.name === cmdName) || null
  } else {
    matchedCommand = commands.find(c => c.name === target) || null
  }

  if (!matchedCommand) {
    new Notification('MTools', { body: `未找到 Tab 键目标指令「${target}」` })
    return
  }

  window.ztools.launch({
    path: matchedCommand.path, type: matchedCommand.type as 'plugin' | 'direct', featureCode: matchedCommand.featureCode,
    name: matchedCommand.name, cmdType: matchedCommand.cmdType || 'text',
    param: { payload: text, type: matchedCommand.cmdType || 'text' }
  })
}

async function detachCurrentPlugin(): Promise<void> {
  try { await window.ztools.detachPlugin() } catch (error: any) { console.error('分离插件失败:', error) }
}

function applyAcrylicOverlay(): void {
  const existingStyle = document.getElementById('acrylic-overlay-style')
  if (existingStyle) existingStyle.remove()
  const material = document.documentElement.getAttribute('data-material')
  if (material === 'acrylic') {
    const style = document.createElement('style')
    style.id = 'acrylic-overlay-style'
    style.textContent = `body::after { content: ""; position: fixed; inset: 0; pointer-events: none; z-index: -1; } @media (prefers-color-scheme: light) { body::after { background: rgb(255 255 255 / ${windowStore.acrylicLightOpacity}%); } } @media (prefers-color-scheme: dark) { body::after { background: rgb(0 0 0 / ${windowStore.acrylicDarkOpacity}%); } }`
    document.head.appendChild(style)
  }
}

watch(currentView, (newView) => { if (newView !== ViewMode.Plugin) updateWindowHeight() })

// 🚨 核心全局键盘监听
async function handleKeydown(event: KeyboardEvent): Promise<void> {
  if (isComposing.value) return

  // 🚨 Spotlight 唤醒拦截 (Cmd+K 或 Ctrl+K)
  if ((event.key === 'k' || event.key === 'K') && (event.metaKey || event.ctrlKey)) {
    event.preventDefault()
    toggleSpotlight(true)
    return
  }

  // 🚨 如果 Spotlight 正在显示，除了上面的 K 键，屏蔽其他主框架快捷键干扰
  if (showSpotlight.value) {
    if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation() // 🚨 核心修复：双重保险，阻止冒泡
      showSpotlight.value = false
    }
    return // 退出继续执行，把焦点锁死在 Spotlight 内部
  }

  if ((event.key === 'd' || event.key === 'D') && (event.metaKey || event.ctrlKey)) {
    event.preventDefault(); if (currentView.value === ViewMode.Plugin && windowStore.currentPlugin) detachCurrentPlugin(); return
  }

  if ((event.key === 'q' || event.key === 'Q') && (event.metaKey || event.ctrlKey)) {
    const settings = (await window.ztools.dbGet('settings-general')) || {}
    if (settings?.builtinAppShortcutsEnabled?.killPlugin === false) return
    event.preventDefault()
    if (currentView.value === ViewMode.Plugin && windowStore.currentPlugin) {
      try { await window.ztools.killPluginAndReturn(windowStore.currentPlugin.path) } catch (error: any) {}
    } else { window.ztools.hideWindow() }
    return
  }

  if (event.key === 'Tab') {
    const target = windowStore.tabTargetCommand
    if (target && currentView.value === ViewMode.Search) {
      event.preventDefault(); launchTabTarget(target, searchQuery.value); return
    }
  }

  const isPlainBackspace = event.key === 'Backspace' && !event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey
  const isSearchInputTarget = event.target instanceof HTMLInputElement && event.target.classList.contains('search-input')

  if (isPlainBackspace && currentView.value === ViewMode.Plugin && windowStore.subInputVisible && isSearchInputTarget && !searchQuery.value.trim()) {
    if (event.defaultPrevented) return
    event.preventDefault(); handlePluginStepExit(); return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    if (isDashboardMode.value) { toggleDashboard(false); return }
    if (currentView.value === ViewMode.Plugin) { handlePluginStepExit(); return }
    if (searchQuery.value.trim()) { searchQuery.value = '' } 
    else if (pastedImageData.value || pastedFilesData.value || pastedTextData.value) { pastedImageData.value = null; pastedFilesData.value = null; pastedTextData.value = null } 
    else { window.ztools.hideWindow() }
    return
  }

  if (currentView.value !== ViewMode.Search) return
  searchResultsRef.value?.handleKeydown(event)
}

onMounted(async () => {
  // 🚨 允许子组件抛出全局事件唤醒 Spotlight
  window.addEventListener('open-spotlight', () => toggleSpotlight(true))

  await Promise.all([windowStore.loadSettings(), commandDataStore.initializeData()])
  updateWindowHeight()

  window.ztools.onFocusSearch(async (windowInfo) => {
    if (windowInfo) windowStore.updateWindowInfo(windowInfo)
    if (currentView.value === ViewMode.Plugin) return
    const shouldClear = windowStore.shouldClearSearch()
    if (shouldClear) {
      searchQuery.value = ''; pastedImageData.value = null; pastedFilesData.value = null; pastedTextData.value = null
    }
    searchResultsRef.value?.resetSelection()
    searchResultsRef.value?.resetCollapseState()
    nextTick(() => {
      searchBoxRef.value?.focus()
      if (!shouldClear && searchQuery.value) searchBoxRef.value?.selectAll()
    })
    const timeLimit = windowStore.getAutoPasteTimeLimit()
    if (timeLimit > 0) {
      try {
        const copiedContent = await window.ztools.getLastCopiedContent(timeLimit)
        if (copiedContent) {
          if (copiedContent.type === 'image') pastedImageData.value = copiedContent.data as string
          else if (copiedContent.type === 'text') pastedTextData.value = copiedContent.data as string
          else if (copiedContent.type === 'file') pastedFilesData.value = copiedContent.data as FileItem[]
        }
      } catch (error) {}
    }
    updateWindowHeight()
  })

  window.ztools.onBackToSearch(() => { currentView.value = ViewMode.Search; searchQuery.value = ''; windowStore.updateCurrentPlugin(null); windowStore.setPluginLoading(false); nextTick(() => { updateWindowHeight(); searchBoxRef.value?.focus() }) })
  window.ztools.onPluginOpened((plugin) => { windowStore.updateCurrentPlugin(plugin); pastedImageData.value = null; pastedFilesData.value = null; pastedTextData.value = null })
  window.ztools.onPluginLoaded((plugin) => { windowStore.setPluginLoading(false) })
  window.ztools.onPluginClosed(() => { windowStore.updateCurrentPlugin(null); windowStore.setPluginLoading(false) })
  window.ztools.onUpdateSubInputPlaceholder?.((data: { pluginPath: string; placeholder: string }) => { windowStore.updateSubInputPlaceholder(data.placeholder) })
  window.ztools.onUpdateSubInputVisible?.((visible: boolean) => { windowStore.updateSubInputVisible(visible) })
  window.ztools.onSetSubInputValue((text: string) => { searchQuery.value = text })
  window.ztools.onFocusSubInput(() => { nextTick(() => { searchBoxRef.value?.focus() }) })
  window.ztools.onSelectSubInput(() => { nextTick(() => { searchBoxRef.value?.focus(); searchBoxRef.value?.selectAll() }) })
  window.ztools.onSetSearchText((text: string) => { searchQuery.value = text; nextTick(() => { searchBoxRef.value?.focus() }) })
  window.ztools.onShowPluginPlaceholder(() => { currentView.value = ViewMode.Plugin; searchQuery.value = ''; pastedImageData.value = null; pastedFilesData.value = null; pastedTextData.value = null })
  window.ztools.onUpdatePlaceholder((placeholder: string) => { windowStore.updatePlaceholder(placeholder) })
  window.ztools.onUpdateAvatar((avatar: string) => { windowStore.updateAvatar(avatar) })
  window.ztools.onUpdateAutoPaste((autoPaste: string) => { windowStore.updateAutoPaste(autoPaste as any) })
  window.ztools.onUpdateAutoClear((autoClear: string) => { windowStore.updateAutoClear(autoClear as any) })
  window.ztools.onUpdateShowRecentInSearch((showRecentInSearch: boolean) => { windowStore.updateShowRecentInSearch(showRecentInSearch) })
  window.ztools.onUpdateMatchRecommendation((showMatchRecommendation: boolean) => { windowStore.updateShowMatchRecommendation(showMatchRecommendation) })
  window.ztools.onUpdateRecentRows((rows: number) => { windowStore.updateRecentRows(rows) })
  window.ztools.onUpdatePinnedRows((rows: number) => { windowStore.updatePinnedRows(rows) })
  window.ztools.onUpdateTabTarget((target: string) => { windowStore.updateTabTargetCommand(target) })
  window.ztools.onUpdateSpaceOpenCommand((enabled: boolean) => { windowStore.updateSpaceOpenCommand(enabled) })
  window.ztools.onUpdateFloatingBallDoubleClickCommand?.((command: string) => { windowStore.updateFloatingBallDoubleClickCommand(command) })
  window.ztools.onUpdateSearchMode((mode: string) => { windowStore.updateSearchMode(mode as 'aggregate' | 'list') })
  window.ztools.onUpdatePrimaryColor((data: { primaryColor: string; customColor?: string }) => { windowStore.updatePrimaryColor(data.primaryColor as any); if (data.customColor) { windowStore.updateCustomColor(data.customColor) } })

  if (window.ztools.getWindowMaterial) { window.ztools.getWindowMaterial().then((material) => { document.documentElement.setAttribute('data-material', material); applyAcrylicOverlay() }) }
  window.ztools.onUpdateWindowMaterial?.((material: 'mica' | 'acrylic' | 'none') => { document.documentElement.setAttribute('data-material', material); applyAcrylicOverlay() })
  window.ztools.onUpdateAcrylicOpacity?.((data: { lightOpacity: number; darkOpacity: number }) => { windowStore.updateAcrylicLightOpacity(data.lightOpacity); windowStore.updateAcrylicDarkOpacity(data.darkOpacity); applyAcrylicOverlay() })
  
  window.ztools.onAppLaunched(() => { searchQuery.value = ''; pastedImageData.value = null; pastedFilesData.value = null; pastedTextData.value = null; currentView.value = ViewMode.Search })
  
  window.ztools.onIpcLaunch((options) => {
    const launchOptions: any = { ...options, type: options.type === 'app' ? ('direct' as const) : options.type }
    if (options.type === 'plugin' && (!options.param || !options.param.payload)) {
      launchOptions.param = { ...options.param, payload: searchQuery.value, type: options.cmdType || 'text', inputState: { searchQuery: searchQuery.value, pastedImage: pastedImageData.value, pastedFiles: pastedFilesData.value } }
    }
    window.ztools.launch(launchOptions)
  })

  window.ztools.onFloatingBallFiles((files) => { currentView.value = ViewMode.Search; pastedFilesData.value = files; nextTick(() => { searchBoxRef.value?.focus() }); updateWindowHeight() })
  window.ztools.onFloatingBallDoubleClickCommand?.((command: string) => { if (!command) return; currentView.value = ViewMode.Search; nextTick(() => { launchTabTarget(command, '') }) })
  window.ztools.onRedirectSearch((data) => { currentView.value = ViewMode.Search; searchQuery.value = data.cmdName; nextTick(() => { searchBoxRef.value?.focus() }) })
  window.ztools.onPluginsChanged(async () => { await commandDataStore.loadCommands(); await commandDataStore.reloadUserData() })
  window.ztools.onUpdateDownloaded((data) => { windowStore.setUpdateDownloadInfo({ hasDownloaded: true, version: data.version, changelog: data.changelog }) })
  
  windowStore.checkDownloadedUpdate()

  window.ztools.onSuperPanelSearch((data: { text: string; clipboardContent?: any }) => {
    const searchText = data.text || ''; const cc = data.clipboardContent; const seen = new Set<string>(); const results: any[] = []
    const addResults = (items: any[]): void => { for (const item of items) { const key = `${item.path}:${item.featureCode || ''}`; if (!seen.has(key)) { seen.add(key); results.push(item) } } }
    if (cc?.type === 'image') { addResults(commandDataStore.searchImageCommands()) } 
    else if (cc?.type === 'file' && cc.files) { addResults(commandDataStore.searchFileCommands(cc.files)) } 
    else if (cc?.type === 'text' && cc.text) { const { bestMatches, regexMatches } = commandDataStore.search(cc.text); addResults(bestMatches); addResults(regexMatches) } 
    else if (searchText) { const { bestMatches, regexMatches } = commandDataStore.search(searchText); addResults(bestMatches); addResults(regexMatches) }
    window.ztools.sendSuperPanelSearchResult({ results: JSON.parse(JSON.stringify(results)), clipboardContent: cc })
  })

  window.ztools.onSuperPanelSearchWindowCommands((windowInfo: { app?: string; title?: string }) => { const results = commandDataStore.searchWindowCommands(windowInfo); window.ztools.sendSuperPanelWindowCommandsResult({ results: JSON.parse(JSON.stringify(results)) }) })

  window.ztools.onSuperPanelLaunch(async (data: { command: any; clipboardContent?: any; windowInfo?: any }) => {
      const cmd = data.command; const cc = data.clipboardContent; let payload: any = ''; let type = cmd.cmdType || 'text'
      if (cmd.cmdType === 'window' && data.windowInfo) { payload = data.windowInfo } 
      else if (cc) {
        if (cc.type === 'text' && cc.text) { payload = cc.text } 
        else if (cc.type === 'image' && cc.image) { payload = cc.image; type = 'img' } 
        else if (cc.type === 'file' && cc.files) { payload = cc.files.map((file: any) => ({ isFile: !file.isDirectory, isDirectory: file.isDirectory, name: file.name, path: file.path })); type = 'files' }
      }
      try { await window.ztools.launch({ path: cmd.path, type: cmd.type || 'plugin', featureCode: cmd.featureCode, name: cmd.name, cmdType: cmd.cmdType || type, param: { payload, type, inputState: { searchQuery: cc?.type === 'text' ? cc.text || '' : '', pastedImage: cc?.type === 'image' ? cc.image : null, pastedFiles: cc?.type === 'file' ? cc.files.map((file: any) => ({ isFile: !file.isDirectory, isDirectory: file.isDirectory, name: file.name, path: file.path })) : null, pastedText: cc?.type === 'text' ? cc.text : null } } }) } catch (error) {}
  })

  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('open-spotlight', () => toggleSpotlight(true))
})
</script>

<style scoped>
/* ================= 🚨 Spotlight 专属全局样式 ================= */
.spotlight-overlay {
  position: fixed;
  top: 0; left: 0;
  width: 100vw; height: 100vh;
  background: rgba(17, 17, 27, 0.75);
  backdrop-filter: blur(10px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 15vh;
  z-index: 99999;
}
.spotlight-modal {
  width: 650px;
  background: #181825;
  border: 1px solid #45475a;
  border-radius: 12px;
  box-shadow: 0 30px 60px rgba(0,0,0,0.6);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.spotlight-input-wrapper {
  display: flex;
  align-items: center;
  padding: 20px 25px;
  border-bottom: 1px solid #313244;
  background: #11111b;
}
.spotlight-icon {
  font-size: 24px;
  margin-right: 15px;
  opacity: 0.8;
}
.spotlight-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #cdd6f4;
  font-size: 22px;
  font-weight: 500;
  font-family: inherit;
}
.spotlight-input::placeholder { color: #6c7086; }
.esc-hint {
  font-size: 12px;
  color: #6c7086;
  background: #313244;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: bold;
}
.spotlight-results {
  max-height: 400px;
  overflow-y: auto;
  padding: 10px;
}
.spotlight-item {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  cursor: pointer;
  border-radius: 8px;
  border: 1px solid transparent;
  transition: 0.1s;
  margin-bottom: 5px;
}
.spotlight-item.active {
  background: rgba(137, 180, 250, 0.1);
  border-color: #89b4fa;
}
.spotlight-item-icon {
  font-size: 24px;
  margin-right: 15px;
  background: #11111b;
  border: 1px solid #313244;
  padding: 8px;
  border-radius: 8px;
}
.spotlight-item-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.spotlight-item-title {
  color: #cdd6f4;
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 4px;
}
.spotlight-item-desc {
  color: #a6adc8;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.module-tag {
  background: #313244;
  color: #bac2de;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  margin-right: 6px;
}
.spotlight-item-action {
  font-size: 12px;
  color: #89b4fa;
  font-weight: bold;
  opacity: 0;
  transition: 0.2s;
}
.spotlight-item.active .spotlight-item-action { opacity: 1; }
.spotlight-empty {
  padding: 40px;
  text-align: center;
  color: #6c7086;
  font-size: 14px;
}
.spotlight-footer {
  padding: 12px 20px;
  background: #11111b;
  border-top: 1px solid #313244;
  display: flex;
  justify-content: flex-end;
  gap: 15px;
  color: #6c7086;
  font-size: 12px;
}
.key-hint {
  background: #313244;
  padding: 2px 6px;
  border-radius: 4px;
  color: #cdd6f4;
  font-weight: bold;
  font-family: monospace;
}
.spin-loader { display: inline-block; animation: spin 2s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }
.fade-in-scale { animation: fadeInScale 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes fadeInScale { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
/* ============================================================== */

.pinned-active {
  color: #a6e3a1 !important; 
  font-weight: bold;
  background: rgba(166, 227, 161, 0.1) !important;
}
.app-container { width: 100%; display: flex; flex-direction: column; outline: none; overflow: hidden; border-radius: 8px; }
.app-container__plugin { border-radius: 0; }
.search-window { width: 100%; height: 100%; display: flex; flex-direction: column; }
.search-box-wrapper { flex-shrink: 0; }
.plugin-placeholder { flex: 1; background: transparent; -webkit-app-region: no-drag; user-select: none; }

.mtools-entry-btn {
  position: absolute; right: 65px; top: 14px; background: #181825; border: 1px solid #313244; color: #89b4fa; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; z-index: 100; transition: all 0.2s ease; font-size: 13px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}
.mtools-entry-btn:hover { background: #89b4fa; color: #11111b; transform: translateY(-1px); }

.mtools-dashboard { display: flex; height: 100vh; background: #11111b; color: #cdd6f4; border-radius: 8px; overflow: hidden; }
.sidebar { width: 200px; background: #181825; border-right: 1px solid #313244; display: flex; flex-direction: column; padding: 20px 0; -webkit-app-region: drag; transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1); overflow: hidden; white-space: nowrap; }
.sidebar.collapsed { width: 68px; }
.logo { display: flex; align-items: center; height: 56px; padding: 0 10px; font-size: 20px; font-weight: 800; color: #89b4fa; border-bottom: 1px solid #313244; margin-bottom: 10px; cursor: pointer; -webkit-app-region: no-drag; }
.logo .icon, .nav-menu { flex: 1; padding: 0 10px; display: flex; flex-direction: column; gap: 5px; }
.nav-item { display: flex; align-items: center; height: 44px; padding: 0 11px; border-radius: 6px; cursor: pointer; color: #a6adc8; transition: background 0.2s, color 0.2s; -webkit-app-region: no-drag; }
.nav-item:hover { background: #313244; color: #cdd6f4; }
.nav-item.active { background: rgba(137, 180, 250, 0.15); color: #89b4fa; font-weight: bold; }
.nav-item .icon { display: inline-block; min-width: 24px; text-align: center; font-size: 16px; margin-right: 12px; flex-shrink: 0; }
.sidebar .text { opacity: 1; transition: opacity 0.2s ease; white-space: nowrap; }
.sidebar.collapsed .text { opacity: 0; pointer-events: none; }
.bottom-tools { padding: 10px; border-top: 1px solid #313244; -webkit-app-region: no-drag; }

.workspace { flex: 1; padding: 20px; background: #1e1e2e; display: flex; overflow: hidden; -webkit-app-region: drag; }
.workspace-full { width: 100%; height: 100%; -webkit-app-region: no-drag; }
.welcome-card { background: #181825; padding: 40px; border-radius: 12px; text-align: center; border: 1px solid #313244; -webkit-app-region: no-drag; margin: auto; }
.welcome-card h2 { color: #f5e0dc; margin-top: 0; }
.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 20px; transition: 0.2s; }
.btn-primary:hover { background: #b4befe; }
.btn-outline { background: transparent; color: #89b4fa; border: 1px solid #89b4fa; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 20px; transition: 0.2s; }
.btn-outline:hover { background: rgba(137, 180, 250, 0.1); }
.fade-in { animation: fadeIn 0.2s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
</style>z