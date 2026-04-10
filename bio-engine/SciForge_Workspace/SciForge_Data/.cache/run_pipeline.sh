#!/bin/bash
# ============================================================================
# ProDesigner Pipeline (带全局日志记录与监控推流机制)
# ============================================================================
set -e
export CUDA_VISIBLE_DEVICES="0"
RFD_SCRIPT="/data/lmk/RFdiffusion/scripts/run_inference.py"
MPNN_SCRIPT="/data/lmk/ProteinMPNN/protein_mpnn_run.py"

OUT_DIR="/data/yc/mx/test/test/task_designer/design_output"
LOG_DIR="/data/yc/mx/test/test/task_designer/logs"
LOG_FILE="$LOG_DIR/master_pipeline.log"

mkdir -p $OUT_DIR/rfd_out $OUT_DIR/mpnn_out $LOG_DIR

# 利用管道和 tee 将全局流程同时输出到终端（供前端实时抓取）并持久化到文件（供最终打包）
{
echo "=========================================================="
echo "🚀 [Start] ProDesigner 计算任务启动时间: $(date)"
echo "=========================================================="

echo "[Step 1/2] 正在服务器上运行 RFdiffusion..."
source /home/amax/mambaforge/etc/profile.d/conda.sh
conda activate lmk_RFdiffusion
for INPUT_PDB in /data/yc/mx/test/test/task_designer/*.pdb; do
    if [ -f "$INPUT_PDB" ]; then
        BASENAME=$(basename "$INPUT_PDB" .pdb)
        echo ">> [RF] 正在扩散: $BASENAME"
        python $RFD_SCRIPT \
            inference.input_pdb="$INPUT_PDB" \
            inference.output_prefix=$OUT_DIR/rfd_out/${BASENAME} \
            contigmap.contigs="[A21-334/25-25/A355-452]" \
            inference.num_designs=10 \
            diffuser.partial_T=
    fi
done

echo "[Step 2/2] 正在服务器上运行 ProteinMPNN..."
source /home/amax/mambaforge/etc/profile.d/conda.sh
conda activate lmk_proteinMPNN
for PDB_FILE in $OUT_DIR/rfd_out/*.pdb; do
    if [ -f "$PDB_FILE" ]; then
        FILENAME=$(basename "$PDB_FILE" .pdb)
        ORIG_NAME="${FILENAME%_*}"
        MPNN_FLAGS=""
        
        FIXED_TPL="/data/yc/mx/test/test/task_designer/${ORIG_NAME}_fixed_template.jsonl"
        if [ ! -f "$FIXED_TPL" ]; then FIXED_TPL="/data/yc/mx/test/test/task_designer/Target_fixed_template.jsonl"; fi
        if [ -f "$FIXED_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$FIXED_TPL" > $OUT_DIR/current_fixed.jsonl
            MPNN_FLAGS="$MPNN_FLAGS --fixed_positions_jsonl $OUT_DIR/current_fixed.jsonl"
        fi
        echo ">> [MPNN] 正在重设计: $FILENAME"
        python $MPNN_SCRIPT \
            --pdb_path "$PDB_FILE" \
            --num_seq_per_target 5 \
            --sampling_temp 0.1 \
            --omit_AAs "" \
            --batch_size 1 \
            --out_folder $OUT_DIR/mpnn_out $MPNN_FLAGS
    fi
done

echo "=========================================================="
echo "🏁 [End] ProDesigner 计算任务结束时间: $(date)"
echo "=========================================================="
echo "✅ 远端计算任务圆满结束！开始打包产物和日志文件..."
cd /data/yc/mx/test/test/task_designer/
tar -czf result_bundle.tar.gz design_output/ logs/
} 2>&1 | tee $LOG_FILE

echo "===BUNDLE_READY==="
