import Foundation
import WhatCableCore

enum CableScoreJob: String, Codable, Sendable {
    case phoneCharge = "phone_charge"
    case mac100w = "mac_100w"
    case mac240w = "mac_240w"
    case thunderbolt = "thunderbolt"
}

enum ChecklistMark: String, Codable, Sendable {
    case yes = "yes"
    case no = "no"
    case unknown = "unknown"
}

struct ChecklistItem: Codable, Sendable {
    let id: String
    let label: String
    let mark: ChecklistMark
    let reason: String
}

struct IndiaRecommendation: Codable, Sendable {
    let id: String
    let title: String
    let why: String
    let amazonInUrl: String
    let amazonInSearch: String
    let jobs: [String]
}

struct CableScorePortReport: Codable, Sendable {
    let portName: String
    let portKey: String?
    let score: Int
    let fitLine: String
    let verdict: String
    let headline: String
    let subtitle: String
    let whatItIs: [String]
    let checklist: [ChecklistItem]
    let missingNext: [String]
    let recommendations: [IndiaRecommendation]
    let trustTier: String?
    let usbifCertID: String?
    let cableSpeed: String?
    let cableWatts: Int?
    let cableVendor: String?
    let chargingSummary: String?
    let dataLinkSummary: String?
    let curatedBrands: [String]
}

struct CableScoreReport: Codable, Sendable {
    let version: String
    let disclaimer: String
    let ports: [CableScorePortReport]
}

enum CableScoreCatalog {
    struct Entry: Codable {
        let id: String
        let jobs: [String]
        let title: String
        let why: String
        let amazonInSearch: String
        let amazonInUrl: String
    }

    static func load() -> [Entry] {
        guard let url = Bundle.module.url(forResource: "india-cable-catalog", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let entries = try? JSONDecoder().decode([Entry].self, from: data)
        else {
            return []
        }
        return entries
    }
}

enum CableScoreEngine {
    static func report(from snapshot: CableSnapshot) -> CableScoreReport {
        let activePortCount = snapshot.ports.filter { $0.connectionActive == true }.count
        let chargerSourceCount = ChargerWattageSource.chargerSourceCount(
            ports: snapshot.ports,
            sources: snapshot.powerSources
        )
        let chargingPortKeys = Set(snapshot.ports.compactMap { port -> String? in
            let portSources = snapshot.powerSources.filter { $0.canonicallyMatches(port: port) }
            return PowerSource.hasLiveChargingContract(in: portSources) ? port.portKey : nil
        })
        let chargerAttached = snapshot.adapter != nil
            || snapshot.powerSources.contains { $0.winning != nil }

        let catalog = CableScoreCatalog.load()

        var portReports: [CableScorePortReport] = []
        for port in snapshot.ports {
            let identities = snapshot.identities.filter { $0.canonicallyMatches(port: port) }
            let sources = snapshot.powerSources.filter { $0.canonicallyMatches(port: port) }
            let devices = port.matchingDevices(from: snapshot.usbDevices)
            let live = isPortLive(
                port: port,
                powerSources: sources,
                identities: identities,
                matchingDevices: devices,
                chargerAttached: chargerAttached
            )
            guard live else { continue }

            let wattageSource = ChargerWattageSource.resolve(
                portSources: sources,
                activePortCount: activePortCount,
                chargerSourceCount: chargerSourceCount,
                adapter: snapshot.adapter
            )
            let anotherCharging = port.portKey.map { key in
                chargingPortKeys.contains { $0 != key }
            } ?? false

            let cio = snapshot.cioCapabilities.first { $0.canonicallyMatches(port: port) }
            let usb3 = snapshot.usb3Transports.filter { $0.canonicallyMatches(port: port) }
            let displays = snapshot.displayPorts.filter { $0.canonicallyMatches(port: port) }

            portReports.append(
                scorePort(
                    port: port,
                    sources: sources,
                    identities: identities,
                    devices: devices,
                    snapshot: snapshot,
                    cio: cio,
                    usb3: usb3,
                    displays: displays,
                    wattageSource: wattageSource,
                    anotherPortActivelyCharging: anotherCharging,
                    catalog: catalog
                )
            )
        }

        return CableScoreReport(
            version: AppInfo.version,
            disclaimer: "Not a safety certification. USB-IF XID is not Apple MFi. Amazon.in links are curated suggestions - verify the listing wattage and Thunderbolt claims yourself.",
            ports: portReports
        )
    }

