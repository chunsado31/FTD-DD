"""Distribution Day 및 Follow-Through Day 분석 모듈"""
import json
import os
from datetime import datetime, timedelta
from config import (
    DISTRIBUTION_DROP_THRESHOLD,
    STALLING_MINOR_DROP,
    STALLING_MICRO_RISE,
    NARROW_RANGE_DROP,
    UPPER_WICK_CLOSE_THRESHOLD,
    UPPER_HALF_CLOSE_THRESHOLD,
    DISTRIBUTION_WINDOW_DAYS,
    DISTRIBUTION_CLUSTER_WINDOW,
    DISTRIBUTION_CLUSTER_COUNT,
    VERTICAL_RISE_INVALIDATION,
    FTD_MIN_RISE,
    FTD_HIGH_VOL_RISE,
    FTD_TIMING_START,
    FTD_TIMING_END,
    FTD_EARLY_DAY,
)

STATE_FILE = "market_state.json"


def load_state():
    """시장 상태 파일을 로드한다."""
    default = {
        "market_status": "confirmed_uptrend",  # confirmed_uptrend, uptrend_under_pressure, downtrend, correction
        "distribution_days": [],                # [{"date": ..., "type": ..., "close": ...}, ...]
        "rally_attempt_start": None,            # 반등 시도 시작일
        "rally_attempt_low": None,              # 반등 시도 저점
        "rally_day_count": 0,                   # 반등 시도 경과 거래일 수
        "last_analyzed_date": None,
    }
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            for k, v in default.items():
                if k not in state:
                    state[k] = v
            return state
    return default


