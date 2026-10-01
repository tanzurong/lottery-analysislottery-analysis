# -*- coding: utf-8 -*-
"""数据同步：从网络拉取最新开奖入库，并在同步后自动核对未核对的推荐。"""
import datetime

import analysis
import db
import fetcher


def _now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def auto_check_picks():
    """对数据库中所有未核对的推荐自动核对（用其保存后最早的一期开奖）。返回本次核对条数。"""
    recs = db.load_records()
    checked = 0
    for pick in db.list_picks():
        if pick["checked"]:
            continue
        result = analysis.check_pick(recs, pick)
        if result is None:
            continue
        db.update_pick_checked(pick["id"], result)
        checked += 1
    return checked


def sync_now():
    """立即同步：无真实数据时拉取约 100 期历史，否则增量拉最新 30 期；随后自动核对推荐。"""
    db.init_db()  # 幂等：确保表存在（scheduler 独立调用时也安全）
    has_real = db.count_real() > 0
    page_size = 100 if not has_real else 30  # 首次同步拉取历史数据
    rows = fetcher.fetch_ssq(page_size=page_size)
    records = [{"period": r["period"], "red": r["red"], "blue": r["blue"]} for r in rows]
    added = db.upsert_records(records, demo=False)
    db.delete_demo()  # 同步成功后移除演示数据，统计窗口保持纯真实
    latest = rows[0]
    db.set_meta("last_sync", _now_str())
    db.set_meta("last_sync_period", latest["period"])
    db.set_meta("last_sync_date", latest["date"])
    db.set_meta("sync_source", "福彩官网（cwl.gov.cn）")
    db.set_meta("sync_pages", str(page_size))
    checked = auto_check_picks()
    return {
        "ok": True,
        "added": added,
        "latest_period": latest["period"],
        "latest_date": latest["date"],
        "history_loaded": not has_real,
        "checked": checked,
    }


def sync_status():
    return {
        "auto": True,
        "last_sync": db.get_meta("last_sync", "从未同步"),
        "last_sync_period": db.get_meta("last_sync_period", ""),
        "last_sync_date": db.get_meta("last_sync_date", ""),
        "source": db.get_meta("sync_source", "福彩官网（cwl.gov.cn）"),
        "total": db.record_count(),
        "real_total": db.count_real(),
    }
