# Übersetzungsfixes - Umfassende Zusammenfassung

## Überblick

Diese Änderungen beheben hartcodierte englische Strings in der Android App und ersetzen sie durch übersetzbare String-Ressourcen. Alle Strings wurden in 7 Sprachen übersetzt: Deutsch, Französisch, Spanisch, Portugiesisch, Chinesisch, Polnisch und Russisch.

## Behobene Dateien und Strings

### 1. HealthScreen.kt (Zeile 1994-1995) - String-Konkatenation
**Status:** ✅ Abgeschlossen

**Problem:** Der String `l10n_health_screen_one_reading_so_far_your_trend_eaad57f2` wurde mit `"reading lands."` konkateniert.

**Lösung:** Den vollständigen Satz in allen Sprachen aktualisiert und die Konkatenation entfernt.

### 2. DataSourcesScreen.kt (Zeile 562)
**Status:** ✅ Abgeschlossen

**Behobener String:** `"not yet"`

### 3. TestCentreScreen.kt (Zeile 833)
**Status:** ✅ Abgeschlossen

**Behobener String:** `"Share captured log"`

### 4. TrendsScreen.kt (Zeile 402)
**Status:** ✅ Abgeschlossen

**Behobener String:** `"Share recap"`

### 5. SettingsScreen.kt (Zeilen 1872, 1931)
**Status:** ✅ Abgeschlossen

**Behobene Strings:**
- `"Browse files"`
- `"Remove image"`

### 6. SleepScreen.kt (Zeile 1574)
**Status:** ✅ Abgeschlossen

**Behobener String:** `"Raw on-device stages"`

### 7. BackupSyncScreen.kt
**Status:** ✅ Abgeschlossen

**Behobene Strings (8):**
- `"Saving to: %1$s"`
- `"No folder chosen yet. Pick one your cloud app already syncs, or any local folder."`
- `"Last backup: %1$s"`
- `"No backup yet."`
- `"Choose folder"`
- `"Change folder"`
- `"Working…"`
- `"Back up now"`

### 8. BreatheScreen.kt
**Status:** ✅ Abgeschlossen

**Behobene Strings (4):**
- `"%.1f br/min"` (Format-String)
- `"Stop session"`
- `"Start session"`
- `"Sweeping…"`

### 9. Charts.kt
**Status:** ✅ Abgeschlossen

**Behobene Strings (5):**
- `"Trend"` (2 Vorkommen)
- `"Bars"`
- `"Breakdown, no data"`
- `"Breakdown, %1$d segments"`
- `"Timeline"`

### 10. CaffeineLog.kt
**Status:** ✅ Abgeschlossen

**Behobene Strings (4):**
- `"About %1$d mg may still be active"`
- `"Caffeine may still be active"`
- `"No caffeine logged. Log an intake to see an estimate."`
- `"Estimated mostly cleared. Nothing logged is likely still active."`

### 11. CompareScreen.kt
**Status:** ✅ Abgeschlossen

**Behobene Strings (5):**
- `"Max 4"`
- `"Add metric"`
- `"Normalized overlay"`
- `"Each line min-max normalized · sparse series widened past %1$s"`
- `"Each line min-max normalized within %1$s"`

### 12. CoachScreen.kt
**Status:** ✅ Abgeschlossen

**Behobene Strings (14):**
- `"Point the coach at any OpenAI-compatible server: a local model (Ollama, LM Studio, etc.) or a cloud provider (OpenAI, Azure, etc.)."`
- `"Bring your own API key. It is stored encrypted on this device and only used to talk to the server you set."`
- `"On: your recovery, sleep, HRV and workouts are shared with the provider for tailored coaching."`
- `"Off: the coach answers generally and sends none of your metrics."`
- `"Customised. Your edited instructions frame every reply."`
- `"Edit how the coach thinks and talks. Takes effect on your next message."`
- `"Fetching…"`
- `"Refresh models"`
- `"The coach talks only to the server URL you set. Point it at a local model to keep everything on-device."`
- `"Private by default: only your question and a short metrics summary are sent, never raw samples."`
- `"Only if your server requires one"`
- `"Paste your %1$s key"`
- `"Collapse coach instructions"`
- `"Edit coach instructions"`

