import Foundation
import WhatCableAppKit
import WhatCableCore
import WhatCableDarwinBackend

enum PowerMonitorCommand {
    @MainActor
    static func register(with registry: PluginRegistry) {
        registry.register(
            cliCommand: CLICommand(
                flagNames: ["--power-monitor", "--power-monitor-json"],
                helpLines: """
                  --power-monitor       Live power telemetry (Home-Automation fork plugin; Ctrl+C to exit)
                  --power-monitor-json  Same, newline-delimited JSON on stdout
                """,
                readsCableData: true,
                matches: { args in
                    args.contains("--power-monitor") || args.contains("--power-monitor-json")
                },
                run: { args in
                    let asJSON = args.contains("--power-monitor-json")
                    await run(asJSON: asJSON)
                }
            )
        )
    }

    @MainActor
    private static func run(asJSON: Bool) async {
        let watcher = PowerTelemetryWatcher()
        watcher.start()
        defer { watcher.stop() }

        let monitorTask = Task {
            var lastText = ""
            for await snapshot in watcher.snapshots {
                if Task.isCancelled { return }

                if asJSON {
                    do {
                        let data = try jsonEncoder.encode(snapshot)
                        guard let line = String(data: data, encoding: .utf8) else { continue }
                        print(line)
                        fflush(stdout)
                    } catch {
                        FileHandle.standardError.write(
                            Data("whatcable: power monitor json encoding failed: \(error)\n".utf8)
                        )
                    }
                    continue
                }

                let text = renderText(snapshot)
                guard text != lastText else { continue }
                lastText = text
                print("\u{1B}[2J\u{1B}[H", terminator: "")
                print("whatcable --power-monitor · \(timestampFormatter.string(from: snapshot.timestamp))")
                print("")
                print(text, terminator: "")
                fflush(stdout)
            }
        }

        var caughtSignal: Int32 = 0
        signal(SIGINT, SIG_IGN)
        signal(SIGTERM, SIG_IGN)

        let intSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
        intSource.setEventHandler {
            caughtSignal = SIGINT
            monitorTask.cancel()
        }
        intSource.resume()

        let termSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        termSource.setEventHandler {
            caughtSignal = SIGTERM
            monitorTask.cancel()
        }
        termSource.resume()

        await monitorTask.value

        intSource.cancel()
        termSource.cancel()
        fflush(stdout)

        if caughtSignal != 0 {
            exit(128 + caughtSignal)
        }
    }

    private static let jsonEncoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    private static let timestampFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter
    }()

    private static func renderText(_ snapshot: PowerMonitorSnapshot) -> String {
        var lines: [String] = []

        let systemW = Double(snapshot.activePowerMW) / 1000.0
        let systemV = Double(snapshot.activeVoltageMV) / 1000.0
        let systemA = Double(snapshot.activeCurrentMA) / 1000.0
        let systemLabel = snapshot.onBattery ? "Battery discharge" : "System input"
        lines.append(String(format: "%@: %.1f W · %.2f V · %.2f A", systemLabel, systemW, systemV, systemA))

        if snapshot.portSamples.isEmpty {
            lines.append("Per-port: no live samples yet")
        } else {
            for sample in snapshot.portSamples.sorted(by: { $0.portKey < $1.portKey }) {
                let watts = Double(sample.watts) / 1000.0
                let volts = Double(sample.configuredVoltage) / 1000.0
                let amps = Double(sample.current) / 1000.0
                let source = sample.isSMCMeasured ? "SMC" : (sample.isContractedFallback ? "contract" : "metered")
                lines.append(
                    String(
                        format: "Port %@: %.1f W · %.2f V · %.2f A (%@)",
                        sample.portKey,
                        watts,
                        volts,
                        amps,
                        source
                    )
                )
            }
        }

        if let estimate = snapshot.resistanceEstimate, estimate.status != .insufficient {
            lines.append(
                String(
                    format: "Cable resistance: %.0f mΩ (%@, n=%d)",
                    estimate.milliohms,
                    estimate.status.rawValue,
                    estimate.sampleCount
                )
            )
        }

        if !snapshot.perPortMeteringSupported {
            lines.append("Note: this Mac may not expose live per-port SMC metering.")
        }

        return lines.joined(separator: "\n") + "\n"
    }
}
