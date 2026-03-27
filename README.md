# NASDAQ Distribution Day / Follow-Through Day Analyzer

나스닥 종합지수의 Distribution Day(분산일) 및 Follow-Through Day(팔로우스루데이)를 자동 분석하여 텔레그램으로 알림을 보내는 도구입니다.

## 설정

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
`.env.example`을 `.env`로 복사하고 값을 채워주세요:
```bash
cp .env.example .env
```

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**텔레그램 봇 토큰**: [@BotFather](https://t.me/BotFather)에서 `/newbot`으로 생성
**채팅 ID**: [@userinfobot](https://t.me/userinfobot)에서 확인

## 사용법

### 즉시 실행 (1회)
```bash
python main.py
```

### 스케줄 실행 (매일 KST 09:00)
```bash
python main.py --schedule
```

### crontab으로 매일 실행 (권장)
```bash
# crontab -e
0 0 * * 1-5 cd /path/to/FTD-DD && python main.py
```
> UTC 00:00 = KST 09:00, 월~금 평일만 실행

## 분석 항목

### Distribution Day (분산일)
- 기본 분산일: 종가 0.2%+ 하락 & 거래량 증가
- 숨겨진 분산일 (스톨링/처닝): 미세 변동 + 거래량 폭증
- 제외 조건: 좁은 변동폭, 상위권 마감 등

### Follow-Through Day (팔로우스루데이)
- 반등 시도 4~7일차에 1%+ 상승 & 거래량 증가
- 변동성 확대 시 기준값 1.7%로 상향
- 3일차 조기 인정 (강력한 매수세 시)

### 시장 상태 진단
- 확인된 상승장 → 압박받는 상승장 → 하락장
- 분산일 25거래일 경과 시 자동 소멸
- 6% 수직 상승 시 분산일 무효화
- FTD 발생 시 분산일 카운트 전면 초기화
