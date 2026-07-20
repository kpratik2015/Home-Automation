# Home-Automation

Personal home automations. Each automation lives in its own folder.

[![License: Proprietary](https://img.shields.io/badge/license-proprietary-red)](LICENSE)

## Licensing

This repository is **proprietary**. Viewing on GitHub does not grant permission to use, copy, modify, or redistribute any part of it. See [LICENSE](LICENSE).

Open-source terms apply only inside [whatcable/](whatcable/): upstream WhatCable under [whatcable/LICENSE](whatcable/LICENSE) (MIT) and the fork plugin under [whatcable/Sources/WhatCablePlugins/LICENSE](whatcable/Sources/WhatCablePlugins/LICENSE) (MIT). Details: [whatcable/FORK.md](whatcable/FORK.md), [whatcable/USAGE.md](whatcable/USAGE.md).

## Automations

| Folder | Description |
|--------|-------------|
| [wiz-night-guard](wiz-night-guard/) | WiZ bulb watchdog: arm after off, force off on power blips overnight |
| [whatcable](whatcable/) | Fork of [WhatCable](https://github.com/darrylmorley/whatcable) with a live power-monitor CLI plugin (not official WhatCable / not Pro) |

## Add a new automation

1. Create `<name>/` with its own README
2. Use `config.example.py` + gitignored `config.local.py` for machine-specific settings (IPs, schedules)
3. Put runtime state and logs under `~/.local/share/<name>/`
4. Do not commit secrets or LAN IPs in tracked config
5. Prefer stdlib until shared code is needed across automations
6. If scheduled on macOS, add `install.sh` / `uninstall.sh` and a `launchd/` template
