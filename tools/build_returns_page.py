#!/usr/bin/env python3
"""Build research-2026-08/returns/index.html from live market data.

Total return = adjusted-close ratio (Yahoo back-adjusts for splits AND cash
dividends, which equals reinvesting each dividend at the ex-date close).
Price-only return = split-adjusted Close ratio, so the gap between the two is
the dividend contribution in percentage points.

Run:  python3 tools/build_returns_page.py
"""
import html
import os

import pandas as pd
import yfinance as yf

OUT = os.path.join(os.path.dirname(__file__), "..", "research-2026-08",
                   "returns", "index.html")

# (ticker, chinese name, subtitle, group)  group: core | peer | bench
NAMES = [
    ("NVDA", "NVIDIA 英伟达",       "AI 算力霸主",          "core"),
    ("MU",   "Micron 美光",         "HBM4 / DRAM 超级周期", "core"),
    ("LITE", "Lumentum",            "EML 激光芯片",         "core"),
    ("COHR", "Coherent",            "光模块 / SiC",         "core"),
    ("SNDK", "SanDisk 闪迪",        "WDC 分拆 · 企业级 SSD","core"),
    ("GOOG", "Alphabet 谷歌",       "Gemini 全栈 AI",       "core"),
    ("TSLA", "Tesla 特斯拉",        "FSD / Robotaxi",       "core"),
    ("PLTR", "Palantir",            "AIP 商业化",           "core"),
    ("DHR",  "Danaher 丹纳赫",      "生物医药卖铲人",       "core"),
    ("ALNY", "Alnylam",             "RNAi 龙头",            "core"),
    ("MRNA", "Moderna",             "mRNA 平台",            "core"),
    ("MRVI", "Maravai",             "CleanCap 耗材",        "core"),
    ("NTLA", "Intellia",            "体内 CRISPR",          "core"),
    ("META", "Meta Platforms",      "社交 / Llama",         "peer"),
    ("KO",   "Coca-Cola 可口可乐",  "股息复利典范",         "peer"),
    ("AXP",  "American Express",    "支付 / 巴菲特重仓",    "peer"),
    ("SPY",  "标普 500 ETF",        "美股大盘基准",         "bench"),
    ("QQQ",  "纳斯达克 100 ETF",    "成长股基准",           "bench"),
    ("XBI",  "生物科技 ETF",        "生物科技基准",         "bench"),
]
GROUP_LABEL = {"core": "研报标的", "peer": "对照标的", "bench": "指数基准"}
# Categorical palette — validated for the #070914 dark surface (lightness band,
# chroma floor, CVD separation, normal-vision floor, contrast) via the dataviz
# validator with --pairs all. Do not substitute by eye.
GROUP_COLOR = {"core": "#14a3b8", "peer": "#c2810c", "bench": "#9061f9"}

# Why a window is missing, for the tickers whose history is too short.
SHORT = {"MRNA": "2018-12 IPO", "MRVI": "2020-11 IPO",
         "PLTR": "2020-09 直接上市", "SNDK": "2025-02 自 WDC 分拆"}

ASOF = [None]        # filled by load(); the charts label their own real start dates
FIRST_PULLED = None  # earliest date in the pull, used to flag window-edge starts

WINDOWS = [("y10", 10, "10 年"), ("y5", 5, "5 年"),
           ("y3", 3, "3 年"), ("y1", 1, "1 年")]


def load():
    tk = [t for t, *_ in NAMES]
    adj = yf.download(tk, period="11y", auto_adjust=True,
                      progress=False, actions=False)["Close"]
    raw = yf.download(tk, period="11y", auto_adjust=False,
                      progress=False, actions=False)["Close"]
    rows = {}
    for t in tk:
        a, r = adj[t].dropna(), raw[t].dropna()
        rec = {"first": a.index[0].date(), "last": float(r.iloc[-1])}
        for key, yrs, _ in WINDOWS:
            end = a.index[-1]
            start = end - pd.DateOffset(years=yrs)
            if a.index[0] > start + pd.Timedelta(days=10):
                rec[key] = None
                continue
            sub = a.loc[:start]
            d = sub.index[-1]
            tr = float(a.iloc[-1] / sub.iloc[-1] - 1)
            years = (end - d).days / 365.25
            rec[key] = {"tr": tr, "cagr": (1 + tr) ** (1 / years) - 1,
                        "px": float(r.iloc[-1] / r.loc[:d].iloc[-1] - 1),
                        "from": d.date(), "p0": float(sub.iloc[-1])}
        rows[t] = rec
    global FIRST_PULLED
    FIRST_PULLED = adj.index[0].date()
    ASOF[0] = adj.index[-1].date()
    return rows, ASOF[0]


