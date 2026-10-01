# -*- coding: utf-8 -*-
"""统计分析、加权随机推荐、双色球中奖级别核对。"""
import random
from itertools import combinations

RED_MAX = 33
BLUE_MAX = 16

# 双色球固定奖金对照：(红球命中数, 蓝球命中数, 奖级, 奖金)
# 一等奖/二等奖为浮动奖金，固定部分标注 None
PRIZE_TABLE = [
    (6, 1, "一等奖", None),
    (6, 0, "二等奖", None),
    (5, 1, "三等奖", 3000),
    (5, 0, "四等奖", 200),
    (4, 1, "四等奖", 200),
    (4, 0, "五等奖", 10),
    (3, 1, "五等奖", 10),
    (2, 1, "六等奖", 5),
    (1, 1, "六等奖", 5),
    (0, 1, "六等奖", 5),
]


# ---------- 统计 ----------
def window(records, win):
    if win and win > 0 and win < len(records):
        return records[:win]
    return records


def freq_of(records, max_n, blue=False):
    f = [0] * (max_n + 1)
    for r in records:
        if blue:
            f[r["blue"]] += 1
        else:
            for n in r["red"]:
                f[n] += 1
    return f


def miss_of(records, max_n, blue=False):
    m = [0] * (max_n + 1)
    for i in range(1, max_n + 1):
        for idx, r in enumerate(records):  # records 最新在前
            hit = r["blue"] == i if blue else i in r["red"]
            if hit:
                m[i] = idx
                break
        else:
            m[i] = len(records)
    return m


def red_sum(r):
    return sum(r["red"])


def odd_count(r):
    return sum(1 for n in r["red"] if n % 2 == 1)


def big_count(r):
    return sum(1 for n in r["red"] if n >= 17)


def stats_payload(records):
    f_red = freq_of(records, RED_MAX)
    f_blue = freq_of(records, BLUE_MAX, True)
    m_red = miss_of(records, RED_MAX)
    m_blue = miss_of(records, BLUE_MAX, True)
    return {
        "freq_red": f_red[1:],
        "freq_blue": f_blue[1:],
        "miss_red": m_red[1:],
        "miss_blue": m_blue[1:],
    }


def sum_series(records):
    rev = list(reversed(records))
    return [{"period": r["period"], "sum": red_sum(r)} for r in rev]


def overview_payload(records, win):
    w = window(records, win)
    st = stats_payload(w)
    sums = [red_sum(r) for r in records[:20]]
    avg = round(sum(sums) / len(sums)) if sums else 0
    hot_r = max(range(1, RED_MAX + 1), key=lambda i: st["freq_red"][i - 1])
    hot_b = max(range(1, BLUE_MAX + 1), key=lambda i: st["freq_blue"][i - 1])
    max_miss = max(st["miss_red"] + st["miss_blue"])
    latest = records[0] if records else None
    return {
        "total": len(records),
        "win": len(w),
        "avg_sum_20": avg,
        "hot_red": hot_r,
        "hot_red_freq": st["freq_red"][hot_r - 1],
        "hot_blue": hot_b,
        "hot_blue_freq": st["freq_blue"][hot_b - 1],
        "max_miss": max_miss,
        "latest": latest,
    }


