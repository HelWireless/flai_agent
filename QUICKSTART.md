# 🚀 快速启动指南

## 第一次使用新版本？跟着这个清单走！

### ✅ 步骤 1：检查配置文件

```bash
# 如果 src/config.yaml 不存在，复制模板
cp config/config.yaml.example src/config.yaml
```

然后编辑 `src/config.yaml`，填入你的实际配置（数据库、API密钥等）。

### ✅ 步骤 2：安装依赖

```bash
pip install -r requirements.txt
```

### ✅ 步骤 3：启动服务

```bash
# 开发模式（带热重载）
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 或者生产模式（后台运行）
nohup python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &
```

### ✅ 步骤 4：验证服务

打开浏览器访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/pillow/

### ✅ 步骤 5：测试配置热更新

1. 修改 `config/prompts/responses.json` 中的某个回复
2. **无需重启服务**
3. 发送请求，新配置会自动生效

## 🎨 配置文件快速参考

| 文件 | 用途 | 修改频率 |
|------|------|----------|
| `config/prompts/characters.json` | 角色定义、系统提示词 | 中 |
| `config/prompts/character_openers.json` | 角色开场白 | 高 |
| `config/prompts/emotions.json` | 情绪分析配置 | 低 |
| `config/prompts/responses.json` | 错误/敏感词回复 | 高 |
| `config/prompts/constants.json` | 颜色、关键词等常量 | 低 |
| `data/sensitive_words.txt` | 敏感词列表 | 中 |

## 🔧 常用操作

### 添加新角色

1. 编辑 `config/prompts/characters.json` - 添加角色定义
2. 编辑 `config/prompts/character_openers.json` - 添加开场白
3. 保存即可，自动生效（下次请求时）

### 查看日志

```bash
# 实时查看
tail -f logs/app.log

# 提取指定时间段
./scripts/log_extractor.sh "2025-11-04 10:00" "2025-11-04 11:00" logs/app.log output.txt
```

### 修改敏感词

编辑 `data/sensitive_words.txt`，每行一个敏感词，保存后自动生效。

## ⚡ 性能提示

- 配置文件会被缓存，首次加载后访问很快
- 文件修改后会自动检测并重新加载
- 如需强制重新加载所有配置，重启服务即可

## 🐛 遇到问题？

1. 查看 `MIGRATION_GUIDE.md` - 迁移指南
2. 查看 `README.md` - 完整文档
3. 检查日志：`logs/app.log`
4. 验证配置文件格式（JSON语法）

## 📞 下一步

- [ ] 阅读 `README.md` 了解完整功能
- [ ] 查看 `MIGRATION_GUIDE.md` 了解所有变更
- [ ] 测试所有API接口
- [ ] 根据需要调整配置

祝使用愉快！🎉