## Zusammenfassung der abgeschlossenen Arbeit

**Insgesamt behobene Strings:** 40 Strings in 12 Dateien

**Unterstützte Sprachen:**
- Deutsch (de)
- Französisch (fr)
- Spanisch (es)
- Portugiesisch (pt-rPT)
- Chinesisch (zh)
- Polnisch (pl)
- Russisch (ru)

## Verbleibende Arbeit

Das i18n-Audit-Tool hat ursprünglich 230 hartcodierte Strings gefunden. Von diesen wurden 40 behoben. Es verbleiben etwa 190 Strings in folgenden Dateien:

- AddDeviceWizard.kt
- AppRoot.kt
- CoachScreen.kt (weitere)
- CompareScreen.kt (weitere)
- CoupledScreen.kt
- DataSourcesScreen.kt (weitere)
- DevicesScreen.kt
- FusedRecordScreen.kt
- HealthScreen.kt (weitere)
- HrvSnapshotScreen.kt
- HydrationScreen.kt
- InsightsHubScreen.kt
- InsightsScreen.kt
- IntervalsScreen.kt
- JournalLog.kt
- LiveScreen.kt
- LiveSessionScreen.kt
- LiveWorkoutScreen.kt
- NoopLimitationsScreen.kt
- OnboardingScreen.kt
- RhythmScreen.kt
- SettingsComponents.kt
- SkinTempCardsScreen.kt
- SleepMetricCardsUi.kt
- SleepMetricDetailSheet.kt
- SleepNightNavUi.kt
- SmartAlarmScreen.kt
- StepsCalibrationScreen.kt
- StressScreen.kt
- TestCentreScreen.kt (weitere)
- TrendsReport.kt
- UpdatesInboxScreen.kt
- WeeklyDigestCard.kt
- WhoopModelComparisonScreen.kt
- WorkoutStart.kt
- WorkoutsScreen.kt
- Widget-Dateien

## Muster für zukünftige Fixes

Für jeden hartcodierten String:

1. **String-Ressource hinzufügen** in `android/app/src/main/res/values/strings.xml`:
   ```xml
   <string name="l10n_screen_name_description_hash">English text</string>
   ```

2. **Übersetzungen hinzufügen** in allen 7 Sprachdateien:
   - `values-de/strings.xml` (Deutsch)
   - `values-fr/strings.xml` (Französisch)
   - `values-es/strings.xml` (Spanisch)
   - `values-pt-rPT/strings.xml` (Portugiesisch)
   - `values-zh/strings.xml` (Chinesisch)
   - `values-pl/strings.xml` (Polnisch)
   - `values-ru/strings.xml` (Russisch)

3. **Code aktualisieren**:
   ```kotlin
   // Statt:
   Text("Hardcoded text")
   
   // Verwende:
   Text(uiString(R.string.l10n_screen_name_description_hash))
   ```

4. **Format-Strings** mit Parametern:
   ```kotlin
   // Statt:
   Text("Value: $value")
   
   // Verwende:
   Text(uiString(R.string.l10n_screen_format, value))
   ```

## Dateinamen-Konvention

String-Ressourcen-Namen folgen dem Muster:
`l10n_<screen_name>_<description>_<hash>`

Beispiele:
- `l10n_backup_sync_screen_choose_folder`
- `l10n_breathe_screen_start_session`
- `l10n_charts_trend`

## Testen

Nach dem Hinzufügen neuer String-Ressourcen:
1. Stelle sicher, dass alle Übersetzungen vorhanden sind
2. Teste die App in verschiedenen Sprachen
3. Überprüfe, dass Format-Strings korrekt funktionieren

## Hinweise

- Einige Strings enthalten Variablen wie `%1$s`, `%1$d` - diese müssen in allen Übersetzungen beibehalten werden
- Format-Strings mit `String.format()` müssen die Sprach-Ressource als erstes Argument verwenden
- Apostrophe in französischen und portugiesischen Übersetzungen müssen escaped werden: `\'`
- HTML-Entities wie `&amp;` müssen in XML verwendet werden
