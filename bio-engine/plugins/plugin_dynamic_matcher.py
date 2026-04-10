# plugins/plugin_dynamic_matcher.py
import os
import sys
import argparse
import json
import tarfile

try:
    import paramiko
    HAS_SSH = True
except ImportError:
    HAS_SSH = False

PLUGIN_NAME = "变长设计与动态匹配引擎 (云端两段式版)"
PLUGIN_ICON = "🧬"
PLUGIN_DESC = "用于变长 Scaffold/Contig 设计。先运行 RF 拉回结果，人工挑选骨架后，再执行动态序列匹配生成精准的约束跑 MPNN。自带编译后序列比对视图！"

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
    {"key": "two_stage", "label": "🔀 开启两段式交互 (变长匹配原理级强制要求开启)", "type": "boolean", "default": True, "span": 12},
    
    {"key": "orig_pdb", "label": "📁 第一阶段：原始骨架/靶点 (WT) PDB (必填)", "type": "file", "span": 12},
    {"key": "rfd_pdbs", "label": "📁 第二阶段：挑选满意的 RF 骨架用于 MPNN (多选)", "type": "file", "span": 12},

    {"key": "mode", "label": "设计模式", "type": "select", "options": [
        "Partial Diffusion (局部微调/构象锁定)", 
        "Motif Scaffolding (变长与搭桥)", 
        "Binder Design (蛋白结合子设计)", 
        "Unconditional (De novo)"
    ], "default": "Motif Scaffolding (变长与搭桥)", "span": 12},

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
    
    {"key": "server_dir", "label": "云端工作流根目录", "type": "string", "default": "/home/user/ztools_workspace/", "span": 8},
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
        {"id": "compile_rfd", "label": "1. 编译 RF", "type": "default"},
        {"id": "run_rfd", "label": "2. 跑 RF 并回收", "type": "primary"},
        {"id": "compile_mpnn", "label": "3. 对齐编译 MPNN", "type": "default"},
        {"id": "run_mpnn", "label": "4. 跑 MPNN", "type": "primary"},
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
                        res_num_raw = line[22:27].strip()
                        res_num_str = "".join([c for c in res_num_raw if c.isdigit() or c == '-'])
                        if res_num_str:
                            pdb_data[chain]['seq'][int(res_num_str)] = AA_MAP[res_name]
            except Exception: pass 
    return pdb_data

