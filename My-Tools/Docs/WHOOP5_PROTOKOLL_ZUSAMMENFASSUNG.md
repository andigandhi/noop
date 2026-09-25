# WHOOP 5.0 / MG – Stand des Protokollverständnisses

Zusammenfassung auf Basis der Repository-Dokumentation (`docs/PROTOCOL*.md`, `docs/WHOOP5_*.md`,
`docs/BLE_REVERSE_ENGINEERING.md`, `docs/RAW_DATA_CAPTURE.md`), Stand `main` @ `141cbd93`
(25.09.2026). Die Tabellen hier sind gekürzt. Maßgeblich bleiben die verlinkten Originalseiten.

---

## 1. Rahmen und Aussagekraft

- **Referenz-Firmware:** Alle aktuellen Verträge beziehen sich auf **50.42.1.0**. Ältere
  Beobachtungen sind an ihre Version gebunden: ECG auf MG 50.39.1.0, Optik/IMU und Reboot auf
  50.40.1.0, R-R auf 50.41.1.0, alter Hello-Decoder auf 50.38.1.0.
- **5.0 und MG** teilen ein Protokollprofil (gleiche GATT-Familie, gleiche Rahmen). Der Unterschied
  liegt in der Hardware: Das MG hat einen ECG-fähigen Verschluss.
- **Kein WHOOP‑4‑Port:** Gleiche Befehlsnummern bedeuten nicht gleiche Payloads. WHOOP‑5-Layouts
  entstehen nicht durch Verschieben von WHOOP‑4-Offsets.
- **Grundregel der Dokumentation:** Die folgenden Dinge werden streng getrennt:
  BLE-Write-ACK ≠ Befehlsergebnis ≠ abgeschlossene asynchrone Arbeit ≠ tatsächlich gelieferte Daten ≠
  Persistenz. „Unbekannt“ heißt ungeklärt, nicht „nicht unterstützt“.
- Die Verträge sind aus Wire-Beobachtungen abgeleitet. Sie sind **keine Gerätevalidierung** jedes
  Zustands.

## 2. Hardware (FW 50.42.1.0)

| Funktion | Baustein | Protokollbezug |
|---|---|---|
| Optik- und ECG-Frontend | ADI **MAX86176** | AFE-Befehle 61/62, Optik R20/R26, ECG R16/R17 (nur MG) |
| 6-Achsen-IMU + Pedometer | TDK **ICM-45686** | R21, Stream-Typen 51/52, Gyro-Modus 150/152 |
| Haptik-Treiber | TI **DRV2625** | Alarm-/Haptik-Befehle 19, 66–69, 122 |
| Fuel Gauge | onsemi **LC709205F** | Battery Pack 151, Batterie 26 |
| Hauttemperatur | ams **AS6221** | Temperaturfelder in R18 |

## 3. GATT und Geräteerkennung

| Rolle | UUID |
|---|---|
| Custom Service | `fd4b0001-cce1-4033-93ce-002d5875f58a` |
| Command Write | `fd4b0002-…` |
| Notify | `fd4b0003`, `0004`, `0005`, `0007` (ein Kanal mehr als bei WHOOP 4) |
| Standard | Heart Rate `180D/2A37` (funktioniert auch **ohne Bonding**), Battery `180F/2A19` |

Weitere erkannte, aber **nicht unterstützte** Service-Familien (NOOP verbindet sich nicht):
`11500001-…` (puffin1150), `8a580001-…` (monument), `59830001-…` (symphony).

**5.0 vs. MG** über die Device Information Service (Heuristik, keine universelle Regel):
Model `MG` → MG, Seriennummer `5AM…` → MG, `5AG…` → 5.0, Hardware-Revision enthält `WG50` → 5.0.
Widersprüchliche Signale bleiben „ungeklärt“. Ein ungeklärtes Gerät gilt **nicht** als ECG-fähig.

**Verbindungsaufbau:** Alle fd4b-Notify-Kanäle abonnieren, dann den festen `CLIENT_HELLO`
(ein Type-35-Frame mit Befehl 145, Revision 1) *with response* an `fd4b0002` schreiben:

```text
AA 01 08 00 00 01 E6 71 23 01 91 01 36 3E 5C 8D
```

## 4. Transport – Format 1 (Standardverkehr)

