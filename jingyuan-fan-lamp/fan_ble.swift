#!/usr/bin/swift
import CoreBluetooth
import Foundation

struct BleCommand {
    let name: String
    let packetA: [UInt16]
    let packetB: [UInt16]
}

private let commands: [String: BleCommand] = [
    "fan-on": BleCommand(
        name: "fan-on",
        packetA: [
            0x08F0, 0x8230, 0xFEFD, 0x5993, 0xFD35, 0x8C2A, 0xC6D9, 0x5208, 0xEC92,
            0x3571, 0x696E, 0x573F, 0x9881,
        ],
        packetB: [
            0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x6394, 0x6812, 0x0A44, 0xFCFB,
            0x58EE, 0xAEF4, 0x7994, 0x3A42,
        ]
    ),
    "fan-off": BleCommand(
        name: "fan-off",
        packetA: [
            0x08F0, 0x8230, 0xFFFD, 0x5993, 0xFD35, 0x8C2A, 0xC6D9, 0x5208, 0xEA92,
            0x0C71, 0x6935, 0x573F, 0x280D,
        ],
        packetB: [
            0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x6354, 0x0812, 0x0A24, 0xFC1B,
            0x7FC9, 0x89F4, 0x80E1, 0x97A1,
        ]
    ),
    "light-on": BleCommand(
        name: "light-on",
        packetA: [
            0x08F0, 0x8230, 0xFEFD, 0x5993, 0xFD35, 0x8C2A, 0xE7D9, 0x5208, 0xEAB2,
            0x2271, 0x69B1, 0x573F, 0x2F9C,
        ],
        packetB: [
            0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x63D0, 0x0812, 0x0A24, 0xFCFB,
            0x07B1, 0xF1F4, 0x4D6C, 0x36E8,
        ]
    ),
    "light-off": BleCommand(
        name: "light-off",
        packetA: [
            0x08F0, 0x8230, 0xFFFD, 0x5993, 0xFD35, 0x8C2A, 0xE6D9, 0x5208, 0xEAB2,
            0xBC71, 0x6979, 0x573F, 0xF68F,
        ],
        packetB: [
            0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x6350, 0x0812, 0x0A24, 0xFC1B,
            0xB80E, 0x4EF4, 0x22BB, 0x2A11,
        ]
    ),
]

private let endPacket: [UInt16] = [0xCDAB, 0x7856]

final class FanAdvertiser: NSObject, CBPeripheralManagerDelegate {
    private let manager = CBPeripheralManager(delegate: nil, queue: .main)
    private var command: BleCommand
    private var usePacketA = true
    private var burstTimer: Timer?
    private var ready = false

    init(command: BleCommand) {
        self.command = command
        super.init()
        manager.delegate = self
    }

    func run() {
        RunLoop.main.run()
    }

    func peripheralManagerDidUpdateState(_ peripheral: CBPeripheralManager) {
        switch peripheral.state {
        case .poweredOn:
            guard !ready else { return }
            ready = true
            fputs("Bluetooth ready. Broadcasting \(command.name) for 2.5s...\n", stderr)
            startBurst()
        case .poweredOff:
            fputs("Bluetooth is off. Turn it on and retry.\n", stderr)
            exit(1)
        case .unauthorized:
            fputs("Bluetooth permission denied. Allow Terminal in System Settings > Privacy > Bluetooth.\n", stderr)
            exit(1)
        case .unsupported:
            fputs("Bluetooth LE peripheral mode is not supported on this Mac.\n", stderr)
            exit(1)
        default:
            break
        }
    }

    private func startBurst() {
        advertise(words: command.packetA)
        usePacketA = false

        burstTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] timer in
            guard let self else {
                timer.invalidate()
                return
            }
            self.usePacketA.toggle()
            let words = self.usePacketA ? self.command.packetA : self.command.packetB
            self.advertise(words: words)
        }

        Timer.scheduledTimer(withTimeInterval: 2.5, repeats: false) { [weak self] _ in
            self?.finishBurst()
        }
    }

    private func finishBurst() {
        burstTimer?.invalidate()
        burstTimer = nil
        advertise(words: endPacket)
        fputs("Done. Check if the fan responded.\n", stderr)
        Timer.scheduledTimer(withTimeInterval: 0.25, repeats: false) { [weak self] _ in
            self?.manager.stopAdvertising()
            exit(0)
        }
    }

    private func advertise(words: [UInt16]) {
        let uuids = words.map { CBUUID(string: String(format: "%04X", $0)) }
        manager.stopAdvertising()
        manager.startAdvertising([CBAdvertisementDataServiceUUIDsKey: uuids])
    }
}

let usage = """
Usage: fan_ble.swift <fan-on|fan-off|light-on|light-off>

Replays BLE advertisement bursts captured from com.jingyuan.fan-lamp.
Stand near the fan. Quit the iPhone app first.
"""

let args = CommandLine.arguments.dropFirst()
guard let raw = args.first, let command = commands[raw] else {
    fputs(usage, stderr)
    exit(1)
}

let advertiser = FanAdvertiser(command: command)
advertiser.run()
