import os
import requests
import xmltodict

API_KEY = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

print(f"=== 환경변수 확인 ===")
print(f"TELEGRAM_TOKEN 설정 여부: {'O' if TELEGRAM_TOKEN else 'X'}")
print(f"CHAT_ID: {CHAT_ID}")
print(f"API_KEY 앞 5자리: {API_KEY[:5]}*** (총길이: {len(API_KEY)})")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"텔레그램 전송 응답 코드: {res.status_code}, 내용: {res.text}")
        return res.status_code == 200
    except Exception as e:
        print(f"텔레그램 전송 예외 발생: {e}")
        return False

# 1. 텔레그램 연결 테스트 (무조건 1회 발송)
send_telegram_message("🤖 <b>[알림봇 연결 성공]</b> 실거래가 조회를 시작합니다.")

# 2. 공공데이터 API 응답 테스트 (양천구 2024년 05월 기준 테스트)
url_trade = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
params = {
    "serviceKey": API_KEY,
    "LAWD_CD": "11470",
    "DEAL_YMD": "202405",
    "numOfRows": "10"
}

try:
    res = requests.get(url_trade, params=params, timeout=10)
    print(f"공공데이터 응답 상태코드: {res.status_code}")
    print(f"공공데이터 응답 원문 (앞 300자):\n{res.text[:300]}")
    
    data = xmltodict.parse(res.content)
    result_code = data.get("response", {}).get("header", {}).get("resultCode", "")
    result_msg = data.get("response", {}).get("header", {}).get("resultMsg", "")
    print(f"API 결과 코드: {result_code}, 메시지: {result_msg}")
    
    if result_code == "00":
        send_telegram_message("✅ <b>[공공데이터 연동 성공]</b> API 데이터가 정상 수신되었습니다.")
    else:
        send_telegram_message(f"❌ <b>[API 인증 에러]</b> 코드: {result_code}\n메시지: {result_msg}")
except Exception as e:
    print(f"API 호출 중 예외: {e}")
