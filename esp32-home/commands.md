# ESP32-C6 commands and debugging

Quick reference for building, flashing, testing, and debugging `esp32-home` firmware on the Seeed XIAO ESP32-C6.

## Before you start

| Term | Meaning |
|------|---------|
| **Flash** | Write firmware to the chip (like installing an app) |
| **Serial monitor** | Live text log from the device over USB (`115200` baud) |
| **Upload port** | USB serial device, usually `/dev/cu.usbmodem101` |
| **NVS** | Small flash storage for guard state (armed, pause, etc.) |

Always work from `esp32-home/`:

```bash
cd esp32-home
```

Config lives in `include/config.h` (gitignored). Copy from `include/config.example.h` on a new machine.

---

## Daily commands

### Build only

```bash
pio run
```

### Flash (build + upload)

```bash
pio run -t upload
```

### Serial monitor (logs + commands)

```bash
pio device monitor
```

Quit monitor: `Ctrl+C`

Close the serial monitor before `pio run -t upload`. Only one program can use the USB port at a time.

### Build, flash, and monitor (production)

```bash
pio run -e home -t upload && pio device monitor
```

Default env is `home` (WiZ + fan BLE). Other envs: `wifi_guard`, `fan_ble_only`.

### Find USB port

```bash
ls /dev/cu.usb*
```

If upload says "port not found", replug USB or check cable (must be data, not charge-only).

### Upload fails (bootloader)

1. Hold **BOOT**
2. Tap **RESET**
3. Release **BOOT**
4. Run `pio run -t upload` again within a few seconds

### Clean rebuild

```bash
pio run -t clean
pio run
```

---

## Serial commands (Phase 2: fan/lamp BLE)

With monitor open, type a command and press Enter:

| Command | Action |
|---------|--------|
| `help` | List commands |
| `status` | WiFi IP, time, night window, guard armed |
| `fan-on` | BLE advert burst (turn fan on) |
| `fan-off` | BLE advert burst (turn fan off) |
| `light-on` | BLE advert burst (turn light on) |
| `light-off` | BLE advert burst (turn light off) |

Stand near the chandelier. Quit the vendor phone app first. Each burst takes ~2.8 seconds.

---

## Stop Mac automations (avoid conflicts)

Only **one** device should control the same thing at a time.

| What you test on ESP32 | Stop on Mac | Why |
|------------------------|-------------|-----|
| WiZ night guard | `wiz-night-guard` LaunchAgent | Both would poll the same bulb IP |
| Fan/lamp BLE | `jingyuan-fan-lamp` bridge LaunchAgent | Both would send BLE bursts |
| Fan Alexa queue | `jingyuan-fan-lamp` bridge | Mac poller would dequeue Alexa commands |

### Check if Mac services are running

```bash
launchctl print gui/$(id -u)/com.wiz.nightguard | grep state
launchctl print gui/$(id -u)/com.jingyuan.fanlamp.bridge | grep state
```

`state = running` means active.

### Stop for ESP32 testing

```bash
# WiZ guard (if installed)
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.wiz.nightguard.plist 2>/dev/null || true

# Fan/lamp bridge + Alexa queue poller
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.jingyuan.fanlamp.bridge.plist 2>/dev/null || true
```

Or use the helper script:

```bash
./scripts/isolate-for-test.sh
```

### Start Mac services again after testing

```bash
./scripts/resume-mac.sh
```

Or reinstall from each project folder: `./install.sh`

---

## Test plans

### Crash loop at boot (WiFi PHY panic)

ESP32-C6 often cannot run **WiFi + BLE linked** reliably in one image. Symptoms: banner then `Guru Meditation` / `esp_phy_enable` before `WiFi OK`.

**Recover WiZ (stable):**

```bash
pio run -e wifi_guard -t erase -t upload && pio device monitor
```

**Test fan only (no WiFi, most reliable for BLE):**

```bash
pio run -e fan_ble_only -t upload && pio device monitor
# type fan-on
```

