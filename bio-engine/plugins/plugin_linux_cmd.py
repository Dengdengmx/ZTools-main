# plugins/plugin_linux_cmd.py
"""
Linux 全能咒语生成器插件
提供防呆与自动补全的 Linux 常用高频命令生成工具，一键复制到剪贴板。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QApplication, QStackedWidget, QDialog)
from PyQt5.QtGui import QFont

from qfluentwidgets import (LineEdit, ComboBox, BodyLabel, SubtitleLabel,
                            PushButton, PrimaryPushButton, TextEdit, 
                            PlainTextEdit, Pivot, FluentIcon as FIF,
                            InfoBar, InfoBarPosition, PrimaryPushSettingCard)

from core.plugin_manager import BasePlugin
from core.ui_base import BasePluginUI
from core.config import GlobalConfig


class LinuxCmdGeneratorUI(BasePluginUI):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(plugin_id="linux_cmd", plugin_name="Linux 咒语生成器", parent=parent)
        self.is_setting_mode = is_setting_mode
        
        # 完整的 20 条核心指令库
        self.cmd_library = {
            "🔓 [权限] 赋予脚本执行权 (chmod)": (
                "解决 Permission denied 的终极方案，让脚本跑起来。", 
                "脚本文件名 (如 run_pipeline.sh)", "", "", 
                "chmod +x {p1}"
            ),
            "🛌 [任务] 挂载后台彻夜运行 (nohup)": (
                "将跑几十个小时的流水线挂到后台，关机下班也不中断。", 
                "要运行的脚本 (如 ./run.sh)", "输出日志名 (如 out.log)", "", 
                "nohup {p1} > {p2} 2>&1 &"
            ),
            "🔪 [任务] 强制杀掉暴走进程 (kill -9)": (
                "AI 跑飞了或者显卡卡死了？用这个物理超度它。", 
                "进程 PID (敲 nvidia-smi 看到的数字)", "", "", 
                "kill -9 {p1}"
            ),
            "🕵️ [任务] 实时滚动看监控日志 (tail -f)": (
                "像看电影字幕一样，实时查看后台任务跑到了哪一步。", 
                "日志文件名 (如 out.log)", "", "", 
                "tail -f {p1}"
            ),
            "🔄 [传输] 本地传到服务器 (scp upload)": (
                "将本地电脑的文件或脚本安全传送到远端服务器。", 
                "本地文件路径 (如 ./run.sh)", "服务器账号@IP (如 root@192.168.1.1)", "服务器存放路径 (如 /home/)", 
                "scp {p1} {p2}:{p3}"
            ),
            "🔄 [传输] 服务器下载到本地 (scp download)": (
                "将服务器跑完的序列拖回本地电脑。", 
                "服务器账号@IP", "服务器文件路径 (如 /home/res.zip)", "本地存放路径 (如 ./)", 
                "scp {p1}:{p2} {p3}"
            ),
            "🚀 [同步] 高可靠断点续传/同步 (rsync)": (
                "安全同步几百G的文件夹，中途断网也不怕，再次运行接着传。", 
                "源数据 (如 user@ip:/data/)", "目标存放地 (如 ./local_data/)", "", 
                "rsync -avzP {p1} {p2}"
            ),
            "🌐 [网络] 下载文件 (wget)": (
                "直接从网上下载 PDB 模板或开源代码包。", 
                "URL下载链接", "", "", 
                "wget {p1}"
            ),
            "📁 [文件] 复制文件或文件夹 (cp)": (
                "备份脚本或复制 PDB 模板。加了 -r 可以连带复制整个文件夹。", 
                "源文件或文件夹", "目标位置", "", 
                "cp -r {p1} {p2}"
            ),
            "🚚 [文件] 移动或重命名 (mv)": (
                "将结果移到归档目录，或者给跑错名字的文件改名。", 
                "原路径/旧名字", "新路径/新名字", "", 
                "mv {p1} {p2}"
            ),
            "📂 [文件] 瞬间创建多层目录 (mkdir -p)": (
                "一次性建好深层文件夹，如 a/b/c，不会报错说父目录不存在。", 
                "目录路径 (如 project/designs/mpnn)", "", "", 
                "mkdir -p {p1}"
            ),
            "🗑️ [文件] 强力删除文件或目录 (rm -rf)": (
                "【高危操作】强制删除垃圾数据，不会反复问你确认。", 
                "要删除的目标 (如 junk_folder/)", "", "", 
                "rm -rf {p1}"
            ),
            "🐍 [环境] 查看 Conda 环境列表 (env list)": (
                "忘记实验室服务器上有哪些 Python 虚拟环境时使用。", 
                "", "", "", 
                "conda env list"
            ),
            "👁️ [系统] 显卡实时盯盘监控 (watch nvidia-smi)": (
                "像看股票一样实时刷新显存占用率，防别人抢卡。", 
                "刷新间隔(秒)", "", "", 
                "watch -n {p1} nvidia-smi"
            ),
            "💾 [系统] 查看服务器硬盘剩余空间 (df)": (
                "如果 AI 报错说 'No space left'，用它看哪个硬盘被撑爆了。", 
                "", "", "", 
                "df -h"
            ),
            "📊 [系统] 查出占用最大的巨型文件夹 (du)": (
                "揪出占用几百G的硬盘刺客，按大小自动排序输出。", 
                "要扫描的目录 (如 /home/user)", "", "", 
                "du -sh {p1}/* | sort -h"
            ),
            "🔍 [系统] 全盘地毯式搜索文件 (find)": (
                "在全服务器迷宫中寻找丢失的脚本或 PDB。", 
                "搜索起点 (如 ~ 或 /)", "文件名 (支持加星号如 *.pdb)", "", 
                "find {p1} -name '{p2}' 2>/dev/null"
            ),
            "📦 [打包] 将输出结果压缩为 tar.gz": (
                "把成百上千个散落的 FASTA 文件打包成一个文件，方便下载提取。", 
                "压缩包命名 (如 res.tar.gz)", "要打包的目录 (如 mpnn_out/)", "", 
                "tar -czvf {p1} {p2}"
            ),
            "🎁 [打包] 解压 tar.gz 压缩包": (
                "解压网盘下载的软件环境包或数据包。", 
                "压缩包名字", "解压到哪个目录(如 ./ , 留空默认当前)", "", 
                "tar -xzvf {p1} -C {p2}"
            ),
            "🎁 [打包] 解压 zip 压缩包 (unzip)": (
                "解压最常见的 zip 格式压缩包。", 
                "压缩包名字 (如 data.zip)", "", "", 
                "unzip {p1}"
            )
        }
        
        self.hints_map = {
            "chmod": ["run_pipeline.sh", "", ""],
            "nohup": ["./run_pipeline.sh", "terminal_out.log", ""],
            "kill": ["12345", "", ""],
            "tail": ["terminal_out.log", "", ""],
            "scp upload": ["./run_pipeline.sh", "root@192.168.1.100", "/home/user/"],
            "scp download": ["root@192.168.1.100", "/home/user/res.tar.gz", "./"],
            "rsync": ["user@192.168.1.100:/data/", "./local_data/", ""],
            "wget": ["https://files.rcsb.org/download/6XKL.pdb", "", ""],
            "cp": ["template.pdb", "./new_folder/", ""],
            "mv": ["old.fa", "new.fa", ""],
            "mkdir -p": ["project/designs/mpnn", "", ""],
            "rm -rf": ["junk_folder/", "", ""],
            "du": ["/home/user", "", ""],
            "watch nvidia-smi": ["1", "", ""],
            "find": ["~", "*.pdb", ""],
            "tar -czvf": ["results.tar.gz", "mpnn_out/", ""],
            "tar -xzvf": ["data.tar.gz", "./", ""],
            "unzip": ["data.zip", "", ""]
        }

        self._setup_ui()
        self.update_inputs()

    def _setup_ui(self):
        # ==========================================
        # 左侧：动态配置区
        # ==========================================
        grp_task, lyt_task = self.create_group("1. 选择服务器操作目标")
        
        self.combo_task = ComboBox()
        self.combo_task.addItems(list(self.cmd_library.keys()))
        self.combo_task.currentIndexChanged.connect(self.update_inputs)
        
        self.lbl_desc = BodyLabel("请在上方选择一个任务...")
        self.lbl_desc.setStyleSheet("color: #0078D7; font-weight: bold;")
        self.lbl_desc.setWordWrap(True)
        
        lyt_task.addWidget(self.combo_task)
        lyt_task.addSpacing(5)
        lyt_task.addWidget(self.lbl_desc)
        self.add_param_widget(grp_task)

        grp_params, self.lyt_params = self.create_group("2. 设定参数 (自动防呆补全)")
        
        self.param_widgets = []
        for i in range(3):
            container = QWidget()
            lyt = QVBoxLayout(container)
            lyt.setContentsMargins(0, 0, 0, 5)
            
            lbl = BodyLabel(f"参数 {i+1}:")
            ent = LineEdit()
            
            lyt.addWidget(lbl)
            lyt.addWidget(ent)
            
            self.lyt_params.addWidget(container)
            self.param_widgets.append({"container": container, "label": lbl, "entry": ent})
            
        self.add_param_widget(grp_params)

        btn_generate = PrimaryPushButton("⚡ 生成标准命令并复制", icon=FIF.COPY)
        btn_generate.setFixedHeight(45)
        btn_generate.clicked.connect(self.generate_command)
        self.param_layout.addWidget(btn_generate)

        if self.is_setting_mode:
            btn_close = PushButton("关闭设置")
            btn_close.clicked.connect(self.save_settings_and_close)
            self.param_layout.addWidget(btn_close)
            return

        self.add_param_stretch()

        # ==========================================
        # 右侧：输出与速查区
        # ==========================================
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pivot = Pivot(self.canvas_panel)
        self.stacked_widget = QStackedWidget(self.canvas_panel)
        
        vbox = QVBoxLayout()
        vbox.addWidget(self.pivot)
        vbox.addWidget(self.stacked_widget)
        self.canvas_layout.addLayout(vbox)

        # Tab 1: 生成的命令
        self.cmd_display = TextEdit()
        self.cmd_display.setFont(QFont("Consolas", 15, QFont.Bold))
        self.cmd_display.setReadOnly(True)
        self.cmd_display.setStyleSheet("background-color: #1e1e1e; color: #4ec9b0; border: none; padding: 20px;")
        self.cmd_display.setPlainText(">_ 等待指令生成...")
        self.addSubInterface(self.cmd_display, 'cmdInterface', '💻 生成指令')

        # Tab 2: 速查手册
        self.cheat_display = TextEdit()
        self.cheat_display.setFont(QFont("Consolas", 11))
        self.cheat_display.setReadOnly(True)
        self.cheat_display.setStyleSheet("background-color: #f4f4f4; color: #333333; border: none;")
        self.addSubInterface(self.cheat_display, 'cheatInterface', '💡 终端速查手册')
        self._load_cheat_sheet()

        self.stacked_widget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem('cmdInterface')

    def addSubInterface(self, widget, objectName, text):
        widget.setObjectName(objectName)
        self.stacked_widget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stacked_widget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stacked_widget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

    def _load_cheat_sheet(self):
        html_text = """
        <div style="padding: 10px; line-height: 1.6;">
            <h3 style="color: #0078D7;">【救急操作】</h3>
            <ul>
                <li><b>[Ctrl + C]</b> : 强制中断当前正在满屏滚代码的任务！(救命神键)</li>
                <li><b>[Ctrl + L]</b> : 清空当前屏幕所有的乱码，还你一个干净的终端。</li>
                <li><b>[Tab] 键</b>   : 敲文件名敲一半时按它，自动补全！别再纯手打了。</li>
                <li><b>[↑] 上方向键</b>: 调出刚刚执行过的上一条命令。</li>
            </ul>
            
            <h3 style="color: #0078D7; margin-top: 20px;">【迷路时怎么找回自己】</h3>
            <ul>
                <li><b>[pwd]</b>      : 打印当前绝对路径 (我到底在哪个文件夹？)</li>
                <li><b>[cd ~]</b>     : 瞬间传送回自己的老家 (根用户目录)。</li>
                <li><b>[cd ..]</b>    : 退回上一级文件夹。</li>
                <li><b>[ls -lh]</b>   : 列出当前目录下所有的文件，并用人类看得懂的单位显示大小。</li>
            </ul>
        </div>
        """
        self.cheat_display.setHtml(html_text)

    def update_inputs(self, index=0):
        task = self.combo_task.currentText()
        if not task in self.cmd_library: return
        
        desc, p1_name, p2_name, p3_name, template = self.cmd_library[task]
        self.lbl_desc.setText(f"💡 说明: {desc}")
        
        p_names = [p1_name, p2_name, p3_name]
        
        current_hints = ["", "", ""]
        for key, hints in self.hints_map.items():
            if key in task:
                current_hints = hints
                break
        
        for i in range(3):
            widget_set = self.param_widgets[i]
            if p_names[i]:
                widget_set["container"].show()
                widget_set["label"].setText(p_names[i] + ":")
                
                # 如果输入框为空，或者输入框里的内容是别的任务的默认 Hint，则刷新它
                current_val = widget_set["entry"].text()
                all_hints = sum(self.hints_map.values(), [])
                if not current_val or current_val in all_hints:
                    widget_set["entry"].setText(current_hints[i])
            else:
                widget_set["container"].hide()
                widget_set["entry"].clear()

    def generate_command(self):
        task = self.combo_task.currentText()
        if not task in self.cmd_library: return
        
        _, _, _, _, template = self.cmd_library[task]
        
        p1 = self.param_widgets[0]["entry"].text().strip()
        p2 = self.param_widgets[1]["entry"].text().strip()
        p3 = self.param_widgets[2]["entry"].text().strip()
        
        final_cmd = template.replace("{p1}", p1).replace("{p2}", p2).replace("{p3}", p3).strip()
        
        if final_cmd.endswith("-C"): 
            final_cmd = final_cmd[:-2].strip()

        self.cmd_display.setPlainText(f">_ {final_cmd}")
        
        # 复制到原生剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(final_cmd)
        
        # 使用现代化的 InfoBar 提示
        InfoBar.success(
            title='✅ 命令已复制',
            content='Linux 命令已自动复制到剪贴板！\n请切换到终端 (Xshell/MobaXterm) 右键粘贴。',
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self.window()
        )

    def save_settings_and_close(self):
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog):
            parent_dlg.accept()


# ==========================================
# 后端：插件描述器
# ==========================================
class LinuxCmdPlugin(BasePlugin):
    plugin_id = "linux_cmd"
    plugin_name = "Linux 咒语生成器"
    icon = "🐧"
    trigger_tag = "运维工具"

    def get_ui(self, parent=None):
        return LinuxCmdGeneratorUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        card = PrimaryPushSettingCard(
            "预览工具", 
            FIF.COMMAND_PROMPT, 
            "🐧 Linux 咒语生成器", 
            "此工具无全局参数，点击可直接打开窗口使用。", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card)
            dlg.setWindowTitle("Linux 终端命令速查生成")
            dlg.resize(800, 500)
            dlg.setStyleSheet("QDialog { background-color: #F9F9F9; }")
            layout = QVBoxLayout(dlg)
            settings_ui = LinuxCmdGeneratorUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    @staticmethod
    def run(file_path, archive_dir):
        return "", "【Linux 咒语生成器】这是一个纯交互式的前端工具，请在工作台中点击 UI 面板使用。"