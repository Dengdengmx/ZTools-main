<template>
  <div class="sample-hub-view">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 @click="navTo(0)" :class="{ active: currentLevel === 0 }">🧪 物理样本库</h2>
        <template v-if="currentLevel > 0"><span class="separator">/</span><h2 @click="navTo(1)" :class="{ active: currentLevel === 1 }">{{ currentEq?.name }}</h2></template>
        <template v-if="currentLevel > 2">
          <span class="separator">/</span><h2 @click="currentRackBox = null" :class="{ active: currentLevel === 2 && !currentRackBox }">{{ currentContainer?.name }}</h2>
        </template>
        <template v-if="currentRackBox">
          <span class="separator">/</span><h2 class="active">第 {{ currentRackBox.layer }} 层 - 盒 {{ currentRackBox.col }}</h2>
        </template>
      </div>
      <div class="header-actions">
        <button class="btn-outline" style="color: #cba6f7; border-color: #cba6f7;" @click="triggerGlobalSearch">🔍 全局搜索</button>
        <button v-if="currentLevel === 1" class="btn-outline" :class="{ 'is-editing': isEditMode }" @click="toggleEditMode">
          {{ isEditMode ? '🔒 锁定物理布局' : '🔓 解锁布局编辑' }}
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
        <div class="eq-capacity">
          <div class="capacity-labels"><span>物理空间负载</span><span>{{ Object.keys(eq.containers || {}).length }} / {{ eq.rows * eq.cols }}</span></div>
          <div class="progress-track"><div class="progress-fill" :style="{ width: `${Math.min(100, (Object.keys(eq.containers || {}).length / (eq.rows * eq.cols)) * 100)}%` }"></div></div>
        </div>
        <div class="eq-footer"><span class="tag">网格: {{ eq.rows }}x{{ eq.cols }}</span></div>
      </div>
    </div>

    <div class="cabinet-view-unified fade-in" v-else-if="currentLevel === 1">
      <div class="cabinet-workspace card">
        <div class="cabinet-frame" :class="{ 'edit-active': isEditMode }">
          <div class="cabinet-title">{{ currentEq.name }} - 物理映射 ({{ currentEq.rows }}x{{ currentEq.cols }})</div>
          <div class="cabinet-grid" :style="{ gridTemplateRows: `repeat(${currentEq.rows}, 1fr)`, gridTemplateColumns: `repeat(${currentEq.cols}, 1fr)` }">
            <div v-for="i in (currentEq.rows * currentEq.cols)" :key="'bg'+i" class="grid-dropzone" @dragover.prevent @dragenter.prevent="isEditMode ? dragHoverIndex = i : null" @dragleave.prevent="dragHoverIndex = null" @drop="isEditMode ? onDrop(i) : null" :class="{ 'drag-hover': dragHoverIndex === i }"></div>
            <div v-for="(cont, cid) in currentEq?.containers" :key="cid" class="draggable-cont" :class="{ 'is-selected': editingContId === cid, 'can-drag': isEditMode, 'can-click': !isEditMode }" :style="{ gridRow: `${cont.r + 1} / span ${cont.rs}`, gridColumn: `${cont.c + 1} / span ${cont.cs}` }" :draggable="isEditMode" @dragstart="isEditMode ? onDragStart($event, cid as string) : null" @click="handleContainerClick(cid as string, cont)">
              <div class="cont-label">{{ cont.name }}</div>
              <div class="cont-size-badge">{{ cont.type === 'rack' ? '冻存架' : (cont.type === 'freeform' ? '散装区' : cont.type) }}</div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="isEditMode" class="cabinet-sidebar card fade-in">
        <h3>🛠️ 空间工具箱</h3>
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
        <div class="grid-container card" style="position: relative; overflow: hidden; padding: 0;">
           <div class="grid-header" style="padding: 20px 25px 0 25px;">
             <div>
               <h3 style="margin:0;">{{ currentRackBox ? `层 ${currentRackBox.layer} / 盒 ${currentRackBox.col}` : currentContainer?.name }}</h3>
               <span style="font-size: 12px; color: #a6adc8;" v-if="currentContainer?.type !== 'freeform' && currentContainer?.type !== 'rack'">💡 提示: 按 <b>Ctrl+V</b> 粘贴 Excel 数据大批量入库</span>
             </div>
             <div style="display: flex; gap: 10px; align-items: center;">
               <span class="tag">{{ currentContainer?.type }}</span>
               <button v-if="currentContainer?.type !== 'freeform' && currentContainer?.type !== 'rack'" class="btn-primary" @click="autoAddSample" style="padding: 4px 12px; font-size: 13px;">➕ 自动寻空位</button>
             </div>
           </div>
           
           <div v-if="currentContainer?.type === 'freeform'" 
                class="infinite-canvas-viewport" 
                @wheel.prevent="handleCanvasZoom"
                @mousedown.middle.prevent="startCanvasPan"
                @mousemove="doCanvasPan"
                @mouseup="endCanvasPan"
                @mouseleave="endCanvasPan"
                @dragover.prevent 
                @drop="onCanvasDrop">
              
              <div class="canvas-hint" style="z-index: 10;">自由画布 <br> 🖱️ 中键拖拽平移 | ⚙️ 滚轮缩放 | 🖱️ 双击新建</div>
              
              <div class="canvas-transform-layer" :style="{ transform: `translate(${canvasPan.x}px, ${canvasPan.y}px) scale(${canvasScale})` }" @dblclick.self="handleCanvasDoubleClick">
                <div class="canvas-grid-bg"></div> <div v-for="(item, key) in boxData" :key="key" class="canvas-item" :class="{ 'selected': selectedWell === key }" :style="{ left: `${item.x}px`, top: `${item.y}px` }" draggable="true" @dragstart="onItemDragStart($event, key as string)" @click.stop="selectWell(key as string)">
                  <div class="item-icon" :class="getSampleColorClass(item)">{{ item.type?.includes('细胞') ? '🧫' : (item.type?.includes('蛋白') ? '🧪' : '🧬') }}</div>
                  <div class="item-name">{{ item.name }}</div>
                </div>
              </div>
           </div>

           <div v-else-if="currentContainer?.type === 'rack' && !currentRackBox" class="rack-shelf-view">
             <div class="rack-frame" :style="{ gridTemplateRows: `repeat(${currentContainer.layers || 5}, 1fr)` }">
                <div v-for="layer in (currentContainer.layers || 5)" :key="'layer'+layer" class="rack-layer">
                  <div class="layer-label">L{{ layer }}</div>
                  <div class="layer-boxes" :style="{ gridTemplateColumns: `repeat(${currentContainer.boxes || 4}, 1fr)` }">
                    <div v-for="col in (currentContainer.boxes || 4)" :key="'box'+layer+'-'+col" class="rack-box-slot" @click="enterRackBox(layer, col)">
                      <span class="box-icon">📦</span>
                      <span class="box-name">盒子 {{ col }}</span>
                    </div>
                  </div>
                </div>
             </div>
           </div>

           <div v-else class="well-board-wrapper" style="padding: 20px; overflow-y: auto; height: 100%; width: 100%; display: flex; justify-content: center;">
             <div class="well-board" :style="{ gridTemplateColumns: `repeat(${gridInfo.cols}, 1fr)` }">
                <div v-for="wid in gridInfo.cells" :key="wid" class="well-cell square" :class="[getWellStatus(wid), getSampleColorClass(boxData[wid]), { 'selected': selectedWell === wid }]" @click="selectWell(wid)">
                  <span v-if="boxData[wid]?.ft >= 5" class="warn-icon" title="冻融次数过多">⚠️</span>
                  {{ boxData[wid]?.name ? boxData[wid].name.substring(0,3) : wid }}
                </div>
             </div>
           </div>
        </div>

        <div class="panel-container card">
          <h3>资产追踪参数</h3>
          <div v-if="!selectedWell" class="empty-state">
            <div class="empty-hint" style="margin-top: 40px;">在左侧点击<br><b>空位</b>：录入资产<br><b>已有物</b>：查看详情</div>
          </div>
          <div v-else class="sample-info fade-in">
            <div class="info-group"><label>标识</label><div class="value highlight">[{{ selectedWell }}]</div></div>
            <div class="info-group"><label>状态</label><div class="value" :class="getWellStatus(selectedWell) === 'empty' ? '' : 'success'">{{ getWellStatus(selectedWell) === 'empty' ? '空闲' : '已入库' }}</div></div>
            <template v-if="getWellStatus(selectedWell) !== 'empty'">
              <div class="info-group"><label>名称</label><div class="value">{{ boxData[selectedWell]?.name || '未知资产' }}</div></div>
              <div class="info-group"><label>大类</label><div class="value">{{ boxData[selectedWell]?.type || '未知' }}</div></div>
              <div class="info-group"><label>当前余量</label><div class="value" style="color: #a6e3a1;">{{ boxData[selectedWell]?.vol || 0 }} {{ boxData[selectedWell]?.unit || 'μL' }}</div></div>
              <div class="info-group"><label>冻融(F/T)</label><div class="value" :class="boxData[selectedWell]?.ft >= 5 ? 'id-value' : ''">{{ boxData[selectedWell]?.ft || 0 }} 次</div></div>
              <div class="info-group" style="flex-direction: column; align-items: flex-start; border: none; padding-top: 15px;">
                 <label style="margin-bottom: 5px;">追溯日志 / 备注</label>
                 <div class="log-box">{{ boxData[selectedWell]?.notes || '无记录' }}</div>
              </div>
            </template>
            <div class="actions-group">
              <button class="btn-primary w-full" v-if="getWellStatus(selectedWell) === 'empty'" @click="showSampleForm = true">📥 确认为其入库</button>
              <template v-else>
                <button class="btn-purple w-full" @click="triggerCheckout" style="margin-bottom: 10px;">📉 取用登记 (耗材追溯)</button>
                <button class="btn-danger w-full" @click="removeSample">🗑️ 彻底报废清除</button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showCheckoutForm" class="modal-overlay fade-in">
      <div class="modal-content card" style="width: 380px; border: 2px solid #cba6f7;">
        <h3 style="margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 10px; color:#cba6f7;">📉 取用登记 ({{ selectedWell }})</h3>
        <p style="font-size: 12px; color: #a6adc8; margin-bottom: 15px;">系统将自动扣减体积，冻融次数 (F/T) +1。</p>
        <div class="form-group-row">
          <div class="form-group"><label>消耗体积</label><input type="number" v-model="checkoutData.vol" class="input-dark"></div>
          <div class="form-group"><label>单位</label><input disabled :value="boxData[selectedWell as string]?.unit" class="input-dark" style="opacity: 0.7;"></div>
        </div>
        <div class="form-group"><label>操作人</label><input v-model="checkoutData.operator" class="input-dark"></div>
        <div class="form-group"><label>附言</label><input v-model="checkoutData.notes" class="input-dark"></div>
        <div class="modal-actions" style="margin-top: 15px;"><button class="btn-outline" @click="showCheckoutForm = false">取消</button><button class="btn-purple" @click="confirmCheckout">确认取用</button></div>
      </div>
    </div>

    <div v-if="showBulkImportForm" class="modal-overlay fade-in">
      <div class="modal-content card" style="width: 650px; max-height: 80vh; overflow-y: auto; border: 2px solid #89b4fa;">
        <h3 style="margin-top: 0; color:#89b4fa;">🚀 剪贴板批量高通量导入</h3>
        <table class="bulk-table">
          <thead><tr><th>映射孔位</th><th>识别样本名</th><th>大类(默认)</th><th>初始体积</th></tr></thead>
          <tbody>
            <tr v-for="(item, idx) in bulkPreviewData" :key="idx">
              <td style="color: #f9e2af; font-weight: bold;">[{{ item.well_index }}]</td>
              <td><input v-model="item.sample_name" class="input-dark" style="padding: 4px; font-size: 12px;"></td>
              <td><select v-model="item.sample_type" class="input-dark" style="padding: 4px; font-size: 12px;"><option>🧬 质粒 (Plasmid)</option><option>🧪 蛋白 (Protein)</option><option>🧫 细胞 (Cell)</option></select></td>
              <td><input type="number" v-model="item.vol" class="input-dark" style="width: 60px; padding: 4px; font-size: 12px;"> μL</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions" style="margin-top: 20px;"><button class="btn-outline" @click="showBulkImportForm = false">放弃导入</button><button class="btn-primary" @click="confirmBulkImport">确认全量入库</button></div>
      </div>
    </div>

    <div v-if="showContainerForm" class="modal-overlay fade-in">
      <div class="modal-content card" style="width: 380px;">
        <h3 style="margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 10px; color:#cdd6f4;">📦 划拨新容器</h3>
        <div class="form-group"><label>容器名称</label><input v-model="containerForm.name" class="input-dark"></div>
        <div class="form-group"><label>大类</label>
          <select v-model="containerForm.category" class="input-dark">
            <option value="rack">🧊 标准冻存架 (含抽屉与嵌套盒)</option>
            <option value="box">📦 独立标准冻存盒</option>
            <option value="holder">🧫 独立试管架</option>
            <option value="freeform">📥 自由散装大抽屉 (2D画布)</option>
          </select>
        </div>
        <div class="form-group" v-if="containerForm.category === 'rack'"><label>内部规格 (层 x 盒)</label><select v-model="containerForm.subSpec" class="input-dark"><option value="5x4">5层 × 每层4盒</option><option value="4x4">4层 × 每层4盒</option></select></div>
        <div class="form-group" v-if="containerForm.category === 'box'"><label>规格</label><select v-model="containerForm.subSpec" class="input-dark"><option value="9x9">9x9 (81孔)</option><option value="10x10">10x10 (100孔)</option></select></div>
        <div class="form-group" v-if="containerForm.category === 'holder'"><label>规格</label><select v-model="containerForm.subSpec" class="input-dark"><option value="12x8">12x8 (96孔板)</option></select></div>
        <div class="form-group-row" v-if="containerForm.category === 'freeform'"><div class="form-group"><label>占据高(行)</label><input type="number" v-model="containerForm.rs" class="input-dark"></div><div class="form-group"><label>占据宽(列)</label><input type="number" v-model="containerForm.cs" class="input-dark"></div></div>
        <div class="modal-actions" style="margin-top: 15px;"><button class="btn-outline" @click="showContainerForm = false">取消</button><button class="btn-primary" @click="confirmAddContainer">确定上架</button></div>
      </div>
    </div>

    <div v-if="showSampleForm" class="modal-overlay fade-in">
      <div class="modal-content card" style="width: 420px;">
        <h3 style="margin-top: 0; border-bottom: 1px solid #313244; padding-bottom: 10px; color:#cdd6f4;">📥 存入标的物 ({{ selectedWell }})</h3>
        <div class="form-group"><label>样本名称</label><input v-model="formData.name" class="input-dark"></div>
        <div class="form-group"><label>样本大类</label><select v-model="formData.type" class="input-dark"><option>🧬 质粒 (Plasmid)</option><option>🧪 蛋白 (Protein)</option><option>🧫 细胞 (Cell)</option></select></div>
        <div class="form-group-row"><div class="form-group"><label>余量</label><input type="number" v-model="formData.vol" class="input-dark"></div><div class="form-group"><label>单位</label><select v-model="formData.unit" class="input-dark"><option>μL</option><option>mL</option><option>管</option></select></div><div class="form-group"><label>冻融</label><input type="number" v-model="formData.ft" class="input-dark"></div></div>
        <div class="form-group"><label>所有人</label><input v-model="formData.owner" class="input-dark"></div>
        <div class="modal-actions" style="margin-top: 15px;"><button class="btn-outline" @click="showSampleForm = false">取消</button><button class="btn-primary" @click="confirmSaveSample">确认入库</button></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'

