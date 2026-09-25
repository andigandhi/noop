#!/usr/bin/env python3
"""Webserver, der den Verlauf von WHOOP 5/MG R18-Byte 82 aus einer NOOP-Datenbank anzeigt.

Byte 82 ist der unbestätigte SpO2-Kandidat (`spo2_candidate_82`). NOOP speichert ihn roh im Slot
`aux_byte_82` der Tabelle `v18AuxSample` (Blob-Format siehe android/.../data/V18AuxCodec.kt bzw.
Packages/WhoopStore/Sources/WhoopStore/V18Aux.swift). Der Nachtmittelwert folgt
`AnalyticsEngine.nightlySpo2CandidateMean`: nur Werte 70-100 innerhalb einer Schlafsession, gerundet.

Nur Standardbibliothek, die Datenbank wird schreibgeschützt geöffnet.

    python3 byte82_server.py [--db PFAD] [--host 127.0.0.1] [--port 8082] [--device ID]
"""

import argparse
import json
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "Database" / "noop-backup.sqlite"

# V18AuxCodec: Byte 0 = Formatversion, Bytes 1..4 = u32-Präsenz-Bitmap (LE), danach die vorhandenen
# Slots in aufsteigender Slot-Reihenfolge. Breiten der Slots vor aux_byte_82 (Index 11).
AUX_FORMAT_VERSION = 2
AUX_HEADER_BYTES = 5
AUX_SLOT_WIDTHS = [4, 1, 1, 1, 1, 2, 1, 1, 2, 2, 2]  # Slots 0..10
AUX_BYTE_82_INDEX = 11

CANDIDATE_RANGE = (70, 100)


def decode_byte82(blob):
    """Liefert den rohen Byte-82-Wert oder None, wenn der Slot fehlt bzw. der Blob ungültig ist."""
    if len(blob) < AUX_HEADER_BYTES or blob[0] != AUX_FORMAT_VERSION:
        return None
    bitmap = int.from_bytes(blob[1:5], "little")
    if not bitmap >> AUX_BYTE_82_INDEX & 1:
        return None
    offset = AUX_HEADER_BYTES
    for index, width in enumerate(AUX_SLOT_WIDTHS):
        if bitmap >> index & 1:
            offset += width
    return blob[offset] if offset < len(blob) else None


def pick_device(conn, requested):
    rows = conn.execute(
        "SELECT deviceId, COUNT(*) FROM v18AuxSample GROUP BY deviceId ORDER BY COUNT(*) DESC"
    ).fetchall()
    if not rows:
        sys.exit("Keine Zeilen in v18AuxSample gefunden.")
    if requested:
        if requested not in {r[0] for r in rows}:
            sys.exit(f"Gerät {requested!r} nicht gefunden. Vorhanden: {[r[0] for r in rows]}")
        return requested, rows
    return rows[0][0], rows


def load_data(db_path, requested_device):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        device, devices = pick_device(conn, requested_device)

        points = []          # [ts, wert] für alle Werte != 0
        coverage = {}        # 10-Minuten-Bucket -> Anzahl Records (inkl. Nullwerte)
        total = zeros = missing = 0
        for ts, blob in conn.execute(
            "SELECT ts, fields FROM v18AuxSample WHERE deviceId = ? ORDER BY ts", (device,)
        ):
            value = decode_byte82(blob)
            if value is None:
                missing += 1
                continue
            total += 1
            bucket = ts - ts % 600
            coverage[bucket] = coverage.get(bucket, 0) + 1
            if value == 0:
                zeros += 1
            else:
                points.append([ts, value])

        # Computed Sessions liegen unter "<gerät>-noop", importierte/ältere unter der Geräte-ID selbst.
        sessions = []
        for start, end in conn.execute(
            "SELECT startTs, endTs FROM sleepSession WHERE deviceId IN (?, ?) ORDER BY startTs",
            (device, device + "-noop"),
        ):
            if end > start:
                sessions.append([start, end])
    finally:
        conn.close()

    lo, hi = CANDIDATE_RANGE
    nights = []
    for start, end in sessions:
        vals = [v for ts, v in points if start <= ts <= end and lo <= v <= hi]
        # v18AuxSample wird erst seit einem App-Update gespeichert: Nächte davor haben keine Aux-Daten,
        # und "kein Kandidat" hieße dort nur "nichts gespeichert".
        aux_records = sum(n for bucket, n in coverage.items() if start - 599 <= bucket <= end)
        nights.append({
            "start": start,
            "end": end,
            "auxCoverage": min(1.0, aux_records / (end - start + 1)),
            "mean": round(sum(vals) / len(vals)) if vals else None,
            "meanExact": sum(vals) / len(vals) if vals else None,
            "n": len(vals),
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        })

    return {
        "device": device,
        "devices": [{"id": d, "rows": n} for d, n in devices],
        "candidateRange": list(CANDIDATE_RANGE),
        "stats": {"records": total, "zeros": zeros, "nonzero": len(points), "slotMissing": missing},
        "points": points,
        "coverage": sorted(coverage.items()),
        "sessions": sessions,
        "nights": nights,
    }


