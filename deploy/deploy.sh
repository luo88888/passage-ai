#!/usr/bin/env bash
# =============================================================================
# passageAI 服务器一键更新脚本（在服务器上执行）
#
# 用法：
#   bash deploy/deploy.sh [分支名]        # 默认 main
#   SKIP_INSTALL=1 bash deploy/deploy.sh  # 只拉代码 + 重启，跳过依赖安装/前端构建
#
# 前置条件：
#   1. 服务器上已按 deploy/部署指南.md 完成首次部署
#   2. 已在 <项目根>/backend/.env 配置好生产环境变量
#   3. 执行用户对项目目录有读写权限，并有 sudo systemctl 权限
# =============================================================================
set -euo pipefail

# 自动定位项目根目录（脚本位于 <root>/deploy/deploy.sh）
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH="${1:-main}"
SERVICE_NAME="${SERVICE_NAME:-passageai-backend}"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"

echo "==> 项目目录: $APP_DIR"
echo "==> 更新分支: $BRANCH"

cd "$APP_DIR"

echo "==> [1/5] 拉取最新代码"
git fetch --all --prune
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  echo "==> [2/5] 后端依赖同步（uv sync）"
  cd "$BACKEND_DIR"
  uv sync

  echo "==> [3/5] 前端依赖安装 + 构建"
  cd "$FRONTEND_DIR"
  # 用 npm install 而非 npm ci：本项目 UserManagePage.vue 使用 scss，
  # 依赖 sass-embedded（已在 package.json 声明）；若 lock 未同步，npm ci 会直接失败，
  # 而 npm install 会自动补齐缺失依赖并更新本地 package-lock.json
  npm install
  npm run build
else
  echo "==> [2-3/5] 已跳过依赖安装与前端构建（SKIP_INSTALL=1）"
fi

echo "==> [4/5] 重启后端服务: $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "==> [5/5] 部署完成 ✅"