Alle Integer sind little-endian. Die Offsets zählen ab Frame-Beginn.

| Offset | Breite | Inhalt |
|---:|---:|---|
| 0 | 1 | SOF `AA` |
| 1 | 1 | Format `01` |
| 2 | 2 | Deklarierte Länge = Gesamtlänge − 8 |
| 4 | 2 | Header-Felder (Request meist `00 01`, Response `01 00`; nicht als Konstante prüfen) |
| 6 | 2 | **CRC16-Modbus** über Bytes 0–5 (Poly `0xA001`, Init `0xFFFF`, reflected) |
| 8 | 1 | Packet Type (35 = Command) |
| 9 | 1 | Sequenz (8 Bit, läuft über) |
| 10 | 1 | Befehlsnummer |
| 11 | var | Body, mit Nullen auf eine 4-Byte-Grenze aufgefüllt |
| end−4 | 4 | **CRC32** (zlib) über den aufgefüllten Body ab Offset 8 |

- Frame-Größe = aufgefüllter Body + 12. Das Padding ist **keine** Semantik: Ein explizites `00` und
  ein fehlendes Argument sind nicht dasselbe.
- Akzeptanz: Frame > 15 Byte (NOOP nimmt empirisch ≥ 13), Längenangabe passt exakt,
  `(len − 4) % 4 == 0`. CRC-Fehler sind lokale Fehler, keine Ergebniscodes.
- Notifications fragmentieren Frames. Deshalb zuerst reassemblieren und dann prüfen.
  Records können über mehrere BLE-Fragmente reichen.

**Command Response (Type 36):** Response-Sequenz @9, Befehl @10, **ursprüngliche Request-Sequenz
@11** (das Korrelationsfeld), Ergebnis @12, Body ab @13.

| Ergebnis | Bedeutung |
|---:|---|
| 0 | Failure |
| 1 | Success (nur Annahme, kein Beweis für Wirkung) |
| 2 | Pending (endgültige Antwort folgt) |
| 3 | Unsupported (alle 88 „U“-IDs in 50.42.1.0) |

Das erste Body-Byte ist befehlsspezifisch (oft ein Revisionsmarker). Es ist **kein** universelles
Status-Flag.

**Format 2:** Existiert (äußerer Typ `0x40`, breitere Felder, innerer Typ 7/8). Wann es zur Laufzeit
verfügbar ist, ist ungeklärt. Normaler Verkehr läuft über Format 1.

## 5. Packet Types (Byte 8)

| Typ | Bedeutung |
|---:|---|
| 35 / 36 | Command / Command Response |
| 40 | Live-HR + R-R |
| 43 | Live-Sensordaten (u. a. ECG R16/R17, IMU R21); Byte 9 wählt das Layout |
| 47 | Historische Records; Byte 9 wählt R16/R17/R18/R20/R21/R22/R26 |
| 48 | Event (Eventnummer @10, u32-Zeitstempel @12, Payload-Länge u16 @18, Payload ab @20) |
| 49 | History-Metadaten (START = 1 / END = 2 / COMPLETE = 3) |
| 50 | Console Logs (Firmware-Text; u8-Sequenz @9, die überläuft) |
| 51 / 52 | Dedizierter Live-/historischer IMU-Stream (Layout dokumentiert, Output **unbestätigt**) |
| 37/38/53–56 | „Puffin“-Typen; 38 → 36 und 56 → 49 werden als Alias behandelt, Rolle in 50.42.1.0 unbestätigt |

Packet Type, Record-Layout, Befehlsnummer und Eventnummer sind **getrennte Namensräume**.

## 6. Befehlsraum (IDs 1–159)

In 50.42.1.0: **71 unterstützt, 88 nicht unterstützt** (→ Ergebnis 3). Die wichtigsten Befehle:

