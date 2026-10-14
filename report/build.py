"""수집된 실거래 원본(report/raw.json.gz)으로 단지별 상세 보고서 HTML 생성."""
import collections
import datetime
import gzip
import html
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = json.load(gzip.open(os.path.join(HERE, "raw.json.gz"), "rt", encoding="utf-8"))
HOUSEHOLDS = {}
if os.path.exists(os.path.join(HERE, "households.json")):
    HOUSEHOLDS = json.load(open(os.path.join(HERE, "households.json"), encoding="utf-8"))

TARGETS = [
    {"key": "mokdong", "display": "목동 건영아파트", "lawd": "11470", "sgg": "서울 양천구",
     "aptNm": "건영", "umdNm": "목동", "jibun": "928"},
    {"key": "yeoju", "display": "여주역 금호어울림베르티스", "lawd": "41670", "sgg": "경기 여주시",
     "aptNm": "여주역금호어울림베르티스", "umdNm": "교동", "jibun": "572"},
    {"key": "sanbon", "display": "산본 한양목련아파트", "lawd": "41410", "sgg": "경기 군포시",
     "aptNm": "한양목련", "umdNm": "산본동", "jibun": "1088"},
]

# 분석 기간: 최근 12개 완결월 (이번 달은 진행 중이라 거래량 집계에서 제외)
ALL_MONTHS = sorted({m for k in ("trade", "rent") for l in RAW[k].values() for m in l})
CUR_MONTH = ALL_MONTHS[-1]
MONTHS = ALL_MONTHS[-13:-1]


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def ym(it):
    return f"{int(it['dealYear'])}{int(it['dealMonth']):02d}"


def date(it):
    return datetime.date(int(it["dealYear"]), int(it["dealMonth"]), int(it["dealDay"]))


def cancelled(it):
    return str(it.get("cdealType") or "").strip() not in ("", "None")


def records(kind, lawd):
    out = []
    for items in RAW[kind][lawd].values():
        for it in items:
            if kind == "trade" and cancelled(it):
                continue
            out.append(it)
    return out


def complex_key(it):
    return (str(it.get("aptNm", "")).strip(), str(it.get("umdNm", "")).strip(), str(it.get("jibun", "")).strip())


def is_target(it, t):
    return complex_key(it) == (t["aptNm"], t["umdNm"], t["jibun"])


def area_group(a):
    return int(round(num(a)))


def won(man):
    """만원 → '8억 5,000' 형식."""
    man = int(round(man))
    eok, rest = divmod(man, 10000)
    if eok and rest:
        return f"{eok}억 {rest:,}"
    if eok:
        return f"{eok}억"
    return f"{rest:,}만"


def pyeong_price(price, area):
    return price / (num(area) / 3.3058) if num(area) else 0


def esc(s):
    return html.escape(str(s))


def ym_label(m):
    return f"{m[2:4]}.{m[4:]}"