    private static func scorePort(
        port: AppleHPMInterface,
        sources: [PowerSource],
        identities: [USBPDSOP],
        devices: [USBDevice],
        snapshot: CableSnapshot,
        cio: CIOCableCapability?,
        usb3: [USB3Transport],
        displays: [IOPortTransportStateDisplayPort],
        wattageSource: ChargerWattageSource,
        anotherPortActivelyCharging: Bool,
        catalog: [CableScoreCatalog.Entry]
    ) -> CableScorePortReport {
        let summary = PortSummary(
            port: port,
            sources: sources,
            identities: identities,
            devices: devices,
            thunderboltSwitches: snapshot.thunderboltSwitches,
            federatedIdentities: snapshot.federatedIdentities,
            usb3Transports: usb3,
            cioCapability: cio,
            chargerWattageSource: wattageSource,
            batteryFullyCharged: snapshot.batteryFullyCharged,
            batteryIsCharging: snapshot.batteryIsCharging,
            adapter: snapshot.adapter
        )

        let cableEmarker = identities.first {
            $0.endpoint == .sopPrime || $0.endpoint == .sopDoublePrime
        }
        let partner = identities.first { $0.endpoint == .sop }
        let hasEmarkerData = cableEmarker.map { !$0.vdos.isEmpty } ?? false

        let charging = ChargingDiagnostic(
            port: port,
            sources: sources,
            identities: identities,
            adapter: snapshot.adapter,
            wattageSource: wattageSource,
            batteryFullyCharged: snapshot.batteryFullyCharged,
            batteryIsCharging: snapshot.batteryIsCharging,
            anotherPortActivelyCharging: anotherPortActivelyCharging
        )

        let dataLink = DataLinkDiagnostic(
            port: port,
            identities: identities,
            devices: devices,
            usb3Transports: usb3,
            cio: cio,
            thunderboltSwitches: snapshot.thunderboltSwitches
        )

        let negotiatedWatts: Int? = sources
            .compactMap { $0.winning.map { Int((Double($0.maxPowerMW) / 1000).rounded()) } }
            .max()

        let trust: CableTrust? = cableEmarker.map { id in
            CableTrust(
                report: CableTrustReport(identity: id, partner: partner),
                vendorRegistered: VendorDB.isRegistered(id.vendorID),
                dataLink: dataLink,
                negotiatedWatts: negotiatedWatts,
                ratedWatts: id.cableVDO?.maxWatts
            )
        }

        let xid = cableEmarker?.certStatVDO.flatMap { cs -> UInt32? in
            cs.isPresent ? cs.xid : nil
        }
        let cableVDO = cableEmarker?.cableVDO
        let curated = cableEmarker.map {
            CableDB.curatedCables(vid: $0.vendorID, pid: $0.productID).map(\.brand)
        } ?? []

        let checklist = buildChecklist(
            hasEmarkerData: hasEmarkerData,
            cableVDO: cableVDO,
            xid: xid,
            trust: trust,
            charging: charging,
            dataLink: dataLink,
            port: port,
            negotiatedWatts: negotiatedWatts,
            displays: displays
        )

        let score = computeScore(
            hasEmarkerData: hasEmarkerData,
            trust: trust,
            charging: charging,
            dataLink: dataLink,
            cableVDO: cableVDO,
            xid: xid,
            negotiatedWatts: negotiatedWatts
        )

        let jobs = inferJobs(
            hasEmarkerData: hasEmarkerData,
            cableVDO: cableVDO,
            charging: charging,
            dataLink: dataLink,
            negotiatedWatts: negotiatedWatts
        )

        let fitLine = fitLineFor(
            score: score,
            hasEmarkerData: hasEmarkerData,
            cableVDO: cableVDO,
            charging: charging,
            dataLink: dataLink,
            negotiatedWatts: negotiatedWatts
        )

        let verdict = verdictText(
            hasEmarkerData: hasEmarkerData,
            cableVDO: cableVDO,
            charging: charging,
            dataLink: dataLink,
            trust: trust,
            negotiatedWatts: negotiatedWatts
        )

        let whatItIs = buildWhatItIs(
            summary: summary,
            charging: charging,
            hasEmarkerData: hasEmarkerData,
            cableEmarker: cableEmarker,
            cableVDO: cableVDO,
            partner: partner,
            trust: trust,
            xid: xid,
            curated: curated,
            negotiatedWatts: negotiatedWatts,
            cio: cio,
            devices: devices
        )

        let missing = buildMissingNext(
            hasEmarkerData: hasEmarkerData,
            cableVDO: cableVDO,
            dataLink: dataLink,
            charging: charging,
            xid: xid
        )

        let recs = pickRecommendations(jobs: jobs, catalog: catalog, curatedBrands: curated)

        return CableScorePortReport(
            portName: port.portDescription ?? port.serviceName,
            portKey: port.portKey,
            score: score,
            fitLine: fitLine,
            verdict: verdict,
            headline: summary.headline,
            subtitle: summary.subtitle,
            whatItIs: whatItIs,
            checklist: checklist,
            missingNext: missing,
            recommendations: recs,
            trustTier: trust.map { $0.tier.rawValue },
            usbifCertID: xid.map { String(format: "0x%08X", $0) },
            cableSpeed: cableVDO?.speed.label,
            cableWatts: cableVDO?.maxWatts,
            cableVendor: cableEmarker.flatMap { VendorDB.name(for: $0.vendorID) },
            chargingSummary: charging?.summary,
            dataLinkSummary: dataLink?.summary,
            curatedBrands: Array(Set(curated)).sorted()
        )
    }