const currentLevel = ref(0)
const equipments = ref<Record<string, any>>({})
const currentEqId = ref('')
const currentEq = ref<any>(null)
const currentContId = ref('')
const currentContainer = ref<any>(null)
const selectedWell = ref<string | null>(null)
const boxData = ref<Record<string, any>>({}) 

// 🚨 冻存架深潜状态
const currentRackBox = ref<{ layer: number, col: number } | null>(null)

// ================= 画布引擎核心状态 =================
const canvasScale = ref(1)
const canvasPan = ref({ x: 0, y: 0 })
const isCanvasPanning = ref(false)
const startPanCoords = ref({ x: 0, y: 0 })

const dragItemKey = ref<string | null>(null)
const tempCanvasX = ref(20)
const tempCanvasY = ref(20)

// 弹窗状态...
const showSampleForm = ref(false); const formData = ref({ name: '', type: '🧬 质粒 (Plasmid)', vol: 100, unit: 'μL', ft: 0, owner: 'Admin', notes: '' })
const showContainerForm = ref(false); const containerForm = ref({ name: '', category: 'box', subSpec: '10x10', rs: 1, cs: 1 })
const showCheckoutForm = ref(false); const checkoutData = ref({ vol: 10, operator: 'Admin', notes: '' })
const showBulkImportForm = ref(false); const bulkPreviewData = ref<any[]>([])
const isEditMode = ref(false); const draggedContId = ref<string | null>(null); const dragHoverIndex = ref<number | null>(null); const editingContId = ref<string | null>(null)

