# 深壤 Agent

AI对话代理服务，基于FastAPI构建，支持多角色对话、情绪分析、语音合成、文字冒险游戏等功能。

## 📋 功能特性

- 🤖 多角色AI对话系统（支持第三方角色 + 虚拟身份卡）
- 🧠 **长短期记忆**（支持语义检索）
- 😊 智能情绪识别与分析
- 🔊 文字转语音（TTS）
- 🎴 占卜抽卡功能
- 🛡️ 敏感内容过滤
- 💾 对话历史记录
- ☁️ OSS云存储集成
- 🔥 配置热更新
- 🌍 **副本世界**（文字冒险游戏，SSE流式响应）
- 🐙 **克苏鲁跑团(COC)**（TRPG角色扮演）

## 🚀 快速开始

### 1. 环境要求

- Python 3.11+
- MySQL 数据库
- 阿里云OSS（用于语音文件存储）
- Qdrant 向量数据库（可选，用于长期记忆功能）

### 2. 使用 UV 构建环境

**安装 UV**：

**Linux/macOS 用户**：
```bash
# 使用官方安装脚本（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pipx 安装
pipx install uv

# 或使用 pip 安装
pip install uv
```

**Windows 用户可以使用以下命令**：
```powershell
# 在 PowerShell 中安装
winget install astral-sh.uv

# 或使用官方安装脚本
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**创建虚拟环境并安装依赖**：
```bash
# 创建虚拟环境
uv venv

# 激活环境
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\Activate.ps1  # Windows

# 安装依赖
uv pip install -r requirements.txt
```

### 3. 配置文件

```bash
# 复制配置模板
cp config/config.yaml.example config/config.yaml

# 编辑配置文件，填入实际的数据库、API密钥等信息
vim config/config.yaml
```

### 4. 启动项目

**开发模式（推荐）**：
```bash
# 方式1：UV 自动管理环境（无需手动激活）
uv run python src/main.py

# 方式2：激活环境后运行
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\Activate.ps1  # Windows
python src/main.py
```

**生产模式（高级配置）**：
```bash
# 使用 uvicorn 高级配置运行（多进程、代理头等）
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\Activate.ps1  # Windows

# 使用高级配置运行
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 3 --proxy-headers --forwarded-allow-ips="*"

# 后台运行
nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 3 --proxy-headers --forwarded-allow-ips="*" > logs/app.log 2>&1 &
```

**访问服务**：
- API 文档：http://localhost:8000/docs
- 交互式文档：http://localhost:8000/redoc

## 📁 项目结构

```
flai_agent/
├── config/                    # 配置文件
│   ├── prompts/              # Prompt配置（JSON格式，支持热更新）
│   │   ├── characters.json   # 角色系统配置
│   │   ├── character_openers.json  # 角色开场白
│   │   ├── emotion_states.json     # 情绪状态配置
│   │   ├── responses.json    # 回复配置
│   │   └── constants.json    # 常量配置
│   └── llm_params.json       # LLM参数配置
├── data/                      # 数据文件
│   └── sensitive_words.txt   # 敏感词列表
├── logs/                      # 运行时日志（按周划分，按月归档）
│   ├── 2025-10/              # 2025年10月的日志
│   │   └── 2025-10-27_2025-11-02.log
│   └── 2025-11/              # 2025年11月的日志
│       └── 2025-11-03_2025-11-09.log
├── scripts/                   # 工具脚本
│   ├── check_dialogue_history.py  # 对话历史检查工具
│   ├── log_extractor.py      # 日志提取工具
│   └── log_extractor.sh
├── src/                       # 源代码
│   ├── api/                  # API层
│   │   ├── prompts/
│   │   │   └── generate_prompts.py
│   │   └── routes.py         # API路由定义
│   ├── core/                 # 核心业务逻辑
│   │   ├── config_loader.py  # 配置加载器（支持热更新）
│   │   ├── content_filter.py # 内容过滤
│   │   └── dialogue_query.py # 对话查询
│   ├── models/               # 数据模型
│   │   └── chat_memory.py    # 聊天记忆模型
│   ├── services/             # 服务层
│   │   ├── chat_service.py        # 聊天服务
│   │   ├── emotion_service.py     # 情绪服务
│   │   ├── fortune_service.py     # 占卜服务
│   │   ├── llm_service.py         # LLM服务
│   │   ├── memory_classifier.py   # 记忆分类器
│   │   ├── memory_service.py      # 记忆服务
│   │   ├── oss_client.py          # OSS客户端
│   │   ├── persistent_memory_service.py  # 持久化记忆服务
│   │   ├── speech_api.py          # 语音API
│   │   ├── vector_store.py        # 向量存储
│   │   └── voice_service.py       # 语音服务
│   ├── custom_logger.py      # 自定义日志配置
│   ├── database.py           # 数据库配置
│   ├── main.py               # 应用入口
│   ├── schemas.py            # 数据模型定义
│   └── utils.py              # 工具函数
├── pyproject.toml            # 项目配置
├── requirements.txt          # 依赖列表
└── .gitignore
```

## 🔧 API 文档

启动服务后，访问 Swagger 文档查看所有 API 接口的详细使用方法：

- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc

### 核心接口

#### 1. 对话接口 `/pillow/chat-pillow`

```json
// 请求
POST /pillow/chat-pillow
{
    "userId": "1000001",
    "message": "你好",
    "message_count": 3,
    "character_id": "c1s1c1_0001",  // 第三方角色ID，默认"default"
    "voice": false,
    "virtualId": 0  // 虚拟身份卡ID，0=用户自己，1-4=身份卡人物
}