def save_state(state):
    """시장 상태를 파일에 저장한다."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _close_position_in_range(high, low, close):
    """종가가 당일 변동폭 내 어디에 위치하는지 비율로 반환 (0=저가, 1=고가)"""
    rng = high - low
    if rng == 0:
        return 0.5
    return (close - low) / rng


def _trading_range_pct(high, low, close):
    """당일 변동폭 비율 (종가 대비)"""
    if close == 0:
        return 0
    return (high - low) / close


def _is_narrow_range(high, low, close, threshold=0.005):
    """변동폭이 좁은지 판단 (0.5% 미만)"""
    return _trading_range_pct(high, low, close) < threshold


def expire_old_distribution_days(state, records):
    """
    25거래일 경과한 분산일을 소멸시킨다.
    records: 전체 거래 데이터 (날짜순)
    """
    if not state["distribution_days"]:
        return

    all_dates = [r["date"] for r in records]
    latest_date = all_dates[-1]

    remaining = []
    expired = []
    for dd in state["distribution_days"]:
        dd_date = dd["date"]
        if dd_date in all_dates:
            dd_idx = all_dates.index(dd_date)
            latest_idx = all_dates.index(latest_date)
            trading_days_elapsed = latest_idx - dd_idx
            if trading_days_elapsed >= DISTRIBUTION_WINDOW_DAYS:
                expired.append(dd)
                continue
        remaining.append(dd)

    state["distribution_days"] = remaining
    return expired


def invalidate_by_vertical_rise(state, records):
    """6% 수직 상승으로 분산일을 무효화한다."""
    if not state["distribution_days"]:
        return []

    latest = records[-1]
    invalidated = []
    remaining = []

    for dd in state["distribution_days"]:
        dd_close = dd["close"]
        # 현재 종가 기준으로 6% 이상 상승했는지 확인
        rise_pct = (latest["close"] - dd_close) / dd_close
        if rise_pct >= VERTICAL_RISE_INVALIDATION:
            invalidated.append(dd)
        else:
            remaining.append(dd)

    state["distribution_days"] = remaining
    return invalidated


def analyze_distribution_day(today, yesterday, state):
    """
    당일 데이터가 분산일인지 분석한다.
    Returns: dict with analysis results
    """
    result = {
        "is_distribution": False,
        "distribution_type": None,  # standard, stalling, churning
        "is_excluded": False,
        "exclusion_reason": None,
        "details": [],
    }

    close_change = (today["close"] - yesterday["close"]) / yesterday["close"]
    volume_increased = today["volume"] > yesterday["volume"]
    close_position = _close_position_in_range(today["high"], today["low"], today["close"])
    narrow_range = _is_narrow_range(today["high"], today["low"], today["close"])

    result["close_change_pct"] = round(close_change * 100, 3)
    result["volume_change"] = today["volume"] - yesterday["volume"]
    result["close_position"] = round(close_position, 3)

    # ── 3. 제외 조건 먼저 체크 ──
    # 좁은 변동폭 + 미세 하락
    if narrow_range and abs(close_change) < NARROW_RANGE_DROP:
        result["is_excluded"] = True
        result["exclusion_reason"] = "좁은 변동폭 + 미세 변동 (거짓 양성)"
        result["details"].append("⬜ 변동폭이 매우 좁고 하락폭이 0.1% 이내로 분산일 제외")
        return result

    # 상위권 마감 (하락 < 0.2% + 거래량 증가 + 종가 상위 50%)
    if close_change < 0 and abs(close_change) < DISTRIBUTION_DROP_THRESHOLD and volume_increased:
        if close_position >= UPPER_HALF_CLOSE_THRESHOLD:
            result["is_excluded"] = True
            result["exclusion_reason"] = "상위권 마감 (거짓 양성)"
            result["details"].append("⬜ 종가가 당일 변동폭 상위 50%에서 마감, 분산일 제외")
            return result

    # ── 1. 기본 분산일 (Standard Distribution Day) ──
    if close_change <= -DISTRIBUTION_DROP_THRESHOLD and volume_increased:
        # 좁은 변동폭 제외 재확인
        if not narrow_range:
            result["is_distribution"] = True
            result["distribution_type"] = "standard"
            result["details"].append("🔴 기본 분산일: 종가 0.2%+ 하락 & 거래량 증가")
            return result

    # ── 2. 숨겨진 분산일 (Stalling / Churning) ──
    # 스톨링: 상승 또는 미세 하락(0.2% 미만) + 거래량 폭증
    if volume_increased and close_change > -STALLING_MINOR_DROP:
        stalling_signals = []

        # 위꼬리 마감: 종가가 하위 25% 이내
        if close_position <= UPPER_WICK_CLOSE_THRESHOLD:
            stalling_signals.append("위꼬리 마감 (종가 하위 25% 이내)")

        # 미세 상승 한계: 0.1% 이상 상승 못함 + 거래량 증가
        if close_change < STALLING_MICRO_RISE:
            stalling_signals.append("미세 상승 한계 (0.1% 이상 상승 실패)")

        if stalling_signals:
            # 보수적 카운팅: 스톨링 개수가 기존 standard 분산일 수 이내에서만 집계
            standard_count = sum(
                1 for d in state["distribution_days"] if d.get("type") == "standard"
            )
            stalling_count = sum(
                1 for d in state["distribution_days"] if d.get("type") == "stalling"
            )

            if stalling_count < standard_count or standard_count == 0:
                result["is_distribution"] = True
                result["distribution_type"] = "stalling"
                result["details"].append(
                    f"🟡 숨겨진 분산일 (스톨링): {', '.join(stalling_signals)}"
                )
            else:
                result["details"].append(
                    "⬜ 스톨링 조건 충족하나, 보수적 카운팅 규칙으로 추가 집계 제외"
                )

    if not result["is_distribution"] and not result["is_excluded"]:
        result["details"].append("✅ 분산일 아님")

    return result


def analyze_follow_through_day(today, yesterday, state, records):
    """
    팔로우스루데이 여부를 분석한다.
    Returns: dict with analysis results
    """
    result = {
        "is_ftd": False,
        "ftd_type": None,  # standard, early
        "details": [],
        "rally_day": None,
    }

    # 반등 시도 진행 중이 아니면 반등 시도 시작 여부 확인
    if state["rally_attempt_start"] is None:
        # 하락장/조정 상태에서 신저가 이후 반등 종가 확인
        if state["market_status"] in ("downtrend", "correction"):
            # 전일 대비 상승 마감 시 반등 시도 시작
            if today["close"] > yesterday["close"]:
                state["rally_attempt_start"] = today["date"]
                state["rally_attempt_low"] = min(today["low"], yesterday["low"])
                state["rally_day_count"] = 1
                result["details"].append(
                    f"📍 반등 시도 시작 (1일차): 저점 {state['rally_attempt_low']}"
                )
            # 장중 신저가 찍었지만 종가가 변동폭 중간 이상이면 반등 시도 인정
            elif today["low"] < yesterday["low"]:
                mid = (today["high"] + today["low"]) / 2
                if today["close"] >= mid:
                    state["rally_attempt_start"] = today["date"]
                    state["rally_attempt_low"] = today["low"]
                    state["rally_day_count"] = 1
                    result["details"].append(
                        f"📍 반등 시도 시작 (1일차, 장중저가+지지마감): 저점 {state['rally_attempt_low']}"
                    )
        return result

    # 반등 시도 진행 중: 신저가 갱신 시 리셋
    if state["rally_attempt_low"] and today["close"] < state["rally_attempt_low"]:
        state["rally_attempt_start"] = None
        state["rally_attempt_low"] = None
        state["rally_day_count"] = 0
        result["details"].append("❌ 반등 시도 실패: 신저가 갱신으로 리셋")
        return result

    # 반등 경과일수 계산
    all_dates = [r["date"] for r in records]
    if state["rally_attempt_start"] in all_dates:
        start_idx = all_dates.index(state["rally_attempt_start"])
        today_idx = all_dates.index(today["date"])
        state["rally_day_count"] = today_idx - start_idx + 1
    else:
        state["rally_day_count"] += 1

    rally_day = state["rally_day_count"]
    result["rally_day"] = rally_day

    # FTD 조건 체크
    close_change = (today["close"] - yesterday["close"]) / yesterday["close"]
    volume_increased = today["volume"] > yesterday["volume"]

    # 변동성 기반 기준값 결정 (최근 20거래일 변동성 확인)
    threshold = FTD_MIN_RISE
    if len(records) >= 20:
        recent_20 = records[-20:]
        daily_ranges = [abs(r["high"] - r["low"]) / r["close"] for r in recent_20]
        avg_range = sum(daily_ranges) / len(daily_ranges)
        if avg_range > 0.02:  # 평균 일일 변동폭 2% 초과 시
            threshold = FTD_HIGH_VOL_RISE
            result["details"].append(
                f"📊 변동성 확대 감지: FTD 기준값 {threshold*100:.1f}%로 상향"
            )

    # 3일차 조기 인정
    if rally_day == FTD_EARLY_DAY:
        if close_change >= threshold and volume_increased:
            result["is_ftd"] = True
            result["ftd_type"] = "early"
            result["details"].append(
                f"⚡ 조기 FTD (3일차): +{close_change*100:.2f}% & 거래량 증가"
            )
            return result

    # 4~7일차 표준 FTD
    if FTD_TIMING_START <= rally_day <= FTD_TIMING_END:
        if close_change >= threshold and volume_increased:
            result["is_ftd"] = True
            result["ftd_type"] = "standard"
            result["details"].append(
                f"🟢 팔로우스루데이 ({rally_day}일차): +{close_change*100:.2f}% & 거래량 증가"
            )
            return result

    if rally_day > FTD_TIMING_END:
        result["details"].append(f"⏰ 반등 시도 {rally_day}일차: FTD 타이밍 창 초과")

    return result


def update_market_status(state, dd_result, ftd_result, records):
    """분석 결과에 따라 시장 상태를 업데이트한다."""
    status_changed = False
    prev_status = state["market_status"]

    # FTD 발생 시 → 확인된 상승장 + 분산일 초기화
    if ftd_result["is_ftd"]:
        state["market_status"] = "confirmed_uptrend"
        state["distribution_days"] = []
        state["rally_attempt_start"] = None
        state["rally_attempt_low"] = None
        state["rally_day_count"] = 0
        status_changed = True

    # 분산일 추가
    if dd_result["is_distribution"] and not dd_result["is_excluded"]:
        today = records[-1]
        state["distribution_days"].append({
            "date": today["date"],
            "type": dd_result["distribution_type"],
            "close": today["close"],
        })

    # 최근 20거래일 내 분산일 군집 확인
    all_dates = [r["date"] for r in records]
    latest_idx = len(all_dates) - 1
    recent_dd_count = 0
    for dd in state["distribution_days"]:
        if dd["date"] in all_dates:
            dd_idx = all_dates.index(dd["date"])
            if latest_idx - dd_idx <= DISTRIBUTION_CLUSTER_WINDOW:
                recent_dd_count += 1

    if recent_dd_count >= DISTRIBUTION_CLUSTER_COUNT:
        if state["market_status"] == "confirmed_uptrend":
            state["market_status"] = "uptrend_under_pressure"
            status_changed = True

    # 50일 이동평균선 하향 돌파 체크 (대량거래 동반)
    if len(records) >= 50 and state["market_status"] == "uptrend_under_pressure":
        ma50 = sum(r["close"] for r in records[-50:]) / 50
        today = records[-1]
        yesterday = records[-2]
        if today["close"] < ma50 and yesterday["close"] >= ma50:
            if today["volume"] > yesterday["volume"]:
                state["market_status"] = "downtrend"
                status_changed = True

    return status_changed, prev_status


def generate_report(today, yesterday, dd_result, ftd_result, state, expired_dds, invalidated_dds):
    """텔레그램 전송용 분석 리포트를 생성한다."""
    close_change_pct = dd_result.get("close_change_pct", 0)
    vol_change = dd_result.get("volume_change", 0)
    vol_dir = "📈" if vol_change > 0 else "📉"

    status_emoji = {
        "confirmed_uptrend": "🟢 확인된 상승장",
        "uptrend_under_pressure": "🟡 압박받는 상승장",
        "downtrend": "🔴 하락장",
        "correction": "🟠 조정 국면",
    }

    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 나스닥 FTD/DD 일일 분석")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # 시세 요약
    lines.append(f"📅 분석일: {today['date']}")
    lines.append(f"  시가: {today['open']:,.2f}")
    lines.append(f"  고가: {today['high']:,.2f}")
    lines.append(f"  저가: {today['low']:,.2f}")
    lines.append(f"  종가: {today['close']:,.2f} ({close_change_pct:+.3f}%)")
    lines.append(f"  거래량: {today['volume']:,} {vol_dir} ({vol_change:+,})")
    lines.append("")

    lines.append(f"📅 전일: {yesterday['date']}")
    lines.append(f"  종가: {yesterday['close']:,.2f}  거래량: {yesterday['volume']:,}")
    lines.append("")

    # 분산일 분석
    lines.append("── Distribution Day 분석 ──")
    for detail in dd_result["details"]:
        lines.append(f"  {detail}")
    if dd_result["is_distribution"]:
        lines.append(f"  ▶ 유형: {dd_result['distribution_type']}")
    if dd_result["is_excluded"]:
        lines.append(f"  ▶ 제외 사유: {dd_result['exclusion_reason']}")
    lines.append("")

    # 소멸/무효화된 분산일
    if expired_dds:
        lines.append("♻️ 소멸된 분산일 (25거래일 경과):")
        for d in expired_dds:
            lines.append(f"  - {d['date']} ({d['type']})")
        lines.append("")

    if invalidated_dds:
        lines.append("♻️ 무효화된 분산일 (6%+ 상승):")
        for d in invalidated_dds:
            lines.append(f"  - {d['date']} ({d['type']})")
        lines.append("")

    # FTD 분석
    lines.append("── Follow-Through Day 분석 ──")
    for detail in ftd_result["details"]:
        lines.append(f"  {detail}")
    if ftd_result["rally_day"]:
        lines.append(f"  ▶ 반등 시도 {ftd_result['rally_day']}일차")
    lines.append("")

    # 시장 상태
    lines.append("── 시장 상태 ──")
    ms = state["market_status"]
    lines.append(f"  {status_emoji.get(ms, ms)}")
    active_dd = len(state["distribution_days"])
    lines.append(f"  누적 분산일: {active_dd}개")
    if state["distribution_days"]:
        for dd in state["distribution_days"]:
            lines.append(f"    - {dd['date']} ({dd['type']}, 종가 {dd['close']:,.2f})")
    if state["rally_attempt_start"]:
        lines.append(f"  반등 시도 시작: {state['rally_attempt_start']} ({state['rally_day_count']}일차)")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)
