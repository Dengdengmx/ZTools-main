import { ref, toRaw, watch } from 'vue'
import { useCommandDataStore } from '../stores/commandDataStore'

/**
 * mainPush 结果项（插件回调返回的单个搜索结果）
 */
export interface MainPushItem {
  icon?: string
  text: string
  title?: string
  [key: string]: any // 插件自定义字段
}

/**
 * mainPush 分组结果（一个 feature 对应一组搜索结果）
 */
export interface MainPushGroup {
  featureKey: string // pluginPath:featureCode
  pluginPath: string
  pluginName: string
  pluginLogo: string
  featureCode: string
  featureExplain: string
  featureIcon?: string
  matchedCmdType: string
  items: MainPushItem[]
}

/**
 * mainPush 查询 composable
 * 监听搜索输入，自动查询匹配的 mainPush 插件获取动态结果
 */
export function useMainPushResults(props: {
  searchQuery: string
  pastedImage?: string | null
  pastedFiles?: any[] | null
  pastedText?: string | null
}): {
  mainPushGroups: typeof mainPushGroups
  handleMainPushSelect: (
    group: MainPushGroup,
    item: MainPushItem,
    searchQuery: string
  ) => Promise<boolean>
} {
  const commandDataStore = useCommandDataStore()
  const mainPushGroups = ref<MainPushGroup[]>([])

  let queryTimer: ReturnType<typeof setTimeout> | null = null
  let queryVersion = 0

  // 查询 mainPush 插件
  async function queryMainPushPlugins(query: string): Promise<void> {
    const currentVersion = ++queryVersion

    // 粘贴图片/文件时不触发 mainPush
    if (props.pastedImage || props.pastedFiles) {
      mainPushGroups.value = []
      return
    }

    const searchText = props.pastedText || query
    if (!searchText.trim()) {
      mainPushGroups.value = []
      return
    }

    // 获取匹配的 mainPush 功能
    const matchingFeatures = commandDataStore.getMatchingMainPushFeatures(searchText)
    if (matchingFeatures.length === 0) {
      mainPushGroups.value = []
      return
    }

    // 并行查询所有匹配的插件
    const results = await Promise.all(
      matchingFeatures.map(async (feature) => {
        try {
          const queryData = {
            code: feature.featureCode,
            type: feature.matchedCmdType,
            payload: searchText
          }
          const items = await window.ztools.queryMainPush(
            feature.pluginPath,
            feature.featureCode,
            queryData
          )
          return { feature, items: Array.isArray(items) ? items : [] }
        } catch (error) {
          console.error(`[MainPush] 查询插件 ${feature.pluginName} 失败:`, error)
          return { feature, items: [] }
        }
      })
    )

    // 检查版本，防止旧查询覆盖新查询
    if (currentVersion !== queryVersion) return

    // 构建分组结果（过滤空结果）
    mainPushGroups.value = results
      .filter((r) => r.items.length > 0)
      .map((r) => ({
        featureKey: `${r.feature.pluginPath}:${r.feature.featureCode}`,
        pluginPath: r.feature.pluginPath,
        pluginName: r.feature.pluginName,
        pluginLogo: r.feature.pluginLogo,
        featureCode: r.feature.featureCode,
        featureExplain: r.feature.featureExplain,
        featureIcon: r.feature.featureIcon,
        matchedCmdType: r.feature.matchedCmdType,
        items: r.items
      }))
  }

  // 监听搜索变化，带防抖
  watch(
    [
      () => props.searchQuery,
      () => props.pastedText,
      () => props.pastedImage,
      () => props.pastedFiles
    ],
    () => {
      if (queryTimer) {
        clearTimeout(queryTimer)
      }
      queryTimer = setTimeout(() => {
        queryMainPushPlugins(props.searchQuery)
      }, 300) // 300ms 防抖
    }
  )

  /**
   * 用户选择 mainPush 结果项
   * @returns 是否需要进入插件界面
   */
  async function handleMainPushSelect(
    group: MainPushGroup,
    item: MainPushItem,
    searchQuery: string
  ): Promise<boolean> {
    try {
      const rawItem = JSON.parse(JSON.stringify(toRaw(item)))
      // 剔除内部展示字段，还原为插件 callback 返回的原始数据
      delete rawItem._resolvedIcon
      const selectData = {
        code: group.featureCode,
        type: group.matchedCmdType,
        payload: searchQuery,
        option: rawItem
      }
      return await window.ztools.selectMainPush(group.pluginPath, group.featureCode, selectData)
    } catch (error) {
      console.error(`[MainPush] 选择处理失败:`, error)
      return false
    }
  }

  return {
    mainPushGroups,
    handleMainPushSelect
  }
}
