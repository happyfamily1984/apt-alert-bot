import datetime
import json
import os
import requests
import xmltodict

API_KEY = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# 모니터링 대상 단지 3곳
TARGET_APTS = [
    {
        "keywords": ["건영"],
        "display_name": "목동 건영아파트",
        "lawd_cd": "11470"   # 서울 양천구
    },
    {
        "keywords": ["금호어울림베르티스", "금호어울림"],
        "display_name": "여주역 금호어울림베르티스",
        "lawd_cd": "41670"   # 경기 여주시
    },
    {
        "keywords": ["목련(한양)", "한양(목련)", "한양목련", "목련한양"],
        "display_name": "산본 한양목련아파트",
        "lawd_cd": "41410"   # 경기 군포시 (산본동)
    }
]

HISTORY_FILE = "sent_trades.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(history), f, ensure_ascii=False, indent=2)

def mask_secrets(msg):
    # 공개 저장소에서는 Actions 로그도 공개되므로 오류 메시지 속 키/토큰을 가린다
    msg = str(msg)
    for secret in (API_KEY, TELEGRAM_TOKEN):
        if secret:
            msg = msg.replace(secret, "***")
    return msg

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"전송 실패: {mask_secrets(e)}")

def get_target_ymds():
    # 최근 3개월 조회 (YYYYMM)
    ymds = []
    now = datetime.datetime.now()
    cur_year = now.year
    cur_month = now.month
    
    for i in range(3):
        m = cur_month - i
        y = cur_year
        if m <= 0:
            m += 12
            y -= 1
        ymds.append(f"{y}{str(m).zfill(2)}")
    return ymds

def fetch_data(base_url, lawd_cd, deal_ymd):
    # API 키 왜곡을 막는 검증된 직접 URL 조합 방식
    req_url = f"{base_url}?serviceKey={API_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=500"
    try:
        res = requests.get(req_url, timeout=15)
        data = xmltodict.parse(res.content)
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        return items
    except Exception as e:
        print(f"API 요청 실패 ({lawd_cd}, {deal_ymd}): {mask_secrets(e)}")
        return []

def is_matched_apt(apt_name, keywords):
    clean_name = str(apt_name).replace(" ", "").replace("(", "").replace(")", "")
    for kw in keywords:
        clean_kw = kw.replace(" ", "").replace("(", "").replace(")", "")
        if clean_kw in clean_name:
            return True
    return False

def clean_val(val):
    if not val:
        return "0"
    return str(val).replace(",", "").strip()

def run():
    sent_history = load_history()
    target_ymds = get_target_ymds()

    url_trade = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
    url_rent = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

    new_count = 0

    for deal_ymd in target_ymds:
        for apt in TARGET_APTS:
            # 1. 매매 실거래가 조회
            items_trade = fetch_data(url_trade, apt["lawd_cd"], deal_ymd)
            for item in items_trade:
                apt_name = str(item.get("aptNm", ""))
                if is_matched_apt(apt_name, apt["keywords"]):
                    deal_amount = clean_val(item.get("dealAmount"))
                    trade_id = f"TRADE_{apt['lawd_cd']}_{apt_name}_{item.get('dealYear')}{str(item.get('dealMonth')).zfill(2)}{str(item.get('dealDay')).zfill(2)}_{item.get('floor')}_{deal_amount}"
                    
                    if trade_id not in sent_history:
                        msg = (
                            f"🚨 <b>[매매 실거래] {apt['display_name']} ({apt_name})</b>\n"
                            f"• 계약일: {item.get('dealYear')}년 {item.get('dealMonth')}월 {item.get('dealDay')}일\n"
                            f"• 거래금액: <b>{deal_amount}만원</b>\n"
                            f"• 전용면적: {item.get('excluUseAr')}㎡ ({item.get('floor')}층)\n"
                            f"• 거래유형: {item.get('dealingGbn', '정보없음')}"
                        )
                        send_telegram_message(msg)
                        sent_history.add(trade_id)
                        new_count += 1

            # 2. 전월세 실거래가 조회
            items_rent = fetch_data(url_rent, apt["lawd_cd"], deal_ymd)
            for item in items_rent:
                apt_name = str(item.get("aptNm", ""))
                if is_matched_apt(apt_name, apt["keywords"]):
                    deposit = clean_val(item.get("deposit"))
                    monthly_rent = clean_val(item.get("monthlyRent") or item.get("monthlyAmount"))
                    
                    is_monthly = monthly_rent not in ["0", "", "None"]
                    trade_type = "월세" if is_monthly else "전세"
                    icon = "🔶" if is_monthly else "🔷"
                    
                    rent_id = f"RENT_{apt['lawd_cd']}_{apt_name}_{item.get('dealYear')}{str(item.get('dealMonth')).zfill(2)}{str(item.get('dealDay')).zfill(2)}_{item.get('floor')}_{deposit}_{monthly_rent}"
                    
                    if rent_id not in sent_history:
                        if is_monthly:
                            price_display = f"보증금 <b>{deposit}만원</b> / 월세 <b>{monthly_rent}만원</b>"
                        else:
                            price_display = f"전세보증금 <b>{deposit}만원</b>"

                        msg = (
                            f"{icon} <b>[{trade_type} 실거래] {apt['display_name']} ({apt_name})</b>\n"
                            f"• 계약일: {item.get('dealYear')}년 {item.get('dealMonth')}월 {item.get('dealDay')}일\n"
                            f"• 임대금액: {price_display}\n"
                            f"• 전용면적: {item.get('excluUseAr')}㎡ ({item.get('floor')}층)"
                        )
                        send_telegram_message(msg)
                        sent_history.add(rent_id)
                        new_count += 1

    # 신규 거래가 없으면 알림을 보내지 않음

    save_history(sent_history)
    print(f"조회 완료: 신규 전송 {new_count}건")

if __name__ == "__main__":
    run()
