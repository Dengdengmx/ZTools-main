<template>
  <div class="sample-hub-view">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 @click="navTo(0)" :class="{ active: currentLevel === 0 }">🧪 物理样本库</h2>
        <template v-if="currentLevel > 0"><span class="separator">/</span><h2 @click="navTo(1)" :class="{ active: currentLevel === 1 }">{{ currentEq?.name }}</h2></template>
        <template v-if="currentLevel > 2"><span class="separator">/</span><h2 class="active">{{ currentContainer?.name }}</h2></template>
      </div>
      <div class="header-actions">
        <button v-if="currentLevel === 1" class="btn-outline" :class="{ 'is-editing': isEditMode }" @click="toggleEditMode">
          {{ isEditMode ? '🔒 锁定物理布局 (点击进入容器)' : '🔓 解锁布局编辑 (允许拖拽与形变)' }}
        </button>
        <button class="btn-primary" @click="fetchTopology">🔄 同步数据</button>
      </div>
    </div>

    <div class="equipments-grid" v-if="currentLevel === 0">
      <div v-for="(eq, id) in equipments" :key="id" class="card eq-card fade-in" @click="enterEquipment(id as string, eq)">
        <div class="eq-header">
          <div class="eq-icon-wrapper"><span class="eq-icon">{{ getIcon(eq.icon) }}</span></div>
          <div class="eq-title"><h3>{{ eq.name }}</h3><div class="eq-status"><span class="status-dot"></span> 在线</div></div>
        </div>
        <p class="eq-desc">{{ eq.desc }}</p>
        <div class="eq-footer"><span class="tag">网格: {{ eq.rows }}x{{ eq.cols }}</span></div>
      </div>
    </div>

    <div class="cabinet-view-unified fade-in" v-else-if="currentLevel === 1">
      <div class="cabinet-workspace card">
        <div class="cabinet-frame" :class="{ 'edit-active': isEditMode }">
          <div class="cabinet-title">{{ currentEq.name }} - 正面物理映射 ({{ currentEq.rows }}x{{ currentEq.cols }})</div>
          <div class="cabinet-grid" :style="{ gridTemplateRows: `repeat(${currentEq.rows}, 1fr)`, gridTemplateColumns: `repeat(${currentEq.cols}, 1fr)` }">
            
            <div v-for="i in (currentEq.rows * currentEq.cols)" :key="'bg'+i" class="grid-dropzone"
                 @dragover.prevent @dragenter.prevent="isEditMode ? dragHoverIndex = i : null"
                 @dragleave.prevent="dragHoverIndex = null" @drop="isEditMode ? onDrop(i) : null"
                 :class="{ 'drag-hover': dragHoverIndex === i }"></div>
            
            <div v-for="(cont, cid) in currentEq?.containers" :key="cid" class="draggable-cont"
                 :class="{ 'is-selected': editingContId === cid, 'can-drag': isEditMode, 'can-click': !isEditMode }"
                 :style="{ gridRow: `${cont.r + 1} / span ${cont.rs}`, gridColumn: `${cont.c + 1} / span ${cont.cs}` }"
                 :draggable="isEditMode" @dragstart="isEditMode ? onDragStart($event, cid as string) : null"
                 @click="handleContainerClick(cid as string, cont)">
              <div class="cont-label">{{ cont.name }}</div>
              <div class="cont-size-badge">{{ cont.type }}</div>
            </div>

          </div>
        </div>
      </div>

      <div v-if="isEditMode" class="cabinet-sidebar card fade-in">
        <h3>🛠️ 空间工具箱</h3>
        <p class="help-text">当前处于解锁状态，您可以拖拽改变左侧容器位置，或通过下方工具划拨新空间。</p>
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
    </div>

    <div class="wells-view fade-in" v-else-if="currentLevel === 2">
       <div class="split-layout">
        <div class="grid-container card">
           <div class="grid-header">
             <h3>{{ currentContainer?.name }}</h3>
             <div style="display: flex; gap: 10px;">
               <span class="tag">规格: {{ currentContainer?.type || '标准布局' }}</span>
               <button v-if="currentContainer?.type !== 'freeform'" class="btn-primary" @click="autoAddSample" style="padding: 4px 12px; font-size: 13px;">➕ 自动分配入库</button>
             </div>
           </div>
           
           <div v-if="currentContainer?.type === 'freeform'" 
                class="freeform-canvas" 
                @dragover.prevent 
                @drop="onCanvasDrop"
                @dblclick="handleCanvasDoubleClick">
              <div class="canvas-hint" v-if="Object.keys(boxData).length === 0">这里是自由散装区<br>双击空白处放入资产，支持自由拖拽排布</div>
              
              <div v-for="(item, key) in boxData" :key="key" 
                   class="canvas-item"
                   :class="{ 'selected': selectedWell === key }"
                   :style="{ left: `${item.x || 20}px`, top: `${item.y || 20}px` }"
                   draggable="true"
                   @dragstart="onItemDragStart($event, key as string)"
                   @click.stop="selectWell(key as string)">
                <div class="item-icon" :class="getSampleColorClass(item)">{{ item.type?.includes('细胞') ? '🧫' : (item.type?.includes('蛋白') ? '🧪' : '🧬') }}</div>
                <div class="item-name">{{ item.name }}</div>
                <span v-if="item.ft >= 5" class="warn-icon">⚠️</span>
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

        <div class="panel-container card">
          <h3>资产参数</h3>
          <div v-if="!selectedWell" class="empty-state">
            <div class="empty-hint" style="margin-top: 40px;">请在左侧点击一个<br><b>空位</b>：直接存入资产<br><b>已有物</b>：查看详情</div>
          </div>
          <div v-else class="sample-info fade-in">
            <div class="info-group"><label>标识</label><div class="value highlight">[{{ selectedWell }}]</div></div>
            <div class="info-group"><label>状态</label><div class="value" :class="getWellStatus(selectedWell) === 'empty' ? '' : 'success'">{{ getWellStatus(selectedWell) === 'empty' ? '草稿/空闲' : '已入库' }}</div></div>
            <template v-if="getWellStatus(selectedWell) !== 'empty'">
              <div class="info-group"><label>名称</label><div class="value">{{ boxData[selectedWell]?.name || '未知资产' }}</div></div>
              <div class="info-group"><label>大类</label><div class="value">{{ boxData[selectedWell]?.type || '未知' }}</div></div>
              <div class="info-group"><label>余量</label><div class="value">{{ boxData[selectedWell]?.vol || 0 }} {{ boxData[selectedWell]?.unit || 'μL' }}</div></div>
              <div class="info-group"><label>所有人</label><div class="value" style="font-size:12px;">{{ boxData[selectedWell]?.owner || '-' }}</div></div>
            </template>
            <div class="actions-group">
              <button class="btn-primary w-full" v-if="getWellStatus(selectedWell) === 'empty'" @click="showSampleForm = true">📥 确认为其入库</button>
              <button class="btn-danger w-full" v-else @click="removeSample">📤 从该位置出库</button>
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
            <option value="box">📦 独立标准方格冻存盒</option>
            <option value="holder">🧫 独立试管架 / 离心管架</option>
            <option value="freeform">📥 自由散装大抽屉 (真实画布映射)</option>
          </select>
        </div>
        <div class="form-group" v-if="containerForm.category === 'box'"><label>内部规格</label><select v-model="containerForm.subSpec" class="input-dark"><option value="9x9">9x9 (81孔)</option><option value="10x10">10x10 (100孔)</option></select></div>
        <div class="form-group" v-if="containerForm.category === 'holder'"><label>内部规格</label><select v-model="containerForm.subSpec" class="input-dark"><option value="12x8">12x8 (96孔板)</option><option value="12x5">12x5 (60孔架)</option></select></div>
        <div class="form-group-row" v-if="containerForm.category === 'freeform'"><div class="form-group"><label>占据高(行)</label><input type="number" v-model="containerForm.rs" class="input-dark"></div><div class="form-group"><label>占据宽(列)</label><input type="number" v-model="containerForm.cs" class="input-dark"></div></div>
        <div class="modal-actions" style="margin-top: 15px;"><button class="btn-outline" @click="showContainerForm = false">取消</button><button class="btn-primary" @click="confirmAddContainer">确定上架</button></div>
      </div>
    </div>

    <div v-if="showSampleForm" class="modal-overlay fade-in">
      <div class="modal-content card" style="width: 420px;">
        <h3 style="margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 10px; color:#cdd6f4;">📥 存入标的物 ({{ selectedWell }})</h3>
        <div class="form-group"><label>样本名称</label><input v-model="formData.name" class="input-dark"></div>
        <div class="form-group"><label>样本大类</label>
          <select v-model="formData.type" class="input-dark">
            <option>🧬 质粒 (Plasmid)</option>
            <option>🧪 蛋白 (Protein)</option>
            <option>🧫 细胞 (Cell)</option>
          </select>
        </div>
        <div class="form-group-row"><div class="form-group"><label>余量</label><input type="number" v-model="formData.vol" class="input-dark"></div><div class="form-group"><label>单位</label><select v-model="formData.unit" class="input-dark"><option>μL</option><option>mL</option><option>管</option></select></div><div class="form-group"><label>冻融次数</label><input type="number" v-model="formData.ft" class="input-dark"></div></div>
        <div class="form-group"><label>所有人</label><input v-model="formData.owner" class="input-dark"></div>
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

