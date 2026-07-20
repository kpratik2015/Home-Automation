# WhatCable fork (Home-Automation)

This directory is a **downstream fork** of [WhatCable](https://github.com/darrylmorley/whatcable) by Darryl Morley. It is **not** the official WhatCable app, **not** WhatCable Pro, and **not** affiliated with or endorsed by the upstream author.

Licensing in the parent [Home-Automation](../) repo is proprietary by default. Only this `whatcable/` subtree carries the open-source terms below.

## What we changed

The upstream `Sources/WhatCablePlugins/` tree is an empty stub in the public repository; the commercial Pro plugin ships only in official release binaries. This fork adds our own MIT-licensed plugin code in that directory:

- `--power-monitor` - live power telemetry in the terminal
- `--power-monitor-json` - same data as newline-delimited JSON
- `--cable-score` - per-port scorecard (checklist, gaps, Amazon.in suggestions)
- `--cable-score-json` - same scorecard as JSON

Implementation uses the upstream MIT modules `WhatCableCore` and `WhatCableDarwinBackend`. We did not copy or reverse-engineer WhatCable Pro. Amazon.in recommendations are a hand-curated catalog in the plugin, not scraped from the web.

## Upstream license

Most of this tree remains under the upstream MIT license. See [LICENSE](LICENSE) (WhatCable copyright retained).

Plugin files under `Sources/WhatCablePlugins/` are MIT-licensed. See [Sources/WhatCablePlugins/LICENSE](Sources/WhatCablePlugins/LICENSE) (same text as [PLUGIN_LICENSE](PLUGIN_LICENSE)).

## Build

Requires macOS 14+, Apple Silicon, Swift 5.9+ (Xcode 15+). Command reference: [USAGE.md](USAGE.md).

```bash
cd whatcable
swift build
swift run whatcable-cli --power-monitor
swift run whatcable-cli --cable-score
```

## Support upstream

If you want the full polished product (Negotiation Diagnostics, Display Diagnostics, cable history, TUI dashboard, and more), buy [WhatCable Pro](https://whatcable.uk/pro) from the upstream project.

## Syncing with upstream

```bash
cd whatcable
git remote add upstream https://github.com/darrylmorley/whatcable.git   # once
git fetch upstream
git merge upstream/main
```

Resolve conflicts in `Sources/WhatCablePlugins/` carefully; keep our plugin files and upstream MIT changes.
