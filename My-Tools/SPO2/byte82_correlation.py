#!/usr/bin/env python3
"""Sucht Zusammenhänge zwischen WHOOP-R18-Byte 82 im Bereich 70-100 und anderen gespeicherten Bytes.

Vergleicht pro Sekunde drei Klassen von Byte 82:
    C = 70..100 (SpO2-Kandidat), Z = 0, O = anderer Wert ≠ 0
und prüft, ob Bits bzw. Werte anderer Felder mit C zusammenhängen. Weil C nur im Schlaf auftritt,
wird zusätzlich nur INNERHALB von Schlafsessions (und ab dem ersten C-Wert) verglichen, damit reine
Schlaf-Korrelationen nicht als Zusammenhang erscheinen.

Quellen je Sekunde (gleiche deviceId und ts):
    v18AuxSample.fields    -> @11 record_index, @23 rr_count, @33, @36, @37, @38, @40, @59, @75, @77,
                              @79, @82, @106..@109, @113 (siehe V18AuxCodec.kt)
    sleepStateSample.rawByte -> @81
    stepSample.activityClass -> @63
    hrSample.bpm             -> @22

    python3 byte82_correlation.py [--db PFAD] [--device ID]
"""

import argparse
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "Database" / "noop-backup.sqlite"

# (Slot-Index, Breite, Name) aus V18AuxCodec.kt
SLOTS = [
    (0, 4, "@11 record_index"), (1, 1, "@23 rr_count"), (2, 1, "@33 cardiac_flags"),
    (3, 1, "@36 hr_quality_flags"), (4, 1, "@37 heart_rate_alt"), (5, 2, "@38 rr_packed"),
    (6, 1, "@40 cardiac_status"), (7, 1, "@59 step_cadence"), (8, 2, "@75 status_word"),
    (9, 2, "@77 status_word_1"), (10, 2, "@79 status_word_2"), (11, 1, "@82 aux_byte_82"),
    (12, 1, "@106 optical_baseline_a"), (13, 1, "@107 optical_baseline_b"),
    (14, 1, "@108 optical_amp_a"), (15, 1, "@109 optical_amp_b"), (16, 4, "@113 unknown_f32_bits"),
]
BYTE82 = "@82 aux_byte_82"
SKIP_FIELDS = {BYTE82, "@11 record_index", "@113 unknown_f32_bits"}


def unpack(blob):
    if len(blob) < 5 or blob[0] != 2:
        return None
    bitmap = int.from_bytes(blob[1:5], "little")
    out, i = {}, 5
    for idx, width, name in SLOTS:
        if bitmap >> idx & 1:
            if i + width > len(blob):
                break
            out[name] = int.from_bytes(blob[i:i + width], "little")
            i += width
    return out


def klass(v):
    if v == 0:
        return "Z"
    return "C" if 70 <= v <= 100 else "O"