def pct(x, d=1):
    return "—" if x is None else f"{x * 100:,.{d}f}%"


def signed(x, d=1):
    return "—" if x is None else f"{'+' if x >= 0 else ''}{x * 100:,.{d}f}%"


def cls(x):
    return "" if x is None else (" pos" if x >= 0 else " neg")


def bars(rows, key, title, note):
    """Ranked horizontal bars, one measure, zero baseline. Each bar carries its
    value in a right-hand column (never overlapping a neighbour), and the group
    legend above carries identity."""
    items = [(t, n, s, g, rows[t][key]) for t, n, s, g in NAMES if rows[t][key]]
    items.sort(key=lambda x: x[4]["cagr"], reverse=True)
    lo = min(0.0, min(i[4]["cagr"] for i in items))
    hi = max(i[4]["cagr"] for i in items)
    pad = (hi - lo) * 0.02
    lo, hi = lo - pad, hi + pad
    span = hi - lo
    zero = (0 - lo) / span * 100

    span_txt = f'{max(i[4]["from"] for i in items)} → {ASOF[0]}｜{note}'
    out = [f'<div class="chart"><div class="chart-hd"><h3>{title}</h3>',
           f'<span class="chart-sub">{span_txt}</span></div>',
           f'<div class="plot" style="--zero:{zero:.3f}%">']
    for t, n, s, g, d in items:
        c = d["cagr"]
        x = (c - lo) / span * 100
        left, width = (zero, x - zero) if c >= 0 else (x, zero - x)
        tip = (f'{n}｜年化 {signed(c)}｜区间总回报 {signed(d["tr"])}'
               f'｜起算 {d["from"]}')
        out.append(
            f'<div class="row"><div class="rl"><b>{t}</b></div>'
            f'<div class="track" data-tip="{html.escape(tip, quote=True)}">'
            f'<i class="bar" style="left:{left:.3f}%;width:{max(width, 0.4):.3f}%;'
            f'background:{GROUP_COLOR[g]}"></i></div>'
            f'<div class="rv{cls(c)}">{signed(c)}</div></div>')
    out.append("</div></div>")
    return "\n".join(out)