    private static func computeScore(
        hasEmarkerData: Bool,
        trust: CableTrust?,
        charging: ChargingDiagnostic?,
        dataLink: DataLinkDiagnostic?,
        cableVDO: PDVDO.CableVDO?,
        xid: UInt32?,
        negotiatedWatts: Int?
    ) -> Int {
        var score = 50

        if hasEmarkerData {
            score += 15
        } else {
            score -= 10
            if let w = negotiatedWatts, w <= 30 {
                // Cap: unread e-marker on phone-class charge is incomplete, not fail
                score = min(score, 62)
            }
        }

        if let trust {
            switch trust.tier {
            case .green: score += 20
            case .amber: score += 0
            case .red: score -= 35
            }
            if trust.contradiction { score -= 20 }
        }

        if let charging {
            switch charging.bottleneck {
            case .fine: score += 10
            case .cableLimit: score -= 25
            case .chargerLimit: score += 2
            case .macLimit: score += 5
            case .standbyCharger: score += 0
            case .noCharger: break
            }
        }

        if let dataLink {
            switch dataLink.bottleneck {
            case .fine: score += 12
            case .cableLimit, .cableContradictsActive: score -= 25
            case .degraded: score -= 15
            case .unknownCable: score -= 5
            case .hostLimit, .deviceLimit: score += 5
            case .blockedBySecurity: score -= 5
            }
            if dataLink.cableSignalConflict { score -= 15 }
        }

        if cableVDO != nil { score += 5 }
        if xid != nil { score += 5 }
        if let watts = cableVDO?.maxWatts, watts >= 100 { score += 3 }

        return max(0, min(100, score))
    }

