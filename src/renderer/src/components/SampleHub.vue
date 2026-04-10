<template>
  <div class="sample-hub-view fade-in">
    <div class="view-header">
      <div class="breadcrumbs">
        <h2 @click="navTo(0)" :class="{ active: currentLevel === 0 }">🧪 物理样本库</h2>
        <template v-if="currentLevel > 0"><span class="separator">/</span><h2 @click="navTo(1)" :class="{ active: currentLevel === 1 }">{{ currentEq?.name }}</h2></template>
        
        <template v-if="currentLevel > 2">
          <span class="separator">/</span>
          <h2 @click="exitToContainer" :class="{ active: currentLevel === 2 && !currentSubBox }">
            {{ currentContainer?.name }}
          </h2>
        </template>
        
        <template v-if="currentSubBox">
          <span class="separator">/</span><h2 class="active">{{ currentSubBox.name }}</h2>
        </template>
      </div>
      <div class="header-actions">
        <button v-if="currentLevel === 1" class="btn-outline" :class="{ 'is-editing': isEditMode }" @click="toggleEditMode">
          {{ isEditMode ? '🔒 锁定物理布局' : '🔓 解锁布局编辑' }}
        </button>
        <button v-if="currentLevel === 0" class="btn-primary" @click="showEqForm = true">➕ 新增设备</button>
        <button class="btn-primary" @click="fetchTopology">🔄 同步数据</button>
      </div>
    </div>

    <div class="equipments-grid" v-if="currentLevel === 0">
      <div v-for="(eq, id) in equipments" :key="id" class="card eq-card fade-in" @click="enterEquipment(id as string, eq)">
        <div class="eq-header" style="justify-content: space-between;">
          <div style="display: flex; align-items: center;">
            <div class="eq-icon-wrapper"><span class="eq-icon">{{ getIcon(eq.icon) }}</span></div>
            <div class="eq-title"><h3>{{ eq.name }}</h3><div class="eq-status"><span class="status-dot"></span> 在线</div></div>
          </div>
          <button class="btn-icon-del" style="font-size: 16px; margin-bottom: auto;" @click.stop="deleteEquipment(id as string)" title="拆除此设备">🗑️</button>
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
        <div class="resize-panel fade-in" style="margin-bottom: 20px;">
          <h4>📐 调整设备网格边界</h4>
          <div class="size-controls">
            <div class="control-row"><label>宽度 (列数)</label><button class="icon-btn" @click="updateEqSize(0, -1)">-</button><span>{{ currentEq.cols }}</span><button class="icon-btn" @click="updateEqSize(0, 1)">+</button></div>
            <div class="control-row"><label>高度 (行数)</label><button class="icon-btn" @click="updateEqSize(-1, 0)">-</button><span>{{ currentEq.rows }}</span><button class="icon-btn" @click="updateEqSize(1, 0)">+</button></div>
          </div>
        </div>
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
               <h3 style="margin:0;">{{ currentSubBox ? currentSubBox.name : currentContainer?.name }}</h3>
               <span style="font-size: 12px; color: #a6adc8;" v-if="!isCanvasMode && currentContainer?.type !== 'rack'">💡 提示: 按 <b>Ctrl+V</b> 粘贴 Excel 数据大批量入库</span>
             </div>
             <div style="display: flex; gap: 10px; align-items: center;">
               <span class="tag">{{ currentSubBox ? getSpecLabel(currentSubBox.spec) : currentContainer?.type }}</span>
               <button v-if="!isCanvasMode && currentContainer?.type !== 'rack'" class="btn-primary" @click="autoAddSample" style="padding: 4px 12px; font-size: 13px;">➕ 自动寻空位</button>
             </div>
           </div>
           
           <div v-if="isCanvasMode" 
                class="infinite-canvas-viewport" 
                @wheel.prevent="handleCanvasZoom"
                @mousedown.middle.prevent="startCanvasPan"
                @mousemove="doCanvasPan"
                @mouseup="endCanvasPan"
                @mouseleave="endCanvasPan"
                @dragover.prevent 
                @drop="onCanvasDrop">
              <div class="canvas-hint" style="z-index: 10;">自由画布 <br> 🖱️ 中键平移 | ⚙️ 滚轮缩放 | 🖱️ 双击空白新增 | 🖱️ 双击容器潜入</div>
              <div class="canvas-controls">
                 <span style="font-size: 12px; color: #a6adc8;">📦 图标缩放:</span>
                 <input type="range" v-model="iconBaseSize" min="20" max="100" step="2" class="custom-range allow-select" @mousedown.stop>
                 <span style="font-size: 12px; color: #a6adc8; width: 30px; text-align: right;">{{ iconBaseSize }}px</span>
              </div>
              <div class="canvas-transform-layer" :style="{ transform: `translate(${canvasPan.x}px, ${canvasPan.y}px) scale(${canvasScale})` }">
                <div class="canvas-grid-bg" @dblclick.self="handleCanvasDoubleClick"></div> 
                <div v-for="(item, key) in boxData" :key="key" 
                     class="canvas-item" 
                     :class="{ 'selected': selectedWell === key }" 
                     :style="{ left: `${item.x}px`, top: `${item.y}px` }" 
                     draggable="true" 
                     @dragstart="onItemDragStart($event, key as string)" 
                     @click.stop="selectWell(key as string)"
                     @dblclick.stop="handleItemDoubleClick(key as string, item)">
                  <div class="item-icon" :class="[getSampleColorClass(item), getShapeClass(item)]" 
                       :style="{ width: (item.size || 44) + 'px', height: (item.size || 44) + 'px', fontSize: ((item.size || 44) / 2) + 'px' }">
                    {{ getItemIcon(item) }}
                  </div>
                  <div class="item-name">{{ item.name }}</div>
                </div>
              </div>
           </div>

           <div v-else-if="currentContainer?.type === 'rack' && !currentSubBox" class="rack-shelf-view">
             <div class="rack-frame-vertical">
                <div v-for="layer in (currentContainer.layers || 5)" :key="'layer'+layer" class="rack-layer-col">
                  
                  <div class="layer-boxes-vertical">
                    <div v-for="col in (currentContainer.boxes || 4)" :key="'box'+layer+'-'+col" 
                         class="rack-box-slot" 
                         :class="{ 'selected': selectedWell === `L${layer}-C${col}`, 'filled': boxData[`L${layer}-C${col}`] }"
                         @click="selectWell(`L${layer}-C${col}`)"
                         @dblclick="handleItemDoubleClick(`L${layer}-C${col}`, boxData[`L${layer}-C${col}`] || { name: `未命名盒子 ${col}`, unit: 'box_9x9', type: '🧊 冻存盒/标本盒 (Box)' })">
                      <span class="box-icon">📦</span>
                      <span class="box-name">{{ boxData[`L${layer}-C${col}`]?.name || `空位 ${col}` }}</span>
                    </div>
                  </div>

                  <div class="rack-handle-bottom">
                    <div class="grip"></div>
                    <span>L{{ layer }} 层</span>
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

        <div class="resize-handle" v-if="selectedWell" @mousedown.prevent="startResize" :class="{ active: isResizing }"></div>

        <transition name="slide-fade">
          <div class="panel-container card" v-if="selectedWell" :style="{ width: rightPanelWidth + 'px', flexBasis: rightPanelWidth + 'px' }">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed #313244; padding-bottom: 12px; margin-bottom: 15px;">
              <h3 style="margin: 0; color: #cba6f7;">资产追踪参数</h3>
              <button class="btn-close" style="position: static; font-size: 16px; color: #a6adc8;" @click="selectedWell = null" title="关闭面板">✖</button>
            </div>
            
            <div class="sample-info fade-in">
              <div class="info-group"><label>映射标识</label><div class="value highlight">[{{ selectedWell }}]</div></div>
              <div class="info-group"><label>占位状态</label><div class="value" :class="getWellStatus(selectedWell) === 'empty' ? '' : 'success'">{{ getWellStatus(selectedWell) === 'empty' ? '空闲' : '已录入' }}</div></div>
              
              <template v-if="getWellStatus(selectedWell) !== 'empty'">
                <div class="info-group"><label>名称</label><div class="value">{{ boxData[selectedWell]?.name || '未知资产' }}</div></div>
                <div class="info-group"><label>类别</label><div class="value">{{ boxData[selectedWell]?.type || '未知' }}</div></div>
                
                <div class="info-group"><label>{{ isContainerItem(boxData[selectedWell]) ? '全局规格节点' : '当前余量/数量' }}</label>
                  <div class="value" style="color: #a6e3a1;">
                    {{ isContainerItem(boxData[selectedWell]) ? getSpecLabel(boxData[selectedWell]?.unit) : (boxData[selectedWell]?.vol + ' ' + boxData[selectedWell]?.unit) }}
                  </div>
                </div>
                
                <div class="info-group" v-if="isConsumableItem(boxData[selectedWell]) && boxData[selectedWell]?.exp"><label>效期/批号</label><div class="value">{{ boxData[selectedWell].exp }}</div></div>
                <div class="info-group" v-if="isSampleItem(boxData[selectedWell]) && !isContainerItem(boxData[selectedWell])"><label>冻融(F/T)</label><div class="value" :class="boxData[selectedWell]?.ft >= 5 ? 'id-value' : ''">{{ boxData[selectedWell]?.ft || 0 }} 次</div></div>
                <div class="info-group" v-if="boxData[selectedWell]?.temp"><label>环境温度</label><div class="value" style="color: #89b4fa;">🌡️ {{ boxData[selectedWell].temp }}</div></div>

                <div class="tags-insight-section">
                  <div class="tags-header">
                     <span style="font-size: 12px; font-weight: bold; color: #bac2de;">🏷️ 资产全局标签</span>
                     <button class="add-tag-btn" @click.stop="openTagModal">+ 添加映射</button>
                  </div>
                  <div class="tags-container">
                     <div v-if="currentSampleTags.length === 0" style="color: #6c7086; font-size: 11px;">未分配任何全局标签。</div>
                     <div v-for="tag in currentSampleTags" :key="tag.id" class="file-tag" :style="{ borderColor: tag.color, color: tag.color, background: `${tag.color}22` }">
                       {{ tag.label }}
                       <span class="tag-close" @click.stop="toggleSampleTag(tag.id)">✖</span>
                     </div>
                  </div>
                </div>

                <div class="info-group" v-if="isCanvasMode" style="border-top: 1px dashed #313244;">
                  <label style="color: #f9e2af;">📐 画布显示大小</label>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <input type="range" v-model.number="boxData[selectedWell].size" min="20" max="200" step="2" class="custom-range allow-select" @change="saveItemState(selectedWell as string)">
                    <span class="value" style="background: transparent; padding: 0;">{{ boxData[selectedWell]?.size || 44 }}px</span>
                  </div>
                </div>

                <div class="info-group" style="flex-direction: column; align-items: flex-start; border: none; padding-top: 15px;">
                   <label style="margin-bottom: 5px;">追溯日志 / 备注</label>
                   <div class="log-box allow-select">{{ boxData[selectedWell]?.notes || '无记录' }}</div>
                </div>
              </template>
              
              <div class="actions-group">
                <button class="btn-primary w-full" v-if="getWellStatus(selectedWell) === 'empty'" @click="triggerAddSample">📥 确认为其录入</button>
                <template v-else>
                  <div style="text-align: center; color: #a6adc8; font-size: 11px; margin-bottom: 10px;" v-if="isContainerItem(boxData[selectedWell])">💡 提示：在左侧双击该容器即可潜入内部</div>
                  <button class="btn-purple w-full" @click="triggerCheckout" style="margin-bottom: 10px;">📉 取用登记 (耗材追溯)</button>
                  <button class="btn-danger w-full" @click="removeSample">🗑️ 彻底报废清除</button>
                </template>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </div>

    <div v-if="showTagModal" class="modal-overlay fade-in" @click.self="showTagModal = false; showNewTagForm = false;">
      <div class="modal-content fade-in-scale" style="width: 450px; height: auto;">
        
        <div v-if="!showNewTagForm">
           <div class="modal-header">
             <div class="modal-title">🏷️ 关联全局字典标签</div>
             <button class="btn-close" @click="showTagModal = false">✖</button>
           </div>
           <div class="modal-body" style="max-height: 400px; overflow-y: auto; padding: 20px;">
             <div class="tag-section-title">📂 项目课题 (Projects)</div>
             <div class="tag-pool">
                <div v-for="tag in globalMeta.tags.projects" :key="tag.id" class="pool-tag" 
                     :class="{ active: currentSampleTagIds.includes(tag.id) }"
                     :style="{ borderColor: tag.color, color: currentSampleTagIds.includes(tag.id) ? '#11111b' : tag.color, background: currentSampleTagIds.includes(tag.id) ? tag.color : 'transparent' }"
                     @click="toggleSampleTag(tag.id)">
                  {{ tag.label }}
                </div>
             </div>
             
             <div class="tag-section-title" style="margin-top: 15px;">🧪 实验类型 (Experiments)</div>
             <div class="tag-pool">
                <div v-for="tag in globalMeta.tags.experiments" :key="tag.id" class="pool-tag" 
                     :class="{ active: currentSampleTagIds.includes(tag.id) }"
                     :style="{ borderColor: tag.color, color: currentSampleTagIds.includes(tag.id) ? '#11111b' : tag.color, background: currentSampleTagIds.includes(tag.id) ? tag.color : 'transparent' }"
                     @click="toggleSampleTag(tag.id)">
                  {{ tag.label }}
                </div>
             </div>

             <div class="tag-section-title" style="margin-top: 15px;">🔖 自定义与其他 (Others)</div>
             <div class="tag-pool">
                <div v-for="tag in globalMeta.tags.others" :key="tag.id" class="pool-tag" 
                     :class="{ active: currentSampleTagIds.includes(tag.id) }"
                     :style="{ borderColor: tag.color, color: currentSampleTagIds.includes(tag.id) ? '#11111b' : tag.color, background: currentSampleTagIds.includes(tag.id) ? tag.color : 'transparent' }"
                     @click="toggleSampleTag(tag.id)">
                  {{ tag.label }}
                </div>
             </div>
           </div>
           <div class="modal-footer" style="justify-content: space-between; padding: 12px 20px;">
              <button class="btn-outline" style="border-style: dashed; padding: 6px 12px; font-size: 12px;" @click="showNewTagForm = true">➕ 新建全局标签</button>
              <button class="btn-primary" style="padding: 6px 15px; font-size: 12px;" @click="showTagModal = false">完成选择</button>
           </div>
        </div>

        <div v-else>
           <div class="modal-header">
             <div class="modal-title">➕ 扩充全局标签库</div>
             <button class="btn-close" @click="showNewTagForm = false; showTagModal = false;">✖</button>
           </div>
           <div class="modal-body" style="padding: 20px;">
              <div class="form-group">
                 <label>归属大类:</label>
                 <select v-model="newTag.category" class="input-dark allow-select">
                   <option value="projects">📂 项目课题 (Projects)</option>
                   <option value="experiments">🧪 实验类型 (Experiments)</option>
                   <option value="others">🔖 其他类别 (Others)</option>
                 </select>
              </div>
              <div class="form-group">
                 <label>标签名称 (支持带 Emoji):</label>
                 <input type="text" v-model="newTag.label" class="input-dark allow-select" placeholder="例如: 🧬 P53重组蛋白...">
              </div>
              <div class="form-group">
                 <label>主题配色:</label>
                 <div style="display: flex; gap: 10px; margin-top: 5px;">
                   <div v-for="c in colorPalette" :key="c" class="color-picker-dot" 
                        :style="{ background: c, border: newTag.color === c ? '2px solid #ffffff' : '2px solid transparent' }"
                        @click="newTag.color = c"></div>
                 </div>
              </div>
           </div>
           <div class="modal-footer" style="padding: 12px 20px;">
              <button class="btn-outline" style="padding: 6px 15px; font-size: 12px;" @click="showNewTagForm = false">返回上级</button>
              <button class="btn-primary" style="padding: 6px 15px; font-size: 12px;" @click="submitNewTag">💾 保存至全局字典</button>
           </div>
        </div>
      </div>
    </div>

    <div v-if="showEqForm" class="modal-overlay" @click.self="showEqForm = false">
      <div class="modal-content fade-in-scale" style="width: 420px; border-color: #89b4fa;">
        <div class="modal-header">
          <div class="modal-title">➕ 新增物理设备</div>
          <button class="btn-close" @click="showEqForm = false">✖</button>
        </div>
        <div class="modal-body">
          <div class="form-group"><label>设备名称</label><input v-model="eqForm.name" class="input-dark allow-select" placeholder="例如: -80℃超低温冰箱"></div>
          <div class="form-group"><label>用途与作用</label><input v-model="eqForm.desc" class="input-dark allow-select" placeholder="例如: 长期存放细胞株与核酸"></div>
          <div class="form-group-row">
            <div class="form-group"><label>内部边界 (行数)</label><input type="number" v-model="eqForm.rows" class="input-dark allow-select"></div>
            <div class="form-group"><label>内部边界 (列数)</label><input type="number" v-model="eqForm.cols" class="input-dark allow-select"></div>
          </div>
        </div>
        <div class="modal-footer"><button class="btn-outline" @click="showEqForm = false">取消</button><button class="btn-primary" @click="confirmAddEq">确认安装</button></div>
      </div>
    </div>

    <div v-if="showCheckoutForm" class="modal-overlay" @click.self="showCheckoutForm = false">
      <div class="modal-content fade-in-scale" style="width: 420px; border-color: #cba6f7;">
        <div class="modal-header">
          <div class="modal-title" style="color: #cba6f7;">📉 取用登记 ({{ selectedWell }})</div>
          <button class="btn-close" @click="showCheckoutForm = false">✖</button>
        </div>
        <div class="modal-body">
          <p class="form-hint">系统将自动扣减存量，如为生物样本则自动增加冻融次数 (F/T)。</p>
          <div class="form-group-row">
            <div class="form-group"><label>消耗数量/体积</label><input type="number" v-model="checkoutData.vol" class="input-dark allow-select"></div>
            <div class="form-group"><label>单位</label><input disabled :value="isContainerItem(boxData[selectedWell as string]) ? '个' : boxData[selectedWell as string]?.unit" class="input-dark disabled-input allow-select"></div>
          </div>
          <div class="form-group"><label>操作人</label><input v-model="checkoutData.operator" class="input-dark allow-select"></div>
          <div class="form-group"><label>附言</label><input v-model="checkoutData.notes" class="input-dark allow-select" placeholder="消耗原因..."></div>
        </div>
        <div class="modal-footer"><button class="btn-outline" @click="showCheckoutForm = false">取消</button><button class="btn-purple" @click="confirmCheckout">确认取用</button></div>
      </div>
    </div>

    <div v-if="showBulkImportForm" class="modal-overlay" @click.self="showBulkImportForm = false">
      <div class="modal-content fade-in-scale" style="width: 700px; max-height: 85vh;">
        <div class="modal-header"><div class="modal-title">🚀 剪贴板批量高通量导入</div><button class="btn-close" @click="showBulkImportForm = false">✖</button></div>
        <div class="modal-body" style="overflow-y: auto;">
          <table class="bulk-table">
            <thead><tr><th>映射孔位</th><th>识别资产名</th><th>大类(默认)</th><th>初始余量</th></tr></thead>
            <tbody>
              <tr v-for="(item, idx) in bulkPreviewData" :key="idx">
                <td style="color: #f9e2af; font-weight: bold; width: 80px;">[{{ item.well_index }}]</td>
                <td><input v-model="item.sample_name" class="input-dark allow-select" style="padding: 6px; font-size: 13px; width: 100%;"></td>
                <td>
                  <select v-model="item.sample_type" class="input-dark allow-select" style="padding: 6px; font-size: 13px; width: 100%;">
                    <option>🧬 质粒/核酸 (Plasmid/DNA)</option><option>🧪 蛋白 (Protein)</option><option>🧫 细胞株 (Cell)</option><option>📦 散装耗材 (Consumables)</option>
                  </select>
                </td>
                <td style="display: flex; align-items: center; gap: 5px;">
                  <input type="number" v-model="item.vol" class="input-dark allow-select" style="width: 70px; padding: 6px; font-size: 13px;"> 
                  <span style="color: #a6adc8; font-size: 12px;">μL</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-footer"><button class="btn-outline" @click="showBulkImportForm = false">放弃导入</button><button class="btn-primary" @click="confirmBulkImport">确认全量入库</button></div>
      </div>
    </div>

    <div v-if="showContainerForm" class="modal-overlay" @click.self="showContainerForm = false">
      <div class="modal-content fade-in-scale" style="width: 420px;">
        <div class="modal-header">
          <div class="modal-title">📦 划拨设备大分区</div>
          <button class="btn-close" @click="showContainerForm = false">✖</button>
        </div>
        <div class="modal-body">
          <div class="form-group"><label>分区名称</label><input v-model="containerForm.name" class="input-dark allow-select" placeholder="例如: 蛋白暂存区 A1"></div>
          <div class="form-group"><label>映射大类</label>
            <select v-model="containerForm.category" class="input-dark allow-select">
              <option value="rack">🧊 标准冻存架 (含抽屉与嵌套盒)</option>
              <option value="box">📦 独立标准冻存盒</option>
              <option value="holder">🧫 独立多孔板/试管架</option>
              <option value="freeform">📥 自由散装大抽屉 (2D画布，支持内部放盒子)</option>
            </select>
          </div>
          <div class="form-group" v-if="containerForm.category === 'rack'"><label>内部规格 (层 x 盒)</label><select v-model="containerForm.subSpec" class="input-dark allow-select"><option value="5x4">5层 × 每层4盒</option><option value="4x4">4层 × 每层4盒</option></select></div>
          <div class="form-group" v-if="containerForm.category === 'box' || containerForm.category === 'holder'">
             <label>关联全局规格节点</label>
             <select v-model="containerForm.subSpec" class="input-dark allow-select">
               <option v-for="spec in containerSpecs" :key="spec.id" :value="spec.id">{{ spec.label }}</option>
             </select>
          </div>
          <div class="form-group-row" v-if="containerForm.category === 'freeform'">
            <div class="form-group"><label>占据高(行)</label><input type="number" v-model="containerForm.rs" class="input-dark allow-select"></div>
            <div class="form-group"><label>占据宽(列)</label><input type="number" v-model="containerForm.cs" class="input-dark allow-select"></div>
          </div>
        </div>
        <div class="modal-footer"><button class="btn-outline" @click="showContainerForm = false">取消</button><button class="btn-primary" @click="confirmAddContainer">确定划拨</button></div>
      </div>
    </div>

    <div v-if="showSampleForm" class="modal-overlay" @click.self="showSampleForm = false">
      <div class="modal-content fade-in-scale" style="width: 460px;">
        <div class="modal-header">
          <div class="modal-title">📥 登记资产 ({{ selectedWell }})</div>
          <button class="btn-close" @click="showSampleForm = false">✖</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>资产名称/编号</label>
            <input v-model="formData.name" class="input-dark allow-select" placeholder="名称、批号或条码...">
          </div>
          <div class="form-group">
            <label>资产大类与形态</label>
            <select v-model="formData.type" class="input-dark allow-select">
              <option disabled style="color: #89b4fa; font-weight: bold;">--- 🧬 生物样本 ---</option>
              <option>🧬 质粒/核酸 (Plasmid/DNA/RNA)</option>
              <option>🧪 蛋白/纯化物 (Protein)</option>
              <option>🧫 细胞株/组织 (Cell/Tissue)</option>
              <option>🦠 菌株/甘油菌 (Bacteria)</option>
              <option disabled style="color: #89b4fa; font-weight: bold;">--- 🧊 嵌套容器 (支持双击潜入) ---</option>
              <option>🧊 冻存盒/标本盒 (Box)</option>
              <option>🪜 离心管架/试管架 (Tube Holder)</option>
              <option>🧫 96/384多孔板 (Well Plate)</option>
              <option disabled style="color: #89b4fa; font-weight: bold;">--- 📦 宏观耗材与试剂 ---</option>
              <option>📦 散装耗材/包材 (Consumables)</option>
              <option>💊 试剂/缓冲液 (Reagents)</option>
              <option>🔧 工具/仪器附件 (Tools)</option>
            </select>
          </div>
          
          <template v-if="isFormContainer">
            <div class="form-group-row">
              <div class="form-group" style="flex: 2;">
                <label style="color: #f9e2af;">🔗 关联全局容器配置节点</label>
                <select v-model="formData.unit" class="input-dark allow-select">
                  <option v-for="spec in containerSpecs" :key="spec.id" :value="spec.id">{{ spec.label }}</option>
                </select>
              </div>
            </div>
            <div class="form-group-row">
              <div class="form-group">
                <label>预设环境温度</label>
                <select v-model="formData.temp" class="input-dark allow-select">
                  <option>常温 (RT)</option><option>4℃</option><option>-20℃</option><option>-80℃</option><option>-196℃ (液氮)</option>
                </select>
              </div>
            </div>
          </template>
          
          <template v-else-if="isFormConsumable">
            <div class="form-group-row">
              <div class="form-group"><label>入库数量/体积</label><input type="number" v-model="formData.vol" class="input-dark allow-select"></div>
              <div class="form-group"><label>计量单位</label>
                <select v-model="formData.unit" class="input-dark allow-select">
                  <option>个</option><option>套</option><option>包</option><option>L</option><option>mL</option><option>盒</option>
                </select>
              </div>
            </div>
            <div class="form-group-row">
               <div class="form-group"><label>效期或批号</label><input v-model="formData.exp" class="input-dark allow-select" placeholder="如: 2028-12 或 Lot:XX"></div>
               <div class="form-group">
                <label>存放要求</label>
                <select v-model="formData.temp" class="input-dark allow-select">
                  <option>常温 (RT)</option><option>4℃</option><option>-20℃</option><option>-80℃</option>
                </select>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="form-group-row">
              <div class="form-group"><label>初始余量</label><input type="number" v-model="formData.vol" class="input-dark allow-select"></div>
              <div class="form-group"><label>单位</label>
                <select v-model="formData.unit" class="input-dark allow-select"><option>μL</option><option>mL</option><option>管</option></select>
              </div>
              <div class="form-group"><label>冻融(F/T)</label><input type="number" v-model="formData.ft" class="input-dark allow-select"></div>
            </div>
            <div class="form-group-row">
              <div class="form-group">
                <label>存放温度</label>
                <select v-model="formData.temp" class="input-dark allow-select">
                  <option>常温 (RT)</option><option>4℃</option><option>-20℃</option><option>-80℃</option><option>-196℃ (液氮)</option>
                </select>
              </div>
            </div>
          </template>
          
          <div class="form-group"><label>所有人/保管人</label><input v-model="formData.owner" class="input-dark allow-select"></div>
          <div class="form-group"><label>附言/备注</label><input v-model="formData.notes" class="input-dark allow-select" placeholder="选填..."></div>
        </div>
        <div class="modal-footer">
          <button class="btn-outline" @click="showSampleForm = false">取消</button>
          <button class="btn-primary" @click="confirmSaveSample">确认入库</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'

