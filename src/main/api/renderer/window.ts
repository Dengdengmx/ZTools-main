import { ipcMain, screen, BrowserWindow } from 'electron'
import path from 'path'
import fs from 'fs'
import { WINDOW_INITIAL_HEIGHT, WINDOW_WIDTH } from '../../common/constants.js'
import windowManager from '../../managers/windowManager.js'

// 窗口材质类型
type WindowMaterial = 'mica' | 'acrylic' | 'none'

/**
 * 窗口管理API - 主程序专用
 */
export class WindowAPI {
  private mainWindow: Electron.BrowserWindow | null = null
  private lockedSize: { width: number; height: number } | null = null
  private currentAssemblyTarget: string | null = null

  public init(mainWindow: Electron.BrowserWindow): void {
    this.mainWindow = mainWindow
    this.setupIPC()
    this.setupWindowEvents()
  }

  private setupIPC(): void {
    ipcMain.on('hide-window', () => this.hideWindow())
    ipcMain.on('resize-window', (_event, height: number) => this.resizeWindow(height))
    ipcMain.handle('get-window-position', () => this.getWindowPosition())
    ipcMain.handle('get-window-material', () => this.getWindowMaterial())
    
    ipcMain.on('set-window-pinned', (_event, pinned: boolean) => {
      windowManager.setWindowPinned(pinned)
    })

    ipcMain.on('set-window-position', (_event, x: number, y: number) =>
      this.setWindowPosition(x, y)
    )
    // 拖动控制：锁定/解锁窗口尺寸
    ipcMain.on('set-window-size-lock', (_event, lock: boolean) => {
      if (!this.mainWindow) return

      if (lock) {
        // 锁定：记录当前尺寸（宽度使用固定常量，避免多显示器 DPI 缩放导致尺寸漂移）
        const [, height] = this.mainWindow.getSize()
        this.lockedSize = { width: WINDOW_WIDTH, height }
      } else {
        // 解锁：验证并恢复尺寸
        if (this.lockedSize) {
          const [, height] = this.mainWindow.getSize()
          if (WINDOW_WIDTH !== this.lockedSize.width || height !== this.lockedSize.height) {
            this.mainWindow.setSize(this.lockedSize.width, this.lockedSize.height)
          }
          this.lockedSize = null
        }
      }
    })
    ipcMain.on('set-window-opacity', (_event, opacity: number) => this.setWindowOpacity(opacity))
    ipcMain.handle('set-tray-icon-visible', (_event, visible: boolean) =>
      this.setTrayIconVisible(visible)
    )
    ipcMain.handle('set-assembly-target', (_event, token: string) => {
      this.currentAssemblyTarget = token
      return true
    })
    ipcMain.handle('end-assembly-plugin', () => {
      return this.currentAssemblyTarget
    })
    ipcMain.on('open-settings', () => this.openSettings())

    // 🌟 挂载开启独立工作站窗口的路由
    ipcMain.handle('open-dashboard-window', () => this.openDashboardWindow())
  }

  private setupWindowEvents(): void {
    let moveTimeout: NodeJS.Timeout | null = null
    this.mainWindow?.on('move', () => {
      if (moveTimeout) clearTimeout(moveTimeout)
      moveTimeout = setTimeout(() => {
        if (this.mainWindow) {
          const [x, y] = this.mainWindow.getPosition()
          const displayId = windowManager.getCurrentDisplayId()
          if (displayId !== null) {
            windowManager.saveWindowPosition(displayId, x, y)
          }
        }
      }, 500)
    })
  }

  private hideWindow(isRestorePreWindow: boolean = true): void {
    windowManager.hideWindow(isRestorePreWindow)
  }