    private static func buildChecklist(
        hasEmarkerData: Bool,
        cableVDO: PDVDO.CableVDO?,
        xid: UInt32?,
        trust: CableTrust?,
        charging: ChargingDiagnostic?,
        dataLink: DataLinkDiagnostic?,
        port: AppleHPMInterface,
        negotiatedWatts: Int?,
        displays: [IOPortTransportStateDisplayPort]
    ) -> [ChecklistItem] {
        var items: [ChecklistItem] = []

        let pdActive = port.transportsActive.contains("CC") || charging != nil
        items.append(ChecklistItem(
            id: "pd_path",
            label: "USB-PD charge path",
            mark: pdActive ? .yes : .no,
            reason: pdActive ? "CC / power negotiation active on this port." : "No PD charge path visible."
        ))

        let phoneClass = (negotiatedWatts ?? 0) >= 15 || (charging?.chargerW ?? 0) >= 15
        items.append(ChecklistItem(
            id: "phone_class_charge",
            label: "Phone-class charge (≥15W)",
            mark: phoneClass ? .yes : (charging == nil ? .unknown : .no),
            reason: phoneClass
                ? "Negotiated or charger ceiling is at least 15W."
                : "No ≥15W charge seen on this port."
        ))

        if hasEmarkerData {
            items.append(ChecklistItem(
                id: "emarker",
                label: "E-marker identity",
                mark: .yes,
                reason: "Cable chip responded with capability data."
            ))
        } else {
            items.append(ChecklistItem(
                id: "emarker",
                label: "E-marker identity",
                mark: .unknown,
                reason: "Not read on this link (common at ≤3A). Use a higher-watt port or Thunderbolt device to reveal."
            ))
        }

        if let watts = cableVDO?.maxWatts {
            items.append(ChecklistItem(
                id: "high_watt",
                label: "5A / 100W+ ready",
                mark: watts >= 100 ? .yes : .no,
                reason: watts >= 100
                    ? "E-marker rates about \(watts)W."
                    : "E-marker rates about \(watts)W - below 100W class."
            ))
        } else {
            items.append(ChecklistItem(
                id: "high_watt",
                label: "5A / 100W+ ready",
                mark: .unknown,
                reason: "Unknown without e-marker power rating."
            ))
        }

        let hasData = port.transportsActive.contains(where: { ["USB2", "USB3", "CIO", "DisplayPort"].contains($0) })
            || dataLink != nil
        if let dataLink {
            let ok: ChecklistMark
            switch dataLink.bottleneck {
            case .fine, .hostLimit, .deviceLimit: ok = .yes
            case .cableLimit, .cableContradictsActive, .degraded: ok = .no
            default: ok = .unknown
            }
            items.append(ChecklistItem(
                id: "data_link",
                label: "Data link confirmed",
                mark: ok,
                reason: dataLink.summary
            ))
        } else {
            items.append(ChecklistItem(
                id: "data_link",
                label: "Data link confirmed",
                mark: hasData ? .yes : .no,
                reason: hasData
                    ? "A data transport is active."
                    : "Charge/PD only - no USB3/Thunderbolt/DisplayPort data on this link."
            ))
        }

        let tbOrUsb4 = port.transportsActive.contains("CIO")
            || (cableVDO?.speed.label.contains("USB4") == true)
            || (cableVDO?.speed.label.contains("Thunderbolt") == true)
        if port.transportsActive.contains("CIO") {
            items.append(ChecklistItem(
                id: "thunderbolt",
                label: "USB4 / Thunderbolt path",
                mark: .yes,
                reason: "Thunderbolt (CIO) transport is active."
            ))
        } else if hasEmarkerData && tbOrUsb4 {
            items.append(ChecklistItem(
                id: "thunderbolt",
                label: "USB4 / Thunderbolt path",
                mark: .unknown,
                reason: "E-marker claims USB4/TB class, but no Thunderbolt link is active this session."
            ))
        } else {
            items.append(ChecklistItem(
                id: "thunderbolt",
                label: "USB4 / Thunderbolt path",
                mark: hasEmarkerData ? .no : .unknown,
                reason: hasEmarkerData
                    ? "No USB4/Thunderbolt claim or active CIO link."
                    : "Unknown until e-marker or a TB device is connected."
            ))
        }

        if let xid {
            items.append(ChecklistItem(
                id: "usbif_xid",
                label: "USB-IF cert (XID)",
                mark: .yes,
                reason: String(format: "XID 0x%08X reported (not Apple MFi).", xid)
            ))
        } else if hasEmarkerData {
            items.append(ChecklistItem(
                id: "usbif_xid",
                label: "USB-IF cert (XID)",
                mark: .no,
                reason: "E-marker present but no USB-IF cert ID (common; not proof of a bad cable)."
            ))
        } else {
            items.append(ChecklistItem(
                id: "usbif_xid",
                label: "USB-IF cert (XID)",
                mark: .unknown,
                reason: "Unknown without e-marker Cert Stat VDO."
            ))
        }

        if let trust {
            items.append(ChecklistItem(
                id: "trust",
                label: "Trust tier",
                mark: trust.tier == .green ? .yes : (trust.tier == .red ? .no : .unknown),
                reason: "WhatCable trust: \(trust.tier.rawValue)"
                    + (trust.contradiction ? " (claim vs link disagreement)." : ".")
            ))
        } else {
            items.append(ChecklistItem(
                id: "trust",
                label: "Trust tier",
                mark: .unknown,
                reason: "No e-marker to assess."
            ))
        }

        if !displays.isEmpty {
            items.append(ChecklistItem(
                id: "display",
                label: "Display over USB-C",
                mark: .yes,
                reason: "DisplayPort path present on this port."
            ))
        }

        return items
    }