def main():
    rows, asof = load()

    ranked = sorted((r for r in NAMES if rows[r[0]]["y10"]),
                    key=lambda r: rows[r[0]]["y10"]["cagr"], reverse=True)
    spy10 = rows["SPY"]["y10"]["cagr"]
    beat = [r[0] for r in ranked if r[3] == "core" and
            rows[r[0]]["y10"]["cagr"] > spy10]
    core10 = [r[0] for r in NAMES if r[3] == "core" and rows[r[0]]["y10"]]
    best, worst = ranked[0][0], ranked[-1][0]

    # dividend contribution over 10Y, biggest first
    div = sorted(((t, n, g, rows[t]["y10"]) for t, n, s, g in NAMES
                  if rows[t]["y10"]),
                 key=lambda x: x[3]["tr"] - x[3]["px"], reverse=True)

    def trow(t, n, s, g):
        r = rows[t]
        note = SHORT.get(t, "")
        tds = ""
        for key, _, _ in WINDOWS:
            d = r[key]
            if d is None:
                tds += f'<td class="num na" title="{note}">—</td><td class="num na">—</td>'
            else:
                tds += (f'<td class="num{cls(d["tr"])}">{signed(d["tr"])}</td>'
                        f'<td class="num sub{cls(d["cagr"])}">{signed(d["cagr"])}</td>')
        # r["first"] is the edge of the 11-year pull, not a listing date, unless
        # the ticker actually started trading inside the window.
        edge = r["first"] <= FIRST_PULLED + pd.Timedelta(days=3)
        first = (f'<span title="早于本表取数窗口，非上市日">&le;{r["first"]}</span>'
                 if edge else f'{r["first"]}')
        return (f'<tr data-g="{g}"><td class="tk">'
                f'<i class="dot" style="background:{GROUP_COLOR[g]}"></i>'
                f'<b>{t}</b><span class="nm">{n}</span>'
                f'<span class="sb">{s}</span></td>{tds}'
                f'<td class="num sub">{first}</td></tr>')

    body_rows = "\n".join(trow(*x) for x in NAMES)

    div_rows = "\n".join(
        f'<tr><td class="tk"><i class="dot" style="background:{GROUP_COLOR[g]}">'
        f'</i><b>{t}</b><span class="nm">{n}</span></td>'
        f'<td class="num{cls(d["tr"])}">{signed(d["tr"])}</td>'
        f'<td class="num{cls(d["px"])}">{signed(d["px"])}</td>'
        f'<td class="num acc">{(d["tr"]-d["px"])*100:+,.1f} pp</td>'
        f'<td class="num sub">{(d["tr"]-d["px"])/abs(d["tr"])*100:,.0f}%</td></tr>'
        for t, n, g, d in div)

    legend = "".join(
        f'<span class="lg"><i style="background:{GROUP_COLOR[g]}"></i>{l}</span>'
        for g, l in GROUP_LABEL.items())

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>研报标的全收益对照表 (含股息再投资) · 10年 / 5年 | Research August 2026</title>
<meta name="description" content="research-2026-08 全部研报标的的 10 年 / 5 年 / 3 年 / 1 年总回报与年化收益，含股息再投资，并与 META、KO、AXP 及 SPY/QQQ/XBI 基准对照。数据截至 {asof}。">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg-dark:#070914; --bg-card:rgba(18,22,40,.78); --bg-card-hover:rgba(26,32,58,.9);
  --border-color:rgba(255,255,255,.08); --accent-cyan:#00f2fe; --accent-purple:#9d4edd;
  --text-primary:#f3f4f6; --text-secondary:#9ca3af; --text-muted:#6b7280;
  --pos:#34d399; --neg:#f87171;
  --font-sans:'Plus Jakarta Sans','Inter',-apple-system,sans-serif;
  --mono:'SF Mono',ui-monospace,'Menlo','Consolas',monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background-color:var(--bg-dark);color:var(--text-primary);font-family:var(--font-sans);
 line-height:1.6;min-height:100vh;padding:30px 20px 80px;
 background-image:radial-gradient(circle at 10% 10%,rgba(0,242,254,.06) 0%,transparent 40%),
 radial-gradient(circle at 90% 90%,rgba(157,78,221,.06) 0%,transparent 40%)}}
.container{{max-width:1280px;margin:0 auto}}
header{{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;
 padding:24px 30px;background:rgba(13,19,31,.85);backdrop-filter:blur(16px);
 border:1px solid var(--border-color);border-radius:20px;margin-bottom:28px}}
