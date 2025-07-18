#!/usr/bin/env python3
"""
MarkItDown GUI - A modern graphical interface for the MarkItDown library
Converts various file formats to Markdown with a user-friendly interface
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import sys
import threading
from pathlib import Path
import json
import warnings

# 抑制pydub的ffmpeg警告
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pydub")

# Add local markitdown package to path
import sys
from pathlib import Path

# 添加本地修改的markitdown包路径
local_markitdown_path = Path(__file__).parent / "packages" / "markitdown" / "src"
if local_markitdown_path.exists():
    sys.path.insert(0, str(local_markitdown_path))
    print(f"✅ 使用本地MarkItDown包: {local_markitdown_path}")
else:
    print("⚠️ 本地MarkItDown包不存在，将使用系统安装的版本")

# Try to import MarkItDown
try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True

    # 验证是否使用了本地版本
    import markitdown
    markitdown_path = Path(markitdown.__file__).parent
    if "packages" in str(markitdown_path):
        print(f"✅ 成功加载本地修改版本: {markitdown_path}")
    else:
        print(f"⚠️ 使用系统版本: {markitdown_path}")

except ImportError:
    MARKITDOWN_AVAILABLE = False
    print("❌ MarkItDown包未找到")

# Try to import OpenAI for image descriptions
try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None  # 定义占位符避免未定义错误
    AzureOpenAI = None  # 定义一个占位符，避免未定义错误


class ChinesePromptWrapper:
    """Azure OpenAI客户端包装器，用于添加中文提示词"""

    def __init__(self, original_client, custom_prompt):
        self.original_client = original_client
        self.custom_prompt = custom_prompt

        # 将原始客户端的所有属性和方法代理到包装器
        for attr_name in dir(original_client):
            if not attr_name.startswith('_') and attr_name != 'chat':
                setattr(self, attr_name, getattr(original_client, attr_name))

    @property
    def chat(self):
        """返回包装后的chat对象"""
        return ChineseChatWrapper(self.original_client.chat, self.custom_prompt)


class ChineseChatWrapper:
    """Chat对象包装器，用于修改消息内容"""

    def __init__(self, original_chat, custom_prompt):
        self.original_chat = original_chat
        self.custom_prompt = custom_prompt

        # 代理其他属性
        for attr_name in dir(original_chat):
            if not attr_name.startswith('_') and attr_name != 'completions':
                setattr(self, attr_name, getattr(original_chat, attr_name))

    @property
    def completions(self):
        """返回包装后的completions对象"""
        return ChineseCompletionsWrapper(self.original_chat.completions, self.custom_prompt)


class ChineseCompletionsWrapper:
    """Completions对象包装器，用于修改请求"""

    def __init__(self, original_completions, custom_prompt):
        self.original_completions = original_completions
        self.custom_prompt = custom_prompt

        # 代理其他属性
        for attr_name in dir(original_completions):
            if not attr_name.startswith('_') and attr_name != 'create':
                setattr(self, attr_name, getattr(original_completions, attr_name))

    def create(self, **kwargs):
        """拦截create调用，添加中文提示词"""
        # 获取消息列表
        messages = kwargs.get('messages', [])

        # 如果有消息且包含图片相关内容，添加中文提示词
        if messages:
            # 查找用户消息
            for message in messages:
                if message.get('role') == 'user':
                    content = message.get('content', '')
                    # 如果是字符串内容，直接添加中文提示词
                    if isinstance(content, str):
                        message['content'] = f"{self.custom_prompt}\n\n{content}"
                    # 如果是列表内容（包含图片），在文本部分添加中文提示词
                    elif isinstance(content, list):
                        text_found = False
                        for item in content:
                            if item.get('type') == 'text':
                                original_text = item.get('text', '')
                                item['text'] = f"{self.custom_prompt}\n\n{original_text}"
                                text_found = True
                                break

                        # 如果没有找到文本项，添加一个新的文本项
                        if not text_found:
                            content.insert(0, {
                                "type": "text",
                                "text": self.custom_prompt
                            })
                    break

        # 调用原始的create方法
        return self.original_completions.create(**kwargs)


class MarkItDownGUI:
    def __init__(self):
        # Set appearance
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        # Create main window
        self.root = ctk.CTk()
        self.root.title("MarkItDown GUI - 文档转换工具")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Initialize variables
        self.selected_file = tk.StringVar()
        self.output_text = tk.StringVar()
        self.conversion_status = tk.StringVar(value="准备就绪")
        
        # Configuration - 默认配置（不包含敏感信息）
        self.config = {
            "enable_plugins": False,
            "docintel_endpoint": "",
            "azure_openai_endpoint": "",  # 用户需要自行配置
            "azure_openai_api_key": "",   # 用户需要自行配置
            "azure_openai_deployment": "",  # 用户需要自行配置
            "azure_openai_api_version": "2024-08-01-preview",
            "llm_model": "gpt-4o",
            "use_chinese_prompt": True,
            "custom_prompt": "请用中文详细描述这张图片的内容。包括：1)图片中的所有文字内容；2)图表、表格、数据信息；3)图片的整体布局和设计；4)任何重要的视觉元素。请确保描述准确、详细且易于理解。",
            "smart_pdf_processing": True,  # 启用智能PDF处理
            "auto_save_results": False,    # 自动保存结果
            "preview_mode": True           # 预览模式
        }
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        """设置用户界面"""
        # Create main scrollable frame
        self.main_scrollable_frame = ctk.CTkScrollableFrame(self.root)
        self.main_scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ctk.CTkLabel(
            self.main_scrollable_frame,
            text="MarkItDown 文档转换工具",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(20, 30))

        # Check if MarkItDown is available
        if not MARKITDOWN_AVAILABLE:
            warning_frame = ctk.CTkFrame(self.main_scrollable_frame, fg_color="red")
            warning_label = ctk.CTkLabel(
                warning_frame,
                text="⚠️ MarkItDown 库未安装。请运行: pip install markitdown",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="white"
            )
            warning_label.pack(pady=10)
            warning_frame.pack(fill="x", padx=20, pady=(0, 20))

        # File selection section
        self.setup_file_selection(self.main_scrollable_frame)

        # Control buttons (moved up, before output)
        self.setup_controls(self.main_scrollable_frame)

        # Output section (now with proper scrolling)
        self.setup_output(self.main_scrollable_frame)

        # Status bar
        self.setup_status_bar(self.main_scrollable_frame)
    
    def setup_file_selection(self, parent):
        """设置文件选择区域"""
        file_frame = ctk.CTkFrame(parent)
        file_frame.pack(fill="x", padx=20, pady=(0, 20))

        # File selection label
        file_label = ctk.CTkLabel(file_frame, text="选择要转换的文件:", font=ctk.CTkFont(size=16))
        file_label.pack(anchor="w", padx=20, pady=(20, 10))

        # File path display and browse button
        file_input_frame = ctk.CTkFrame(file_frame)
        file_input_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.file_entry = ctk.CTkEntry(
            file_input_frame,
            textvariable=self.selected_file,
            placeholder_text="请选择文件...",
            font=ctk.CTkFont(size=12)
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)

        browse_button = ctk.CTkButton(
            file_input_frame,
            text="浏览",
            command=self.browse_file,
            width=80
        )
        browse_button.pack(side="right", padx=(5, 10), pady=10)

        # Options frame for quick settings
        options_frame = ctk.CTkFrame(file_frame)
        options_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Enable plugins checkbox
        self.plugins_var = tk.BooleanVar(value=self.config["enable_plugins"])
        plugins_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="启用插件 (扩展转换功能)",
            variable=self.plugins_var,
            command=self.save_config
        )
        plugins_checkbox.pack(anchor="w", padx=10, pady=10)

        # Smart PDF processing checkbox
        self.smart_pdf_var = tk.BooleanVar(value=self.config["smart_pdf_processing"])
        smart_pdf_checkbox = ctk.CTkCheckBox(
            options_frame,
            text="智能PDF处理 (自动检测图片并AI分析)",
            variable=self.smart_pdf_var,
            command=self.save_config
        )
        smart_pdf_checkbox.pack(anchor="w", padx=10, pady=(0, 10))

        # Supported formats info
        formats_label = ctk.CTkLabel(
            file_frame,
            text="支持的格式: PDF, DOCX, PPTX, XLSX, 图片 (JPG, PNG), HTML, TXT 等",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        formats_label.pack(anchor="w", padx=20, pady=(0, 10))

        # Smart processing info
        smart_info_label = ctk.CTkLabel(
            file_frame,
            text="💡 智能PDF处理：自动检测PDF中的图片，只对包含图片的PDF调用AI分析，节省成本",
            font=ctk.CTkFont(size=10),
            text_color="blue"
        )
        smart_info_label.pack(anchor="w", padx=20, pady=(0, 20))
    

    
    def setup_controls(self, parent):
        """设置控制按钮"""
        controls_frame = ctk.CTkFrame(parent)
        controls_frame.pack(fill="x", padx=20, pady=(0, 20))

        buttons_frame = ctk.CTkFrame(controls_frame)
        buttons_frame.pack(pady=20)

        # Convert button
        self.convert_button = ctk.CTkButton(
            buttons_frame,
            text="转换为 Markdown",
            command=self.convert_file,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            width=150
        )
        self.convert_button.pack(side="left", padx=10)

        # Clear button
        clear_button = ctk.CTkButton(
            buttons_frame,
            text="清空",
            command=self.clear_output,
            height=40,
            width=100
        )
        clear_button.pack(side="left", padx=10)

        # Save button
        self.save_button = ctk.CTkButton(
            buttons_frame,
            text="保存结果",
            command=self.save_output,
            height=40,
            width=100,
            state="disabled"
        )
        self.save_button.pack(side="left", padx=10)

        # Model configuration button
        config_button = ctk.CTkButton(
            buttons_frame,
            text="🤖 模型配置",
            command=self.open_config_window,
            height=40,
            width=120
        )
        config_button.pack(side="left", padx=10)

        # Preview button
        self.preview_button = ctk.CTkButton(
            buttons_frame,
            text="👁️ 预览",
            command=self.preview_file,
            height=40,
            width=100
        )
        self.preview_button.pack(side="left", padx=10)
    
    def setup_output(self, parent):
        """设置输出区域"""
        output_frame = ctk.CTkFrame(parent)
        output_frame.pack(fill="x", padx=20, pady=(0, 20))

        output_label = ctk.CTkLabel(output_frame, text="转换结果:", font=ctk.CTkFont(size=16))
        output_label.pack(anchor="w", padx=20, pady=(20, 10))

        # Text output area with fixed height
        self.output_textbox = ctk.CTkTextbox(
            output_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
            height=300  # 固定高度，确保可见
        )
        self.output_textbox.pack(fill="x", padx=20, pady=(0, 20))
    
    def setup_status_bar(self, parent):
        """设置状态栏"""
        status_frame = ctk.CTkFrame(parent)
        status_frame.pack(fill="x", padx=20, pady=(0, 20))

        # Main status
        self.status_label = ctk.CTkLabel(
            status_frame,
            textvariable=self.conversion_status,
            font=ctk.CTkFont(size=11)
        )
        self.status_label.pack(pady=(10, 5))

        # Processing details (for smart PDF processing)
        self.detail_status = tk.StringVar(value="")
        self.detail_label = ctk.CTkLabel(
            status_frame,
            textvariable=self.detail_status,
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.detail_label.pack(pady=(0, 10))
    
    def browse_file(self):
        """浏览并选择文件"""
        file_types = [
            ("所有支持的文件", "*.pdf;*.docx;*.pptx;*.xlsx;*.jpg;*.jpeg;*.png;*.html;*.htm;*.txt"),
            ("PDF 文件", "*.pdf"),
            ("Word 文档", "*.docx"),
            ("PowerPoint 演示文稿", "*.pptx"),
            ("Excel 表格", "*.xlsx"),
            ("图片文件", "*.jpg;*.jpeg;*.png"),
            ("HTML 文件", "*.html;*.htm"),
            ("文本文件", "*.txt"),
            ("所有文件", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="选择要转换的文件",
            filetypes=file_types
        )
        
        if filename:
            self.selected_file.set(filename)
            file_name = os.path.basename(filename)
            file_size = os.path.getsize(filename)
            size_mb = file_size / (1024 * 1024)

            self.conversion_status.set(f"已选择文件: {file_name}")
            self.detail_status.set(f"文件大小: {size_mb:.2f} MB | 类型: {os.path.splitext(filename)[1].upper()}")

            # 如果是PDF文件，显示智能处理提示
            if filename.lower().endswith('.pdf') and self.smart_pdf_var.get():
                self.detail_status.set(f"文件大小: {size_mb:.2f} MB | PDF文件 - 将启用智能图片检测")

    def preview_file(self):
        """预览文件内容（快速转换，不使用AI）"""
        if not MARKITDOWN_AVAILABLE:
            messagebox.showerror("错误", "MarkItDown 库未安装。请运行: pip install markitdown")
            return

        file_path = self.selected_file.get().strip()
        if not file_path:
            messagebox.showwarning("警告", "请先选择要预览的文件")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("错误", "选择的文件不存在")
            return

        # 禁用预览按钮
        self.preview_button.configure(state="disabled", text="预览中...")
        self.conversion_status.set("正在生成预览...")
        self.detail_status.set("快速转换中，不使用AI分析...")

        # 在后台线程中执行预览
        thread = threading.Thread(target=self._preview_file_thread, args=(file_path,))
        thread.daemon = True
        thread.start()

    def _preview_file_thread(self, file_path):
        """在后台线程中执行文件预览"""
        try:
            # 创建基础MarkItDown实例（不使用AI）
            md = MarkItDown(enable_plugins=self.plugins_var.get())

            # 快速转换
            result = md.convert(file_path)

            # 截取前1000字符作为预览
            preview_content = result.text_content[:1000]
            if len(result.text_content) > 1000:
                preview_content += "\n\n... (预览模式，显示前1000字符)"

            # 更新UI
            self.root.after(0, lambda: self._preview_complete(preview_content, file_path))

        except Exception as e:
            error_msg = f"预览失败: {str(e)}"
            self.root.after(0, lambda: self._preview_error(error_msg))

    def _preview_complete(self, preview_content, file_path):
        """预览完成后的UI更新"""
        # 启用预览按钮
        self.preview_button.configure(state="normal", text="👁️ 预览")

        # 显示预览内容
        self.output_textbox.delete("1.0", tk.END)
        self.output_textbox.insert("1.0", preview_content)

        # 更新状态
        file_name = os.path.basename(file_path)
        self.conversion_status.set(f"预览完成: {file_name}")
        self.detail_status.set("预览模式 - 如需完整转换和AI分析，请点击'转换为 Markdown'")

    def _preview_error(self, error_msg):
        """预览错误后的UI更新"""
        # 启用预览按钮
        self.preview_button.configure(state="normal", text="👁️ 预览")

        # 更新状态
        self.conversion_status.set("预览失败")
        self.detail_status.set("")

        # 显示错误消息
        messagebox.showerror("预览错误", error_msg)

    def open_config_window(self):
        """打开模型配置窗口"""
        config_window = ctk.CTkToplevel(self.root)
        config_window.title("模型配置")
        config_window.geometry("600x500")
        config_window.transient(self.root)
        config_window.grab_set()  # 模态窗口

        # 创建滚动框架
        scrollable_frame = ctk.CTkScrollableFrame(config_window)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 标题
        title_label = ctk.CTkLabel(
            scrollable_frame,
            text="🤖 模型配置选项",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=(0, 20))

        # 插件配置
        plugin_frame = ctk.CTkFrame(scrollable_frame)
        plugin_frame.pack(fill="x", pady=(0, 20))

        plugin_title = ctk.CTkLabel(
            plugin_frame,
            text="插件设置",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        plugin_title.pack(anchor="w", padx=20, pady=(20, 10))

        plugin_info = ctk.CTkLabel(
            plugin_frame,
            text="插件可以扩展文档转换能力，支持更多文件格式和转换选项",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        plugin_info.pack(anchor="w", padx=20, pady=(0, 10))

        # Azure OpenAI 配置
        if OPENAI_AVAILABLE:
            openai_frame = ctk.CTkFrame(scrollable_frame)
            openai_frame.pack(fill="x", pady=(0, 20))

            openai_title = ctk.CTkLabel(
                openai_frame,
                text="Azure OpenAI 配置 (图片描述功能)",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            openai_title.pack(anchor="w", padx=20, pady=(20, 10))

            openai_info = ctk.CTkLabel(
                openai_frame,
                text="配置后可为图片文件生成智能描述，提升转换质量",
                font=ctk.CTkFont(size=11),
                text_color="gray"
            )
            openai_info.pack(anchor="w", padx=20, pady=(0, 15))

            # API Key
            api_key_label = ctk.CTkLabel(openai_frame, text="API Key:")
            api_key_label.pack(anchor="w", padx=20, pady=(5, 2))

            self.config_api_key_entry = ctk.CTkEntry(
                openai_frame,
                placeholder_text="输入 Azure OpenAI API Key",
                show="*",
                width=500
            )
            self.config_api_key_entry.pack(anchor="w", padx=20, pady=(0, 10))
            if self.config["azure_openai_api_key"]:
                self.config_api_key_entry.insert(0, self.config["azure_openai_api_key"])

            # Endpoint
            endpoint_label = ctk.CTkLabel(openai_frame, text="Endpoint:")
            endpoint_label.pack(anchor="w", padx=20, pady=(5, 2))

            self.config_endpoint_entry = ctk.CTkEntry(
                openai_frame,
                placeholder_text="Azure OpenAI Endpoint (如: https://your-resource.openai.azure.com/)",
                width=500
            )
            self.config_endpoint_entry.pack(anchor="w", padx=20, pady=(0, 10))
            if self.config["azure_openai_endpoint"]:
                self.config_endpoint_entry.insert(0, self.config["azure_openai_endpoint"])

            # Deployment Name
            deployment_label = ctk.CTkLabel(openai_frame, text="Deployment Name:")
            deployment_label.pack(anchor="w", padx=20, pady=(5, 2))

            self.config_deployment_entry = ctk.CTkEntry(
                openai_frame,
                placeholder_text="部署名称 (如: gpt-4o-2)",
                width=500
            )
            self.config_deployment_entry.pack(anchor="w", padx=20, pady=(0, 15))
            if self.config["azure_openai_deployment"]:
                self.config_deployment_entry.insert(0, self.config["azure_openai_deployment"])

            # 中文提示词配置
            prompt_frame = ctk.CTkFrame(openai_frame)
            prompt_frame.pack(fill="x", padx=20, pady=(0, 20))

            # 启用中文提示词选项
            self.chinese_prompt_var = tk.BooleanVar(value=self.config.get("use_chinese_prompt", True))
            chinese_prompt_checkbox = ctk.CTkCheckBox(
                prompt_frame,
                text="启用中文提示词 (图片描述使用中文)",
                variable=self.chinese_prompt_var
            )
            chinese_prompt_checkbox.pack(anchor="w", padx=10, pady=(10, 5))

            # 自定义提示词
            custom_prompt_label = ctk.CTkLabel(prompt_frame, text="自定义提示词:")
            custom_prompt_label.pack(anchor="w", padx=10, pady=(10, 2))

            self.config_custom_prompt_entry = ctk.CTkTextbox(
                prompt_frame,
                height=80,
                width=480
            )
            self.config_custom_prompt_entry.pack(anchor="w", padx=10, pady=(0, 10))

            # 设置默认提示词
            default_prompt = self.config.get("custom_prompt", "请用中文详细描述这张图片的内容，包括图片中的文字、图表、数据等信息。")
            self.config_custom_prompt_entry.insert("1.0", default_prompt)
        else:
            # OpenAI 不可用提示
            no_openai_frame = ctk.CTkFrame(scrollable_frame, fg_color="orange")
            no_openai_label = ctk.CTkLabel(
                no_openai_frame,
                text="⚠️ OpenAI 库未安装，无法使用图片描述功能\n请运行: pip install openai",
                font=ctk.CTkFont(size=12),
                text_color="white"
            )
            no_openai_label.pack(pady=15)
            no_openai_frame.pack(fill="x", pady=(0, 20))

        # 按钮区域
        button_frame = ctk.CTkFrame(config_window)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))

        # 保存按钮
        save_button = ctk.CTkButton(
            button_frame,
            text="保存配置",
            command=lambda: self.save_config_from_window(config_window),
            width=100
        )
        save_button.pack(side="right", padx=(10, 20), pady=15)

        # 取消按钮
        cancel_button = ctk.CTkButton(
            button_frame,
            text="取消",
            command=config_window.destroy,
            width=100
        )
        cancel_button.pack(side="right", padx=(10, 0), pady=15)

    def save_config_from_window(self, window):
        """从配置窗口保存配置"""
        try:
            # 保存 Azure OpenAI 配置
            if OPENAI_AVAILABLE and hasattr(self, 'config_api_key_entry'):
                self.config["azure_openai_api_key"] = self.config_api_key_entry.get().strip()
                self.config["azure_openai_endpoint"] = self.config_endpoint_entry.get().strip()
                self.config["azure_openai_deployment"] = self.config_deployment_entry.get().strip()

                # 保存中文提示词配置
                if hasattr(self, 'chinese_prompt_var'):
                    self.config["use_chinese_prompt"] = self.chinese_prompt_var.get()

                if hasattr(self, 'config_custom_prompt_entry'):
                    self.config["custom_prompt"] = self.config_custom_prompt_entry.get("1.0", tk.END).strip()

            # 保存配置到文件
            self.save_config()

            # 显示成功消息
            messagebox.showinfo("成功", "配置已保存")

            # 关闭窗口
            window.destroy()

        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def convert_file(self):
        """转换文件为 Markdown"""
        if not MARKITDOWN_AVAILABLE:
            messagebox.showerror("错误", "MarkItDown 库未安装。请运行: pip install markitdown")
            return

        file_path = self.selected_file.get().strip()
        if not file_path:
            messagebox.showwarning("警告", "请先选择要转换的文件")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("错误", "选择的文件不存在")
            return

        # Disable convert button during conversion
        self.convert_button.configure(state="disabled", text="转换中...")
        self.conversion_status.set("正在转换文件...")

        # Run conversion in a separate thread to avoid blocking UI
        thread = threading.Thread(target=self._convert_file_thread, args=(file_path,))
        thread.daemon = True
        thread.start()

    def _convert_file_thread(self, file_path):
        """在后台线程中执行文件转换"""
        try:
            # 更新状态：开始分析文件
            self.root.after(0, lambda: self.conversion_status.set("正在分析文件类型..."))

            # Initialize MarkItDown with configuration
            md_kwargs = {
                "enable_plugins": self.plugins_var.get()
            }

            # 检查文件类型
            file_ext = os.path.splitext(file_path)[1].lower()
            is_pdf = file_ext == '.pdf'
            smart_pdf_enabled = self.smart_pdf_var.get()

            print(f"正在转换文件: {file_path}")
            print(f"文件类型: {file_ext}")
            print(f"启用插件: {self.plugins_var.get()}")
            print(f"智能PDF处理: {smart_pdf_enabled}")

            # 如果是PDF且启用智能处理，先检测图片
            has_images = False
            if is_pdf and smart_pdf_enabled:
                self.root.after(0, lambda: self.conversion_status.set("正在检测PDF中的图片..."))
                self.root.after(0, lambda: self.detail_status.set("智能检测中，这将决定是否需要AI分析..."))

                try:
                    # 使用我们改进的PDF转换器检测图片
                    from markitdown.converters._pdf_converter import PdfConverter
                    pdf_converter = PdfConverter()

                    with open(file_path, 'rb') as f:
                        has_images = pdf_converter._check_pdf_has_images(f)

                    if has_images:
                        print("✅ PDF中检测到图片，将使用AI分析")
                        self.root.after(0, lambda: self.detail_status.set("检测到图片，将启用AI分析（可能需要较长时间）"))
                    else:
                        print("📄 PDF中未检测到图片，跳过AI分析")
                        self.root.after(0, lambda: self.detail_status.set("未检测到图片，将快速处理（节省成本）"))

                except Exception as e:
                    print(f"⚠️ 图片检测失败: {e}")
                    has_images = True  # 检测失败时假设有图片，保险起见

            # Add Azure OpenAI client if configuration is provided and needed
            should_use_ai = False

            # 决定是否需要使用AI
            if is_pdf and smart_pdf_enabled:
                should_use_ai = has_images  # PDF只有在检测到图片时才使用AI
            elif not is_pdf:
                should_use_ai = True  # 非PDF文件（如图片）总是尝试使用AI

            if should_use_ai and OPENAI_AVAILABLE:
                api_key = self.config["azure_openai_api_key"]
                endpoint = self.config["azure_openai_endpoint"]
                deployment = self.config["azure_openai_deployment"]

                if api_key and endpoint and deployment:
                    try:
                        self.root.after(0, lambda: self.conversion_status.set("正在配置AI模型..."))
                        self.root.after(0, lambda: self.detail_status.set("连接Azure OpenAI服务..."))

                        # 创建原始客户端
                        original_client = AzureOpenAI(
                            api_key=api_key,
                            azure_endpoint=endpoint,
                            api_version=self.config["azure_openai_api_version"]
                        )

                        # 如果启用中文提示词，创建包装器客户端
                        if self.config.get("use_chinese_prompt", True):
                            custom_prompt = self.config.get("custom_prompt", "请用中文详细描述这张图片的内容，包括图片中的文字、图表、数据等信息。")
                            client = ChinesePromptWrapper(original_client, custom_prompt)
                            print(f"已启用中文提示词: {custom_prompt}")
                        else:
                            client = original_client
                            print("使用默认英文提示词")

                        md_kwargs["llm_client"] = client
                        md_kwargs["llm_model"] = deployment  # 使用部署名称作为模型名
                        print(f"Azure OpenAI 配置成功: {deployment}")

                        self.root.after(0, lambda: self.detail_status.set(f"AI模型已配置: {deployment}"))

                    except Exception as e:
                        print(f"Azure OpenAI 配置错误: {str(e)}")
                        self.root.after(0, lambda: self.conversion_status.set(f"Azure OpenAI 配置错误: {str(e)}"))
                        self.root.after(0, lambda: self.detail_status.set("AI配置失败，将进行基础转换"))
                else:
                    print("Azure OpenAI 配置不完整，跳过图片描述功能")
                    self.root.after(0, lambda: self.detail_status.set("AI配置不完整，将进行基础转换"))
            else:
                if is_pdf and smart_pdf_enabled and not has_images:
                    print("📄 PDF无图片，跳过AI分析（智能优化）")
                    self.root.after(0, lambda: self.detail_status.set("智能优化：PDF无图片，跳过AI分析"))
                else:
                    print("OpenAI 库不可用或未启用智能处理")
                    self.root.after(0, lambda: self.detail_status.set("基础转换模式"))

            # Add Document Intelligence endpoint if provided
            if self.config["docintel_endpoint"]:
                md_kwargs["docintel_endpoint"] = self.config["docintel_endpoint"]
                print(f"使用 Document Intelligence: {self.config['docintel_endpoint']}")

            # 更新状态：开始转换
            self.root.after(0, lambda: self.conversion_status.set("正在转换文档..."))

            # Create MarkItDown instance
            md = MarkItDown(**md_kwargs)
            print(f"MarkItDown 实例创建成功，配置: {md_kwargs}")

            # Convert file
            print("开始转换文件...")
            result = md.convert(file_path)
            print(f"转换完成，内容长度: {len(result.text_content)} 字符")

            # 分析转换结果
            has_image_content = "## Images in PDF" in result.text_content
            image_count = result.text_content.count("### Image")
            content_length = len(result.text_content)

            if has_image_content:
                print(f"✅ 检测到图片相关内容，共 {image_count} 张图片")
            else:
                print("⚠️ 未检测到图片相关内容")

            print(f"转换结果统计：内容长度 {content_length} 字符")

            # Update UI in main thread
            self.root.after(0, lambda: self._conversion_complete(result, file_path, has_image_content, image_count))

        except Exception as e:
            error_msg = f"转换失败: {str(e)}"
            print(f"转换错误: {error_msg}")
            self.root.after(0, lambda: self._conversion_error(error_msg))

    def _conversion_complete(self, result, file_path, has_image_content=False, image_count=0):
        """转换完成后的UI更新"""
        # Enable convert button
        self.convert_button.configure(state="normal", text="转换为 Markdown")

        # Display result
        self.output_textbox.delete("1.0", tk.END)
        self.output_textbox.insert("1.0", result.text_content)

        # Enable save button
        self.save_button.configure(state="normal")

        # Update status with detailed information
        file_name = os.path.basename(file_path)
        content_length = len(result.text_content)

        self.conversion_status.set(f"转换完成: {file_name}")

        # 详细状态信息
        if has_image_content:
            self.detail_status.set(f"✅ 内容长度: {content_length} 字符 | AI分析了 {image_count} 张图片")
            success_msg = f"文件 '{file_name}' 已成功转换为 Markdown\n\n📊 转换统计:\n• 内容长度: {content_length} 字符\n• AI分析图片: {image_count} 张"
        else:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.pdf' and self.smart_pdf_var.get():
                self.detail_status.set(f"✅ 内容长度: {content_length} 字符 | 智能处理：无图片，节省了AI成本")
                success_msg = f"文件 '{file_name}' 已成功转换为 Markdown\n\n📊 转换统计:\n• 内容长度: {content_length} 字符\n• 智能优化: 检测到无图片，节省了AI调用成本"
            else:
                self.detail_status.set(f"✅ 内容长度: {content_length} 字符 | 基础转换完成")
                success_msg = f"文件 '{file_name}' 已成功转换为 Markdown\n\n📊 转换统计:\n• 内容长度: {content_length} 字符"

        # Show success message
        messagebox.showinfo("转换成功", success_msg)

        # 自动保存（如果启用）
        if self.config.get("auto_save_results", False):
            self.auto_save_result(file_path, result.text_content)

    def auto_save_result(self, original_file_path, content):
        """自动保存转换结果"""
        try:
            # 生成自动保存文件名
            base_name = os.path.splitext(os.path.basename(original_file_path))[0]
            auto_save_path = f"{base_name}_converted.md"

            # 如果文件已存在，添加时间戳
            if os.path.exists(auto_save_path):
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                auto_save_path = f"{base_name}_converted_{timestamp}.md"

            with open(auto_save_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self.detail_status.set(f"✅ 已自动保存到: {auto_save_path}")

        except Exception as e:
            print(f"自动保存失败: {e}")

    def _conversion_error(self, error_msg):
        """转换错误后的UI更新"""
        # Enable convert button
        self.convert_button.configure(state="normal", text="转换为 Markdown")

        # Update status
        self.conversion_status.set("转换失败")
        self.detail_status.set("请检查文件格式或网络连接")

        # Show error message
        messagebox.showerror("转换错误", error_msg)

    def clear_output(self):
        """清空输出区域"""
        self.output_textbox.delete("1.0", tk.END)
        self.save_button.configure(state="disabled")
        self.conversion_status.set("输出已清空")

    def save_output(self):
        """保存转换结果"""
        content = self.output_textbox.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("警告", "没有内容可保存")
            return

        # Get original file name for default save name
        original_file = self.selected_file.get()
        if original_file:
            base_name = os.path.splitext(os.path.basename(original_file))[0]
            default_name = f"{base_name}.md"
        else:
            default_name = "converted.md"

        # Ask user where to save
        save_path = filedialog.asksaveasfilename(
            title="保存 Markdown 文件",
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[
                ("Markdown 文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )

        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", f"文件已保存到: {save_path}")
                self.conversion_status.set(f"已保存到: {os.path.basename(save_path)}")
            except Exception as e:
                messagebox.showerror("保存错误", f"保存文件时出错: {str(e)}")

    def load_config(self):
        """加载配置文件"""
        config_file = "markitdown_gui_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def save_config(self):
        """保存配置文件"""
        config_file = "markitdown_gui_config.json"
        try:
            # Update config with current values
            if hasattr(self, 'plugins_var'):
                self.config["enable_plugins"] = self.plugins_var.get()

            if hasattr(self, 'smart_pdf_var'):
                self.config["smart_pdf_processing"] = self.smart_pdf_var.get()

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def run(self):
        """运行GUI应用"""
        self.root.mainloop()


def main():
    """主函数"""
    # Check if running from correct directory
    if not os.path.exists("markitdown_gui.py"):
        print("请在包含 markitdown_gui.py 的目录中运行此程序")
        return

    # Create and run GUI
    app = MarkItDownGUI()
    app.run()


if __name__ == "__main__":
    main()
