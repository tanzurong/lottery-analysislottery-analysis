# 双色球娱乐分析工作台（NAS / Docker 部署版）

基于历史开奖数据的**娱乐统计分析工具**：数据导入、冷热/遗漏/和值统计、走势图、加权随机号码生成，以及「我的推荐 → 开奖后自动核对中奖级别与奖金」。

> **重要声明**：双色球每期开奖均为独立随机事件，任何历史统计与号码生成均**不构成中奖预测**，本工具仅用于数据学习与娱乐参考，不提供购彩建议，请理性娱乐。

## 技术栈

- 后端：Python 3.11 + Flask + SQLite（零外部依赖，数据存 `./data/lottery.db`）
- 前端：原生 HTML/JS + ECharts（无构建步骤）
- 部署：Docker / Docker Compose（镜像基于 python:3.11-slim，gunicorn 生产运行）

## 数据自动更新（重要）

- **开奖数据无需手动导入**：服务启动约 15 秒后自动从福彩官网公开接口（cwl.gov.cn）拉取最新开奖数据入库；若库中尚无真实数据则先拉取约 100 期历史，随后每日 **10:00（Asia/Shanghai）** 自动增量更新。
- **「我的推荐 · 中奖核对」每日自动核对**：每次同步完成后自动用「保存后最早的一期开奖」核对所有未核对推荐，页面也可点「立即核对」手动执行。
- 数据页提供「立即从网络更新」按钮手动触发同步；网络异常时同步失败不影响服务运行，仍可用「导入开奖数据」兜底。
- 数据来源标注：概览页显示「网络自动更新 · 最新期 XXXXXX」；库中真实数据入库后自动清除内置演示数据。
- 环境变量 `AUTO_SYNC=0` 可关闭自动同步（一般无需设置）。

## 目录结构

```
lottery-nas/
├── app.py              # Flask 入口（REST API + 静态托管 + 同步/调度接入）
├── db.py               # SQLite 数据层（开奖记录 + 我的推荐 + 元信息）
├── analysis.py         # 统计 / 加权随机推荐 / 中奖级别核对
├── fetcher.py          # 开奖数据网络获取（福彩官网公开接口）
├── sync.py             # 数据同步 + 自动核对推荐
├── scheduler.py        # 每日定时任务（APScheduler，10:00 自动同步）
├── demo_data.py        # 内置演示数据（首次启动写入，联网后自动替换为真实数据）
├── static/index.html   # 前端页面（单文件，离线可预览）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── data/               # SQLite 数据库（容器内挂载，持久化）
```

## 一、部署到 NAS

### 方式 0.5：飞牛 NAS（fnOS）

1. GitHub 仓库页面 → **Code → Download ZIP**，解压到 NAS 任意文件夹（例如 `/vol1/1000/docker/lottery`）。
2. 打开飞牛 **Docker → Compose 项目 → 新建项目**：
   - 项目名称：`lottery-analysis`
   - 路径：选择刚才的解压目录（该目录内已含 `docker-compose.yml`）
   - 内容：选择「使用已有文件」或粘贴下方 docker-compose.yml
3. 保存并启动：飞牛自动拉取基础镜像、构建、运行。
4. 浏览器访问 `http://NAS的IP:8056`。

> 有终端权限也可一条命令：`git clone https://github.com/tanzurong/lottery-analysislottery-analysis.git && cd lottery-analysislottery-analysis && docker compose up -d --build`

### 方式 0：图形界面直接拉取（最简单，无需 SSH / 命令行）

如果你的 NAS 是**群晖**（Container Manager）或装了 **Portainer**，直接在网页界面填 Git 地址即可自动拉取、构建、启动：

- **群晖**：打开 Container Manager → 项目 → 新增 → 名称填 `lottery-analysis`，来源选 **Git 仓库**，粘贴 `https://github.com/tanzurong/lottery-analysislottery-analysis.git`，确认 `docker-compose.yml` 路径后创建。
- **Portainer**：Stacks → Add stack → 填 Git 仓库地址 → Deploy。

### 方式 1：Docker Compose（推荐，支持群晖 Container Manager / 威联通 / 任何 Linux NAS）

1. 把整个 `lottery-nas/` 目录拷贝到 NAS（例如 `docker/lottery-nas/`）。
2. SSH 登录 NAS 进入该目录，执行：

