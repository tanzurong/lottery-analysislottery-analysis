# -*- coding: utf-8 -*-
"""双色球娱乐分析工作台 —— Flask 入口。
REST API + 托管前端静态页面。部署见 README.md（Docker / NAS）。
"""
import os

from flask import Flask, jsonify, request, send_from_directory

import analysis
import db
import fetcher  # noqa: F401（保持导入，便于排查）
import sync
from demo_data import DEMO_RAW, parse_raw

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=None)
app.config["JSON_AS_ASCII"] = False

# 模块级初始化：gunicorn 直接 import 时也会执行（首次启动写入演示数据）
db.init_db()
if db.record_count() == 0:
    db.upsert_records(parse_raw(DEMO_RAW), demo=True)


def records():
    return db.load_records()


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    """托管 static/ 目录下的静态资源（echarts.min.js 等，本地化不依赖外网 CDN）。"""
    return send_from_directory(STATIC_DIR, filename)


# ---------- 基础数据 ----------
@app.get("/api/overview")
def api_overview():
    win = _win_param()
    return jsonify(analysis.overview_payload(records(), win))


@app.get("/api/history")
def api_history():
    recs = records()
    win = _win_param()
    w = analysis.window(recs, win)
    limit = request.args.get("limit", type=int) or len(w)
    data = [{
        "period": r["period"],
        "red": r["red"],
        "blue": r["blue"],
        "sum": analysis.red_sum(r),
        "odd": f"{analysis.odd_count(r)}:{6 - analysis.odd_count(r)}",
        "big": f"{analysis.big_count(r)}:{6 - analysis.big_count(r)}",
        "demo": r["demo"],
    } for r in w[:limit]]
    return jsonify({"total": len(recs), "win": len(w), "rows": data})


@app.post("/api/import")
def api_import():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "")
    parsed = parse_raw(text.splitlines())
    if not parsed:
        return jsonify({"ok": False, "msg": "未解析到有效数据：每行格式为「期号 红1…红6 蓝」。"}), 400
    added = db.upsert_records(parsed)
    total = db.record_count()
    return jsonify({"ok": True, "added": added, "total": total,
                    "msg": f"导入成功 {added} 条，当前共 {total} 期。"})


@app.post("/api/reset")
def api_reset():
    db.clear_records()
    db.upsert_records(parse_raw(DEMO_RAW), demo=True)
    return jsonify({"ok": True, "msg": "已重置为内置演示数据。"})


@app.post("/api/clear")
def api_clear():
    db.clear_records()
    return jsonify({"ok": True, "msg": "已清空全部开奖数据。"})


# ---------- 统计 / 走势 ----------
@app.get("/api/stats")
def api_stats():
    win = _win_param()
    w = analysis.window(records(), win)
    return jsonify({**analysis.stats_payload(w), "win": len(w)})


@app.get("/api/sums")
def api_sums():
    win = _win_param()
    w = analysis.window(records(), win)
    series = analysis.sum_series(w)
    avg = round(sum(x["sum"] for x in series) / len(series)) if series else 0
    return jsonify({"win": len(w), "avg": avg, "series": series})


# ---------- 推荐 ----------
@app.post("/api/recommend")
def api_recommend():
    body = request.get_json(silent=True) or {}
    strategy = body.get("strategy", "hot")
    if strategy not in ("hot", "cold", "mix", "multi", "pair"):
        strategy = "hot"
    count = max(1, min(20, int(body.get("count", 5))))
    win = int(body.get("win") or 0) or 100
    sets = analysis.recommend(records(), win, strategy, count)
    return jsonify({"sets": sets, "strategy": strategy})


@app.get("/api/pairs")
def api_pairs():
    """热搭档 Top10（共现提升度）。"""
    win = int(request.args.get("win") or 0) or 100
    w = analysis.window(records(), win)
    return jsonify({"top": analysis.top_pairs(w, 10)})


@app.post("/api/wheel")
def api_wheel():
    """胆拖旋转矩阵：用户选 8~12 个红球，生成覆盖注单。"""
    body = request.get_json(silent=True) or {}
    try:
        reds = [int(x) for x in body.get("reds", [])]
        blue = int(body.get("blue", 0))
        if not (1 <= blue <= 16):
            return jsonify({"ok": False, "msg": "请选择 1 个蓝球（1-16）。"}), 400
        result = analysis.wheel_cover(reds, 5)
        sets = [{"red": list(b), "blue": blue} for b in result["bets"]]
        return jsonify({"ok": True, "sets": sets, "count": result["count"], "note": result["note"]})
    except ValueError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "msg": f"生成失败：{e}"}), 500


# ---------- 我的推荐 / 中奖核对 ----------
@app.post("/api/picks")
def api_add_pick():
    body = request.get_json(silent=True) or {}
    strategy = body.get("strategy", "hot")
    sets = body.get("sets", [])
    if not sets:
        return jsonify({"ok": False, "msg": "缺少号码组。"}), 400
    base = body.get("base_period")
    if not base:
        recs = records()
        base = recs[0]["period"] if recs else ""
    pid = db.add_pick(strategy, base, sets)
    return jsonify({"ok": True, "id": pid, "base_period": base})


@app.get("/api/picks")
def api_list_picks():
    return jsonify({"picks": db.list_picks()})


@app.delete("/api/picks/<int:pid>")
def api_delete_pick(pid):
    db.delete_pick(pid)
    return jsonify({"ok": True})


@app.post("/api/picks/check")
def api_check_picks():
    recs = records()
    checked_any = False
    summary = []
    for pick in db.list_picks():
        if pick["checked"]:
            continue
        result = analysis.check_pick(recs, pick)
        if result is None:
            continue
        db.update_pick_checked(pick["id"], result)
        checked_any = True
        summary.append({"id": pick["id"], "draw_period": result["draw_period"],
                        "won": any(r["won"] for r in result["results"])})
    return jsonify({"ok": True, "checked": checked_any, "summary": summary})


@app.get("/api/sync/status")
def api_sync_status():
    return jsonify(sync.sync_status())


@app.post("/api/sync")
def api_sync():
    try:
        result = sync.sync_now()
        return jsonify(result)
    except Exception as exc:
        return jsonify({"ok": False, "msg": f"同步失败：{exc}"}), 502


def _win_param():
    return request.args.get("win", type=int) or 0


def _start_background():
    """启动定时任务与首次同步（AUTO_SYNC=0 可关闭，便于测试）。"""
    if os.environ.get("AUTO_SYNC", "1") == "0":
        return
    from scheduler import start_scheduler
    start_scheduler()


# 模块级初始化：gunicorn 直接 import 时也会执行（首次启动写入演示数据）
db.init_db()
if db.record_count() == 0:
    db.upsert_records(parse_raw(DEMO_RAW), demo=True)

# 每日自动同步开奖数据 + 自动核对推荐（可用环境变量 AUTO_SYNC=0 关闭）
_start_background()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