// ================= 画布引擎方法 =================
const handleCanvasZoom = (e: WheelEvent) => {
  const zoomSensitivity = 0.001
  const delta = -e.deltaY * zoomSensitivity
  canvasScale.value = Math.min(Math.max(0.3, canvasScale.value + delta), 3)
}
const startCanvasPan = (e: MouseEvent) => {
  isCanvasPanning.value = true
  startPanCoords.value = { x: e.clientX - canvasPan.value.x, y: e.clientY - canvasPan.value.y }
}
const doCanvasPan = (e: MouseEvent) => {
  if (!isCanvasPanning.value) return
  canvasPan.value.x = e.clientX - startPanCoords.value.x
  canvasPan.value.y = e.clientY - startPanCoords.value.y
}
const endCanvasPan = () => { isCanvasPanning.value = false }

const handleCanvasDoubleClick = (e: MouseEvent) => {
  // 逆向计算真实坐标（受 scale 和 pan 影响）
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const rawX = (e.clientX - rect.left) / canvasScale.value
  const rawY = (e.clientY - rect.top) / canvasScale.value
  tempCanvasX.value = Math.round(rawX); tempCanvasY.value = Math.round(rawY)
  
  const keys = Object.keys(boxData.value).filter(k => k.startsWith('F-'))
  selectedWell.value = `F-${keys.length + 1}`
  triggerAddSample()
}

