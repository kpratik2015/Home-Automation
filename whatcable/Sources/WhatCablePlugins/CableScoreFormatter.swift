import Foundation

enum CableScoreFormatter {
    static func renderText(_ report: CableScoreReport) -> String {
        if report.ports.isEmpty {
            return """
            No occupied USB-C ports detected.
            Plug in a cable and try again.

            \(report.disclaimer)

            """
        }

        var out = ""
        for port in report.ports {
            out += renderPort(port)
            out += "\n"
        }
        out += "────────────────────────────────────────\n"
        out += report.disclaimer + "\n"
        return out
    }

    static func renderJSON(_ report: CableScoreReport) throws -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(report)
        guard let text = String(data: data, encoding: .utf8) else {
            throw CocoaError(.fileReadCorruptFile)
        }
        return text
    }

    private static func renderPort(_ port: CableScorePortReport) -> String {
        let bar = String(repeating: "=", count: 40)
        var lines: [String] = []
        lines.append(bar)
        lines.append("\(port.portName) · SCORE \(port.score)/100 · \(port.fitLine)")
        lines.append(bar)
        lines.append("Verdict: \(port.verdict)")
        lines.append("")
        lines.append("WHAT IT IS (now)")
        for item in port.whatItIs {
            lines.append("  \(item)")
        }
        lines.append("")
        lines.append("CAPABILITIES CHECKLIST")
        for item in port.checklist {
            let mark: String
            switch item.mark {
            case .yes: mark = "✓"
            case .no: mark = "✗"
            case .unknown: mark = "?"
            }
            lines.append("  \(mark) \(item.label)")
            lines.append("      \(item.reason)")
        }
        lines.append("")
        lines.append("WHAT'S MISSING / NEXT TEST")
        for item in port.missingNext {
            lines.append("  • \(item)")
        }
        lines.append("")
        lines.append("BETTER CABLES (India · Amazon.in)")
        if port.recommendations.isEmpty {
            lines.append("  (no curated suggestions for this session)")
        } else {
            for rec in port.recommendations {
                lines.append("  • \(rec.title)")
                lines.append("    \(rec.why)")
                lines.append("    \(rec.amazonInUrl)")
            }
        }
        lines.append("")
        return lines.joined(separator: "\n")
    }
}