| ID | Name | Kurzvertrag |
|---:|---|---|
| 1 | `LINK_VALID` | Success + feste 13-Byte-Bestätigung (keine Identität) |
| 3 | `TOGGLE_REALTIME_HR` | `0/1` |
| 14 | `TOGGLE_GENERIC_HR_PROFILE` | `0/1`, nichtflüchtig |
| 19 | `RUN_HAPTIC_PATTERN_MAVERICK` | 12-Byte-Haptikbody (siehe §11) |
| 20 / 22 / 23 | History Abort / Send / Result | siehe §8 |
| 26 | `GET_BATTERY_LEVEL` | Body = **u32 ganze Prozent** (0 kann ein Fallback sein) |
| 34 | `GET_DATA_RANGE` | Pending, dann 65-Byte-Body (siehe §8) |
| 48 | `SEND_EVENT_PACKETS` | Toggle für Event-Auslieferung |
| 61 / 62 | `SET/GET_AFE_PARAMETERS` | 12 Byte: Kanal, Setting, Wert (3 × u32, **ohne** Revision) |
| 66–69 | Alarm SET/GET/RUN/DISABLE | siehe §11 |
| 81 / 82 | `START/STOP_RAW_DATA` | Revision 1 |
| 84 | `GET_BODY_LOCATION_AND_STATUS` | `[1,0,255,on_body]` (Mittelbytes sind Platzhalter) |
| 96 / 97 | High-Frequency Sync Enter/Exit | Rev 2, Periode > 60, Dauer < 28 800 s; Events 97/96/98 |
| 103 | `DISABLE_BLE_UART` | Rev 1 |
| 105–108 | IMU speichern / IMU live / Optik speichern / Optik live | Rev-1-Boolean `[1,state]` |
| 115–121, 128 | Benannte Konfiguration (Enumerieren/Set/Get) | siehe §10 |
| 122 | `STOP_HAPTICS` | Rev 1, Pending, dann Final, jeweils Body `[1]` |
| 123–127, 139 | ECG (Handgelenk, Start/Stop, Raw/Filtered speichern/senden) | siehe §12 |
| 138 | Signal-Processing-Konfiguration | Presets 0–8 (Bedeutung unbekannt) |
| 140 / 141 | Advertising-Name Set/Get | 0–15 Byte / fester 19-Byte-Body |
| 145 | `GET_HELLO` | Rev 1/3, Pending, dann 107/111 Byte (siehe §7) |
| 146 / 147 | `SET/GET_CLOCK` | Rev 1, u32 Sekunden + u16 Ticks (1/32768 s) |
| 148 | Wear-Detection-Override | `1` = immer „getragen“ |
| 149 | LED-Accessibility | persistent |
| 150 / 152 | Gyro-Modus Set/Status | Ein failed SET kann den Modus trotzdem ändern, deshalb zurücklesen |
| 151 | `GET_BATTERY_PACK_INFO` | 28 Byte, aus dem Cache |
| 153 / 154 | Persistente R20- (Optik) / R21-Policy (IMU) | Rev-1-Boolean, kein Getter |
| 83, 142–144 | Firmware-Image Verify/Start/Load/Process | **NOOP sendet diese nie** |
| 155–159 | Zertifikate / `LOCK_DEVICE` | Autorisierung; NOOP implementiert das nicht |

Die alten Low-Number-Befehle (10/11 Clock, 35 Hello) sind nicht gegen 146/147/145 austauschbar.
Als **destruktiv** gelten und werden nie gesendet: 25 `FORCE_TRIM`, 32 `POWER_CYCLE`, 33
`SET_READ_POINTER` sowie 142–144 und 155–159. 15 `FORGET_BONDS` und 29 `REBOOT` unterbrechen die
Verbindung. Reboot gibt es nur als bestätigungspflichtige Nutzeraktion.

## 7. Uhr und Identität

- **SET_CLOCK (146):** `[1, secs u32, ticks u16]`. Gespeichert wird in Hundertstelsekunden, deshalb
  ist ein Set/Get-Roundtrip verlustbehaftet. Eine Uhrzeit, die gesetzt wird, während der Strap nicht
  verfügbar ist, wird höchstens einmal angewendet und nur, wenn sie > `1293840001` und neuer als die
  aktuelle Zeit ist.
- **GET_CLOCK (147):** Liefert 7 Byte. Die Antwort kann **Success mit Zeit 0** sein, es gibt kein
  Gültigkeits-Flag.
- **GET_HELLO (145), finaler Body:** Batterie (Zehntel-%) @1, Unix-Sekunden @6, Ticks @10,
  Identitätstext A @14 (11 Byte), opaker Block @25, Identitätstext B @49 (30 Byte), **Firmware-Version
  @91** (`50, 42, 1`), Profilwert @101, Preparation-Bits @103 (`0x10`/`0x20` = Identitätsblock A/B
  nicht befüllt). Die Antwort enthält Seriennummer bzw. Session-Token. Decoder lesen nur Name und
  Version aus.

