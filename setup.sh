#!/bin/bash
# 项目环境快速设置脚本（使用 UV）

set -e  # 遇到错误立即退出

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          🚀 Flai Agent 项目环境设置（使用 UV）              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 检查 UV 是否已安装
if ! command -v uv &> /dev/null; then
    echo "⚠️  UV 未安装，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✅ UV 安装完成！"
    echo ""
else
    echo "✅ UV 已安装: $(uv --version)"
    echo ""
fi

# 创建虚拟环境
echo "📦 创建虚拟环境..."
uv venv
echo "✅ 虚拟环境创建完成！"
echo ""

# 激活虚拟环境提示
echo "📝 激活虚拟环境："
echo "   source .venv/bin/activate"
echo ""

# 安装依赖
echo "📥 安装项目依赖（使用 UV，极快！）..."
source .venv/bin/activate
uv pip install -r requirements.txt
echo "✅ 依赖安装完成！"
echo ""

# 检查配置文件
if [ ! -f "src/config.yaml" ]; then
    echo "⚠️  配置文件不存在，正在复制模板..."
    cp config/config.yaml.example src/config.yaml
    echo "✅ 配置模板已复制到 src/config.yaml"
    echo ""
    echo "⚠️  请编辑 src/config.yaml 填入实际配置后再启动服务！"
    echo "   vim src/config.yaml"
    echo ""
else
    echo "✅ 配置文件已存在：src/config.yaml"
    echo ""
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     ✨ 设置完成！✨                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 下一步："
echo ""
echo "1. 编辑配置文件（如果还没有）："
echo "   vim src/config.yaml"
echo ""
echo "2. 启动开发服务器："
echo "   uv run uvicorn src.main:app --reload"
echo ""
echo "   或者："
echo "   source .venv/bin/activate"
echo "   uvicorn src.main:app --reload"
echo ""
echo "3. 访问 API 文档："
echo "   http://localhost:8000/docs"
echo ""
echo "📚 更多帮助："
echo "   • README.md - 完整文档"
echo "   • QUICKSTART.md - 快速上手"
echo "   • UV_SETUP.md - UV 详细说明"
echo ""
echo "🎉 祝使用愉快！"

