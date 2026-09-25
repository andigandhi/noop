package com.noop.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import com.noop.R
import com.noop.analytics.AnalyticsEngine
import com.noop.analytics.DetectedSleep
import com.noop.data.V18AuxRow
import kotlin.math.floor
import kotlin.math.roundToInt

// MARK: - Nightly SpO₂ strap-estimate timeline (#103)
//
// The WHOOP 5/MG writes its `spo2_candidate_82` byte (R18 @82) only inside short measurement windows —
// ~30 consecutive records roughly every 20 minutes while the band reports SLEEP — and leaves it 0x00
// everywhere else. Values outside 70..100 inside a window are flag-like codes, not percentages. So the
// honest time series is ONE point per window (the mean of its in-band records), not one per second.
//
// DISPLAY-ONLY, behind the same default-off `NoopPrefs.spo2CandidateDisplay` toggle as the Blood Oxygen
// tile's estimate: the byte is not validated as SpO₂ (docs/WHOOP5_DEEP_DATA.md), so nothing here is
// persisted, scored or fed to a gate. The night mean is delegated to
// `AnalyticsEngine.nightlySpo2CandidateMean`, so the number on this card is the same formula the
// Blood Oxygen tile shows for the night. No iOS twin yet (Android-only UI; the analytics it reads are
// shared and unchanged).

/** One measurement window: the in-band mean of [samples] records centred on [ts]. */
internal data class Spo2Window(
    val ts: Long,
    val mean: Double,
    val samples: Int,
    val min: Int,
    val max: Int,
)

/** The resolved night for [SleepSpo2Card]; [auxRows] = banked v18 rows in the night window at all. */
internal data class Spo2Night(
    val windows: List<Spo2Window>,
    val nightMean: Int?,
    val auxRows: Int,
)

internal object SleepSpo2Timeline {
    /** In-band candidate range, identical to `AnalyticsEngine.nightlySpo2CandidateMean`. */
    const val MIN_PCT = 70L
    const val MAX_PCT = 100L

    /**
     * Largest gap between two in-band records that still counts as the SAME window. Observed windows are
     * 30 s long and 20 min apart, and flag codes can interrupt a window for a few seconds, so any value
     * well above the in-window gaps and well below the inter-window spacing separates them cleanly.
     */
    const val WINDOW_GAP_S = 120L

    /**
     * Group the in-band @82 values that fall inside any of [spans] (inclusive `start..end`, the night's
     * sleep fragments) into measurement windows, ascending by time.
     */
    fun windows(aux: List<V18AuxRow>, spans: List<LongRange>): List<Spo2Window> {
        if (aux.isEmpty() || spans.isEmpty()) return emptyList()
        val inBand = aux.asSequence()
            .mapNotNull { row -> row.auxByte82?.let { row.ts to it } }
            .filter { (ts, v) -> v in MIN_PCT..MAX_PCT && spans.any { ts in it } }
            .sortedBy { it.first }
            .toList()
        if (inBand.isEmpty()) return emptyList()

        val out = ArrayList<Spo2Window>()
        var group = ArrayList<Pair<Long, Long>>()
        fun flush() {
            if (group.isEmpty()) return
            val values = group.map { it.second }
            out += Spo2Window(
                ts = (group.first().first + group.last().first) / 2,
                mean = values.sum().toDouble() / values.size,
                samples = values.size,
                min = values.min().toInt(),
                max = values.max().toInt(),
            )
            group = ArrayList()
        }
        for (p in inBand) {
            if (group.isNotEmpty() && p.first - group.last().first > WINDOW_GAP_S) flush()
            group += p
        }
        flush()
        return out
    }

    /** The night's candidate mean via the engine's own formula (per-record mean over the spans, rounded). */
    fun nightMean(aux: List<V18AuxRow>, spans: List<LongRange>): Int? =
        AnalyticsEngine.nightlySpo2CandidateMean(
            spans.map { DetectedSleep(it.first, it.last, 1.0, emptyList(), null, null) },
            aux,
        )?.first

    fun resolve(aux: List<V18AuxRow>, spans: List<LongRange>): Spo2Night =
        Spo2Night(windows(aux, spans), nightMean(aux, spans), aux.size)

    /**
     * Y domain for the chart: anchored at 100 with a floor a little below the lowest window, never above
     * 90. SpO₂ lives in a narrow band, so a 0..100 axis would flatten every real dip into the top edge.
     */
    fun yDomain(windows: List<Spo2Window>): ClosedFloatingPointRange<Double> {
        val lowest = windows.minOfOrNull { it.mean } ?: return 90.0..100.0
        return minOf(90.0, floor(lowest) - 1.0)..100.0
    }
}

/**
 * The Sleep tab's SpO₂ strap-estimate card for the browsed night. [night] null = still loading.
 */
@Composable
internal fun SleepSpo2Card(night: Spo2Night?) {
    val windows = night?.windows.orEmpty()
    SleepChartCard(
        title = uiString(R.string.sleep_spo2_title),
        subtitle = uiString(R.string.spo2_strap_estimate_caption),
        trailing = night?.nightMean?.let { uiString(R.string.sleep_spo2_night_mean, it) },
        tint = Palette.restColor,
        footer = {
            Column {
                if (windows.isNotEmpty()) {
                    val lowest = windows.minOf { it.mean }.roundToInt()
                    Text(
                        uiString(R.string.sleep_spo2_footer_windows, windows.size, lowest),
                        style = NoopType.footnote,
                        color = Palette.textSecondary,
                    )
                }
                Text(
                    uiString(R.string.sleep_spo2_footer_disclaimer),
                    style = NoopType.footnote,
                    color = Palette.textTertiary,
                )
            }
        },
    ) {
        when {
            night == null -> Unit
            windows.size >= 2 -> LineChart(
                values = windows.map { it.mean },
                modifier = Modifier.fillMaxWidth().height(Metrics.compactChartHeight)
                    .semantics { contentDescription = uiString(R.string.sleep_spo2_chart_description) },
                color = Palette.metricCyan,
                fill = false,
                selectionEnabled = true,
                formatValue = { uiString(R.string.sleep_spo2_point_value, it) },
                timestamps = windows.map { it.ts },
                yDomain = SleepSpo2Timeline.yDomain(windows),
                showsPoints = true,
            )
            else -> Text(
                uiString(
                    when {
                        night.auxRows == 0 -> R.string.sleep_spo2_empty_no_aux
                        windows.size == 1 -> R.string.sleep_spo2_empty_one_window
                        else -> R.string.sleep_spo2_empty_no_windows
                    },
                ),
                style = NoopType.subhead,
                color = Palette.textTertiary,
            )
        }
    }
}
