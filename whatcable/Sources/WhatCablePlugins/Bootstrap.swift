import WhatCableAppKit

@MainActor
public func bootstrapPlugins(registry: PluginRegistry) {
    PowerMonitorCommand.register(with: registry)
    CableScoreCommand.register(with: registry)
}