    private static func inferJobs(
        hasEmarkerData: Bool,
        cableVDO: PDVDO.CableVDO?,
        charging: ChargingDiagnostic?,
        dataLink: DataLinkDiagnostic?,
        negotiatedWatts: Int?
    ) -> [CableScoreJob] {
        var jobs: [CableScoreJob] = []

        if !hasEmarkerData || (negotiatedWatts ?? 0) <= 45 || (charging?.chargerW ?? 0) <= 45 {
            jobs.append(.phoneCharge)
        }

        if let watts = cableVDO?.maxWatts {
            if watts < 100 { jobs.append(.mac100w) }
            if watts < 140 { jobs.append(.mac240w) }
        } else if case .cableLimit = charging?.bottleneck {
            jobs.append(.mac100w)
        } else if (negotiatedWatts ?? 0) >= 60 && (cableVDO?.maxWatts ?? 0) < 100 {
            jobs.append(.mac100w)
        }

        if case .cableLimit = dataLink?.bottleneck { jobs.append(.thunderbolt) }
        if case .unknownCable = dataLink?.bottleneck { jobs.append(.thunderbolt) }
        if hasEmarkerData,
           let label = cableVDO?.speed.label,
           (label.contains("USB4") || label.contains("Thunderbolt") || label.contains("40")),
           dataLink == nil
        {
            jobs.append(.thunderbolt)
        }

        if jobs.isEmpty {
            jobs.append(.phoneCharge)
            jobs.append(.mac100w)
        }

        return Array(Set(jobs)).sorted { $0.rawValue < $1.rawValue }
    }