PAGE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Byte-82-Verlauf</title>
<style>
:root {
  color-scheme: light;
  --surface-0: #f4f4f2;
  --surface-1: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #77766f;
  --grid: #e4e3de;
  --axis: #b9b8b0;
  --band: #2a78d614;
  --sleep: #0b0b0b0d;
  --series-1: #2a78d6;   /* Kandidat 70-100 */
  --series-2: #eb6834;   /* andere Werte */
  --border: #dedcd5;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface-0: #111110;
    --surface-1: #1a1a19;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #96958c;
    --grid: #2c2c2a;
    --axis: #55554f;
    --band: #3987e520;
    --sleep: #ffffff0f;
    --series-1: #3987e5;
    --series-2: #d95926;
    --border: #32322f;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0: #111110;
  --surface-1: #1a1a19;
  --text-primary: #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted: #96958c;
  --grid: #2c2c2a;
  --axis: #55554f;
  --band: #3987e520;
  --sleep: #ffffff0f;
  --series-1: #3987e5;
  --series-2: #d95926;
  --border: #32322f;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px 16px 48px;
  background: var(--surface-0); color: var(--text-primary);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 1200px; margin: 0 auto; }
h1 { font-size: 20px; margin: 0 0 4px; }
.sub { color: var(--text-secondary); margin: 0 0 16px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px; }
.filters button, .filters select, .filters input {
  font: inherit; color: var(--text-primary); background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 6px; padding: 5px 10px;
}
.filters button[aria-pressed="true"] { border-color: var(--series-1); color: var(--series-1); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-bottom: 16px; }
.tile { background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; }
.tile .v { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile .l { color: var(--text-secondary); font-size: 12px; }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 8px; padding: 14px 14px 8px; margin-bottom: 16px; position: relative; }
.card h2 { font-size: 15px; margin: 0 0 2px; }
.card p.note { color: var(--text-secondary); font-size: 12px; margin: 0 0 8px; }
.legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; background: var(--k); }
.legend span.box::before { border-radius: 2px; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { fill: var(--text-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.tip {
  position: absolute; pointer-events: none; display: none; z-index: 5;
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 6px;
  padding: 6px 9px; font-size: 12px; box-shadow: 0 2px 8px #0003; white-space: nowrap;
}
.tip strong { font-size: 14px; }
.tip .k { display: inline-block; width: 12px; height: 2px; vertical-align: middle; margin-right: 6px; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 4px 8px; border-bottom: 1px solid var(--grid); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--text-secondary); font-weight: 500; }
details summary { cursor: pointer; color: var(--text-secondary); margin: 4px 0 8px; }
.warn { color: var(--text-secondary); font-size: 12px; border-left: 3px solid var(--series-2); padding-left: 8px; }
</style>
</head>
<body>
<main>
  <h1>WHOOP 5/MG · R18 Byte 82</h1>
  <p class="sub" id="sub">Lade Daten …</p>

  <div class="filters" role="group" aria-label="Zeitraum">
    <button data-range="all" aria-pressed="true">Alles</button>
    <button data-range="30">30 Tage</button>
    <button data-range="7">7 Tage</button>
    <select id="night" aria-label="Einzelne Nacht"><option value="">Nacht wählen …</option></select>
    <label><input type="checkbox" id="onlyCand"> nur 70–100</label>
  </div>

  <div class="stats" id="stats"></div>

  <section class="card">
    <h2>Rohwerte von Byte 82 (≠ 0)</h2>
    <p class="note">Jeder Punkt ist ein R18-Record. Nullwerte (außerhalb der Messfenster) sind ausgeblendet. Grau hinterlegt: erkannte Schlafsessions. Blaues Band: Kandidatenbereich 70–100.</p>
    <div class="legend">
      <span style="--k: var(--series-1)">Wert 70–100 (SpO₂-Kandidat)</span>
      <span style="--k: var(--series-2)">anderer Wert (vermutlich Flags/Status)</span>
      <span class="box" style="--k: var(--sleep); outline: 0">Schlafsession</span>
    </div>
    <svg id="scatter" role="img" aria-label="Streudiagramm der Byte-82-Werte über die Zeit"></svg>
    <div class="tip" id="tipScatter"></div>
  </section>

  <section class="card">
    <h2>Nachtmittel (70–100 innerhalb der Schlafsession)</h2>
    <p class="note">Entspricht <code>AnalyticsEngine.nightlySpo2CandidateMean</code>. Nächte ohne Kandidatenwert fehlen. „Aux-Abdeckung“ = Anteil der Nacht, für den überhaupt R18-Zusatzdaten gespeichert sind.</p>
    <svg id="nights" role="img" aria-label="Balkendiagramm der Nachtmittel"></svg>
    <div class="tip" id="tipNights"></div>
    <details>
      <summary>Tabelle</summary>
      <table id="table"><thead><tr><th>Nacht (Ende)</th><th>Start</th><th>Ende</th><th>Mittel</th><th>exakt</th><th>Min</th><th>Max</th><th>Werte</th><th>Aux-Abdeckung</th></tr></thead><tbody></tbody></table>
    </details>
  </section>

  <section class="card">
    <h2>Datenabdeckung</h2>
    <p class="note">R18-Records pro 10 Minuten (inkl. Nullwerte). Lücken bedeuten: kein Sync bzw. keine Daten, nicht „Byte 82 = 0“.</p>
    <svg id="coverage" role="img" aria-label="Records pro 10 Minuten"></svg>
    <div class="tip" id="tipCoverage"></div>
  </section>

  <p class="warn">Byte 82 ist <strong>nicht</strong> als SpO₂ validiert (siehe docs/WHOOP5_DEEP_DATA.md, Issue #103). Keine medizinische Aussage.</p>
</main>

<script>
"use strict";
const $ = (s) => document.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
let DATA = null;
let view = { from: null, to: null, onlyCand: false };

const fmtDay = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit" });
const fmtDate = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });
const fmtTime = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const fmtFull = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
const nf = new Intl.NumberFormat("de-DE");
const d = (ts) => new Date(ts * 1000);

function el(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function text(parent, x, y, str, anchor) {
  const t = el("text", { x, y, "text-anchor": anchor || "middle" }, parent);
  t.textContent = str;
  return t;
}
function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function isCand(v) { return v >= DATA.candidateRange[0] && v <= DATA.candidateRange[1]; }

// SVG-Koordinaten (viewBox) -> Pixel relativ zur Karte, in der der Tooltip absolut positioniert ist.
function toCard(svg, f, sx, sy) {
  const r = svg.getBoundingClientRect(), c = svg.parentElement.getBoundingClientRect(), k = r.width / f.width;
  return [r.left - c.left + sx * k, r.top - c.top + sy * k];
}

function setTip(tip, card, x, y, rows) {
  tip.replaceChildren();
  rows.forEach((r, i) => {
    const line = document.createElement("div");
    if (r.key) {
      const k = document.createElement("span");
      k.className = "k"; k.style.background = r.key;
      line.appendChild(k);
    }
    const v = document.createElement(i === 0 ? "strong" : "span");
    v.textContent = r.text;
    line.appendChild(v);
    tip.appendChild(line);
  });
  tip.style.display = "block";
  const cw = card.clientWidth, tw = tip.offsetWidth;
  tip.style.left = Math.min(Math.max(x + 12, 0), cw - tw - 4) + "px";
  tip.style.top = (y - tip.offsetHeight - 10) + "px";
}

function timeTicks(from, to, width) {
  const span = to - from, day = 86400;
  const steps = [3600, 3 * 3600, 6 * 3600, 12 * 3600, day, 2 * day, 7 * day, 14 * day, 30 * day];
  const target = Math.max(2, Math.floor(width / 90));
  const step = steps.find((s) => span / s <= target) || 60 * day;
  const offset = new Date().getTimezoneOffset() * 60;
  const first = Math.ceil((from - offset) / step) * step + offset;
  const ticks = [];
  for (let t = first; t <= to; t += step) ticks.push(t);
  return { ticks, fmt: step < day ? (t) => fmtTime.format(d(t)) : (t) => fmtDay.format(d(t)) };
}

function frame(svg, height) {
  svg.replaceChildren();
  const width = svg.parentElement.clientWidth - 28;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  return { width, height, m: { l: 36, r: 8, t: 8, b: 22 } };
}

function drawTimeAxis(svg, f, x, from, to) {
  const { ticks, fmt } = timeTicks(from, to, f.width - f.m.l - f.m.r);
  for (const t of ticks) {
    el("line", { x1: x(t), x2: x(t), y1: f.m.t, y2: f.height - f.m.b, stroke: cssVar("--grid") }, svg);
    text(svg, x(t), f.height - 6, fmt(t));
  }
  el("line", { x1: f.m.l, x2: f.width - f.m.r, y1: f.height - f.m.b, y2: f.height - f.m.b, stroke: cssVar("--axis") }, svg);
}

function range() {
  const all = DATA.coverage;
  const from = view.from ?? (all.length ? all[0][0] : 0);
  const to = view.to ?? (all.length ? all[all.length - 1][0] + 600 : 1);
  return [from, to];
}

function drawScatter() {
  const svg = $("#scatter"), tip = $("#tipScatter"), card = svg.parentElement;
  const f = frame(svg, 300);
  const [from, to] = range();
  const pts = DATA.points.filter(([t, v]) => t >= from && t <= to && (!view.onlyCand || isCand(v)));
  const maxV = view.onlyCand ? 100 : Math.max(100, ...pts.map((p) => p[1]));
  const yMin = view.onlyCand ? 65 : 0;
  const yMax = view.onlyCand ? 101 : Math.ceil(maxV / 20) * 20;
  const x = (t) => f.m.l + (t - from) / (to - from) * (f.width - f.m.l - f.m.r);
  const y = (v) => f.height - f.m.b - (v - yMin) / (yMax - yMin) * (f.height - f.m.t - f.m.b);

  for (const [s, e] of DATA.sessions) {
    if (e < from || s > to) continue;
    const x0 = x(Math.max(s, from)), x1 = x(Math.min(e, to));
    el("rect", { x: x0, y: f.m.t, width: Math.max(1, x1 - x0), height: f.height - f.m.t - f.m.b, fill: cssVar("--sleep") }, svg);
  }
  el("rect", { x: f.m.l, y: y(100), width: f.width - f.m.l - f.m.r, height: y(70) - y(100), fill: cssVar("--band") }, svg);
  const yStep = view.onlyCand ? 5 : (yMax > 120 ? 40 : 20);
  for (let v = Math.ceil(yMin / yStep) * yStep; v <= yMax; v += yStep) {
    el("line", { x1: f.m.l, x2: f.width - f.m.r, y1: y(v), y2: y(v), stroke: cssVar("--grid") }, svg);
    text(svg, f.m.l - 6, y(v) + 4, v, "end");
  }
  drawTimeAxis(svg, f, x, from, to);

  const c1 = cssVar("--series-1"), c2 = cssVar("--series-2"), ring = cssVar("--surface-1");
  const g = el("g", {}, svg);
  for (const [t, v] of pts) {
    el("circle", { cx: x(t), cy: y(v), r: 3.5, fill: isCand(v) ? c1 : c2, stroke: ring, "stroke-width": 1 }, g);
  }
  if (!pts.length) text(svg, f.width / 2, f.height / 2, "Keine Werte ≠ 0 in diesem Zeitraum");

  const hover = el("circle", { r: 6, fill: "none", "stroke-width": 2, visibility: "hidden" }, svg);
  svg.onpointermove = (ev) => {
    const r = svg.getBoundingClientRect(), k = f.width / r.width;
    const px = (ev.clientX - r.left) * k, py = (ev.clientY - r.top) * k;
    let best = null, bd = 144;
    for (const p of pts) {
      const dx = x(p[0]) - px, dy = y(p[1]) - py, dist = dx * dx + dy * dy;
      if (dist < bd) { bd = dist; best = p; }
    }
    if (!best) { tip.style.display = "none"; hover.setAttribute("visibility", "hidden"); return; }
    const col = isCand(best[1]) ? c1 : c2;
    hover.setAttribute("cx", x(best[0])); hover.setAttribute("cy", y(best[1]));
    hover.setAttribute("stroke", col); hover.setAttribute("visibility", "visible");
    const bits = best[1].toString(2).padStart(8, "0");
    const [tx, ty] = toCard(svg, f, x(best[0]), y(best[1]));
    setTip(tip, card, tx, ty, [
      { text: `${best[1]}`, key: col },
      { text: fmtFull.format(d(best[0])) },
      { text: `0x${best[1].toString(16).padStart(2, "0")} · ${bits}b` },
    ]);
  };
  svg.onpointerleave = () => { tip.style.display = "none"; hover.setAttribute("visibility", "hidden"); };
}

function drawNights() {
  const svg = $("#nights"), tip = $("#tipNights"), card = svg.parentElement;
  const f = frame(svg, 220);
  const [from, to] = range();
  const nights = DATA.nights.filter((n) => n.mean !== null && n.end >= from && n.start <= to);
  const lowest = Math.min(...nights.map((n) => n.mean), 80);
  const yMin = Math.floor((lowest - 1) / 5) * 5, yMax = 100;
  const y = (v) => f.height - f.m.b - (Math.max(v, yMin) - yMin) / (yMax - yMin) * (f.height - f.m.t - f.m.b);
  for (let v = yMin; v <= yMax; v += 5) {
    el("line", { x1: f.m.l, x2: f.width - f.m.r, y1: y(v), y2: y(v), stroke: cssVar("--grid") }, svg);
    text(svg, f.m.l - 6, y(v) + 4, v, "end");
  }
  el("line", { x1: f.m.l, x2: f.width - f.m.r, y1: y(yMin), y2: y(yMin), stroke: cssVar("--axis") }, svg);
  if (!nights.length) { text(svg, f.width / 2, f.height / 2, "Keine Nacht mit Kandidatenwerten"); return; }

  const slot = (f.width - f.m.l - f.m.r) / nights.length;
  const bw = Math.max(3, Math.min(28, slot - 2));
  const c1 = cssVar("--series-1");
  const labelEvery = Math.ceil(nights.length / Math.max(1, Math.floor((f.width - f.m.l) / 48)));
  nights.forEach((n, i) => {
    const cx = f.m.l + slot * (i + 0.5), top = y(n.mean), h = y(yMin) - top;
    const r = Math.min(4, bw / 2, h);
    el("path", {
      d: `M${cx - bw / 2},${y(yMin)} V${top + r} Q${cx - bw / 2},${top} ${cx - bw / 2 + r},${top} H${cx + bw / 2 - r} Q${cx + bw / 2},${top} ${cx + bw / 2},${top + r} V${y(yMin)} Z`,
      fill: c1,
    }, svg);
    if (i % labelEvery === 0) text(svg, cx, f.height - 6, fmtDay.format(d(n.end)));
    const hit = el("rect", { x: cx - slot / 2, y: f.m.t, width: slot, height: f.height - f.m.t - f.m.b, fill: "transparent", tabindex: 0 }, svg);
    const show = () => {
      const [tx, ty] = toCard(svg, f, cx, top);
      setTip(tip, card, tx, ty, [
        { text: `${n.mean} %  (exakt ${n.meanExact.toFixed(2)})`, key: c1 },
        { text: `Nacht bis ${fmtDate.format(d(n.end))}` },
        { text: `${fmtTime.format(d(n.start))}–${fmtTime.format(d(n.end))} · ${n.n} Werte · ${n.min}–${n.max}` },
        { text: `Aux-Abdeckung der Nacht: ${(100 * n.auxCoverage).toFixed(0)} %` },
      ]);
    };
    hit.addEventListener("pointermove", show);
    hit.addEventListener("focus", show);
    hit.addEventListener("pointerleave", () => { tip.style.display = "none"; });
    hit.addEventListener("blur", () => { tip.style.display = "none"; });
    hit.addEventListener("click", () => selectNight(n));
  });
}

function drawCoverage() {
  const svg = $("#coverage"), tip = $("#tipCoverage"), card = svg.parentElement;
  const f = frame(svg, 120);
  const [from, to] = range();
  const buckets = DATA.coverage.filter(([t]) => t >= from && t < to);
  const x = (t) => f.m.l + (t - from) / (to - from) * (f.width - f.m.l - f.m.r);
  const y = (v) => f.height - f.m.b - v / 600 * (f.height - f.m.t - f.m.b);
  for (const v of [0, 300, 600]) {
    el("line", { x1: f.m.l, x2: f.width - f.m.r, y1: y(v), y2: y(v), stroke: cssVar("--grid") }, svg);
    text(svg, f.m.l - 6, y(v) + 4, v, "end");
  }
  drawTimeAxis(svg, f, x, from, to);
  const w = Math.max(1, x(from + 600) - x(from));
  const col = cssVar("--text-muted");
  for (const [t, n] of buckets) el("rect", { x: x(t), y: y(Math.min(n, 600)), width: w, height: y(0) - y(Math.min(n, 600)), fill: col, opacity: 0.55 }, svg);
  svg.onpointermove = (ev) => {
    const r = svg.getBoundingClientRect(), k = f.width / r.width;
    const t = from + ((ev.clientX - r.left) * k - f.m.l) / (f.width - f.m.l - f.m.r) * (to - from);
    const b = t - (t % 600);
    const hit = buckets.find(([bt]) => bt === b);
    const [tx, ty] = toCard(svg, f, f.m.l + (b - from) / (to - from) * (f.width - f.m.l - f.m.r), f.m.t);
    setTip(tip, card, tx, ty + 20, [
      { text: `${hit ? hit[1] : 0} Records` },
      { text: `${fmtFull.format(d(b))} (+10 min)` },
    ]);
  };
  svg.onpointerleave = () => { tip.style.display = "none"; };
}

function drawStats() {
  const [from, to] = range();
  const pts = DATA.points.filter(([t]) => t >= from && t <= to);
  const cand = pts.filter(([, v]) => isCand(v));
  const records = DATA.coverage.filter(([t]) => t >= from && t < to).reduce((a, [, n]) => a + n, 0);
  const nights = DATA.nights.filter((n) => n.mean !== null && n.end >= from && n.start <= to);
  const avg = nights.length ? (nights.reduce((a, n) => a + n.meanExact, 0) / nights.length).toFixed(1) : "–";
  const tiles = [
    [nf.format(records), "R18-Records im Zeitraum"],
    [nf.format(pts.length), "davon Byte 82 ≠ 0"],
    [nf.format(cand.length), "davon im Bereich 70–100"],
    [records ? (100 * pts.length / records).toFixed(2) + " %" : "–", "Anteil ≠ 0"],
    [nf.format(nights.length), "Nächte mit Kandidat"],
    [avg, "Mittel der Nachtwerte"],
  ];
  const box = $("#stats");
  box.replaceChildren();
  for (const [v, l] of tiles) {
    const t = document.createElement("div"); t.className = "tile";
    const a = document.createElement("div"); a.className = "v"; a.textContent = v;
    const b = document.createElement("div"); b.className = "l"; b.textContent = l;
    t.append(a, b); box.appendChild(t);
  }
}

function drawTable() {
  const body = $("#table tbody");
  body.replaceChildren();
  for (const n of [...DATA.nights].reverse()) {
    const tr = document.createElement("tr");
    const cells = [
      fmtDate.format(d(n.end)), fmtTime.format(d(n.start)), fmtTime.format(d(n.end)),
      n.mean ?? "–", n.meanExact !== null ? n.meanExact.toFixed(2) : "–", n.min ?? "–", n.max ?? "–", n.n,
      (100 * n.auxCoverage).toFixed(0) + " %",
    ];
    for (const c of cells) { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); }
    body.appendChild(tr);
  }
}

function render() { drawStats(); drawScatter(); drawNights(); drawCoverage(); }

function setPressed(btn) {
  document.querySelectorAll("[data-range]").forEach((b) => b.setAttribute("aria-pressed", b === btn ? "true" : "false"));
}
function selectNight(n) {
  view.from = n.start - 1800; view.to = n.end + 1800;
  $("#night").value = String(n.start);
  setPressed(null); render();
}

document.querySelectorAll("[data-range]").forEach((b) => b.addEventListener("click", () => {
  const r = b.dataset.range, last = DATA.coverage.length ? DATA.coverage[DATA.coverage.length - 1][0] + 600 : 0;
  view.to = r === "all" ? null : last;
  view.from = r === "all" ? null : last - Number(r) * 86400;
  $("#night").value = ""; setPressed(b); render();
}));
$("#night").addEventListener("change", (e) => {
  const n = DATA.nights.find((x) => String(x.start) === e.target.value);
  if (n) selectNight(n);
});
$("#onlyCand").addEventListener("change", (e) => { view.onlyCand = e.target.checked; render(); });
window.addEventListener("resize", () => { if (DATA) render(); });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (DATA) render(); });

