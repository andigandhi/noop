# NOOP-Scores: Charge, Effort, Rest – Stand und Bewertung

Stand: `main` @ `141cbd93`, 25.09.2026. Grundlage sind der Code in `Packages/StrandAnalytics` bzw.
`Strand/` und die Dokumentation in `docs/ANALYTICS.md`.

> **Hinweis zu den Quellen:** Das Repository zitiert selbst nur einige der unten genannten Arbeiten
> (Task Force 1996, Malik 1989, Karvonen, Edwards, Banister, Tanaka, Walch 2019, te Lindert,
> Van Dongen 2003, Banks 2010, Doty 2020). Die übrigen Quellen sind aus dem Fachwissen ergänzt und
> wurden für dieses Dokument **nicht online verifiziert**. Vor einer Veröffentlichung oder einem PR
> bitte Jahr, Journal und Kernaussage gegenprüfen.

---

## 1. Überblick

| Score | Frage | Engine | Interner Schlüssel | Skala |
|---|---|---|---|---|
| **Charge** | Wie erholt bin ich? | `RecoveryScorer` | `recovery` | 0–100, logistisch |
| **Effort** | Wie stark wurde das Herz belastet? | `StrainScorer` | `strain` | 0–100, logarithmisch (optional 0–21) |
| **Rest** | Wie erholsam war der Schlaf? | `AnalyticsEngine.Rest` | `sleep_performance` | 0–100, gewichtete Summe |

Abhängigkeiten zwischen den Scores:
- Rest fließt mit 15 % in Charge ein.
- Charge bestimmt die angezeigte „optimale“ Effort-Spanne.
- Effort fließt in die Trainingslast-Modelle ein (`ReadinessEngine`, `TrainingLoadEngine`).

---

## 2. Charge (Erholung)

### 2.1 Berechnung

**Eingangswerte der Hauptnacht**
- **HRV:** Mittelwert der RMSSD aus 5-Minuten-Fenstern im Schlaf (`sessionAvgHRV`). Vor der Berechnung
  werden Intervalle außerhalb 300–2000 ms verworfen und Extraschläge nach Malik entfernt
  (> 20 % Abweichung vom lokalen Median über 5 Schläge). Pro Fenster sind mindestens 20 saubere
  Intervalle nötig.
- **Ruhe-HF:** der niedrigste 5-Minuten-Mittelwert der Nacht (`sessionRestingHR`).
- **Atemfrequenz**, **Hauttemperatur-Abweichung** (±°C) und **Rest**.

**Persönliche Baseline** (`Baselines.swift`)
- Gleitender Mittelwert mit abnehmender Gewichtung (EWMA), Halbwertszeit 14 Nächte.
- Die Streuung wird als EWMA der absoluten Abweichung mit 21 Nächten Halbwertszeit verfolgt.
- Ausreißer werden gekappt (Winsorisierung bei ±3 Streuungen). Werte mit mehr als 5 Streuungen
  Abstand werden verworfen.
- Status: *calibrating* unter 4 Nächten, *provisional* bei 4–13, *trusted* ab 14.

**Standardisierung und Verdichtung**
```text
z_i   = (Wert − Baseline) / (1,253 · Streuung)       # Vorzeichen umgedreht bei Ruhe-HF und Atemfrequenz
z_Rest = (Rest/100 − 0,85) / 0,12
z_Temp = −|ΔT| / 1,0 °C
Z     = Σ w_i · z_i / Σ w_i                          # fehlende Terme fallen weg, Gewichte werden neu verteilt
Charge = 100 / (1 + e^(−1,6 · (Z + 0,2)))            # Z = 0 ergibt ≈ 58
```

| Messgröße | Gewicht |
|---|---|
| HRV | 0,55 |
| Ruhe-HF | 0,20 |
| Rest | 0,15 |
| Atemfrequenz | 0,05 |
| Hauttemperatur | 0,05 |
| optional: Recovery Index (nächtlicher Abfall der Ruhe-HF) | 0,05 |
| optional: Activity Balance (Effort des Vortags) | 0,05 |

- Farbbänder: rot < 34, gelb 34–66, grün ≥ 67.
- Ohne verwendbare HRV-Baseline gibt es keinen Wert, die App zeigt „Calibrating“.
- Für stark parasympathisch dominierte Nächte ist eine Korrektur eingebaut („parasympathetic
  saturation guard“). Sie wird aber **nur protokolliert und nicht angewendet**.

