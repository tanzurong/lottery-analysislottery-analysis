# -*- coding: utf-8 -*-
"""开奖数据网络获取（数据源：中国福彩官网公开接口）。
该接口返回公开开奖数据，无需密钥；若官方调整接口导致失效，页面保留手动导入兜底。
"""
import requests

CWL_API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Referer": "https://www.cwl.gov.cn/",
}
TIMEOUT = 25


def fetch_ssq(page_size=100):
    """从福彩官网拉取双色球开奖记录，返回列表（最新在前）：
    [{period, red:[6 个升序 int], blue:int, date:"YYYY-MM-DD"}]。
    注意：该接口不支持分页，单次最多返回约 100 期最新记录。
    失败时抛异常（由调用方处理）。
    """
    resp = requests.get(
        CWL_API,
        params={"name": "ssq", "pageNo": 1, "pageSize": page_size, "issueCount": page_size},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    result = []
    rows = data.get("result") or []
    for row in rows:
        code = row.get("code", "")
        red_raw = row.get("red", "")
        blue_raw = row.get("blue", "")
        try:
            red = sorted(int(x) for x in red_raw.split(",") if x.strip())
            blue = int(blue_raw)
        except (ValueError, TypeError):
            continue
        if len(red) != 6 or not all(1 <= n <= 33 for n in red) or not (1 <= blue <= 16):
            continue
        date = (row.get("date") or "")[:10]
        result.append({"period": str(code), "red": red, "blue": blue, "date": date})
    if not result:
        raise RuntimeError("数据源未返回有效开奖记录")
    return result
