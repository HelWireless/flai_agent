#!/bin/bash
# 部署脚本 - 在服务器上运行

echo "===== 开始部署 ====="

# 1. 进入项目目录
cd /root/flai_agent || exit 1

# 2. 拉取最新代码
echo "[1/4] 拉取最新代码..."
git pull origin company_pc

# 3. 检查是否需要创建数据库表
echo "[2/4] 检查数据库表..."
python scripts/create_preset_tables.py

# 4. 停止旧服务
echo "[3/4] 停止旧服务..."
pkill -f "python -m src.main" || true
sleep 2

# 5. 启动新服务
echo "[4/4] 启动新服务..."
nohup python -m src.main > logs/app.log 2>&1 &

echo ""
echo "===== 部署完成 ====="
echo "服务日志: tail -f logs/app.log"
echo ""
echo "提示: 如果是首次部署，请运行以下命令生成预制数据:"
echo "  python scripts/generate_preset_characters.py"