const rightPanelWidth = ref(350)
const isResizing = ref(false)

const startResize = (e: MouseEvent) => {
  isResizing.value = true
  document.body.style.userSelect = 'none' 
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
}

const handleResize = (e: MouseEvent) => {
  if (!isResizing.value) return
  let newWidth = window.innerWidth - e.clientX - 20
  if (newWidth < 280) newWidth = 280
  if (newWidth > 600) newWidth = 600
  rightPanelWidth.value = newWidth
}

const stopResize = () => {
  isResizing.value = false
  document.body.style.userSelect = ''
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
}

const containerSpecs = [
  { id: 'box_9x9', label: '🧊 9x9 标准冻存盒 (81孔)', rows: 9, cols: 9 },
  { id: 'box_10x10', label: '🧊 10x10 标准冻存盒 (100孔)', rows: 10, cols: 10 },
  { id: 'plate_96', label: '🧫 96孔板 (12x8)', rows: 8, cols: 12 },
  { id: 'plate_384', label: '🧫 384孔板 (16x24)', rows: 16, cols: 24 },
  { id: 'holder_15', label: '🪜 15孔离心管架 (5x3)', rows: 3, cols: 5 },
  { id: 'holder_24', label: '🪜 24孔离心管架 (6x4)', rows: 4, cols: 6 },
  { id: 'holder_50', label: '🪜 50孔离心管架 (10x5)', rows: 5, cols: 10 }
]

