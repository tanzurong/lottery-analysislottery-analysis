#!/bin/bash
# 一键更新：从 GitHub 下载最新代码并重建容器（免 git，用 curl + python 解压）。
# 用法：cd 到本目录后执行  bash update.sh
set -e
cd "$(dirname "$0")"
REPO="https://github.com/tanzurong/lottery-analysislottery-analysis/archive/refs/heads/main.zip"

echo "==> [1/3] 下载最新代码..."
curl -fL -o /tmp/lottery-main.zip "$REPO"

echo "==> [2/3] 解压覆盖（data 目录不在包内，自动保留）..."
rm -rf /tmp/lottery-new-tmp
mkdir -p /tmp/lottery-new-tmp
python3 -m zipfile -e /tmp/lottery-main.zip /tmp/lottery-new-tmp
cp -rf /tmp/lottery-new-tmp/lottery-analysislottery-analysis-main/. ./
chmod +x update.sh 2>/dev/null || true

echo "==> [3/3] 重建容器..."
docker compose up -d --build

echo "==> 完成。访问 http://<飞牛IP>:8056  （页面没变就 Ctrl+F5 强刷）"