## 8. Historischer Datenabzug (Offload)

Ablauf: `GET_DATA_RANGE (34)`, dann `SEND_HISTORICAL_DATA (22, [00])`, dann Stream aus Type 49 START,
Type‑47-Records und Type 49 END. Nach jedem END folgt `HISTORICAL_DATA_RESULT (23)`. Am Ende steht
COMPLETE.

- **Das ACK ist Pflicht für den Fortschritt:** Ohne ACK liefert der Strap immer wieder denselben
  frühen Chunk (in einer Messung blieb der Trim-Cursor eingefroren, es kamen 0 Records). Mit ACK
  wandert der Cursor weiter (3 193 Frames in 90 s).
- **END-Token:** 8 Byte bei Frame `[21:29]` (erstes Wort = Trim/Read-Page-Cursor, zweites Wort =
  Write-Wrap-State). Das Token wird **unverändert** zurückgesendet als `01 ‖ token[8]`, und zwar
  **erst nach dem dauerhaften lokalen Commit**. Nie aus Zeitstempeln rekonstruieren.
- **Sondertokens:** `0xFFFFFFFF` = Abschluss ohne Vorrücken, `0xFEFEFEFE`- und `0xFDFDFDFD`-Paare =
  Sondermodi. Diese nie selbst synthetisieren.
- **Wiederholungen:** Ein unbeantwortetes END wird bis zu 4× erneut gesendet. Nach dem 5. Timeout
  oder dem 5. Nicht-Success-ACK endet der Versuch. Ein neuer Versuch spielt ab der Trim-Grenze erneut
  ab, deshalb müssen Duplikate toleriert werden. COMPLETE ist bei Backlog ≤ 6 möglich und beweist
  keine Vollständigkeit.
- Records sind höchstens 2 140 Byte groß. Der Ringpuffer hat 4096-Byte-Pages. 20 `ABORT` trimmt
  nicht.
- **DATA_RANGE (65 Byte):** Rev + 16 × u32, darunter Ringgrenze A, Read-Cursor, Write-Cursor,
  Trim-Grenze, Wrap-Zähler, Kapazität, Record-Schätzung (Fallback 15/Page), abgeleitete Menge und vier
  Uhrpaare. Die Werte sind Zähler bzw. Page-Distanzen, **keine** Zeitdauern. `0xFFFFFFFF` bzw. 65535
  sind Sentinels für fehlgeschlagene Page-Reads.

## 9. Sensor-Records

Die gemeinsamen Felder für R18/R20/R21/R26 sind: Layout @9, Marker @10, **Record-Index u32 @11**
(kein Zeitstempel) und **Unix-Sekunden u32 @15**.

### Packet 40 – Live-HR
Zeit u32 @10, unklares Zeitfeld u16 @14, **HR bpm @16**, R-R-Anzahl @17, R-R ab @18 als u16 in
1/1024 s. Umrechnung: `ms = (ticks·1000 + 512) // 1024`, Nullwerte werden verworfen.

### R18 – Biometrische Zusammenfassung (124 Byte, CRC @120)
| Offset | Feld |
|---:|---|
| 22 | HR (bpm) |
| 23 / 24+2i | R-R-Anzahl / bis zu 4 R-R-Werte (1/1024 s) |
| 36 | HR/R-R-Qualitäts- und Quellwahlbits (Bit 4/5 = alternative Quelle aktiv/Nachlauf) |
| 37 | Alternative HR |
| 41 | f32 dynamische Beschleunigung (g, ohne Schwerkraft) |
| 45/49/53 | f32 Schwerkraftvektor x/y/z (g) |
| 57 / 59 / 61 / 64 | Schrittzähler / Kadenz-Rohwert / HW-Zähler bei SW-Override / `0x10` = Override aktiv |
| 63 | Aktivität 0 = still, 1 = gehen, 2 = laufen, `FF` = andere |
| 69, 71 | i16 Hilfs-Temperaturen (raw/10 °C) |
| 73 | u16 **Hauttemperatur (raw/100 °C)** |
| 81 | 4 × 2 Bit; Bits 4–5 = Band-Zustand **0 WAKE, 1 STILL, 2 SLEEP, 3 UP** (kein Schlafstadium) |
| 82 | Rohbyte, **SpO₂-Kandidat, nicht bestätigt** |
| 106–109 | Optische Baseline-/Amplitudenwerte (128/128 = Qualitäts-Sentinel) |