const getSpecLabel = (specId: string) => {
  const spec = containerSpecs.find(s => s.id === specId);
  return spec ? spec.label : specId;
}

const currentLevel = ref(0)
const equipments = ref<Record<string, any>>({})
const currentEqId = ref('')
const currentEq = ref<any>(null)
const currentContId = ref('')
const currentContainer = ref<any>(null)
const selectedWell = ref<string | null>(null)
const boxData = ref<Record<string, any>>({}) 

const currentRackBox = ref<{ layer: number, col: number } | null>(null)
const currentSubBox = ref<{ id: string, spec: string, name: string } | null>(null)

const isCanvasMode = computed(() => {
  return currentContainer.value?.type === 'freeform' && !currentSubBox.value;
})

const canvasScale = ref(1)
const canvasPan = ref({ x: 0, y: 0 })
const isCanvasPanning = ref(false)
const startPanCoords = ref({ x: 0, y: 0 })
const iconBaseSize = ref(44)

const dragItemKey = ref<string | null>(null)
const tempCanvasX = ref(20)
const tempCanvasY = ref(20)

const showSampleForm = ref(false); 
const formData = ref({ name: '', type: '', vol: 100, unit: '', ft: 0, owner: 'Admin', notes: '', size: 44, temp: '常温 (RT)', exp: '' })
const showContainerForm = ref(false); const containerForm = ref({ name: '', category: 'box', subSpec: 'box_10x10', rs: 1, cs: 1 })
const showCheckoutForm = ref(false); const checkoutData = ref({ vol: 1, operator: 'Admin', notes: '' })
const showBulkImportForm = ref(false); const bulkPreviewData = ref<any[]>([])
const isEditMode = ref(false); const draggedContId = ref<string | null>(null); const dragHoverIndex = ref<number | null>(null); const editingContId = ref<string | null>(null)

