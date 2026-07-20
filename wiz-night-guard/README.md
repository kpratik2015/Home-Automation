# WiZ Night Guard

Forces a WiZ bulb off during overnight power blips after you have turned it off for the night.

Copyright (c) 2026 Pratik Kataria. All rights reserved. See [LICENSE](LICENSE).

## How it works

1. Runs daily from `NIGHT_START` to `NIGHT_END` (default 1:00 AM - 10:00 AM)
2. **Monitoring:** at window start, always disarms and watches without forcing off
3. **Armed:** after the bulb is off for the first time in the window (turn-off, or already off at window start)
4. **Pause:** use CLI before intentional night use; when pause ends with light still on, guard forces off again

## Setup

```bash
cd wiz-night-guard
cp config.example.py config.local.py
# Edit config.local.py: BULB_IP, NIGHT_START, NIGHT_END
chmod +x bin/wiz-guard install.sh uninstall.sh
./install.sh
```

`install.sh` creates `~/.local/share/wiz-night-guard/`, generates the LaunchAgent from your config, and optionally symlinks `wiz-guard` into `~/bin`.

## Prerequisites

1. WiZ app: **Allow local communication** ON
2. Router DHCP reservation for the bulb IP
3. Mac plugged in overnight (lid closed OK; LaunchAgent uses `caffeinate -is`)

## CLI

```bash
./bin/wiz-guard status
./bin/wiz-guard run --force-window --dry-run   # safe daytime test
./bin/wiz-guard run --force-window             # live test
./bin/wiz-guard pause
./bin/wiz-guard pause 120
./bin/wiz-guard resume
```

Without pause, intentional turn-on while armed is forced off within one poll.

## Change schedule

1. Edit `NIGHT_START` / `NIGHT_END` in `config.local.py`
2. Re-run `./install.sh` (regenerates LaunchAgent start time)

## Uninstall

```bash
./uninstall.sh
./uninstall.sh --purge   # also remove state and logs
```

## Logs

`~/.local/share/wiz-night-guard/guard.log`
