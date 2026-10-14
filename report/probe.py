"""단지정보(세대수) API 경로 탐색."""
import gzip, json, os, sys
import requests
sys.path.insert(0, os.path.dirname(__file__))
import collect

raw = json.load(gzip.open("report/raw.json.gz", "rt", encoding="utf-8"))
probe = {}
for pid in ["15058453", "15058467", "15057332", "15058476", "15044934", "15117209", "15151846"]:
    try:
        r = requests.get(f"https://www.data.go.kr/catalog/{pid}/openapi.json", timeout=20)
        j = r.json()
        probe[f"cat_{pid}"] = {"title": j.get("info", {}).get("title"), "host": j.get("host"), "base": j.get("basePath"),
                               "servers": j.get("servers"), "paths": list((j.get("paths") or {}).keys())}
    except Exception as e:
        probe[f"cat_{pid}"] = f"ERR {e} {r.text[:200] if 'r' in locals() else ''}"
cands = []
for k, v in probe.items():
    if isinstance(v, dict) and v.get("paths"):
        base = (v.get("servers") or [{}])[0].get("url") if v.get("servers") else f"https://{v.get('host')}{v.get('base') or ''}"
        for p in v["paths"]:
            cands.append(base.rstrip("/") + p)
probe["calls"] = {}
for url in cands:
    params = {"_type": "json", "numOfRows": 3, "pageNo": 1}
    if "Legaldong" in url or "bjd" in url.lower():
        params["bjdCode"] = "4141010400"
    elif "Sigungu" in url:
        params["sigunguCode"] = "41410"
    elif "Bass" in url or "Basis" in url or "Dtl" in url:
        params["kaptCode"] = "A41085601"
    try:
        r = collect.get(url, params)
        probe["calls"][url] = f"{r.status_code} {r.text[:500]}"
    except Exception as e:
        probe["calls"][url] = f"ERR {e}"
raw["probe2"] = probe
with gzip.open("report/raw.json.gz", "wt", encoding="utf-8") as f:
    json.dump(raw, f, ensure_ascii=False)
print(json.dumps(probe, ensure_ascii=False, indent=1)[:5000])
