# Übersetzungsfixes - Zusammenfassung

## Behobene Probleme

### 1. HealthScreen.kt - String-Konkatenation behoben
**Datei:** `android/app/src/main/java/com/noop/ui/HealthScreen.kt:1994`

**Problem:** Der String `l10n_health_screen_one_reading_so_far_your_trend_eaad57f2` wurde mit dem hartcodierten englischen Text `"reading lands."` konkateniert.

**Lösung:**
- Den bestehenden String in allen Sprachen aktualisiert, um den vollständigen Satz zu enthalten
- Die String-Konkatenation im Code entfernt

**Aktualisierte Strings:**
- Englisch: "One reading so far — your trend chart fills in here once a second until a reading lands."
- Deutsch: "Eine Lektüre bisher - dein Trendchart füllt sich hier einmal pro Sekunde aus, bis eine Messung eintrifft."
- Französisch: "Une lecture à ce jour — votre graphique de tendance remplit ici une fois par seconde jusqu'à ce qu'une lecture arrive."
- Spanisch: "Una lectura hasta ahora — su gráfico de tendencia se llena aquí una vez por segundo hasta que llega una lectura."
- Portugiesisch: "Uma leitura até agora – o teu gráfico de tendências é aqui preenchido uma vez por segundo até chegar uma leitura."
- Chinesisch: "目前只有一条读数 — 您的趋势图将在此处按秒实时更新，直到新的读数到达。"
- Polnisch: "Jak dotąd jeden odczyt — wykres trendu wypełnia się tutaj raz na sekundę, aż pojawi się odczyt."
- Russisch: "Пока одно измерение — график тренда появится здесь, как только будет второе измерение."

### 2. DataSourcesScreen.kt - "not yet" übersetzt
**Datei:** `android/app/src/main/java/com/noop/ui/DataSourcesScreen.kt:562`

**Problem:** Der Text `"not yet"` war hartcodiert.

**Lösung:**
- Neue String-Ressource `l10n_data_sources_screen_not_yet` erstellt
- Code aktualisiert, um die String-Ressource zu verwenden
- Übersetzungen in allen Sprachen hinzugefügt

### 3. TestCentreScreen.kt - "Share captured log" übersetzt
**Datei:** `android/app/src/main/java/com/noop/ui/TestCentreScreen.kt:833`

**Problem:** Der Button-Text `"Share captured log"` war hartcodiert.

**Lösung:**
- Neue String-Ressource `l10n_test_centre_screen_share_captured_log` erstellt
- Code aktualisiert, um die String-Ressource zu verwenden
- Übersetzungen in allen Sprachen hinzugefügt

### 4. TrendsScreen.kt - "Share recap" übersetzt
**Datei:** `android/app/src/main/java/com/noop/ui/TrendsScreen.kt:402`

**Problem:** Der Button-Text `"Share recap"` war hartcodiert.

**Lösung:**
- Neue String-Ressource `l10n_trends_screen_share_recap` erstellt
- Code aktualisiert, um die String-Ressource zu verwenden
- Übersetzungen in allen Sprachen hinzugefügt

### 5. SettingsScreen.kt - Zwei Button-Texte übersetzt
**Datei:** `android/app/src/main/java/com/noop/ui/SettingsScreen.kt:1872,1931`

**Problem:** Die Button-Texte `"Browse files"` und `"Remove image"` waren hartcodiert.

**Lösung:**
- Neue String-Ressourcen `l10n_settings_screen_browse_files` und `l10n_settings_screen_remove_image` erstellt
- Code aktualisiert, um die String-Ressourcen zu verwenden
- Übersetzungen in allen Sprachen hinzugefügt

### 6. SleepScreen.kt - "Raw on-device stages" übersetzt
**Datei:** `android/app/src/main/java/com/noop/ui/SleepScreen.kt:1574`

**Problem:** Der Text `"Raw on-device stages"` war hartcodiert.

**Lösung:**
- Neue String-Ressource `l10n_sleep_screen_raw_on_device_stages` erstellt
- Code aktualisiert, um die String-Ressource zu verwenden
- Übersetzungen in allen Sprachen hinzugefügt

## Unterstützte Sprachen

Alle neuen Strings wurden in folgende Sprachen übersetzt:
- Deutsch (de)
- Französisch (fr)
- Spanisch (es)
- Portugiesisch (pt-rPT)
- Chinesisch (zh)
- Polnisch (pl)
- Russisch (ru)

## Dateien geändert

### Kotlin-Dateien:
1. `android/app/src/main/java/com/noop/ui/HealthScreen.kt`
2. `android/app/src/main/java/com/noop/ui/DataSourcesScreen.kt`
3. `android/app/src/main/java/com/noop/ui/TestCentreScreen.kt`
4. `android/app/src/main/java/com/noop/ui/TrendsScreen.kt`
5. `android/app/src/main/java/com/noop/ui/SettingsScreen.kt`
6. `android/app/src/main/java/com/noop/ui/SleepScreen.kt`

### String-Ressourcen-Dateien:
1. `android/app/src/main/res/values/strings.xml` (Englisch)
2. `android/app/src/main/res/values-de/strings.xml` (Deutsch)
3. `android/app/src/main/res/values-fr/strings.xml` (Französisch)
4. `android/app/src/main/res/values-es/strings.xml` (Spanisch)
5. `android/app/src/main/res/values-pt-rPT/strings.xml` (Portugiesisch)
6. `android/app/src/main/res/values-zh/strings.xml` (Chinesisch)
7. `android/app/src/main/res/values-pl/strings.xml` (Polnisch)
8. `android/app/src/main/res/values-ru/strings.xml` (Russisch)

## Weitere hartcodierte Strings

Das i18n-Audit-Tool (`Tools/i18n_audit.py`) hat insgesamt 236 hartcodierte Strings in der Android App gefunden. Diese Änderungen beheben die wichtigsten Fälle von String-Konkatenationen und häufig verwendeten UI-Texten. Weitere hartcodierte Strings können in zukünftigen PRs behoben werden.
