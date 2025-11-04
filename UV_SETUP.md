# ⚡ 使用 UV 快速构建环境

`uv` 是一个极快的 Python 包管理工具，比 pip 快 10-100 倍！

## 📦 安装 UV

### macOS / Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 使用 pip 安装
```bash
pip install uv
```

验证安装：
```bash
uv --version
```

---

## 🚀 使用 UV 构建项目环境

### 方法 1：使用 pyproject.toml（推荐）⭐

```bash
# 1. 创建虚拟环境并安装所有依赖（一条命令搞定！）
uv venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows

# 2. 同步安装依赖
uv pip sync requirements.txt

# 或者直接使用 pyproject.toml
uv pip install -e .
```

### 方法 2：直接从 requirements.txt 安装

```bash
# 创建虚拟环境
uv venv

# 激活环境
source .venv/bin/activate  # Linux/macOS

# 安装依赖（超快！）
uv pip install -r requirements.txt
```

### 方法 3：一键安装（最简单）

```bash
# UV 会自动创建虚拟环境并安装依赖
uv run python3 -m uvicorn src.main:app --reload
```

---

## ⚡ UV 的优势

| 特性 | pip | uv |
|------|-----|-----|
| 安装速度 | 慢 | **快 10-100倍** ⚡ |
| 依赖解析 | 慢 | **极快** |
| 磁盘缓存 | 有 | **全局缓存** 💾 |
| 环境管理 | 需要 venv | **内置支持** |
| 锁文件 | 无 | **uv.lock** 🔒 |

---

## 📝 常用命令对照

| 操作 | pip | uv |
|------|-----|-----|
| 安装包 | `pip install fastapi` | `uv pip install fastapi` |
| 批量安装 | `pip install -r requirements.txt` | `uv pip install -r requirements.txt` |
| 创建环境 | `python -m venv .venv` | `uv venv` |
| 运行脚本 | `python script.py` | `uv run script.py` |
| 同步依赖 | 无 | `uv pip sync requirements.txt` |

---

## 🎯 项目开发工作流

### 初次设置

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 进入项目目录
cd /Users/ch3/PycharmProjects/flai_agent

# 3. 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 4. 复制配置文件
cp config/config.yaml.example src/config.yaml
vim src/config.yaml  # 填入实际配置

# 5. 启动服务
uvicorn src.main:app --reload
```

### 日常开发

```bash
# 激活环境
source .venv/bin/activate

# 添加新依赖
uv pip install new-package

# 更新 requirements.txt
uv pip freeze > requirements.txt

# 启动服务
uvicorn src.main:app --reload
```

### 一键运行（无需手动激活环境）

```bash
# uv 会自动使用虚拟环境
uv run uvicorn src.main:app --reload
```

---

## 🔒 依赖锁定（可选）

UV 支持生成锁文件，确保跨环境一致性：

```bash
# 生成锁文件
uv pip compile pyproject.toml -o requirements.lock

# 从锁文件安装
uv pip install -r requirements.lock
```

---

## 🔄 从 pip/conda 迁移到 UV

### 如果你之前使用 conda

```bash
# 1. 导出当前环境的依赖
conda list --export > conda_packages.txt

# 2. 使用 uv 创建新环境
uv venv
source .venv/bin/activate

# 3. 安装项目依赖
uv pip install -r requirements.txt
```

### 如果你之前使用 pip + venv

```bash
# 1. 删除旧的虚拟环境（可选）
rm -rf venv/

# 2. 使用 uv 创建新环境
uv venv .venv

# 3. 安装依赖
source .venv/bin/activate
uv pip install -r requirements.txt
```

---

## 💡 UV 最佳实践

### 1. 使用虚拟环境

```bash
# 始终在虚拟环境中工作
uv venv .venv
source .venv/bin/activate
```

### 2. 使用 pyproject.toml

本项目已配置好 `pyproject.toml`，可以直接：

```bash
uv pip install -e .              # 开发模式安装
uv pip install -e ".[dev]"       # 包含开发依赖
```

### 3. 保持依赖同步

```bash
# 安装新包后，更新 requirements.txt
uv pip freeze > requirements.txt
```

---

## 🐛 常见问题

### Q: uv venv 失败？

**A**: 确保已安装 uv：
```bash
uv --version
# 如果未安装，运行安装脚本
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Q: 找不到 Python？

**A**: uv 会自动检测系统 Python，或指定版本：
```bash
uv venv --python 3.11
```

### Q: 依赖冲突？

**A**: uv 的依赖解析器非常强大，通常能自动解决。如果有问题：
```bash
uv pip install --upgrade-package problematic-package
```

---

## 📚 更多资源

- UV 官方文档: https://github.com/astral-sh/uv
- UV 安装指南: https://astral.sh/uv
- 性能对比: https://github.com/astral-sh/uv#benchmarks

---

## ✅ 验证清单

设置完成后，验证以下内容：

- [ ] `uv --version` 能正常运行
- [ ] `.venv/` 目录已创建
- [ ] `uv pip list` 显示所有依赖
- [ ] `uvicorn src.main:app --reload` 能启动服务
- [ ] API文档可访问：http://localhost:8000/docs

---

**🎉 享受 UV 带来的极速体验！**

