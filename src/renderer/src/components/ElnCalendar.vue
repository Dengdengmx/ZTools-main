<template>
  <div class="eln-view">
    
    <div class="view-header">
      <h2>📓 实验记录 (ELN)</h2>
      <button class="btn-create" @click="createNewLog">+ 新建实验 (Protocol)</button>
    </div>
    
    <div class="split-layout">
      <div class="calendar-section card">
        <div class="month-header">
          <button class="icon-btn">◀</button>
          <h3>2026年 3月</h3>
          <button class="icon-btn">▶</button>
        </div>
        <div class="weekdays">
          <span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span>
        </div>
        <div class="days-grid">
          <div class="day empty" v-for="n in 6" :key="'empty'+n"></div>
          <div class="day" v-for="day in 31" :key="day" :class="{ 'active': selectedDay === day, 'has-log': hasLog(day) }" @click="selectedDay = day">
            <span class="date-num">{{ day }}</span>
            <div class="dots" v-if="hasLog(day)"><span class="dot"></span></div>
          </div>
        </div>
      </div>
      
      <div class="logs-section card">
        <h3>📅 3月{{ selectedDay }}日 的实验流</h3>
        <div v-if="loading" class="empty-state">正在呼叫 127.0.0.1:8080 获取数据...</div>
        <div v-else-if="currentLogs.length === 0" class="empty-state">无实验记录，去休息一下或者喝杯咖啡吧 ☕</div>
        <ul v-else class="log-list">
          <li v-for="log in currentLogs" :key="log.id" class="log-item">
            <div class="log-info"><span class="log-id">[{{ log.id }}]</span><span class="log-title">{{ log.title }}</span></div>
            <span class="status-badge" :class="log.status">{{ log.status }}</span>
          </li>
        </ul>
      </div>
    </div> <div v-if="showPrompt" class="modal-overlay">
      <div class="modal-content card fade-in">
        <h3>✨ 新建实验记录 (3月{{ selectedDay }}日)</h3>
        <input 
          v-model="newLogTitle" 
          class="input-dark" 
          placeholder="输入实验标题 (例如: 诱导表达重组蛋白)" 
          @keyup.enter="confirmCreate" 
          autofocus
        />
        <div class="modal-actions">
          <button class="btn-cancel" @click="showPrompt = false">取消</button>
          <button class="btn-primary" @click="confirmCreate">确认创建</button>
        </div>
      </div>
    </div>
    
  </div> </template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
const selectedDay = ref(30)
const loading = ref(true)
const logs = ref<any[]>([])

const fetchLogs = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/eln/recent')
    const data = await res.json()
    if (data.code === 200) logs.value = data.data
  } catch (e) {
    console.error("引擎未连接", e)
  } finally {
    loading.value = false
  }
}

const hasLog = (day: number) => {
  const dayStr = day < 10 ? `0${day}` : `${day}`
  return logs.value.some(log => log.date.endsWith(`-${dayStr}`))
}

const currentLogs = computed(() => {
  const dayStr = selectedDay.value < 10 ? `0${selectedDay.value}` : `${selectedDay.value}`
  return logs.value.filter(log => log.date.endsWith(`-${dayStr}`))
})

// ... 保持原有的 fetchLogs 等代码 ...

// ... 原有的 import 保持不变 ...
const showPrompt = ref(false)
const newLogTitle = ref('')

// 1. 点击按钮时，只负责呼出弹窗
const createNewLog = () => {
  newLogTitle.value = ''
  showPrompt.value = true
}

// 2. 确认创建时，真正发送给 Python 后端
const confirmCreate = async () => {
  if (!newLogTitle.value.trim()) return // 防空输入

  const dayStr = selectedDay.value < 10 ? `0${selectedDay.value}` : `${selectedDay.value}`
  const dateStr = `2026-03-${dayStr}`

  try {
    const res = await fetch('http://127.0.0.1:8080/api/eln/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newLogTitle.value, date: dateStr, status: '进行中' })
    })
    
    if (res.ok) {
      showPrompt.value = false // 关闭弹窗
      fetchLogs() // 刷新列表！
    }
  } catch (e) {
    console.error("引擎未连接", e)
  }
}

onMounted(() => fetchLogs())
</script>

<style scoped>
.eln-view { display: flex; flex-direction: column; gap: 20px; height: 100%; }
.view-header { display: flex; justify-content: space-between; align-items: center; }
h2, h3 { margin: 0; color: #f5e0dc; }
.btn-create { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; }
.btn-create:hover { background: #b4befe; }
.split-layout { display: flex; gap: 20px; flex: 1; }
.card { background: #181825; border: 1px solid #313244; border-radius: 16px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
.calendar-section { flex: 1; max-width: 450px; }
.logs-section { flex: 2; display: flex; flex-direction: column; }
.month-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.icon-btn { background: none; border: none; color: #a6adc8; cursor: pointer; font-size: 18px; }
.weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; color: #6c7086; font-weight: bold; margin-bottom: 15px; }
.days-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
.day { aspect-ratio: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; border-radius: 8px; cursor: pointer; transition: all 0.2s; background: #1e1e2e; border: 1px solid transparent; }
.day.empty { background: transparent; cursor: default; }
.day:not(.empty):hover { border-color: #45475a; }
.day.active { background: rgba(137, 180, 250, 0.15); border-color: #89b4fa; color: #89b4fa; font-weight: bold; transform: scale(1.05); }
.dots { margin-top: 4px; height: 6px; }
.dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #a6e3a1; box-shadow: 0 0 5px #a6e3a1; }
.empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: #6c7086; font-style: italic; }
.log-list { list-style: none; padding: 0; margin-top: 20px; display: flex; flex-direction: column; gap: 12px; }
.log-item { display: flex; justify-content: space-between; align-items: center; background: #1e1e2e; padding: 15px 20px; border-radius: 8px; border-left: 4px solid #89b4fa; }
.log-info { display: flex; gap: 15px; align-items: center; }
.log-id { color: #6c7086; font-family: monospace; }
.log-title { color: #cdd6f4; font-weight: 500; font-size: 15px; }
.status-badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold; }
/* 🚨 弹窗专属样式 */
.modal-overlay { 
  position: absolute; top: 0; left: 0; right: 0; bottom: 0; 
  background: rgba(17, 17, 27, 0.8); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; z-index: 100; 
}
.modal-content { width: 400px; display: flex; flex-direction: column; gap: 20px; }
.input-dark { 
  background: #11111b; border: 1px solid #313244; color: #cdd6f4; 
  padding: 12px 15px; border-radius: 8px; font-size: 15px; outline: none; 
}
.input-dark:focus { border-color: #89b4fa; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.btn-cancel { 
  background: transparent; color: #a6adc8; border: 1px solid #45475a; 
  padding: 10px 20px; border-radius: 8px; cursor: pointer; transition: 0.2s;
}
.btn-cancel:hover { background: #313244; color: #cdd6f4; }
</style>