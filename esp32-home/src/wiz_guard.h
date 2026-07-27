#pragma once

#include <Arduino.h>

namespace wiz {

void begin(const char *bulbIp, uint16_t port);
void setNightWindow(int startHour, int startMinute, int endHour, int endMinute, int pollSec);
bool getPilot(bool *isOn);
bool turnOff();
bool inNightWindow();
void beginNightWindow();
bool isArmed();
void setArmed(bool armed);
bool isPaused();
void setPausedUntil(unsigned long unixSeconds);
unsigned long pausedUntil();
void setLastGuardOffAt(unsigned long unixSeconds);
unsigned long lastGuardOffAt();
const char *windowKey();
void setWindowKey(const char *key);
void runOnce(bool dryRun, bool forceWindow);
void endNightWindow();
int pollIntervalSeconds();

}  // namespace wiz
