import Foundation
import WhatCableAppKit
import WhatCableCore
import WhatCableDarwinBackend

enum CableScoreCommand {
    @MainActor
    static func register(with registry: PluginRegistry) {
        registry.register(
            cliCommand: CLICommand(
                flagNames: ["--cable-score", "--cable-score-json"],
                helpLines: """
                  --cable-score         Per-port cable scorecard (Home-Automation fork; customer-facing)
                  --cable-score-json    Same report as JSON
                """,
                readsCableData: true,
                matches: { args in
                    args.contains("--cable-score") || args.contains("--cable-score-json")
                },
                run: { args in
                    let asJSON = args.contains("--cable-score-json")
                    await run(asJSON: asJSON)
                }
            )
        )
    }

    @MainActor
    private static func run(asJSON: Bool) async {
        let provider = makeDefaultSnapshotProvider()
        do {
            let snapshot = try await provider.snapshot()
            let report = CableScoreEngine.report(from: snapshot)
            if asJSON {
                print(try CableScoreFormatter.renderJSON(report))
            } else {
                print(CableScoreFormatter.renderText(report), terminator: "")
            }
        } catch {
            FileHandle.standardError.write(Data("whatcable: \(error)\n".utf8))
            exit(1)
        }
    }
}
