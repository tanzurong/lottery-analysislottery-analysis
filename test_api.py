# -*- coding: utf-8 -*-
"""API 自动化验证脚本：使用独立临时数据目录，不污染正式数据。
运行：python test_api.py
"""
import json
import os
import tempfile

tmp = tempfile.mkdtemp(prefix="lottery_test_")
os.environ["DATA_DIR"] = tmp
os.environ["AUTO_SYNC"] = "0"  # 测试时不启动定时任务/首次网络同步

import app as APP  # noqa: E402


def t(client, method, path, body=None):
    if method == "GET":
        r = client.get(path)
    elif method == "POST":
        r = client.post(path, json=body or {})
    else:
        r = client.delete(path)
    return r.status_code, r.get_json(silent=True)


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if detail else ""))
    if not cond:
        raise SystemExit(1)


def main():
    c = APP.app.test_client()

    r = c.get("/")
    check("GET / 首页", r.status_code == 200 and "开奖工作台" in r.get_data(as_text=True))

    code, ov = t(c, "GET", "/api/overview")
    check("overview 初始 60 期", code == 200 and ov["total"] == 60, f"total={ov['total']}")
    check("overview 最新期", ov["latest"]["period"] == "2025050", ov["latest"]["period"])

    code, h = t(c, "GET", "/api/history?win=30")
    check("history 窗口 30", code == 200 and h["win"] == 30 and len(h["rows"]) == 30)

    code, st = t(c, "GET", "/api/stats?win=100")
    check("stats 频次长度", code == 200 and len(st["freq_red"]) == 33 and len(st["freq_blue"]) == 16)

    code, sm = t(c, "GET", "/api/sums")
    check("sums 序列", code == 200 and len(sm["series"]) == 60 and sm["avg"] > 0)

    code, rec = t(c, "POST", "/api/recommend", {"strategy": "mix", "count": 3, "win": 100})
    sets = rec.get("sets", [])
    valid = all(len(s["red"]) == 6 and len(set(s["red"])) == 6
                and all(1 <= n <= 33 for n in s["red"]) and 1 <= s["blue"] <= 16
                for s in sets)
    check("recommend mix 生成 3 组合法", code == 200 and len(sets) == 3 and valid, f"n={len(sets)}")

    code, rec2 = t(c, "POST", "/api/recommend", {"strategy": "cold", "count": 1, "win": 30})
    check("recommend cold", code == 200 and len(rec2["sets"]) == 1)

    # 保存推荐
    code, pk = t(c, "POST", "/api/picks", {"strategy": "mix", "base_period": "2025050", "sets": sets})
    check("保存推荐", code == 200 and pk["ok"])
    pid = pk["id"]

    # 导入更新的一期（2025091 在保存之后）
    code, imp = t(c, "POST", "/api/import", {"text": "2025091 02 08 14 19 25 33 07\n2025092,01,05,11,20,26,32,15"})
    check("导入新增 2 期", code == 200 and imp["added"] == 2, imp.get("msg", ""))
    code, imp2 = t(c, "POST", "/api/import", {"text": "2025091 02 08 14 19 25 33 07"})
    check("重复期号去重", code == 200 and imp2["added"] == 0)

    # 中奖核对：保存基准 2025050 之后最早一期 = 2025091（02 08 14 19 25 33 | 07）
    code, ck = t(c, "POST", "/api/picks/check")
    check("核对执行", code == 200 and ck["checked"])

    code, picks = t(c, "GET", "/api/picks")
    p0 = picks["picks"][0]
    check("核对结果持久化", p0["checked"] is not None and p0["checked"]["draw_period"] == "2025091",
          f"draw={p0['checked']['draw_period'] if p0['checked'] else None}")
    # 手工构造一个必然 6+1 的组验证奖级：2025091 开奖号 02 08 14 19 25 33 + 07
    exact = {"strategy": "hot", "base_period": "2025050",
             "sets": [{"red": [2, 8, 14, 19, 25, 33], "blue": 7}]}
    code, e = t(c, "POST", "/api/picks", exact)
    code, ck2 = t(c, "POST", "/api/picks/check")
    code, picks2 = t(c, "GET", "/api/picks")
    r0 = picks2["picks"][0]["checked"]["results"][0]
    check("6+1 一等奖识别", r0["level"] == "一等奖" and r0["won"], json.dumps(r0, ensure_ascii=False))

    # 删除
    code, d = t(c, "DELETE", f"/api/picks/{pid}")
    check("删除推荐", code == 200 and d["ok"])

    # 重置
    code, rst = t(c, "POST", "/api/reset")
    code, ov2 = t(c, "GET", "/api/overview")
    check("重置回演示数据", rst["ok"] and ov2["total"] == 60)

    print("\n全部 API 验证通过 ✅")


if __name__ == "__main__":
    main()