**Weitere Engines**
- **`HRVReadiness`** (Experimental, standardmäßig aus): Stufen nach Plews und Altini, berechnet aus
  ln(RMSSD), einem 7-Nächte-Schnitt und einem Normalbereich von ±0,5 SD.
- **`ReadinessEngine`**: Verhältnis akuter zu chronischer Belastung (ACWR, 7/28 Tage) und
  Foster-Monotonie als Hinweissignale.

### 2.2 Wissenschaftliche Grundlage

| Baustein | Quelle | Stützung |
|---|---|---|
| RMSSD, Datenbereinigung | Task Force ESC/NASPE (1996), *Circulation* 93:1043; Malik et al. (1989) | stark (Messstandard) |
| HRV relativ zur eigenen Baseline | Plews et al. (2013), *Sports Med* 43:773; Buchheit (2014), *Front Physiol* 5:73 | stark |
| HRV-gesteuertes Training | Kiviniemi et al. (2007), *Eur J Appl Physiol* 101:743; Vesterinen et al. (2016), *MSSE* 48:1347; Javaloyes et al. (2019), *IJSPP* 14:1334 | mittel bis stark |
| Nächtliche HRV als Messzeitpunkt | Nuuttila et al. (2022), *MSSE* 54:1776 | mittel |
| Ruhe-HF als Ermüdungszeichen | Buchheit (2014); Bosquet et al. (2008), *Sports Med* 38:1045 | schwach bis mittel, uneinheitlich |
| Hauttemperatur und Atemfrequenz bei Infekten | Mason et al. (2022), *Sci Rep* 12:3463; Miller et al. (2020), *PLoS ONE* (WHOOP-finanziert) | mittel, aber für Krankheit und nicht für Erholung |
| Parasympathische Sättigung | Plews et al. (2012), *Eur J Appl Physiol* 112:3729 | mittel |
| Gewichte, Kurvenparameter, Bänder | – | **keine**, eigene Festlegungen |
| 58 % als Mittelpunkt | WHOOP-Durchschnitt der Nutzer | Produktkennzahl, keine Wissenschaft |

### 2.3 Bewertung

**Stärken**
- Die Berechnung setzt HRV ins Zentrum und normalisiert auf die persönliche Baseline. Das entspricht dem
  Stand der Sportwissenschaft.
- Die Baseline ist robust gegen Ausreißer (Winsorisierung, Ausschluss grober Ausreißer).
- Der Code ist ehrlich im Umgang mit fehlenden Daten: Fehlt die Baseline, gibt es „Calibrating“ statt
  einer erfundenen Zahl. Fehlende Terme werden neu gewichtet.
- Alle Konstanten sind dokumentiert, der Score ist nachvollziehbar.

**Schwächen**
1. Die HRV geht als **rohe RMSSD** ein, nicht als **ln(RMSSD)**. RMSSD ist rechtsschief verteilt, deshalb
   sind die z-Werte mit Normalverteilungsannahme verzerrt (Plews 2012/2013).
2. Es wird eine **einzelne Nacht** gegen die Baseline gestellt. Die Literatur empfiehlt einen
   **7-Tage-Schnitt**, weil ein einzelner Tag viel Rauschen enthält.
3. Die **Gewichte und die Kurvenform** sind nicht aus Daten abgeleitet. Es gibt **keine Validierung**
   gegen Leistung, Krankheit oder subjektive Erholung. Die einzige genannte Prüfung ist die Korrelation
   r ≈ 0,71 mit Oura Readiness, also ein Vergleich zweier unvalidierter Scores.
4. Die Sättigungskorrektur ist deaktiviert. Sehr fitte Personen können bei guter Erholung zu niedrige
   Charge-Werte bekommen.
5. Hauttemperatur und Atemfrequenz zeigen eher Krankheit als Erholung an. Als lineare Abzüge sind sie
   methodisch fragwürdig.

### 2.4 Verbesserungsvorschläge

