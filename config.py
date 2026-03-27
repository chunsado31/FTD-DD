"""설정 모듈"""
import os

# Telegram 설정
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Yahoo Finance API
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EIXIC"

# 분산일 판정 기준값
DISTRIBUTION_DROP_THRESHOLD = 0.002       # 0.2% 하락
STALLING_MINOR_DROP = 0.002               # 0.2% 미만 하락 (스톨링 상한)
STALLING_MICRO_RISE = 0.001               # 0.1% 미세 상승 한계
NARROW_RANGE_DROP = 0.001                 # 0.1% 이내 미세 하락
UPPER_WICK_CLOSE_THRESHOLD = 0.25         # 하위 25% 이내 마감
UPPER_HALF_CLOSE_THRESHOLD = 0.50         # 상위 50% 이내 마감

# 분산일 누적 기준
DISTRIBUTION_WINDOW_DAYS = 25             # 분산일 소멸 거래일 수
DISTRIBUTION_CLUSTER_WINDOW = 20          # 군집 판단 거래일 수 (4~5주)
DISTRIBUTION_CLUSTER_COUNT = 4            # 군집 경고 임계치
VERTICAL_RISE_INVALIDATION = 0.06         # 6% 수직 상승 무효화

# FTD 기준값
FTD_MIN_RISE = 0.01                       # 1% 기본 상승률
FTD_HIGH_VOL_RISE = 0.017                 # 1.7% 변동성 확대 시
FTD_TIMING_START = 4                      # 반등 시도 후 4일차부터
FTD_TIMING_END = 7                        # 7일차까지
FTD_EARLY_DAY = 3                         # 조기 인정 3일차

# 데이터 범위
YAHOO_RANGE = "3mo"                       # 3개월치 데이터 (이동평균 등 계산용)
YAHOO_INTERVAL = "1d"
