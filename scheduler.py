# -*- coding: utf-8 -*-
"""定时任务：每天自动同步开奖数据并核对推荐（容器内单 worker 运行）。"""
import threading
import logging

from apscheduler.schedulers.background import BackgroundScheduler

import sync

log = logging.getLogger("lottery.scheduler")

SCHED_HOUR = 10  # 每天 10:00（Asia/Shanghai），可自行修改
INIT_DELAY = 15  # 启动后延迟秒数执行首次同步


def _daily_job():
    try:
        result = sync.sync_now()
        log.info("daily sync ok: %s", result)
    except Exception as exc:  # 网络/接口异常不中断服务
        log.warning("daily sync failed: %s", exc)


def _initial_sync():
    try:
        result = sync.sync_now()
        log.info("initial sync ok: %s", result)
    except Exception as exc:
        log.warning("initial sync failed: %s", exc)


_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(_daily_job, "cron", hour=SCHED_HOUR, minute=0, id="daily_sync")
    _scheduler.start()
    log.info("scheduler started: daily %02d:00", SCHED_HOUR)
    threading.Timer(INIT_DELAY, _initial_sync).start()