fetch("api/data").then((r) => r.json()).then((data) => {
  DATA = data;
  const s = data.stats;
  $("#sub").textContent = `Gerät ${data.device} · ${nf.format(s.records)} Records · ${nf.format(data.sessions.length)} Schlafsessions`;
  const sel = $("#night");
  for (const n of [...data.nights].reverse()) {
    const o = document.createElement("option");
    o.value = String(n.start);
    const state = n.mean !== null ? " · " + n.mean + " %" : (n.auxCoverage < 0.01 ? " · keine Aux-Daten" : " · kein Kandidat");
    o.textContent = `${fmtDate.format(d(n.end))}${state}`;
    sel.appendChild(o);
  }
  drawTable(); render();
}).catch((err) => { $("#sub").textContent = "Fehler beim Laden: " + err; });
</script>
</body>
</html>
"""


def make_handler(payload):
    body_json = json.dumps(payload, separators=(",", ":")).encode()
    body_html = PAGE.encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", body_html)
            elif path == "/api/data":
                self._send(200, "application/json", body_json)
            else:
                self._send(404, "text/plain; charset=utf-8", b"Nicht gefunden")

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Zeigt den Verlauf von WHOOP-R18-Byte 82 im Browser.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"NOOP-Datenbank (Standard: {DEFAULT_DB})")
    parser.add_argument("--host", default="127.0.0.1", help="Bind-Adresse (Standard: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8082, help="Port (Standard: 8082)")
    parser.add_argument("--device", help="deviceId in v18AuxSample (Standard: Gerät mit den meisten Zeilen)")
    args = parser.parse_args()

    if not args.db.is_file():
        sys.exit(f"Datenbank nicht gefunden: {args.db}")

    print(f"Lese {args.db} …", flush=True)
    payload = load_data(args.db, args.device)
    s = payload["stats"]
    print(f"Gerät {payload['device']}: {s['records']} Records, {s['nonzero']} mit Byte 82 ≠ 0, "
          f"{len(payload['sessions'])} Schlafsessions")

    server = ThreadingHTTPServer((args.host, args.port), make_handler(payload))
    print(f"Server läuft auf http://{args.host}:{args.port}/  (Strg+C beendet)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