const showEqForm = ref(false)
const eqForm = ref({ name: '新冷冻塔', desc: '用于长期存储', rows: 5, cols: 5, icon: 'tiles' })

const globalMeta = ref({
  tags: { projects: [], experiments: [], others: [] },
  file_tags: {}
})

const showTagModal = ref(false)
const showNewTagForm = ref(false)
const newTag = ref({ category: 'projects', label: '', color: '#89b4fa' })
const colorPalette = ['#f9e2af', '#a6e3a1', '#89b4fa', '#cba6f7', '#f38ba8', '#94e2d5']

const currentSamplePath = computed(() => {
  if (!selectedWell.value) return ''
  return `${getActualBoxId()}/${selectedWell.value}`
})

const currentSampleTagIds = computed(() => {
  if (!currentSamplePath.value) return []
  return globalMeta.value.file_tags[currentSamplePath.value] || []
})

const currentSampleTags = computed(() => {
  const ids = currentSampleTagIds.value
  const allTags = [...globalMeta.value.tags.projects, ...globalMeta.value.tags.experiments, ...globalMeta.value.tags.others]
  return ids.map(id => allTags.find(t => t.id === id)).filter(Boolean)
})

const fetchMeta = async () => {
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/data/meta`)
    const json = await res.json()
    if (json.code === 200) globalMeta.value = json.data
  } catch (e) { console.error("无法加载元数据字典") }
}

const openTagModal = () => { showTagModal.value = true; showNewTagForm.value = false; }

const toggleSampleTag = async (tagId: string) => {
  if (!currentSamplePath.value) return
  const path = currentSamplePath.value
  let currentTags = [...(globalMeta.value.file_tags[path] || [])]
  
  if (currentTags.includes(tagId)) currentTags = currentTags.filter(t => t !== tagId)
  else currentTags.push(tagId)

  globalMeta.value.file_tags[path] = currentTags
  
  try {
    await fetch(`http://127.0.0.1:8080/api/data/meta/file/update`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, tags: currentTags })
    })
  } catch (e) { console.error("标签同步失败") }
}

const submitNewTag = async () => {
  if (!newTag.value.label.trim()) return alert("请输入标签名称！")
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/data/meta/tag/add`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newTag.value)
    })
    const json = await res.json()
    if (res.ok && json.code === 200) {
      globalMeta.value = json.data
      showNewTagForm.value = false
      newTag.value = { category: 'projects', label: '', color: '#89b4fa' } 
    }
  } catch (e) { alert("标签创建失败") }
}

const isContainerItem = (item: any) => {
  if (!item || !item.type) return false;
  return item.type.includes('盒') || item.type.includes('架') || item.type.includes('板');
}

const isConsumableItem = (item: any) => {
  if (!item || !item.type) return false;
  return item.type.includes('耗材') || item.type.includes('试剂') || item.type.includes('工具');
}

const isSampleItem = (item: any) => {
  if (!item || !item.type) return true; 
  return item.type.includes('质粒') || item.type.includes('核酸') || item.type.includes('蛋白') || item.type.includes('细胞') || item.type.includes('菌株');
}

const isFormContainer = computed(() => isContainerItem({ type: formData.value.type }));
const isFormConsumable = computed(() => isConsumableItem({ type: formData.value.type }));

const processBoxData = (data: any) => {
  for (let k in data) {
    let item = data[k];
    item.size = isContainerItem(item) ? 80 : 44; 
    item.temp = item.temp || '常温 (RT)';
    item.exp = item.exp || '';
    
    if (item.notes) {
       const sizeMatch = item.notes.match(/\[SIZE:(.*?)\]/);
       if (sizeMatch) { item.size = parseInt(sizeMatch[1]); item.notes = item.notes.replace(/\[SIZE:.*?\]\n?/g, ''); }

       const tempMatch = item.notes.match(/\[TEMP:(.*?)\]/);
       if (tempMatch) { item.temp = tempMatch[1]; item.notes = item.notes.replace(/\[TEMP:.*?\]\n?/g, ''); }

       const expMatch = item.notes.match(/\[EXP:(.*?)\]/);
       if (expMatch) { item.exp = expMatch[1]; item.notes = item.notes.replace(/\[EXP:.*?\]\n?/g, ''); }

       item.notes = item.notes.trim();
    }
  }
  return data;
}

const saveItemState = async (wid: string) => {
  const item = boxData.value[wid];
  if (!item) return;
  let finalNotes = item.notes || '';
  if (item.size && item.size !== 44) finalNotes += `\n[SIZE:${item.size}]`;
  if (item.temp && item.temp !== '常温 (RT)') finalNotes += `\n[TEMP:${item.temp}]`;
  if (item.exp) finalNotes += `\n[EXP:${item.exp}]`;
  finalNotes = finalNotes.trim();
  
  try {
    await fetch('http://127.0.0.1:8080/api/samples/add', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        box_id: getActualBoxId(), well_index: wid, sample_name: item.name, sample_type: item.type,
        vol: Number(item.vol) || 0, unit: item.unit, ft_count: Number(item.ft) || 0, owner: item.owner || 'Admin',
        notes: finalNotes, x: item.x, y: item.y
      })
    });
  } catch(e) { console.error('保存状态失败', e); }
}

const handleItemDoubleClick = (wid: string, item: any) => {
  if (isContainerItem(item)) {
    enterSubBox(wid, item);
  } else if (!item || getWellStatus(wid) === 'empty') {
    selectedWell.value = wid;
    triggerAddSample();
  }
}

const enterSubBox = async (wid: string, item: any) => {
  const spec = item?.unit && containerSpecs.some(s => s.id === item.unit) ? item.unit : 'box_9x9';
  currentSubBox.value = { id: wid, spec: spec, name: item?.name || `未命名容器 ${wid}` };
  selectedWell.value = null; canvasScale.value = 1; canvasPan.value = { x: 0, y: 0 };
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(getActualBoxId())}`);
    const json = await res.json();
    boxData.value = processBoxData(json.data || {});
  } catch(e) { console.error('加载子容器失败', e); }
}

