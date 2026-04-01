<template>
  <div class="sample-hub-view">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 @click="navTo(0)" :class="{ active: currentLevel === 0 }">🧪 物理样本库</h2>
        <template v-if="currentLevel > 0">
          <span class="separator">/</span>
          <h2 @click="navTo(1)" :class="{ active: currentLevel === 1 }">{{ currentEq?.name }}</h2>
        </template>
        <template v-if="currentLevel > 2">
          <span class="separator">/</span>
          <h2 class="active">{{ currentContainer?.name }}</h2>
        </template>
      </div>
      <div class="header-actions">
        <button v-if="currentLevel === 1" class="btn-outline" :class="{ 'is-editing': isEditMode }" @click="toggleEditMode">
          {{ isEditMode ? '💾 保存并退出蓝图' : '📐 进入蓝图建造模式' }}
        </button>
        <button class="btn-primary" @click="fetchTopology">🔄 同步数据</button>
      </div>
    </div>

    <div class="equipments-grid" v-if="currentLevel === 0">
      <div v-for="(eq, id) in equipments" :key="id" class="card eq-card fade-in" @click="enterEquipment(id as string, eq)">
        <div class="eq-header">
          <div class="eq-icon-wrapper"><span class="eq-icon">{{ getIcon(eq.icon) }}</span></div>
          <div class="eq-title">
            <h3>{{ eq.name }}</h3>
            <div class="eq-status"><span class="status-dot"></span> 传感器在线</div>
          </div>
        </div>
        <p class="eq-desc">{{ eq.desc }}</p>
        <div class="eq-capacity">
          <div class="capacity-labels"><span>物理空间负载</span><span>{{ Object.keys(eq.containers || {}).length }} / {{ eq.rows * eq.cols }} 容器</span></div>
          <div class="progress-track"><div class="progress-fill" :style="{ width: `${Math.min(100, (Object.keys(eq.containers || {}).length / (eq.rows * eq.cols)) * 100)}%` }"></div></div>
        </div>
        <div class="eq-footer">
          <span class="tag warning" v-if="['equip_drawer', 'equip_chromatography', 'equip_fridge_4_20', 'equip_fridge_80'].includes(id as string)">🔒 系统常驻</span>
          <span class="tag">网格: {{ eq.rows }}x{{ eq.cols }}</span>
        </div>
      </div>
    </div>

    <div class="containers-view fade-in" v-else-if="currentLevel === 1">
      <div v-if="!isEditMode">
        <div class="action-bar"><h3>📦 {{ currentEq?.name }} 内部容器</h3></div>
        <div class="empty-state" v-if="!currentEq?.containers || Object.keys(currentEq.containers).length === 0">
          <div class="i-z-plugin empty-icon" style="font-size: 48px;"></div>
          <div class="empty-text">该设备是空的</div>
          <div class="empty-hint">点击右上角"进入蓝图建造模式"来布置柜体和抽屉。</div>
        </div>
        <div class="containers-grid" v-else>
          <div v-for="(cont, cid) in currentEq?.containers" :key="cid" class="card cont-card fade-in" @click="enterContainer(cid as string, cont)">
            <div class="cont-icon">🍱</div>
            <div class="cont-details">
              <div class="cont-name">{{ cont.name }}</div>
              <div class="cont-location">位置: R{{ cont.r + 1 }}, C{{ cont.c + 1 }} | 类型: {{ cont.type }}</div>
            </div>
            <div class="cont-arrow">➔</div>
          </div>
        </div>
      </div>

      <div v-else class="blueprint-editor fade-in">
        <div class="editor-sidebar card">
          <h3>🛠️ 空间工具箱</h3>
          <p class="help-text">1. 拖拽右侧容器可移动位置<br>2. 点击容器可调整尺寸</p>
          <button class="btn-primary w-full" @click="triggerAddContainer" style="margin-bottom: 20px;">+ 划拨新容器</button>
          <div v-if="editingContId" class="resize-panel fade-in">
            <h4>调节 "{{ currentEq.containers[editingContId].name }}"</h4>
            <div class="size-controls">
              <div class="control-row"><label>宽度</label><button class="icon-btn" @click="resizeContainer(editingContId, 0, -1)">-</button><span>{{ currentEq.containers[editingContId].cs }}</span><button class="icon-btn" @click="resizeContainer(editingContId, 0, 1)">+</button></div>
              <div class="control-row"><label>高度</label><button class="icon-btn" @click="resizeContainer(editingContId, -1, 0)">-</button><span>{{ currentEq.containers[editingContId].rs }}</span><button class="icon-btn" @click="resizeContainer(editingContId, 1, 0)">+</button></div>
            </div>
            <button class="btn-danger w-full" @click="deleteContainer(editingContId)" style="margin-top: 15px;">🗑️ 拆除该容器</button>
          </div>
        </div>

        <div class="editor-workspace card">
          <div class="cabinet-frame">
            <div class="cabinet-title">柜体正面视图 ({{ currentEq.rows }}x{{ currentEq.cols }})</div>
            <div class="cabinet-grid" :style="{ gridTemplateRows: `repeat(${currentEq.rows}, 1fr)`, gridTemplateColumns: `repeat(${currentEq.cols}, 1fr)` }">
              <div v-for="i in (currentEq.rows * currentEq.cols)" :key="'bg'+i" class="grid-dropzone" @dragover.prevent @dragenter.prevent="dragHoverIndex = i" @dragleave.prevent="dragHoverIndex = null" @drop="onDrop(i)" :class="{ 'drag-hover': dragHoverIndex === i }"></div>
              <div v-for="(cont, cid) in currentEq?.containers" :key="cid" class="draggable-cont" :class="{ 'is-selected': editingContId === cid }" :style="{ gridRow: `${cont.r + 1} / span ${cont.rs}`, gridColumn: `${cont.c + 1} / span ${cont.cs}` }" draggable="true" @dragstart="onDragStart($event, cid as string)" @click="editingContId = cid as string">
                <div class="cont-label">{{ cont.name }}</div>
                <div class="cont-size-badge">{{ cont.type }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="wells-view fade-in" v-else-if="currentLevel === 2">
       <div class="split-layout">
        <div class="grid-container card">
           <div class="grid-header">
             <h3>{{ currentContainer?.name }}</h3>
             <div style="display: flex; gap: 10px;">
               <span class="tag">规格: {{ currentContainer?.type || '标准布局' }}</span>
               <button class="btn-primary" @click="autoAddSample" style="padding: 4px 12px; font-size: 13px;">➕ 自动分配空位入库</button>
             </div>
           </div>
           
           <div class="freeform-board" v-if="currentContainer?.type === 'freeform' || currentContainer?.type === 'rack'" style="width: 100%; max-width: 550px;">
              <div class="empty-state" v-if="Object.keys(boxData).length === 0">
                <div class="i-z-plugin empty-icon" style="font-size: 32px; margin-bottom: 10px;"></div>
                <div class="empty-hint">这是一个散装大容量区域，无固定孔位。</div>
                <div class="empty-hint">请点击右上角的“自动分配空位入库”来存入资产。</div>
              </div>
              <div v-for="(item, key) in boxData" :key="key" class="freeform-item card fade-in" style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; padding: 15px; border: 1px solid #313244; background: #181825;">
                 <div>
                   <span class="tag" :class="getSampleColorClass(item)">{{ item.type || '未知' }}</span>
                   <strong style="margin-left: 10px; color: #cdd6f4;">{{ item.name }}</strong>
                   <div style="font-size: 12px; color: #6c7086; margin-top: 8px;">余量: {{ item.vol }}{{ item.unit }} | 所有人: {{ item.owner }} | 系统编码: {{ key }}</div>
                 </div>
                 <button class="btn-danger" @click="selectedWell = key as string; removeSample()">📤 取出</button>
              </div>
           </div>

           <div class="well-board" v-else :style="{ gridTemplateColumns: `repeat(${gridInfo.cols}, 1fr)` }">
              <div v-for="wid in gridInfo.cells" :key="wid" 
                   class="well-cell square" 
                   :class="[getWellStatus(wid), getSampleColorClass(boxData[wid]), { 'selected': selectedWell === wid }]" 
                   @click="selectWell(wid)">
                <span v-if="boxData[wid]?.ft >= 5" class="warn-icon" title="冻融次数过多">⚠️</span>
                {{ boxData[wid]?.name ? boxData[wid].name.substring(0,3) : wid }}
              </div>
           </div>
        </div>

        <div class="panel-container card" v-if="currentContainer?.type !== 'freeform' && currentContainer?.type !== 'rack'">
          <h3>资产参数</h3>
          <div v-if="!selectedWell" class="empty-state">
            <div class="empty-hint" style="margin-top: 40px;">请在左侧点击一个<br><b>空位</b>：直接存入资产<br><b>已有物</b>：查看详情</div>
          </div>
          <div v-else class="sample-info fade-in">
            <div class="info-group"><label>孔位</label><div class="value highlight">[{{ selectedWell }}]</div></div>
            <div class="info-group"><label>状态</label><div class="value" :class="getWellStatus(selectedWell) === 'empty' ? '' : 'success'">{{ getWellStatus(selectedWell) === 'empty' ? '空闲' : '已存入' }}</div></div>
            <template v-if="getWellStatus(selectedWell) !== 'empty'">
              <div class="info-group"><label>名称</label><div class="value">{{ boxData[selectedWell]?.name || '未知资产' }}</div></div>
              <div class="info-group"><label>大类</label><div class="value">{{ boxData[selectedWell]?.type || '未知' }}</div></div>
              <div class="info-group"><label>余量</label><div class="value">{{ boxData[selectedWell]?.vol || 0 }} {{ boxData[selectedWell]?.unit || 'μL' }}</div></div>
              <div class="info-group"><label>冻融(F/T)</label><div class="value" :class="boxData[selectedWell]?.ft >= 5 ? 'id-value' : ''">{{ boxData[selectedWell]?.ft || 0 }} 次</div></div>
              <div class="info-group"><label>所有人</label><div class="value" style="font-size:12px;">{{ boxData[selectedWell]?.owner || '-' }}</div></div>
              <div class="info-group" style="flex-direction: column; align-items: flex-start; border: none; padding-top: 20px;">
                 <label style="margin-bottom: 5px;">存入时间</label>
                 <div style="font-size: 11px; color: #a6adc8; width: 100%;">{{ boxData[selectedWell]?.deposit_time || '-' }}</div>
              </div>
            </template>
            <div class="actions-group">
              <button class="btn-danger w-full" v-if="getWellStatus(selectedWell) !== 'empty'" @click="removeSample">📤 出库此样本</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showContainerForm" class="modal-overlay fade-in">
      <div class="modal-content card" style="width: 380px;">
        <h3 style="margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 10px; color:#cdd6f4;">📦 划拨新容器</h3>
        <div class="form-group"><label>容器名称</label><input v-model="containerForm.name" class="input-dark"></div>
        <div class="form-group"><label>容器大类</label>
          <select v-model="containerForm.category" class="input-dark">
            <option value="rack">🧊 标准冻存架 (含多个抽屉/盒子)</option>
            <option value="box">📦 独立标准方格冻存盒</option>
            <option value="holder">🧫 独立试管架 / 离心管架</option>
            <option value="freeform">📥 自由散装大抽屉 (可跨格且可嵌套)</option>
          </select>
        </div>
        <div class="form-group" v-if="containerForm.category === 'rack'"><label>内部规格 (层 x 盒)</label><select v-model="containerForm.subSpec" class="input-dark"><option value="5x4">5层 × 每层4盒</option><option value="4x4">4层 × 每层4盒</option></select></div>
        <div class="form-group" v-if="containerForm.category === 'box'"><label>内部规格 (孔位数)</label><select v-model="containerForm.subSpec" class="input-dark"><option value="9x9">9x9 (81孔标准盒)</option><option value="10x10">10x10 (100孔密集盒)</option></select></div>
        <div class="form-group" v-if="containerForm.category === 'holder'"><label>内部规格 (孔位数)</label><select v-model="containerForm.subSpec" class="input-dark"><option value="12x8">12x8 (96孔板/PCR管架)</option><option value="12x5">12x5 (60孔标准试管架)</option></select></div>
        <div class="form-group-row" v-if="containerForm.category === 'freeform'"><div class="form-group"><label>占据高(行)</label><input type="number" v-model="containerForm.rs" class="input-dark"></div><div class="form-group"><label>占据宽(列)</label><input type="number" v-model="containerForm.cs" class="input-dark"></div></div>
        <div class="modal-actions" style="margin-top: 15px;"><button class="btn-outline" @click="showContainerForm = false">取消</button><button class="btn-primary" @click="confirmAddContainer">确定上架</button></div>
      </div>
    </div>

    <div v-if="showSampleForm" class="modal-overlay fade-in">
      <div class="modal-content card" style="width: 420px;">
        <h3 style="margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 10px; color:#cdd6f4;">📥 存入标的物 (孔位 [{{ selectedWell }}])</h3>
        <div class="form-group"><label>样本名称</label><input v-model="formData.name" class="input-dark"></div>
        <div class="form-group"><label>样本大类</label>
          <select v-model="formData.type" class="input-dark">
            <option>🧬 质粒 (Plasmid)</option>
            <option>🧪 蛋白 (Protein)</option>
            <option>🧫 细胞 (Cell)</option>
            <option>💧 核酸 (DNA/RNA)</option>
            <option>📦 其他耗材</option>
          </select>
        </div>
        <div class="form-group-row"><div class="form-group"><label>余量</label><input type="number" v-model="formData.vol" class="input-dark"></div><div class="form-group"><label>单位</label><select v-model="formData.unit" class="input-dark"><option>μL</option><option>mL</option><option>管</option><option>盒</option></select></div><div class="form-group"><label>冻融次数</label><input type="number" v-model="formData.ft" class="input-dark"></div></div>
        <div class="form-group"><label>所有人</label><input v-model="formData.owner" class="input-dark"></div>
        <div class="form-group"><label>备注</label><input v-model="formData.notes" class="input-dark" placeholder="选填..."></div>
        <div class="modal-actions" style="margin-top: 15px;"><button class="btn-outline" @click="showSampleForm = false">取消</button><button class="btn-primary" @click="confirmSaveSample">确认入库</button></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

const currentLevel = ref(0)
const equipments = ref<Record<string, any>>({})
const currentEqId = ref('')
const currentEq = ref<any>(null)
const currentContId = ref('')
const currentContainer = ref<any>(null)
const selectedWell = ref<string | null>(null)
const boxData = ref<Record<string, any>>({}) 

const showSampleForm = ref(false)
const formData = ref({ name: '', type: '🧬 质粒 (Plasmid)', vol: 100, unit: 'μL', ft: 0, owner: 'Admin', notes: '' })

const showContainerForm = ref(false)
const containerForm = ref({ name: '', category: 'box', subSpec: '10x10', rs: 1, cs: 1 })

const isEditMode = ref(false)
const draggedContId = ref<string | null>(null)
const dragHoverIndex = ref<number | null>(null)
const editingContId = ref<string | null>(null)

const getSampleColorClass = (item: any) => {
  if (!item) return ''
  if (item.type?.includes('蛋白')) return 'bg-protein'
  if (item.type?.includes('质粒')) return 'bg-plasmid'
  if (item.type?.includes('细胞')) return 'bg-cell'
  return 'bg-default'
}

const getIcon = (iconName: string) => { return { 'folder': '📁', 'tiles': '🧊', 'calendar': '🌡️', 'snowflake': '❄️' }[iconName] || '🗄️' }

const navTo = (level: number) => { 
  if (level <= currentLevel.value) { currentLevel.value = level; isEditMode.value = false; }
}

const fetchTopology = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/topology')
    const json = await res.json()
    if (json.code === 200) equipments.value = json.data
  } catch (e) { console.error("网络故障") }
}

