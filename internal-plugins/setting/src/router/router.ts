import { createRouter, createWebHashHistory } from 'vue-router'

// 🚨 只引入我们 Mtools 需要的核心设置面板
import GeneralSetting from '../views/GeneralSetting/GeneralSetting.vue'
import ShortcutsSetting from '../views/ShortcutsSetting/ShortcutsSetting.vue'
import PluginsSetting from '../views/PluginsSetting/PluginsSetting.vue'
import AboutSetting from '../views/AboutSetting/AboutSetting.vue'

const routes = [
  {
    path: '/',
    redirect: '/general'
  },
  {
    path: '/general',
    name: 'GeneralSetting',
    component: GeneralSetting,
    meta: { menu: { label: '常规设置', icon: 'i-carbon-settings' } }
  },
  {
    path: '/shortcuts',
    name: 'ShortcutsSetting',
    component: ShortcutsSetting,
    meta: { menu: { label: '全局快捷键', icon: 'i-carbon-keyboard' } }
  },
  {
    path: '/plugins',
    name: 'PluginsSetting',
    component: PluginsSetting,
    // 🚨 名字改成更准确的“轻量插件管理”
    meta: { menu: { label: '轻量插件管理', icon: 'i-carbon-plugin' } } 
  },
  {
    path: '/about',
    name: 'AboutSetting',
    component: AboutSetting,
    meta: { menu: { label: '关于 Mtools', icon: 'i-carbon-information' } }
  }
  // 💀 其他的 Sync(同步)、AiModels(大模型)、Market(市场)、Mcp、Http 统统砍掉了！
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export type MenuRouterItemType = {
  name: string
  path: string
  meta: {
    menu: {
      label: string
      icon: string
    }
  }
}