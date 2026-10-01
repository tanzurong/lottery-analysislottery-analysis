# -*- coding: utf-8 -*-
"""SQLite 数据层：开奖记录 + 我的推荐（推荐批次）持久化。"""
import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_DIR, "lottery.db")


def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS records (
            period TEXT PRIMARY KEY,
            red TEXT NOT NULL,
            blue INTEGER NOT NULL,
            demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            base_period TEXT,
            sets TEXT NOT NULL,
            checked TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()
    conn.close()


# ---------- 元信息 ----------
def set_meta(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def get_meta(key, default=""):
    conn = get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def count_real():
    """非演示（网络同步/导入）数据条数。"""
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM records WHERE demo=0").fetchone()["c"]
    conn.close()
    return n


def delete_demo():
    """删除全部演示数据（网络同步成功后调用，保证统计窗口纯真实）。"""
    conn = get_conn()
    conn.execute("DELETE FROM records WHERE demo=1")
    conn.commit()
    conn.close()


# ---------- 开奖记录 ----------
def load_records():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM records ORDER BY period DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "period": r["period"],
            "red": json.loads(r["red"]),
            "blue": r["blue"],
            "demo": bool(r["demo"]),
        })
    return out


def record_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM records").fetchone()["c"]
    conn.close()
    return n


def upsert_records(records, demo=False):
    conn = get_conn()
    added = 0
    for rec in records:
        cur = conn.execute("SELECT 1 FROM records WHERE period=?", (rec["period"],))
        if cur.fetchone():
            continue
        conn.execute(
            "INSERT INTO records(period, red, blue, demo) VALUES(?,?,?,?)",
            (rec["period"], json.dumps(rec["red"]), rec["blue"], 1 if demo else 0),
        )
        added += 1
    conn.commit()
    conn.close()
    return added


def clear_records():
    conn = get_conn()
    conn.execute("DELETE FROM records")
    conn.commit()
    conn.close()


# ---------- 我的推荐 ----------
def add_pick(strategy, base_period, sets):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO picks(strategy, base_period, sets) VALUES(?,?,?)",
        (strategy, base_period, json.dumps(sets)),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def list_picks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM picks ORDER BY id DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "strategy": r["strategy"],
            "base_period": r["base_period"],
            "sets": json.loads(r["sets"]),
            "checked": json.loads(r["checked"]) if r["checked"] else None,
            "created_at": r["created_at"],
        })
    return out


def update_pick_checked(pid, checked):
    conn = get_conn()
    conn.execute("UPDATE picks SET checked=? WHERE id=?", (json.dumps(checked), pid))
    conn.commit()
    conn.close()


def delete_pick(pid):
    conn = get_conn()
    conn.execute("DELETE FROM picks WHERE id=?", (pid,))
    conn.commit()
    conn.close()
