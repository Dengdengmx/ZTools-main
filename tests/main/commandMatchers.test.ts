import { describe, it, expect } from 'vitest'
import {
  findCommandIndex,
  filterOutCommand,
  hasCommand
} from '../../src/main/api/renderer/commandMatchers'

// ========== findCommandIndex ==========

describe('findCommandIndex', () => {
  const list = [
    { name: '原神', path: 'C:\\launcher.exe', type: 'app' },
    { name: '米哈游启动器', path: 'C:\\launcher.exe', type: 'app' },
    { name: 'Chrome', path: 'C:\\chrome.exe', type: 'app' },
    { name: '翻译', path: '/plugins/translate', type: 'plugin', featureCode: 'translate' },
    { name: '词典', path: '/plugins/translate', type: 'plugin', featureCode: 'dict' }
  ]

  describe('非插件类型', () => {
    it('应同时匹配 name 和 path', () => {
      const idx = findCommandIndex(list, 'C:\\launcher.exe', 'app', undefined, '原神')
      expect(idx).toBe(0)
    })

    it('应区分同路径不同名的应用', () => {
      const idx = findCommandIndex(list, 'C:\\launcher.exe', 'app', undefined, '米哈游启动器')
      expect(idx).toBe(1)
    })

    it('路径匹配但名称不匹配时应返回 -1', () => {
      const idx = findCommandIndex(list, 'C:\\launcher.exe', 'app', undefined, '不存在的名称')
      expect(idx).toBe(-1)
    })

    it('名称匹配但路径不匹配时应返回 -1', () => {
      const idx = findCommandIndex(list, 'C:\\other.exe', 'app', undefined, '原神')
      expect(idx).toBe(-1)
    })
  })

  describe('插件类型', () => {
    it('应匹配 path + featureCode', () => {
      const idx = findCommandIndex(list, '/plugins/translate', 'plugin', 'translate')
      expect(idx).toBe(3)
    })

    it('应区分同路径不同 featureCode 的插件', () => {
      const idx = findCommandIndex(list, '/plugins/translate', 'plugin', 'dict')
      expect(idx).toBe(4)
    })

    it('featureCode 不匹配时应返回 -1', () => {
      const idx = findCommandIndex(list, '/plugins/translate', 'plugin', 'nonexistent')
      expect(idx).toBe(-1)
    })
  })

  describe('旧数据兼容（name 缺失）', () => {
    it('未传 name 时应降级为仅匹配 path', () => {
      const idx = findCommandIndex(list, 'C:\\launcher.exe', 'app')
      expect(idx).toBe(0) // 匹配到第一个同路径的
    })

    it('未传 name 时对不存在的 path 应返回 -1', () => {
      const idx = findCommandIndex(list, 'C:\\nonexistent.exe', 'app')
      expect(idx).toBe(-1)
    })
  })

  it('列表为空时应返回 -1', () => {
    expect(findCommandIndex([], 'any', 'app', undefined, 'any')).toBe(-1)
  })
})

// ========== filterOutCommand ==========

describe('filterOutCommand', () => {
  describe('非插件类型', () => {
    it('应只过滤匹配 name + path 的项', () => {
      const list = [
        { name: '原神', path: 'C:\\launcher.exe', type: 'app' },
        { name: '米哈游启动器', path: 'C:\\launcher.exe', type: 'app' },
        { name: 'Chrome', path: 'C:\\chrome.exe', type: 'app' }
      ]
      const result = filterOutCommand(list, 'C:\\launcher.exe', undefined, '原神')
      expect(result).toHaveLength(2)
      expect(result.map((i) => i.name)).toEqual(['米哈游启动器', 'Chrome'])
    })

    it('不应误删同路径不同名的应用', () => {
      const list = [
        { name: '原神', path: 'C:\\launcher.exe', type: 'app' },
        { name: '米哈游启动器', path: 'C:\\launcher.exe', type: 'app' }
      ]
      const result = filterOutCommand(list, 'C:\\launcher.exe', undefined, '原神')
      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('米哈游启动器')
    })

    it('没有 name 参数时应按纯路径匹配（兼容旧逻辑）', () => {
      const list = [
        { name: '原神', path: 'C:\\launcher.exe', type: 'app' },
        { name: '米哈游启动器', path: 'C:\\launcher.exe', type: 'app' }
      ]
      const result = filterOutCommand(list, 'C:\\launcher.exe')
      expect(result).toHaveLength(0)
    })
  })

  describe('插件类型', () => {
    it('应只过滤匹配 path + featureCode 的插件', () => {
      const list = [
        { name: '翻译', path: '/plugins/translate', type: 'plugin', featureCode: 'translate' },
        { name: '词典', path: '/plugins/translate', type: 'plugin', featureCode: 'dict' }
      ]
      const result = filterOutCommand(list, '/plugins/translate', 'translate')
      expect(result).toHaveLength(1)
      expect(result[0].featureCode).toBe('dict')
    })
  })
})

// ========== hasCommand ==========

describe('hasCommand', () => {
  const list = [
    { name: '原神', path: 'C:\\launcher.exe', type: 'app' },
    { name: '米哈游启动器', path: 'C:\\launcher.exe', type: 'app' },
    { name: '翻译', path: '/plugins/translate', type: 'plugin', featureCode: 'translate' }
  ]

  it('应找到匹配 name + path 的非插件项', () => {
    expect(hasCommand(list, 'C:\\launcher.exe', undefined, '原神')).toBe(true)
  })

  it('应区分同路径不同名的应用', () => {
    expect(hasCommand(list, 'C:\\launcher.exe', undefined, '米哈游启动器')).toBe(true)
    expect(hasCommand(list, 'C:\\launcher.exe', undefined, '不存在')).toBe(false)
  })

  it('应找到匹配 path + featureCode 的插件项', () => {
    expect(hasCommand(list, '/plugins/translate', 'translate')).toBe(true)
    expect(hasCommand(list, '/plugins/translate', 'nonexistent')).toBe(false)
  })

  describe('旧数据兼容（name 缺失）', () => {
    it('未传 name 时应降级为仅匹配 path', () => {
      expect(hasCommand(list, 'C:\\launcher.exe')).toBe(true)
    })

    it('未传 name 时对不存在的 path 应返回 false', () => {
      expect(hasCommand(list, 'C:\\nonexistent.exe')).toBe(false)
    })
  })

  it('列表为空时应返回 false', () => {
    expect(hasCommand([], 'any', undefined, 'any')).toBe(false)
  })
})
