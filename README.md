# Flai Agent

AI对话代理服务，基于FastAPI构建，支持多角色对话、情绪分析、语音合成等功能。

## 📋 功能特性

- 🤖 多角色AI对话系统
- 😊 智能情绪识别与分析
- 🔊 文字转语音（TTS）
- 🎴 占卜抽卡功能
- 🛡️ 敏感内容过滤
- 💾 对话历史记录
- ☁️ OSS云存储集成

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- MySQL 数据库
- 阿里云OSS（用于语音文件存储）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

复制配置模板并修改：

```bash
cp config/config.yaml.example src/config.yaml
```

编辑 `src/config.yaml`，填入你的配置信息：
- 数据库连接信息
- API密钥（模型API、语音API等）
- OSS配置

### 4. 运行服务

```bash
# 开发模式
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式（后台运行）
nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &
```

服务将在 `http://localhost:8000` 启动

API文档：`http://localhost:8000/docs`

## 📁 项目结构

```
flai_agent/
├── config/                    # 配置文件
│   └── prompts/              # Prompt配置（JSON格式）
│       ├── characters.json   # 角色系统配置
│       ├── character_openers.json  # 角色开场白
│       ├── emotions.json     # 情绪配置
│       ├── responses.json    # 回复配置
│       └── constants.json    # 常量配置
├── data/                      # 数据文件
│   └── sensitive_words.txt   # 敏感词列表
├── logs/                      # 运行时日志
├── scripts/                   # 工具脚本
│   ├── log_extractor.py      # Python日志提取工具
│   └── log_extractor.sh      # Shell日志提取工具
├── src/                       # 源代码
│   ├── api/                  # API层
│   │   └── routes.py         # API路由定义
│   ├── core/                 # 核心业务逻辑
│   │   ├── config_loader.py  # 配置加载器
│   │   ├── content_filter.py # 内容过滤
│   │   └── dialogue_query.py # 对话查询
│   ├── services/             # 第三方服务
│   │   ├── oss_client.py     # OSS客户端
│   │   └── speech_api.py     # 语音API
│   ├── database.py           # 数据库配置
│   ├── schemas.py            # 数据模型
│   ├── utils.py              # 工具函数
│   ├── custom_logger.py      # 日志配置
│   └── main.py               # 应用入口
├── requirements.txt           # 依赖列表
├── .gitignore
└── README.md
```

## 🔧 API接口

### 1. 对话接口

```http
POST /pillow/chat-pillow
```

**请求参数**：
```json
{
  "user_id": "string",
  "message": "string",
  "message_count": 1,
  "character_id": "default",
  "voice": false
}
```

**响应**：
```json
{
  "user_id": "string",
  "llm_message": ["string"],
  "emotion_type": 2
}
```

### 2. 文字转语音

```http
POST /pillow/text2voice
```

### 3. 角色开场白

```http
POST /pillow/character_opener
```

### 4. 占卜抽卡

```http
POST /pillow/draw-card
```

## 🛠️ 开发说明

### 配置热更新

配置文件支持热更新，修改 `config/prompts/*.json` 后会自动生效，无需重启服务。

### 添加新角色

编辑 `config/prompts/characters.json` 和 `config/prompts/character_openers.json`，添加新的角色配置。

### 日志查看

```bash
# 实时查看日志
tail -f logs/app.log

# 提取指定时间段日志
./scripts/log_extractor.sh "2025-11-04 10:00" "2025-11-04 11:00" logs/app.log
```

## 📝 许可证

本项目为个人项目。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。