const exitToContainer = async () => {
  currentSubBox.value = null; selectedWell.value = null;
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(getActualBoxId())}`);
    const json = await res.json();
    boxData.value = processBoxData(json.data || {});
  } catch(e) { console.error('退出容器失败', e); }
}

const getActualBoxId = () => {
  if (currentContainer.value?.type === 'rack' && currentRackBox.value && !currentSubBox.value) return `${currentEqId.value}/${currentContId.value}/L${currentRackBox.value.layer}-C${currentRackBox.value.col}`
  if (currentSubBox.value) return `${currentEqId.value}/${currentContId.value}/${currentSubBox.value.id}`
  return `${currentEqId.value}/${currentContId.value}`
}

const gridInfo = computed(() => {
  let rowsCount = 10, colsCount = 10;
  if (currentSubBox.value) {
     const spec = containerSpecs.find(s => s.id === currentSubBox.value?.spec);
     if (spec) { rowsCount = spec.rows; colsCount = spec.cols; }
  } else if (currentContainer.value?.type !== 'freeform' && currentContainer.value?.type !== 'rack') {
     const specStr = currentContainer.value?.type || 'box_10x10';
     const spec = containerSpecs.find(s => s.id === specStr);
     if (spec) { rowsCount = spec.rows; colsCount = spec.cols; }
  }
  let r: string[] = []; for(let i=0; i<rowsCount; i++) r.push(String.fromCharCode(65 + i));
  let cells: string[] = []; r.forEach(row => { for (let i = 1; i <= colsCount; i++) cells.push(`${row}${i}`) })
  return { rows: r, cols: colsCount, cells }
})

const findFreeGridSpace = (eq: any, rs: number, cs: number) => {
  const occupied = Array.from({length: eq.rows}, () => Array(eq.cols).fill(false));
  for (const cid in eq.containers) {
    const cont = eq.containers[cid];
    for(let i = cont.r; i < cont.r + cont.rs; i++) {
      for(let j = cont.c; j < cont.c + cont.cs; j++) {
        if (i < eq.rows && j < eq.cols) occupied[i][j] = true;
      }
    }
  }
  for (let i = 0; i <= eq.rows - rs; i++) {
    for (let j = 0; j <= eq.cols - cs; j++) {
      let canFit = true;
      for(let x = i; x < i + rs; x++) {
        for(let y = j; y < j + cs; y++) {
          if (occupied[x][y]) { canFit = false; break; }
        }
        if(!canFit) break;
      }
      if (canFit) return { r: i, c: j };
    }
  }
  return { r: 0, c: 0 };
}

const confirmAddEq = async () => {
  if (!eqForm.value.name || eqForm.value.name.trim() === '') return alert("请输入设备名称！");
  
  const newId = 'EQ_' + Date.now()
  try { 
    const res = await fetch('http://127.0.0.1:8080/api/samples/equipment/add', { 
        method:'POST', headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({id: newId, name: eqForm.value.name, desc: eqForm.value.desc, rows: Number(eqForm.value.rows) || 1, cols: Number(eqForm.value.cols) || 1, icon: eqForm.value.icon })
    });
    if (!res.ok) alert("保存设备失败: " + await res.text());
    else await fetchTopology();
  } catch(e){ alert("网络连接失败，请检查后端引擎是否开启"); }
  showEqForm.value = false
}

const deleteEquipment = async (id: string) => {
  if(!confirm("⚠️ 危险操作！确定要彻底拆除该设备及其内部的所有数字资产吗？")) return;
  try {
    const res = await fetch(`http://127.0.0.1:8080/api/samples/equipment/delete`, { 
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) 
    });
    if (res.ok) {
      if (currentEqId.value === id) { currentEqId.value = ''; currentEq.value = null; currentLevel.value = 0; }
      await fetchTopology();
    } else alert("删除设备失败: " + await res.text());
  } catch(e) { alert("网络错误"); }
}

const updateEqSize = async (dRow: number, dCol: number) => {
  if(!currentEq.value) return;
  currentEq.value.rows = Math.max(1, currentEq.value.rows + dRow); currentEq.value.cols = Math.max(1, currentEq.value.cols + dCol)
  try { await fetch('http://127.0.0.1:8080/api/samples/equipment/resize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: currentEqId.value, rows: currentEq.value.rows, cols: currentEq.value.cols }) }) } catch(e){}
}

const handleCanvasZoom = (e: WheelEvent) => { canvasScale.value = Math.min(Math.max(0.3, canvasScale.value - e.deltaY * 0.001), 3) }
const startCanvasPan = (e: MouseEvent) => { isCanvasPanning.value = true; startPanCoords.value = { x: e.clientX - canvasPan.value.x, y: e.clientY - canvasPan.value.y } }
const doCanvasPan = (e: MouseEvent) => { if (isCanvasPanning.value) { canvasPan.value.x = e.clientX - startPanCoords.value.x; canvasPan.value.y = e.clientY - startPanCoords.value.y } }
const endCanvasPan = () => { isCanvasPanning.value = false }

const getNonOverlappingPos = (startX: number, startY: number, itemSize: number) => {
  let x = startX, y = startY, hasCollision = true, attempts = 0;
  while (hasCollision && attempts < 50) {
    hasCollision = false;
    for (const k in boxData.value) {
      if (k === selectedWell.value) continue;
      const it = boxData.value[k];
      const itX = it.x || 0, itY = it.y || 0, itS = it.size || 44;
      if (x < itX + itS + 5 && x + itemSize + 5 > itX && y < itY + itS + 5 && y + itemSize + 5 > itY) {
        hasCollision = true; x += 25; y += 25; break;
      }
    }
    attempts++;
  }
  return { x, y };
};

const handleCanvasDoubleClick = (e: MouseEvent) => {
  if ((e.target as HTMLElement).closest('.canvas-item')) return;
  const viewport = document.querySelector('.infinite-canvas-viewport') as HTMLElement;
  if (!viewport) return;
  
  const rect = viewport.getBoundingClientRect();
  tempCanvasX.value = Math.round(((e.clientX - rect.left) - canvasPan.value.x) / canvasScale.value - 20);
  tempCanvasY.value = Math.round(((e.clientY - rect.top) - canvasPan.value.y) / canvasScale.value - 20);
  
  let newIdIndex = 1;
  while (boxData.value[`F-${newIdIndex}`]) { newIdIndex++; }
  selectedWell.value = `F-${newIdIndex}`;
  triggerAddSample();
}

const onItemDragStart = (e: DragEvent, key: string) => { dragItemKey.value = key; selectWell(key); if (e.dataTransfer) { e.dataTransfer.setData('text/plain', key); e.dataTransfer.setDragImage(e.target as Element, 20, 20) } }
const onCanvasDrop = async (e: DragEvent) => {
  if (!dragItemKey.value) return
  const wrapper = document.querySelector('.canvas-transform-layer') as HTMLElement
  if(!wrapper) return
  const rect = wrapper.getBoundingClientRect()
  const x = Math.round(((e.clientX - rect.left) - canvasPan.value.x) / canvasScale.value) - 20
  const y = Math.round(((e.clientY - rect.top) - canvasPan.value.y) / canvasScale.value) - 20
  
  if (boxData.value[dragItemKey.value]) { boxData.value[dragItemKey.value].x = x; boxData.value[dragItemKey.value].y = y }
  try { await fetch('http://127.0.0.1:8080/api/samples/move_item', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box_id: getActualBoxId(), well_index: dragItemKey.value, x, y }) }) } catch (e) {}
  dragItemKey.value = null
}

