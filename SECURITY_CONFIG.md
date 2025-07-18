# 🔒 安全配置指南

## ⚠️ 重要安全提醒

**请勿在代码中硬编码API密钥或其他敏感信息！**

本项目已经移除了所有硬编码的敏感信息，请按照以下步骤安全配置您的环境。

## 🔧 配置步骤

### 1️⃣ 创建配置文件

复制模板文件并填入您的配置：

```bash
# 复制配置模板
cp markitdown_gui_config.template.json markitdown_gui_config.json
```

### 2️⃣ 编辑配置文件

编辑 `markitdown_gui_config.json`，填入您的真实配置：

```json
{
  "enable_plugins": false,
  "docintel_endpoint": "",
  "azure_openai_endpoint": "https://your-actual-resource.openai.azure.com/",
  "azure_openai_api_key": "your-actual-api-key",
  "azure_openai_deployment": "your-actual-deployment-name",
  "azure_openai_api_version": "2024-08-01-preview",
  "llm_model": "gpt-4o",
  "use_chinese_prompt": true,
  "custom_prompt": "请用中文详细描述这张图片的内容...",
  "smart_pdf_processing": true,
  "auto_save_results": false,
  "preview_mode": true
}
```

### 3️⃣ 环境变量方式（推荐）

您也可以使用环境变量来配置敏感信息：

#### Windows (PowerShell)
```powershell
$env:AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY="your-api-key"
$env:AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
```

#### Linux/Mac (Bash)
```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
```

#### 创建 .env 文件
```bash
# 创建 .env 文件（已在.gitignore中排除）
echo "AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/" > .env
echo "AZURE_OPENAI_API_KEY=your-api-key" >> .env
echo "AZURE_OPENAI_DEPLOYMENT=your-deployment-name" >> .env
```

## 🔑 获取Azure OpenAI配置

### 1. 创建Azure OpenAI资源

1. 访问 [Azure Portal](https://portal.azure.com)
2. 创建新的 "Azure OpenAI" 资源
3. 选择合适的区域和定价层

### 2. 获取配置信息

在Azure Portal中找到您的OpenAI资源：

- **Endpoint**: 在"Keys and Endpoint"页面找到
- **API Key**: 在"Keys and Endpoint"页面找到Key1或Key2
- **Deployment Name**: 在"Model deployments"页面创建或查看

### 3. 部署模型

1. 在Azure OpenAI Studio中部署GPT-4o模型
2. 记录部署名称（Deployment Name）

## 🛡️ 安全最佳实践

### ✅ 推荐做法

1. **使用环境变量**：将敏感信息存储在环境变量中
2. **配置文件权限**：确保配置文件只有您可以读取
3. **定期轮换密钥**：定期更新API密钥
4. **监控使用情况**：在Azure Portal中监控API使用情况

### ❌ 避免做法

1. **硬编码密钥**：不要在代码中直接写入API密钥
2. **提交敏感信息**：不要将包含密钥的文件提交到Git
3. **共享配置文件**：不要与他人共享包含真实密钥的配置文件
4. **使用弱密钥**：不要使用简单或可预测的密钥

## 🔍 验证配置

运行以下命令验证配置是否正确：

```bash
# 测试基本功能
python markitdown_gui.py

# 或者运行测试脚本
python test_local_markitdown.py
```

## 🚨 如果密钥泄露

如果您的API密钥意外泄露：

1. **立即撤销密钥**：在Azure Portal中撤销泄露的密钥
2. **生成新密钥**：创建新的API密钥
3. **更新配置**：使用新密钥更新您的配置
4. **检查使用情况**：查看是否有异常的API调用

## 📞 获取帮助

如果您在配置过程中遇到问题：

1. 查看 [Azure OpenAI文档](https://docs.microsoft.com/azure/cognitive-services/openai/)
2. 检查 [Azure OpenAI定价](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)
3. 在项目Issues中提问（请勿包含敏感信息）

---

🔒 **记住：安全是第一位的！永远不要在公开代码中包含真实的API密钥。**