| # | Vorschlag | Begründung / Quelle |
|---|---|---|
| C1 | Im HRV-Term ln(RMSSD) verwenden | Plews et al. (2012, 2013) |
| C2 | Den 7-Nächte-Schnitt gegen den Normalbereich ±0,5 SD als Haupttreiber verwenden; `HRVReadiness` ist bereits implementiert und müsste nur eingebunden werden | Plews (2013); Javaloyes (2019) |
| C3 | Die Tagesschwankung (CV von ln(RMSSD), 7 Tage) als Zusatzsignal nutzen | Plews et al. (2012); Flatt & Esco (2016), *JSCR* |
| C4 | Hauttemperatur und Atemfrequenz als **Warnschwelle** behandeln (z. B. > 2 SD), nicht als lineare Gewichte | Mason (2022); Miller (2020) |
| C5 | Die Sättigungskorrektur nach Prüfung echter Fälle aktivieren, und zwar nur, wenn Ruhe-HF *und* HRV gleichzeitig niedrig sind | Plews (2012); Buchheit (2014) |
| C6 | Gewichte offen validieren: tägliche subjektive Erholung abfragen (z. B. Hooper-Index oder Skala nach Laurent) und die Gewichte daran prüfen | Hooper et al. (1995), *MSSE*; Laurent et al. (2011), *JSCR* |
| C7 | Die Bänder als persönliche Perzentile statt als feste 34/67 berechnen | Folgt aus der Individualisierung (Buchheit 2014) |

---

## 3. Effort (kardiovaskuläre Belastung)

### 3.1 Berechnung

**Grundgrößen** (`StrainScorer.swift`)
- HF-Reserve nach Karvonen: `HRR = HFmax − Ruhe-HF`, Intensität `%HRR = (HF − Ruhe-HF)/HRR`, begrenzt auf
  0–100 %.
- **HFmax:** das 99,5. Perzentil der gemessenen HF (bei mindestens 600 Werten), mindestens aber der
  Tanaka-Wert `208 − 0,7·Alter`.

