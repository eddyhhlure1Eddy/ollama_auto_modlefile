import sys
import os
import subprocess
import io
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QListWidgetItem, QSplitter, QTextEdit, QMessageBox, 
                             QInputDialog, QMenu, QStatusBar, QTabWidget, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
                             QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont, QTextCursor
import webbrowser
from ollama_api import OllamaAPI, ensure_utf8_encoding
import re
import tempfile
import time

class ModelfileEditor(QWidget):
    """Modelfile编辑器组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # 编辑区域
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Courier", 10))
        self.editor.setPlaceholderText("# 在此编辑Modelfile内容\n# 例如:\nFROM llama2\nPARAMETER temperature 0.7\nPARAMETER top_p 0.9\nPARAMETER stop \"User:\"\nSYSTEM 你是一个有用的AI助手。")
        
        # 工具栏
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.reset_button = QPushButton("重置")
        self.help_button = QPushButton("参数说明")
        self.template_button = QPushButton("插入模板")
        self.select_model_button = QPushButton("选择基础模型")
        
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.reset_button)
        self.button_layout.addWidget(self.help_button)
        self.button_layout.addWidget(self.template_button)
        self.button_layout.addWidget(self.select_model_button)
        
        self.layout.addWidget(QLabel("Modelfile 编辑器"))
        self.layout.addWidget(self.editor)
        self.layout.addLayout(self.button_layout)
        
        # 初始内容
        self.original_content = ""
        
        # 连接信号
        self.help_button.clicked.connect(self.show_help)
        self.template_button.clicked.connect(self.insert_template)
        self.select_model_button.clicked.connect(self.select_base_model)
        
        # API引用
        self.api = None
    
    def set_api(self, api):
        """设置API引用"""
        self.api = api
    
    def set_content(self, content):
        """设置编辑器内容"""
        self.original_content = content
        self.editor.setText(content)
    
    def get_content(self):
        """获取编辑器内容"""
        return self.editor.toPlainText()
    
    def reset(self):
        """重置为原始内容"""
        self.editor.setText(self.original_content)
    
    def select_base_model(self):
        """选择基础模型底座"""
        if not self.api:
            QMessageBox.warning(
                self,
                "错误",
                "无法获取模型列表，API引用未设置"
            )
            return
            
        # 获取可用模型列表
        models = self.api.list_models()
        if not models:
            QMessageBox.warning(
                self,
                "无法获取模型列表",
                "无法获取可用的基础模型列表。请确保Ollama服务正常运行。"
            )
            return
            
        # 提取模型名称
        model_names = [model.get('name', '') for model in models if model.get('name')]
        
        # 显示选择对话框
        model_name, ok = QInputDialog.getItem(
            self,
            "选择基础模型",
            "请选择一个基础模型作为底座:",
            model_names,
            0,
            False
        )
        
        if not ok or not model_name:
            return
            
        # 获取当前内容
        current_content = self.get_content()
        lines = current_content.strip().split('\n')
        new_content = []
        
        # 添加新的FROM指令
        from_added = False
        for line in lines:
            if line.strip().startswith('FROM '):
                new_content.append(f"FROM {model_name}")
                from_added = True
            else:
                new_content.append(line)
        
        # 如果没有找到FROM行，在开头添加
        if not from_added:
            new_content = [f"FROM {model_name}"] + new_content
            
        # 更新编辑器内容
        self.set_content("\n".join(new_content))
        
        QMessageBox.information(
            self,
            "基础模型已更新",
            f"已将基础模型设置为 {model_name}"
        )
    
    def show_help(self):
        """显示Modelfile参数说明"""
        help_text = """
<h3>Modelfile 常用参数说明</h3>

<p><b>FROM</b> - 指定基础模型，例如：llama2, mistral, gemma</p>

<p><b>PARAMETER</b> - 设置模型参数：</p>
<ul>
  <li><b>temperature</b> - 控制生成的随机性 (0.0-1.0)，越高越随机</li>
  <li><b>top_p</b> - 控制生成多样性 (0.0-1.0)</li>
  <li><b>top_k</b> - 控制每步考虑的最可能token数</li>
  <li><b>stop</b> - 停止生成的token，如 "User:", "Human:"</li>
  <li><b>num_ctx</b> - 模型上下文长度</li>
</ul>

<p><b>SYSTEM</b> - 系统提示，定义模型的行为和角色</p>

<p><b>TEMPLATE</b> - 自定义提示模板格式</p>

<p><b>ADAPTER</b> - 指定adapter文件(适用于LoRA等微调)</p>