def generate_alignment_comments(pdb_data_dict, fixed_data_map, bias_data_map):
    """生成极其直观的序列、二级结构、与动态约束比对视图"""
    align_comments = []
    align_comments.append("# ============================================================================")
    align_comments.append("# 📊 编译后序列对齐与约束落位视图 (Visual Alignment)")
    align_comments.append("# ============================================================================")
    align_comments.append("# 说明: IDX代表连续编号. H(螺旋) E(折叠) C(卷曲). 约束: F(锁定) B(偏好) -(自由)")
    align_comments.append("#")
    
    for pdb_name, data in pdb_data_dict.items():
        local_fixed = fixed_data_map.get(pdb_name, {})
        local_bias = bias_data_map.get(pdb_name, {})
        has_bias = len(local_bias) > 0

        align_comments.append(f"# >>> 实体模型: {pdb_name} <<<")
        for chain, cdata in data.items():
            seq_dict = cdata['seq']
            if not seq_dict: continue
            align_comments.append(f"# ---------- Chain {chain} ----------")
            sorted_res = sorted(list(seq_dict.keys()))
            seq_str = "".join([seq_dict[r] for r in sorted_res])
            fix_str = "".join(["F" if (chain in local_fixed and r in local_fixed[chain]) else "-" for r in sorted_res])

            bia_str = ""
            for r in sorted_res:
                b_val = local_bias.get(chain, {}).get(r) or local_bias.get(chain, {}).get(str(r))
                if isinstance(b_val, dict): bia_str += list(b_val.keys())[0]
                elif isinstance(b_val, str): bia_str += b_val
                else: bia_str += "-"

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
    parser.add_argument('--action', type=str, default='compile_rfd')
    for item in UI_SCHEMA:
        if item["type"] == "boolean": parser.add_argument(f"--{item['key']}", action="store_true")
        elif item["type"] == "number": parser.add_argument(f"--{item['key']}", type=float, default=item.get("default", 0.0))
        else: parser.add_argument(f"--{item['key']}", type=str, default=str(item.get("default", "")))
            
    args = parser.parse_args()
    
    workspace = get_sync_workspace()
    temp_dir = os.path.join(workspace, ".cache")
    os.makedirs(temp_dir, exist_ok=True)
    manifest_rfd = os.path.join(temp_dir, "matcher_rfd_manifest.json")
    manifest_mpnn = os.path.join(temp_dir, "matcher_mpnn_manifest.json")
    
    server_dir = args.server_dir.strip()
    if server_dir and not server_dir.endswith('/'): server_dir += '/'
    task_dir = f"{server_dir}task_dynamic_matcher/"

    # =========================================================================
    # Phase 1: 编译 RFdiffusion (Action: compile_rfd)
    # =========================================================================
    if args.action == 'compile_rfd':
        print(">>> 启动第一阶段：编译 RF 拓扑扩散脚本...")
        
        if not getattr(args, 'two_stage', False):
            print("❌ [拦截] 变长设计与匹配引擎【必须】使用两段式交互流水线。")
            print("💡 原因: 需要先让云端跑出 RF 变长骨架并拉回本地，才能由本机 Python 执行精确的子序列拓扑追踪与对齐。")
            print("👉 请勾选参数顶部的 [🔀 开启两段式交互] 选项后再试！"); sys.exit(1)

        orig_pdb_str = str(getattr(args, 'orig_pdb', '')).strip()
        if not orig_pdb_str:
            print("❌ [Fatal] 请上传【原始骨架/靶点 (WT) PDB】！"); sys.exit(1)
            
        orig_pdb_path = os.path.join(workspace, orig_pdb_str.split(',')[0].strip())
        if not os.path.exists(orig_pdb_path):
            print(f"❌ [Fatal] 找不到原始 PDB: {orig_pdb_path}"); sys.exit(1)

        # 构建对原始 WT PDB 的序列约束预览视图
        orig_name = os.path.splitext(os.path.basename(orig_pdb_path))[0]
        orig_data_dict = { orig_name: parse_pdb_atoms(orig_pdb_path) }
        global_fixed, global_bias = {}, {}
        
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

        align_str = generate_alignment_comments(orig_data_dict, {orig_name: global_fixed}, {orig_name: global_bias})

        rfd_extras = ""
        if "Binder" in args.mode and args.hotspot: rfd_extras += f" \\\n            ppi.hotspot_res=[{args.hotspot}]"
        if "Partial" in args.mode: rfd_extras += f" \\\n            diffuser.partial_T={args.partial_t}"
        if args.ss_bias.strip(): rfd_extras += f" \\\n            scaffoldguided.scaffoldguided=True scaffoldguided.target_ss=\"{args.ss_bias.strip()}\""
        
        bash_script = f"""#!/bin/bash\n{align_str}
# ============================================================================
# 动态匹配引擎 Phase 1: RFdiffusion
# ============================================================================
set -e
export CUDA_VISIBLE_DEVICES="{args.gpu_id.strip()}"
RFD_SCRIPT="{args.rfd_path.strip()}"

INPUT_DIR="{task_dir}wt_input"
OUT_DIR="{task_dir}design_output/rfd_out"
LOG_DIR="{task_dir}logs"
LOG_FILE="$LOG_DIR/master_pipeline.log"

mkdir -p $INPUT_DIR $OUT_DIR $LOG_DIR
echo $$ > "{task_dir}main_pipeline.pid"

{{
echo "=========================================================="
echo "🚀 [Start] RFdiffusion 生成开始时间: $(date)"
echo "=========================================================="
source {args.conda_sh.strip()}
conda activate {args.rfd_env.strip()}

for INPUT_PDB in $INPUT_DIR/*.pdb; do
    if [ -f "$INPUT_PDB" ]; then
        BASENAME=$(basename "$INPUT_PDB" .pdb)
        echo ">> [RF] 正在扩散: $BASENAME"
        python $RFD_SCRIPT \\
            inference.input_pdb="$INPUT_PDB" \\
            inference.output_prefix=$OUT_DIR/${{BASENAME}} \\
            contigmap.contigs="{args.contig}" \\
            inference.num_designs={int(args.num_designs)}{rfd_extras} &
        
        STEP_PID=$!
        echo $STEP_PID > "{task_dir}current_step.pid"
        wait $STEP_PID
    fi
done

echo "=========================================================="
echo "🏁 [End] RFdiffusion 结束时间: $(date)"
echo "=========================================================="
echo "✅ RF 生成完成！打包 rfd_out 回传前端..."
cd {task_dir}
tar -czf rfd_bundle.tar.gz design_output/rfd_out/ logs/
}} 2>&1 | tee $LOG_FILE

echo "===BUNDLE_READY==="
"""
        sh_path = os.path.join(temp_dir, "1_run_rfd.sh")
        with open(sh_path, 'w', encoding='utf-8', newline='\n') as f: 
            f.write(bash_script.replace('\r\n', '\n').replace('\r', ''))
        
        with open(manifest_rfd, 'w', encoding='utf-8') as f:
            json.dump({"orig_pdb": orig_pdb_path, "sh": sh_path, "task_dir": task_dir}, f)

        print(f"[OutputCode] .cache/1_run_rfd.sh")
        print("\n" + "="*50)
        print(" 🛠️ RF 编译完成！请在上方代码区检查原始序列比对后，点击 [2. 跑 RF 并回收]。")
        print("="*50)


    # =========================================================================
    # Phase 2: 跑 RF 并回收 (Action: run_rfd)
    # =========================================================================
    elif args.action == 'run_rfd':
        if not HAS_SSH: print("❌ [Fatal] 缺少 paramiko"); sys.exit(1)
        if not os.path.exists(manifest_rfd): print("❌ [Fatal] 未找到 rfd_manifest！"); sys.exit(1)
            
        with open(manifest_rfd, 'r', encoding='utf-8') as f: manifest = json.load(f)
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(args.ssh_host, port=int(args.ssh_port), username=args.ssh_user, password=args.ssh_pwd, timeout=10)
            
            sftp = ssh.open_sftp()
            print(f"📂 [SSH] 初始化云端沙盒目录: {task_dir}wt_input")
            _, stdout, _ = ssh.exec_command(f"mkdir -p {task_dir}wt_input")
            stdout.channel.recv_exit_status()

            print(f"⬆️ [SFTP] 投递 WT PDB 和 RF 脚本至云端...")
            sftp.put(manifest['sh'], f"{task_dir}1_run_rfd.sh")
            _, stdout, _ = ssh.exec_command(f"chmod +x {task_dir}1_run_rfd.sh")
            stdout.channel.recv_exit_status()
            
            sftp.put(manifest['orig_pdb'], f"{task_dir}wt_input/{os.path.basename(manifest['orig_pdb'])}")
            
            print(f"🔥 [SSH] 开始下发执行命令，前方发来高能日志流...\n")
            print("—" * 50)
            ssh.exec_command(f"sed -i 's/\\r$//' {task_dir}1_run_rfd.sh")
            stdin, stdout, stderr = ssh.exec_command(f"bash -lc 'bash {task_dir}1_run_rfd.sh'", get_pty=True)
            
            for line in iter(stdout.readline, ""):
                if not line: break
                clean_line = line.strip()
                if clean_line == "===BUNDLE_READY===": break
                if clean_line: print(f"[Cluster] {clean_line}", flush=True)

            print("—" * 50)
            print(f"\n⬇️ [SFTP] RF 运算结束！正在将骨架打包下载至前端...")
            
            remote_tar = f"{task_dir}rfd_bundle.tar.gz"
            local_tar = os.path.join(temp_dir, "rfd_bundle.tar.gz")
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
                                if ext in ['.pdb', '.log']:
                                    rel_path = os.path.relpath(os.path.join(root, file), workspace)
                                    print(f"[OutputFile] {rel_path.replace(os.sep, '/')}")
            except Exception as tar_err: print(f"❌ 本地解压失败: {tar_err}")

            print(f"\n🎉 [Success] RF 骨架已回收！")
            print("👉 请在左侧【📤 批量产物导出】保存满意的骨架，并将其拖入第二阶段的参数框中！")

        except Exception as e: print(f"❌ [SSH Error] 执行崩溃: {e}"); sys.exit(1)


    # =========================================================================
    # Phase 3: 动态匹配并编译 MPNN (Action: compile_mpnn)
    # =========================================================================
    elif args.action == 'compile_mpnn':
        print(">>> 启动第二阶段：动态序列对齐与 MPNN 编译...")
        orig_pdb_str = str(getattr(args, 'orig_pdb', '')).strip()
        rfd_pdbs_str = str(getattr(args, 'rfd_pdbs', '')).strip()
        
        if not orig_pdb_str or not rfd_pdbs_str:
            print("❌ [Fatal] 请确保已正确填写【原始WT PDB】与【挑选的 RF 骨架】！"); sys.exit(1)
            
        orig_pdb_path = os.path.join(workspace, orig_pdb_str.split(',')[0].strip())
        rfd_pdb_paths = [os.path.join(workspace, p.strip()) for p in rfd_pdbs_str.split(',') if p.strip()]

        print(">>> 启动 [固定区块顺序寻迹] 防弹追踪引擎...")
        
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
        
        rfd_parsed_dict = {}
        generated_fixed_data, generated_bias_data, generated_omit_data = {}, {}, {}
        success_count, fail_count = 0, 0

        for rf_path in rfd_pdb_paths:
            if not os.path.exists(rf_path): continue
            rf_name = os.path.splitext(os.path.basename(rf_path))[0]
            
            try:
                rf_data = parse_pdb_atoms(rf_path)
                rfd_parsed_dict[rf_name] = rf_data
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
                                    temp_map[orig_res_num] = (rf_chain, int(rf_mapped_idx))
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
                        if rf_chain: rf_fixed.setdefault(rf_chain, []).append(mapped_idx)

                for orig_chain in global_bias:
                    if orig_chain not in orig_data: continue
                    for req_num, mut_aa in global_bias[orig_chain].items():
                        rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                        if rf_chain: rf_bias.setdefault(rf_chain, {})[str(mapped_idx)] = {mut_aa: 10000.0}

                for orig_chain in global_omit:
                    if orig_chain not in orig_data: continue
                    for req_num in global_omit[orig_chain]:
                        rf_chain, mapped_idx = get_mapped(orig_chain, req_num)
                        if rf_chain: rf_omit.setdefault(rf_chain, {})[str(mapped_idx)] = "PG"

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

        # 🌟 核心：注入变长后的真实骨架约束对齐视图！
        align_str = generate_alignment_comments(rfd_parsed_dict, generated_fixed_data, generated_bias_data)

        bash_script = f"""#!/bin/bash\n{align_str}
# ============================================================================
# 动态匹配引擎 Phase 2: ProteinMPNN
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
        print(" 🛠️ MPNN 动态匹配编译完成！请在上方代码区检查真实落位对齐后，点击 [4. 跑 MPNN]。")
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
        if not HAS_SSH: print("❌ [Fatal] 缺少 paramiko"); sys.exit(1)
        print(f"\n" + "="*50)
        print(f"👁️ [SSH] 正在握手云端节点: {args.ssh_host} 并查询显卡状态...")
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(args.ssh_host, port=int(args.ssh_port), username=args.ssh_user, password=args.ssh_pwd, timeout=10)
            print("—" * 50)
            stdin, stdout, stderr = ssh.exec_command("nvidia-smi")
            for line in iter(stdout.readline, ""): print(line.strip('\n'), flush=True)
            print("—" * 50)
            ssh.close()
        except Exception as e: print(f"❌ [SSH Error] 获取显卡状态失败: {e}"); sys.exit(1)

    # =========================================================================
    # Phase 6: 紧急防碰撞急停机制 (Action: abort)
    # =========================================================================
    elif args.action == 'abort':
        if not HAS_SSH: print("❌ [Fatal] 缺少 paramiko"); sys.exit(1)
        print(f"\n" + "="*50)
        print(f"🛑 [SSH] 危险！接收到急停指令。正在建立高优抢占式连接...")
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(args.ssh_host, port=int(args.ssh_port), username=args.ssh_user, password=args.ssh_pwd, timeout=10)
            
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
            for line in stdout.readlines(): print(line.strip(), flush=True)
            print("✅ 您的设计任务已被安全中止，未误伤其他用户的进程。")
            ssh.close()
        except Exception as e: print(f"❌ [SSH Error] 紧急中断下发失败: {e}"); sys.exit(1)

    sys.exit(0)