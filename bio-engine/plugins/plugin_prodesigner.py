# plugins/plugin_prodesigner.py
import os
import sys
import argparse
import json
import uuid
import tarfile

try:
    import paramiko
    HAS_SSH = True
except ImportError:
    HAS_SSH = False

PLUGIN_NAME = "静态架构师引擎 (云端全能版)"
PLUGIN_ICON = "☁️"
PLUGIN_DESC = "生成 RF/MPNN 级联流水线。现已支持「单段全自动」与「两段式交互」无缝切换，生成的脚本头部自带动态序列比对视图供直观确认！"

AA_MAP = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
    'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
    'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
    'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
}

# ==========================================
# 前端表单 UI Schema 描述
# ==========================================
UI_SCHEMA = [
    {"key": "two_stage", "label": "🔀 开启两段式交互 (跑完 RF 后停止以供筛选骨架)", "type": "boolean", "default": False, "span": 12},
    {"key": "file_path", "label": "📁 导入骨架/靶点 WT PDB (第一阶段必填)", "type": "file", "span": 12},
    {"key": "rfd_pdbs", "label": "📁 第二阶段：输入挑选的 RF 骨架 (两段式必填)", "type": "file", "span": 12},

    {"key": "mode", "label": "设计模式", "type": "select", "options": [
        "Partial Diffusion (局部微调/构象锁定)", 
        "Binder Design (蛋白结合子设计)", 
        "Motif Scaffolding", 
        "Unconditional (De novo)"
    ], "default": "Partial Diffusion (局部微调/构象锁定)", "span": 12},

    {"key": "run_rfd", "label": "跑 RFdiffusion", "type": "boolean", "default": True, "span": 6},
    {"key": "run_mpnn", "label": "跑 ProteinMPNN", "type": "boolean", "default": True, "span": 6},

    {"key": "contig", "label": "Contig 拓扑 (原链名)", "type": "string", "default": "[A1-150/0 B1-200/10-10/B211-452]", "span": 12},
    {"key": "bias", "label": "偏好突变 (如: A15:W)", "type": "string", "default": "", "span": 6},
    {"key": "fixed", "label": "锁定不变 (如: A, B1-50)", "type": "string", "default": "A, B1-770", "span": 6},

    {"key": "hotspot", "label": "靶点热区 (Binder模式)", "type": "string", "default": "", "span": 6},
    {"key": "partial_t", "label": "扰动强度 (Partial模式)", "type": "string", "default": "15", "span": 6},
    {"key": "ss_bias", "label": "二级结构约束 (SS Bias)", "type": "string", "default": "", "span": 6},
    {"key": "num_designs", "label": "RF 生成批次", "type": "number", "default": 10, "span": 6},

    {"key": "omit_aa", "label": "MPNN 禁用氨基酸", "type": "string", "default": "C", "span": 6},
    {"key": "seq_per_target", "label": "MPNN 每骨架序列数", "type": "number", "default": 2, "span": 6},
    {"key": "ss_enhance", "label": "🛡️ 开启二级结构保护 (禁止螺旋/折叠出 P/G)", "type": "boolean", "default": True, "span": 12},

    {"key": "ssh_host", "label": "云端 IP", "type": "string", "default": "192.168.1.100", "span": 4},
    {"key": "ssh_port", "label": "端口", "type": "number", "default": 22, "span": 2},
    {"key": "ssh_user", "label": "用户名", "type": "string", "default": "root", "span": 3},
    {"key": "ssh_pwd", "label": "云端密码", "type": "string", "default": "", "span": 3},

    {"key": "conda_sh", "label": "Conda 路径", "type": "string", "default": "/opt/conda/etc/profile.d/conda.sh", "span": 12},
    {"key": "rfd_env", "label": "RF 环境名", "type": "string", "default": "SE3nv", "span": 6},
    {"key": "mpnn_env", "label": "MPNN 环境名", "type": "string", "default": "mlfold", "span": 6},
    
    {"key": "rfd_path", "label": "RF 推理脚本路径", "type": "string", "default": "/home/user/RFdiffusion/scripts/run_inference.py", "span": 12},
    {"key": "mpnn_path", "label": "MPNN 运行脚本路径", "type": "string", "default": "/home/user/ProteinMPNN/protein_mpnn_run.py", "span": 12},
    
    {"key": "server_dir", "label": "云端工作流根目录 (将自动创建子任务盒)", "type": "string", "default": "/home/user/ztools_workspace/", "span": 8},
    {"key": "gpu_id", "label": "GPU ID", "type": "string", "default": "0", "span": 4}
]

UI_LAYOUT = {
    "direction": "row",
    "blocks": [
        {"type": "form", "width": "420px", "height": "100%"},
        {"type": "tabs", "flex": "1", "height": "100%", "panes": [
            {"title": "💻 级联流水线脚本", "type": "code"},
            {"title": "🎯 远端监控日志", "type": "terminal"},
            {"title": "📤 批量云端产物", "type": "export"}
        ]}
    ],
    "footer_actions": [
        {"id": "compile", "label": "⚙️ 1. 编译", "type": "default"},
        {"id": "run_rfd", "label": "🚀 2. 跑RF(或全自动)", "type": "primary"},
        {"id": "compile_mpnn", "label": "⚙️ 3. 对齐MPNN", "type": "default"},
        {"id": "run_mpnn", "label": "🚀 4. 跑MPNN", "type": "primary"},
        {"id": "check_gpu", "label": "👀 查显卡", "type": "default"},
        {"id": "abort", "label": "🛑 急停", "type": "danger"}
    ]
}

def get_sync_workspace():
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../sciforge_config.json"))
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("data_hub_path"): return cfg.get("data_hub_path")
        except: pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../SciForge_Workspace/SciForge_Data"))

