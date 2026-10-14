"""누락분 재수집 + 단지정보 API 응답 확인."""
import gzip, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import collect

raw = json.load(gzip.open("report/raw.json.gz", "rt", encoding="utf-8"))
for kind in ("trade", "rent"):
    for lawd, months in raw[kind].items():
        for ymd, items in months.items():
            if not items:
                months[ymd] = collect.fetch_rtms(kind, lawd, ymd)

probe = {}
for name, url, params in [
    ("list3_sgg", "https://apis.data.go.kr/1613000/AptListService3/getSigunguAptList3", {"sigunguCode": "41410", "numOfRows": 5, "pageNo": 1}),
    ("list3_bjd", "https://apis.data.go.kr/1613000/AptListService3/getLegaldongAptList3", {"bjdCode": "4141010400", "numOfRows": 5, "pageNo": 1}),
    ("list2_sgg", "https://apis.data.go.kr/1613000/AptListService2/getSigunguAptList", {"sigunguCode": "41410", "numOfRows": 5, "pageNo": 1}),
    ("basis4", "https://apis.data.go.kr/1613000/AptBasisInfoServiceV4/getAphusBassInfoV4", {"kaptCode": "A41085601"}),
    ("basis3", "https://apis.data.go.kr/1613000/AptBasisInfoServiceV3/getAphusBassInfoV3", {"kaptCode": "A41085601"}),
]:
    try:
        r = collect.get(url, {**params, "_type": "json"})
        probe[name] = f"{r.status_code} {r.text[:600]}"
    except Exception as e:
        probe[name] = f"ERR {e}"
raw["probe"] = probe
raw["log"] += collect.log
with gzip.open("report/raw.json.gz", "wt", encoding="utf-8") as f:
    json.dump(raw, f, ensure_ascii=False)
print(json.dumps(probe, ensure_ascii=False, indent=1))
print("\n".join(collect.log))