<p>更多详细说明请参考<a href='https://github.com/ollama/ollama/blob/main/docs/modelfile.md'>Ollama Modelfile官方文档</a></p>
"""
        msg = QMessageBox()
        msg.setWindowTitle("Modelfile 参数说明")
        msg.setText(help_text)
        msg.setTextFormat(Qt.RichText)
        msg.exec_()
    
    def insert_template(self):
        """插入Modelfile模板"""
        # 获取基础模型名称
        base_model, ok = QInputDialog.getText(
            self, "基础模型", "请输入基础模型名称(如llama2, mistral等):"
        )
        
        if not ok or not base_model:
            return
        
        # 获取系统提示词
        system_prompt, ok = QInputDialog.getText(
            self, "系统提示", "请输入系统提示词:", 
            text="你是一个有用的AI助手。请简洁明了地回答问题。"
        )
        
        if not ok:
            return
        
        # 获取模板并替换变量
        template = OllamaAPI.get_modelfile_template()
        template = template.replace("{{base_model}}", base_model)
        template = template.replace("{{system_prompt}}", system_prompt)
        
        # 设置编辑器内容
        self.editor.setText(template)

class ModelDetailsWidget(QWidget):
    """模型详情显示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # 创建表格来显示模型信息
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["属性", "值"])
        self.details_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        # 创建选项卡
        self.tabs = QTabWidget()
        self.info_tab = QWidget()
        self.modelfile_tab = QWidget()
        
        # 设置信息选项卡
        self.info_layout = QVBoxLayout(self.info_tab)
        self.info_layout.addWidget(self.details_table)
        
        # 设置Modelfile选项卡
        self.modelfile_layout = QVBoxLayout(self.modelfile_tab)
        self.modelfile_editor = ModelfileEditor()
        self.modelfile_layout.addWidget(self.modelfile_editor)
        
        # 添加选项卡
        self.tabs.addTab(self.info_tab, "模型信息")
        self.tabs.addTab(self.modelfile_tab, "Modelfile")
        
        self.layout.addWidget(self.tabs)
    
    def display_model_info(self, model_info):
        """显示模型信息"""
        self.details_table.setRowCount(0)
        
        if not model_info:
            return
        
        # 添加基本信息
        self._add_table_row("名称", model_info.get("name", ""))
        self._add_table_row("大小", f"{model_info.get('size', 0) / 1024 / 1024 / 1024:.2f} GB")
        self._add_table_row("修改时间", model_info.get("modified", ""))
        
        # 添加其他可用信息
        for key, value in model_info.items():
            if key not in ["name", "size", "modified", "modelfile"]:
                if isinstance(value, (dict, list)):
                    self._add_table_row(key, str(value))
                else:
                    self._add_table_row(key, str(value))
        
        # 设置Modelfile内容
        if "modelfile" in model_info:
            self.modelfile_editor.set_content(model_info["modelfile"])
    
    def _add_table_row(self, key, value):
        """向表格添加一行"""
        row = self.details_table.rowCount()
        self.details_table.insertRow(row)
        self.details_table.setItem(row, 0, QTableWidgetItem(key))
        self.details_table.setItem(row, 1, QTableWidgetItem(value))

class CreateModelThread(QThread):
    """创建模型的线程，避免界面卡死"""
    # 定义信号
    finished = pyqtSignal(bool, str, str)  # 成功/失败, 模型名称, 错误信息
    progress = pyqtSignal(str)  # 进度消息
    
    def __init__(self, api, model_name, modelfile_content):
        super().__init__()
        self.api = api
        self.model_name = model_name
        # 确保modelfile_content是UTF-8编码
        self.modelfile_content = ensure_utf8_encoding(modelfile_content)
    
    def run(self):
        """执行模型创建"""
        try:
            # 发送进度
            self.progress.emit(f"正在创建模型 {self.model_name}...")
            
            # 重新确保UTF-8编码
            modelfile_content = ensure_utf8_encoding(self.modelfile_content)
            
            # 验证Modelfile内容 - 使用更宽松的检查，允许前导空白和注释
            has_from = False
            for line in modelfile_content.strip().split('\n'):
                line = line.strip()
                if line.startswith('#'):  # 跳过注释
                    continue
                if line.startswith('FROM '):
                    has_from = True
                    break
                if line:  # 如果遇到非空非注释行但不是FROM，则无效
                    break
                    
            if not has_from:
                self.finished.emit(False, self.model_name, "Modelfile内容无效，必须包含FROM指令")
                return
                
            # 创建模型
            success = self.api.create_model(self.model_name, modelfile_content)
            
            # 验证模型是否创建成功且可用
            if success:
                self.progress.emit(f"正在验证模型 {self.model_name}...")
                # 这里添加额外验证...
                
            # 发送结果
            if success:
                self.finished.emit(True, self.model_name, "")
            else:
                self.finished.emit(False, self.model_name, "模型创建失败，请检查日志")
        except Exception as e:
            error_msg = f"创建模型线程出错: {e}"
            print(error_msg)
            self.finished.emit(False, self.model_name, error_msg)

