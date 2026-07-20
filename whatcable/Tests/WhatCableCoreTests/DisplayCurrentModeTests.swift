import Testing
@testable import WhatCableCore

@Suite("Display Current Mode")
struct DisplayCurrentModeTests {

    @Test("shortLabel names common Mac/monitor resolutions")
    func shortLabelNamesCommonResolutions() {
        #expect(DisplayCurrentMode(width: 5120, height: 2880, refreshHz: 60).shortLabel == "5K 60Hz")
        #expect(DisplayCurrentMode(width: 3840, height: 2160, refreshHz: 120).shortLabel == "4K 120Hz")
        #expect(DisplayCurrentMode(width: 2560, height: 1440, refreshHz: 144).shortLabel == "1440p 144Hz")
        #expect(DisplayCurrentMode(width: 1920, height: 1080, refreshHz: 60).shortLabel == "1080p 60Hz")
    }

    @Test("shortLabel rounds refresh and falls back to raw pixels")
    func shortLabelFallsBackToRawPixels() {
        // Unusual resolution: no friendly name, so show raw pixels.
        #expect(DisplayCurrentMode(width: 1234, height: 567, refreshHz: 59.94).shortLabel == "1234x567 60Hz")
    }
}
