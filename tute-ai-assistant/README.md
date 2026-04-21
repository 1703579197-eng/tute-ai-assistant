# 🎓 天津职业技术师范大学校园AI助手

基于 Flask 和 AI 大模型的校园智能问答系统，专门为学生提供学生手册相关的咨询服务。

## 📁 项目结构

```
tute-ai-assistant/
├── backend/                    # 后端服务
│   ├── app.py                 # Flask 主程序
│   ├── config.py              # 配置文件
│   ├── requirements.txt       # Python 依赖
│   ├── .env                   # 环境变量（API密钥）
│   ├── .env.example           # 环境变量模板
│   └── knowledge_base/        # 知识库模块
│       └── __init__.py
│
├── frontend/                   # 前端界面
│   ├── index.html             # 主页面
│   ├── css/
│   │   └── style.css          # 样式文件
│   └── js/
│       ├── chat.js            # 聊天逻辑
│       └── avatar.png         # AI 头像
│
└── README.md                   # 项目说明
```

## 🚀 快速开始

### 1. 安装依赖

确保你已安装 Python 3.8+，然后安装依赖：

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置 API 密钥

**⚠️ 重要：不要在代码中直接写入 API 密钥！**

复制环境变量模板并填入你的密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 密钥（三选一即可）：

```env
# Google Gemini（推荐，免费额度充足）
GEMINI_API_KEY=your_actual_api_key_here

# 或 OpenAI
OPENAI_API_KEY=your_actual_api_key_here

# 或 DeepSeek
DEEPSEEK_API_KEY=your_actual_api_key_here
```

**获取 API 密钥：**
- Gemini: https://aistudio.google.com/app/apikey
- OpenAI: https://platform.openai.com/api-keys
- DeepSeek: https://platform.deepseek.com/

### 3. 启动服务

```bash
python app.py
```

服务启动后，打开浏览器访问：
```
http://localhost:5000
```

## 🎨 界面预览

- **背景**：优雅的紫色渐变（#701F9D）
- **聊天框**：居中白色卡片，柔和阴影
- **AI 名称**：天职小咕
- **用户气泡**：浅紫色
- **AI 气泡**：浅灰色

## 🔧 功能特性

### 后端功能
- ✅ 安全读取学生手册知识库
- ✅ 支持多个 AI 提供商（Gemini/OpenAI/DeepSeek）
- ✅ API 密钥通过环境变量管理，绝不暴露
- ✅ 自动加载知识库作为系统提示词
- ✅ 健康检查接口

### 前端功能
- ✅ 美观的紫色主题界面
- ✅ AI 头像显示
- ✅ 区分用户和 AI 消息气泡
- ✅ 快速问题按钮
- ✅ 打字机效果加载动画
- ✅ 响应式设计（支持移动端）
- ✅ Enter 发送，Shift+Enter 换行

## 📚 知识库内容

AI 助手已学习以下学生手册内容：

- 学生权利和义务
- 学籍管理（入学、注册、转学、转专业）
- 课程考核与成绩记载
- 休学、复学规定
- 学业预警制度
- 退学规定
- 主辅修、双学位
- 毕业、结业、肄业
- 学士学位授予
- 考勤、纪律及处分
- 请假规定

## 🔌 API 接口

### POST /api/chat
发送消息获取 AI 回复

**请求体：**
```json
{
  "message": "转专业需要什么条件？"
}
```

**响应：**
```json
{
  "success": true,
  "reply": "根据学生手册第二十八条规定...",
  "ai_name": "天职小咕"
}
```

### GET /api/health
健康检查

**响应：**
```json
{
  "status": "healthy",
  "handbook_loaded": true,
  "ai_provider": "gemini",
  "ai_name": "天职小咕"
}
```

## ⚠️ 注意事项

1. **API 密钥安全**：`.env` 文件已添加到 `.gitignore`，请勿将其提交到代码仓库
2. **知识库路径**：如需修改学生手册文件路径，请编辑 `.env` 文件中的 `STUDENT_HANDBOOK_1` 和 `STUDENT_HANDBOOK_2`
3. **防火墙**：确保防火墙允许访问 5000 端口

## 📝 常见问题

**Q: 启动时报错 "No module named 'flask'"**
A: 请确保已安装依赖：`pip install -r requirements.txt`

**Q: 提示 "未配置 API 密钥"**
A: 请检查 `.env` 文件是否正确创建，并包含有效的 API 密钥

**Q: 知识库加载失败**
A: 请检查 `.env` 中的 `STUDENT_HANDBOOK_1` 和 `STUDENT_HANDBOOK_2` 路径是否正确

## 🛠️ 技术栈

- **后端**：Python + Flask
- **前端**：HTML5 + CSS3 + Vanilla JavaScript
- **AI 接口**：Google Gemini / OpenAI / DeepSeek
- **依赖管理**：pip

## 📄 许可证

本项目仅供学习交流使用。

---

Made with ❤️ for TUTE
