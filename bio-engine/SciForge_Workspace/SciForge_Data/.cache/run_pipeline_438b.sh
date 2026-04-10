#!/bin/bash
# ============================================================================
# ProDesigner Pipeline (由 ZTools 云直连引擎生成)
# ============================================================================
set -e
export CUDA_VISIBLE_DEVICES="0"
RFD_SCRIPT="/data/lmk/RFdiffusion/scripts/run_inference.py"
MPNN_SCRIPT="/data/lmk/ProteinMPNN/protein_mpnn_run.py"
OUT_DIR="/data/yc/mx/8ilq_Gn_helix_design/task_438b/design_output"

mkdir -p $OUT_DIR/rfd_out $OUT_DIR/mpnn_out

echo "[Step 1/2] 正在服务器上运行 RFdiffusion..."
source /home/amax/mambaforge/etc/profile.d/conda.sh
conda activate lmk_RFdiffusion
for INPUT_PDB in /data/yc/mx/8ilq_Gn_helix_design/task_438b/*.pdb; do
    if [ -f "$INPUT_PDB" ]; then
        BASENAME=$(basename "$INPUT_PDB" .pdb)
        echo ">> [RF] 正在扩散: $BASENAME"
        python $RFD_SCRIPT \
            inference.input_pdb="$INPUT_PDB" \
            inference.output_prefix=$OUT_DIR/rfd_out/${BASENAME} \
            contigmap.contigs="[A1-150/0 B1-200/10-10/B211-452]" \
            inference.num_designs=10 \
            diffuser.partial_T=15
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
        
        FIXED_TPL="/data/yc/mx/8ilq_Gn_helix_design/task_438b/438b_${ORIG_NAME}_fixed_template.jsonl"
        if [ ! -f "$FIXED_TPL" ]; then FIXED_TPL="/data/yc/mx/8ilq_Gn_helix_design/task_438b/438b_Target_fixed_template.jsonl"; fi
        if [ -f "$FIXED_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$FIXED_TPL" > $OUT_DIR/current_fixed.jsonl
            MPNN_FLAGS="$MPNN_FLAGS --fixed_positions_jsonl $OUT_DIR/current_fixed.jsonl"
        fi
        OMIT_TPL="/data/yc/mx/8ilq_Gn_helix_design/task_438b/438b_${ORIG_NAME}_omit_template.jsonl"
        if [ -f "$OMIT_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$OMIT_TPL" > $OUT_DIR/current_omit.jsonl
            MPNN_FLAGS="$MPNN_FLAGS --omit_AA_jsonl $OUT_DIR/current_omit.jsonl"
        fi
        echo ">> [MPNN] 正在重设计: $FILENAME"
        python $MPNN_SCRIPT \
            --pdb_path "$PDB_FILE" \
            --num_seq_per_target 2 \
            --sampling_temp 0.1 \
            --omit_AAs "C" \
            --batch_size 1 \
            --out_folder $OUT_DIR/mpnn_out $MPNN_FLAGS
    fi
done


echo "✅ 远端计算任务圆满结束！开始打包产物..."
cd /data/yc/mx/8ilq_Gn_helix_design/task_438b/
tar -czf result_bundle.tar.gz design_output/
echo "===BUNDLE_READY==="