const onItemDragStart = (e: DragEvent, key: string) => { dragItemKey.value = key; selectWell(key); if (e.dataTransfer) { e.dataTransfer.setData('text/plain', key); e.dataTransfer.setDragImage(e.target as Element, 20, 20) } }
const onCanvasDrop = async (e: DragEvent) => {
  if (!dragItemKey.value) return
  // 逆向计算放到画布里的真实坐标
  const wrapper = document.querySelector('.canvas-transform-layer') as HTMLElement
  if(!wrapper) return
  const rect = wrapper.getBoundingClientRect()
  const x = Math.round((e.clientX - rect.left) / canvasScale.value) - 20
  const y = Math.round((e.clientY - rect.top) / canvasScale.value) - 20
  
  if (boxData.value[dragItemKey.value]) { boxData.value[dragItemKey.value].x = x; boxData.value[dragItemKey.value].y = y }
  try { await fetch('http://127.0.0.1:8080/api/samples/move_item', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box_id: `${currentEqId.value}/${currentContId.value}`, well_index: dragItemKey.value, x, y }) }) } catch (e) {}
  dragItemKey.value = null
}

// ================= 冻存架 (Rack) 深潜逻辑 =================
const enterRackBox = async (layer: number, col: number) => {
  currentRackBox.value = { layer, col }
  selectedWell.value = null
  // 组装更深层的虚拟路径: 冰箱ID / 冻存架ID / 盒子ID
  const path = `${currentEqId.value}/${currentContId.value}/L${layer}-C${col}`
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(path)}`)
    boxData.value = (await res.json()).data || {}
  } catch (e) {}
}

const getActualBoxId = () => {
  if (currentContainer.value?.type === 'rack' && currentRackBox.value) {
    return `${currentEqId.value}/${currentContId.value}/L${currentRackBox.value.layer}-C${currentRackBox.value.col}`
  }
  return `${currentEqId.value}/${currentContId.value}`
}

// ================= 全局与其他通用方法 =================
const handlePaste = (e: ClipboardEvent) => {
  if (currentLevel.value !== 2 || currentContainer.value?.type === 'freeform' || (currentContainer.value?.type === 'rack' && !currentRackBox.value)) return
  if (showSampleForm.value || showContainerForm.value || showCheckoutForm.value) return 
  const text = e.clipboardData?.getData('text'); if (!text) return
  const names = text.split('\n').map(r => r.split('\t').map(c => c.trim()).filter(c => c)).flat().filter(n => n)
  if (names.length === 0) return
  const availableWells = gridInfo.value.cells.filter(wid => !boxData.value[wid])
  if (names.length > availableWells.length) { alert("容器空位不足！"); return }
  bulkPreviewData.value = names.map((name, idx) => ({ well_index: availableWells[idx], sample_name: name, sample_type: '🧬 质粒 (Plasmid)', vol: 100, unit: 'μL', ft_count: 0, owner: 'Admin', notes: 'Excel 批量导入', x: 0, y: 0 }))
  showBulkImportForm.value = true
}

const confirmBulkImport = async () => {
  try {
    if ((await fetch('http://127.0.0.1:8080/api/samples/bulk_add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box_id: getActualBoxId(), samples: bulkPreviewData.value }) })).ok) {
      if (currentRackBox.value) await enterRackBox(currentRackBox.value.layer, currentRackBox.value.col)
      else await enterContainer(currentContId.value, currentContainer.value)
      showBulkImportForm.value = false
    }
  } catch (e) {}
}

const getSampleColorClass = (item: any) => {
  if (!item) return ''; if (item.type?.includes('蛋白')) return 'bg-protein'; if (item.type?.includes('质粒')) return 'bg-plasmid'; if (item.type?.includes('细胞')) return 'bg-cell'; return 'bg-default'
}
const getIcon = (iconName: string) => { return { 'folder': '📁', 'tiles': '🧊', 'calendar': '🌡️', 'snowflake': '❄️' }[iconName] || '🗄️' }

const navTo = (level: number) => { 
  if (level <= currentLevel.value) { currentLevel.value = level; isEditMode.value = false; if(level < 2) currentRackBox.value = null; }
}

const fetchTopology = async () => { try { const res = await fetch('http://127.0.0.1:8080/api/samples/topology'); if (res.ok) equipments.value = (await res.json()).data } catch (e) {} }

const triggerGlobalSearch = async () => {
  const keyword = prompt("输入要搜索的样本名称:")
  if(!keyword) return
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/search/omnibar?q=${keyword}`)
    const json = await res.json()
    let msg = json.message + "\n\n"; json.data.forEach((d:any) => msg += `${d.icon} ${d.title}\n${d.desc}\n\n`)
    alert(msg)
  } catch (e) {}
}

