#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE_DIR="$ROOT_DIR/release"

cd "$ROOT_DIR"

echo "[1/4] 正在构建前端 dist"
npm run build

echo "[2/4] 正在准备 release 目录"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR/frontend-dist"
mkdir -p "$RELEASE_DIR/deploy"

echo "[3/4] 正在复制发布产物"
cp -R dist/. "$RELEASE_DIR/frontend-dist/"
cp -R deploy/. "$RELEASE_DIR/deploy/"
cp .env.production "$RELEASE_DIR/"
cp package.json "$RELEASE_DIR/"

echo "[4/4] 发布目录已准备完成"
echo "前端产物目录: $RELEASE_DIR/frontend-dist"
echo "部署配置目录: $RELEASE_DIR/deploy"