    private static func fitLineFor(
        score: Int,
        hasEmarkerData: Bool,
        cableVDO: PDVDO.CableVDO?,
        charging: ChargingDiagnostic?,
        dataLink: DataLinkDiagnostic?,
        negotiatedWatts: Int?
    ) -> String {
        if case .cableLimit = charging?.bottleneck {
            return "Caution - cable limits charging"
        }
        if case .cableLimit = dataLink?.bottleneck {
            return "Caution - cable limits data speed"
        }
        if case .cableContradictsActive = dataLink?.bottleneck {
            return "Caution - e-marker vs link disagree"
        }
        if !hasEmarkerData {
            if let w = negotiatedWatts, w <= 30 {
                return "OK for phone charge · identity incomplete"
            }
            return "Identity incomplete · retest with high-watt or TB"
        }
        if let watts = cableVDO?.maxWatts, watts >= 100,
           let speed = cableVDO?.speed.label,
           speed.contains("40") || speed.contains("USB4") || speed.contains("Thunderbolt")
        {
            if dataLink != nil { return "OK for Thunderbolt / high-watt charge" }
            return "Claims TB4-class · data not verified this session"
        }
        if let watts = cableVDO?.maxWatts, watts >= 100 {
            return "OK for Mac 100W charging"
        }
        if score >= 70 {
            return "OK for everyday charge / data"
        }
        return "Usable · check gaps below"
    }

    private static func verdictText(
        hasEmarkerData: Bool,
        cableVDO: PDVDO.CableVDO?,
        charging: ChargingDiagnostic?,
        dataLink: DataLinkDiagnostic?,
        trust: CableTrust?,
        negotiatedWatts: Int?
    ) -> String {
        var parts: [String] = []

        if let charging {
            parts.append(charging.summary)
        }

        if !hasEmarkerData {
            parts.append("Cable chip not read - specs unknown until you force an e-marker read (high-watt charger or Thunderbolt device).")
        } else if let cableVDO {
            parts.append(
                "E-marker: \(cableVDO.speed.label), \(cableVDO.current.label), up to ~\(cableVDO.maxWatts)W."
            )
        }

        if let dataLink {
            parts.append(dataLink.summary)
        } else if negotiatedWatts != nil {
            parts.append("No high-speed data link on this session (charge/PD only).")
        }

        if let trust {
            parts.append("Trust tier: \(trust.tier.rawValue).")
        }

        return parts.joined(separator: " ")
    }

    private static func buildWhatItIs(
        summary: PortSummary,
        charging: ChargingDiagnostic?,
        hasEmarkerData: Bool,
        cableEmarker: USBPDSOP?,
        cableVDO: PDVDO.CableVDO?,
        partner: USBPDSOP?,
        trust: CableTrust?,
        xid: UInt32?,
        curated: [String],
        negotiatedWatts: Int?,
        cio: CIOCableCapability?,
        devices: [USBDevice]
    ) -> [String] {
        var lines: [String] = []
        lines.append("Role: \(summary.headline)")
        if !summary.subtitle.isEmpty {
            lines.append(summary.subtitle)
        }

        if let charging {
            let charger = charging.chargerW.map { "\($0)W charger" } ?? "charger"
            let negotiated = negotiatedWatts.map { "negotiated \($0)W" } ?? "no live contract"
            lines.append("Charging: \(charger) · \(negotiated) · \(charging.summary)")
        }

        if hasEmarkerData, let cableVDO, let cableEmarker {
            let vendor = VendorDB.name(for: cableEmarker.vendorID)
                ?? String(format: "VID 0x%04X", cableEmarker.vendorID)
            lines.append(
                "Cable chip: \(cableVDO.speed.label) · \(cableVDO.current.label) · ~\(cableVDO.maxWatts)W · \(cableVDO.cableType == .active ? "active" : "passive") · \(vendor)"
            )
            lines.append(
                String(format: "USB-IF XID: %@", xid.map { String(format: "0x%08X", $0) } ?? "none")
            )
            if let trust {
                lines.append("Trust: \(trust.tier.rawValue)"
                    + (trust.confirmedBy.isEmpty
                        ? " (not yet confirmed under load)"
                        : " (confirmed: \(trust.confirmedBy.map(\.rawValue).sorted().joined(separator: ", ")))"))
            }
            if !curated.isEmpty {
                lines.append("Known fingerprints: \(Array(Set(curated)).sorted().joined(separator: ", "))")
            }
        } else {
            lines.append("Cable chip: not read (common at ≤3A) - speed/power rating unknown")
        }

        if let partner {
            let vendor = VendorDB.name(for: partner.vendorID) ?? "No vendor reported"
            let kind = partner.idHeader.map {
                $0.ufpProductType != .undefined ? $0.ufpProductType.label : $0.dfpProductType.label
            } ?? "Partner"
            lines.append("Partner: \(kind) · \(vendor)")
        }

        if let cio, let speed = cio.negotiatedLinkSpeed {
            lines.append("Thunderbolt measured floor: \(CIOCableCapability.speedLabel(for: speed) ?? "code \(speed)")")
        }

        if !devices.isEmpty {
            let names = devices.prefix(3).map { $0.productName ?? "Unknown" }.joined(separator: ", ")
            lines.append("USB devices: \(names)")
        }

        return lines
    }

