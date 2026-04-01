import path from 'path'
import { pathToFileURL } from 'url'

/**
 * 标准化图标路径
 * @param iconPath 原始图标路径
 * @param basePath 基础路径（插件根目录路径）
 * @returns 标准化后的图标路径
 */
export function normalizeIconPath(iconPath: string, basePath: string): string {
  // 如果是 base64，直接返回
  if (iconPath.startsWith('data:')) {
    return iconPath
  }

  // 如果是 http/https，直接返回
  if (iconPath.startsWith('http://') || iconPath.startsWith('https://')) {
    return iconPath
  }

  // 如果已经是 file:// 协议，直接返回
  if (iconPath.startsWith('file:///')) {
    return iconPath
  }

  // 否则认为是相对路径，转换为绝对路径
  const absolutePath = path.join(basePath, iconPath)
  return pathToFileURL(absolutePath).href
}