# ---------- 推荐（加权随机，娱乐向） ----------
def recommend(records, win, strategy, count):
    w = window(records, win)
    f_red = freq_of(w, RED_MAX)
    m_red = miss_of(w, RED_MAX)
    f_blue = freq_of(w, BLUE_MAX, True)

    # ---- 新策略：multi 多因子 / pair 搭档偏好 ----
    if strategy in ("multi", "pair"):
        scores = multi_scores(w, win)
        M = co_matrix(w) if strategy == "pair" else None
        results = []
        guard = 0
        while len(results) < count and guard < count * 400:
            guard += 1
            red = _pick_many(scores, 6)
            red.sort()
            if not combo_ok(red):
                continue
            if M is not None:
                bonus = _combo_pair_bonus(red, M)
                # 搭档偏好：低于均值偏多的组合直接淘汰一轮再选
                if bonus < 0.6 and random.random() < 0.7:
                    continue
            blue = _weighted_pick(list(range(1, BLUE_MAX + 1)), [f_blue[i] + 1 for i in range(1, BLUE_MAX + 1)])
            blue = blue if blue is not None else random.randint(1, BLUE_MAX)
            results.append({"red": red, "blue": blue})
        return results

    # ---- 旧策略 ----
    weight = [1] * (RED_MAX + 1)
    if strategy == "hot":
        for i in range(1, RED_MAX + 1):
            weight[i] = pow(f_red[i], 1.4) + 1
    elif strategy == "cold":
        for i in range(1, RED_MAX + 1):
            weight[i] = m_red[i] + 1
    else:  # mix 均衡组合
        th_hot = max(2, round(len(w) * 6 / RED_MAX * 1.6))
        th_cold = max(3, round(len(w) / 2))
        for i in range(1, RED_MAX + 1):
            if f_red[i] >= th_hot:
                weight[i] = 4
            elif m_red[i] >= th_cold:
                weight[i] = 3
            else:
                weight[i] = 1

    results = []
    guard = 0
    while len(results) < count and guard < count * 80:
        guard += 1
        red = None
        if strategy == "mix":
            red = _pick_mix(weight)
            if red is None:
                continue
        else:
            red = _pick_many(weight, 6)
        red.sort()
        blue = _weighted_pick(list(range(1, BLUE_MAX + 1)), [f_blue[i] + 1 for i in range(1, BLUE_MAX + 1)])
        blue = blue if blue is not None else random.randint(1, BLUE_MAX)
        results.append({"red": red, "blue": blue})
    return results


def _weighted_pick(pool, w):
    total = sum(w)
    if total <= 0:
        return None
    r = random.random() * total
    for i, p in enumerate(pool):
        r -= w[i]
        if r < 0:
            return p
    return pool[-1]


def _pick_many(weight, k):
    pool = list(range(1, RED_MAX + 1))
    w = [weight[i] for i in pool]
    out = []
    while len(out) < k and pool:
        total = sum(w)
        r = random.random() * total
        idx = 0
        for i in range(len(pool)):
            r -= w[i]
            if r < 0:
                idx = i
                break
        else:
            idx = len(pool) - 1
        out.append(pool[idx])
        pool.pop(idx)
        w.pop(idx)
    return out


def _pick_mix(weight):
    red = []
    pool = list(range(1, RED_MAX + 1))
    for k in range(6):
        candidates = [n for n in pool if n not in red]
        if k == 5:
            odd_n = sum(1 for n in red if n % 2)
            big_n = sum(1 for n in red if n >= 17)
            candidates = [n for n in candidates
                          if abs((odd_n + n % 2) - 3) <= 1 and abs((big_n + (n >= 17)) - 3) <= 1]
        if not candidates:
            return None
        w = [weight[n] for n in candidates]
        p = _weighted_pick(candidates, w)
        if p is None:
            return None
        red.append(p)
    s = sum(red)
    if s < 60 or s > 140:
        return None
    return red


# ---------- 进阶：组合质量约束 ----------
def ac_value(red):
    """AC 值：不同差值个数 - (r-1)，衡量号码离散复杂度。"""
    diffs = set()
    for i in range(len(red)):
        for j in range(i + 1, len(red)):
            diffs.add(abs(red[i] - red[j]))
    return len(diffs) - (len(red) - 1)


def combo_ok(red):
    """组合形态过滤：和值、奇偶、大小、AC 值。"""
    s = sum(red)
    if not (60 <= s <= 140):
        return False
    odd = sum(1 for n in red if n % 2)
    if not (2 <= odd <= 4):
        return False
    big = sum(1 for n in red if n >= 17)
    if not (2 <= big <= 4):
        return False
    if ac_value(red) < 5:
        return False
    return True


# ---------- 进阶：共现搭档矩阵 ----------
def co_matrix(records):
    """33×33 共现次数矩阵（索引 1..33）。"""
    M = [[0] * (RED_MAX + 1) for _ in range(RED_MAX + 1)]
    for r in records:
        red = sorted(r["red"])
        for i in range(len(red)):
            for j in range(i + 1, len(red)):
                a, b = red[i], red[j]
                M[a][b] += 1
                M[b][a] += 1
    return M


def top_pairs(records, topn=10):
    """返回共现提升度 lift 最高的红球搭档对：
    lift = 共现次数 × 期数 / (freq_a × freq_b)，>1 表示搭档强于随机期望。"""
    M = co_matrix(records)
    f = freq_of(records, RED_MAX)
    N = max(1, len(records))
    out = []
    for a in range(1, RED_MAX + 1):
        for b in range(a + 1, RED_MAX + 1):
            c = M[a][b]
            if c == 0 or f[a] == 0 or f[b] == 0:
                continue
            lift = c * N / (f[a] * f[b])
            out.append({"a": a, "b": b, "count": c, "lift": round(lift, 2)})
    out.sort(key=lambda x: (-x["lift"], -x["count"]))
    return out[:topn]