// 画布相关临时状态
const dragItemKey = ref<string | null>(null)
const tempCanvasX = ref(20)
const tempCanvasY = ref(20)

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
    if (res.ok) equipments.value = (await res.json()).data
  } catch (e) { console.error("网络故障") }
}

const enterEquipment = (id: string, eq: any) => {
  currentEqId.value = id; currentEq.value = eq; currentLevel.value = 1; isEditMode.value = false;
}

const toggleEditMode = () => { isEditMode.value = !isEditMode.value; editingContId.value = null; if (!isEditMode.value) fetchTopology(); }

const handleContainerClick = (cid: string, cont: any) => {
  if (isEditMode.value) {
    editingContId.value = cid // 编辑模式下点击选中
  } else {
    enterContainer(cid, cont) // 正常模式下点击进入
  }
}

// ---- 柜体拖拽逻辑 ----
const onDragStart = (e: DragEvent, cid: string) => { draggedContId.value = cid; editingContId.value = cid; if (e.dataTransfer) { e.dataTransfer.setData('text/plain', cid) } }
const onDrop = async (cellIndex: number) => {
  dragHoverIndex.value = null; if (!draggedContId.value || !currentEq.value) return
  const c = (cellIndex - 1) % currentEq.value.cols, r = Math.floor((cellIndex - 1) / currentEq.value.cols)
  currentEq.value.containers[draggedContId.value].r = r; currentEq.value.containers[draggedContId.value].c = c
  try { await fetch('http://127.0.0.1:8080/api/samples/container/move', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equip_id: currentEqId.value, cid: draggedContId.value, r, c }) }) } catch (e) {}
  draggedContId.value = null
}