const enterRackBox = async (layer: number, col: number) => {
  currentRackBox.value = { layer, col }; selectedWell.value = null;
  try { boxData.value = processBoxData((await (await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(getActualBoxId())}`)).json()).data || {}) } catch (e) {}
}

const handlePaste = (e: ClipboardEvent) => {
  if (currentLevel.value !== 2 || isCanvasMode.value || (currentContainer.value?.type === 'rack' && !currentRackBox.value)) return
  if (showSampleForm.value || showContainerForm.value || showCheckoutForm.value) return 
  const text = e.clipboardData?.getData('text'); if (!text) return
  const names = text.split('\n').map(r => r.split('\t').map(c => c.trim()).filter(c => c)).flat().filter(n => n)
  if (names.length === 0) return
  const availableWells = gridInfo.value.cells.filter(wid => !boxData.value[wid])
  if (names.length > availableWells.length) { alert("容器空位不足！"); return }
  bulkPreviewData.value = names.map((name, idx) => ({ well_index: availableWells[idx], sample_name: name, sample_type: '🧬 质粒/核酸 (Plasmid/DNA)', vol: 100, unit: 'μL', ft_count: 0, owner: 'Admin', notes: 'Excel 批量导入', x: 0, y: 0 }))
  showBulkImportForm.value = true
}

const confirmBulkImport = async () => {
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/bulk_add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box_id: getActualBoxId(), samples: bulkPreviewData.value }) });
    if (res.ok) {
      if (currentSubBox.value) await enterSubBox(currentSubBox.value.id, currentSubBox.value)
      else await enterContainer(currentContId.value, currentContainer.value)
      showBulkImportForm.value = false
    } else alert("批量导入失败: " + await res.text());
  } catch (e) { alert("网络错误"); }
}

const getShapeClass = (item: any) => {
  const t = item?.type || '';
  if (t.includes('盒') || t.includes('架') || t.includes('板') || t.includes('耗材') || t.includes('工具') || t.includes('试剂')) return 'shape-square';
  return 'shape-circle';
}

const getItemIcon = (item: any) => {
  const t = item?.type || '';
  if (t.includes('细胞') || t.includes('组织')) return '🧫';
  if (t.includes('蛋白')) return '🧪';
  if (t.includes('菌株')) return '🦠';
  if (t.includes('冻存盒') || t.includes('标本盒')) return '🧊';
  if (t.includes('架')) return '🪜';
  if (t.includes('板')) return '🧫';
  if (t.includes('试剂') || t.includes('缓冲液')) return '💊';
  if (t.includes('耗材') || t.includes('包材')) return '📦';
  if (t.includes('工具') || t.includes('附件')) return '🔧';
  return '🧬'; 
}

const getSampleColorClass = (item: any) => {
  if (!item) return ''; const t = item.type || '';
  if (t.includes('蛋白')) return 'bg-protein'; 
  if (t.includes('质粒') || t.includes('核酸')) return 'bg-plasmid'; 
  if (t.includes('细胞') || t.includes('菌株')) return 'bg-cell'; 
  if (t.includes('试剂')) return 'bg-reagent'; 
  if (t.includes('耗材') || t.includes('架') || t.includes('盒') || t.includes('板') || t.includes('工具')) return 'bg-consumable'; 
  return 'bg-default';
}

const getIcon = (iconName: string) => { return { 'folder': '📁', 'tiles': '🧊', 'calendar': '🌡️', 'snowflake': '❄️' }[iconName] || '🗄️' }

const navTo = (level: number) => { 
  if (level <= currentLevel.value) { 
    currentLevel.value = level; isEditMode.value = false; selectedWell.value = null;
    if(level < 2) { currentRackBox.value = null; currentSubBox.value = null; }
  }
}

const fetchTopology = async () => { 
  try { 
    const res = await fetch('http://127.0.0.1:8080/api/samples/topology'); 
    if (res.ok) {
      equipments.value = (await res.json()).data
      if (currentEqId.value && equipments.value[currentEqId.value]) { currentEq.value = equipments.value[currentEqId.value] }
    } 
  } catch (e) { console.error("获取拓扑失败", e); } 
}

const enterEquipment = (id: string, eq: any) => { currentEqId.value = id; currentEq.value = eq; currentLevel.value = 1; isEditMode.value = false; }
const toggleEditMode = async () => { 
  isEditMode.value = !isEditMode.value; 
  editingContId.value = null; 
  if (!isEditMode.value) await fetchTopology(); 
}
const handleContainerClick = (cid: string, cont: any) => { if (isEditMode.value) editingContId.value = cid; else enterContainer(cid, cont) }

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

const triggerAddContainer = () => { containerForm.value = { name: '新容器', category: 'box', subSpec: 'box_10x10', rs: 1, cs: 1 }; showContainerForm.value = true }
const confirmAddContainer = async () => {
  if (!containerForm.value.name || containerForm.value.name.trim() === '') return alert("请输入分区名称！");

  let payload: any = { 
    equip_id: currentEqId.value, 
    name: containerForm.value.name, 
    type: containerForm.value.category === 'freeform' ? 'freeform' : containerForm.value.subSpec, 
    rs: Number(containerForm.value.rs) || 1, 
    cs: Number(containerForm.value.cs) || 1 
  }
  
  if (containerForm.value.category === 'rack') { 
    payload.type = 'rack'; 
    let parts = containerForm.value.subSpec.split('x'); 
    payload.layers = parseInt(parts[0]) || 5; 
    payload.boxes = parseInt(parts[1]) || 4;
  }
  
  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/container/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (res.ok) { 
       const json = await res.json();
       const newCid = json.data?.cid;
       
       if (newCid && payload.type !== 'rack') {
          const pos = findFreeGridSpace(currentEq.value, payload.rs, payload.cs);
          if (pos.r !== 0 || pos.c !== 0) {
             await fetch('http://127.0.0.1:8080/api/samples/container/move', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ equip_id: currentEqId.value, cid: newCid, r: pos.r, c: pos.c })
             });
          }
       }
       await fetchTopology(); 
       currentEq.value = equipments.value[currentEqId.value]; 
       showContainerForm.value = false 
    } else {
       alert("添加容器失败: " + await res.text());
    }
  } catch (e) { alert("网络异常"); }
}

const deleteContainer = async (cid: string) => { 
  if (!window.confirm("确定拆除此容器？")) return;
  try { 
    const res = await fetch(`http://127.0.0.1:8080/api/samples/container/delete`, { 
        method: 'POST', headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ equip_id: currentEqId.value, cid }) 
    });
    if (res.ok) { 
      editingContId.value = null;
      await fetchTopology();
    } else {
      alert("删除失败: " + await res.text());
    }
  } catch (e) { alert("网络错误"); } 
}

const enterContainer = async (cid: string, cont: any) => { 
  currentContId.value = cid; currentContainer.value = cont; currentLevel.value = 2; selectedWell.value = null; currentRackBox.value = null; currentSubBox.value = null;
  canvasScale.value = 1; canvasPan.value = { x: 0, y: 0 };
  if(cont.type === 'rack') return 
  try { boxData.value = processBoxData((await (await fetch(`http://127.0.0.1:8080/api/samples/${encodeURIComponent(getActualBoxId())}`)).json()).data || {}) } catch (e) {}
}

const getWellStatus = (wid: string) => { return boxData.value[wid] ? 'filled' : 'empty' }

const selectWell = (wid: string) => { 
  selectedWell.value = wid; 
  if (getWellStatus(wid) === 'empty' && !isCanvasMode.value && currentContainer.value?.type !== 'rack') {
    triggerAddSample() 
  }
}

const autoAddSample = () => { const firstEmpty = gridInfo.value.cells.find(wid => !boxData.value[wid]); if (firstEmpty) { selectedWell.value = firstEmpty; triggerAddSample() } else { alert("⚠️ 容器已满！") } }

const triggerAddSample = () => { 
  if (!selectedWell.value) return; 
  let defType = '🧬 质粒/核酸 (Plasmid/DNA/RNA)';
  let defUnit = 'μL';
  let defSize = 44;

  if (isCanvasMode.value) {
    defType = '📦 散装耗材/包材 (Consumables)';
    defUnit = '个';
    defSize = 80;
  } else if (currentContainer.value?.type === 'rack' && !currentSubBox.value) {
    defType = '🧊 冻存盒/标本盒 (Box)';
    defUnit = 'box_9x9';
    defSize = 80;
  }

  formData.value = { name: '', type: defType, vol: 1, unit: defUnit, ft: 0, owner: 'Admin', notes: '', size: defSize, temp: '常温 (RT)', exp: '' }; 
  showSampleForm.value = true 
}