```bash
docker compose up -d --build
```

3. 浏览器访问 `http://NAS的IP:8056`。

数据持久化在 `lottery-nas/data/`，容器重建/升级不丢数据；如需迁移只需备份该目录。

### 方式 2：群晖 Container Manager（图形界面）

1. 打开 Container Manager → 项目 → 新增，选择 `lottery-nas/` 目录（其中需有 docker-compose.yml）。
2. 按向导构建并启动即可；容器名为 `lottery-analysis`，端口 8056。

### 方式 3：不想用 Docker（直接跑）

```bash
pip install -r requirements.txt
python app.py        # 默认 8000 端口，可用 PORT 环境变量修改
```

## 二、配置说明

| 项 | 默认值 | 说明 |
| --- | --- | --- |
| 访问端口 | 8056（宿主）→ 8000（容器） | 修改 `docker-compose.yml` 中 `ports` 左侧数字即可 |
| 数据文件 | `./data/lottery.db` | 容器内挂载卷，删除该文件即恢复初始状态 |
| 时区 | Asia/Shanghai | 可在 compose 中修改 |

## 三、功能与使用

1. **数据**：首次启动内置 60 期**演示数据**（非真实开奖）。在「数据」页粘贴或选择 `.txt/.csv` 文件导入真实开奖历史，每行一条：
   ```
   2025091 02 08 14 19 25 33 07
   2025090,03,09,15,21,26,32,12
   ```
   导入自动按期号去重。数据来源建议：彩票官方渠道发布的公开历史开奖数据（自行下载后导入，本工具不内置爬虫）。
2. **统计 / 走势**：支持 30/50/100/全部期窗口切换，展示频次、遗漏、奇偶比、大小比、和值走势。
3. **推荐**：热号加权 / 冷号加权 / 均衡组合三种策略生成娱乐号码。
4. **我的推荐 · 中奖核对**：生成后点「保存这批推荐」（记录保存时的基准期号）；导入保存之后的开奖数据后，点「核对中奖」，自动用**保存后最早的一期开奖**核对每组红球命中数、蓝球命中、奖级与固定奖金（一二等奖为浮动奖金标注「浮动」）。

## 四、中奖核对规则（双色球固定奖金）

| 红球命中 | 蓝球 | 奖级 | 奖金 |
| --- | --- | --- | --- |
| 6 | 1 | 一等奖 | 浮动 |
| 6 | 0 | 二等奖 | 浮动 |
| 5 | 1 | 三等奖 | 3000 |
| 5 / 4 | 0 / 1 | 四等奖 | 200 |
| 4 / 3 | 0 / 1 | 五等奖 | 10 |
| 2 / 1 / 0 | 1 | 六等奖 | 5 |

## 五、常见问题

- **构建时拉取基础镜像超时**（`registry-1.docker.io ... Timeout`）：国内网络直连 Docker Hub 不稳定。本仓库已默认在 `docker-compose.yml` 中通过 `PY_BASE` 走镜像加速源 `docker.m.daocloud.io`；若该源不可用，把它替换为以下任一可用源即可：
  ```
  docker.1ms.run
  docker.xuanyuan.me
  hub.rat.dev
  docker.m.daocloud.io
  ```
  替换位置：`docker-compose.yml` 中 `build.args.PY_BASE` 的 `docker.m.daocloud.io/library/python:3.11-slim`（换前缀，保留 `/library/python:3.11-slim` 部分）。也可在飞牛/群晖的 Docker 设置里添加镜像加速器，全局生效。
- **pip 安装慢**：Dockerfile 已默认使用阿里云 PyPI 镜像（`mirrors.aliyun.com`）。
- **端口冲突**：8056 被占用时修改 compose 里 `ports` 左侧端口，如 `8057:8000`。
- **数据丢失**：确认 `./data` 卷挂载正常；备份该目录即可迁移。
- **页面显示「离线演示」**：说明浏览器没连上后端（仅离线预览模式，功能受浏览器存储限制）；部署成功后刷新即显示「后端在线」。
- **想清空数据**：页面「数据 → 清空数据」；或删除容器后移除 `data/lottery.db`。

## 合规提醒

请勿将本工具用于付费荐号、会员收费等商业用途，请勿宣称可预测开奖结果；开奖完全随机，请理性娱乐。