    private static func buildMissingNext(
        hasEmarkerData: Bool,
        cableVDO: PDVDO.CableVDO?,
        dataLink: DataLinkDiagnostic?,
        charging: ChargingDiagnostic?,
        xid: UInt32?
    ) -> [String] {
        var next: [String] = []

        if !hasEmarkerData {
            next.append("To identify the cable: plug into a higher-watt charger port, or a Thunderbolt dock/SSD, then re-run --cable-score.")
        }

        if hasEmarkerData,
           let label = cableVDO?.speed.label,
           (label.contains("USB4") || label.contains("Thunderbolt") || label.contains("40")),
           dataLink == nil
        {
            next.append("E-marker claims high-speed data, but no TB/USB4 link ran this session. Connect a dock or fast SSD to verify.")
        }

        if case .cableLimit = charging?.bottleneck {
            next.append("Cable is limiting charge vs the charger. Prefer a 5A / 100W+ e-marked cable for this brick.")
        }

        if case .cableLimit = dataLink?.bottleneck {
            next.append("Cable is the data bottleneck. Prefer a Thunderbolt 4 / USB4 40Gbps cable for docks and fast storage.")
        }

        if hasEmarkerData && xid == nil {
            next.append("No USB-IF XID - optional pedigree signal; many good cables omit it.")
        }

        if next.isEmpty {
            next.append("Optional: stress-test with your real workload (SSD copy, display, 15 min charge) and feel the plugs for excess heat.")
        }

        return next
    }

    private static func pickRecommendations(
        jobs: [CableScoreJob],
        catalog: [CableScoreCatalog.Entry],
        curatedBrands: [String]
    ) -> [IndiaRecommendation] {
        let jobSet = Set(jobs.map(\.rawValue))
        var picked: [CableScoreCatalog.Entry] = []

        for brand in curatedBrands {
            let lower = brand.lowercased()
            for entry in catalog where entry.jobs.contains(where: { jobSet.contains($0) }) {
                if entry.title.lowercased().contains(lower) || entry.why.lowercased().contains(lower) {
                    if !picked.contains(where: { $0.id == entry.id }) {
                        picked.append(entry)
                    }
                }
            }
        }

        for job in jobs {
            for entry in catalog where entry.jobs.contains(job.rawValue) {
                if !picked.contains(where: { $0.id == entry.id }) {
                    picked.append(entry)
                }
                if picked.count >= 3 { break }
            }
            if picked.count >= 3 { break }
        }

        return Array(picked.prefix(3)).map {
            IndiaRecommendation(
                id: $0.id,
                title: $0.title,
                why: $0.why,
                amazonInUrl: $0.amazonInUrl,
                amazonInSearch: $0.amazonInSearch,
                jobs: $0.jobs
            )
        }
    }
}