.header-title h1{{font-size:1.6rem;font-weight:800;
 background:linear-gradient(90deg,#fff,var(--accent-cyan));
 -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.header-title p{{font-size:.88rem;color:var(--text-secondary)}}
.back-btn{{background:rgba(255,255,255,.05);border:1px solid var(--border-color);
 color:var(--accent-cyan);padding:8px 16px;border-radius:12px;font-size:.85rem;
 font-weight:600;text-decoration:none;transition:all .25s ease;white-space:nowrap}}
.back-btn:hover{{background:rgba(0,242,254,.15);border-color:var(--accent-cyan)}}
.section-header{{display:flex;align-items:center;gap:12px;margin:40px 0 18px;flex-wrap:wrap}}
.section-title{{font-size:1.25rem;font-weight:700;color:#fff}}
.badge{{background:rgba(0,242,254,.12);color:var(--accent-cyan);padding:4px 12px;
 border-radius:20px;font-size:.75rem;font-weight:700}}
.panel{{background:var(--bg-card);backdrop-filter:blur(16px);border:1px solid var(--border-color);
 border-radius:18px;padding:24px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}
.tile{{background:var(--bg-card);border:1px solid var(--border-color);border-radius:16px;padding:20px 22px}}
.tile .k{{font-size:.78rem;color:var(--text-secondary);font-weight:600;letter-spacing:.02em}}
.tile .v{{font-size:1.85rem;font-weight:800;font-family:var(--mono);margin:4px 0 2px;line-height:1.15}}
.tile .n{{font-size:.78rem;color:var(--text-muted)}}
.pos{{color:var(--pos)}} .neg{{color:var(--neg)}} .acc{{color:var(--accent-cyan)}}
.lead{{font-size:.92rem;color:var(--text-secondary);max-width:88ch}}
.lead b{{color:var(--text-primary);font-weight:600}}
.legend{{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:18px}}
.lg{{display:flex;align-items:center;gap:7px;font-size:.8rem;color:var(--text-secondary);font-weight:600}}
.lg i{{width:11px;height:11px;border-radius:3px;display:inline-block}}
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:20px}}
.chart{{background:var(--bg-card);border:1px solid var(--border-color);border-radius:18px;padding:22px 24px}}
.chart-hd{{margin-bottom:14px}}
.chart-hd h3{{font-size:1rem;font-weight:700;color:#fff}}
.chart-sub{{font-size:.78rem;color:var(--text-muted)}}
.plot{{position:relative}}
.row{{display:flex;align-items:center;gap:10px;height:24px}}
.rl{{width:66px;flex:none;font-size:.78rem;color:var(--text-secondary);font-family:var(--mono)}}
.rl b{{color:var(--text-primary);font-weight:600}}
.rv{{width:62px;flex:none;text-align:right;font-size:.74rem;font-family:var(--mono);
 font-weight:600;font-variant-numeric:tabular-nums;color:var(--text-secondary)}}
.track{{position:relative;flex:1;height:100%;min-width:0}}
/* zero baseline, drawn inside the track so it needs no cross-unit calc */
.track::before{{content:'';position:absolute;top:0;bottom:0;left:var(--zero);
 width:1px;background:rgba(255,255,255,.2)}}
.bar{{position:absolute;top:6px;height:12px;border-radius:3px;display:block;
 transition:filter .15s ease}}
.track:hover .bar{{filter:brightness(1.3)}}
/* hover layer: the row's own values, without leaning on the native title delay */
.track[data-tip]:hover::after{{content:attr(data-tip);position:absolute;left:0;top:-34px;
 z-index:5;background:rgba(9,13,26,.97);border:1px solid var(--border-color);
 border-radius:9px;padding:6px 10px;font-size:.74rem;font-weight:500;
 color:var(--text-primary);white-space:nowrap;pointer-events:none;
 box-shadow:0 8px 24px rgba(0,0,0,.55)}}
.row:first-child .track[data-tip]:hover::after{{top:22px}}
.tablewrap{{overflow-x:auto;border:1px solid var(--border-color);border-radius:18px;background:var(--bg-card)}}
table{{border-collapse:collapse;width:100%;min-width:940px;font-size:.85rem}}
th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid rgba(255,255,255,.05);white-space:nowrap}}
thead th{{position:sticky;top:0;background:rgba(13,19,31,.97);backdrop-filter:blur(8px);
 font-size:.72rem;font-weight:700;color:var(--text-secondary);letter-spacing:.03em;
 text-transform:uppercase;user-select:none;white-space:nowrap}}
thead th[data-col]{{cursor:pointer}}
thead th[data-col]:hover{{color:var(--accent-cyan)}}
thead th[data-dir]{{color:var(--accent-cyan)}}
thead th[data-dir="desc"]::after{{content:' \\2193'}}
thead th[data-dir="asc"]::after{{content:' \\2191'}}
thead th.grp{{text-align:center;border-bottom:1px solid var(--border-color);cursor:default}}
tbody tr:hover{{background:rgba(255,255,255,.035)}}
td.num{{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}}
td.sub{{color:var(--text-muted);font-size:.78rem}}
td.na{{color:var(--text-muted)}}
td.tk b{{font-weight:700;color:#fff;margin-right:8px}}
td.tk .nm{{color:var(--text-secondary);font-size:.8rem}}
td.tk .sb{{display:block;color:var(--text-muted);font-size:.72rem;padding-left:19px}}
.dot{{width:9px;height:9px;border-radius:3px;display:inline-block;margin-right:8px;vertical-align:1px}}
.notes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-top:8px}}
.note{{background:var(--bg-card);border:1px solid var(--border-color);border-radius:16px;padding:20px 22px}}
.note h4{{font-size:.92rem;font-weight:700;color:#fff;margin-bottom:8px}}
.note p,.note li{{font-size:.83rem;color:var(--text-secondary);line-height:1.65}}
.note ul{{padding-left:18px}} .note li{{margin-bottom:6px}}
.note code{{font-family:var(--mono);font-size:.78rem;color:var(--accent-cyan);
 background:rgba(0,242,254,.08);padding:1px 6px;border-radius:5px}}
.warn{{border-color:rgba(248,113,113,.28)}}
.warn h4{{color:var(--neg)}}
footer{{text-align:center;margin-top:60px;color:var(--text-secondary);font-size:.82rem;
 border-top:1px solid var(--border-color);padding-top:30px}}
@media (max-width:640px){{
  body{{padding:16px 12px 60px}} header{{padding:20px}}
  .header-title h1{{font-size:1.25rem}}
  .rl{{width:52px}} .rv{{width:56px}} .charts{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>
<div class="container">

<header>
  <div class="header-title">
    <h1>全收益对照表 · 含股息再投资</h1>
    <p>Total Return with Dividends Reinvested · research-2026-08 全部标的 + META / KO / AXP 对照 + 三大基准 · 数据截至 {asof}</p>
  </div>
  <a href="../index.html" class="back-btn">&larr; 返回 2026年8月研报导航</a>
</header>

<p class="lead">下表为<b>总回报（Total Return）</b>：假设期间每一笔现金股息都在除息日收盘价<b>全额再投资</b>，并已还原全部拆股。
计算口径为复权收盘价之比 <code>P_adj(末) / P_adj(初) − 1</code>；年化列为对应的几何年化收益（CAGR）。
上市不足对应年限的标的以 <b>—</b> 标注，不做任何填补或回溯拼接。</p>

<div class="section-header"><div class="section-title">📌 关键结论</div><div class="badge">10 年窗口</div></div>
<div class="tiles">
  <div class="tile"><div class="k">10 年最佳 · {best}</div>
    <div class="v pos">{signed(rows[best]['y10']['cagr'])}</div>
    <div class="n">年化 · 区间总回报 {signed(rows[best]['y10']['tr'], 0)}</div></div>
  <div class="tile"><div class="k">10 年最差 · {worst}</div>
    <div class="v neg">{signed(rows[worst]['y10']['cagr'])}</div>
    <div class="n">年化 · 区间总回报 {signed(rows[worst]['y10']['tr'], 0)}</div></div>
  <div class="tile"><div class="k">标普 500 (SPY) 基准</div>
    <div class="v acc">{signed(spy10)}</div>
    <div class="n">年化 · 区间总回报 {signed(rows['SPY']['y10']['tr'], 0)}</div></div>
  <div class="tile"><div class="k">跑赢 SPY 的研报标的</div>
    <div class="v">{len(beat)} / {len(core10)}</div>
    <div class="n">{'、'.join(beat)}</div></div>
</div>

<div class="section-header"><div class="section-title">📊 年化收益率排名（CAGR）</div>
  <div class="badge">含股息再投资</div></div>
<div class="legend">{legend}<span class="lg" style="color:var(--text-muted)">悬停查看区间总回报与起算日</span></div>
<div class="charts">
{bars(rows, 'y10', '10 年年化收益率', '上市不足 10 年者不参与排名')}
{bars(rows, 'y5', '5 年年化收益率', '上市不足 5 年者不参与排名')}
</div>

<div class="section-header"><div class="section-title">📋 完整对照表</div>
  <div class="badge">点击表头排序</div></div>
<div class="tablewrap">
<table id="main">
<thead>
  <tr>
    <th rowspan="2" data-col="0" data-text>标的</th>
    <th class="grp" colspan="2">10 年</th><th class="grp" colspan="2">5 年</th>
    <th class="grp" colspan="2">3 年</th><th class="grp" colspan="2">1 年</th>
    <th rowspan="2" data-col="9" data-text>数据起点</th>
  </tr>
  <tr>
    <th data-col="1">总回报</th><th data-col="2">年化</th>
    <th data-col="3">总回报</th><th data-col="4">年化</th>
    <th data-col="5">总回报</th><th data-col="6">年化</th>
    <th data-col="7">总回报</th><th data-col="8">年化</th>
  </tr>
</thead>
<tbody>
{body_rows}
</tbody>
</table>
</div>

<div class="section-header"><div class="section-title">💰 股息对 10 年回报的贡献</div>
  <div class="badge">总回报 − 纯价格回报</div></div>
<p class="lead">这一栏说明<b>为什么必须用总回报口径</b>。对本组研报标的（除 DHR / GOOG / MU / NVDA 外均不分红）股息几乎不影响结论；
但对 KO、AXP 与 SPY 这类分红资产，只看股价会系统性低估其真实回报——KO 有近四成的十年回报来自股息再投资。</p>
<div class="tablewrap">
<table id="div">
<thead><tr><th data-col="0" data-text>标的</th><th data-col="1">10 年总回报</th>
<th data-col="2">纯价格回报</th><th data-col="3">股息贡献</th><th data-col="4">占总回报比重</th></tr></thead>
<tbody>
{div_rows}
</tbody>
</table>
</div>

<div class="section-header"><div class="section-title">🔬 方法与口径</div></div>
<div class="notes">
  <div class="note">
    <h4>怎么算出来的</h4>
    <p>数据源为 Yahoo Finance 日线复权收盘价（<code>yfinance</code>，<code>auto_adjust=True</code>）。
    Yahoo 的复权价对拆股与现金分红同时做后向调整，在数学上等价于<b>每笔股息于除息日收盘价再投资</b>，
    因此无需另行模拟 DRIP。纯价格回报列使用未做分红调整、但已做拆股调整的收盘价。</p>
    <p style="margin-top:10px">生成脚本：<code>tools/build_returns_page.py</code>（本页）与
    <code>tools/total_returns.py</code>（命令行表格）。重跑即刷新全部数字。</p>
  </div>
  <div class="note">
    <h4>窗口如何取</h4>
    <ul>
      <li>末点为最近一个交易日（{asof}）。</li>
      <li>起点为“末点减 N 年”当日或之前的最后一个交易日，因此实际年数可能略偏离整数，年化按实际天数 / 365.25 计算。</li>
      <li>上市不足窗口长度者标 <b>—</b>：{'；'.join(f'{k} {v}' for k, v in SHORT.items())}。</li>
    </ul>
  </div>
  <div class="note warn">
    <h4>⚠️ 三点必须注意的偏差</h4>
    <ul>
      <li><b>SPCX 无市场数据。</b>SpaceX 为非上市公司，研报目录中唯一无法计算回报的标的，本页不含该标的。</li>
      <li><b>DHR 的 10 年回报被低估。</b>Danaher 期间分拆了 Fortive (2016)、Envista (2019) 与 Veralto (2023)，
      而 Yahoo 复权价<b>不计入分拆所得股份</b>。表中 DHR 数字仅代表母公司股票本身，真实持有人回报显著更高。同理适用于 SNDK 自 WDC 分拆前的历史。</li>
      <li><b>存在幸存者偏差。</b>本表是用“今天的标的清单”回看历史，可以回答“这只股票过去表现如何”，
      但不能回答“当年我能否选中它”——十年前的可选集合远比这份清单大且噪音更多。</li>
    </ul>
  </div>
  <div class="note">
    <h4>本表未包含的成本</h4>
    <p>数字为<b>税前、免佣金</b>的理论总回报，未扣除股息预扣税、买卖价差与交易费用，也未考虑实际建仓的时间分布
    （单点买入 vs. 定投的结果可能相差很大）。用于横向对比标的相对表现是合适的，直接等同于个人账户实际收益则不合适。</p>
  </div>
</div>

<footer>
  <p>© 2026 Financial Research Repository · 全收益对照表（含股息再投资）· 数据截至 {asof} · 由 <code>tools/build_returns_page.py</code> 自动生成</p>
</footer>
</div>

<script>
// Sorting: every sortable header carries data-col, so nothing has to be inferred
// from rowspan/colspan. Numeric columns sort on the parsed percentage; columns
// marked data-text sort as strings. Missing values ("—") always sink.
document.querySelectorAll('table').forEach(function (table) {{
  var body = table.tBodies[0];
  table.querySelectorAll('th[data-col]').forEach(function (th) {{
    var col = +th.dataset.col, isText = th.hasAttribute('data-text'), desc = !isText;
    th.addEventListener('click', function () {{
      table.querySelectorAll('th[data-col]').forEach(function (o) {{
        if (o !== th) o.removeAttribute('data-dir');
      }});
      var num = function (cell) {{
        var v = parseFloat(cell.textContent.replace(/[^0-9.+-]/g, ''));
        return isNaN(v) ? null : v;
      }};
      Array.prototype.slice.call(body.rows).sort(function (a, b) {{
        var x = a.cells[col], y = b.cells[col];
        if (isText) {{
          return x.textContent.trim().localeCompare(y.textContent.trim()) * (desc ? -1 : 1);
        }}
        var va = num(x), vb = num(y);
        if (va === null && vb === null) return 0;
        if (va === null) return 1;          // "—" sinks in both directions
        if (vb === null) return -1;
        return desc ? vb - va : va - vb;
      }}).forEach(function (r) {{ body.appendChild(r); }});
      th.dataset.dir = desc ? 'desc' : 'asc';
      desc = !desc;
    }});
  }});
}});
</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"wrote {os.path.normpath(OUT)}  (as of {asof})")


if __name__ == "__main__":
    main()