const confirmSaveSample = async () => {
  if (!formData.value.name || formData.value.name.trim() === '') return alert("请输入资产名称！");

  if (isFormContainer.value && !containerSpecs.some(s => s.id === formData.value.unit)) formData.value.unit = 'box_9x9'; 
  
  let finalNotes = formData.value.notes || '';
  if (formData.value.size && formData.value.size !== 44) finalNotes += `\n[SIZE:${formData.value.size}]`;
  if (formData.value.temp && formData.value.temp !== '常温 (RT)') finalNotes += `\n[TEMP:${formData.value.temp}]`;
  if (formData.value.exp) finalNotes += `\n[EXP:${formData.value.exp}]`;
  finalNotes = finalNotes.trim();

  const finalVol = Number(formData.value.vol) || 0;
  const finalFt = Number(formData.value.ft) || 0;

  const isNew = !boxData.value[selectedWell.value as string];
  const targetSize = formData.value.size || (isFormContainer.value ? 80 : 44);
  if (isNew && isCanvasMode.value) {
     const pos = getNonOverlappingPos(tempCanvasX.value, tempCanvasY.value, targetSize);
     tempCanvasX.value = pos.x;
     tempCanvasY.value = pos.y;
  }

  try {
    const res = await fetch('http://127.0.0.1:8080/api/samples/add', { 
      method: 'POST', headers: { 'Content-Type': 'application/json' }, 
      body: JSON.stringify({ box_id: getActualBoxId(), well_index: selectedWell.value, sample_name: formData.value.name, sample_type: formData.value.type, vol: finalVol, unit: formData.value.unit, ft_count: finalFt, owner: formData.value.owner, notes: finalNotes, x: tempCanvasX.value, y: tempCanvasY.value }) 
    });
    
    if (res.ok) { 
      boxData.value[selectedWell.value as string] = { ...formData.value, vol: finalVol, ft: finalFt, notes: finalNotes, x: tempCanvasX.value, y: tempCanvasY.value }; 
      showSampleForm.value = false;
      tempCanvasX.value = 20; tempCanvasY.value = 20; 
    } else {
      alert("入库失败: " + await res.text());
    }
  } catch (e) {
    alert("网络请求失败");
  }
}

const removeSample = async () => { 
  if (!selectedWell.value || !window.confirm("确定彻底删除吗？")) return
  try { 
    const res = await fetch(`http://127.0.0.1:8080/api/samples/remove`, { 
        method: 'POST', headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ box_id: getActualBoxId(), well_index: selectedWell.value }) 
    });
    if (res.ok) { 
      delete boxData.value[selectedWell.value]; 
      selectedWell.value = null; 
    } else alert("删除失败: " + await res.text());
  } catch (e) { alert("网络错误"); }
}