def parse_pdb_atoms(filepath):
    pdb_data = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                if line.startswith("HELIX "):
                    chain = line[19].strip()
                    pdb_data.setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                    pdb_data[chain]['helices'].append((int(line[21:25].strip()), int(line[33:37].strip())))
                elif line.startswith("SHEET "):
                    chain = line[21].strip()
                    pdb_data.setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                    pdb_data[chain]['sheets'].append((int(line[22:26].strip()), int(line[33:37].strip())))
                elif (line.startswith("ATOM  ") or line.startswith("HETATM")) and line[13:16].strip() == "CA":
                    chain = line[21].strip()
                    res_name = line[17:20].strip()
                    if res_name in AA_MAP:
                        pdb_data.setdefault(chain, {'seq':{}, 'helices':[], 'sheets':[]})
                        res_num_str = "".join([c for c in line[22:27].strip() if c.isdigit() or c == '-'])
                        if res_num_str: pdb_data[chain]['seq'][int(res_num_str)] = AA_MAP[res_name]
            except Exception: pass 
    return pdb_data

def generate_alignment_comments(pdb_data_dict, global_fixed, global_bias):
    align_comments = []
    align_comments.append("# ============================================================================")
    align_comments.append("# 📊 编译后序列比对与约束确认视图 (Visual Alignment)")
    align_comments.append("# ============================================================================")
    align_comments.append("# 说明: IDX代表原PDB连续编号. H(螺旋) E(折叠) C(卷曲). 约束: F(锁定) B(偏好) -(自由)")
    align_comments.append("#")
    has_bias = len(global_bias) > 0
    for pdb_name, data in pdb_data_dict.items():
        align_comments.append(f"# >>> PDB: {pdb_name} <<<")
        for chain, cdata in data.items():
            align_comments.append(f"# ---------- Chain {chain} ----------")
            seq_dict = cdata['seq']
            if not seq_dict: continue
            sorted_res = sorted(list(seq_dict.keys()))
            seq_str = "".join([seq_dict[r] for r in sorted_res])
            fix_str = "".join(["F" if (chain in global_fixed and r in global_fixed[chain]) else "-" for r in sorted_res])
            bia_str = "".join([global_bias.get(chain, {}).get(r, "-") for r in sorted_res])
            
            ss_str, idx_str = "", ""
            for i, r in enumerate(sorted_res):
                is_h = any(start <= r <= end for start, end in cdata.get('helices', []))
                is_e = any(start <= r <= end for start, end in cdata.get('sheets', []))
                if is_h: ss_str += "H"
                elif is_e: ss_str += "E"
                else: ss_str += "C"
                
                mapping_idx = i + 1
                if mapping_idx % 10 == 0: idx_str += str(mapping_idx // 10)[-1]
                elif mapping_idx % 5 == 0: idx_str += "+"
                else: idx_str += "."
            
            for i in range(0, len(seq_str), 60):
                chunk_ss = ss_str[i:i+60]
                chunk_seq = seq_str[i:i+60]
                chunk_fix = fix_str[i:i+60]
                chunk_bia = bia_str[i:i+60]
                chunk_idx = idx_str[i:i+60]
                res_start = sorted_res[i] 
                renum_start = i + 1 
                
                align_comments.append(f"# IDX [{renum_start:4d}] : {chunk_idx}")
                align_comments.append(f"# SS  [{res_start:4d}] : {chunk_ss}")
                align_comments.append(f"# SEQ [{res_start:4d}] : {chunk_seq}")
                align_comments.append(f"# FIX        : {chunk_fix}")
                if has_bias: align_comments.append(f"# BIA        : {chunk_bia}")
                align_comments.append("#")
    align_comments.append("# ============================================================================\n")
    return "\n".join(align_comments)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', type=str, default='compile')
    for item in UI_SCHEMA:
        if item["type"] == "boolean": parser.add_argument(f"--{item['key']}", action="store_true")
        elif item["type"] == "number": parser.add_argument(f"--{item['key']}", type=float, default=item.get("default", 0.0))
        else: parser.add_argument(f"--{item['key']}", type=str, default=str(item.get("default", "")))
            
    args = parser.parse_args()
    
    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)
    manifest_path = os.path.join(temp_dir, "prodesigner_manifest.json")
    manifest_rfd = os.path.join(temp_dir, "prodesigner_rfd_manifest.json")
    manifest_mpnn = os.path.join(temp_dir, "prodesigner_mpnn_manifest.json")

    server_dir = args.server_dir.strip()
    if server_dir and not server_dir.endswith('/'): server_dir += '/'
    task_dir = f"{server_dir}task_designer/"

    # =========================================================================
    # Phase 1: 编译约束模板与流水线脚本 (Action: compile)
    # =========================================================================
    if args.action == 'compile':
        print(">>> 启动 ProDesigner 编译引擎 (Step 1)...")
        f_path_str = str(getattr(args, 'file_path', '')).strip()
        pdb_filepaths = []
        if f_path_str:
            for f in f_path_str.split(','):
                if f.strip():
                    full_path = os.path.join(workspace, f.strip())
                    if os.path.exists(full_path): pdb_filepaths.append(full_path)

        pdb_data_dict = {}
        for filepath in pdb_filepaths:
            pdb_name = os.path.splitext(os.path.basename(filepath))[0]
            pdb_data_dict[pdb_name] = parse_pdb_atoms(filepath)

        global_bias, global_fixed = {}, {}
        if args.bias.strip():
            for p in [x.strip() for x in args.bias.split(',')]:
                if ':' in p:
                    loc, aa = p.split(':')
                    try: global_bias.setdefault(loc[0], {})[int(loc[1:])] = aa.upper()
                    except: pass
        if args.fixed.strip():
            for item in args.fixed.split(','):
                item = item.strip()
                if not item: continue
                chain = item[0]
                if chain not in global_fixed: global_fixed[chain] = []
                if len(item) == 1: global_fixed[chain].extend(list(range(-1000, 10000)))
                elif '-' in item[1:]:
                    start, end = map(int, item[1:].split('-'))
                    global_fixed[chain].extend(list(range(start, end+1)))
                else: global_fixed[chain].append(int(item[1:]))

        has_bias = len(global_bias) > 0
        has_fixed = len(global_fixed) > 0

        # 🌟 生成注入到 Shell 脚本顶部的多链序列比对注释图
        align_str = generate_alignment_comments(pdb_data_dict, global_fixed, global_bias)

        jsonl_files_content = {}
        if not pdb_filepaths:
            if has_bias: jsonl_files_content['Target_bias_template.jsonl'] = json.dumps({"__PDB_NAME__": {c: {str(r): {aa: 10000.0} for r, aa in rd.items()} for c, rd in global_bias.items()}})
            if has_fixed: jsonl_files_content['Target_fixed_template.jsonl'] = json.dumps({"__PDB_NAME__": {c: [r for r in rl] for c, rl in global_fixed.items()}})
        else:
            for pdb_name, data in pdb_data_dict.items():
                local_bias, local_fixed, local_omit = {}, {}, {}
                chain_map = {old_c: chr(65 + i) for i, old_c in enumerate(data.keys())}
                if has_bias:
                    for chain, res_dict in global_bias.items():
                        if chain in data:
                            mapped_chain = chain_map[chain]
                            local_bias[mapped_chain] = {}
                            for res_num, aa in res_dict.items():
                                if res_num in data[chain]['mapping']: local_bias[mapped_chain][str(data[chain]['mapping'][res_num])] = {aa: 10000.0}
                    jsonl_files_content[f'{pdb_name}_bias_template.jsonl'] = json.dumps({"__PDB_NAME__": local_bias})
                if has_fixed:
                    for chain, res_list in global_fixed.items():
                        if chain in data:
                            mapped_chain = chain_map[chain]
                            local_fixed[mapped_chain] = []
                            for res_num in res_list:
                                if res_num in data[chain]['mapping']: local_fixed[mapped_chain].append(data[chain]['mapping'][res_num])
                    jsonl_files_content[f'{pdb_name}_fixed_template.jsonl'] = json.dumps({"__PDB_NAME__": local_fixed})
                if args.ss_enhance:
                    for chain, cdata in data.items():
                        mapped_chain = chain_map[chain]
                        ss_res_list = set()
                        for start, end in cdata.get('helices', []) + cdata.get('sheets', []): ss_res_list.update(list(range(start, end + 1)))
                        valid_ss = [r for r in ss_res_list if r in cdata['seq']]
                        if valid_ss:
                            local_omit[mapped_chain] = {}
                            for res_num in valid_ss:
                                if res_num in cdata['mapping']: local_omit[mapped_chain][str(cdata['mapping'][res_num])] = "PG"
                    if local_omit: jsonl_files_content[f'{pdb_name}_omit_template.jsonl'] = json.dumps({"__PDB_NAME__": local_omit})

        local_jsonl_paths = []
        for filename, content in jsonl_files_content.items():
            out_path = os.path.join(temp_dir, filename)
            with open(out_path, 'w', encoding='utf-8') as f: f.write(content + "\n")
            local_jsonl_paths.append(out_path)

        rfd_extras = ""
        if "Binder" in args.mode and args.hotspot: rfd_extras += f" \\\n            ppi.hotspot_res=[{args.hotspot}]"
        if "Partial" in args.mode: rfd_extras += f" \\\n            diffuser.partial_T={args.partial_t}"
        if args.ss_bias.strip(): rfd_extras += f" \\\n            scaffoldguided.scaffoldguided=True scaffoldguided.target_ss=\"{args.ss_bias.strip()}\""
        
        rfd_block = f"""
echo "[Step 1/2] 正在服务器上运行 RFdiffusion..."
source {args.conda_sh.strip()}
conda activate {args.rfd_env.strip()}
for INPUT_PDB in {task_dir}*.pdb; do
    if [ -f "$INPUT_PDB" ]; then
        BASENAME=$(basename "$INPUT_PDB" .pdb)
        echo ">> [RF] 正在扩散: $BASENAME"
        python {args.rfd_path.strip()} \\
            inference.input_pdb="$INPUT_PDB" \\
            inference.output_prefix=$OUT_DIR/rfd_out/${{BASENAME}} \\
            contigmap.contigs="{args.contig}" \\
            inference.num_designs={int(args.num_designs)}{rfd_extras} &
        STEP_PID=$!
        echo $STEP_PID > "{task_dir}current_step.pid"
        wait $STEP_PID
    fi
done
"""
        sed_commands, mpnn_flags = "", ""
        if has_fixed:
            sed_commands += f"""
        FIXED_TPL="{task_dir}${{ORIG_NAME}}_fixed_template.jsonl"
        if [ ! -f "$FIXED_TPL" ]; then FIXED_TPL="{task_dir}Target_fixed_template.jsonl"; fi
        if [ -f "$FIXED_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$FIXED_TPL" > $OUT_DIR/current_fixed.jsonl
            MPNN_FLAGS="$MPNN_FLAGS --fixed_positions_jsonl $OUT_DIR/current_fixed.jsonl"
        fi"""
        if has_bias:
            sed_commands += f"""
        BIAS_TPL="{task_dir}${{ORIG_NAME}}_bias_template.jsonl"
        if [ ! -f "$BIAS_TPL" ]; then BIAS_TPL="{task_dir}Target_bias_template.jsonl"; fi
        if [ -f "$BIAS_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$BIAS_TPL" > $OUT_DIR/current_bias.jsonl
            MPNN_FLAGS="$MPNN_FLAGS --bias_AA_jsonl $OUT_DIR/current_bias.jsonl"
        fi"""
        if args.ss_enhance:
            sed_commands += f"""
        OMIT_TPL="{task_dir}${{ORIG_NAME}}_omit_template.jsonl"
        if [ -f "$OMIT_TPL" ]; then
            sed "s/__PDB_NAME__/$FILENAME/g" "$OMIT_TPL" > $OUT_DIR/current_omit.jsonl
            MPNN_FLAGS="$MPNN_FLAGS --omit_AA_jsonl $OUT_DIR/current_omit.jsonl"
        fi"""

        mpnn_block = f"""
echo "[Step 2/2] 正在服务器上运行 ProteinMPNN..."
source {args.conda_sh.strip()}
conda activate {args.mpnn_env.strip()}
for PDB_FILE in $OUT_DIR/rfd_out/*.pdb; do
    if [ -f "$PDB_FILE" ]; then
        FILENAME=$(basename "$PDB_FILE" .pdb)
        ORIG_NAME="${{FILENAME%_*}}"
        MPNN_FLAGS=""
        {sed_commands}
        echo ">> [MPNN] 正在重设计: $FILENAME"
        python {args.mpnn_path.strip()} \\
            --pdb_path "$PDB_FILE" \\
            --num_seq_per_target {int(args.seq_per_target)} \\
            --sampling_temp 0.1 \\
            --omit_AAs "{args.omit_aa}" \\
            --batch_size 1 \\
            --out_folder $OUT_DIR/mpnn_out $MPNN_FLAGS &
        STEP_PID=$!
        echo $STEP_PID > "{task_dir}current_step.pid"
        wait $STEP_PID
    fi
done
"""
        
        # 判断模式生成脚本
        if getattr(args, 'two_stage', False):
            # 开启了两段式：只输出 1_run_rfd.sh
            bash_script = f"""#!/bin/bash\n{align_str}
# ============================================================================
# ProDesigner Pipeline (两段式专属 - 仅运行 RFdiffusion)
# ============================================================================
set -e
export CUDA_VISIBLE_DEVICES="{args.gpu_id.strip()}"
OUT_DIR="{task_dir}design_output"
LOG_DIR="{task_dir}logs"
LOG_FILE="$LOG_DIR/master_pipeline.log"

mkdir -p $OUT_DIR/rfd_out $LOG_DIR
echo $$ > "{task_dir}main_pipeline.pid"

{{
echo "=========================================================="
echo "🚀 [Start] ProDesigner 阶段一(RF) 启动时间: $(date)"
echo "=========================================================="
{rfd_block}
echo "=========================================================="
echo "🏁 [End] ProDesigner 阶段一(RF) 结束时间: $(date)"
echo "=========================================================="
echo "✅ 远端计算任务圆满结束！开始打包产物和日志文件..."
cd {task_dir}
tar -czf rfd_bundle.tar.gz design_output/rfd_out/ logs/
}} 2>&1 | tee $LOG_FILE

echo "===BUNDLE_READY==="
"""
            sh_path = os.path.join(temp_dir, f"1_run_rfd.sh")
            with open(sh_path, 'w', encoding='utf-8', newline='\n') as f: f.write(bash_script.replace('\r\n', '\n').replace('\r', ''))
            with open(manifest_rfd, 'w', encoding='utf-8') as f:
                json.dump({"pdbs": pdb_filepaths, "jsonls": local_jsonl_paths, "sh": sh_path, "task_dir": task_dir}, f)
            print(f"[OutputCode] .cache/1_run_rfd.sh")
            print("\n" + "="*50)
            print(" 🛠️ 阶段一(RF)编译完成！顶部序列比对已就绪，请点击 [2. 跑RF]。")
            print("="*50)

        else:
            # 单段全自动：一键跑完
            bash_script = f"""#!/bin/bash\n{align_str}
# ============================================================================
# ProDesigner Pipeline (单段全自动 - RF + MPNN)
# ============================================================================
set -e
export CUDA_VISIBLE_DEVICES="{args.gpu_id.strip()}"
OUT_DIR="{task_dir}design_output"
LOG_DIR="{task_dir}logs"
LOG_FILE="$LOG_DIR/master_pipeline.log"

mkdir -p $OUT_DIR/rfd_out $OUT_DIR/mpnn_out $LOG_DIR
echo $$ > "{task_dir}main_pipeline.pid"

{{
echo "=========================================================="
echo "🚀 [Start] ProDesigner 全自动任务启动时间: $(date)"
echo "=========================================================="
{rfd_block}{mpnn_block}
echo "=========================================================="
echo "🏁 [End] ProDesigner 全自动任务结束时间: $(date)"
echo "=========================================================="
echo "✅ 远端计算任务圆满结束！开始打包产物和日志文件..."
cd {task_dir}
tar -czf result_bundle.tar.gz design_output/ logs/
}} 2>&1 | tee $LOG_FILE

echo "===BUNDLE_READY==="
"""
            sh_path = os.path.join(temp_dir, f"run_pipeline.sh")
            with open(sh_path, 'w', encoding='utf-8', newline='\n') as f: f.write(bash_script.replace('\r\n', '\n').replace('\r', ''))
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump({"pdbs": pdb_filepaths, "jsonls": local_jsonl_paths, "sh": sh_path, "task_dir": task_dir}, f)
            print(f"[OutputCode] .cache/run_pipeline.sh")
            print("\n" + "="*50)
            print(" 🛠️ 全自动编译完成！顶部序列比对已就绪，请核对后点击 [2. 跑RF/全自动]。")
            print("="*50)


    # =========================================================================
    # Phase 2: 上传并跑第一段 (Action: run_rfd)
    # =========================================================================
    elif args.action == 'run_rfd':
        if not HAS_SSH: print("❌ [Fatal] 云端直连需要 paramiko"); sys.exit(1)
            
        is_two_stage = getattr(args, 'two_stage', False)
        target_manifest = manifest_rfd if is_two_stage else manifest_path
        
        if not os.path.exists(target_manifest):
            print("❌ [Fatal] 尚未执行编译！请先点击 [1. 编译]。"); sys.exit(1)
            
        with open(target_manifest, 'r', encoding='utf-8') as f: manifest = json.load(f)
        task_dir = manifest['task_dir']

        print(f"\n" + "="*50)
        print(f"🚀 [SSH] 正在握手远程集群: {args.ssh_user}@{args.ssh_host} ...")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(args.ssh_host, port=int(args.ssh_port), username=args.ssh_user, password=args.ssh_pwd, timeout=10)
            
            sftp = ssh.open_sftp()
            print(f"📂 [SSH] 初始化云端沙盒目录: {task_dir}")
            _, stdout_mkdir, _ = ssh.exec_command(f"mkdir -p {task_dir}")
            stdout_mkdir.channel.recv_exit_status() 

            print(f"⬆️ [SFTP] 正在投递 PDB、JSONL 约束和脚本至云端...")
            sh_file = manifest['sh']
            sh_basename = os.path.basename(sh_file)
            sftp.put(sh_file, f"{task_dir}{sh_basename}")
            _, stdout_chmod, _ = ssh.exec_command(f"chmod +x {task_dir}{sh_basename}")
            stdout_chmod.channel.recv_exit_status()
            
            for f in manifest.get('pdbs', []): sftp.put(f, f"{task_dir}{os.path.basename(f)}")
            for f in manifest.get('jsonls', []): sftp.put(f, f"{task_dir}{os.path.basename(f)}")
            
            print(f"🔥 [SSH] 开始下发执行命令，前方发来高能日志流...\n")
            print("—" * 50)
            
            ssh.exec_command(f"sed -i 's/\\r$//' {task_dir}{sh_basename}")
            stdin, stdout, stderr = ssh.exec_command(f"bash -lc 'bash {task_dir}{sh_basename}'", get_pty=True)
            
            for line in iter(stdout.readline, ""):
                if not line: break
                clean_line = line.strip()
                if clean_line == "===BUNDLE_READY===": break
                if clean_line: print(f"[Cluster] {clean_line}", flush=True)

            print("—" * 50)
            print(f"\n⬇️ [SFTP] 云端运算结束！正在将资产与 LOG日志 下载至前端...")
            
            bundle_name = "rfd_bundle.tar.gz" if is_two_stage else "result_bundle.tar.gz"
            remote_tar = f"{task_dir}{bundle_name}"
            local_tar = os.path.join(temp_dir, bundle_name)
            
            try:
                sftp.get(remote_tar, local_tar)
            except Exception:
                print(f"❌ [SFTP Error] 无法拉取产物，说明脚本在远端崩溃！请翻阅日志寻找原因。")
                sys.exit(1)
                
            sftp.close(); ssh.close()

            try:
                with tarfile.open(local_tar, "r:gz") as tar: 
                    tar.extractall(path=temp_dir)
                for target_dir in ["design_output", "logs"]:
                    extract_dir = os.path.join(temp_dir, target_dir)
                    if os.path.exists(extract_dir):
                        for root, _, files in os.walk(extract_dir):
                            for file in files:
                                ext = os.path.splitext(file)[1].lower()
                                if ext in ['.pdb', '.fa', '.fasta', '.jsonl', '.csv', '.trb', '.log']:
                                    rel_path = os.path.relpath(os.path.join(root, file), workspace)
                                    print(f"[OutputFile] {rel_path.replace(os.sep, '/')}")
            except Exception as tar_err: print(f"❌ 本地解压失败: {tar_err}")

            print(f"\n🎉 [Success] 本阶段已完成回收！")
            if is_two_stage:
                print("👉 (两段式模式) 请在左侧【📤批量产物导出】归档并精选骨架后，拖入输入框，再点击 [3. 对齐MPNN]。")
            else:
                print("👉 (全自动模式) 所有设计产物均已成功生成，请点击 [📤批量产物导出] 入库！")

        except Exception as e: print(f"❌ [SSH Error] 云端执行崩溃: {e}"); sys.exit(1)


    # =========================================================================
    # Phase 3: 动态匹配并编译 MPNN (Action: compile_mpnn)
    # =========================================================================
    elif args.action == 'compile_mpnn':
        if not getattr(args, 'two_stage', False):
            print("❌ [Error] 仅在勾选【开启两段式交互】时需要此功能。全自动模式请直接查看产物。"); sys.exit(1)

        print(">>> 启动 [固定区块顺序寻迹] 防弹追踪引擎，开始第二阶段对齐...")
        orig_pdb_str = str(getattr(args, 'file_path', '')).strip()
        rfd_pdbs_str = str(getattr(args, 'rfd_pdbs', '')).strip()
        
        if not orig_pdb_str or not rfd_pdbs_str:
            print("❌ [Fatal] 请确保已正确填写【第一阶段 WT PDB】与【第二阶段挑选的 RF 骨架】！"); sys.exit(1)
            
        orig_pdb_path = os.path.join(workspace, orig_pdb_str.split(',')[0].strip())
        rfd_pdb_paths = [os.path.join(workspace, p.strip()) for p in rfd_pdbs_str.split(',') if p.strip()]

        orig_data = parse_pdb_atoms(orig_pdb_path)
        global_fixed, global_bias, global_omit = {}, {}, {}
        
        if args.fixed.strip():
            for item in args.fixed.split(','):
                item = item.strip()
                if not item: continue
                chain = item[0]
                if len(item) == 1: global_fixed.setdefault(chain, []).extend(list(range(-1000, 10000)))
                elif '-' in item[1:]:
                    s, e = map(int, item[1:].split('-'))
                    global_fixed.setdefault(chain, []).extend(list(range(s, e+1)))
                else: global_fixed.setdefault(chain, []).append(int(item[1:]))

        if args.bias.strip():
            for p in [x.strip() for x in args.bias.split(',')]:
                if ':' in p:
                    loc, aa = p.split(':')
                    try: global_bias.setdefault(loc[0], {})[int(loc[1:])] = aa.upper()
                    except ValueError: pass

        if args.ss_enhance:
            for chain, data in orig_data.items():
                ss_res_list = set()
                for start, end in data['helices'] + data['sheets']:
                    ss_res_list.update(list(range(start, end + 1)))
                valid_ss = [r for r in ss_res_list if r in data['seq']]
                if valid_ss: global_omit[chain] = valid_ss
        
        has_fixed, has_bias, has_omit = len(global_fixed)>0, len(global_bias)>0, len(global_omit)>0
        print(f"找到 {len(rfd_pdb_paths)} 个需对齐的新骨架，执行安全处理...")
        
        generated_fixed_data, generated_bias_data, generated_omit_data = {}, {}, {}
        success_count, fail_count = 0, 0

        for rf_path in rfd_pdb_paths:
            if not os.path.exists(rf_path): continue
            rf_name = os.path.splitext(os.path.basename(rf_path))[0]
            
            try:
                rf_data = parse_pdb_atoms(rf_path)
                rf_fixed, rf_bias, rf_omit = {}, {}, {}
                orig_to_rf_map = {}
                
                for orig_chain in global_fixed:
                    if orig_chain not in orig_data: continue
                    orig_to_rf_map.setdefault(orig_chain, {})
                    
                    req_nums = sorted(list(set(global_fixed[orig_chain])))
                    if not req_nums: continue
                    
                    blocks = []
                    current_block = [req_nums[0]]
                    for i in range(1, len(req_nums)):
                        if req_nums[i] == req_nums[i-1] + 1:
                            current_block.append(req_nums[i])
                        else:
                            blocks.append(current_block)
                            current_block = [req_nums[i]]
                    blocks.append(current_block)

                    for rf_chain, rf_cdata in rf_data.items():
                        rf_nums = sorted(list(rf_cdata['seq'].keys()))
                        rf_seq = "".join([rf_cdata['seq'][r] for r in rf_nums])
                        
                        search_start_idx = 0
                        temp_map = {}
                        matched_all_blocks = True
                        
                        for block in blocks:
                            valid_block = [r for r in block if r in orig_data[orig_chain]['seq']]
                            if not valid_block: continue
                            probe_seq = "".join([orig_data[orig_chain]['seq'][r] for r in valid_block])
                            
                            found_idx = rf_seq.find(probe_seq, search_start_idx)
                            
                            if found_idx != -1:
                                for i, orig_res_num in enumerate(valid_block):
                                    rf_mapped_idx = found_idx + i + 1  
                                    temp_map[orig_res_num] = (rf_chain, str(rf_mapped_idx))
                                search_start_idx = found_idx + len(probe_seq)
                            else:
                                matched_all_blocks = False
                                break 
                                
                        if matched_all_blocks and temp_map:
                            orig_to_rf_map[orig_chain].update(temp_map)
                            break 

                def get_mapped(orig_chain, req_num):
                    if orig_chain in orig_to_rf_map and req_num in orig_to_rf_map[orig_chain]:
                        return orig_to_rf_map[orig_chain][req_num]
                    return None, None

                for orig_chain in global_fixed:
                    if orig_chain not in orig_data: continue
                    for req_num in global_fixed[orig_chain]:
                        rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                        if rf_chain: rf_fixed.setdefault(rf_chain, []).append(int(mapped_idx))

                for orig_chain in global_bias:
                    if orig_chain not in orig_data: continue
                    for req_num, mut_aa in global_bias[orig_chain].items():
                        rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                        if rf_chain: rf_bias.setdefault(rf_chain, {})[mapped_idx] = {mut_aa: 10000.0}

                for orig_chain in global_omit:
                    if orig_chain not in orig_data: continue
                    for req_num in global_omit[orig_chain]:
                        rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                        if rf_chain: rf_omit.setdefault(rf_chain, {})[mapped_idx] = "PG"

                for c in rf_fixed: rf_fixed[c] = list(set(rf_fixed[c]))
                
                if has_fixed: generated_fixed_data[rf_name] = rf_fixed
                if has_bias: generated_bias_data[rf_name] = rf_bias
                if has_omit: generated_omit_data[rf_name] = rf_omit
                success_count += 1
                
            except Exception as inner_e:
                print(f"⚠️ 跳过受损文件 {rf_name}.pdb: {str(inner_e)}")
                fail_count += 1
            
        print(f"\n✅ 对齐解算圆满结束！成功解算 {success_count} 个，废弃 {fail_count} 个。")

        local_jsonls = []
        if has_fixed:
            jp = os.path.join(temp_dir, "dynamic_fixed.jsonl")
            with open(jp, 'w', encoding='utf-8') as f:
                for n, d in generated_fixed_data.items(): f.write(json.dumps({n: d}) + "\n")
            local_jsonls.append(jp)
            print(f"[OutputCode] .cache/dynamic_fixed.jsonl")
            
        if has_bias:
            jp = os.path.join(temp_dir, "dynamic_bias.jsonl")
            with open(jp, 'w', encoding='utf-8') as f:
                for n, d in generated_bias_data.items(): f.write(json.dumps({n: d}) + "\n")
            local_jsonls.append(jp)
            
        if has_omit:
            jp = os.path.join(temp_dir, "dynamic_omit.jsonl")
            with open(jp, 'w', encoding='utf-8') as f:
                for n, d in generated_omit_data.items(): f.write(json.dumps({n: d}) + "\n")
            local_jsonls.append(jp)

        mpnn_flags = ""
        if has_fixed: mpnn_flags += f" \\\n    --fixed_positions_jsonl {task_dir}dynamic_fixed.jsonl"
        if has_bias: mpnn_flags += f" \\\n    --bias_AA_jsonl {task_dir}dynamic_bias.jsonl"
        if has_omit: mpnn_flags += f" \\\n    --omit_AA_jsonl {task_dir}dynamic_omit.jsonl"

        json_preview = []
        json_preview.append("# ============================================================================")
        json_preview.append("# 📦 动态序列对齐结果预览 (展示首个骨架映射)")
        json_preview.append("# ============================================================================")
        if generated_fixed_data:
            k, v = list(generated_fixed_data.items())[0]
            json_preview.append(f"# [Fixed] {k}: {json.dumps(v)}")
        if generated_bias_data:
            k, v = list(generated_bias_data.items())[0]
            json_preview.append(f"# [Bias]  {k}: {json.dumps(v)}")
        if generated_omit_data:
            k, v = list(generated_omit_data.items())[0]
            json_preview.append(f"# [Omit]  {k}: {json.dumps(v)}")
        json_preview.append("# ============================================================================\n")
        preview_str = "\n".join(json_preview)

        bash_script = f"""#!/bin/bash\n{preview_str}
# ============================================================================
# ProDesigner Pipeline (阶段二: ProteinMPNN)
# ============================================================================
set -e
export CUDA_VISIBLE_DEVICES="{args.gpu_id.strip()}"
MPNN_SCRIPT="{args.mpnn_path.strip()}"

INPUT_DIR="{task_dir}mpnn_inputs"
OUT_DIR="{task_dir}design_output/mpnn_out"
LOG_DIR="{task_dir}logs"
LOG_FILE="$LOG_DIR/master_pipeline.log"

mkdir -p $INPUT_DIR $OUT_DIR $LOG_DIR
echo $$ > "{task_dir}main_pipeline.pid"

{{
echo "=========================================================="
echo "🚀 [Start] ProteinMPNN 设计开始时间: $(date)"
echo "=========================================================="
source {args.conda_sh.strip()}
conda activate {args.mpnn_env.strip()}

echo ">> 开始逐个读取筛选的 RF 骨架并进行序列设计..."
for PDB_FILE in $INPUT_DIR/*.pdb; do
    if [ -f "$PDB_FILE" ]; then
        BASENAME=$(basename "$PDB_FILE" .pdb)
        echo "   正在为 $BASENAME 设计序列..."
        python $MPNN_SCRIPT \\
            --pdb_path "$PDB_FILE" \\
            --out_folder $OUT_DIR \\
            --num_seq_per_target {int(args.seq_per_target)} \\
            --sampling_temp 0.1 \\
            --omit_AAs "{args.omit_aa}" \\
            --batch_size 1 {mpnn_flags} &
        
        STEP_PID=$!
        echo $STEP_PID > "{task_dir}current_step.pid"
        wait $STEP_PID
    fi
done

echo "=========================================================="
echo "🏁 [End] ProteinMPNN 结束时间: $(date)"
echo "=========================================================="
echo "✅ MPNN 生成完成！打包 mpnn_out 回传前端..."
cd {task_dir}
tar -czf mpnn_bundle.tar.gz design_output/mpnn_out/ logs/
}} 2>&1 | tee -a $LOG_FILE

echo "===BUNDLE_READY==="
"""
        sh_path = os.path.join(temp_dir, "2_run_mpnn.sh")
        with open(sh_path, 'w', encoding='utf-8', newline='\n') as f: 
            f.write(bash_script.replace('\r\n', '\n').replace('\r', ''))
        
        with open(manifest_mpnn, 'w', encoding='utf-8') as f:
            json.dump({"pdbs": rfd_pdb_paths, "jsonls": local_jsonls, "sh": sh_path, "task_dir": task_dir}, f)

        print(f"[OutputCode] .cache/2_run_mpnn.sh")
        print("\n" + "="*50)
        print(" 🛠️ MPNN 动态匹配编译完成！请点击 [4. 跑 MPNN] 执行最终运算。")
        print("="*50)


    # =========================================================================
    # Phase 4: 跑 MPNN 并回收 (Action: run_mpnn)
    # =========================================================================
    elif args.action == 'run_mpnn':
        if not HAS_SSH: print("❌ [Fatal] 缺少 paramiko"); sys.exit(1)
        if not os.path.exists(manifest_mpnn): print("❌ [Fatal] 未找到 mpnn_manifest！请先编译"); sys.exit(1)
            
        with open(manifest_mpnn, 'r', encoding='utf-8') as f: manifest = json.load(f)
        task_dir = manifest['task_dir']

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(args.ssh_host, port=int(args.ssh_port), username=args.ssh_user, password=args.ssh_pwd, timeout=10)
            
            sftp = ssh.open_sftp()
            print(f"📂 [SSH] 初始化云端沙盒目录: {task_dir}mpnn_inputs")
            _, stdout, _ = ssh.exec_command(f"mkdir -p {task_dir}mpnn_inputs")
            stdout.channel.recv_exit_status()

            print(f"⬆️ [SFTP] 投递精选 PDB、动态 JSONL 约束和脚本至云端...")
            sftp.put(manifest['sh'], f"{task_dir}2_run_mpnn.sh")
            _, stdout, _ = ssh.exec_command(f"chmod +x {task_dir}2_run_mpnn.sh")
            stdout.channel.recv_exit_status()
            
            for f in manifest['pdbs']: sftp.put(f, f"{task_dir}mpnn_inputs/{os.path.basename(f)}")
            for f in manifest['jsonls']: sftp.put(f, f"{task_dir}{os.path.basename(f)}")
            
            print(f"🔥 [SSH] 开始下发执行命令，前方发来高能日志流...\n")
            print("—" * 50)
            ssh.exec_command(f"sed -i 's/\\r$//' {task_dir}2_run_mpnn.sh")
            stdin, stdout, stderr = ssh.exec_command(f"bash -lc 'bash {task_dir}2_run_mpnn.sh'", get_pty=True)
            
            for line in iter(stdout.readline, ""):
                if not line: break
                clean_line = line.strip()
                if clean_line == "===BUNDLE_READY===": break
                if clean_line: print(f"[Cluster] {clean_line}", flush=True)

            print("—" * 50)
            print(f"\n⬇️ [SFTP] MPNN 运算结束！正在将序列包下载至前端...")
            
            remote_tar = f"{task_dir}mpnn_bundle.tar.gz"
            local_tar = os.path.join(temp_dir, "mpnn_bundle.tar.gz")
            sftp.get(remote_tar, local_tar)
            sftp.close(); ssh.close()

            try:
                with tarfile.open(local_tar, "r:gz") as tar: tar.extractall(path=temp_dir)
                for target_dir in ["design_output", "logs"]:
                    extract_dir = os.path.join(temp_dir, target_dir)
                    if os.path.exists(extract_dir):
                        for root, _, files in os.walk(extract_dir):
                            for file in files:
                                ext = os.path.splitext(file)[1].lower()
                                if ext in ['.pdb', '.fa', '.fasta', '.log']:
                                    rel_path = os.path.relpath(os.path.join(root, file), workspace)
                                    print(f"[OutputFile] {rel_path.replace(os.sep, '/')}")
            except Exception as tar_err: print(f"❌ 本地解压失败: {tar_err}")

            print(f"\n🎉 [Success] MPNN 序列重设计已全量回收！")

        except Exception as e: print(f"❌ [SSH Error] 执行崩溃: {e}"); sys.exit(1)


    # =========================================================================
    # Phase 5: 显卡占用探针 (Action: check_gpu)
    # =========================================================================
    elif args.action == 'check_gpu':
        if not HAS_SSH:
            print("❌ [Fatal] 云端直连需要 paramiko，请执行: pip install paramiko"); sys.exit(1)
            
        print(f"\n" + "="*50)
        print(f"👁️ [SSH] 正在握手云端节点: {args.ssh_host} 并查询显卡状态...")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(args.ssh_host, port=int(args.ssh_port), username=args.ssh_user, password=args.ssh_pwd, timeout=10)
            
            print("—" * 50)
            stdin, stdout, stderr = ssh.exec_command("nvidia-smi")
            for line in iter(stdout.readline, ""):
                print(line.strip('\n'), flush=True)
            print("—" * 50)
            print("✅ 显卡状态核查完毕！请确保 GPU 处于空闲状态后，再点击执行。")
            
            ssh.close()
        except Exception as e:
            print(f"❌ [SSH Error] 无法获取显卡状态，请检查网络或 IP 密码是否正确: {e}")
            sys.exit(1)

    # =========================================================================
    # Phase 6: 紧急防碰撞急停机制 (Action: abort)
    # =========================================================================
    elif args.action == 'abort':
        if not HAS_SSH:
            print("❌ [Fatal] 云端直连需要 paramiko，请执行: pip install paramiko"); sys.exit(1)
            
        print(f"\n" + "="*50)
        print(f"🛑 [SSH] 危险！接收到急停指令。正在建立高优抢占式连接...")
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(args.ssh_host, port=int(args.ssh_port), username=args.ssh_user, password=args.ssh_pwd, timeout=10)
            
            print("🔪 正在读取任务 PID，执行精准定点清除...")
            
            kill_script = f'''
            if [ -f "{task_dir}current_step.pid" ]; then
                CHILD_PID=$(cat "{task_dir}current_step.pid")
                kill -9 $CHILD_PID 2>/dev/null || true
                echo "✅ 已精确击杀当前计算子进程 (PID: $CHILD_PID)"
            fi
            if [ -f "{task_dir}main_pipeline.pid" ]; then
                MAIN_PID=$(cat "{task_dir}main_pipeline.pid")
                kill -9 $MAIN_PID 2>/dev/null || true
                echo "✅ 已精确击杀流水线主控进程 (PID: $MAIN_PID)"
            fi
            '''
            
            stdin, stdout, stderr = ssh.exec_command(kill_script)
            for line in stdout.readlines():
                print(line.strip(), flush=True)
                
            print("✅ 击杀指令执行完毕！您的设计任务已被安全中止，未误伤其他用户的进程。")
            print("💡 建议您点击 [👀 查显卡] 再次确认显存是否已被彻底释放。")
            
            ssh.close()
        except Exception as e:
            print(f"❌ [SSH Error] 紧急中断下发失败，可能需要您手动登入服务器去 kill 进程: {e}")
            sys.exit(1)

    sys.exit(0)