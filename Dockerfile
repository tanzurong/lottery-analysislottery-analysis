# 双色球娱乐分析工作台 —— 生产镜像（python slim + gunicorn）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py db.py analysis.py demo_data.py ./
COPY static ./static

# 数据目录：docker-compose 挂载卷持久化
RUN mkdir -p /app/data

EXPOSE 8000

# 首次启动自动初始化演示数据（见 app.py __main__ / wsgi 初始化）
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "--timeout", "60", "app:app"]
