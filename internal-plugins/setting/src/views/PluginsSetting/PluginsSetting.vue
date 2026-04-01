<template>
  <div class="content-panel">
    <Transition name="list-slide">
      <div v-show="!isDetailVisible" class="scrollable-content">
        <div class="panel-header">
          <div class="tab-group">
            <button class="tab-btn" :class="{ active: filterStatus === 'all' }" @click="filterStatus = 'all'">
              全部 <span class="tab-count">{{ allPluginsCount }}</span>
            </button>
            <button class="tab-btn" :class="{ active: filterStatus === 'running' }" @click="filterStatus = 'running'">
              运行中 <span class="tab-count">{{ runningPluginsCount }}</span>
            </button>
          </div>
          <div class="button-group">
            <button class="btn" :disabled="isImporting" @click="importPlugin">
              {{ isImporting ? '导入中...' : '📥 导入本地插件' }}
            </button>
            <button class="btn btn-outline" :disabled="isImportingDev" @click="importDevPlugin">
              🔧 添加开发中插件
            </button>
            <button class="btn btn-danger" :disabled="isKillingAll || runningPluginsCount === 0" @click="handleKillAllPlugins">
              ⏹ 停止所有
            </button>
          </div>
        </div>

        <div class="plugin-list">
          <div v-for="plugin in filteredPlugins" :key="plugin.path" class="card plugin-item" @click="openPluginDetail(plugin)">
            <AdaptiveIcon v-if="plugin.logo" :src="plugin.logo" class="plugin-icon" draggable="false" />
            <div v-else class="plugin-icon-placeholder">🧩</div>
            
            <div class="plugin-info">
              <div class="plugin-name">
                {{ plugin.title || plugin.name }}
                <span class="plugin-version">v{{ plugin.version }}</span>
                <span v-if="plugin.isDevelopment" class="dev-badge">开发中</span>
                <span v-if="isPluginRunning(plugin.path)" class="running-badge">
                  <span class="status-dot"></span>运行中
                </span>
              </div>
              <div class="plugin-desc">{{ plugin.description || '纯本地轨道拓展模块' }}</div>
            </div>
          </div>

          <div v-if="!isLoading && plugins.length === 0" class="empty-state">
            <div class="empty-text">Mtools 轨道一：暂无轻量插件</div>
            <div class="empty-hint">点击右上角 "导入本地插件" 开始拓展</div>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="slide">
      <PluginDetail
        v-if="isDetailVisible && selectedPlugin"
        :plugin="selectedPlugin"
        :is-running="isPluginRunning(selectedPlugin.path)"
        :is-pinned="isPluginPinned(selectedPlugin.path)"
        @back="closePluginDetail"
        @open="handleOpenPlugin(selectedPlugin)"
        @uninstall="handleUninstallFromDetail(selectedPlugin)"
        @kill="handleKillPlugin(selectedPlugin)"
        @open-folder="handleOpenFolder(selectedPlugin)"
        @reload="handleReloadPluginFromDetail(selectedPlugin)"
        @toggle-pin="togglePin(selectedPlugin)"
      />
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useToast, AdaptiveIcon } from '@/components'
// 🚨 这里绝对没有导入 NpmInstallPanel
import { PluginDetail } from './components'
import { weightedSearch } from '@/utils'
import { useJumpFunction, useZtoolsSubInput } from '@/composables'
import { useRouter } from 'vue-router'

const { success, error, warning, confirm } = useToast()
const router = useRouter()

const plugins = ref<any[]>([])
const runningPlugins = ref<string[]>([])
const isLoading = ref(true)
const isImporting = ref(false)
const isImportingDev = ref(false)
const isKillingAll = ref(false)

const isDetailVisible = ref(false)
const selectedPlugin = ref<any | null>(null)
const filterStatus = ref<'all' | 'running'>('all')

const PINNED_PLUGINS_KEY = 'plugin-center-pinned'
const pinnedPluginPaths = ref<string[]>([])

const { value: searchQuery } = useZtoolsSubInput('', '搜索本地插件...')

const searchFilteredPlugins = computed(() => {
  return weightedSearch(plugins.value, searchQuery.value || '', [
    { value: (p) => p.title || p.name || '', weight: 10 },
    { value: (p) => p.description || '', weight: 5 }
  ])
})

const allPluginsCount = computed(() => searchFilteredPlugins.value.length)
const runningFilteredPlugins = computed(() => searchFilteredPlugins.value.filter((p) => isPluginRunning(p.path)))
const runningPluginsCount = computed(() => runningFilteredPlugins.value.length)

const filteredPlugins = computed(() => {
  let list = filterStatus.value === 'running' ? runningFilteredPlugins.value : searchFilteredPlugins.value
  const pinnedOrder = pinnedPluginPaths.value
  if (pinnedOrder.length === 0) return list
  const pinnedSet = new Set(pinnedOrder)
  const pinnedItems = pinnedOrder.map((path) => list.find((p) => p.path === path)).filter(Boolean) as typeof list
  const unpinnedItems = list.filter((p) => !pinnedSet.has(p.path))
  return [...pinnedItems, ...unpinnedItems]
})

function isPluginPinned(path: string) { return pinnedPluginPaths.value.includes(path) }
function isPluginRunning(path: string) { return runningPlugins.value.includes(path) }