# ---------------------------------------------------------------- SVG charts
def bar_chart(months, series, height=190, stacked=True):
    """series: [(name, cssvar, {month: value})]"""
    w, pl, pr, pt, pb = 640, 34, 8, 12, 26
    iw, ih = w - pl - pr, height - pt - pb
    totals = [sum(s[2].get(m, 0) for s in series) for m in months]
    vmax = max(totals + [1])
    step = nice_step(vmax)
    top = step * -(-vmax // step)
    bw = iw / len(months)
    out = [f'<div class="cw"><svg viewBox="0 0 {w} {height}" class="chart" role="img">']
    for i in range(0, int(top) + 1, int(step)):
        y = pt + ih - ih * i / top
        out.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{pl - 6}" y="{y + 4:.1f}" class="tick" text-anchor="end">{i}</text>')
    for mi, m in enumerate(months):
        x = pl + bw * mi + bw * 0.18
        cw = bw * 0.64
        base = 0
        tip = [f"{m[:4]}년 {int(m[4:])}월"]
        segs = []
        for name, var, vals in series:
            v = vals.get(m, 0)
            tip.append(f"{name} {v}건")
            if not v:
                continue
            y0 = pt + ih - ih * base / top
            y1 = pt + ih - ih * (base + v) / top
            segs.append((y1, y0 - y1, var))
            base += v
        for si, (y, h, var) in enumerate(segs):
            gap = 2 if si > 0 else 0
            r = 3 if si == len(segs) - 1 else 0
            hh = max(h - gap, 1)
            if r and hh > 4:
                out.append(f'<path d="M{x:.1f},{y + hh:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
                           f'H{x + cw - r:.1f} Q{x + cw:.1f},{y:.1f} {x + cw:.1f},{y + r:.1f} V{y + hh:.1f} Z" fill="var({var})"/>')
            else:
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" height="{hh:.1f}" fill="var({var})"/>')
        out.append(f'<rect x="{pl + bw * mi:.1f}" y="{pt}" width="{bw:.1f}" height="{ih}" class="hit" data-tip="{esc(" · ".join(tip))}"/>')
        if len(months) <= 12 or mi % 2 == 0:
            out.append(f'<text x="{x + cw / 2:.1f}" y="{height - 8}" class="tick" text-anchor="middle">{ym_label(m)}</text>')
    out.append(f'<line x1="{pl}" x2="{w - pr}" y1="{pt + ih}" y2="{pt + ih}" class="axis"/></svg></div>')
    return "".join(out)


def nice_step(vmax, ticks=4):
    raw = vmax / ticks
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    for s in (1, 2, 2.5, 5, 10):
        if s * mag >= raw:
            return max(1, s * mag)
    return 10 * mag


def scatter_chart(points, months, height=230):
    """points: [(date, price, series_idx, tip)] series 0=매매, 1=전세"""
    w, pl, pr, pt, pb = 640, 56, 10, 12, 26
    iw, ih = w - pl - pr, height - pt - pb
    if not points:
        return '<p class="muted">해당 기간 거래 없음</p>'
    d0 = datetime.date(int(months[0][:4]), int(months[0][4:]), 1)
    d1 = datetime.date.today() + datetime.timedelta(days=1)
    vals = [p[1] for p in points]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.12 or hi * 0.1
    lo, hi = max(0, lo - pad), hi + pad
    step = nice_step(hi - lo, 4)
    lo = step * (lo // step)
    hi = step * -(-hi // step)
    X = lambda d: pl + iw * (d - d0).days / max((d1 - d0).days, 1)
    Y = lambda v: pt + ih - ih * (v - lo) / (hi - lo)
    out = [f'<div class="cw"><svg viewBox="0 0 {w} {height}" class="chart" role="img">']
    v = lo
    while v <= hi + 1e-6:
        out.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                   f'<text x="{pl - 6}" y="{Y(v) + 4:.1f}" class="tick" text-anchor="end">{won(v)}</text>')
        v += step
    for i, m in enumerate(months + [CUR_MONTH]):
        if i % 2:
            continue
        d = datetime.date(int(m[:4]), int(m[4:]), 1)
        out.append(f'<text x="{X(d):.1f}" y="{height - 8}" class="tick" text-anchor="middle">{ym_label(m)}</text>')
    # 시리즈별 월 중앙값 선
    for s, var in ((0, "--s1"), (1, "--s2")):
        by = collections.defaultdict(list)
        for d, p, si, _ in points:
            if si == s:
                by[d.strftime("%Y%m")].append(p)
        pts = [(datetime.date(int(k[:4]), int(k[4:]), 15), statistics.median(v)) for k, v in sorted(by.items())]
        if len(pts) >= 2:
            path = " ".join(f"{'M' if i == 0 else 'L'}{X(d):.1f},{Y(p):.1f}" for i, (d, p) in enumerate(pts))
            out.append(f'<path d="{path}" fill="none" stroke="var({var})" stroke-width="2" stroke-linejoin="round" opacity=".55"/>')
    for d, p, si, tip in sorted(points, key=lambda x: x[2]):
        var = "--s1" if si == 0 else "--s2"
        out.append(f'<circle cx="{X(d):.1f}" cy="{Y(p):.1f}" r="4.5" fill="var({var})" class="dot"/>'
                   f'<circle cx="{X(d):.1f}" cy="{Y(p):.1f}" r="10" class="hit" data-tip="{esc(tip)}"/>')
    out.append(f'<line x1="{pl}" x2="{w - pr}" y1="{pt + ih}" y2="{pt + ih}" class="axis"/></svg></div>')
    return "".join(out)


def hbar_chart(rows, height_per=24):
    """rows: [(label, value, highlight, tip)]"""
    w, pl, pr = 640, 170, 44
    iw = w - pl - pr
    vmax = max([r[1] for r in rows] + [1])
    h = height_per * len(rows) + 6
    out = [f'<div class="cw"><svg viewBox="0 0 {w} {h}" class="chart" role="img">']
    for i, (label, v, hl, tip) in enumerate(rows):
        y = 3 + i * height_per
        bw = max(iw * v / vmax, 2)
        cls = "hl" if hl else ""
        out.append(f'<text x="{pl - 8}" y="{y + 15}" class="ylab {cls}" text-anchor="end">{esc(label)}</text>')
        out.append(f'<path d="M{pl},{y + 4} H{pl + bw - 3:.1f} Q{pl + bw:.1f},{y + 4} {pl + bw:.1f},{y + 7} V{y + 16} '
                   f'Q{pl + bw:.1f},{y + 19} {pl + bw - 3:.1f},{y + 19} H{pl} Z" fill="var({"--s1" if hl else "--neutral"})"/>')
        out.append(f'<text x="{pl + bw + 6:.1f}" y="{y + 15}" class="val {cls}">{v:g}</text>')
        out.append(f'<rect x="0" y="{y}" width="{w}" height="{height_per}" class="hit" data-tip="{esc(tip)}"/>')
    out.append("</svg></div>")
    return "".join(out)


# ---------------------------------------------------------------- analysis
def analyze(t):
    trades = records("trade", t["lawd"])
    rents = records("rent", t["lawd"])
    in_window = lambda it: ym(it) in MONTHS
    mt = [it for it in trades if is_target(it, t)]
    mr = [it for it in rents if is_target(it, t)]
    jeonse = [it for it in mr if num(it.get("monthlyRent")) == 0]
    wolse = [it for it in mr if num(it.get("monthlyRent")) > 0]

    areas = collections.Counter(area_group(it["excluUseAr"]) for it in mt + mr)
    main_area = areas.most_common(1)[0][0] if areas else None
    build_year = next((it.get("buildYear") for it in mt + mr if it.get("buildYear")), "-")

    def cnt(lst):
        c = collections.Counter(ym(it) for it in lst)
        return {m: c.get(m, 0) for m in MONTHS}

    vol = {"매매": cnt(mt), "전세": cnt(jeonse), "월세": cnt(wolse)}
    tot = {k: sum(v.values()) for k, v in vol.items()}

    # 대표 면적 가격
    ma = [it for it in mt if area_group(it["excluUseAr"]) == main_area]
    mj = [it for it in jeonse if area_group(it["excluUseAr"]) == main_area]
    ma.sort(key=date)
    mj.sort(key=date)
    first_half = MONTHS[:6]
    second_half = MONTHS[6:] + [CUR_MONTH]
    med = lambda lst, ms: statistics.median([num(it["dealAmount" if "dealAmount" in it else "deposit"]) for it in lst if ym(it) in ms]) if [1 for it in lst if ym(it) in ms] else None
    p1, p2 = med(ma, first_half), med(ma, second_half)
    j1, j2 = med(mj, first_half), med(mj, second_half)
    last_trade = ma[-1] if ma else None
    hi_trade = max(ma, key=lambda it: num(it["dealAmount"])) if ma else None
    jratio = (j2 / p2 * 100) if (j2 and p2) else None

    points = []
    for it in ma:
        points.append((date(it), num(it["dealAmount"]), 0,
                       f"매매 {won(num(it['dealAmount']))} · {date(it):%Y.%m.%d} · {it.get('floor')}층 · {it.get('dealingGbn') or ''}"))
    for it in mj:
        points.append((date(it), num(it["deposit"]), 1,
                       f"전세 {won(num(it['deposit']))} · {date(it):%Y.%m.%d} · {it.get('floor')}층 · {it.get('contractType') or ''}"))

    # 시군구 전체 매매 거래량 (맥락)
    sgg_vol = collections.Counter(ym(it) for it in trades)
    share = tot["매매"] / max(sum(sgg_vol[m] for m in MONTHS), 1) * 100

    # 인근 단지 비교 (동일 법정동)
    nb = collections.defaultdict(lambda: {"trade": 0, "rent": 0, "py": [], "by": "", "areas": collections.Counter()})
    for it in trades:
        if it["umdNm"].strip() == t["umdNm"] and in_window(it):
            k = complex_key(it)
            nb[k]["trade"] += 1
            nb[k]["py"].append(pyeong_price(num(it["dealAmount"]), it["excluUseAr"]))
            nb[k]["by"] = it.get("buildYear") or nb[k]["by"]
            nb[k]["areas"][area_group(it["excluUseAr"])] += 1
    for it in rents:
        if it["umdNm"].strip() == t["umdNm"] and in_window(it):
            k = complex_key(it)
            nb[k]["rent"] += 1
            nb[k]["by"] = it.get("buildYear") or nb[k]["by"]
    tkey = (t["aptNm"], t["umdNm"], t["jibun"])
    ranked = sorted(nb.items(), key=lambda kv: (-kv[1]["trade"], -kv[1]["rent"]))
    rank = next((i + 1 for i, (k, _) in enumerate(ranked) if k == tkey), None)
    n_traded = sum(1 for _, v in ranked if v["trade"] > 0)
    # 비슷한 연식(±5년) 단지
    try:
        by0 = int(build_year)
        similar = [(k, v) for k, v in ranked if v["by"] and abs(int(v["by"]) - by0) <= 5]
    except ValueError:
        similar = ranked
    similar_med = statistics.median([v["trade"] for _, v in similar]) if similar else 0
    dong_med = statistics.median([v["trade"] for _, v in ranked]) if ranked else 0

    return dict(t=t, mt=mt, mr=mr, jeonse=jeonse, wolse=wolse, areas=areas, main_area=main_area,
                build_year=build_year, vol=vol, tot=tot, p1=p1, p2=p2, j1=j1, j2=j2, jratio=jratio,
                last_trade=last_trade, hi_trade=hi_trade, points=points, sgg_vol=sgg_vol, share=share,
                ranked=ranked, rank=rank, n_traded=n_traded, n_complex=len(ranked), similar=similar,
                similar_med=similar_med, dong_med=dong_med, tkey=tkey)


def pct(a, b):
    if not a or not b:
        return None
    return (b - a) / a * 100


def fmt_pct(v):
    if v is None:
        return "-"
    arrow = "▲" if v > 0.5 else ("▼" if v < -0.5 else "■")
    return f"{arrow} {abs(v):.1f}%"


def hh_of(t):
    return HOUSEHOLDS.get(t["key"])


# ---------------------------------------------------------------- render
def section(a):
    t = a["t"]
    hh = hh_of(t)
    hh_val = hh.get("households") if hh else None
    turnover = (a["tot"]["매매"] / hh_val * 100) if hh_val else None
    lt = a["last_trade"]
    ch = pct(a["p1"], a["p2"])
    jch = pct(a["j1"], a["j2"])

    kpis = [
        ("세대수", f"{hh_val:,}세대" if hh_val else "확인 불가",
         (hh.get("note") or "") if hh else "공동주택 단지정보 API 미연동"),
        ("12개월 매매", f"{a['tot']['매매']}건",
         f"연 회전율 {turnover:.1f}%" if turnover is not None else f"{t['sgg']} 매매의 {a['share']:.2f}%"),
        ("12개월 전월세", f"{a['tot']['전세'] + a['tot']['월세']}건", f"전세 {a['tot']['전세']} · 월세 {a['tot']['월세']}"),
        (f"최근 매매 ({a['main_area']}㎡)", won(num(lt["dealAmount"])) if lt else "-",
         f"{date(lt):%Y.%m.%d} · {lt.get('floor')}층" if lt else ""),
        ("매매 중앙값 변화", fmt_pct(ch),
         f"{won(a['p1'])} → {won(a['p2'])}" if a["p1"] and a["p2"] else "비교 구간 거래 부족"),
        ("전세가율", f"{a['jratio']:.0f}%" if a["jratio"] else "-",
         f"전세 중앙값 {won(a['j2'])} ({fmt_pct(jch)})" if a["j2"] else "최근 전세 거래 부족"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="k-label">{esc(l)}</div><div class="k-val">{esc(v)}</div>'
                       f'<div class="k-sub">{esc(s)}</div></div>' for l, v, s in kpis)

    vol_chart = bar_chart(MONTHS, [("매매", "--s1", a["vol"]["매매"]), ("전세", "--s2", a["vol"]["전세"]),
                                   ("월세", "--s3", a["vol"]["월세"])])
    sc = scatter_chart(a["points"], MONTHS)

    # 면적 구성
    area_txt = " · ".join(f"{k}㎡ {v}건" for k, v in sorted(a["areas"].items()))

    # 인근 단지 비교
    rows = []
    shown = a["ranked"][:12]
    if a["tkey"] not in [k for k, _ in shown]:
        shown = shown[:11] + [(a["tkey"], dict(a["ranked"])[a["tkey"]])] if a["tkey"] in dict(a["ranked"]) else shown
    for k, v in shown:
        hl = k == a["tkey"]
        rows.append((k[0] if k[0] != t["aptNm"] or not hl else f"★ {k[0]}", v["trade"], hl,
                     f"{k[0]} ({k[1]} {k[2]}) · {v['by']}년 준공 · 매매 {v['trade']}건 · 전월세 {v['rent']}건"))
    nb_chart = hbar_chart(rows)

    sim_rows = ""
    for k, v in a["similar"][:10]:
        hl = k == a["tkey"]
        py = statistics.median(v["py"]) if v["py"] else None
        sim_rows += (f'<tr class="{"hl" if hl else ""}"><td>{"★ " if hl else ""}{esc(k[0])}</td><td>{esc(k[2])}</td>'
                     f'<td>{esc(v["by"])}</td><td class="r">{v["trade"]}</td>'
                     f'<td class="r">{v["rent"]}</td>'
                     f'<td class="r">{won(py) if py else "-"}</td></tr>')

    # 최근 거래 내역
    recent = sorted([(date(it), "매매", it) for it in a["mt"]] +
                    [(date(it), "전세" if num(it.get("monthlyRent")) == 0 else "월세", it) for it in a["mr"]],
                    key=lambda x: x[0], reverse=True)[:15]
    rec_rows = ""
    for d, kind, it in recent:
        if kind == "매매":
            price = won(num(it["dealAmount"]))
            extra = esc(it.get("dealingGbn") or "")
        elif kind == "전세":
            price = won(num(it["deposit"]))
            extra = esc(it.get("contractType") or "")
        else:
            price = f"{won(num(it['deposit']))} / {int(num(it['monthlyRent']))}만"
            extra = esc(it.get("contractType") or "")
        rec_rows += (f'<tr><td>{d:%Y.%m.%d}</td><td><span class="tag t-{ {"매매": 1, "전세": 2, "월세": 3}[kind]}">{kind}</span></td>'
                     f'<td class="r">{price}</td><td class="r">{num(it["excluUseAr"]):.2f}㎡</td><td class="r">{esc(it.get("floor"))}층</td><td>{extra}</td></tr>')

    # 해석 문장
    notes = []
    if a["rank"]:
        notes.append(f"{t['umdNm']}에서 최근 12개월 실거래가 신고된 {a['n_complex']}개 단지 중 매매 건수 {a['rank']}위입니다 "
                     f"(동 내 단지 중앙값 {a['dong_med']:g}건, 비슷한 연식 단지 중앙값 {a['similar_med']:g}건).")
    if ch is not None:
        notes.append(f"전용 {a['main_area']}㎡ 매매 중앙값은 앞 6개월 {won(a['p1'])} → 최근 {won(a['p2'])}로 {fmt_pct(ch)} 변했습니다.")
    if a["hi_trade"]:
        h = a["hi_trade"]
        notes.append(f"기간 내 최고 매매가는 {won(num(h['dealAmount']))} ({date(h):%Y.%m.%d}, {h.get('floor')}층)입니다.")
    if a["jratio"]:
        notes.append(f"최근 전세가율은 약 {a['jratio']:.0f}%입니다.")
    sim_py = [statistics.median(v["py"]) for k, v in a["similar"] if v["py"] and k != a["tkey"]]
    my_py = dict(a["ranked"]).get(a["tkey"], {}).get("py")
    if sim_py and my_py:
        mine, others = statistics.median(my_py), statistics.median(sim_py)
        diff = pct(others, mine)
        notes.append(f"전용 평당가 {won(mine)}으로, 비슷한 연식 단지 중앙값 {won(others)}보다 {abs(diff):.0f}% {'높습니다' if diff > 0 else '낮습니다'}.")
    direct = [it for it in a["mt"] if "직거래" in str(it.get("dealingGbn") or "")]
    if direct:
        lows = ", ".join(f"{date(it):%m.%d} {won(num(it['dealAmount']))}" for it in sorted(direct, key=date))
        notes.append(f"직거래 {len(direct)}건({lows})은 시세와 차이가 날 수 있습니다.")
    extra_note = t.get("note")
    if extra_note:
        notes.append(extra_note)
    notes_html = "".join(f"<li>{esc(n)}</li>" for n in notes)

    return f"""
<section class="apt" id="{t['key']}">
  <header class="apt-head">
    <h2>{esc(t['display'])}</h2>
    <p class="muted">{esc(t['sgg'])} {esc(t['umdNm'])} {esc(t['jibun'])} · 실거래 단지명 “{esc(t['aptNm'])}” · {esc(a['build_year'])}년 준공 · 거래 면적 {esc(area_txt)}</p>
  </header>
  <div class="kpis">{kpi_html}</div>
  <ul class="notes">{notes_html}</ul>

  <h3>월별 거래량</h3>
  <div class="legend"><span><i style="background:var(--s1)"></i>매매</span><span><i style="background:var(--s2)"></i>전세</span><span><i style="background:var(--s3)"></i>월세</span></div>
  {vol_chart}

  <h3>전용 {a['main_area']}㎡ 실거래가 추이</h3>
  <div class="legend"><span><i style="background:var(--s1)"></i>매매</span><span><i style="background:var(--s2)"></i>전세</span><span class="muted">점=개별 거래, 선=월 중앙값</span></div>
  {sc}

  <h3>인근 단지 매매 거래량 비교 <span class="muted">({esc(t['umdNm'])}, 최근 12개월 상위)</span></h3>
  {nb_chart}

  <h3>비슷한 연식 단지 비교 <span class="muted">({esc(t['umdNm'])}, 준공 ±5년)</span></h3>
  <div class="tbl"><table>
    <thead><tr><th>단지</th><th>지번</th><th>준공</th><th class="r">매매</th><th class="r">전월세</th><th class="r">평당가(전용)</th></tr></thead>
    <tbody>{sim_rows}</tbody></table></div>

  <h3>최근 거래 내역</h3>
  <div class="tbl"><table>
    <thead><tr><th>계약일</th><th>구분</th><th class="r">금액</th><th class="r">전용</th><th class="r">층</th><th>비고</th></tr></thead>
    <tbody>{rec_rows}</tbody></table></div>
</section>"""


def summary_table(results):
    rows = ""
    for a in results:
        t = a["t"]
        hh = (hh_of(t) or {}).get("households")
        ch = pct(a["p1"], a["p2"])
        jr = f"{a['jratio']:.0f}%" if a["jratio"] else "-"
        rows += (f'<tr><td><a href="#{t["key"]}">{esc(t["display"])}</a></td><td class="r">{f"{hh:,}" if hh else "-"}</td>'
                 f'<td class="r">{a["tot"]["매매"]}</td><td class="r">{a["tot"]["전세"] + a["tot"]["월세"]}</td>'
                 f'<td class="r">{won(a["p2"]) if a["p2"] else "-"}</td><td class="r">{fmt_pct(ch)}</td>'
                 f'<td class="r">{jr}</td>'
                 f'<td class="r">{a["rank"]}/{a["n_complex"]}</td></tr>')
    return rows


def main():
    TARGETS[0]["note"] = ("알림 봇의 ‘건영’ 키워드는 신정동 890-13 ‘건영’(1996년 준공)도 함께 잡습니다. "
                          "이 보고서는 목동 928 건영만 분석했습니다.")
    results = [analyze(t) for t in TARGETS]
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    period = f"{MONTHS[0][:4]}.{MONTHS[0][4:]} ~ {MONTHS[-1][:4]}.{MONTHS[-1][4:]}"
    sections = "".join(section(a) for a in results)
    hh_src = HOUSEHOLDS.get("_source", "")
    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>관심단지 실거래 보고서</title>
<style>
:root {{
  color-scheme: light;
  --bg:#f6f6f4; --surface:#fcfcfb; --border:#e4e3df; --text:#0b0b0b; --text2:#52514e; --muted:#7a7974;
  --grid:#ecebe7; --axis:#c9c8c3; --neutral:#c9c8c3; --hl-row:#eef4fc;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --bg:#111110; --surface:#1a1a19; --border:#2e2d2b; --text:#f0efec; --text2:#c3c2b7; --muted:#9a998f;
    --grid:#2a2928; --axis:#4a4945; --neutral:#4f4e4a; --hl-row:#1c2a3d;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg:#111110; --surface:#1a1a19; --border:#2e2d2b; --text:#f0efec; --text2:#c3c2b7; --muted:#9a998f;
  --grid:#2a2928; --axis:#4a4945; --neutral:#4f4e4a; --hl-row:#1c2a3d;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif; }}
main {{ max-width:760px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:24px; margin:0 0 4px; letter-spacing:-.01em; }}
h2 {{ font-size:20px; margin:0; letter-spacing:-.01em; }}
h3 {{ font-size:15px; margin:28px 0 8px; color:var(--text); }}
.muted {{ color:var(--muted); font-weight:400; font-size:13px; }}
.card, .apt {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; margin-top:16px; }}
.apt-head p {{ margin:4px 0 0; }}
.kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:16px; }}
.kpi {{ border:1px solid var(--border); border-radius:10px; padding:10px 12px; }}
.k-label {{ font-size:12px; color:var(--text2); }}
.k-val {{ font-size:19px; font-weight:650; margin-top:2px; font-variant-numeric:tabular-nums; }}
.k-sub {{ font-size:12px; color:var(--muted); }}
.notes {{ margin:14px 0 0; padding-left:18px; color:var(--text2); font-size:14px; }}
.notes li {{ margin:3px 0; }}
.legend {{ display:flex; gap:14px; font-size:12px; color:var(--text2); margin-bottom:4px; flex-wrap:wrap; }}
.legend i {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:5px; vertical-align:-1px; }}
.cw {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
.chart {{ min-width:560px; width:100%; height:auto; display:block; overflow:visible; }}
.chart .grid {{ stroke:var(--grid); stroke-width:1; }}
.chart .axis {{ stroke:var(--axis); stroke-width:1; }}
.chart .tick {{ fill:var(--muted); font-size:11px; }}
.chart .ylab {{ fill:var(--text2); font-size:12px; }}
.chart .val {{ fill:var(--text2); font-size:12px; font-variant-numeric:tabular-nums; }}
.chart .hl {{ fill:var(--text); font-weight:650; }}
.chart .dot {{ stroke:var(--surface); stroke-width:2; }}
.chart .hit {{ fill:transparent; cursor:default; }}
.chart .hit:hover {{ fill:var(--text); fill-opacity:.05; }}
.tbl {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:left; padding:7px 8px; border-bottom:1px solid var(--border); white-space:nowrap; }}
th {{ color:var(--text2); font-weight:600; font-size:12px; }}
td.r, th.r {{ text-align:right; }}
tr.hl td {{ background:var(--hl-row); font-weight:600; }}
a {{ color:var(--s1); text-decoration:none; }}
.tag {{ display:inline-block; font-size:11px; padding:1px 7px; border-radius:99px; border:1px solid currentColor; color:var(--text2); }}
.tag.t-1 {{ border-color:var(--s1); }} .tag.t-2 {{ border-color:var(--s2); }} .tag.t-3 {{ border-color:var(--s3); }}
#tip {{ position:fixed; pointer-events:none; background:var(--text); color:var(--surface); font-size:12px; padding:6px 9px; border-radius:6px; opacity:0; transition:opacity .1s; max-width:280px; z-index:10; }}
.foot {{ font-size:12px; color:var(--muted); margin-top:24px; }}
.foot li {{ margin:2px 0; }}
@media (max-width:560px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} .apt, .card {{ padding:14px; }} }}
</style></head>
<body><main>
<h1>관심단지 실거래 상세 보고서</h1>
<div class="muted">분석 기간 {period} (12개월) · 작성 {now:%Y.%m.%d %H:%M} KST · 국토교통부 아파트 매매·전월세 실거래가 공개자료</div>