const enterEquipment = (id: string, eq: any) => { currentEqId.value = id; currentEq.value = eq; currentLevel.value = 1; isEditMode.value = false; }
const toggleEditMode = () => { isEditMode.value = !isEditMode.value; editingContId.value = null; if (!isEditMode.value) fetchTopology(); }
const handleContainerClick = (cid: string, cont: any) => { if (isEditMode.value) editingContId.value = cid; else enterContainer(cid, cont) }

// ...拖拽缩放等操作保持原样
const onDragStart = (e: DragEvent, cid: string) => { draggedContId.value = cid; editingContId.value = cid; if (e.dataTransfer) e.dataTransfer.setData('text/plain', cid) }
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
  if (containerForm.value.category === 'rack') { payload.type = 'rack'; let parts = containerForm.value.subSpec.split('x'); payload.layers = parseInt(parts[0]); payload.boxes = parseInt(parts[1]) }
  try {
    if ((await fetch('http://127.0.0.1:8080/api/samples/container/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })).ok) { await fetchTopology(); currentEq.value = equipments.value[currentEqId.value]; showContainerForm.value = false }
  } catch (e) {}
}
const deleteContainer = async (cid: string) => { if (window.confirm("确定拆除此容器？")) { try { if ((await fetch(`http://127.0.0.1:8080/api/samples/container/delete?equip_id=${currentEqId.value}&cid=${cid}`, { method: 'POST' })).ok) { delete currentEq.value.containers[cid]; editingContId.value = null } } catch (e) {} } }

const enterContainer = async (cid: string, cont: any) => { 
  currentContId.value = cid; currentContainer.value = cont; currentLevel.value = 2; selectedWell.value = null; currentRackBox.value = null
  // 初始化画布
  canvasScale.value = 1; canvasPan.value = { x: 0, y: 0 };
  
  if(cont.type === 'rack') return // 冻存架顶层没有直接的样本数据，需深入抽屉
  try {
    boxData.value = (await (await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(getActualBoxId())}`)).json()).data || {}
  } catch (e) {}
}

const gridInfo = computed(() => {
  const t = currentContainer.value?.type === 'rack' ? '9x9' : (currentContainer.value?.type || '10x10'); let r: string[] = [], c = 0
  if (t === '10x10') { r = ['A','B','C','D','E','F','G','H','I','J']; c = 10 }
  else if (t === '9x9') { r = ['A','B','C','D','E','F','G','H','I']; c = 9 }
  else if (t === '12x8') { r = ['A','B','C','D','E','F','G','H']; c = 12 }
  else return { rows: [], cols: 0, cells: [] } 
  let cells: string[] = []; r.forEach(row => { for (let i = 1; i <= c; i++) cells.push(`${row}${i}`) })
  return { rows: r, cols: c, cells }
})

const getWellStatus = (wid: string) => { return boxData.value[wid] ? 'filled' : 'empty' }
const selectWell = (wid: string) => { selectedWell.value = wid; if (getWellStatus(wid) === 'empty' && currentContainer.value?.type !== 'freeform') triggerAddSample() }
const autoAddSample = () => { const firstEmpty = gridInfo.value.cells.find(wid => !boxData.value[wid]); if (firstEmpty) { selectedWell.value = firstEmpty; triggerAddSample() } else { alert("⚠️ 容器已满！") } }

const triggerAddSample = () => { if (!selectedWell.value) return; formData.value = { name: '', type: '🧬 质粒 (Plasmid)', vol: 100, unit: 'μL', ft: 0, owner: 'Admin', notes: '' }; showSampleForm.value = true }
const confirmSaveSample = async () => {
  if (!formData.value.name) return
  try {
    if ((await fetch('http://127.0.0.1:8080/api/samples/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box_id: getActualBoxId(), well_index: selectedWell.value, sample_name: formData.value.name, sample_type: formData.value.type, vol: formData.value.vol, unit: formData.value.unit, ft_count: formData.value.ft, owner: formData.value.owner, notes: formData.value.notes, x: tempCanvasX.value, y: tempCanvasY.value }) })).ok) { boxData.value[selectedWell.value as string] = { ...formData.value, x: tempCanvasX.value, y: tempCanvasY.value }; showSampleForm.value = false }
  } catch (e) {}
}

const removeSample = async () => { 
  if (!selectedWell.value || !window.confirm("确定彻底删除吗？")) return
  try { if ((await fetch(`http://127.0.0.1:8080/api/samples/remove?box_id=${encodeURIComponent(getActualBoxId())}&well_index=${selectedWell.value}`, { method: 'POST' })).ok) { delete boxData.value[selectedWell.value]; selectedWell.value = null } } catch (e) {}
}

const triggerCheckout = () => { if (!selectedWell.value) return; checkoutData.value = { vol: 10, operator: 'Admin', notes: '' }; showCheckoutForm.value = true }
const confirmCheckout = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/checkout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box_id: getActualBoxId(), well_index: selectedWell.value, checkout_vol: checkoutData.value.vol, operator: checkoutData.value.operator, notes: checkoutData.value.notes }) })
    const json = await res.json()
    if (json.code === 200) { boxData.value[selectedWell.value as string] = json.data; showCheckoutForm.value = false } else { alert(json.message) }
  } catch (e) {}
}