# ---------- 进阶：多因子评分 ----------
def multi_scores(records, win):
    """每号综合分（0..1）：热度 0.35 + 遗漏回补 0.25 + 动量 0.20 + 共现倾向 0.20（以热度近似）。"""
    w = window(records, win)
    f = freq_of(w, RED_MAX)
    m = miss_of(w, RED_MAX)
    f10 = freq_of(w[:10], RED_MAX)
    N = max(1, len(w))

    def norm(vals):
        lo, hi = min(vals[1:]), max(vals[1:])
        return [0.5] + [((v - lo) / (hi - lo)) if hi > lo else 0.5 for v in vals[1:]]

    heat = norm(f)
    miss_ratio = [0.5] * (RED_MAX + 1)
    for i in range(1, RED_MAX + 1):
        if f[i] > 0:
            exp = N / f[i]
            miss_ratio[i] = min(1.0, m[i] / exp if exp > 0 else 0.5)
        else:
            miss_ratio[i] = 1.0
    mom = [0.0] * (RED_MAX + 1)
    for i in range(1, RED_MAX + 1):
        base = f[i] / N * 10
        mom[i] = min(1.0, max(0.0, (f10[i] - base) / max(1.0, base)))
    scores = [0.0] * (RED_MAX + 1)
    for i in range(1, RED_MAX + 1):
        scores[i] = round(0.35 * heat[i] + 0.25 * miss_ratio[i] + 0.20 * mom[i] + 0.20 * heat[i], 4)
    return scores


def _combo_pair_bonus(red, M):
    """组合内配对的平均共现次数（搭档偏好分）。"""
    total = 0
    for i in range(len(red)):
        for j in range(i + 1, len(red)):
            total += M[red[i]][red[j]]
    return total / 15.0  # C(6,2)=15


# ---------- 胆拖旋转矩阵（覆盖设计） ----------
def wheel_cover(reds, cover_k=5):
    """贪心集合覆盖：从用户胆码 reds 中生成最少注单，
    保证「胆码中 cover_k 个红球时，至少有一注命中 cover_k 个」。
    返回注单列表。胆码数需在 8~12。"""
    reds = sorted(set(int(x) for x in reds))
    if not (8 <= len(reds) <= 12):
        raise ValueError("请选择 8~12 个红球胆码")
    bets = list(combinations(reds, 6))
    uncovered = set(combinations(reds, cover_k))
    chosen = []
    while uncovered:
        best, best_cov = None, set()
        for bet in bets:
            cov = set(combinations(bet, cover_k)) & uncovered
            if len(cov) > len(best_cov):
                best, best_cov = bet, cov
        if best is None or not best_cov:
            break
        chosen.append(list(best))
        uncovered -= best_cov
    return {
        "bets": [list(b) for b in chosen],
        "count": len(chosen),
        "cover_k": cover_k,
        "note": f"胆码 {len(reds)} 个 · 共 {len(chosen)} 注 · 保证：胆码中 {cover_k} 红时至少一注中 {cover_k} 红",
    }


# ---------- 中奖核对 ----------
def check_one(red, blue, draw_red, draw_blue):
    hit = len(set(red) & set(draw_red))
    blue_hit = (blue == draw_blue)
    for (r, b, level, prize) in PRIZE_TABLE:
        if hit == r and blue_hit == b:
            return {
                "hit_red": hit,
                "hit_blue": blue_hit,
                "level": level,
                "prize": prize,
                "won": True,
            }
    return {"hit_red": hit, "hit_blue": blue_hit, "level": None, "prize": 0, "won": False}


def find_draw_after(records, base_period):
    """找到 base_period 之后最早的一期开奖（records 最新在前）。"""
    cand = [r for r in records if r["period"] > base_period]
    if not cand:
        return None
    return min(cand, key=lambda r: r["period"])


def check_pick(records, pick):
    """核对一个推荐批次：返回 {draw, results:[...]} 或 None（暂无可核对开奖）。"""
    draw = find_draw_after(records, pick["base_period"])
    if draw is None:
        return None
    results = [check_one(s["red"], s["blue"], draw["red"], draw["blue"]) for s in pick["sets"]]
    return {"draw_period": draw["period"], "draw": draw, "results": results}
