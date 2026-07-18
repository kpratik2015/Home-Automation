# Home-Automation

Personal home automations. Each automation lives in its own folder.

## Automations

| Folder | Description |
|--------|-------------|
| [wiz-night-guard](wiz-night-guard/) | WiZ bulb watchdog: arm after off, force off on power blips overnight |

## Add a new automation

1. Create `<name>/` with its own README
2. Use `config.example.py` + gitignored `config.local.py` for machine-specific settings (IPs, schedules)
3. Put runtime state and logs under `~/.local/share/<name>/`
4. Do not commit secrets or LAN IPs in tracked config
5. Prefer stdlib until shared code is needed across automations
6. If scheduled on macOS, add `install.sh` / `uninstall.sh` and a `launchd/` template
