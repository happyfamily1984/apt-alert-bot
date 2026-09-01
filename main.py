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
        "keywords": ["금호어울림", "금호", "베르티스"],
        "display_name": "여주역 금호어울림베르티스",
        "lawd_cd": "41670"   # 경기 여주시
    },
    {
        "keywords": ["한양목련", "목련한양", "한양", "목련"],
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

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"전송 실패: {e}")

def get_target_ymds():
    # 최근 3개월 조회 (7월, 8월, 9월)
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
    req_url = f"{base_url}?serviceKey={API_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=500"
    try:
        res = requests.get(req_url, timeout=15)
        data = xmltodict.parse(res.content)
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        return items
    except Exception as e:
        print(f"API 요청 실패 ({lawd_cd}, {deal_ymd}): {e}")
        return []

def is_matched_apt(apt_name, keywords):
    clean_name = str(apt_name).replace(" ", "").replace("(", "").replace(")", "")
    for kw in keywords:
        clean_kw = kw.replace(" ", "").replace("(", "").replace(")", "")
        if clean_kw in clean_name:
            return True
    return False

def run():
    sent_history = load_history()
    target_ymds = get_target_ymds()
    now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    current_time_str = now_kst.strftime("%Y년 %m월 %d일 %H시")

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
                    trade_id = f"TRADE_{apt['lawd_cd']}_{apt_name}_{item.get('dealYear')}{str(item.get('dealMonth')).zfill(2)}{str(item.get('dealDay')).zfill(2)}_{item.get('floor')}_{str(item.get('dealAmount', '')).strip()}"
                    if trade_id not in sent_history:
                        msg = (
                            f"🚨 <b>[매매 실거래] {apt['display_name']} ({apt_name})</b>\n"
                            f"• 계약일: {item.get('dealYear')}년 {item.get('dealMonth')}월 {item.get('dealDay')}일\n"
                            f"• 거래금액: <b>{str(item.get('dealAmount', '')).strip()}만원</b>\n"
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
                    monthly = str(item.get("monthlyAmount", "0")).strip()
                    rent_type = "월세" if monthly not in ["0", ""] else "전세"
                    deposit = str(item.get("deposit", "")).strip()
                    rent_id = f"RENT_{apt['lawd_cd']}_{apt_name}_{item.get('dealYear')}{str(item.get('dealMonth')).zfill(2)}{str(item.get('dealDay')).zfill(2)}_{item.get('floor')}_{deposit}_{monthly}"
                    if rent_id not in sent_history:
                        price_info = f"보증금 {deposit}만원"
                        if rent_type == "월세":
                            price_info += f" / 월세 {monthly}만원"

                        msg = (
                            f"📋 <b>[{rent_type} 실거래] {apt['display_name']} ({apt_name})</b>\n"
                            f"• 계약일: {item.get('dealYear')}년 {item.get('dealMonth')}월 {item.get('dealDay')}일\n"
                            f"• 금액: <b>{price_info}</b>\n"
                            f"• 전용면적: {item.get('excluUseAr')}㎡ ({item.get('floor')}층)"
                        )
                        send_telegram_message(msg)
                        sent_history.add(rent_id)
                        new_count += 1

    # 신규 거래가 없을 경우 정기 안내 메시지
    if new_count == 0:
        no_trade_msg = (
            f"📢 <b>[{current_time_str} 정기 브리핑]</b>\n"
            f"지정하신 3개 관심단지에\n"
            f"새로 등록된 매매/전월세 실거래 내역이 없습니다."
        )
        send_telegram_message(no_trade_msg)

    save_history(sent_history)
    print(f"조회 완료: 신규 전송 {new_count}건")

if __name__ == "__main__":
    run()