// 响应
{
    "user_id": "1000001",
    "llm_message": ["你好呀~", "今天心情怎么样？"],
    "emotion_type": 1
}
```

**virtualId 身份卡说明**：
- `0`：用户自己身份（默认）
- `1`：常骁（男，大三学生/外卖员）
- `2`：陆耀阳（男，CEO）
- `3`：贺筱满（女，大学生/视频博主）
- `4`：沈清舟（女，CFO）

#### 2. 副本世界 `/pillow/freak-world/chat`

```json
// 请求 - 新游戏
POST /pillow/freak-world/chat
{
    "userId": "1000001",
    "worldId": "01",
    "gmId": "yan",
    "action": "chat"
}

// 响应 (SSE)
data: {"type": "delta", "content": "欢迎来到..."}
data: {"type": "done", "result": {...}}
```

#### 3. 克苏鲁跑团 `/pillow/coc/chat`

```json
// 请求 - 新游戏
POST /pillow/coc/chat
{
    "accountId": 1000001,
    "action": "start"
}

// 响应
{
    "sessionId": "coc_abc123",
    "gameStatus": "gm_select",
    "content": "欢迎来到《克苏鲁的呼唤》...",
    "selections": [
        {"id": "female", "text": "女性GM"},
        {"id": "male", "text": "男性GM"}
    ]
}

// 请求 - 选择GM
{
    "sessionId": "coc_abc123",
    "accountId": 1000001,
    "selection": "female"
}
```

**COC 游戏状态流程**：
```
gm_select → step1_attributes → step2_secondary → 
step3_profession → step4_background → step5_summary → playing
```

#### 4. 其他接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/pillow/text2voice` | POST | 文字转语音 |
| `/pillow/character_opener` | POST | 获取角色开场白 |
| `/pillow/draw-card` | POST | 占卜抽卡 |
| `/pillow/memory/{user_id}/profile` | GET | 获取用户画像 |
| `/pillow/memory/{user_id}/stats` | GET | 获取记忆统计 |
| `/pillow/memory/{user_id}` | DELETE | 清除用户记忆 |

## 🛠️ 开发说明

### 架构说明

项目采用分层架构：
- **API层**（`routes.py`）- 纯路由定义，参数验证
- **服务层**（`services/`）- 业务逻辑，LLM调用
- **核心层**（`core/`）- 通用功能，数据查询
- **配置层**（`config/`）- JSON配置，支持热更新

### 三层记忆系统

本项目实现智能的三层记忆架构：