class OllamaManagerGUI(QMainWindow):
    """Ollama模型管理器主窗口"""
    def __init__(self):
        super().__init__()
        self.api = OllamaAPI()
        self.setup_ui()
        
        # 初始化后检查连接并加载模型
        QTimer.singleShot(100, self.check_connection)
        
        # 当前正在进行的操作
        self.current_operation = None
        self.create_thread = None
        self.model_backups = {}  # 存储模型备份信息
        
        # 防火墙规则名称
        self.firewall_rule_name_out = "OllamaSecurityOut"
        self.firewall_rule_name_in = "OllamaSecurityIn"
        
        # 检查防火墙规则状态
        self.check_firewall_rules()
    
    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("Ollama 模型管理器")
        self.setMinimumSize(1000, 600)
        
        # 中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部按钮区域
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("刷新")
        self.add_model_button = QPushButton("新建模型")
        self.pull_model_button = QPushButton("下载模型")
        self.delete_model_button = QPushButton("删除选中模型")
        self.start_ollama_button = QPushButton("启动Ollama服务")
        self.restore_model_button = QPushButton("恢复模型")
        
        # 添加安全模式复选框
        self.security_mode_checkbox = QCheckBox("安全模式(禁止联网)")
        self.security_mode_checkbox.setToolTip("开启安全模式后，Ollama将无法联网，保护本地对话安全")
        self.security_mode_checkbox.stateChanged.connect(self.toggle_security_mode)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.add_model_button)
        button_layout.addWidget(self.pull_model_button)
        button_layout.addWidget(self.delete_model_button)
        button_layout.addWidget(self.start_ollama_button)
        button_layout.addWidget(self.restore_model_button)
        button_layout.addWidget(self.security_mode_checkbox)
        button_layout.addStretch()
        
        # 设置状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # 创建拆分器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧模型列表
        self.model_list = QListWidget()
        splitter.addWidget(self.model_list)
        
        # 右侧详情区域
        self.details_widget = ModelDetailsWidget()
        splitter.addWidget(self.details_widget)
        
        # 设置API引用
        self.details_widget.modelfile_editor.set_api(self.api)
        
        # 设置拆分器比例
        splitter.setSizes([300, 700])
        
        # 添加组件到主布局
        main_layout.addLayout(button_layout)
        main_layout.addWidget(splitter)
        
        # 连接信号和槽
        self.refresh_button.clicked.connect(self.refresh_models)
        self.add_model_button.clicked.connect(self.create_new_model)
        self.pull_model_button.clicked.connect(self.pull_model)
        self.delete_model_button.clicked.connect(self.delete_selected_model)
        self.start_ollama_button.clicked.connect(self.start_ollama_service)
        self.model_list.itemClicked.connect(self.show_model_details)
        self.model_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.model_list.customContextMenuRequested.connect(self.show_context_menu)
        
        # 连接Modelfile编辑器的保存按钮
        self.details_widget.modelfile_editor.save_button.clicked.connect(self.save_modelfile)
        self.details_widget.modelfile_editor.reset_button.clicked.connect(
            self.details_widget.modelfile_editor.reset)
        
        # 添加恢复按钮
        self.restore_model_button.clicked.connect(self.restore_model)
    
    def check_connection(self):
        """检查与Ollama API的连接"""
        if self.api.check_connection():
            self.statusBar.showMessage("已连接到Ollama服务")
            self.refresh_models()
            self.start_ollama_button.setEnabled(False)  # 已连接时禁用启动按钮
        else:
            self.statusBar.showMessage("无法连接到Ollama服务", 5000)
            self.start_ollama_button.setEnabled(True)  # 未连接时启用启动按钮
            QMessageBox.warning(
                self, 
                "连接错误", 
                "无法连接到Ollama服务。请确保Ollama已安装并正在运行，或点击\"启动Ollama服务\"按钮。"
            )
    
    def refresh_models(self):
        """刷新模型列表"""
        self.model_list.clear()
        models = self.api.list_models()
        
        if not models:
            self.statusBar.showMessage("未找到模型或无法连接到Ollama")
            return
        
        for model in models:
            item = QListWidgetItem(model.get("name", "未知"))
            item.setData(Qt.UserRole, model)
            self.model_list.addItem(item)
        
        self.statusBar.showMessage(f"已加载 {len(models)} 个模型")
    
    def show_model_details(self, item):
        """显示选中模型的详细信息"""
        model_name = item.text()
        self.statusBar.showMessage(f"加载模型 {model_name} 的详细信息...")
        
        # 获取详细信息
        model_info = self.api.get_model_info(model_name)
        if model_info:
            self.details_widget.display_model_info(model_info)
            self.statusBar.showMessage(f"已加载模型 {model_name} 的详细信息")
        else:
            self.statusBar.showMessage(f"无法获取模型 {model_name} 的详细信息")
    
    def create_new_model(self):
        """创建新模型"""
        # 获取所有可用模型作为基础模型
        available_models = [self.model_list.item(i).text() for i in range(self.model_list.count())]
        
        if not available_models:
            QMessageBox.warning(
                self, 
                "创建失败", 
                "没有发现可用的基础模型。请先下载或创建至少一个模型。"
            )
            return
        
        # 第1步：让用户选择基础模型
        base_model, ok = QInputDialog.getItem(
            self,
            "选择基础模型",
            "选择一个作为基础的模型:",
            available_models,
            0,  # 默认选择第一个
            False  # 不可编辑
        )
        
        if not ok:
            return
        
        # 第2步：获取基础模型的Modelfile
        base_modelfile = self.api.get_modelfile(base_model)
        if not base_modelfile:
            QMessageBox.warning(
                self, 
                "创建失败", 
                f"无法获取模型 {base_model} 的Modelfile。"
            )
            return
        
        # 第3步：设置编辑器内容为基础模型的Modelfile并提示用户编辑
        self.details_widget.tabs.setCurrentIndex(1)  # 切换到Modelfile选项卡
        self.details_widget.modelfile_editor.set_content(base_modelfile)
        
        # 提示用户编辑Modelfile
        QMessageBox.information(
            self,
            "编辑Modelfile",
            f"您正在基于 {base_model} 创建新模型。\n\n"
            f"请在编辑器中根据需要修改Modelfile内容，例如：\n"
            f"- 调整PARAMETER参数（如temperature, top_p等）\n"
            f"- 修改SYSTEM提示词\n"
            f"- 添加其他配置\n\n"
            f"完成编辑后，点击保存按钮继续。"
        )
        
        # 第4步：保存按钮点击时要求用户输入新模型名称
        self.current_operation = "create"
        self.details_widget.modelfile_editor.save_button.clicked.disconnect()
        self.details_widget.modelfile_editor.save_button.clicked.connect(
            lambda: self._ask_model_name_and_create(base_model)
        )
    
    def _ask_model_name_and_create(self, base_model):
        """询问新模型名称并创建模型"""
        # 获取编辑后的Modelfile内容
        modelfile_content = self.details_widget.modelfile_editor.get_content()
        
        # 验证和修复Modelfile内容
        fixed_content = self._ensure_valid_from_directive(modelfile_content)
        if not fixed_content:
            return  # 用户取消了操作
        
        # 如果内容有变化，更新编辑器
        if fixed_content != modelfile_content:
            self.details_widget.modelfile_editor.set_content(fixed_content)
            modelfile_content = fixed_content
            QMessageBox.information(
                self,
                "Modelfile已更新",
                "Modelfile已更新为使用您选择的基础模型。请检查内容并确认。"
            )
        
        # 让用户输入新模型名称
        model_name, ok = QInputDialog.getText(
            self, 
            "新建模型", 
            f"您已修改了基于 {base_model} 的Modelfile。\n请为新模型命名:"
        )
        
        if not (ok and model_name):
            return
        
        # 验证模型名称合法性
        if not re.match(r'^[a-zA-Z0-9._-]+$', model_name):
            QMessageBox.warning(
                self, 
                "无效的模型名称", 
                "模型名称只能包含字母、数字、下划线、点和连字符"
            )
            return
        
        # 确认创建
        reply = QMessageBox.question(
            self,
            "确认创建",
            f"您将创建新模型 {model_name}，基于 {base_model} 的修改配置。\n是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.No:
            return
        
        # 创建模型（使用线程）
        self._create_model_with_thread(model_name, modelfile_content)
    
    def _create_model_with_thread(self, model_name, modelfile_content):
        """使用线程创建模型，避免界面卡死"""
        # 检查是否正在创建模型
        if self.create_thread and self.create_thread.isRunning():
            QMessageBox.warning(self, "正在进行中", "正在创建另一个模型，请等待完成")
            return
            
        # 只在创建新模型时验证模型名称合法性
        # 当current_operation为'save'时，表示修改现有模型，跳过名称验证
        if self.current_operation != "save" and (not model_name or not re.match(r'^[a-zA-Z0-9._-]+$', model_name)):
            QMessageBox.warning(
                self, 
                "无效的模型名称", 
                "模型名称只能包含字母、数字、下划线、点和连字符"
            )
            return
        
        # 验证Modelfile内容
        # 当current_operation为'save'时，表示修改现有模型，跳过FROM指令验证
        # 因为在save_modelfile方法中已经处理过了
        if self.current_operation != "save":
            # 创建新模型时，提供选择并可能修改内容
            fixed_content = self._ensure_valid_from_directive(modelfile_content)
            if not fixed_content:
                return  # If user canceled, abort
            modelfile_content = fixed_content
        
        # 显示等待对话框
        self.progress_dialog = QMessageBox(self)
        self.progress_dialog.setWindowTitle("创建中")
        self.progress_dialog.setText(f"正在创建模型 {model_name}，这可能需要一些时间...\n请耐心等待。")
        self.progress_dialog.setStandardButtons(QMessageBox.Cancel)
        self.progress_dialog.setDefaultButton(QMessageBox.Cancel)
        
        # 处理取消按钮
        def handle_cancel():
            if self.create_thread and self.create_thread.isRunning():
                reply = QMessageBox.question(
                    self, 
                    "确认取消", 
                    "确定要取消创建模型吗？\n注意：操作可能已在进行，取消可能不完全。",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    # 这里无法真正终止创建过程，只是关闭对话框
                    self.progress_dialog.close()
        
        # 连接取消按钮
        cancel_button = self.progress_dialog.button(QMessageBox.Cancel)
        cancel_button.clicked.disconnect()
        cancel_button.clicked.connect(handle_cancel)
        
        # 创建线程
        # 确保传入的modelfile_content是UTF-8编码
        modelfile_content = ensure_utf8_encoding(modelfile_content)
        self.create_thread = CreateModelThread(self.api, model_name, modelfile_content)
        
        # 连接信号
        self.create_thread.finished.connect(self._on_model_created)
        self.create_thread.progress.connect(self._update_progress)
        
        # 启动线程
        self.create_thread.start()
        
        # 显示进度对话框（非模态）
        self.progress_dialog.setModal(False)
        self.progress_dialog.show()
        
        # 更新状态栏
        self.statusBar.showMessage(f"正在创建模型 {model_name}...")
    
    def _update_progress(self, message):
        """更新进度信息"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setText(message)
        self.statusBar.showMessage(message)
    
    def _on_model_created(self, success, model_name, error_msg=""):
        """模型创建完成后的回调"""
        # 关闭进度对话框
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        # 处理创建结果
        if success:
            self.statusBar.showMessage(f"模型 {model_name} 创建成功")
            QMessageBox.information(self, "创建成功", f"模型 {model_name} 已成功创建")
            
            # 刷新模型列表
            self.refresh_models()
            
            # 恢复保存按钮的原始功能
            if self.current_operation == "create" or self.current_operation == "clone":
                try:
                    self.details_widget.modelfile_editor.save_button.clicked.disconnect()
                except:
                    pass
                self.details_widget.modelfile_editor.save_button.clicked.connect(self.save_modelfile)
                self.current_operation = None
            
            # 选择新创建的模型
            for i in range(self.model_list.count()):
                if self.model_list.item(i).text() == model_name:
                    self.model_list.setCurrentRow(i)
                    self.show_model_details(self.model_list.item(i))
                    break
        else:
            error_detail = f"\n错误详情: {error_msg}" if error_msg else ""
            self.statusBar.showMessage(f"模型 {model_name} 创建失败")
            QMessageBox.warning(
                self, 
                "创建失败", 
                f"无法创建模型 {model_name}\n请检查Modelfile格式和Ollama服务状态。{error_detail}"
            )
    
    def pull_model(self):
        """下载模型"""
        # 检查安全模式是否开启
        if self.security_mode_checkbox.isChecked():
            reply = QMessageBox.question(
                self,
                "安全模式警告",
                "安全模式已开启，Ollama无法联网下载模型。\n" +
                "是否暂时关闭安全模式以下载模型？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 暂时关闭安全模式
                self.security_mode_checkbox.setChecked(False)
            else:
                return
                
        model_name, ok = QInputDialog.getText(
            self, "下载模型", "输入要下载的模型名称 (例如: llama2, mistral):"
        )
        
        if ok and model_name:
            self.statusBar.showMessage(f"正在下载模型 {model_name}...")
            
            # 提示用户下载可能需要一段时间
            QMessageBox.information(
                self,
                "下载模型",
                f"正在开始下载模型 {model_name}，这可能需要一些时间。\n"
                f"Ollama将在后台下载。您可以稍后刷新列表查看下载状态。"
            )
            
            # 使用系统命令执行下载
            os.system(f'start cmd /k ollama pull {model_name}')
    
    def delete_selected_model(self):
        """删除选中的模型"""
        current_item = self.model_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "删除失败", "请先选择一个模型")
            return
        
        model_name = current_item.text()
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除模型 {model_name} 吗？这个操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.statusBar.showMessage(f"正在删除模型 {model_name}...")
            success = self.api.delete_model(model_name)
            
            if success:
                self.statusBar.showMessage(f"模型 {model_name} 已删除")
                self.refresh_models()
            else:
                self.statusBar.showMessage(f"删除模型 {model_name} 失败")
                QMessageBox.warning(self, "删除失败", f"无法删除模型 {model_name}")
    
    def save_modelfile(self):
        """保存当前编辑的Modelfile并重构模型"""
        current_item = self.model_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "保存失败", "请先选择一个模型")
            return
        
        model_name = current_item.text()
        modelfile_content = self.details_widget.modelfile_editor.get_content()
        
        # 检查Modelfile内容，如果无效，提供选择基座模型
        # 这里不使用check_only=True，允许用户选择基座模型
        fixed_content = self._ensure_valid_from_directive(modelfile_content)
        if not fixed_content:
            return  # 用户取消了选择
        
        # 如果内容有变更，更新编辑器
        if fixed_content != modelfile_content:
            self.details_widget.modelfile_editor.set_content(fixed_content)
            modelfile_content = fixed_content
            QMessageBox.information(
                self,
                "Modelfile已更新",
                "Modelfile已更新为使用您选择的基础模型。请检查内容并确认。"
            )
        
        # 显示预览并确认
        preview_dialog = QMessageBox(self)
        preview_dialog.setWindowTitle("确认Modelfile内容")
        preview_dialog.setText(f"即将更新模型 {model_name} 的Modelfile。请确认内容正确:")
        preview_dialog.setDetailedText(modelfile_content)
        preview_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        preview_dialog.setDefaultButton(QMessageBox.No)
        
        if preview_dialog.exec_() != QMessageBox.Yes:
            return
        
        # 备份原始模型的Modelfile
        try:
            original_modelfile = self.api.get_modelfile(model_name)
            backup_path = os.path.join(tempfile.gettempdir(), f"{model_name}_backup.modelfile")
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_modelfile or "")
            
            # 保存备份信息
            self.model_backups[model_name] = {
                "path": backup_path,
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "content": original_modelfile
            }
            
            self.statusBar.showMessage(f"已备份原始Modelfile到 {backup_path}")
        except Exception as e:
            print(f"备份Modelfile失败: {e}")
        
        reply = QMessageBox.question(
            self,
            "确认重构",
            f"确定要使用新的Modelfile重构模型 {model_name} 吗？\n此操作可能需要几分钟时间。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 使用线程重构模型
            self.current_operation = "save"
            # 直接传递更新后的内容
            self._create_model_with_thread(model_name, modelfile_content)
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        current_item = self.model_list.currentItem()
        if not current_item:
            return
        
        context_menu = QMenu(self)
        view_action = context_menu.addAction("查看详情")
        edit_action = context_menu.addAction("编辑Modelfile")
        clone_action = context_menu.addAction("基于此模型创建新模型")
        delete_action = context_menu.addAction("删除模型")
        export_action = context_menu.addAction("导出Modelfile")
        
        # 显示菜单并获取选择的动作
        action = context_menu.exec_(self.model_list.mapToGlobal(position))
        
        model_name = current_item.text()
        
        if action == view_action:
            self.show_model_details(current_item)
            self.details_widget.tabs.setCurrentIndex(0)  # 切换到信息选项卡
        elif action == edit_action:
            self.show_model_details(current_item)
            self.details_widget.tabs.setCurrentIndex(1)  # 切换到Modelfile选项卡
        elif action == clone_action:
            self.clone_model(model_name)
        elif action == delete_action:
            self.delete_selected_model()
        elif action == export_action:
            self.export_modelfile(model_name)
    
    def export_modelfile(self, model_name):
        """导出Modelfile到文件"""
        modelfile_content = self.api.get_modelfile(model_name)
        if not modelfile_content:
            QMessageBox.warning(self, "导出失败", f"无法获取模型 {model_name} 的Modelfile")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出Modelfile",
            f"{model_name}_Modelfile.txt",
            "文本文件 (*.txt);;所有文件 (*)"
        )
        
        if file_path:
            try:
                # 明确指定使用UTF-8编码保存文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modelfile_content)
                self.statusBar.showMessage(f"已将Modelfile导出到 {file_path}")
                QMessageBox.information(self, "导出成功", f"Modelfile已成功导出到\n{file_path}")
            except Exception as e:
                self.statusBar.showMessage(f"导出失败: {e}")
                QMessageBox.warning(self, "导出失败", f"导出Modelfile时出错:\n{e}")
    
    def start_ollama_service(self):
        """启动Ollama服务"""
        self.statusBar.showMessage("尝试启动Ollama服务...")
        
        try:
            # 使用系统命令在新窗口中启动ollama serve
            if sys.platform == 'win32':
                os.system('start cmd /k ollama serve')
            else:
                os.system('gnome-terminal -- bash -c "ollama serve; exec bash"')
            
            # 给服务一些启动时间
            QMessageBox.information(
                self,
                "启动Ollama",
                "正在启动Ollama服务，这可能需要几秒钟时间...\n"
                "服务启动后，请点击'刷新'按钮重新连接。"
            )
            
            # 3秒后尝试重新连接
            QTimer.singleShot(3000, self.check_connection)
            
        except Exception as e:
            self.statusBar.showMessage(f"启动Ollama服务失败: {e}")
            QMessageBox.warning(
                self, 
                "启动失败", 
                f"无法启动Ollama服务: {e}\n请确保Ollama已正确安装。"
            )
    
    def clone_model(self, base_model_name):
        """基于选中的模型创建新模型"""
        # 获取基础模型的Modelfile
        base_modelfile = self.api.get_modelfile(base_model_name)
        if not base_modelfile:
            QMessageBox.warning(
                self, 
                "创建失败", 
                f"无法获取模型 {base_model_name} 的Modelfile。"
            )
            return
        
        # 设置编辑器内容为基础模型的Modelfile
        self.details_widget.tabs.setCurrentIndex(1)  # 切换到Modelfile选项卡
        self.details_widget.modelfile_editor.set_content(base_modelfile)
        
        # 提示用户编辑Modelfile
        QMessageBox.information(
            self,
            "编辑Modelfile",
            f"您正在基于 {base_model_name} 创建新模型。\n\n"
            f"请在编辑器中修改Modelfile内容，例如：\n"
            f"- 可以调整PARAMETER参数（如temperature, top_p等）\n"
            f"- 可以修改SYSTEM提示词\n"
            f"- 可以添加其他配置\n\n"
            f"完成编辑后，点击保存按钮继续。"
        )
        
        # 保存按钮点击时要求用户输入新模型名称
        self.current_operation = "clone"
        self.details_widget.modelfile_editor.save_button.clicked.disconnect()
        self.details_widget.modelfile_editor.save_button.clicked.connect(
            lambda: self._ask_model_name_and_create(base_model_name)
        )

    def check_firewall_rules(self):
        """检查防火墙规则是否存在"""
        try:
            # 检查出站规则
            cmd_out = f'powershell -Command "Get-NetFirewallRule -DisplayName \'{self.firewall_rule_name_out}\' -ErrorAction SilentlyContinue"'
            result_out = subprocess.run(cmd_out, capture_output=True, text=True)
            
            # 检查入站规则
            cmd_in = f'powershell -Command "Get-NetFirewallRule -DisplayName \'{self.firewall_rule_name_in}\' -ErrorAction SilentlyContinue"'
            result_in = subprocess.run(cmd_in, capture_output=True, text=True)
            
            # 如果规则存在，则说明安全模式已开启
            if result_out.returncode == 0 and result_in.returncode == 0:
                self.security_mode_checkbox.setChecked(True)
                self.statusBar.showMessage("安全模式已开启，Ollama无法联网")
            else:
                self.security_mode_checkbox.setChecked(False)
                self.statusBar.showMessage("安全模式已关闭，Ollama可以联网")
                
        except Exception as e:
            self.statusBar.showMessage(f"检查防火墙规则失败: {e}")
            self.security_mode_checkbox.setChecked(False)
    
    def toggle_security_mode(self, state):
        """切换安全模式状态"""
        try:
            # 找到Ollama路径
            ollama_path = self.find_ollama_path()
            if not ollama_path:
                QMessageBox.warning(
                    self,
                    "找不到Ollama",
                    "无法定位Ollama可执行文件，请确保Ollama已正确安装。\n" +
                    "安全模式需要知道Ollama程序的位置才能设置防火墙规则。"
                )
                self.security_mode_checkbox.setChecked(False)
                return
                
            if state == Qt.Checked:  # 开启安全模式
                self.enable_security_mode(ollama_path)
            else:  # 关闭安全模式
                self.disable_security_mode()
        except Exception as e:
            QMessageBox.warning(
                self,
                "操作失败",
                f"设置安全模式时出错: {e}\n" +
                "可能需要以管理员身份运行此应用程序。"
            )
            # 恢复复选框状态
            self.check_firewall_rules()
    
    def find_ollama_path(self):
        """查找Ollama可执行文件的路径"""
        # 常见的Ollama安装路径
        potential_paths = [
            os.path.expanduser("~\\AppData\\Local\\Programs\\Ollama\\ollama.exe"),
            "C:\\Program Files\\Ollama\\ollama.exe",
            "C:\\Ollama\\ollama.exe"
        ]
        
        # 通过where命令找到路径
        try:
            result = subprocess.run("where ollama", capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        # 检查潜在路径
        for path in potential_paths:
            if os.path.exists(path):
                return path
                
        return None
    
    def enable_security_mode(self, ollama_path):
        """启用安全模式，禁止Ollama联网"""
        try:
            # 创建出站规则
            cmd_out = (
                f'powershell -Command "New-NetFirewallRule -DisplayName \'{self.firewall_rule_name_out}\' '
                f'-Direction Outbound -Program \'{ollama_path}\' -Action Block '
                f'-Description \'Block Ollama outbound connections for security\'"'
            )
            subprocess.run(cmd_out, check=True)
            
            # 创建入站规则
            cmd_in = (
                f'powershell -Command "New-NetFirewallRule -DisplayName \'{self.firewall_rule_name_in}\' '
                f'-Direction Inbound -Program \'{ollama_path}\' -Action Block -LocalPort Any -RemotePort Any '
                f'-Description \'Block Ollama inbound connections for security\'"'
            )
            subprocess.run(cmd_in, check=True)
            
            self.statusBar.showMessage("安全模式已开启，Ollama无法联网")
            QMessageBox.information(
                self,
                "安全模式已开启",
                "已为Ollama创建防火墙规则，禁止其联网。\n" +
                "本地对话不受影响，但无法下载新模型或访问在线资源。"
            )
        except Exception as e:
            raise Exception(f"启用安全模式失败: {e}")
    
    def disable_security_mode(self):
        """关闭安全模式，允许Ollama联网"""
        try:
            # 删除出站规则
            cmd_out = f'powershell -Command "Remove-NetFirewallRule -DisplayName \'{self.firewall_rule_name_out}\' -ErrorAction SilentlyContinue"'
            subprocess.run(cmd_out, check=True)
            
            # 删除入站规则
            cmd_in = f'powershell -Command "Remove-NetFirewallRule -DisplayName \'{self.firewall_rule_name_in}\' -ErrorAction SilentlyContinue"'
            subprocess.run(cmd_in, check=True)
            
            self.statusBar.showMessage("安全模式已关闭，Ollama可以联网")
            QMessageBox.information(
                self,
                "安全模式已关闭",
                "已移除Ollama的防火墙限制，现在可以联网。\n" +
                "可以下载新模型和访问在线资源。"
            )
        except Exception as e:
            raise Exception(f"关闭安全模式失败: {e}")

    def restore_model(self):
        """恢复损坏的模型"""
        # 检查是否有模型备份
        if not self.model_backups:
            # 尝试恢复当前选中的模型
            current_item = self.model_list.currentItem()
            if current_item:
                model_name = current_item.text()
                self._restore_specific_model(model_name)
            else:
                QMessageBox.information(
                    self,
                    "无备份",
                    "未找到模型备份。您可以手动重新拉取模型。"
                )
        else:
            # 有备份，显示选择对话框
            backup_models = list(self.model_backups.keys())
            model_name, ok = QInputDialog.getItem(
                self,
                "选择要恢复的模型",
                "选择一个要恢复的模型:",
                backup_models,
                0,
                False
            )
            
            if ok and model_name:
                self._restore_from_backup(model_name)
    
    def _restore_specific_model(self, model_name):
        """尝试恢复特定模型"""
        reply = QMessageBox.question(
            self,
            "恢复模型",
            f"是否要尝试恢复模型 {model_name}？\n这将重新拉取或重建模型。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 检查是否有备份
        backup_path = os.path.join(tempfile.gettempdir(), f"{model_name}_backup.modelfile")
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                    
                if backup_content and backup_content.strip().startswith("FROM"):
                    # 有可用备份，询问是否使用
                    use_backup = QMessageBox.question(
                        self,
                        "使用备份",
                        f"找到模型 {model_name} 的备份。是否使用备份恢复？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    
                    if use_backup == QMessageBox.Yes:
                        # 使用备份恢复
                        self._create_model_with_thread(model_name, backup_content)
                        return
            except Exception as e:
                print(f"读取备份失败: {e}")
        
        # 没有可用备份，尝试重新拉取
        try:
            # 先删除可能损坏的模型
            subprocess.run(f'ollama rm {model_name}', shell=True, capture_output=True)
            
            # 询问用户如何恢复
            options = ["重新拉取(下载)模型", "手动创建新模型", "取消"]
            choice, ok = QInputDialog.getItem(
                self,
                "恢复方式",
                f"模型 {model_name} 没有可用备份。请选择恢复方式:",
                options,
                0,
                False
            )
            
            if not ok or choice == "取消":
                return
                
            if choice == "重新拉取(下载)模型":
                # 启动下载
                QMessageBox.information(
                    self,
                    "开始下载",
                    f"即将开始下载模型 {model_name}。\n这可能需要一些时间。"
                )
                os.system(f'start cmd /k ollama pull {model_name}')
            else:
                # 创建新模型
                self.create_new_model()
        except Exception as e:
            QMessageBox.warning(
                self,
                "恢复失败",
                f"无法恢复模型 {model_name}: {e}"
            )
    
    def _restore_from_backup(self, model_name):
        """从备份恢复模型"""
        if model_name not in self.model_backups:
            QMessageBox.warning(
                self,
                "无备份",
                f"未找到模型 {model_name} 的备份。"
            )
            return
            
        backup_info = self.model_backups[model_name]
        
        reply = QMessageBox.question(
            self,
            "确认恢复",
            f"是否要从 {backup_info['time']} 的备份恢复模型 {model_name}？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 从备份恢复
        try:
            # 读取备份内容
            with open(backup_info['path'], 'r', encoding='utf-8') as f:
                backup_content = f.read()
                
            # 使用备份重建模型
            self._create_model_with_thread(model_name, backup_content)
        except Exception as e:
            QMessageBox.warning(
                self,
                "恢复失败",
                f"从备份恢复模型 {model_name} 失败: {e}"
            )

    def _ensure_valid_from_directive(self, modelfile_content, check_only=False):
        """确保Modelfile内容有有效的FROM指令，如果没有则让用户选择
        
        参数:
            modelfile_content: Modelfile内容
            check_only: 如果为True，只检查不修改内容，发现问题时返回None并警告
        """
        if not modelfile_content:
            return None
            
        # 检查是否包含有效的FROM指令
        has_valid_from = False
        from_line = ""
        lines = modelfile_content.strip().split('\n')
        
        for line in lines:
            if line.strip().startswith('#'):  # 跳过注释行
                continue
            if line.strip().startswith('FROM '):
                from_line = line.strip()
                # 检查FROM指令是否有效（不包含本地文件路径）
                if not re.search(r'FROM\s+[a-zA-Z0-9._-]+(?::[a-zA-Z0-9._-]+)?$', from_line):
                    # 无效的FROM指令
                    break
                else:
                    has_valid_from = True
                    break
            if line.strip() and not line.strip().startswith('#'):
                # 遇到非注释、非空行但不是FROM，说明Modelfile格式错误
                break
        
        if has_valid_from:
            return modelfile_content
            
        # 如果只是检查并且发现没有有效的FROM指令
        if check_only:
            QMessageBox.warning(
                self,
                "无效的Modelfile",
                "当前Modelfile没有有效的FROM指令，这可能导致模型创建失败。\n\n"
                "FROM指令应该是模型的第一个非注释指令，格式如: FROM llama2\n\n"
                "请添加或修复FROM指令后再保存。"
            )
            return None
        
        # 如果没有有效的FROM指令，提供用户选择
        # 获取可用模型列表
        models = self.api.list_models()
        if not models:
            QMessageBox.warning(
                self,
                "无法获取模型列表",
                "无法获取可用的基础模型列表。请确保Ollama服务正常运行，或手动编辑Modelfile添加有效的FROM指令。"
            )
            return None
            
        # 提取模型名称
        model_names = [model.get('name', '') for model in models if model.get('name')]
        
        # 显示选择对话框
        model_name, ok = QInputDialog.getItem(
            self,
            "选择基础模型",
            "请选择一个基础模型作为底座:",
            model_names,
            0,
            False
        )
        
        if not ok or not model_name:
            return None
            
        # 分离用户编辑器中的非FROM行内容（包括注释）
        user_content = []
        for line in lines:
            # 跳过原来的FROM行，但保留所有其他行，包括注释和空行
            if not line.strip().startswith('FROM '):
                user_content.append(line)
        
        # 构造新Modelfile：新FROM指令 + 用户编辑的其他内容
        new_content = [f"FROM {model_name}"]
        new_content.extend(user_content)
        
        return "\n".join(new_content)

if __name__ == "__main__":
    # 确保使用UTF-8编码
    if sys.platform == 'win32':
        # Windows系统下设置控制台编码为UTF-8
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)       # 设置控制台输入编码为UTF-8
        kernel32.SetConsoleOutputCP(65001) # 设置控制台输出编码为UTF-8
    
    # PyQt全局设置
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)  # 高DPI支持
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用Fusion风格提高跨平台一致性
    
    # 设置默认编码
    import locale
    locale.setlocale(locale.LC_ALL, '')
    
    window = OllamaManagerGUI()
    window.show()
    sys.exit(app.exec_()) 