<div class="card">
  <h3 style="margin-top:0">요약</h3>
  <div class="tbl"><table>
    <thead><tr><th>단지</th><th class="r">세대수</th><th class="r">매매</th><th class="r">전월세</th><th class="r">최근 매매 중앙값</th><th class="r">6개월 대비</th><th class="r">전세가율</th><th class="r">동 내 매매 순위</th></tr></thead>
    <tbody>{summary_table(results)}</tbody></table></div>
</div>
{sections}
<ul class="foot">
  <li>거래량은 계약일 기준이며, 실거래 신고 기한(계약 후 30일) 때문에 최근 1~2개월은 이후 늘어날 수 있습니다. {CUR_MONTH[:4]}.{CUR_MONTH[4:]} 진행 중 거래는 가격 추이와 최근 거래 내역에만 포함했습니다.</li>
  <li>매매 중앙값 변화는 대표 면적 기준, 앞 6개월과 최근 6개월(이번 달 포함)의 중앙값을 비교했습니다. 해제(취소)된 매매 신고는 제외했습니다.</li>
  <li>전세가율 = 최근 6개월 전세 보증금 중앙값 ÷ 매매가 중앙값 (같은 대표 면적).</li>
  <li>평당가는 전용면적 3.3058㎡ 기준이며, 인근 단지는 같은 법정동에서 기간 내 거래가 신고된 단지입니다.</li>
  <li>매매 회전율 = 12개월 매매 건수 ÷ 세대수. {esc(hh_src)}</li>
</ul>
</main>
<div id="tip"></div>
<script>
(function(){{
  var tip=document.getElementById('tip');
  document.addEventListener('pointerover',function(e){{
    var t=e.target.closest&&e.target.closest('[data-tip]');
    if(!t){{tip.style.opacity=0;return;}}
    tip.textContent=t.getAttribute('data-tip');tip.style.opacity=1;
  }});
  document.addEventListener('pointermove',function(e){{
    var x=Math.min(e.clientX+12, window.innerWidth-tip.offsetWidth-8);
    tip.style.left=x+'px';tip.style.top=(e.clientY+14)+'px';
  }});
}})();
</script>
</body></html>"""
    with open(os.path.join(HERE, "apt_report.html"), "w", encoding="utf-8") as f:
        f.write(doc)
    for a in results:
        print(a["t"]["display"], a["tot"], a["main_area"], a["p1"], a["p2"], a["jratio"], a["rank"], a["n_complex"])


if __name__ == "__main__":
    main()