1. **对话历史**（MySQL）- 最近30天20轮对话，保持连贯性
2. **持久化记忆**（MySQL chat_memory表）- LLM自动提取用户特征
   - 短期记忆：最近事件（"我昨天吃了火锅"）→ 每20轮对话批量更新，时间精确到秒
   - 长期记忆：用户偏好（"我喜欢吃辣的"）→ 立即更新
   - 自动整理：非当天的多条短期记忆会自动按日期合并成一条总结
3. **额外记忆**（Qdrant，可选）- 语义相似的历史对话检索（相似度阈值0.8）

**配置示例**：
```
# 持久化记忆（默认启用）
persistent_memory:
  enabled: true
  short_term_update_interval: 20
  enabled_characters: []  # 空=全部启用，或指定角色

# 向量检索（可选）
vector_db:
  enabled: false  # 改为 true 启用
```

### 时间感知

Pillow 角色能够感知当前时间（精确到秒），并在回复中自然地引用时间概念：
- 系统自动将当前时间注入到 system prompt 中
- 时间格式：`YYYY年MM月DD日 HH点MM分SS秒`
- 角色会根据时间使用模糊表达（如"早上"、"晚上"），必要时精确到分钟

### 情绪处理系统

本项目采用多层次的情绪处理机制：

1. **情绪状态**：系统内部维护的情绪状态，如 'happy', 'anger', 'sadness' 等
2. **情绪表现**：根据情绪状态生成的外在表现描述，如 "快乐"、"气愤" 等
3. **情绪编码**：最终用于接口返回的数字编码，如 1、6 等

情绪处理流程：
1. 系统获取当前的内在情绪状态（如 'happy'）
2. 通过 `emotion_states.json` 配置将内在情绪映射为外在表现描述（如 "快乐"）
3. 将情绪信息嵌入到提示词中，引导LLM生成具有相应情绪色彩的回复
4. LLM在生成回复时可能会返回情绪类型（如"开心"）
5. 系统通过 `get_emotion_type` 函数将情绪表现转换为数字编码

### 配置热更新

配置文件支持热更新，修改以下文件后会自动生效，无需重启服务：
- `config/prompts/*.json` - 所有 Prompt 配置
- `config/llm_params.json` - LLM 参数配置
- `data/sensitive_words.txt` - 敏感词列表

### 添加新角色

编辑 `config/prompts/characters.json` 和 `config/prompts/character_openers.json`，添加新的角色配置。

### 日志管理

日志按周划分，自动按月归档到文件夹：
- **文件夹**：`logs/YYYY-MM/` (按开始日期的月份)
- **文件名**：`YYYY-MM-DD_YYYY-MM-DD.log` (周一到周日)
- **自动清理**：超过6个月的日志会在服务启动时自动清理

示例：
```
logs/
├── 2025-10/
│   └── 2025-10-27_2025-11-02.log  (跨月的周，按开始日期归档到10月)
└── 2025-11/
    └── 2025-11-03_2025-11-09.log
```

查看日志：
```bash
# 查看当前周的日志
tail -f logs/$(date +%Y-%m)/*.log

# 或查看最新的日志文件
tail -f $(ls -t logs/*/*.log | head -1)

# 提取指定时间段日志
./scripts/log_extractor.sh "2025-11-04 10:00" "2025-11-04 11:00" logs/2025-11/*.log
```

### 常用命令

```bash
# 添加新依赖
source .venv/bin/activate
uv pip install package-name
pip freeze > requirements.txt

# 查看已安装的包
source .venv/bin/activate
pip list
```

## 📋 更新日志

### 2026-02-04
- 新增虚拟身份卡功能（virtualId 参数）
- 支持用户扮演虚拟人物与第三方角色对话
- 对话历史按 virtualId 隔离
- 新增 COC 克苏鲁跑团功能测试
- 完善 API 文档和 Swagger 用例

### 2026-02-01
- 新增副本世界（Freak World）文字冒险系统
- 新增克苏鲁跑团（COC）TRPG 系统
- 清理一次性工具脚本
- 同步代码到 online 和 main 分支

### 2026-01
- 批量添加 C1S7 角色配置和开场白
- 优化角色查找和错误处理机制
- 重构 prompt 生成模块，迁移到 JSON 配置

## 📝 许可证

本项目为个人项目。