# ESP32 home automation (XIAO ESP32-C6)

Firmware for [Seeed XIAO ESP32-C6](https://wiki.seeedstudio.com/xiao_esp32c6_getting_started/). Replaces always-on Mac scripts over time.

## Production (`home` env)

24/7 on one chip:

- **WiZ night guard** - arms after off, force-off during night window (1:00-10:00 by default)
- **Fan/lamp BLE** - serial commands `fan-on`, `fan-off`, `light-on`, `light-off`

Stop Mac `com.wiz.nightguard` when ESP owns the bulb. Mac fan bridge can stay for Alexa until Phase 3.

```bash
pio run -e home -t upload
pio device monitor
```

See [commands.md](commands.md) for test envs, Mac isolation, debugging.

## Phase 3 (later): Alexa queue poller on ESP

## Hardware

- USB-C **data** cable to Mac
- Device port: `/dev/cu.usbmodem101` (yours may differ)
- Power from USB charger for 24/7 use (not Mac tethered)

## Setup

### 1. Install PlatformIO

```bash
brew install platformio
```

ESP32-C6 needs the **pioarduino** platform (already set in `platformio.ini`). Stock `espressif32` only ships Arduino 2.x and cannot build for C6.

### 2. Configure WiFi and bulb

```bash
cd esp32-home
cp include/config.example.h include/config.h
# Edit WIFI_SSID, WIFI_PASSWORD, BULB_IP, night window
```

### 3. Flash

```bash
pio run -t upload
pio device monitor
```

If upload fails, hold **BOOT**, tap **RESET**, release **BOOT**, retry upload.

### 4. Daytime test

Set in `config.h`:

```c
#define FORCE_NIGHT_WINDOW 1
```

Rebuild and flash. Serial log should show guard polling. Set back to `0` for production.

## LED

Built-in LED on while night window is active.

## Files

| File | Role |
|------|------|
| [commands.md](commands.md) | Flash, monitor, test plans, Mac isolation, debugging |
| `src/main.cpp` | WiFi, NTP, scheduler, serial commands |
| `src/wiz_guard.cpp` | WiZ UDP + guard state (NVS) |
| `src/fan_ble.cpp` | Jingyuan BLE advert bursts |
| `include/config.h` | Secrets (gitignored) |
| `scripts/isolate-for-test.sh` | Stop Mac LaunchAgents before ESP32 tests |

## Next

- Fan/lamp BLE adverts from `jingyuan-fan-lamp/protocol.py`
- Poll `pratikkataria.com` queue instead of Mac `queue_poller.py`