const triggerCheckout = () => { if (!selectedWell.value) return; checkoutData.value = { vol: 1, operator: 'Admin', notes: '' }; showCheckoutForm.value = true }
const confirmCheckout = async () => {
  try {
    const finalVol = Number(checkoutData.value.vol) || 1;
    const res = await fetch('http://127.0.0.1:8080/api/samples/checkout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ box_id: getActualBoxId(), well_index: selectedWell.value, checkout_vol: finalVol, operator: checkoutData.value.operator, notes: checkoutData.value.notes }) })
    const json = await res.json()
    if (json.code === 200) { 
      boxData.value[selectedWell.value as string] = processBoxData({[selectedWell.value as string]: json.data})[selectedWell.value as string]; 
      showCheckoutForm.value = false 
    } else { alert(json.message) }
  } catch (e) { alert("取用失败"); }
}

onMounted(() => { fetchTopology(); fetchMeta(); window.addEventListener('paste', handlePaste) })
onUnmounted(() => { 
  window.removeEventListener('paste', handlePaste) 
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<style scoped>
/* 🚨 高亮防爆防线 */
input:not([type="checkbox"]), textarea, select, .allow-select,
:deep(input:not([type="checkbox"])), :deep(textarea), :deep(select) {
  -webkit-user-select: text !important;
  user-select: text !important;
  pointer-events: auto !important;
  cursor: text !important;
  -webkit-app-region: no-drag !important;
}

.sample-hub-view { height: 100%; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; color: #cdd6f4; user-select: none; }

.view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #313244; padding-bottom: 15px; flex-shrink: 0;}
.breadcrumbs { display: flex; gap: 10px; align-items: baseline;}
.breadcrumbs h2 { margin: 0; font-size: 22px; color: #6c7086; cursor: pointer; transition: 0.2s;}
.breadcrumbs h2:hover { color: #b4befe;}
.breadcrumbs h2.active { color: #89b4fa; font-weight: bold;}
.separator { color: #45475a; font-weight: bold;}

.header-actions { display: flex; gap: 15px; align-items: center; }

.btn-primary { background: #89b4fa; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s; flex-shrink: 0;}
.btn-purple { background: #cba6f7; color: #11111b; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; transition: 0.2s;}

/* 🚨 修复 btn-outline 的明亮文字对比度 */
.btn-outline { 
  background: transparent; 
  color: #bac2de; 
  border: 1px dashed #6c7086; 
  padding: 8px 15px; 
  border-radius: 8px; 
  cursor: pointer; 
  font-weight: bold; 
  transition: 0.2s;
  flex-shrink: 0;
}
.btn-outline:hover { 
  color: #89b4fa; 
  border-color: #89b4fa; 
  background: rgba(137, 180, 250, 0.1);
}
.btn-outline.is-editing { border-color: #f38ba8; color: #f38ba8; background: rgba(243, 139, 168, 0.1);}
.btn-danger { background: rgba(243, 139, 168, 0.1); color: #f38ba8; border: 1px solid #f38ba8; padding: 8px 15px; border-radius: 6px; cursor: pointer; transition: 0.2s;}
.btn-icon-del { background: transparent; border: none; color: #f38ba8; cursor: pointer; opacity: 0.5; transition: 0.2s;}
.btn-icon-del:hover { opacity: 1; transform: scale(1.2); }
.w-full { width: 100%; }

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
.resize-panel { background: #11111b; padding: 15px; border-radius: 8px; border: 1px solid #45475a;}
.control-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #bac2de; margin-bottom: 10px;}
.icon-btn { background: #313244; color: #cdd6f4; border: none; width: 28px; height: 28px; border-radius: 6px; cursor: pointer; font-weight: bold;}

.wells-view { flex: 1; min-height: 0; display: flex; flex-direction: column; height: 100%; }
.split-layout { display: flex; gap: 20px; flex: 1; min-height: 0; height: 100%; align-items: stretch; }
.grid-container { flex: 1; background: #11111b; border-radius: 12px; border: 1px solid #313244; display: flex; flex-direction: column; align-items: stretch; overflow: hidden; min-height: 0; height: 100%;}
.grid-header { display: flex; justify-content: space-between; align-items: center; width: 100%; flex-shrink: 0; z-index: 20; background: #11111b;}

/* 🚨 无极拖拽面板把手 (Resizer) */
.resize-handle { width: 8px; margin: 0 -4px; cursor: col-resize; z-index: 10; transition: background 0.2s; border-radius: 4px; }
.resize-handle:hover, .resize-handle.active { background: #89b4fa; }

/* 🌟 无极画布引擎 */
.infinite-canvas-viewport { width: 100%; flex: 1; min-height: 0; position: relative; overflow: hidden; background: #181825; border-top: 1px solid #313244; cursor: crosshair;}
.canvas-hint { position: absolute; top: 10px; left: 10px; color: #6c7086; font-size: 12px; font-weight: bold; pointer-events: none; background: rgba(17,17,27,0.7); padding: 5px 10px; border-radius: 6px;}

.canvas-controls { position: absolute; bottom: 20px; left: 20px; z-index: 10; background: rgba(17,17,27,0.8); padding: 10px 15px; border-radius: 8px; border: 1px solid #313244; display: flex; align-items: center; gap: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);}

.canvas-transform-layer { position: absolute; top: 0; left: 0; width: 5000px; height: 5000px; transform-origin: 0 0; transition: transform 0.05s linear; }
.canvas-grid-bg { width: 100%; height: 100%; background-image: linear-gradient(#313244 1px, transparent 1px), linear-gradient(90deg, #313244 1px, transparent 1px); background-size: 40px 40px; opacity: 0.3;}
.canvas-item { position: absolute; display: flex; flex-direction: column; align-items: center; cursor: grab; padding: 5px; z-index: 10;}
.canvas-item:active { cursor: grabbing; transform: scale(1.1); }
.canvas-item.selected .item-icon { box-shadow: 0 0 0 4px #f9e2af; border-color: #f9e2af; }

.item-icon { display: flex; align-items: center; justify-content: center; border: 2px solid transparent; background: #11111b; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);}
.shape-circle { border-radius: 50%; }
.shape-square { border-radius: 8px; }

.item-name { font-size: 11px; color: #cdd6f4; margin-top: 5px; font-weight: bold; text-shadow: 0 1px 2px #000; background: rgba(17,17,27,0.8); padding: 2px 6px; border-radius: 4px; white-space: nowrap;}

/* 🚨 拟物化冻存架：绝对竖排，把手朝下 */
.rack-shelf-view { width: 100%; flex: 1; padding: 30px; display: flex; justify-content: center; overflow-x: auto; overflow-y: auto;}
.rack-frame-vertical { display: flex; gap: 20px; padding: 20px; background: #181825; border: 4px solid #45475a; border-radius: 12px; align-items: flex-end;}
.rack-layer-col { display: flex; flex-direction: column; align-items: center; gap: 10px; background: #11111b; padding: 10px; border-radius: 8px; border: 1px solid #313244; box-shadow: inset 0 0 10px rgba(0,0,0,0.5);}

.layer-boxes-vertical { display: flex; flex-direction: column-reverse; gap: 10px; }

.rack-handle-bottom { width: 100%; height: 40px; background: #313244; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; display: flex; justify-content: center; align-items: center; border-bottom: 5px solid #89b4fa; color: #a6adc8; font-weight: bold; margin-top: 10px; position: relative;}
.rack-handle-bottom .grip { position: absolute; width: 40px; height: 8px; border-top: 2px solid #45475a; border-bottom: 2px solid #45475a; top: 4px; border-radius: 2px;}

.rack-box-slot { background: #1e1e2e; border: 1px solid #45475a; border-radius: 6px; height: 60px; width: 75px; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: 0.2s;}
.rack-box-slot:hover { border-color: #f9e2af; background: rgba(249, 226, 175, 0.1); transform: scale(1.02);}
.rack-box-slot.selected { border-color: #f9e2af; box-shadow: 0 0 12px rgba(249,226,175,0.4); transform: scale(1.05); background: rgba(249, 226, 175, 0.1);}
.rack-box-slot.filled { background: rgba(137, 180, 250, 0.1); border-color: #89b4fa; }

.box-icon { font-size: 20px;}
.box-name { font-size: 11px; color: #bac2de; margin-top: 5px; font-weight: bold; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 90%;}

.well-board { display: grid; gap: 8px; width: 100%; max-width: 550px;}
.well-cell.square { background: #181825; aspect-ratio: 1; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 13px; color: #6c7086; cursor: pointer; border: 1px solid #313244; transition: 0.1s;}
.well-cell.square:hover { border-color: #89b4fa; background: #1e1e2e;}
.well-cell.square.selected { border-color: #f9e2af; box-shadow: 0 0 12px rgba(249,226,175,0.2); transform: scale(1.05);}
.well-cell.square.filled { background: #89b4fa; color: #11111b; font-weight: bold; border-color: #89b4fa;}

.panel-container { flex-shrink: 0; background: #181825; padding: 20px; border-radius: 12px; border: 1px solid #313244; overflow-y: auto; height: 100%; box-sizing: border-box;}
.info-group { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px dashed #313244;}
.info-group label { color: #a6adc8; font-weight: bold; flex-shrink: 0;}
.value { font-family: monospace; padding: 4px 10px; border-radius: 6px; font-weight: bold; background: #11111b; text-align: right; color: #cdd6f4;}
.value.highlight { color: #f9e2af; font-size: 16px;}
.log-box { width: 100%; height: 100px; background: #11111b; border: 1px solid #313244; border-radius: 6px; padding: 10px; color: #cdd6f4; font-size: 12px; font-family: monospace; overflow-y: auto; white-space: pre-wrap; box-sizing: border-box;}
.actions-group { margin-top: 30px;}

.custom-range { -webkit-appearance: none; width: 100px; background: transparent; -webkit-app-region: no-drag;}
.custom-range::-webkit-slider-thumb { -webkit-appearance: none; height: 14px; width: 14px; border-radius: 50%; background: #f9e2af; cursor: pointer; margin-top: -5px; }
.custom-range::-webkit-slider-runnable-track { width: 100%; height: 4px; cursor: pointer; background: #313244; border-radius: 2px; }

/* 🚨 紧凑版资产标签区 (Tags Insight) */
.tags-insight-section { display: flex; flex-direction: column; gap: 8px; background: #11111b; border: 1px solid #313244; border-radius: 8px; padding: 10px; flex-shrink: 0; margin-top: 10px;}
.tags-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed #313244; padding-bottom: 6px;}
.add-tag-btn { background: transparent; border: 1px dashed #45475a; color: #a6adc8; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 10px; font-weight: bold; transition: 0.2s;}
.add-tag-btn:hover { border-color: #89b4fa; color: #89b4fa;}
.tags-container { display: flex; flex-wrap: wrap; gap: 4px; }
.file-tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 6px; border-radius: 4px; border: 1px solid; font-size: 10px; font-weight: bold; }
.tag-close { cursor: pointer; opacity: 0.6; transition: 0.2s; font-size: 10px;}
.tag-close:hover { opacity: 1; color: #f38ba8 !important;}

/* 🚨 标签选择器弹窗特有样式 */
.tag-section-title { font-size: 12px; font-weight: bold; color: #a6adc8; margin-bottom: 8px;}
.tag-pool { display: flex; flex-wrap: wrap; gap: 6px; padding-bottom: 10px; border-bottom: 1px dashed #313244;}
.pool-tag { padding: 4px 8px; border-radius: 4px; border: 1px solid; font-size: 11px; font-weight: bold; cursor: pointer; transition: 0.2s;}
.pool-tag:hover { transform: scale(1.05); }

.color-picker-dot { width: 24px; height: 24px; border-radius: 50%; cursor: pointer; transition: 0.2s; box-sizing: border-box;}
.color-picker-dot:hover { transform: scale(1.2); }

/* 资产色彩映射 */
.well-cell.bg-protein, .item-icon.bg-protein { background: rgba(166, 227, 161, 0.2); border-color: #a6e3a1; color: #a6e3a1; }
.well-cell.bg-plasmid, .item-icon.bg-plasmid { background: rgba(243, 139, 168, 0.2); border-color: #f38ba8; color: #fab387; }
.well-cell.bg-cell, .item-icon.bg-cell { background: rgba(203, 166, 247, 0.2); border-color: #cba6f7; color: #cba6f7; }
.well-cell.bg-consumable, .item-icon.bg-consumable { background: rgba(166, 173, 200, 0.2); border-color: #a6adc8; color: #a6adc8; }
.well-cell.bg-reagent, .item-icon.bg-reagent { background: rgba(249, 226, 175, 0.2); border-color: #f9e2af; color: #f9e2af; }
.well-cell.bg-default, .item-icon.bg-default { background: rgba(137, 180, 250, 0.2); border-color: #89b4fa; color: #89b4fa; }
.warn-icon { position: absolute; top: -5px; right: -5px; font-size: 10px; z-index: 2; }

.slide-fade-enter-active { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.slide-fade-leave-active { transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
.slide-fade-enter-from, .slide-fade-leave-to { transform: translateX(30px); opacity: 0; }

.modal-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(17, 17, 27, 0.85); backdrop-filter: blur(5px); display: flex; justify-content: center; align-items: center; z-index: 9999;}
.modal-content { background: #1e1e2e; border: 1px solid #45475a; border-radius: 12px; display: flex; flex-direction: column; box-shadow: 0 20px 50px rgba(0,0,0,0.5); overflow: hidden;}
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 25px; background: #11111b; border-bottom: 1px solid #313244; flex-shrink: 0;}
.modal-title { font-size: 16px; font-weight: bold; color: #cdd6f4; }
.btn-close { background: transparent; border: none; color: #f38ba8; font-size: 20px; cursor: pointer; transition: 0.2s;}
.btn-close:hover { transform: scale(1.2); }
.modal-body { padding: 25px; display: flex; flex-direction: column; gap: 15px;}
.modal-footer { padding: 15px 25px; background: #11111b; border-top: 1px solid #313244; display: flex; justify-content: flex-end; gap: 10px;}

.form-hint { color: #bac2de; font-size: 12px; margin: 0 0 10px 0; }
.form-group { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.form-group label { font-size: 12px; color: #89b4fa; font-weight: bold;}
.form-group-row { display: flex; gap: 15px; }

.input-dark { background: #11111b; border: 1px solid #313244; color: #cdd6f4; padding: 10px 12px; border-radius: 6px; outline: none; transition: 0.2s; font-size: 14px;}
.input-dark:focus { border-color: #a6e3a1; box-shadow: 0 0 8px rgba(166, 227, 161, 0.2); }
.disabled-input { opacity: 0.5; cursor: not-allowed !important; background: #181825;}

.bulk-table { width: 100%; border-collapse: collapse; margin-top: 10px;}
.bulk-table th { color: #89b4fa; text-align: left; padding: 8px 12px; border-bottom: 2px solid #313244; font-size: 12px;}
.bulk-table td { padding: 8px 12px; border-bottom: 1px dashed #313244; vertical-align: middle;}

.fade-in { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.fade-in-scale { animation: fadeInScale 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
@keyframes fadeInScale { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
</style>