const enterEquipment = (id: string, eq: any) => {
  currentEqId.value = id; currentEq.value = eq; currentLevel.value = 1;
}

const toggleEditMode = () => { isEditMode.value = !isEditMode.value; editingContId.value = null; if (!isEditMode.value) fetchTopology(); }

const onDragStart = (e: DragEvent, cid: string) => { draggedContId.value = cid; editingContId.value = cid; if (e.dataTransfer) { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', cid) } }

const onDrop = async (cellIndex: number) => {
  dragHoverIndex.value = null; if (!draggedContId.value || !currentEq.value) return
  const c = (cellIndex - 1) % currentEq.value.cols, r = Math.floor((cellIndex - 1) / currentEq.value.cols)
  currentEq.value.containers[draggedContId.value].r = r; currentEq.value.containers[draggedContId.value].c = c
  try { await fetch('http://127.0.0.1:8080/api/samples/container/move', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equip_id: currentEqId.value, cid: draggedContId.value, r, c }) }) } catch (e) {}
  draggedContId.value = null
}

const resizeContainer = async (cid: string, dRow: number, dCol: number) => {
  const cont = currentEq.value.containers[cid]
  const newRs = Math.max(1, cont.rs + dRow), newCs = Math.max(1, cont.cs + dCol)
  if (cont.r + newRs > currentEq.value.rows || cont.c + newCs > currentEq.value.cols) return
  cont.rs = newRs; cont.cs = newCs
  try { await fetch('http://127.0.0.1:8080/api/samples/container/resize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equip_id: currentEqId.value, cid, d_row: dRow, d_col: dCol }) }) } catch (e) {}
}

const triggerAddContainer = () => {
  containerForm.value = { name: '新建容器 ' + Math.floor(Math.random() * 100), category: 'box', subSpec: '10x10', rs: 1, cs: 1 }; showContainerForm.value = true
}

const confirmAddContainer = async () => {
  if (!containerForm.value.name.trim()) return
  let payload: any = { equip_id: currentEqId.value, name: containerForm.value.name, type: 'freeform', rs: 1, cs: 1 }
  if (containerForm.value.category === 'rack') {
     payload.type = 'rack'; let parts = containerForm.value.subSpec.split('x'); payload.layers = parseInt(parts[0]); payload.boxes = parseInt(parts[1])
  } else if (containerForm.value.category === 'box' || containerForm.value.category === 'holder') {
     payload.type = containerForm.value.subSpec
  } else { payload.type = 'freeform'; payload.rs = containerForm.value.rs; payload.cs = containerForm.value.cs }

  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/container/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    const json = await res.json()
    if (json.code === 200) { await fetchTopology(); currentEq.value = equipments.value[currentEqId.value]; editingContId.value = json.data.cid; showContainerForm.value = false }
  } catch (e) {}
}

const deleteContainer = async (cid: string) => {
  if (window.confirm("确定要拆除此容器吗？其内部样本将丢失！")) {
    try {
      const res = await fetch(`http://127.0.0.1:8080/api/samples/container/delete?equip_id=${currentEqId.value}&cid=${cid}`, { method: 'POST' })
      if ((await res.json()).code === 200) { delete currentEq.value.containers[cid]; editingContId.value = null }
    } catch (e) {}
  }
}

const enterContainer = async (cid: string, cont: any) => { 
  currentContId.value = cid; currentContainer.value = cont; currentLevel.value = 2; selectedWell.value = null
  const path = `${currentEqId.value}/${cid}`
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(path)}`)
    const json = await res.json()
    if (json.code === 200) boxData.value = json.data || {}
  } catch (e) { console.error("读取容器数据失败") }
}

const gridInfo = computed(() => {
  const type = currentContainer.value?.type || '10x10'
  let rows: string[] = [], cols = 0
  if (type === '10x10') { rows = ['A','B','C','D','E','F','G','H','I','J']; cols = 10 }
  else if (type === '9x9') { rows = ['A','B','C','D','E','F','G','H','I']; cols = 9 }
  else if (type === '12x8') { rows = ['A','B','C','D','E','F','G','H']; cols = 12 }
  else if (type === '12x5') { rows = ['A','B','C','D','E']; cols = 12 }
  else return { rows: [], cols: 0, cells: [] } 
  let cells: string[] = []
  for (let r of rows) { for (let c = 1; c <= cols; c++) cells.push(`${r}${c}`) }
  return { rows, cols, cells }
})

const getWellStatus = (wid: string) => { return boxData.value[wid] ? 'filled' : 'empty' }

// 🚨 交互优化核心：选定孔位，如果是空的直接触发填表！
const selectWell = (wid: string) => { 
  selectedWell.value = wid 
  if (getWellStatus(wid) === 'empty') triggerAddSample()
}

// 🚨 新增：一键自动找空位功能
const autoAddSample = () => {
   if (currentContainer.value?.type === 'freeform' || currentContainer.value?.type === 'rack') {
      const keys = Object.keys(boxData.value).filter(k => k.startsWith('F-'))
      selectedWell.value = `F-${keys.length + 1}` // 自动生成散装流水号
      triggerAddSample()
   } else {
      const firstEmpty = gridInfo.value.cells.find(wid => !boxData.value[wid])
      if (firstEmpty) {
         selectedWell.value = firstEmpty
         triggerAddSample()
      } else { alert("⚠️ 当前容器已满，无法放入更多样本！") }
   }
}

const triggerAddSample = () => {
  if (!selectedWell.value) return
  formData.value = { name: '', type: '🧬 质粒 (Plasmid)', vol: 100, unit: 'μL', ft: 0, owner: 'Admin', notes: '' }
  showSampleForm.value = true
}

const confirmSaveSample = async () => {
  if (!formData.value.name) { alert("请输入样本名称"); return }
  const path = `${currentEqId.value}/${currentContId.value}`
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/add', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        box_id: path, well_index: selectedWell.value, sample_name: formData.value.name,
        sample_type: formData.value.type, vol: formData.value.vol, unit: formData.value.unit,
        ft_count: formData.value.ft, owner: formData.value.owner, notes: formData.value.notes
      })
    })
    if (res.ok) { boxData.value[selectedWell.value as string] = { ...formData.value }; showSampleForm.value = false }
  } catch (e) {}
}

const removeSample = async () => { 
  if (!selectedWell.value || !window.confirm(`确认取出 [${boxData.value[selectedWell.value].name}] 吗？`)) return
  const path = `${currentEqId.value}/${currentContId.value}`
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/remove?box_id=${encodeURIComponent(path)}&well_index=${selectedWell.value}`, { method: 'POST' })
    if (res.ok) { delete boxData.value[selectedWell.value]; selectedWell.value = null }
  } catch (e) {}
}

