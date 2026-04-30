# CraftFlow Backend 开发服务器启动脚本 (PowerShell)

Write-Host "🚀 启动 CraftFlow Backend 开发服务器..." -ForegroundColor Green
Write-Host ""

# 激活虚拟环境
& .\.venv\Scripts\Activate.ps1

# 检查 .env.dev 是否存在
if (-Not (Test-Path ".env.dev")) {
    Write-Host "⚠️  未找到 .env.dev 文件" -ForegroundColor Yellow
    Write-Host "正在从 .env.example 复制..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env.dev"
    Write-Host "✅ 已创建 .env.dev，请编辑并填写 API Key" -ForegroundColor Green
    Write-Host ""
}

# 启动服务器
Write-Host "启动 Uvicorn 服务器..." -ForegroundColor Cyan
uv run uvicorn app.main:app --reload --env-file .env.dev --host 127.0.0.1 --port 8000
