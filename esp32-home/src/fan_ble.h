#pragma once

#include <Arduino.h>

namespace fan {

using HookFn = void (*)();

void setWifiHooks(HookFn pause, HookFn resume);
bool send(const char *commandName);
void printHelp();

}  // namespace fan