onMounted(() => fetchTopology())
</script>

<style scoped>
/* (由于篇幅限制，保留你原有的 CSS 即可，以下为补充核心样式) */
.sample-hub-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4;}
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.containers-view, .wells-view { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086; cursor: pointer; transition: 0.2s;}
.breadcrumbs h2:hover { color: #b4befe;}
.breadcrumbs h2.active { color: #89b4fa; font-weight: bold;}
.separator { color: #45475a; font-weight: bold;}
.header-actions { display: flex; gap: 10px;}
.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0;}
.btn-outline { background: transparent; color: #a6adc8; border: 1px dashed #45475a; padding: 8px 15px; border-radius: 8px; cursor: pointer; transition: 0.2s; flex-shrink: 0;}
.btn-outline.is-editing { border-color: #a6e3a1; color: #a6e3a1; background: rgba(166, 227, 161, 0.1);}
.btn-danger { background: rgba(243, 139, 168, 0.1); color: #f38ba8; border: 1px solid #f38ba8; padding: 8px 15px; border-radius: 6px; cursor: pointer; transition: 0.2s;}
.w-full { width: 100%; }

.equipments-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); grid-auto-rows: max-content; gap: 18px; overflow-y: auto; flex: 1; min-height: 0; padding: 5px 5px 20px 5px; }
.eq-card { display: flex; flex-direction: column; padding: 20px; background: #181825; border: 1px solid #313244; border-radius: 12px; cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);}
.eq-card:hover { border-color: #89b4fa; transform: translateY(-4px); box-shadow: 0 12px 25px rgba(0,0,0,0.3);}
.eq-header { display: flex; align-items: center; margin-bottom: 12px; }
.eq-icon-wrapper { font-size: 26px; background: #11111b; border: 1px solid #313244; border-radius: 50%; margin-right: 15px; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;}
.eq-title h3 { margin: 0 0 6px 0; font-size: 16px; color: #cdd6f4; font-weight: bold;}
.eq-status { font-size: 11px; color: #a6e3a1; display: flex; align-items: center; gap: 6px; }
.status-dot { width: 6px; height: 6px; background: #a6e3a1; border-radius: 50%; box-shadow: 0 0 6px #a6e3a1; animation: pulse 2s infinite;}
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
.eq-desc { font-size: 12px; color: #6c7086; line-height: 1.5; margin: 0 0 18px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.eq-capacity { background: #11111b; padding: 12px; border-radius: 8px; border: 1px solid #313244; margin-bottom: 15px;}
.capacity-labels { display: flex; justify-content: space-between; font-size: 11px; color: #a6adc8; margin-bottom: 8px; font-weight: bold;}
.progress-track { width: 100%; height: 6px; background: #313244; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #89b4fa, #cba6f7); transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1); }
.eq-footer { display: flex; gap: 8px; margin-top: auto; flex-wrap: wrap;}

.action-bar { margin-bottom: 20px; flex-shrink: 0;}
.action-bar h3 { margin: 0; color: #bac2de;}
.containers-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; overflow-y: auto; padding-bottom: 20px;}
.cont-card { display: flex; align-items: center; padding: 15px 20px; background: #181825; border: 1px solid #313244; border-radius: 10px; cursor: pointer; transition: 0.2s;}
.cont-card:hover { border-color: #89b4fa; background: #1e1e2e;}
.cont-icon { font-size: 28px; margin-right: 15px;}
.cont-name { font-weight: bold; font-size: 16px; color: #cdd6f4; margin-bottom: 4px;}
.cont-location { font-size: 12px; color: #6c7086;}

.blueprint-editor { display: flex; gap: 20px; flex: 1; min-height: 0;}
.editor-sidebar { flex: 1; max-width: 300px; background: #181825; padding: 20px; border-radius: 12px; border: 1px solid #313244; overflow-y: auto;}
.editor-sidebar h3 { margin-top: 0; color: #a6e3a1; border-bottom: 1px solid #313244; padding-bottom: 10px;}
.help-text { font-size: 13px; color: #6c7086; margin-bottom: 20px; line-height: 1.6;}
.resize-panel { background: #11111b; padding: 15px; border-radius: 8px; border: 1px solid #45475a;}
.resize-panel h4 { margin: 0 0 15px 0; color: #f9e2af; font-size: 14px;}
.size-controls { display: flex; flex-direction: column; gap: 10px;}
.control-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #bac2de;}
.icon-btn { background: #313244; color: #cdd6f4; border: none; width: 28px; height: 28px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.icon-btn:hover { background: #89b4fa; color: #11111b;}
.editor-workspace { flex: 3; background: #11111b; padding: 30px; border-radius: 12px; border: 1px solid #313244; display: flex; flex-direction: column; align-items: center; overflow-y: auto;}
.cabinet-frame { width: 100%; max-width: 800px; background: #1e1e2e; padding: 20px; border-radius: 12px; border: 4px solid #45475a; box-shadow: inset 0 0 30px rgba(0,0,0,0.5); flex-shrink: 0; margin-bottom: 20px;}
.cabinet-title { text-align: center; color: #6c7086; font-weight: bold; margin-bottom: 20px; letter-spacing: 2px;}
.cabinet-grid { display: grid; position: relative; gap: 6px; background: #11111b; padding: 6px; border-radius: 8px; min-height: 400px;}
.grid-dropzone { background: rgba(49, 50, 68, 0.4); border: 1px dashed #45475a; border-radius: 6px; min-height: 80px; transition: all 0.2s;}
.grid-dropzone.drag-hover { background: rgba(166, 227, 161, 0.2); border-color: #a6e3a1; transform: scale(0.95);}
.draggable-cont { background: rgba(137, 180, 250, 0.2); border: 2px solid #89b4fa; border-radius: 8px; cursor: grab; display: flex; flex-direction: column; align-items: center; justify-content: center; backdrop-filter: blur(4px); transition: box-shadow 0.2s, border-color 0.2s; z-index: 10;}
.draggable-cont:active { cursor: grabbing;}
.draggable-cont.is-selected { border-color: #f9e2af; box-shadow: 0 0 15px rgba(249, 226, 175, 0.3); background: rgba(249, 226, 175, 0.15);}
.cont-label { font-weight: bold; color: #cdd6f4; font-size: 14px; text-shadow: 0 1px 2px #000; text-align: center; padding: 0 10px;}
.cont-size-badge { font-size: 11px; background: rgba(17,17,27,0.8); color: #a6adc8; padding: 2px 8px; border-radius: 10px; margin-top: 5px;}

.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}
.grid-container { flex: 2; background: #11111b; padding: 25px; border-radius: 12px; border: 1px solid #313244; display: flex; flex-direction: column; align-items: center; overflow-y: auto;}
.grid-header { display: flex; justify-content: space-between; align-items: center; width: 100%; max-width: 550px; margin-bottom: 15px; flex-shrink: 0;}
.grid-header h3 { margin: 0; color: #cdd6f4;}
.well-board { display: grid; gap: 8px; width: 100%; max-width: 550px; padding-bottom: 20px;}
.well-cell.square { background: #181825; aspect-ratio: 1; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 13px; color: #6c7086; cursor: pointer; transition: all 0.2s ease; border: 1px solid #313244;}
.well-cell.square:hover { border-color: #89b4fa; background: #1e1e2e; color: #bac2de;}
.well-cell.square.selected { border-color: #f9e2af; background: rgba(249, 226, 175, 0.1); color: #f9e2af; box-shadow: 0 0 12px rgba(249,226,175,0.2); transform: scale(1.05);}
.well-cell.square.filled { background: #89b4fa; color: #11111b; font-weight: bold; border-color: #89b4fa;}

.panel-container { flex: 1; max-width: 350px; background: #181825; padding: 20px; border-radius: 12px; border: 1px solid #313244; overflow-y: auto;}
.panel-container h3 { margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 15px;}
.info-group { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px dashed #313244;}
.info-group:last-of-type { border-bottom: none;}
.info-group label { color: #a6adc8; font-weight: bold;}
.value { font-family: monospace; padding: 4px 10px; border-radius: 6px; font-weight: bold; background: #11111b;}
.value.highlight { color: #f9e2af; font-size: 16px;}
.value.success { background: rgba(166, 227, 161, 0.1); color: #a6e3a1;}
.value.id-value { color: #f38ba8; font-size: 12px;}
.actions-group { margin-top: 30px;}
.empty-state { text-align: center; padding: 40px 20px;}
.empty-text { font-size: 18px; color: #cdd6f4; font-weight: bold; margin-bottom: 8px;}
.empty-hint { color: #6c7086; font-size: 14px;}
.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

.well-cell.bg-protein { background: rgba(166, 227, 161, 0.2); border-color: #a6e3a1; color: #a6e3a1; font-weight: bold; }
.well-cell.bg-plasmid { background: rgba(243, 139, 168, 0.2); border-color: #f38ba8; color: #fab387; font-weight: bold; }
.well-cell.bg-cell { background: rgba(203, 166, 247, 0.2); border-color: #cba6f7; color: #cba6f7; font-weight: bold; }
.well-cell.bg-default { background: rgba(137, 180, 250, 0.2); border-color: #89b4fa; color: #89b4fa; font-weight: bold; }
.warn-icon { position: absolute; top: -5px; right: -5px; font-size: 10px; z-index: 2; }
.modal-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(17, 17, 27, 0.8); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-content { display: flex; flex-direction: column; }
.form-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; flex: 1; }
.form-group-row { display: flex; gap: 15px; }
.form-group label { font-size: 12px; color: #a6adc8; font-weight: bold; }
.input-dark { background: #11111b; border: 1px solid #313244; color: #cdd6f4; padding: 10px 12px; border-radius: 6px; outline: none; transition: 0.2s;}
.input-dark:focus { border-color: #89b4fa; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>