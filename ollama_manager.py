import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QListWidgetItem, QSplitter, QTextEdit, QMessageBox, 
                             QInputDialog, QMenu, QStatusBar, QTabWidget, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QFont, QTextCursor
import webbrowser
from ollama_api import OllamaAPI

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
        
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.reset_button)
        self.button_layout.addWidget(self.help_button)
        self.button_layout.addWidget(self.template_button)
        
        self.layout.addWidget(QLabel("Modelfile 编辑器"))
        self.layout.addWidget(self.editor)
        self.layout.addLayout(self.button_layout)
        
        # 初始内容
        self.original_content = ""
        
        # 连接信号
        self.help_button.clicked.connect(self.show_help)
        self.template_button.clicked.connect(self.insert_template)
    
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

class OllamaManagerGUI(QMainWindow):
    """Ollama模型管理器主窗口"""
    def __init__(self):
        super().__init__()
        self.api = OllamaAPI()
        self.setup_ui()
        
        # 初始化后检查连接并加载模型
        QTimer.singleShot(100, self.check_connection)
    
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
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.add_model_button)
        button_layout.addWidget(self.pull_model_button)
        button_layout.addWidget(self.delete_model_button)
        button_layout.addWidget(self.start_ollama_button)
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
        self.details_widget.modelfile_editor.save_button.clicked.disconnect()
        self.details_widget.modelfile_editor.save_button.clicked.connect(
            lambda: self._ask_model_name_and_create(base_model)
        )
    
    def _ask_model_name_and_create(self, base_model):
        """询问新模型名称并创建模型"""
        # 获取编辑后的Modelfile内容
        modelfile_content = self.details_widget.modelfile_editor.get_content()
        
        if not modelfile_content:
            QMessageBox.warning(self, "创建失败", "Modelfile内容不能为空")
            return
        
        # 让用户输入新模型名称
        model_name, ok = QInputDialog.getText(
            self, 
            "新建模型", 
            f"您已修改了基于 {base_model} 的Modelfile。\n请为新模型命名:"
        )
        
        if not (ok and model_name):
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
        
        # 创建模型
        self._create_model_with_modelfile(model_name)
    
    def _create_model_with_modelfile(self, model_name):
        """使用Modelfile创建模型"""
        modelfile_content = self.details_widget.modelfile_editor.get_content()
        
        if not modelfile_content:
            QMessageBox.warning(self, "创建失败", "Modelfile内容不能为空")
            return
        
        # 检查是否修改了FROM行，如果没有修改则提醒用户
        first_line = modelfile_content.split('\n')[0] if modelfile_content else ""
        self.statusBar.showMessage(f"正在创建模型 {model_name}...")
        
        # 提示用户操作正在进行
        progress_msg = QMessageBox(self)
        progress_msg.setWindowTitle("创建中")
        progress_msg.setText(f"正在创建模型 {model_name}，这可能需要一些时间...\n请耐心等待。")
        progress_msg.setStandardButtons(QMessageBox.NoButton)
        progress_msg.show()
        
        # 处理事件，确保消息框显示
        QApplication.processEvents()
        
        success = False
        try:
            # 创建模型
            success = self.api.create_model(model_name, modelfile_content)
        finally:
            # 无论如何都关闭进度提示
            progress_msg.close()
            # 再次处理事件，确保对话框被关闭
            QApplication.processEvents()
        
        if success:
            self.statusBar.showMessage(f"模型 {model_name} 创建成功")
            QMessageBox.information(self, "创建成功", f"模型 {model_name} 已成功创建")
            self.refresh_models()
            
            # 恢复保存按钮的原始功能
            self.details_widget.modelfile_editor.save_button.clicked.disconnect()
            self.details_widget.modelfile_editor.save_button.clicked.connect(self.save_modelfile)
            
            # 选择新创建的模型
            for i in range(self.model_list.count()):
                if self.model_list.item(i).text() == model_name:
                    self.model_list.setCurrentRow(i)
                    self.show_model_details(self.model_list.item(i))
                    break
        else:
            self.statusBar.showMessage(f"模型 {model_name} 创建失败")
            QMessageBox.warning(self, "创建失败", f"无法创建模型 {model_name}")
    
    def pull_model(self):
        """下载模型"""
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
        
        reply = QMessageBox.question(
            self,
            "确认重构",
            f"确定要使用新的Modelfile重构模型 {model_name} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.statusBar.showMessage(f"正在重构模型 {model_name}...")
            success = self.api.create_model(model_name, modelfile_content)
            
            if success:
                self.statusBar.showMessage(f"模型 {model_name} 重构成功")
                QMessageBox.information(self, "重构成功", f"模型 {model_name} 已成功重构")
                
                # 刷新模型信息
                model_info = self.api.get_model_info(model_name)
                if model_info:
                    self.details_widget.display_model_info(model_info)
            else:
                self.statusBar.showMessage(f"模型 {model_name} 重构失败")
                QMessageBox.warning(self, "重构失败", f"无法重构模型 {model_name}")
    
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
        self.details_widget.modelfile_editor.save_button.clicked.disconnect()
        self.details_widget.modelfile_editor.save_button.clicked.connect(
            lambda: self._ask_model_name_and_create(base_model_name)
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用Fusion风格提高跨平台一致性
    window = OllamaManagerGUI()
    window.show()
    sys.exit(app.exec_()) 