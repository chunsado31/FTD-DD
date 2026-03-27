"""Yahoo Finance에서 나스닥 지수 데이터를 가져오는 모듈"""
import requests
from datetime import datetime, timezone
from config import YAHOO_CHART_URL, YAHOO_RANGE, YAHOO_INTERVAL


def fetch_nasdaq_data():
    """
    Yahoo Finance 비공식 API를 통해 나스닥 종합지수(^IXIC) 데이터를 가져온다.
    Returns: list of dict (날짜순 정렬, 각 항목에 date, open, high, low, close, volume 포함)
    """
    params = {
        "interval": YAHOO_INTERVAL,
        "range": YAHOO_RANGE,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    resp = requests.get(YAHOO_CHART_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    records = []
    for i, ts in enumerate(timestamps):
        o = quote["open"][i]
        h = quote["high"][i]
        l = quote["low"][i]
        c = quote["close"][i]
        v = quote["volume"][i]
        # null 데이터 건너뛰기
        if any(x is None for x in [o, h, l, c, v]):
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        records.append({
            "date": dt,
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": int(v),
        })

    return records


def get_recent_days(records, n=2):
    """최근 n거래일 데이터를 반환한다. records[-n:]"""
    if len(records) < n:
        raise ValueError(f"데이터가 {n}거래일 미만입니다.")
    return records[-n:]