### R20 – Optische Blöcke (2 140 Byte, CRC @2136)
26-Byte-Header plus **5 Blöcke à 422 Byte** (Basen 26, 448, 870, 1292, 1714). Jeder Block hat einen
21-Byte-Konfigurationsheader (Anzahl gültiger Samples je Slot 0–50, Emitter-/Drive-/Detektor-/Range-/
Offset-Felder A/B) und zwei Slots **A/B** mit je 50 × i32-Rohwerten. Beobachtet wurden die Anzahlen
`[25,0,0,25,25]`. Block 3 kann eine Fallback-Quelle nutzen (Marker Bit 0). Wellenlängen
(rot/IR/grün) und physikalische Einheiten sind **ungeklärt**.

### R21 – 6-Achsen-IMU (1 244 Byte, CRC @1240)
Accel-Anzahl u16 @24, dann ax/ay/az als je 100 × i16 ab 28/228/428. Gyro-Anzahl @630, dann
gx/gy/gz ab 640/840/1040. Feinzeit u16 @19: `t = secs + frac/32768`. Die übliche Konvention ist
100 Hz, `raw/4096 g` und `raw·2000/32768 °/s`. Validiert wurde das über 1 423 echte Puffer (ruhend
≈ 1,006 g).

### R22 – Versionierter 188-Byte-Record
Innere Version @21 und Subversion @22. Die Präferenzreihenfolge ist 9 → 6 → 5 → 4 → 3 → 2 → 1, mit
Fallbacks: v3 → v2, v5 → v4, v9 ohne Queue → **v4**. **v9:** Kanal-ID @141 (0 = aktuell,
1–5 = gespeicherte Queues à 60 Records, Wiedergabe in der Reihenfolge 1, 2, 4, 5, 3),
Initial-Sample u32 @31 plus 49 × i16-Deltas @35, also 50 Samples. Die Deltas sind geclippt und damit
verlustbehaftet. Gepackte Metadaten @137. Physikalische Kanalzuordnung: unbekannt.

### R26 – Kompaktes optisches Fenster (88 Byte, CRC @84)
Burst-Zähler u16 @21, Basiswert u32 @23 und **24 × i16-Deltas @27** ergeben 25 Samples
(≈ 1 s-Fenster). Dazu kommen Bewegung f32 @75, Status @79, On-Wrist @81 und Signalakzeptanz @82.
Die Deltas sind auf ±32767 geclippt.

### Typ 51/52 – Dedizierter IMU-Stream
Die Anzahlen A/G stehen @24/@26, die Achsen-Arrays liegen planar ab 28. Es gibt **keinen
bestätigten Strap-Output**. Nicht als R21 dekodieren.

### Events (Typ 48)
Wichtige Nummern: 3 Batterie (Deci-Prozent @21, mV @25, Laden @30), 9/10 Wrist on/off,
14 Double Tap, 23 BLE bonded, 56–59 Alarm, 96–98 HF-Sync, 115/116 Gyro. 61, 62, 110, 112, 116, 120
und 123 werden gesendet, sind aber **nicht benannt** und bleiben roh. Jedes Event löst in NOOP einen
Sync aus.

## 10. Konfiguration

**Benannte Schlüssel (115–121, 128):** Jeweils Revision 1 plus Schlüssel (32 Byte) plus Wert (32 Byte,
ASCII). SET hat 65 Byte, GET antwortet mit 65 Byte. Die Enumeration läuft über einen gemeinsamen
Cursor (sequenziell), Index 255 markiert das Ende.

- **8 Device-Keys**, z. B. `cont_collection_mode` (0 = aus, 1 = Optik + IMU),
  `max_collection_backlog` (Zehntel-%), `enable_raw_data_w_ecg` (0/1 = true, 2 = false; das ist
  **nicht** der ECG-Master-Schalter), `sigproc_wear_detect`, `dorset_detection_period_min`.