**Combined WiZ + fan (experimental):**

```bash
pio run -e seeed_xiao_esp32c6 -t erase -t upload && pio device monitor
```

Uses `bleInUse()` override so WiFi boots first; device reboots after each fan command to restore WiFi.

### WiZ-only fallback (no fan BLE)

If combined build still panics on boot:

```bash
pio run -e wifi_guard -t erase -t upload && pio device monitor
```

Uses `default.csv` partition and excludes `fan_ble.cpp`.

**Mac isolation:** stop `com.wiz.nightguard` (see above). Your Mac fan bridge can stay running; it does not touch the WiZ bulb.

1. In `config.h`, set `FORCE_NIGHT_WINDOW 1`
2. `pio run -t upload && pio device monitor`
3. Expect: `WiFi OK`, `Time synced`, `Night window opened`, polling logs
4. Turn the WiZ bulb on with the switch/app; within ~30s serial should show force-off
5. Set `FORCE_NIGHT_WINDOW 0`, reflash for production schedule

### Phase 2: Fan/lamp BLE

**Mac isolation:** stop `com.jingyuan.fanlamp.bridge` (running on your Mac right now). WiZ Mac guard is already stopped.

1. `./scripts/isolate-for-test.sh`
2. Optional: in `config.h`, set `WIZ_GUARD_ENABLED 0` so the loop does not sleep 30s between serial commands
3. `pio run -t upload && pio device monitor`
4. Type `fan-on` - fan should respond
5. Type `fan-off`, then `light-on`, `light-off`
6. `./scripts/resume-mac.sh` when done

### Alexa did not work

Smart Home - no invocation name. Use device names:

- *"Alexa, turn on center fan"*
- *"Alexa, turn off center light"*

**Setup checklist:**

1. `./scripts/deploy-fan-queue.sh` (deploys `smarthome.php`)
2. [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) → **Smart Home** skill → endpoint `https://pratikkataria.com/home-automation/fan-queue/smarthome.php`
3. Alexa app → **Devices** → discover devices → **Center Fan**, **Center Light**
4. Disable old custom skill **Hall Fan Light** if enabled
5. ESP32 running `home` env with `QUEUE_*` in `config.h` (serial should show `Queue:` dequeue lines)

See `jingyuan-fan-lamp/alexa-skill/README.md` for full steps.

### Queue: invalid HTTP response

Reflash latest `home` firmware (uses HTTPClient + HTTP/1.1 ALPN). Empty queue is silent - no error every 3s when working.

---

## `config.h` flags

| Flag | Default | Purpose |
|------|---------|---------|
| `FORCE_NIGHT_WINDOW` | `0` | `1` = ignore clock, always run guard (daytime test) |
| `WIZ_GUARD_ENABLED` | `1` | `0` = skip WiZ loop (BLE testing) |
| `FAN_BLE_SERIAL_ENABLED` | `1` | `0` = disable serial BLE commands |

Add new flags to your `config.h` when you pull firmware updates (see `config.example.h`).

---

## Reading serial output

### Healthy monitor

Boot once, then steady logs. Example:

```
esp32-home: WiZ guard + fan BLE (phase 2)
WiFi connecting to YourSSID.....
WiFi OK: 192.168.0.xxx
Time synced: ...
```

### Crash loop (not normal)

If you see repeating:

```
Guru Meditation Error: Core 0 panic'ed ...
Rebooting...
ESP-ROM:esp32c6-...
```

the firmware crashed and the chip auto-restarts. The monitor is just showing each reboot.

**Common causes**

1. **Partition table changed** (e.g. after adding BLE) - erase flash then reflash:
   ```bash
   pio run -t erase
   pio run -t upload && pio device monitor
   ```
2. **Do not call `esp_bt_controller_mem_release`** when BLE is linked - it breaks WiFi PHY on ESP32-C6. Firmware uses WiFi first, lazy BLE init on `fan-on`, WiFi paused during bursts.
3. **Brownout** - use a good USB cable/port or powered hub.

