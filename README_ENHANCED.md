# MarkItDown 智能PDF处理增强版

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MarkItDown](https://img.shields.io/badge/Based%20on-MarkItDown-orange.svg)](https://github.com/microsoft/markitdown)

> 🚀 基于Microsoft MarkItDown的智能PDF处理增强版，专注于PDF图片的智能检测和AI分析，实现成本优化和处理效率的双重提升。

## ✨ 核心特性

### 🧠 智能PDF处理
- **🔍 自动检测**: 智能识别PDF是否包含图片
- **💰 成本优化**: 只对有图片的PDF调用AI，节省高达90%的API成本
- **🎯 精准分析**: 使用Azure OpenAI对图片进行详细中文描述
- **⚡ 性能提升**: 无图片PDF处理速度极快

### 🎨 现代化GUI
- **💻 用户友好**: 直观的图形界面，支持拖拽操作
- **📊 智能反馈**: 实时显示处理状态和成本信息
- **👁️ 预览功能**: 快速预览转换效果
- **🔧 配置管理**: 完整的AI模型配置界面

### 🔄 完全兼容
- **✅ 向后兼容**: 支持原版MarkItDown的所有功能
- **📦 模块化**: 可选依赖，按需安装
- **🔌 插件支持**: 兼容第三方插件生态

## 🚀 快速开始

### 📦 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/markitdown-enhanced.git
cd markitdown-enhanced

# 安装依赖
pip install -e packages/markitdown[all]

# 安装GUI依赖
pip install customtkinter openai
```

### 🔒 安全配置

**重要：请先配置您的Azure OpenAI密钥！**

```bash
# 1. 复制配置模板
cp markitdown_gui_config.template.json markitdown_gui_config.json

# 2. 编辑配置文件，填入您的真实Azure OpenAI配置
# 详细配置说明请参考 SECURITY_CONFIG.md
```

### 🎯 基础使用

#### 命令行
```bash
# 基础转换
python -m markitdown document.pdf > output.md

# 使用GUI
python markitdown_gui.py
```

#### Python API
```python
from markitdown import MarkItDown
from openai import AzureOpenAI

# 基础转换（智能检测）
md = MarkItDown()
result = md.convert("document.pdf")

# 完整AI功能
client = AzureOpenAI(
    azure_endpoint="your-endpoint",
    api_key="your-key",
    api_version="2024-08-01-preview"
)

result = md.convert(
    "document.pdf",
    llm_client=client,
    llm_model="gpt-4o-2"
)
```

## 🔧 配置说明

### Azure OpenAI配置

⚠️ **安全提醒：请勿在代码中硬编码API密钥！**

```json
{
    "azure_openai_endpoint": "https://your-resource.openai.azure.com/",
    "azure_openai_api_key": "your-api-key",
    "azure_openai_deployment": "gpt-4o-2",
    "azure_openai_api_version": "2024-08-01-preview",
    "use_chinese_prompt": true,
    "custom_prompt": "请用中文详细描述这张图片的内容..."
}
```

📖 **详细配置指南**: 请参考 [SECURITY_CONFIG.md](SECURITY_CONFIG.md)

### 智能处理选项
```python
{
    "smart_pdf_processing": true,    # 启用智能PDF处理
    "enable_plugins": false,         # 启用插件
    "auto_save_results": false       # 自动保存结果
}
```

## 📊 性能对比

| 场景 | 传统方式 | 智能方式 | 节省效果 |
|------|----------|----------|----------|
| 无图片PDF (100个) | 100次API调用 | 0次API调用 | **100%** |
| 有图片PDF (10个) | 10次API调用 | 10次API调用 | 0% |
| 混合场景 (90无+10有) | 100次API调用 | 10次API调用 | **90%** |

## 🛠️ 开发指南

### 本地开发
```bash
# 以开发模式安装
./install_local_markitdown.sh  # Linux/Mac
# 或
install_local_markitdown.bat   # Windows

# 运行测试
python test_local_markitdown.py
```

### 项目结构
```
markitdown-enhanced/
├── packages/markitdown/           # 核心MarkItDown包
│   ├── src/markitdown/
│   │   └── converters/
│   │       ├── _pdf_converter.py  # 增强的PDF转换器
│   │       └── _enhanced_pdf_converter.py
│   └── pyproject.toml             # 依赖配置
├── markitdown_gui.py              # GUI应用
├── install_local_markitdown.*     # 安装脚本
└── README_ENHANCED.md             # 本文档
```

## 🎯 使用场景

### 📄 文档处理
- **学术论文**: 提取文字和图表描述
- **技术文档**: 转换流程图和架构图
- **报告分析**: 处理数据图表和图片

### 💼 商业应用
- **合同处理**: 智能识别关键信息
- **财务报表**: 提取图表数据
- **产品手册**: 转换产品图片描述

### 🔬 研究用途
- **数据分析**: 批量处理PDF文档
- **内容挖掘**: 提取图文信息
- **知识图谱**: 构建结构化数据

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 🐛 报告问题
- 使用GitHub Issues报告bug
- 提供详细的复现步骤
- 包含系统环境信息

### 💡 功能建议
- 在Issues中提出新功能建议
- 描述使用场景和预期效果
- 讨论技术实现方案

### 🔧 代码贡献
1. Fork本仓库
2. 创建功能分支
3. 提交代码更改
4. 创建Pull Request

## 📝 许可证

本项目基于MIT许可证开源，与原始MarkItDown项目保持一致。

## 🙏 致谢

- **Microsoft AutoGen团队**: 提供优秀的MarkItDown基础框架
- **OpenAI**: 提供强大的AI图片分析能力
- **开源社区**: 提供各种优秀的Python库支持

## 📞 联系方式

- **GitHub Issues**: [提交问题和建议](https://github.com/your-username/markitdown-enhanced/issues)
- **讨论区**: [参与社区讨论](https://github.com/your-username/markitdown-enhanced/discussions)

---

⭐ 如果这个项目对您有帮助，请给我们一个Star！
