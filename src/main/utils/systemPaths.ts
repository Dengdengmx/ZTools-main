import { app } from 'electron'
import os from 'os'
import path from 'path'

/**
 * 获取 Windows 开始菜单路径
 */
export function getWindowsScanPaths(): string[] {
  // 系统级开始菜单
  const programDataStartMenu = path.join(
    'C:',
    'ProgramData',
    'Microsoft',
    'Windows',
    'Start Menu',
    'Programs'
  )

  // 用户级开始菜单
  const userStartMenu = path.join(
    os.homedir(),
    'AppData',
    'Roaming',
    'Microsoft',
    'Windows',
    'Start Menu',
    'Programs'
  )

  // 用户桌面（使用 Electron API 获取真实路径，支持桌面被移到其他位置的情况）
  const userDesktop = app.getPath('desktop')

  // 公共桌面
  const publicDesktop = path.join('C:', 'Users', 'Public', 'Desktop')

  return [programDataStartMenu, userStartMenu, userDesktop, publicDesktop]
}

/**
 * 获取 macOS 应用目录路径
 */
export function getMacApplicationPaths(): string[] {
  return ['/Applications', '/System/Applications', `${process.env.HOME}/Applications`]
}