def load(db, device):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    if device is None:
        device = conn.execute(
            "SELECT deviceId FROM v18AuxSample GROUP BY deviceId ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()[0]
    rows = {}
    for ts, blob in conn.execute("SELECT ts, fields FROM v18AuxSample WHERE deviceId=?", (device,)):
        f = unpack(blob)
        if f and BYTE82 in f:
            rows[ts] = f
    extra = [
        ("SELECT ts, rawByte FROM sleepStateSample WHERE deviceId=? AND rawByte IS NOT NULL", "@81 sleep_state_raw"),
        ("SELECT ts, activityClass FROM stepSample WHERE deviceId=? AND activityClass IS NOT NULL", "@63 activity_class"),
        ("SELECT ts, bpm FROM hrSample WHERE deviceId=?", "@22 heart_rate"),
    ]
    for sql, name in extra:
        for ts, v in conn.execute(sql, (device,)):
            if ts in rows:
                rows[ts][name] = v
    sessions = conn.execute(
        "SELECT startTs, endTs FROM sleepSession WHERE deviceId IN (?, ?) AND endTs > startTs ORDER BY startTs",
        (device, device + "-noop"),
    ).fetchall()
    events = conn.execute(
        "SELECT ts, kind FROM event WHERE deviceId=? AND kind != 'STANDARD_HR_CONTACT'", (device,)
    ).fetchall()
    conn.close()
    return device, rows, sessions, events


def in_sessions(ts, sessions):
    return any(s <= ts <= e for s, e in sessions)


def field_width(name):
    for _, w, n in SLOTS:
        if n == name:
            return w
    return 1


def bit_table(recs, fields):
    """P(Bit gesetzt | Klasse) für jedes Bit jedes Felds; sortiert nach |P(C) − P(Z)|."""
    res = []
    by = defaultdict(list)
    for f in recs:
        by[klass(f[BYTE82])].append(f)
    for name in fields:
        bits = 8 * field_width(name)
        for b in range(bits):
            p = {}
            for k in "CZO":
                vals = [f[name] for f in by[k] if name in f]
                p[k] = sum(v >> b & 1 for v in vals) / len(vals) if vals else float("nan")
            if not math.isnan(p["C"]) and not math.isnan(p["Z"]):
                res.append((abs(p["C"] - p["Z"]), name, b, p))
    res.sort(reverse=True)
    return res, {k: len(v) for k, v in by.items()}


def cramers_v(pairs):
    """Cramérs V zwischen Byte-82-Klasse (C vs. nicht C) und dem Feldwert (seltene Werte gebündelt)."""
    vc = Counter(v for _, v in pairs)
    keep = {v for v, n in vc.items() if n >= 20}
    tab = Counter((k == "C", v if v in keep else "rest") for k, v in pairs)
    rows = sorted({r for r, _ in tab})
    cols = sorted({c for _, c in tab}, key=str)
    n = sum(tab.values())
    if len(rows) < 2 or len(cols) < 2:
        return 0.0
    rs = {r: sum(tab[(r, c)] for c in cols) for r in rows}
    cs = {c: sum(tab[(r, c)] for r in rows) for c in cols}
    chi2 = sum((tab[(r, c)] - rs[r] * cs[c] / n) ** 2 / (rs[r] * cs[c] / n) for r in rows for c in cols)
    return math.sqrt(chi2 / (n * (min(len(rows), len(cols)) - 1)))


def runs(ts_sorted, rows):
    """Zusammenhängende Läufe gleicher Byte-82-Klasse (Lücke > 2 s trennt)."""
    out, cur = [], None
    for ts in ts_sorted:
        k = klass(rows[ts][BYTE82])
        if cur and cur["k"] == k and ts - cur["end"] <= 2:
            cur["end"] = ts
            cur["n"] += 1
        else:
            cur = {"k": k, "start": ts, "end": ts, "n": 1}
            out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--device")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    device, rows, sessions, events = load(args.db, args.device)
    ts_sorted = sorted(rows)
    first_c = next((t for t in ts_sorted if klass(rows[t][BYTE82]) == "C"), None)
    fields = sorted({k for f in rows.values() for k in f} - SKIP_FIELDS)
    print(f"Gerät {device}: {len(rows)} Sekunden mit Byte 82, {len(sessions)} Schlafsessions")
    if first_c is None:
        print("Keine Werte 70..100 gefunden.")
        return

    scopes = {
        "ALLE Records": [rows[t] for t in ts_sorted],
        "NUR im Schlaf ab erstem C-Wert": [rows[t] for t in ts_sorted if t >= first_c and in_sessions(t, sessions)],
    }
    for label, recs in scopes.items():
        table, n = bit_table(recs, fields)
        print(f"\n=== Bits mit größtem Unterschied P(C) vs. P(Z) — {label} "
              f"(C={n.get('C', 0)}, Z={n.get('Z', 0)}, O={n.get('O', 0)}) ===")
        print(f"{'Feld':28} {'Bit':>3}  {'P|C':>6} {'P|Z':>6} {'P|O':>6}")
        for diff, name, b, p in table[:args.top]:
            print(f"{name:28} {b:>3}  {p['C']:6.3f} {p['Z']:6.3f} {p['O']:6.3f}")

        print(f"\n--- Cramérs V (C vs. nicht C) je Feld — {label} ---")
        vs = []
        for name in fields:
            pairs = [(klass(f[BYTE82]), f[name]) for f in recs if name in f]
            if pairs:
                vs.append((cramers_v(pairs), name, len(pairs)))
        for v, name, npairs in sorted(vs, reverse=True):
            print(f"{name:28} V={v:.3f}  (n={npairs})")

    # Laufstruktur: Wie sehen die C-Fenster aus, und was steht direkt davor/danach?
    rs = runs(ts_sorted, rows)
    c_runs = [r for r in rs if r["k"] == "C"]
    print(f"\n=== C-Läufe: {len(c_runs)}, Längen: {Counter(r['n'] for r in c_runs).most_common(8)} ===")
    starts = sorted(r["start"] for r in c_runs)
    gaps = Counter(round((b - a) / 60) for a, b in zip(starts, starts[1:]) if b - a < 7200)
    print(f"Abstand Laufanfang->nächster Laufanfang (min, <2 h): {gaps.most_common(8)}")
    before, after = Counter(), Counter()
    for r in c_runs:
        for dt, bucket in ((-1, before), (1, after)):
            t = (r["start"] if dt < 0 else r["end"]) + dt
            if t in rows:
                bucket[rows[t][BYTE82]] += 1
    print(f"Byte 82 eine Sekunde VOR einem C-Lauf:  {before.most_common(8)}")
    print(f"Byte 82 eine Sekunde NACH einem C-Lauf: {after.most_common(8)}")

    o_runs = [r for r in rs if r["k"] == "O"]
    print(f"O-Läufe: {len(o_runs)}, Längen: {Counter(r['n'] for r in o_runs).most_common(8)}")
    o_near = sum(1 for r in o_runs if any(abs(r["start"] - c["end"]) <= 5 or abs(c["start"] - r["end"]) <= 5 for c in c_runs))
    print(f"O-Läufe direkt (≤ 5 s) an einem C-Lauf: {o_near}")
    o_in_sleep = sum(1 for r in o_runs if in_sessions(r["start"], sessions))
    print(f"O-Läufe innerhalb einer Schlafsession: {o_in_sleep}")
    print(f"O-Werte: {Counter(rows[t][BYTE82] for t in ts_sorted if klass(rows[t][BYTE82]) == 'O').most_common(12)}")

    # Ereignisse im Umfeld der C-Läufe (±60 s um den Laufanfang) im Vergleich zur Grundrate.
    ev_by_kind = defaultdict(list)
    for ts, kind in events:
        ev_by_kind[kind].append(ts)
    span = ts_sorted[-1] - ts_sorted[0]
    print("\n=== Events ±60 s um C-Laufanfänge (vs. Erwartung bei Zufall) ===")
    out = []
    for kind, tss in ev_by_kind.items():
        hits = sum(1 for s in starts if any(abs(t - s) <= 60 for t in tss))
        expected = len(starts) * min(1.0, len(tss) * 121 / span)
        if hits:
            out.append((hits / max(expected, 1e-9), kind, hits, expected, len(tss)))
    for ratio, kind, hits, exp, total in sorted(out, reverse=True)[:12]:
        print(f"{kind:34} Treffer {hits:4} / {len(starts)}  erwartet {exp:6.1f}  (Faktor {ratio:5.1f}, {total} Events)")


if __name__ == "__main__":
    main()