- **25 Feature-Flags** (Tri-State `0/1/2`, davon 20 benennbar setzbar). Die Polarität gilt pro Key:
  meist ist nur **`1` = an**, `0` und `2` = aus. Beispiele: `enable_r22_packets` (R22-Master),
  `enable_r22_v2…v9_packets`, `disable_pip_r26_packets` (**invertiert**), `hr_ch_switching`,
  `enable_rocky_again` (löst ein Re-Init aus). Das historische „ASCII `2` schreiben“ **deaktiviert**
  R22 in 50.42.1.0.
- Ein Read kann bei Speicherfehlern Nullen mit Success liefern. Null heißt deshalb nicht
  „Werkseinstellung“.

**Sammel-Policy (Priorität):** persistente Präferenz (153/154) > Raw-Request (81) >
Einzelsensor-Session (105/107) > Continuous Mode. Die Steuerungen überlappen sich und wirken in
Befehlsreihenfolge. Ein späteres Raw-Stop kann Requests des ECG-Begleiters löschen. Ein
Sensor-Restart löscht temporäre Requests. Nach einem Reconnect muss explizit abgeglichen werden.

**Hardware-verifizierte IMU-Aufnahme:** `81 [01]` → `106 [01 01]` → 100-Hz-Puffer. Stop:
`82 [01]` → `106 [01 00]`. Befehl 106 allein liefert Success, **startet aber nichts**.

**AFE (61/62):** Settings 1–24 mit feldspezifischer Quantisierung, z. B. Setting 9/10 →
{0, 8, 16, 32} und Setting 11/12 → {0, 8000, 16000, 24000}. Setting 2 liest als Summe mit Setting 3
zurück. Es gibt keine sichere Tuning-Schnittstelle, und die Einheiten sind unbekannt.

## 11. Alarme und Haptik

- **SET_ALARM (66), Revision 4, 21 Byte:** ID (1–6), Epoch-Sekunden u32, Ticks u16, 8 Effektbytes
  (je ≤ 251), Loop-Control u16, Repeats (< 8), Duration (30–120 bei Repeats = 7), Crescendo (0/1).
  Die Antwort `[4, detail]` enthält Validierungscodes: 1 ok, 2 Effekt, 3 Repeat, 4 Duration,
  10 Zeit nicht in der Zukunft, 11 ID, 12 Crescendo.
- Die Alarmzeit muss **in ganzen Sekunden** in der Zukunft liegen. Alarme sind **einmalig**
  (werden beim Auslösen gelöscht), der Scan läuft etwa alle 0,5 s. Sind mehrere Alarme gleichzeitig
  fällig, kann nur die höchste ID laufen.
- **DISABLE (69):** `[2, ID]` bzw. `[2, 255]` für alle. **RUN (68):** `[2, ID]` antwortet mit
  Pending, dann Final (Detail 5 = ok, 7 = Timeout). RUN **verbraucht** den gespeicherten Alarm.
  Events: 57 = Strap-getrieben, 58 = App-getrieben.
- **Haptik (19):** `[1, 8 × Effekt, loop u16, repeats]`, wobei repeats = N − 1 Pulse. Beispiel für
  eine einzelne Benachrichtigung: `01 2F 98 00 00 00 00 00 00 00 00 00`.

## 12. ECG (nur MG, Codename „Labrador“)

| Befehl | Payload |
|---|---|
| 123 Handgelenk | `01 01` rechts / `01 02` links (nicht 0/1!) |
| 124 Erzeugung | `01 01` **Stop** / `01 02` Start (`03` wirkt ebenfalls als Start) |
| 125 / 127 | Raw / Filtered speichern: `01 00` / `01 01` |
| 126 / 139 | Raw / Filtered live senden: `01 00` / `01 01` |

- Erzeugung und Ausgabe-Gates sind unabhängig voneinander. Nachgewiesen ist auf einem MG: `139=1`,
  dann `124=2`, danach etwa 100-Hz-Wellenform, solange beide Elektroden berührt werden. Ein
  Start-ACK beweist keine Samples. Wiederholte Starts können das Aufräumen des Begleitsensors
  verhindern.
- **R17 gefiltert (240 Byte):** Status @21–33 (Qualität 0–3, Präsenz-Bit 3 in @22, Classifier,
  Fortschritt, HR/HRV-Werte), Anzahl u16 @32, **100 × i16 @34–233**, 2 Byte Alignment, CRC @236.
  Das Verhältnis beträgt 1 gefiltertes Sample pro 5 Raw-Samples.
