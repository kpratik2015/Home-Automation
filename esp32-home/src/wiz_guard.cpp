#include "wiz_guard.h"

#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <time.h>

namespace {

constexpr unsigned long kUdpTimeoutMs = 3000;
constexpr size_t kJsonCapacity = 512;

Preferences prefs;
WiFiUDP udp;
String bulbIp;
uint16_t wizPort = 38899;

int nightStartHour = 1;
int nightStartMinute = 0;
int nightEndHour = 10;
int nightEndMinute = 0;
int pollSeconds = 30;

bool armed = false;
unsigned long pausedUntilEpoch = 0;
unsigned long lastGuardOffAtEpoch = 0;
char windowKeyBuf[12] = "";

bool sendUdp(const JsonDocument &request, JsonDocument &response) {
  String payload;
  serializeJson(request, payload);

  if (!udp.beginPacket(bulbIp.c_str(), wizPort)) {
    return false;
  }
  udp.write(reinterpret_cast<const uint8_t *>(payload.c_str()), payload.length());
  if (!udp.endPacket()) {
    return false;
  }

  unsigned long deadline = millis() + kUdpTimeoutMs;
  while (static_cast<long>(deadline - millis()) > 0) {
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
      char buffer[kJsonCapacity];
      int len = udp.read(buffer, sizeof(buffer) - 1);
      if (len < 0) {
        return false;
      }
      buffer[len] = '\0';
      DeserializationError err = deserializeJson(response, buffer);
      return !err;
    }
    delay(10);
  }
  return false;
}

bool timeReady() {
  time_t now = time(nullptr);
  return now > 1704067200;  // 2024-01-01
}

void formatWindowKey(char *out, size_t outLen) {
  struct tm timeInfo {};
  if (!getLocalTime(&timeInfo)) {
    out[0] = '\0';
    return;
  }
  strftime(out, outLen, "%Y-%m-%d", &timeInfo);
}

void logLine(const char *level, const char *message) {
  struct tm timeInfo {};
  if (!getLocalTime(&timeInfo)) {
    Serial.printf("[%s] %s\n", level, message);
    return;
  }
  char stamp[20];
  strftime(stamp, sizeof(stamp), "%Y-%m-%d %H:%M:%S", &timeInfo);
  Serial.printf("%s [%s] %s\n", stamp, level, message);
}

void saveState() {
  prefs.putBool("armed", armed);
  prefs.putULong("paused_until", pausedUntilEpoch);
  prefs.putULong("last_guard_off", lastGuardOffAtEpoch);
  prefs.putString("window_key", windowKeyBuf);
}

void loadState() {
  armed = prefs.getBool("armed", false);
  pausedUntilEpoch = prefs.getULong("paused_until", 0);
  lastGuardOffAtEpoch = prefs.getULong("last_guard_off", 0);
  if (prefs.isKey("window_key")) {
    String key = prefs.getString("window_key", "");
    key.toCharArray(windowKeyBuf, sizeof(windowKeyBuf));
  } else {
    windowKeyBuf[0] = '\0';
  }
}

}  // namespace

