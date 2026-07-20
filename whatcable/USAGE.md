# CLI usage

Home-Automation fork of [WhatCable](https://github.com/darrylmorley/whatcable). Not official WhatCable or WhatCable Pro. See [FORK.md](FORK.md).

**Requires:** macOS 14+, Apple Silicon, Swift 5.9+ (Xcode 15+).

## Build

```bash
cd whatcable
swift build
```

Binary after build: `.build/debug/whatcable-cli`

Optional symlink:

```bash
ln -sf "$(pwd)/.build/debug/whatcable-cli" ~/.local/bin/whatcable-fork
```

Run commands below as `swift run whatcable-cli …` or `whatcable-fork …` if symlinked.

---

## Fork plugin: live power monitor

| Command | Description |
|---------|-------------|
| `--power-monitor` | Full-screen TUI; refreshes ~1/s. Ctrl+C to quit. |
| `--power-monitor-json` | Newline-delimited JSON on stdout. Ctrl+C to quit. |

```bash
swift run whatcable-cli --power-monitor
swift run whatcable-cli --power-monitor-json
```

**Watch charger input (watts):**

```bash
swift run whatcable-cli --power-monitor-json \
  | jq -r '"\(.timestamp) \(.systemSample.systemPowerIn / 1000) W in"'
```

**Watch one port** (change `2/2` to your `portKey` from output):

```bash
swift run whatcable-cli --power-monitor-json \
  | jq -r '.portSamples[] | select(.portKey=="2/2") | "\(.portKey) \(.watts/1000) W"'
```

**Reading the output:**

- **System input** - live power from the charger into the Mac (best number for charge rate).
- **Port `SMC`** - live measured draw on that port.
- **Port `contract`** - PD negotiated cap, not live draw (can show 100 W while laptop pulls less).
- **Port `metered`** - battery-controller reading; can lag under load.

On battery, the top line switches to **Battery discharge** using pack voltage/current/power.

---

## Fork plugin: cable scorecard

| Command | Description |
|---------|-------------|
| `--cable-score` | Per occupied port: score, checklist, gaps, Amazon.in suggestions |
| `--cable-score-json` | Same as JSON |

```bash
swift run whatcable-cli --cable-score
swift run whatcable-cli --cable-score-json | jq '.ports[] | {portName, score, fitLine}'
```

Each port card includes:

- **Score 0–100** and a plain **fit line** (e.g. OK for phone charge)
- **What it is now** - role, charger, e-marker, trust, partner
- **Capabilities checklist** - ✓ / ✗ / ? with reasons
- **What's missing / next test** - how to reveal more (high-watt / TB)
- **Better cables (Amazon.in)** - curated India search links by job

E-marker unread at ≤3A is normal - score stays mid and checklist marks identity as `?`, with a retest hint.

---

## Cable snapshot (upstream free CLI)

One-shot port/cable summary:

```bash
swift run whatcable-cli
swift run whatcable-cli --json
swift run whatcable-cli --json --raw    # include raw IOKit fields
```

Live updates when cables connect/disconnect:

```bash
swift run whatcable-cli --watch
swift run whatcable-cli --watch --json
```

**Cable report** (e-marker cables only; opens pre-filled GitHub issue URL):

```bash
swift run whatcable-cli --report
```

**Pipe JSON into jq:**

```bash
swift run whatcable-cli --json | jq '.ports[] | {name, headline, charging}'
```

---

## GUI app (upstream)

```bash
swift run whatcable-cli --popover    # menu bar mode
swift run whatcable-cli --desktop    # Dock window mode
swift run WhatCable                  # dev menu bar build (swift run, not CLI)
```

---

## Diagnostics / troubleshooting

| Flag | Description |
|------|-------------|
| `--no-usb-probe` | Skip USB control transfers if a hub/KVM misbehaves when WhatCable runs |
| `--tb-debug` | Dump IOThunderboltSwitch tree (contributor/debug) |
| `--version` | Print version |
| `-h`, `--help` | Show all options |

---

## Not in this fork

Official **WhatCable Pro** adds `--monitor`, `--dashboard`, negotiation/display diagnostics UI, cable history, and more. This fork adds `--power-monitor` / `--power-monitor-json` and `--cable-score` / `--cable-score-json`. See [whatcable.uk/pro](https://whatcable.uk/pro).

---

## Help

```bash
swift run whatcable-cli --help
```