- **R16 raw (1 584 Byte):** 500 × 3-Byte-Slots @34:
  `raw18 = ((b0&3)<<16)|(b1<<8)|b2`, signiert 18 Bit (±131072), Flags in b0-Bit 6/7. Danach folgen
  eine Lead-off-Anzahl @1534 und 11 I- sowie 11 Q-Halbwörter. Flag 7 wird in Gruppen 51/50×8/49 auf
  die Samples verteilt.
- Ungeklärt: **Abtastrate, Volt pro Count**, Bedeutung der Classifier-Codes, klinische Aussagekraft.

## 13. Firmware-Update und Autorisierung (nur zur Dokumentation)

Container: 512-Byte-Header (Payload-CRC32 @0, Länge @4, Image-Typ @12, Header-CRC32 @504 über
Bytes 8–503). Typ 5 = gzip, Typ 1 = dekomprimiert. Übertragung per 142 (Start), 143 (Offset u32,
≤ 224 Byte Daten), 144 (CRC-Gate), 83 (Verify). 155–159 prüfen ein signiertes, identitätsgebundenes
Zertifikat. **NOOP implementiert weder Update noch Unlock**, und diese Befehle werden nie gesendet.

## 14. Was noch offen ist

| Bereich | Offene Fragen |
|---|---|
| Optik | Wellenlängen und Einheiten in R20/R26/R22, Bedeutung der Blöcke 1/2 (bisher leer); ein Experiment-Harness existiert (`WHOOP5_OPTICAL_EXPERIMENT.md`), bisher ohne ausgewerteten Lauf |
| SpO₂ / Atmung | **Kein** Befehl und kein bestätigtes Feld. R18 @82 ist nur ein Kandidat. In den Console Logs taucht „generated a valid SPO2 during sleep“ auf, allerdings ohne Zahlenwert |
| ECG | Abtastrate, Spannungsskala, Classifier-Semantik, Kontaktschwellen |
| IMU | Output auf Typ 51/52 unbestätigt; aktive Range-Konfiguration nicht aus dem Record ablesbar |
| R18 | Gültigkeit der Bits 7 @36 und @37, Status-Wörter 75–79, Tail-Bytes |
| R22 | v8 nicht abgebildet, Bedeutung der v9-Metadaten und der Kanäle |
| Transport | Format-2-Aushandlung, Replay nach Disconnect, Sequenz-Wrap und Duplikate |
| Konfiguration | Polarität und Wirkung vieler Feature-Flags, Werkseinstellungen, Persistenz nach Reboot |
| Batterie | Skala des Battery-Pack-Ladewerts (NOOP teilt durch 10, nur Client-Konvention) |
| Events | Payloads von 61/62/110/112/120/123, `EXTENDED_BATTERY_INFORMATION`, `STRAP_CONDITION_REPORT` |
| Parität | Korrektur des Console-Headers (u8-Sequenz statt u16-Index) fehlt noch im Android-Decoder |

## 15. Quellen im Repository

- Einstieg: `docs/PROTOCOL.md`, `docs/PROTOCOL_WHOOP5.md`, `docs/PROTOCOL_CONCEPTS.md`
- Themen: `PROTOCOL_TRANSPORT.md`, `PROTOCOL_COMMANDS.md`, `PROTOCOL_CONFIGURATION.md`,
  `PROTOCOL_SENSORS.md`, `PROTOCOL_ECG.md`, `PROTOCOL_ALARMS.md`, `PROTOCOL_UPDATES.md`
- Implementierung und Historie: `PROTOCOL_IMPLEMENTATION.md`, `BLE_REVERSE_ENGINEERING.md`,
  `WHOOP5_DEEP_DATA.md`, `WHOOP5_OPTICAL_EXPERIMENT.md`, `RAW_DATA_CAPTURE.md`
- Code: `Packages/WhoopProtocol/Sources/WhoopProtocol/` (`Framing.swift`, `Interpreter.swift`,
  `Whoop5*.swift`, `Resources/whoop_protocol.json`); Android unter `android/…/com/noop/protocol/`
- Externe Vorarbeiten: b-nnett/goose, judes.club, Asherlc/dofek, Issue #103
