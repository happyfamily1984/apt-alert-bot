import datetime
import json
import os
import requests
import xmltodict

API_KEY = os.environ.get("DATA_GO_KR_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TARGET_APTS = [
    {"name": "건영", "display_name": "목동 건영아파트", "lawd_cd": "11470"},               # 서울 양천구
    {"name": "금호어울림", "display_name": "여주역 금호어울림베르티스", "lawd_cd": "41670"}, # 경기 여주시 (매칭 완화)
    {"name": "목련", "display_name": "한양목련아파트", "lawd_cd": "41173"}                 # 경기 안양시 동안구 (매칭 완화)
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
    # 당월 및 전월 (YYYYMM) 목록 생성
    now = datetime.datetime.now()
    this_month = now.strftime("%Y%m")
    
    first_day = now.replace(day=1)
    prev_month_day = first_day - datetime.timedelta(days=1)
    prev_month = prev_month_day.strftime("%Y%m")
    
    return [prev_month, this_month]

def run():
    sent_history = load_history()
    target_ymds = get_target_ymds()

    url_trade = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
    url_rent = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"

    new_count = 0

    for deal_ymd in target_ymds:
        for apt in TARGET_APTS:
            # 1. 매매 실거래가 조회
            try:
                res_trade = requests.get(url_trade, params={"serviceKey": API_KEY, "LAWD_CD": apt["lawd_cd"], "DEAL_YMD": deal_ymd, "numOfRows": "200"}, timeout=10)
                data_trade = xmltodict.parse(res_trade.content)
                items_trade = data_trade.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if isinstance(items_trade, dict):
                    items_trade = [items_trade]

                for item in items_trade:
                    apt_name = str(item.get("aptNm", ""))
                    if apt["name"] in apt_name:
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
            except Exception as e:
                print(f"[{apt['display_name']}] 매매 에러 ({deal_ymd}): {e}")

            # 2. 전월세 실거래가 조회
            try:
                res_rent = requests.get(url_rent, params={"serviceKey": API_KEY, "LAWD_CD": apt["lawd_cd"], "DEAL_YMD": deal_ymd, "numOfRows": "200"}, timeout=10)
                data_rent = xmltodict.parse(res_rent.content)
                items_rent = data_rent.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if isinstance(items_rent, dict):
                    items_rent = [items_rent]

                for item in items_rent:
                    apt_name = str(item.get("aptNm", ""))
                    if apt["name"] in apt_name:
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
            except Exception as e:
                print(f"[{apt['display_name']}] 전월세 에러 ({deal_ymd}): {e}")

    save_history(sent_history)
    print(f"조회 완료: 신규 전송 {new_count}건")

if __name__ == "__main__":
    run()
