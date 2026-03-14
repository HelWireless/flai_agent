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
- Windows 10/11 或 Linux 64-bit
- 4GB+ RAM
- MySQL 数据库 (生产环境：81.68.235.167)
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
# 生产环境数据库名为: pillow_customer_prod
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

**生产模式（部署建议）**：
```bash
# 使用 uvicorn 高级配置运行（多进程、代理头等）
source .venv/bin/activate

# 推荐参数：4个worker进程
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips="*"

# 后台运行
nohup python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 > logs/app.log 2>&1 &
```

## 🛠️ 生产环境部署指南

### 1. 数据库准备 (MySQL)
- 数据库名：`pillow_customer_prod`
- 执行 `scripts/create_coc_tables.sql` 和 `scripts/create_instance_world_tables.sql` 初始化表结构。
- 验证核心表：`t_coc_game_state`, `t_freak_world_game_state`, `t_prompt_config`, `t_coc_save_slot`。

### 2. 健康检查与监控
- **健康检查**: `curl http://localhost:8000/health`
- **日志监控**: `tail -f logs/app.log`
- **性能指标**: 访问 `/metrics` 获取 Prometheus 格式指标。

### 3. 备份策略
- **每日备份**: `mysqldump -u pillow -p pillow_customer_prod > backup_$(date +%F).sql`
- **日志轮转**: 系统默认保留60天日志并自动清理。

### 4. 运维建议
- **SSL 部署**: 建议使用 Nginx 作为反向代理并配置 SSL 证书。
- **配置重载**: `curl -X POST http://localhost:8000/reload-config` 可在不重启服务的情况下重载 Prompt 配置。

## 📁 项目结构

*(此处保持原 README 结构描述不变...)*

## 🔧 API 文档

启动服务后，访问 Swagger 文档查看所有 API 接口的详细使用方法：

- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc

*(此处保持原核心接口说明不变...)*

## 🛠️ 开发说明

*(此处保持原开发说明不变...)*

## 📝 许可证

本项目为个人项目。
