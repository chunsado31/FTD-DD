"""
나스닥 Distribution Day / Follow-Through Day 분석 및 텔레그램 알림

사용법:
  1. .env 파일에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 설정
  2. pip install -r requirements.txt
  3. python main.py          # 즉시 1회 실행
  4. python main.py --schedule  # 매일 KST 오전 9시 스케줄 실행
"""
import argparse
import time
import schedule
import pytz
from datetime import datetime

from data_fetcher import fetch_nasdaq_data, get_recent_days
from analyzer import (
    load_state,
    save_state,
    expire_old_distribution_days,
    invalidate_by_vertical_rise,
    analyze_distribution_day,
    analyze_follow_through_day,
    update_market_status,
    generate_report,
)
from telegram_sender import send_telegram_message


def run_analysis():
    """데이터를 가져와 분석하고 텔레그램으로 전송한다."""
    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")
    print(f"\n[{now_kst}] 분석 시작...")

    try:
        # 1. 데이터 가져오기
        records = fetch_nasdaq_data()
        if len(records) < 2:
            print("[ERROR] 데이터가 2거래일 미만입니다.")
            return

        today, yesterday = records[-1], records[-2]
        print(f"[INFO] 분석 대상: {today['date']} (전일: {yesterday['date']})")

        # 2. 상태 로드
        state = load_state()

        # 이미 분석한 날짜면 스킵
        if state["last_analyzed_date"] == today["date"]:
            print(f"[SKIP] {today['date']}는 이미 분석 완료")
            return

        # 3. 분산일 소멸 및 무효화 처리
        expired_dds = expire_old_distribution_days(state, records) or []
        invalidated_dds = invalidate_by_vertical_rise(state, records)

        # 4. Distribution Day 분석
        dd_result = analyze_distribution_day(today, yesterday, state)

        # 5. Follow-Through Day 분석
        ftd_result = analyze_follow_through_day(today, yesterday, state, records)

        # 6. 시장 상태 업데이트
        update_market_status(state, dd_result, ftd_result, records)

        # 7. 리포트 생성 및 전송
        report = generate_report(
            today, yesterday, dd_result, ftd_result,
            state, expired_dds, invalidated_dds
        )
        print(report)
        send_telegram_message(report)

        # 8. 상태 저장
        state["last_analyzed_date"] = today["date"]
        save_state(state)
        print("[OK] 분석 완료 및 상태 저장")

    except Exception as e:
        error_msg = f"[ERROR] 분석 실패: {e}"
        print(error_msg)
        send_telegram_message(f"⚠️ 나스닥 FTD/DD 분석 오류\n{e}")


def main():
    parser = argparse.ArgumentParser(description="나스닥 DD/FTD 분석기")
    parser.add_argument(
        "--schedule", action="store_true",
        help="매일 KST 오전 9시에 자동 실행"
    )
    args = parser.parse_args()

    # .env 파일 로드 (dotenv 없이 수동 로드)
    _load_env()

    if args.schedule:
        # KST 09:00 = UTC 00:00
        schedule.every().day.at("00:00").do(run_analysis)
        print("[SCHEDULER] 매일 KST 09:00 (UTC 00:00) 실행 예약됨")
        print("[SCHEDULER] Ctrl+C로 종료")

        # 시작 시 1회 실행
        run_analysis()

        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_analysis()


def _load_env():
    """간단한 .env 파일 로더"""
    import os
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
        print("[INFO] .env 파일 로드 완료")
    else:
        print("[WARN] .env 파일이 없습니다. 환경변수를 직접 설정하세요.")


if __name__ == "__main__":
    main()