namespace wiz {

void begin(const char *ip, uint16_t port) {
  bulbIp = ip;
  wizPort = port;
  prefs.begin("wiz_guard", false);
  loadState();
}

bool getPilot(bool *isOn) {
  if (isOn == nullptr) {
    return false;
  }

  JsonDocument request;
  request["method"] = "getPilot";
  request["params"].to<JsonObject>();

  JsonDocument response;
  if (!sendUdp(request, response)) {
    logLine("WARN", "getPilot failed");
    return false;
  }

  JsonObject result = response["result"].as<JsonObject>();
  if (result.isNull()) {
    logLine("WARN", "getPilot unexpected response");
    return false;
  }

  *isOn = result["state"] | false;
  return true;
}

bool turnOff() {
  JsonDocument request;
  request["method"] = "setPilot";
  JsonObject params = request["params"].to<JsonObject>();
  params["state"] = false;

  JsonDocument response;
  if (!sendUdp(request, response)) {
    logLine("WARN", "setPilot off failed");
    return false;
  }

  logLine("INFO", "Turned off bulb");
  return true;
}

void setNightWindow(int startHour, int startMinute, int endHour, int endMinute, int pollSec) {
  nightStartHour = startHour;
  nightStartMinute = startMinute;
  nightEndHour = endHour;
  nightEndMinute = endMinute;
  pollSeconds = pollSec;
}

bool inNightWindow() {
  if (!timeReady()) {
    return false;
  }

  struct tm timeInfo {};
  if (!getLocalTime(&timeInfo)) {
    return false;
  }

  const int nowMinutes = timeInfo.tm_hour * 60 + timeInfo.tm_min;
  const int startMinutes = nightStartHour * 60 + nightStartMinute;
  const int endMinutes = nightEndHour * 60 + nightEndMinute;
  return nowMinutes >= startMinutes && nowMinutes < endMinutes;
}

void beginNightWindow() {
  armed = false;
  formatWindowKey(windowKeyBuf, sizeof(windowKeyBuf));
  saveState();
}

bool isArmed() { return armed; }
void setArmed(bool value) {
  armed = value;
  saveState();
}

bool isPaused() {
  if (!timeReady()) {
    return false;
  }
  return static_cast<unsigned long>(time(nullptr)) < pausedUntilEpoch;
}

void setPausedUntil(unsigned long unixSeconds) {
  pausedUntilEpoch = unixSeconds;
  saveState();
}

unsigned long pausedUntil() { return pausedUntilEpoch; }

void setLastGuardOffAt(unsigned long unixSeconds) {
  lastGuardOffAtEpoch = unixSeconds;
  saveState();
}

unsigned long lastGuardOffAt() { return lastGuardOffAtEpoch; }

const char *windowKey() { return windowKeyBuf; }

void setWindowKey(const char *key) {
  strncpy(windowKeyBuf, key, sizeof(windowKeyBuf) - 1);
  windowKeyBuf[sizeof(windowKeyBuf) - 1] = '\0';
  saveState();
}

void runOnce(bool dryRun, bool forceWindow) {
  if (!forceWindow && !inNightWindow()) {
    logLine("INFO", "Outside night window");
    armed = false;
    saveState();
    return;
  }

  bool wasPaused = isPaused();
  bool bulbOn = false;
  if (!getPilot(&bulbOn)) {
    return;
  }

  const bool paused = isPaused();
  const bool pauseJustEnded = wasPaused && !paused;

  if (paused) {
    logLine("INFO", "Paused; skipping force-off");
    return;
  }

  static bool waitingLogged = false;
  static bool prevBulbOnValid = false;
  static bool prevBulbOn = false;

  if (!armed) {
    if (bulbOn) {
      if (!waitingLogged) {
        logLine("INFO", "Monitoring; waiting for bulb off before arming");
        waitingLogged = true;
      }
    } else if (!prevBulbOnValid || prevBulbOn) {
      armed = true;
      waitingLogged = false;
      saveState();
      if (prevBulbOnValid && prevBulbOn) {
        logLine("INFO", "Bulb turned off; guard armed");
      } else {
        logLine("INFO", "Bulb already off at window start; guard armed");
      }
    }
  } else if (bulbOn) {
    if (pauseJustEnded) {
      logLine("INFO", "Forcing off (pause ended)");
    } else {
      logLine("INFO", "Forcing off (bulb on while armed)");
    }
    if (!dryRun && turnOff()) {
      setLastGuardOffAt(static_cast<unsigned long>(time(nullptr)));
    } else if (dryRun) {
      logLine("INFO", "[dry-run] would turn off bulb");
    }
  }

  prevBulbOnValid = true;
  prevBulbOn = bulbOn;
}

int pollIntervalSeconds() { return pollSeconds; }

void endNightWindow() {
  armed = false;
  saveState();
  logLine("INFO", "Night window ended; disarmed");
}

}  // namespace wiz