**TRIMP (Trainingsimpuls)**
- **Edwards** (Standard): Zonengewichte 1–5 bei 50/60/70/80/90 %HRR, jeweils × Minuten.
- **Banister** (wählbar): `Σ Dauer · x · 0,64 · e^(b·x)`, mit b = 1,92 für Männer und 1,67 für Frauen.
  Abgezogen wird ein Sockel für sitzende Tätigkeit bei 10 %HRR, damit ein Bürotag nicht bei etwa 45
  landet (#1624).

**Log-Skala**
```text
Effort = 100 · ln(TRIMP + 1) / ln(D),   D = 7201 (Edwards: 5 × 1440 min + 1)
```
Für Banister gibt es einen eigenen Nenner. Voraussetzung sind mindestens 600 HF-Werte, bei dünnem
5/MG-Datenstrom mindestens 20 Werte über ≥ 10 min.

**Anzeige und Umfeld**
- **„Optimale“ Tagesspanne** (`CoupledView.optimalStrainRange`, feste Tabelle, nur Anzeige):
  grün 14–18, gelb 10–14, rot 4–10 auf der Skala 0–21.
- **Trainingslast:** `TrainingLoadEngine` berechnet CTL/ATL/TSB (τ = 42 bzw. 7 Tage) über die
  Effort-Werte, rein beschreibend. `ReadinessEngine` liefert ACWR und Foster-Monotonie als Hinweise.
- **Unstimmigkeit:** `docs/ANALYTICS.md` beschreibt einen Mindestwert für Effort aus Schritten bzw.
  Aktivkalorien. Im `StrainScorer` bzw. in `AnalyticsEngine` war dafür **kein Code zu finden**. Die Doku
  ist hier vermutlich veraltet und sollte geprüft werden.

### 3.2 Wissenschaftliche Grundlage

| Baustein | Quelle | Stützung |
|---|---|---|
| HF-Reserve | Karvonen et al. (1957), *Ann Med Exp Biol Fenn* 35:307 | stark |
| Edwards-TRIMP | Edwards (1993), *The Heart Rate Monitor Book* | mittel (Buch, weit verbreitet) |
| Banister-TRIMP | Banister (1991), in *Physiological Testing of the High-Performance Athlete*; Morton et al. (1990), *J Appl Physiol* 69:1171 | stark als Belastungsmaß |
| HFmax-Formel | Tanaka et al. (2001), *JACC* 37:153 | stark auf Gruppenebene, individuell ±10 bpm |
| TRIMP als internes Belastungsmaß | Borresen & Lambert (2009), *Sports Med* 39:779; Impellizzeri et al. (2019), *IJSPP* 14:270 | stark |
| Fitness-Fatigue-Modell (CTL/ATL) | Banister et al. (1975); Busso (2003), *MSSE* 35:1188; Hellard et al. (2006), *IJSPP* | mittel, individuelle Parameter instabil |
| Foster-Monotonie | Foster (1998), *MSSE* 30:1164 | mittel |
| ACWR | Gabbett (2016), *BJSM* 50:273; **Kritik:** Impellizzeri et al. (2020), *IJSPP* 15:907 | umstritten |
| Log-Skala mit D = 7201 | WHOOP/NOOP-Konvention | **keine** |
| „Optimale“ Spanne nach Charge-Farbe | – | **keine** |

### 3.3 Bewertung

**Stärken**
- Die Basis besteht aus etablierten Belastungsmaßen (Karvonen, Edwards, Banister).
- HFmax wird aus den eigenen Daten bestimmt und mit Tanaka nach unten abgesichert.
- Der Banister-Sockel und die eigenen Nenner je Methode sind durchdachte Korrekturen.
- Der Umgang mit dünnen Datenströmen ist ehrlich: Bei zu wenig Daten gibt es keinen Wert statt einer 0.
- CTL/ATL/TSB und Monotonie sind bereits als beschreibende Größen vorhanden.

**Schwächen**
1. Die **Log-Skala** staucht die Belastung stark. Zwischen Effort 14 und 18 (Skala 0–21) liegt etwa der
   Faktor 5 an TRIMP (ca. 370 vs. 2 000 Edwards-Zonen-Minuten, grob nachgerechnet). Für Vergleiche über
   Tage ist TRIMP selbst aussagekräftiger.
2. **CTL/ATL werden auf Effort berechnet, nicht auf TRIMP.** Das Banister-Modell setzt eine **lineare**
   Belastungsgröße voraus. Auf einer log-Skala ist die Aufsummierung physiologisch nicht sinnvoll. Der
   Code weist selbst darauf hin, dass die Werte nicht TRIMP sind.
3. **Edwards** ignoriert alles unter 50 %HRR. Leichte Aktivität zählt nicht, und an den Zonengrenzen
   springt der Wert.
4. **Krafttraining und kurze intervallartige Belastungen** werden unterschätzt, weil die HF verzögert
   reagiert. Das ist eine bekannte Grenze HF-basierter Maße (Borresen & Lambert 2009).
5. Die **„optimale“ Spanne** besteht aus drei festen Stufen ohne Quelle, ohne Personalisierung und ohne
   Bezug zur Trainingshistorie.

### 3.4 Verbesserungsvorschläge

| # | Vorschlag | Begründung / Quelle |
|---|---|---|
| E1 | TRIMP pro Tag als lineare Größe speichern und `TrainingLoadEngine` mit **TRIMP statt Effort** füttern | Banister (1975); Morton (1990); Busso (2003) |
| E2 | Die feste Spanne durch eine **Empfehlung zur Intensität** ersetzen (HRV-7-Tage-Schnitt gegen den Normalbereich, dann locker/moderat/intensiv) | Kiviniemi (2007); Vesterinen (2016); Javaloyes (2019); Nuuttila (2022) |
| E3 | Die Kategorie **personalisiert in TRIMP übersetzen**, bezogen auf CTL (z. B. intensiv ≈ CTL halten bzw. leicht steigern, locker deutlich darunter); die Faktoren als Praxisregel kennzeichnen | Banister-Modell; Faktoren nicht validiert |
| E4 | Foster-Monotonie und Wochenbelastung als Leitplanken zeigen und auf ACWR verzichten bzw. es klar als umstritten kennzeichnen | Foster (1998); Impellizzeri (2020) |
| E5 | Die wöchentliche Intensitätsverteilung (Zone 1–2 vs. 4–5) anzeigen | Seiler (2010), *IJSPP* 5:276; Stöggl & Sperlich (2014), *Front Physiol* 5:33 |
| E6 | Optional sRPE (subjektives Anstrengungsempfinden × Dauer) erfassen, besonders für Krafttraining | Foster et al. (2001), *JSCR* 15:109; Haddad et al. (2017), *Front Neurosci* |
| E7 | Die veraltete Doku zum Schritt-Mindestwert korrigieren oder die Funktion umsetzen | Konsistenz („Two readouts of one fact“, AGENTS.md) |

---

## 4. Rest (Schlaferholung)

### 4.1 Berechnung

**Schlaferkennung** (`SleepStager.swift`; in der App ist `SleepStagerV2` standardmäßig aktiv)
- Stillephasen werden über Änderungen des Schwerkraftvektors erkannt (< 0,01 g, 70 % still in
  15-Minuten-Fenstern) und mit der HF bestätigt.
- Als Gegenprüfung dient der Cole–Kripke-Index nach te Lindert.
- Wach wird nicht allein wegen erhöhter HF vergeben, wenn keine Bewegung vorliegt.

**Schlafstadien:** 30-s-Epochen werden über session-relative Perzentile eingeteilt.
- *Deep:* still, RMSSD ≥ 70. Perzentil, HF ≤ 25. Perzentil, regelmäßige Atmung.
- *REM:* still, aktiviertes Herz-Kreislauf-System, unregelmäßige Atmung.
- Danach Glättung und physiologische Regeln (kein REM in den ersten 15 min, kein Deep nach dem ersten
  Drittel der Nacht).

**Rest-Score** (`AnalyticsEngine.Rest.composite`)
```text
Dauer       = min(1, Schlafdauer / Schlafbedarf)                                      × 0,50
Effizienz   = Schlafdauer / Zeit im Bett                                              × 0,20
Erholsamkeit = min(1, (Deep+REM)/Schlafdauer / 0,50) · DeepFaktor                     × 0,20
               DeepFaktor = 0,5 + 0,5·min(1, (Deep/Schlafdauer)/0,13)
Konstanz    = 1 − CV der Schlafdauer (≥ 3 Nächte; sonst neutral 0,5)                  × 0,10
Rest = 100 · Σ
```

**Schlafbedarf:** das 75. Perzentil der eigenen Schlafdauer (ab 7 Nächten). Untergrenze ist der
Bevölkerungszielwert nach NSF/AASM (8 h für Erwachsene, 9 h unter 18), Obergrenze 9,5 h.

**Schlafschuld:** `nächsteSchuld = 0,55 · max(0, Bedarf − Schlaf)`. Der Faktor 0,55 wurde an 853 Nächten
einer einzelnen Person gegen die WHOOP-Werte kalibriert.

### 4.2 Wissenschaftliche Grundlage

| Baustein | Quelle | Stützung |
|---|---|---|
| Schlafbedarf 7–9 h für Erwachsene | Hirshkowitz et al. (2015), *Sleep Health* 1:40 (NSF); Watson et al. (2015), *Sleep* 38:843 (AASM/SRS) | stark |
| Schlafeffizienz, AASM-Kennzahlen | AASM Scoring Manual; Ohayon et al. (2017), *Sleep Health* 3:6 (Effizienz ≥ 85 % als gut) | stark |
| Konstanz / Regelmäßigkeit | Phillips et al. (2017), *Sci Rep* 7:3216 (Sleep Regularity Index); Windred et al. (2024), *Sleep* 47 (UK Biobank) | stark, aber für den **SRI** und nicht für den CV der Dauer |
| Schlafschuld und Erholungsdynamik | Van Dongen et al. (2003), *Sleep* 26:117; Banks et al. (2010), *Sleep* 33:1013; Doty et al. (2020) | stark als Prinzip, Faktor 0,55 empirisch an n = 1 |
| Stadien aus HF und Bewegung | Walch et al. (2019), *Sleep* 42 (≈ 65–73 % Übereinstimmung pro Epoche); te Lindert & Van Someren (2013), *Sleep* 36:781 | mittel; Deep/Light ist am unsichersten |
| Deep+REM ≈ 40–50 %, Deep ≥ 13 % als „gut“ | Ohayon et al. (2004), *Sleep* 27:1255 (Normwerte nach Alter) | mittel; stark altersabhängig |
| Gewichte 0,5/0,2/0,2/0,1 | – | **keine** |

### 4.3 Bewertung

**Stärken**
- Die Dauer im Verhältnis zum persönlichen Bedarf hat das größte Gewicht. Das deckt sich mit der
  Evidenz: Dauer ist der am besten belegte Faktor.
- Der Schlafbedarf kann nicht unter den Bevölkerungszielwert fallen. Chronischer Schlafmangel wird so
  nicht als persönlicher Normalzustand gelernt.
- Die Schlafschuld-Logik ist sauber begründet und ehrlich als Planungshilfe gekennzeichnet.
- Die Grenzen der Stadienerkennung sind offen dokumentiert (Walch 2019).

**Schwächen**
1. **40 % des Scores** (Erholsamkeit und Effizienz) hängen von Stadien und Wach-Erkennung ab. Genau diese
   sind ohne EEG am unzuverlässigsten, besonders Deep vs. Light. Beim WHOOP 5/MG kommt hinzu, dass die
   Bewegungsdaten laut Doku teils lückenhaft sind (#345).
2. **Konstanz = 1 − CV der Dauer** misst nur, wie gleich lang die Nächte sind, **nicht die
   Regelmäßigkeit der Uhrzeiten**. Gerade die Uhrzeiten sind im SRI gesundheitlich relevant (Phillips
   2017; Windred 2024). Die Daten dafür (Einschlaf- und Aufwachzeit) liegen vor.
3. Die **Zielwerte** 50 % Deep+REM und 13 % Deep sind **nicht altersangepasst**. Deep nimmt mit dem
   Alter deutlich ab (Ohayon 2004), ältere Nutzer werden dadurch systematisch abgewertet.
4. Die **Gewichte** sind eigene Festlegungen und nicht validiert.
5. Der Faktor 0,55 für die Schlafschuld ist an einer einzigen Person kalibriert.

### 4.4 Verbesserungsvorschläge

| # | Vorschlag | Begründung / Quelle |
|---|---|---|
| R1 | Konstanz als **Sleep Regularity Index** oder als Streuung des Schlafmittelpunkts berechnen statt als CV der Dauer | Phillips et al. (2017); Windred et al. (2024) |
| R2 | Die Zielwerte für Deep und REM **altersabhängig** machen | Ohayon et al. (2004) |
| R3 | Das Gewicht der Erholsamkeit senken (z. B. 0,10) bzw. an die Datenqualität koppeln (bei lückenhafter Bewegung → neutral) | Walch (2019); #345 |
| R4 | Die Schlafdauer als Kurve statt linear bis zur Obergrenze bewerten und leichte Abzüge für deutliche Überlänge ergänzen | Watson (2015): > 9 h ohne Nutzen, U-förmige Zusammenhänge |
| R5 | Den Schlafschuld-Faktor mit weiteren Datenspenden prüfen (mehrere Personen) | Van Dongen (2003); Banks (2010) |
| R6 | Optional die subjektive Schlafqualität erfassen und mit Rest abgleichen | Buysse et al. (1989), *Psychiatry Res* (PSQI) |

---

## 5. Gesamtbewertung

| Kriterium | Charge | Effort | Rest |
|---|---|---|---|
| Bausteine wissenschaftlich fundiert | ✅ | ✅ | ✅ (Dauer) / ⚠️ (Stadien) |
| Personalisierung | ✅ Baseline | ⚠️ nur HFmax und Ruhe-HF | ✅ Schlafbedarf |
| Gewichte/Skalierung begründet | ❌ | ❌ (Log-Skala, Spanne) | ❌ |
| Gegen Zielgrößen validiert | ❌ (nur r ≈ 0,71 mit Oura) | ❌ | ❌ (Stadien: Literaturwert) |
| Transparenz | ✅ | ✅ | ✅ |
| Umgang mit fehlenden Daten | ✅ | ✅ | ✅ |

**Fazit:** NOOP baut die drei Scores ehrlich und nachvollziehbar aus etablierten Einzelmethoden auf. Die
**Verdichtung** zu einer Zahl von 0–100 beruht aber bei allen dreien auf nicht validierten Gewichten und
Skalen. Das gilt allerdings genauso für die proprietären Scores von WHOOP und Oura. Bei den
Verbesserungen ist das Verhältnis von Nutzen zu Aufwand am besten bei:

1. **C1/C2:** ln(RMSSD) und den 7-Tage-Schnitt in Charge übernehmen. `HRVReadiness` existiert bereits.
2. **E1:** CTL/ATL auf linearer TRIMP statt auf Effort berechnen.
3. **E2/E3:** Die feste „optimale“ Spanne durch eine HRV-gesteuerte Empfehlung zur Intensität ersetzen.
4. **R1:** Konstanz über die Regelmäßigkeit der Uhrzeiten berechnen.
5. **C6:** Subjektive Erholung erfassen, um die Gewichte überhaupt validieren zu können.

**Projektregeln bei der Umsetzung (AGENTS.md):**
- Jede Änderung an Analytics muss in **Swift und Kotlin identisch** umgesetzt werden, mit Oracle-Test.
- Neue Methoden gehören zunächst hinter einen **Experimental-Schalter** (standardmäßig aus).
- Eine Methode muss nachweislich **variierenden Werten folgen**. Eine einzelne passende Nacht zählt
  nicht als Validierung.
- Pro PR nur **ein Thema**.