  public resizeWindow(height: number): void {
    if (this.mainWindow) {
      // 🚨 精准判定：传入高度大于 600，说明进入了重型工作站模式
      const isDashboard = height > 600
      
      // 工作站给 1200 的宽广视野，搜索框则恢复原版 WINDOW_WIDTH
      const width = isDashboard ? 1200 : WINDOW_WIDTH 
      
      const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint())
      const maxHeight = display.workAreaSize.height
      const newHeight = Math.max(WINDOW_INITIAL_HEIGHT, Math.min(height, maxHeight))

      // 必须先开启 resizable，Electron 才允许程序修改大小
      this.mainWindow.setResizable(true)
      this.mainWindow.setSize(width, newHeight) 

      // 🚨 核心精准控制：
      // 如果当前是工作站，保留 resizable = true，允许你用鼠标自由拖拽拉伸！
      // 如果退回了搜索框，立刻恢复 resizable = false，锁死尺寸！
      this.mainWindow.setResizable(isDashboard)

      if (this.lockedSize) {
        this.lockedSize = { width, height: newHeight }
        console.log('[WindowAPI] 更新锁定尺寸:', this.lockedSize)
      }
    }
  }

  public getWindowPosition(): { x: number; y: number } {
    if (this.mainWindow) {
      const [x, y] = this.mainWindow.getPosition()
      return { x, y }
    }
    return { x: 0, y: 0 }
  }

  public setWindowPosition(x: number, y: number): void {
    if (this.mainWindow && this.lockedSize) {
      // 拖动时强制保持锁定的尺寸
      this.mainWindow.setBounds({
        x: Math.round(x),
        y: Math.round(y),
        width: this.lockedSize.width,
        height: this.lockedSize.height
      })
    } else if (this.mainWindow) {
      this.mainWindow.setPosition(x, y)
    }
  }

  private setWindowOpacity(opacity: number): void {
    if (this.mainWindow) {
      const clampedOpacity = Math.max(0.3, Math.min(1, opacity))
      this.mainWindow.setOpacity(clampedOpacity)
      console.log('[WindowAPI] 设置窗口不透明度:', clampedOpacity)
    }
  }

  private setTrayIconVisible(visible: boolean): void {
    windowManager.setTrayIconVisible(visible)
    console.log('[WindowAPI] 设置托盘图标可见性:', visible)
  }

  public setWindowMaterial(material: WindowMaterial): { success: boolean } {
    const result = windowManager.setWindowMaterial(material)
    console.log('[WindowAPI] 设置窗口材质:', material, '结果:', result)
    return result
  }

  public async getWindowMaterial(): Promise<WindowMaterial> {
    const material = await windowManager.getWindowMaterial()
    return material
  }

  private openSettings(): void {
    windowManager.showSettings()
    console.log('[WindowAPI] 打开设置插件')
  }

  public async updateAutoBackToSearch(autoBackToSearch: string): Promise<void> {
    await windowManager.updateAutoBackToSearch(autoBackToSearch)
    console.log('[WindowAPI] 更新自动返回搜索配置:', autoBackToSearch)
  }

  // 🌟 新增：独立孵化工作站窗口的方法 (修复白屏崩溃版本)
  public openDashboardWindow(): void {
    if (!this.mainWindow) return

    // 🚨 核心修复 1: 动态多级探测 preload.js 路径，防止由于打包层级不同导致找不到 preload 从而白屏
    let preloadPath = path.join(__dirname, '../../../preload/index.js')
    if (!fs.existsSync(preloadPath)) {
        preloadPath = path.join(__dirname, '../../preload/index.js')
    }
    if (!fs.existsSync(preloadPath)) {
        preloadPath = path.join(__dirname, '../preload/index.js')
    }

    const isMac = process.platform === 'darwin'
    const dashWin = new BrowserWindow({
      width: 1200,
      height: 800,
      minWidth: 800,
      minHeight: 600,
      frame: isMac ? false : true,
      titleBarStyle: isMac ? 'hiddenInset' : 'default',
      autoHideMenuBar: true,
      backgroundColor: '#11111b', // 强制黑底色，防止渲染前出现刺眼的白屏闪烁
      title: "Mtools 实验室工作站",
      ...(isMac && { trafficLightPosition: { x: 15, y: 18 } }),
      webPreferences: {
        preload: preloadPath,
        contextIsolation: true,
        nodeIntegration: false,
        webSecurity: false,
        backgroundThrottling: false
      }
    })

    // 🚨 核心修复 2: 提取当前主窗口 URL，并完美保留 Vue 的 Hash 路由结构，防止路由丢失导致白纸
    let currentUrl = this.mainWindow.webContents.getURL()
    let hash = currentUrl.includes('#') ? '#' + currentUrl.split('#')[1] : ''
    let baseUrl = currentUrl.split('#')[0].split('?')[0]

    dashWin.loadURL(`${baseUrl}?mode=dashboard${hash}`)

    dashWin.once('ready-to-show', () => {
      dashWin.show()
      this.hideWindow() // 隐藏主搜索框，等待热键再次唤醒
    })
  }
}

export default new WindowAPI()