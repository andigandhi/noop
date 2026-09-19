import XCTest
@testable import NOOP

/**
 * Pins the pure display-only helpers behind the Coupled view (task #43) so they stay byte-identical to the
 * Android [CoupledScreen] twin:
 *  - the OPTIMAL recovery->strain band mapping (green >= 67 -> 14-18, yellow 34-66 -> 10-14, red < 34 -> 4-10),
 *  - the 0-100 scale conversion for each band.
 * These are display-only reads (never fed back into scoring), so the values here ARE the contract.
 */
class CoupledViewTests: XCTestCase {

    // MARK: - WHOOP scale (0-21)

    func testOptimalRange_whoopScale_greenDay_suggests14to18() {
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 90.0, effortScale: .whoop), "14 to 18")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 67.0, effortScale: .whoop), "14 to 18") // lower boundary of green is inclusive
    }

    func testOptimalRange_whoopScale_yellowDay_suggests10to14() {
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 66.9, effortScale: .whoop), "10 to 14")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 50.0, effortScale: .whoop), "10 to 14")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 34.0, effortScale: .whoop), "10 to 14") // lower boundary of yellow is inclusive
    }

    func testOptimalRange_whoopScale_redDay_suggests4to10() {
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 33.9, effortScale: .whoop), "4 to 10")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 10.0, effortScale: .whoop), "4 to 10")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 0.0, effortScale: .whoop), "4 to 10")
    }

    func testOptimalRange_whoopScale_noRecovery_isDash() {
        XCTAssertNil(CoupledView.optimalStrainRange(recovery: nil))
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: nil, effortScale: .whoop), "—")
    }

    // MARK: - 0-100 scale

    func testOptimalRange_hundredScale_greenDay_suggests67to86() {
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 90.0, effortScale: .hundred), "67 to 86")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 67.0, effortScale: .hundred), "67 to 86") // lower boundary of green is inclusive
    }

    func testOptimalRange_hundredScale_yellowDay_suggests48to67() {
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 66.9, effortScale: .hundred), "48 to 67")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 50.0, effortScale: .hundred), "48 to 67")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 34.0, effortScale: .hundred), "48 to 67") // lower boundary of yellow is inclusive
    }

    func testOptimalRange_hundredScale_redDay_suggests19to48() {
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 33.9, effortScale: .hundred), "19 to 48")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 10.0, effortScale: .hundred), "19 to 48")
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: 0.0, effortScale: .hundred), "19 to 48")
    }

    func testOptimalRange_hundredScale_noRecovery_isDash() {
        XCTAssertEqual(CoupledView.optimalStrainRangeText(recovery: nil, effortScale: .hundred), "—")
    }

    // MARK: - Band structure

    func testOptimalRange_bands_matchTheStruct() {
        XCTAssertEqual(CoupledView.optimalStrainRange(recovery: 80.0), 14...18)
        XCTAssertEqual(CoupledView.optimalStrainRange(recovery: 40.0), 10...14)
        XCTAssertEqual(CoupledView.optimalStrainRange(recovery: 5.0), 4...10)
    }
}