onMounted(() => { fetchTopology(); window.addEventListener('paste', handlePaste) })
onUnmounted(() => { window.removeEventListener('paste', handlePaste) })
</script>

<style scoped>
/* 基础与宏观布局 (与上版相同，不赘述，直接保留) */
.sample-hub-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4;}
.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086; cursor: pointer; transition: 0.2s;}
.breadcrumbs h2:hover { color: #b4befe;}
.breadcrumbs h2.active { color: #89b4fa; font-weight: bold;}
.separator { color: #45475a; font-weight: bold;}
.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0;}
.btn-purple { background: #cba6f7; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}
.btn-outline { background: transparent; color: #a6adc8; border: 1px dashed #45475a; padding: 8px 15px; border-radius: 8px; cursor: pointer; transition: 0.2s; flex-shrink: 0;}
.btn-outline.is-editing { border-color: #f38ba8; color: #f38ba8; background: rgba(243, 139, 168, 0.1);}
.btn-danger { background: rgba(243, 139, 168, 0.1); color: #f38ba8; border: 1px solid #f38ba8; padding: 8px 15px; border-radius: 6px; cursor: pointer; transition: 0.2s;}
.w-full { width: 100%; }

/* 宏观设备卡片 */
.equipments-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); grid-auto-rows: max-content; gap: 18px; overflow-y: auto; flex: 1; min-height: 0; padding: 5px 5px 20px 5px; }
.eq-card { display: flex; flex-direction: column; padding: 20px; background: #181825; border: 1px solid #313244; border-radius: 12px; cursor: pointer; transition: all 0.2s; }
.eq-card:hover { border-color: #89b4fa; transform: translateY(-4px); box-shadow: 0 12px 25px rgba(0,0,0,0.3);}
.eq-header { display: flex; align-items: center; margin-bottom: 12px; }
.eq-icon-wrapper { font-size: 26px; background: #11111b; border: 1px solid #313244; border-radius: 50%; margin-right: 15px; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center;}
.eq-title h3 { margin: 0 0 6px 0; font-size: 16px; color: #cdd6f4;}
.eq-status { font-size: 11px; color: #a6e3a1; display: flex; align-items: center; gap: 6px; }
.status-dot { width: 6px; height: 6px; background: #a6e3a1; border-radius: 50%; animation: pulse 2s infinite;}
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
.eq-desc { font-size: 12px; color: #6c7086; margin: 0 0 18px 0; }
.eq-capacity { background: #11111b; padding: 12px; border-radius: 8px; border: 1px solid #313244; margin-bottom: 15px;}
.capacity-labels { display: flex; justify-content: space-between; font-size: 11px; color: #a6adc8; margin-bottom: 8px; font-weight: bold;}
.progress-track { width: 100%; height: 6px; background: #313244; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #89b4fa, #cba6f7); transition: width 0.8s; }
.eq-footer { margin-top: auto;}

/* 中观大柜体 */
.cabinet-view-unified { display: flex; gap: 20px; flex: 1; min-height: 0; }
.cabinet-workspace { flex: 3; background: #11111b; padding: 30px; border-radius: 12px; border: 1px solid #313244; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow-y: auto;}
.cabinet-frame { width: 100%; max-width: 800px; background: #1e1e2e; padding: 20px; border-radius: 12px; border: 4px solid #45475a; box-shadow: inset 0 0 30px rgba(0,0,0,0.5); transition: border-color 0.3s;}
.cabinet-frame.edit-active { border-color: #f38ba8; border-style: dashed; }
.cabinet-title { text-align: center; color: #6c7086; font-weight: bold; margin-bottom: 20px; letter-spacing: 2px;}
.cabinet-grid { display: grid; position: relative; gap: 6px; background: #11111b; padding: 6px; border-radius: 8px; min-height: 400px;}
.grid-dropzone { background: rgba(49, 50, 68, 0.4); border: 1px dashed #45475a; border-radius: 6px; min-height: 80px; transition: all 0.2s;}
.grid-dropzone.drag-hover { background: rgba(243, 139, 168, 0.2); border-color: #f38ba8; transform: scale(0.95);}
.draggable-cont { background: rgba(137, 180, 250, 0.15); border: 2px solid #89b4fa; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; transition: all 0.2s; z-index: 10;}
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

/* 微观布局拆分 */
.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0;}
.grid-container { flex: 2; background: #11111b; border-radius: 12px; border: 1px solid #313244; display: flex; flex-direction: column; align-items: center;}
.grid-header { display: flex; justify-content: space-between; align-items: center; width: 100%; flex-shrink: 0; z-index: 20; background: #11111b;}

/* 🌟 无极画布引擎 (Infinite Canvas) */
.infinite-canvas-viewport { width: 100%; flex: 1; position: relative; overflow: hidden; background: #181825; border-top: 1px solid #313244; cursor: crosshair;}
.canvas-hint { position: absolute; top: 10px; left: 10px; color: #6c7086; font-size: 12px; font-weight: bold; pointer-events: none; background: rgba(17,17,27,0.7); padding: 5px 10px; border-radius: 6px;}
.canvas-transform-layer { position: absolute; top: 0; left: 0; width: 5000px; height: 5000px; transform-origin: 0 0; transition: transform 0.05s linear; }
.canvas-grid-bg { width: 100%; height: 100%; background-image: linear-gradient(#313244 1px, transparent 1px), linear-gradient(90deg, #313244 1px, transparent 1px); background-size: 40px 40px; opacity: 0.3;}
.canvas-item { position: absolute; display: flex; flex-direction: column; align-items: center; cursor: grab; padding: 5px; z-index: 10;}
.canvas-item:active { cursor: grabbing; transform: scale(1.1); }
.canvas-item.selected .item-icon { box-shadow: 0 0 0 3px #f9e2af; border-color: #f9e2af; }
.item-icon { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; border: 2px solid transparent; background: #11111b; box-shadow: 0 4px 6px rgba(0,0,0,0.3);}
.item-name { font-size: 11px; color: #cdd6f4; margin-top: 5px; font-weight: bold; text-shadow: 0 1px 2px #000; background: rgba(17,17,27,0.8); padding: 2px 6px; border-radius: 4px; white-space: nowrap;}

/* 🌟 冻存架侧视图 (Rack Shelf) */
.rack-shelf-view { width: 100%; flex: 1; padding: 30px; display: flex; justify-content: center; overflow-y: auto;}
.rack-frame { background: #181825; border: 4px solid #45475a; border-radius: 10px; padding: 10px; width: 100%; max-width: 600px; display: grid; gap: 10px;}
.rack-layer { background: #11111b; border: 1px solid #313244; border-radius: 6px; display: flex; align-items: center; padding: 10px;}
.layer-label { width: 40px; text-align: center; font-weight: bold; color: #89b4fa; font-size: 18px; border-right: 1px dashed #45475a; margin-right: 15px;}
.layer-boxes { flex: 1; display: grid; gap: 15px;}
.rack-box-slot { background: #1e1e2e; border: 1px solid #45475a; border-radius: 6px; height: 60px; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: 0.2s;}
.rack-box-slot:hover { border-color: #f9e2af; background: rgba(249, 226, 175, 0.1); transform: translateY(-2px);}
.box-icon { font-size: 24px;}
.box-name { font-size: 12px; color: #bac2de; margin-top: 5px; font-weight: bold;}

/* 标准网格 */
.well-board { display: grid; gap: 8px; width: 100%; max-width: 550px;}
.well-cell.square { background: #181825; aspect-ratio: 1; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 13px; color: #6c7086; cursor: pointer; border: 1px solid #313244; transition: 0.1s;}
.well-cell.square:hover { border-color: #89b4fa; background: #1e1e2e;}
.well-cell.square.selected { border-color: #f9e2af; box-shadow: 0 0 12px rgba(249,226,175,0.2); transform: scale(1.05);}
.well-cell.square.filled { background: #89b4fa; color: #11111b; font-weight: bold; border-color: #89b4fa;}

/* 侧边参数面板 */
.panel-container { flex: 1; max-width: 350px; background: #181825; padding: 20px; border-radius: 12px; border: 1px solid #313244; overflow-y: auto;}
.info-group { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px dashed #313244;}
.info-group label { color: #a6adc8; font-weight: bold; flex-shrink: 0;}
.value { font-family: monospace; padding: 4px 10px; border-radius: 6px; font-weight: bold; background: #11111b; text-align: right;}
.value.highlight { color: #f9e2af; font-size: 16px;}
.log-box { width: 100%; height: 100px; background: #11111b; border: 1px solid #313244; border-radius: 6px; padding: 10px; color: #a6adc8; font-size: 12px; font-family: monospace; overflow-y: auto; white-space: pre-wrap; box-sizing: border-box;}
.actions-group { margin-top: 30px;}
.empty-state { text-align: center; padding: 40px 20px;}

/* 弹窗表格与其他 */
.bulk-table { width: 100%; border-collapse: collapse; margin-top: 15px;}
.bulk-table th { color: #89b4fa; text-align: left; padding: 8px; border-bottom: 1px solid #313244;}
.bulk-table td { padding: 8px; border-bottom: 1px dashed #313244;}
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