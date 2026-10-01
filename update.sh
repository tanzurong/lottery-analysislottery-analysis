#!/bin/bash
# 一键更新：从 GitHub 拉取最新代码并重建容器。
# 用法：cd 到本目录后执行  bash update.sh
set -e
cd "$(dirname "$0")"
echo "==> [1/3] 拉取最新代码..."
git pull --ff-only
echo "==> [2/3] 重建容器..."
docker compose up -d --build
echo "==> [3/3] 完成。"
echo "    访问 http://<飞牛IP>:8056  （若页面未变，浏览器按 Ctrl+F5 强制刷新）"