async function togglePin(plugin: any) {
  const path = plugin.path
  if (pinnedPluginPaths.value.includes(path)) {
    pinnedPluginPaths.value = pinnedPluginPaths.value.filter((p) => p !== path)
  } else {
    pinnedPluginPaths.value = [path, ...pinnedPluginPaths.value]
  }
  try { await window.ztools.internal.dbPut(PINNED_PLUGINS_KEY, [...pinnedPluginPaths.value]) } catch (e) {}
}

async function loadPlugins() {
  isLoading.value = true
  try {
    const installed = await window.ztools.internal.getPlugins()
    plugins.value = installed.map((p: any) => ({ ...p, installed: true }))
    await loadRunningPlugins()
  } catch (err) {} finally { isLoading.value = false }
}

async function loadRunningPlugins() {
  try { runningPlugins.value = await window.ztools.internal.getRunningPlugins() } catch (e) {}
}

async function importPlugin() {
  if (isImporting.value) return
  isImporting.value = true
  try {
    const result = await window.ztools.internal.selectPluginFile()
    if (result.success && result.filePath) {
      router.replace({ name: 'PluginInstaller', query: { _t: Date.now() }, state: { installFilePath: result.filePath } })
    }
  } catch (err) {} finally { isImporting.value = false }
}

async function importDevPlugin() {
  isImportingDev.value = true
  try {
    const result = await window.ztools.internal.importDevPlugin()
    if (result.success) { await loadPlugins(); success('开发中插件添加成功!') }
  } catch (err) {} finally { isImportingDev.value = false }
}

async function handleKillAllPlugins() {
  if (isKillingAll.value || runningFilteredPlugins.value.length === 0) return
  isKillingAll.value = true
  try {
    for (const p of runningFilteredPlugins.value) await window.ztools.internal.killPlugin(p.path)
    await loadRunningPlugins()
    success('已停止所有插件')
  } catch (err) {} finally { isKillingAll.value = false }
}

async function handleKillPlugin(plugin: any) {
  await window.ztools.internal.killPlugin(plugin.path)
  await loadRunningPlugins()
}

async function handleOpenPlugin(plugin: any) {
  await window.ztools.internal.launch({ path: plugin.path, type: 'plugin', name: plugin.title || plugin.name, param: {} })
}

async function handleOpenFolder(plugin: any) { await window.ztools.internal.revealInFinder(plugin.path) }

async function handleReloadPluginFromDetail(plugin: any) {
  const res = await window.ztools.internal.reloadPlugin(plugin.path)
  if (res.success) { await loadPlugins(); success('重载成功') }
}

async function handleUninstallFromDetail(plugin: any) {
  const res = await window.ztools.internal.deletePlugin(plugin.path)
  if (res.success) { closePluginDetail(); await loadPlugins(); success('卸载成功') }
}

function openPluginDetail(plugin: any) { selectedPlugin.value = plugin; isDetailVisible.value = true }
function closePluginDetail() { isDetailVisible.value = false; selectedPlugin.value = null }

useJumpFunction(() => { void loadRunningPlugins() })

onMounted(async () => {
  try {
    const data = await window.ztools.internal.dbGet(PINNED_PLUGINS_KEY)
    pinnedPluginPaths.value = Array.isArray(data) ? data : []
  } catch (e) {}
  await loadPlugins()
})
</script>

<style scoped>
.content-panel {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.scrollable-content {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px;
  background: var(--bg-color);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.tab-group {
  display: flex;
  gap: 6px;
  background: var(--control-bg);
  padding: 3px;
  border-radius: 8px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.tab-btn:hover {
  background: var(--hover-bg);
  color: var(--text-color);
}

.tab-btn.active {
  background: var(--active-bg);
  color: var(--primary-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.tab-count {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--control-bg);
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.tab-btn.active .tab-count {
  background: var(--primary-light-bg);
  color: var(--primary-color);
}

.button-group {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: bold;
  border: none;
  cursor: pointer;
  background: var(--primary-color);
  color: #fff;
}

.btn-outline {
  background: transparent;
  color: var(--text-color);
  border: 1px solid var(--control-border);
}

.btn-danger {
  background: transparent;
  color: var(--warning-color);
  border: 1px solid var(--control-border);
}

.plugin-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.plugin-item {
  display: flex;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--dialog-bg, var(--bg-color));
  border: 1px solid var(--divider-color);
  border-radius: 8px;
}

.plugin-item:hover {
  background: var(--hover-bg);
  transform: translateX(2px);
  border-color: var(--control-border);
}

.plugin-icon,
.plugin-icon-placeholder {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  margin-right: 12px;
  flex-shrink: 0;
}

.plugin-icon-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--active-bg);
  font-size: 24px;
}

.plugin-info {
  flex: 1;
  min-width: 0;
}

.plugin-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.plugin-version {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 2px 6px;
  background: var(--active-bg);
  border-radius: 4px;
}

.dev-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  color: var(--purple-color);
  background: var(--purple-light-bg);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--purple-border);
}

.running-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  color: var(--success-color);
  background: var(--success-light-bg);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--success-color);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--success-color);
  animation: pulse-dot 2s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.plugin-desc {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 14px;
  color: var(--text-secondary);
}

.list-slide-enter-active,
.list-slide-leave-active {
  transition: transform 0.2s ease-out, opacity 0.15s ease;
}

.list-slide-enter-from,
.list-slide-leave-to {
  transform: translateX(-10%);
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>