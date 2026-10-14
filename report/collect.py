"""일회성 보고서용 원본 데이터 수집 (GitHub Actions에서 실행)."""
import datetime
import json
import os
import requests
import xmltodict

API_KEY = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
SGGS = {"11470": "서울 양천구", "41670": "경기 여주시", "41410": "경기 군포시"}
MONTHS = 13
URLS = {
    "trade": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "rent": "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
}
log = []


def ymds():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    y, m, out = now.year, now.month, []
    for _ in range(MONTHS):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def get(url, params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return requests.get(f"{url}?serviceKey={API_KEY}&{q}", timeout=30)


def fetch_rtms(kind, lawd, ymd):
    items, page = [], 1
    while True:
        try:
            res = get(URLS[kind], {"LAWD_CD": lawd, "DEAL_YMD": ymd, "numOfRows": 1000, "pageNo": page})
            body = xmltodict.parse(res.content).get("response", {}).get("body", {}) or {}
        except Exception as e:
            log.append(f"{kind} {lawd} {ymd} p{page}: {e} / {res.text[:200] if 'res' in dir() else ''}")
            break
        got = (body.get("items") or {}).get("item", []) or []
        if isinstance(got, dict):
            got = [got]
        items += got
        total = int(body.get("totalCount") or 0)
        if page * 1000 >= total:
            break
        page += 1
    log.append(f"{kind} {lawd} {ymd}: {len(items)}")
    return items


def fetch_json(url, params):
    try:
        res = get(url, {**params, "_type": "json"})
        return res.json()
    except Exception as e:
        log.append(f"{url.split('/')[-1]} {params}: {e} / {res.text[:300] if 'res' in locals() else ''}")
        return None


def main():
    out = {"generated": datetime.datetime.utcnow().isoformat(), "trade": {}, "rent": {}, "aptlist": {}, "basis": {}}
    for lawd in SGGS:
        for kind in ("trade", "rent"):
            out[kind][lawd] = {ymd: fetch_rtms(kind, lawd, ymd) for ymd in ymds()}

    # 공동주택 단지 목록 (시군구) → 기본정보(세대수)
    for lawd in SGGS:
        lst, page = [], 1
        while True:
            j = fetch_json("https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3",
                           {"sigunguCode": lawd, "numOfRows": 1000, "pageNo": page})
            body = ((j or {}).get("response") or {}).get("body") or {}
            got = body.get("items") or []
            if isinstance(got, dict):
                got = got.get("item", [])
            if isinstance(got, dict):
                got = [got]
            lst += got
            if not got or page * 1000 >= int(body.get("totalCount") or 0):
                break
            page += 1
        out["aptlist"][lawd] = lst
        log.append(f"aptlist {lawd}: {len(lst)}")
        for apt in lst:
            code = apt.get("kaptCode")
            j = fetch_json("https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusBassInfoV4", {"kaptCode": code})
            item = (((j or {}).get("response") or {}).get("body") or {}).get("item")
            if item:
                out["basis"][code] = item
            elif len(out["basis"]) == 0 and len(log) < 400:
                log.append(f"basis {code}: {json.dumps(j, ensure_ascii=False)[:300]}")
        log.append(f"basis total: {len(out['basis'])}")

    out["log"] = log
    with open("report_raw.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("\n".join(log[-60:]))


if __name__ == "__main__":
    main()
