# 🔄 项目重构迁移指南

本文档说明如何从旧结构迁移到新的项目结构。

## ⚠️ 重要提醒

**首次部署新版本前请完成以下步骤**：

### 1. 配置文件迁移

旧版本的配置文件在 `src/config.yaml`，新版本需要：

```bash
# 确保配置文件存在（如果没有，复制模板）
cp config/config.yaml.example src/config.yaml
```

然后编辑 `src/config.yaml` 填入实际配置。

### 2. 依赖安装

```bash
pip install -r requirements.txt
```

### 3. 数据库表结构

无需修改，数据库表结构保持不变。

## 📊 主要变更说明

### 配置热更新

新版本支持配置热更新！修改以下文件后**无需重启服务**：

- `config/prompts/characters.json` - 角色配置
- `config/prompts/character_openers.json` - 开场白
- `config/prompts/emotions.json` - 情绪配置
- `config/prompts/responses.json` - 回复文本
- `config/prompts/constants.json` - 常量配置

配置会在下次请求时自动重新加载。

### 导入路径变更

**如果你有自定义代码，需要更新导入路径**：

| 旧路径 | 新路径 |
|--------|--------|
| `from src.dialogue_query import ...` | `from src.core.dialogue_query import ...` |
| `from src.content_filter import ...` | `from src.core.content_filter import ...` |
| `from src.speech_api import ...` | `from src.services.speech_api import ...` |
| `from src.oss_client import ...` | `from src.services.oss_client import ...` |

### 配置文件访问方式

**旧方式**（已废弃）：
```python
from src.api.prompts.character_other_info import characters_opener
```

**新方式**：
```python
from src.core.config_loader import get_config_loader

loader = get_config_loader()
characters_opener = loader.get_character_openers()

# 或使用便捷函数
from src.core.config_loader import get_character_opener
opener = get_character_opener('c1s1c1_0001')
```

## 🎯 配置文件编辑

### 添加新角色

编辑 `config/prompts/characters.json`：

```json
{
  "characters": {
    "new_character_id": {
      "name": "角色名称",
      "age": 25,
      "traits": ["特质1", "特质2"],
      "user_prompt": "..."
    }
  }
}
```

编辑 `config/prompts/character_openers.json`：

```json
{
  "new_character_id": [
    "开场白1",
    "开场白2"
  ]
}
```

### 修改回复文本

编辑 `config/prompts/responses.json`：

```json
{
  "sensitive_responses": ["回复1", "回复2"],
  "error_responses": ["错误回复1", "错误回复2"]
}
```

## 🔍 验证清单

部署后请检查：

- [ ] API 服务正常启动
- [ ] 访问 `/docs` 查看 API 文档
- [ ] 测试 `/pillow/chat-pillow` 接口
- [ ] 测试 `/pillow/character_opener` 接口
- [ ] 检查日志输出是否正常
- [ ] 修改配置文件，验证热更新是否生效

## 🐛 常见问题

### 1. 找不到配置文件

**错误**：`FileNotFoundError: 配置文件不存在`

**解决**：检查 `config/prompts/*.json` 是否存在，权限是否正确。

### 2. 导入错误

**错误**：`ModuleNotFoundError: No module named 'src.dialogue_query'`

**解决**：更新导入路径为 `from src.core.dialogue_query import ...`

### 3. 配置未生效

**问题**：修改配置后没有生效

**解决**：
- 检查 JSON 格式是否正确
- 如果需要立即生效，可以重启服务
- 或者调用 `config_loader.reload_all()` 强制重新加载

## 📞 获取帮助

如有问题，请检查：
1. 日志文件：`logs/app.log`
2. README.md 中的文档
3. Git 提交历史：`git log --oneline`

## 🔙 回滚方法

如果遇到问题需要回滚到旧版本：

```bash
# 回滚到重构前
git checkout b316db2

# 或回滚到更早版本
git checkout 70f0e29
```