const resizeContainer = async (cid: string, dRow: number, dCol: number) => {
  const cont = currentEq.value.containers[cid]; const newRs = Math.max(1, cont.rs + dRow), newCs = Math.max(1, cont.cs + dCol)
  if (cont.r + newRs > currentEq.value.rows || cont.c + newCs > currentEq.value.cols) return
  cont.rs = newRs; cont.cs = newCs
  try { await fetch('http://127.0.0.1:8080/api/samples/container/resize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equip_id: currentEqId.value, cid, d_row: dRow, d_col: dCol }) }) } catch (e) {}
}

const triggerAddContainer = () => { containerForm.value = { name: '新容器', category: 'box', subSpec: '10x10', rs: 1, cs: 1 }; showContainerForm.value = true }
const confirmAddContainer = async () => {
  let payload: any = { equip_id: currentEqId.value, name: containerForm.value.name, type: containerForm.value.category === 'freeform' ? 'freeform' : containerForm.value.subSpec, rs: containerForm.value.rs, cs: containerForm.value.cs }
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/container/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (res.ok) { await fetchTopology(); currentEq.value = equipments.value[currentEqId.value]; showContainerForm.value = false }
  } catch (e) {}
}

const deleteContainer = async (cid: string) => {
  if (window.confirm("确定拆除此容器？")) {
    try {
      if ((await fetch(`http://127.0.0.1:8080/api/samples/container/delete?equip_id=${currentEqId.value}&cid=${cid}`, { method: 'POST' })).ok) { delete currentEq.value.containers[cid]; editingContId.value = null }
    } catch (e) {}
  }
}

// ---- 微观与画布逻辑 ----
const enterContainer = async (cid: string, cont: any) => { 
  currentContId.value = cid; currentContainer.value = cont; currentLevel.value = 2; selectedWell.value = null
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(currentEqId.value + '/' + cid)}`)
    boxData.value = (await res.json()).data || {}
  } catch (e) {}
}

const gridInfo = computed(() => {
  const t = currentContainer.value?.type || '10x10'; let r: string[] = [], c = 0
  if (t === '10x10') { r = ['A','B','C','D','E','F','G','H','I','J']; c = 10 }
  else if (t === '9x9') { r = ['A','B','C','D','E','F','G','H','I']; c = 9 }
  else if (t === '12x8') { r = ['A','B','C','D','E','F','G','H']; c = 12 }
  else if (t === '12x5') { r = ['A','B','C','D','E']; c = 12 }
  else return { rows: [], cols: 0, cells: [] } 
  let cells: string[] = []; r.forEach(row => { for (let i = 1; i <= c; i++) cells.push(`${row}${i}`) })
  return { rows: r, cols: c, cells }
})

const getWellStatus = (wid: string) => { return boxData.value[wid] ? 'filled' : 'empty' }

// 🚨 画布：双击新建样本点
const handleCanvasDoubleClick = (e: MouseEvent) => {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  tempCanvasX.value = e.clientX - rect.left - 20
  tempCanvasY.value = e.clientY - rect.top - 20
  
  // 自动生成散装流水号
  const keys = Object.keys(boxData.value).filter(k => k.startsWith('F-'))
  selectedWell.value = `F-${keys.length + 1}` 
  
  formData.value = { name: '新样本', type: '🧬 质粒 (Plasmid)', vol: 100, unit: 'μL', ft: 0, owner: 'Admin', notes: '' }
  showSampleForm.value = true
}

// 🚨 画布：拖拽改变位置并保存到后端
const onItemDragStart = (e: DragEvent, key: string) => { 
  dragItemKey.value = key; selectWell(key)
  if (e.dataTransfer) { e.dataTransfer.setData('text/plain', key); e.dataTransfer.setDragImage(e.target as Element, 20, 20) }
}
const onCanvasDrop = async (e: DragEvent) => {
  if (!dragItemKey.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const x = e.clientX - rect.left - 20
  const y = e.clientY - rect.top - 20
  
  // 乐观更新前端
  if (boxData.value[dragItemKey.value]) {
     boxData.value[dragItemKey.value].x = x
     boxData.value[dragItemKey.value].y = y
  }
  
  // 同步坐标给后端
  try {
    await fetch('http://127.0.0.1:8080/api/samples/move_item', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ box_id: `${currentEqId.value}/${currentContId.value}`, well_index: dragItemKey.value, x, y })
    })
  } catch (e) {}
  dragItemKey.value = null
}

const selectWell = (wid: string) => { selectedWell.value = wid; if (getWellStatus(wid) === 'empty' && currentContainer.value?.type !== 'freeform') triggerAddSample() }

const triggerAddSample = () => {
  if (!selectedWell.value) return
  formData.value = { name: '', type: '🧬 质粒 (Plasmid)', vol: 100, unit: 'μL', ft: 0, owner: 'Admin', notes: '' }; showSampleForm.value = true
}

const confirmSaveSample = async () => {
  if (!formData.value.name) return
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/add', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        box_id: `${currentEqId.value}/${currentContId.value}`, well_index: selectedWell.value, 
        sample_name: formData.value.name, sample_type: formData.value.type, vol: formData.value.vol, unit: formData.value.unit, 
        ft_count: formData.value.ft, owner: formData.value.owner, notes: formData.value.notes,
        x: tempCanvasX.value, y: tempCanvasY.value // 传入画布坐标
      })
    })
    if (res.ok) { boxData.value[selectedWell.value as string] = { ...formData.value, x: tempCanvasX.value, y: tempCanvasY.value }; showSampleForm.value = false }
  } catch (e) {}
}

const removeSample = async () => { 
  if (!selectedWell.value) return
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/remove?box_id=${encodeURIComponent(currentEqId.value + '/' + currentContId.value)}&well_index=${selectedWell.value}`, { method: 'POST' })
    if (res.ok) { delete boxData.value[selectedWell.value]; selectedWell.value = null }
  } catch (e) {}
}

