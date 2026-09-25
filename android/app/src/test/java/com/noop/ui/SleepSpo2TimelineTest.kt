package com.noop.ui

import com.noop.analytics.AnalyticsEngine
import com.noop.analytics.DetectedSleep
import com.noop.data.V18AuxRow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * #103 — the Sleep tab's per-window SpO₂ strap-estimate timeline. Pins the window grouping, what it refuses
 * to count (out-of-band flag codes, zeros, records outside the night's fragments), and that the card's
 * night mean is the engine's own `nightlySpo2CandidateMean` rather than a second formula.
 */
class SleepSpo2TimelineTest {

    private fun aux(ts: Long, v: Long?) = V18AuxRow(ts = ts, auxByte82 = v)

    /** A 30-record window starting at [start]: in-band [values] cycled, with optional flag codes spliced in. */
    private fun window(start: Long, values: List<Long>, flags: Map<Int, Long> = emptyMap()) =
        (0 until 30).map { i -> aux(start + i, flags[i] ?: values[i % values.size]) }

    @Test fun oneWindowPerMeasurementBurst() {
        val rows = window(1_000, listOf(96, 98)) + window(2_200, listOf(94)) + window(3_400, listOf(97))
        val w = SleepSpo2Timeline.windows(rows, listOf(0L..10_000L))
        assertEquals(3, w.size)
        assertEquals(listOf(97.0, 94.0, 97.0), w.map { it.mean })
        assertEquals(listOf(30, 30, 30), w.map { it.samples })
        assertEquals(1_000L + 14, w[0].ts)   // centred on the window's first..last in-band record
        assertEquals(96, w[0].min)
        assertEquals(98, w[0].max)
    }

    @Test fun flagCodesZerosAndMissingSlotsAreNotReadings() {
        // Flag-like codes (2, 32, 160) inside the window, zeros and absent slots around it.
        val rows = listOf(aux(900, 0), aux(950, null)) +
            window(1_000, listOf(95), flags = mapOf(0 to 2, 10 to 32, 29 to 160)) +
            listOf(aux(1_100, 0))
        val w = SleepSpo2Timeline.windows(rows, listOf(0L..10_000L)).single()
        assertEquals(27, w.samples)
        assertEquals(95.0, w.mean, 0.0)
        // The first and last records are flags, so the window is centred on the in-band ones (1001..1028).
        assertEquals(1_014L, w.ts)
    }

    @Test fun aShortInterruptionDoesNotSplitAWindowButTheInterWindowGapDoes() {
        val gap = SleepSpo2Timeline.WINDOW_GAP_S
        val rows = listOf(aux(0, 96), aux(gap, 96), aux(2 * gap + 1, 90))
        val w = SleepSpo2Timeline.windows(rows, listOf(0L..10_000L))
        assertEquals(listOf(2, 1), w.map { it.samples })
    }

    @Test fun onlyRecordsInsideTheNightsFragmentsCount() {
        // Two fragments with an awake gap; the window in the gap and the one after wake are dropped.
        val rows = window(1_000, listOf(96)) + window(2_200, listOf(80)) + window(3_400, listOf(98)) +
            window(9_000, listOf(88))
        val spans = listOf(900L..1_500L, 3_000L..4_000L)
        val w = SleepSpo2Timeline.windows(rows, spans)
        assertEquals(listOf(96.0, 98.0), w.map { it.mean })
    }

    @Test fun nightMeanIsTheEnginesFormula() {
        val rows = window(1_000, listOf(96, 97, 99)) + window(2_200, listOf(91, 94)) +
            window(3_400, listOf(98), flags = mapOf(3 to 8))
        val spans = listOf(900L..2_500L, 3_300L..4_000L)
        val engine = AnalyticsEngine.nightlySpo2CandidateMean(
            spans.map { DetectedSleep(it.first, it.last, 0.9, emptyList(), 50, 60.0) }, rows,
        )?.first
        assertEquals(engine, SleepSpo2Timeline.nightMean(rows, spans))
        // Per-RECORD mean (not a mean of window means): windows 97.33 / 92.5 / 98 over 30/30/29 records.
        assertEquals(96, SleepSpo2Timeline.nightMean(rows, spans))
    }

    @Test fun emptyInputsResolveHonestly() {
        assertTrue(SleepSpo2Timeline.windows(emptyList(), listOf(0L..10L)).isEmpty())
        assertTrue(SleepSpo2Timeline.windows(window(0, listOf(95)), emptyList()).isEmpty())
        assertNull(SleepSpo2Timeline.nightMean(listOf(aux(5, 0), aux(6, 150)), listOf(0L..10L)))
        val night = SleepSpo2Timeline.resolve(listOf(aux(5, 0)), listOf(0L..10L))
        assertEquals(Spo2Night(emptyList(), null, 1), night)
    }

    @Test fun yDomainKeepsTheNarrowBandVisible() {
        fun w(mean: Double) = Spo2Window(0, mean, 30, 0, 0)
        assertEquals(90.0..100.0, SleepSpo2Timeline.yDomain(listOf(w(96.0), w(98.0))))
        assertEquals(85.0..100.0, SleepSpo2Timeline.yDomain(listOf(w(86.4), w(97.0))))
        assertEquals(90.0..100.0, SleepSpo2Timeline.yDomain(emptyList()))
    }
}