Decode a crash (optional):

```bash
pio run
ADDR2LINE=$(find ~/.platformio/packages -name 'riscv32-esp-elf-addr2line' | head -1)
$ADDR2LINE -pfiaC -e .pio/build/seeed_xiao_esp32c6/firmware.elf <MEPC from log>
```

Add monitor filter for readable backtraces:

```ini
monitor_filters = esp32_exception_decoder
```

(in `platformio.ini`)

---

```
esp32-home: WiZ night guard (phase 1)
WiFi OK: 192.168.0.xxx
Time synced: 2026-07-27 17:18:23
```

### First boot NVS message (harmless)

```
[E][Preferences.cpp:506] getString(): nvs_get_str len fail: window_key NOT_FOUND
```

Normal on first run. State keys are created after the first night window.

### WiFi failed

- Wrong SSID/password in `config.h`
- ESP32 needs **2.4 GHz** WiFi (not 5 GHz-only)
- Router MAC filtering blocking new device

### NTP sync failed

Guard will not enter the night window (needs correct time). Check internet/DNS on your LAN.

### `getPilot failed`

- Wrong `BULB_IP` in `config.h`
- Bulb powered off or on a different VLAN
- Test from Mac: `python3 -c "import socket; ..."` or run `wiz-night-guard` once manually

### BLE burst no response

Serial shows `Advertisement data too long` - reflash latest firmware (raw 16-bit UUID adverts).

If no error but fan still ignores:

1. Stand closer, quit phone app, retry `fan-on`
2. **Mac baseline** (proves fan + protocol work; no server involved):
   ```bash
   cd jingyuan-fan-lamp
   ./fan_ble.swift fan-on
   ```
   - Mac works, ESP32 does not → ESP32 BLE issue
   - Neither works → fan/app/range/hardware, not hosting

### Alexa vs ESP32 (different paths)

| Path | Uses pratikkataria.com? |
|------|-------------------------|
| ESP32 `fan-on` serial | **No** - direct BLE only |
| Alexa | **Yes** - Smart Home → queue → ESP32 → BLE |

Hosting health (Alexa path only):

```bash
curl -s https://pratikkataria.com/home-automation/fan-queue/health.php
# expect: {"ok":true}
```

If health is OK but Alexa fails: Smart Home skill endpoint saved, devices discovered, ESP queue poller running.

---

## Useful Mac-side checks

### WiZ bulb reachable

```bash
cd wiz-night-guard
python3 wiz_guard.py --once --dry-run
```

### Fan BLE from Mac (compare with ESP32)

```bash
cd jingyuan-fan-lamp
./fan_ble.swift fan-on
```

Stop Mac bridge before comparing ESP32 `fan-on` serial command.

### Alexa queue health (hosting)

```bash
curl -s https://pratikkataria.com/home-automation/fan-queue/health.php
```

---

## PlatformIO tips

- **Edit code** -> `pio run -t upload` (monitor can stay closed)
- **Change `config.h`** -> rebuild and reflash (not hot-reload)
- **Weird build errors** -> `pio run -t clean` then `pio run`
- **Board docs:** [Seeed XIAO ESP32C6](https://docs.platformio.org/en/latest/boards/espressif32/seeed_xiao_esp32c6.html)

This project uses **pioarduino** (not stock `espressif32`) because ESP32-C6 needs Arduino core 3.x.

---

## What runs where (migration map)

| Job | Mac today | ESP32 target |
|-----|-----------|--------------|
| WiZ night guard | `wiz-night-guard` | Phase 1 (done) |
| Fan/lamp BLE | `fan_ble.swift` via bridge | Phase 2 (serial test now) |
| Alexa queue poll | `queue_poller.py` | Phase 3 (planned) |

When ESP32 owns a job, keep the matching Mac LaunchAgent stopped to avoid double control.
