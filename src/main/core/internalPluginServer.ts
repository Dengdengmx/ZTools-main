import { app } from 'electron'
import { createServer, Server } from 'http'
import fs from 'fs'
import path from 'path'

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.webp': 'image/webp',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject',
  '.map': 'application/json',
  '.wasm': 'application/wasm'
}

let serverPort = 0
let server: Server | null = null

/**
 * 启动内置插件静态文件 HTTP server（仅生产环境）
 * 用于解决 file:// 协议下第三方 iframe CSP 限制问题
 */
export async function startInternalPluginServer(): Promise<number> {
  if (!app.isPackaged) return 0

  const basePath = path.join(process.resourcesPath, 'app.asar.unpacked', 'internal-plugins')

  if (!fs.existsSync(basePath)) {
    console.warn('[InternalPluginServer] 内置插件目录不存在:', basePath)
    return 0
  }

  server = createServer((req, res) => {
    if (!req.url || req.method !== 'GET') {
      res.writeHead(405)
      res.end()
      return
    }

    // 解析 URL，去掉 query string
    const urlPath = decodeURIComponent(req.url.split('?')[0])

    // 映射到文件系统路径
    const filePath = path.resolve(path.join(basePath, urlPath))

    // 安全检查：防止目录穿越
    if (!filePath.startsWith(basePath)) {
      res.writeHead(403)
      res.end()
      return
    }

    // 检查文件是否存在
    if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
      res.writeHead(404)
      res.end()
      return
    }

    // 确定 MIME 类型
    const ext = path.extname(filePath).toLowerCase()
    const contentType = MIME_TYPES[ext] || 'application/octet-stream'

    try {
      const content = fs.readFileSync(filePath)
      res.writeHead(200, { 'Content-Type': contentType })
      res.end(content)
    } catch {
      res.writeHead(500)
      res.end()
    }
  })

  return new Promise((resolve, reject) => {
    server!.listen(0, '127.0.0.1', () => {
      const addr = server!.address()
      if (addr && typeof addr === 'object') {
        serverPort = addr.port
        console.log(`[InternalPluginServer] 已启动: http://127.0.0.1:${serverPort}`)
        resolve(serverPort)
      } else {
        reject(new Error('无法获取 server 地址'))
      }
    })

    server!.on('error', (err) => {
      console.error('[InternalPluginServer] 启动失败:', err)
      reject(err)
    })
  })
}

/**
 * 获取内置插件的 HTTP URL
 */
export function getInternalPluginUrl(pluginName: string, mainFile: string): string {
  if (serverPort === 0) return ''
  return `http://127.0.0.1:${serverPort}/${pluginName}/${mainFile}`
}

/**
 * 获取 server 端口号（0 表示未启动）
 */
export function getInternalPluginServerPort(): number {
  return serverPort
}
