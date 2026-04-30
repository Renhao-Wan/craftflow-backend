#!/bin/bash
# CraftFlow Backend 开发服务器启动脚本 (Bash)

echo "🚀 启动 CraftFlow Backend 开发服务器..."
echo ""

# 激活虚拟环境
source .venv/Scripts/activate

# 检查 .env.dev 是否存在
if [ ! -f ".env.dev" ]; then
    echo "⚠️  未找到 .env.dev 文件"
    echo "正在从 .env.example 复制..."
    cp .env.example .env.dev
    echo "✅ 已创建 .env.dev，请编辑并填写 API Key"
    echo ""
fi

# 启动服务器
echo "启动 Uvicorn 服务器..."
uv run uvicorn app.main:app --reload --env-file .env.dev --host 127.0.0.1 --port 8000