onMounted(() => fetchTopology())
</script>

<style scoped>
/* ================= 基础布局 (高度锁死防溢出) ================= */
.sample-hub-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4;}
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086; cursor: pointer; transition: 0.2s;}
.breadcrumbs h2:hover { color: #b4befe;}
.breadcrumbs h2.active { color: #89b4fa; font-weight: bold;}
.separator { color: #45475a; font-weight: bold;}

.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0;}
.btn-outline { background: transparent; color: #a6adc8; border: 1px dashed #45475a; padding: 8px 15px; border-radius: 8px; cursor: pointer; transition: 0.2s; flex-shrink: 0;}
.btn-outline.is-editing { border-color: #f38ba8; color: #f38ba8; background: rgba(243, 139, 168, 0.1);}
.btn-danger { background: rgba(243, 139, 168, 0.1); color: #f38ba8; border: 1px solid #f38ba8; padding: 8px 15px; border-radius: 6px; cursor: pointer; transition: 0.2s;}
.w-full { width: 100%; }

/* ================= 宏观层 ================= */
.equipments-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); grid-auto-rows: max-content; gap: 18px; overflow-y: auto; flex: 1; min-height: 0; padding: 5px 5px 20px 5px; }
.eq-card { display: flex; flex-direction: column; padding: 20px; background: #181825; border: 1px solid #313244; border-radius: 12px; cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);}
.eq-card:hover { border-color: #89b4fa; transform: translateY(-4px); box-shadow: 0 12px 25px rgba(0,0,0,0.3);}
.eq-header { display: flex; align-items: center; margin-bottom: 12px; }
.eq-icon-wrapper { font-size: 26px; background: #11111b; border: 1px solid #313244; border-radius: 50%; margin-right: 15px; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center;}
.eq-title h3 { margin: 0 0 6px 0; font-size: 16px; color: #cdd6f4;}
.eq-status { font-size: 11px; color: #a6e3a1; display: flex; align-items: center; gap: 6px; }
.status-dot { width: 6px; height: 6px; background: #a6e3a1; border-radius: 50%; animation: pulse 2s infinite;}
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
.eq-desc { font-size: 12px; color: #6c7086; line-height: 1.5; margin: 0 0 18px 0; }
.eq-footer { margin-top: auto;}

/* ================= 🚨 中观层：统一所见即所得视图 ================= */
.cabinet-view-unified { display: flex; gap: 20px; flex: 1; min-height: 0; }
.cabinet-workspace { flex: 3; background: #11111b; padding: 30px; border-radius: 12px; border: 1px solid #313244; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow-y: auto;}
.cabinet-frame { width: 100%; max-width: 800px; background: #1e1e2e; padding: 20px; border-radius: 12px; border: 4px solid #45475a; box-shadow: inset 0 0 30px rgba(0,0,0,0.5); transition: border-color 0.3s;}
.cabinet-frame.edit-active { border-color: #f38ba8; border-style: dashed; }
.cabinet-title { text-align: center; color: #6c7086; font-weight: bold; margin-bottom: 20px; letter-spacing: 2px;}

.cabinet-grid { display: grid; position: relative; gap: 6px; background: #11111b; padding: 6px; border-radius: 8px; min-height: 400px;}
.grid-dropzone { background: rgba(49, 50, 68, 0.4); border: 1px dashed #45475a; border-radius: 6px; min-height: 80px; transition: all 0.2s;}
.grid-dropzone.drag-hover { background: rgba(243, 139, 168, 0.2); border-color: #f38ba8; transform: scale(0.95);}

.draggable-cont { 
  background: rgba(137, 180, 250, 0.15); border: 2px solid #89b4fa; border-radius: 8px; 
  display: flex; flex-direction: column; align-items: center; justify-content: center; 
  transition: all 0.2s; z-index: 10;
}
.draggable-cont.can-click { cursor: pointer; }
.draggable-cont.can-click:hover { background: rgba(137, 180, 250, 0.3); transform: scale(1.02); }
.draggable-cont.can-drag { cursor: grab; border-style: dashed; border-color: #a6adc8; background: rgba(166, 173, 200, 0.1); }
.draggable-cont.can-drag:active { cursor: grabbing;}
.draggable-cont.is-selected { border-color: #f38ba8 !important; box-shadow: 0 0 15px rgba(243, 139, 168, 0.3); background: rgba(243, 139, 168, 0.15) !important;}

.cont-label { font-weight: bold; color: #cdd6f4; font-size: 14px; text-align: center; }
.cont-size-badge { font-size: 11px; background: rgba(17,17,27,0.8); color: #a6adc8; padding: 2px 8px; border-radius: 10px; margin-top: 5px;}

.cabinet-sidebar { flex: 1; max-width: 300px; background: #181825; padding: 20px; border-radius: 12px; border: 1px solid #313244; overflow-y: auto;}
.help-text { font-size: 13px; color: #6c7086; margin-bottom: 20px; line-height: 1.6;}
.resize-panel { background: #11111b; padding: 15px; border-radius: 8px; border: 1px solid #45475a;}
.control-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #bac2de; margin-bottom: 10px;}
.icon-btn { background: #313244; color: #cdd6f4; border: none; width: 28px; height: 28px; border-radius: 6px; cursor: pointer; font-weight: bold;}

/* ================= 🚨 微观层与画布 ================= */
.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}
.grid-container { flex: 2; background: #11111b; padding: 25px; border-radius: 12px; border: 1px solid #313244; display: flex; flex-direction: column; align-items: center; overflow-y: auto;}
.grid-header { display: flex; justify-content: space-between; align-items: center; width: 100%; max-width: 600px; margin-bottom: 15px; flex-shrink: 0;}

/* 🌟 2D自由画布核心样式 */
.freeform-canvas {
  width: 100%; max-width: 600px; flex: 1; min-height: 400px; 
  background: #181825; border: 2px dashed #45475a; border-radius: 12px;
  position: relative; /* 核心：开启相对定位底板 */
  overflow: hidden; cursor: crosshair;
}
.canvas-hint { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #45475a; text-align: center; font-weight: bold; pointer-events: none; }
.canvas-item {
  position: absolute; /* 核心：内部元素绝对定位 */
  display: flex; flex-direction: column; align-items: center;
  cursor: grab; transition: transform 0.1s; padding: 5px;
}
.canvas-item:active { cursor: grabbing; transform: scale(1.1); }
.canvas-item.selected .item-icon { box-shadow: 0 0 0 3px #f9e2af; border-color: #f9e2af; }
.item-icon {
  width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 20px; border: 2px solid transparent; background: #11111b; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}
.item-name { font-size: 11px; color: #cdd6f4; margin-top: 5px; font-weight: bold; text-shadow: 0 1px 2px #000; background: rgba(17,17,27,0.7); padding: 2px 6px; border-radius: 4px;}

.well-board { display: grid; gap: 8px; width: 100%; max-width: 550px; padding-bottom: 20px;}
.well-cell.square { background: #181825; aspect-ratio: 1; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 13px; color: #6c7086; cursor: pointer; border: 1px solid #313244;}
.well-cell.square:hover { border-color: #89b4fa; background: #1e1e2e;}
.well-cell.square.selected { border-color: #f9e2af; box-shadow: 0 0 12px rgba(249,226,175,0.2); transform: scale(1.05);}
.well-cell.square.filled { background: #89b4fa; color: #11111b; font-weight: bold; border-color: #89b4fa;}

.panel-container { flex: 1; max-width: 350px; background: #181825; padding: 20px; border-radius: 12px; border: 1px solid #313244; overflow-y: auto;}
.info-group { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px dashed #313244;}
.info-group label { color: #a6adc8; font-weight: bold;}
.value { font-family: monospace; padding: 4px 10px; border-radius: 6px; font-weight: bold; background: #11111b;}
.value.highlight { color: #f9e2af; font-size: 16px;}
.actions-group { margin-top: 30px;}
.empty-state { text-align: center; padding: 40px 20px;}

/* 通用弹窗与色彩 */
.well-cell.bg-protein, .item-icon.bg-protein { background: rgba(166, 227, 161, 0.2); border-color: #a6e3a1; color: #a6e3a1; }
.well-cell.bg-plasmid, .item-icon.bg-plasmid { background: rgba(243, 139, 168, 0.2); border-color: #f38ba8; color: #fab387; }
.well-cell.bg-cell, .item-icon.bg-cell { background: rgba(203, 166, 247, 0.2); border-color: #cba6f7; color: #cba6f7; }
.well-cell.bg-default, .item-icon.bg-default { background: rgba(137, 180, 250, 0.2); border-color: #89b4fa; color: #89b4fa; }
.warn-icon { position: absolute; top: -5px; right: -5px; font-size: 10px; z-index: 2; }
.modal-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(17, 17, 27, 0.8); backdrop-filter: blur(4px); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-content { display: flex; flex-direction: column; }
.form-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; flex: 1; }
.form-group-row { display: flex; gap: 15px; }
.input-dark { background: #11111b; border: 1px solid #313244; color: #cdd6f4; padding: 10px 12px; border-radius: 6px; outline: none;}
.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>