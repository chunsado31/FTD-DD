"""텔레그램 메시지 전송 모듈"""
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram_message(text):
    """텔레그램 봇을 통해 메시지를 전송한다."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ERROR] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        print("[INFO] .env 파일을 확인하세요.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[OK] 텔레그램 전송 성공")
        return True
    except requests.RequestException as e:
        print(f"[ERROR] 텔레그램 전송 실패: {e}")
        return False
