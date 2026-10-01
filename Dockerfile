# 双色球娱乐分析工作台 —— 生产镜像（python slim + gunicorn）
# PY_BASE 可用构建参数覆盖，国内部署建议通过 docker-compose 传入镜像加速源
ARG PY_BASE=python:3.11-slim
FROM ${PY_BASE}

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

COPY app.py db.py analysis.py demo_data.py fetcher.py sync.py scheduler.py ./
COPY static ./static

# 数据目录：docker-compose 挂载卷持久化
RUN mkdir -p /app/data

EXPOSE 8000

# 单 worker：定时任务由主进程调度，避免多 worker 重复执行
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "1", "--timeout", "120", "app:app"]
