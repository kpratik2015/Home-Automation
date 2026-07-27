#include <Arduino.h>

#if !WIFI_DISABLED
#include <WiFi.h>
#endif

#if __has_include("config.h")
#include "config.h"
#else
#include "config.example.h"
#endif

#ifndef WIZ_GUARD_ENABLED
#define WIZ_GUARD_ENABLED 1
#endif

#ifndef WIFI_DISABLED
#define WIFI_DISABLED 0
#endif

#ifndef FAN_BLE_SERIAL_ENABLED
#define FAN_BLE_SERIAL_ENABLED 1
#endif

#ifndef QUEUE_ENABLED
#define QUEUE_ENABLED 0
#endif

#include "fan_ble.h"

#if WIZ_GUARD_ENABLED
#include "wiz_guard.h"
#endif

#if QUEUE_ENABLED && !WIFI_DISABLED
#include "queue_poller.h"
#endif

// Combined build: defer BLE RAM so WiFi PHY can init first.
#if FAN_BLE_SERIAL_ENABLED && !WIFI_DISABLED
extern "C" bool bleInUse(void) {
  return false;
}
#endif

namespace {

constexpr bool kDryRun = false;

bool wifiConnected = false;
bool inWindow = false;

#if !WIFI_DISABLED
void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    return;
  }

  WiFi.mode(WIFI_STA);
  delay(200);
  Serial.printf("WiFi connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long deadline = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && static_cast<long>(deadline - millis()) > 0) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();

  wifiConnected = WiFi.status() == WL_CONNECTED;
  if (wifiConnected) {
    Serial.printf("WiFi OK: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi failed");
  }
}

void syncTime() {
  configTime(19800, 0, "pool.ntp.org", "time.google.com");
  Serial.println("Waiting for NTP...");
  for (int attempt = 0; attempt < 20; attempt += 1) {
    struct tm timeInfo {};
    if (getLocalTime(&timeInfo)) {
      Serial.printf("Time synced: %04d-%02d-%02d %02d:%02d:%02d\n",
                    timeInfo.tm_year + 1900,
                    timeInfo.tm_mon + 1,
                    timeInfo.tm_mday,
                    timeInfo.tm_hour,
                    timeInfo.tm_min,
                    timeInfo.tm_sec);
      return;
    }
    delay(500);
  }
  Serial.println("NTP sync failed; night window checks may be wrong");
}
#endif

void printStatus() {
  Serial.println("--- status ---");
#if !WIFI_DISABLED
  Serial.printf("WiFi: %s\n", WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString().c_str() : "disconnected");

  struct tm timeInfo {};
  if (getLocalTime(&timeInfo)) {
    Serial.printf("Time: %04d-%02d-%02d %02d:%02d:%02d\n",
                  timeInfo.tm_year + 1900,
                  timeInfo.tm_mon + 1,
                  timeInfo.tm_mday,
                  timeInfo.tm_hour,
                  timeInfo.tm_min,
                  timeInfo.tm_sec);
  } else {
    Serial.println("Time: not synced");
  }
#else
  Serial.println("WiFi: disabled (fan_ble_only)");
#endif

#if WIZ_GUARD_ENABLED
  const bool forceWindow = FORCE_NIGHT_WINDOW != 0;
  const bool windowNow = forceWindow || wiz::inNightWindow();
  Serial.printf("Night window: %s (forced=%d)\n", windowNow ? "active" : "inactive", forceWindow ? 1 : 0);
  Serial.printf("Guard armed: %s\n", wiz::isArmed() ? "yes" : "no");
#else
  Serial.println("WiZ guard: disabled");
#endif
#if QUEUE_ENABLED && !WIFI_DISABLED
  Serial.printf("Alexa queue: enabled (%us poll)\n", static_cast<unsigned>(QUEUE_POLL_SECONDS));
#else
  Serial.println("Alexa queue: disabled");
#endif
  Serial.println("--------------");
}

void handleSerialLine(const String &line) {
  if (line.length() == 0) {
    return;
  }

  if (line == "help") {
#if FAN_BLE_SERIAL_ENABLED
    fan::printHelp();
#else
    Serial.println("Serial commands: help, status");
#endif
    return;
  }

  if (line == "status") {
    printStatus();
    return;
  }

#if FAN_BLE_SERIAL_ENABLED
  if (fan::send(line.c_str())) {
    return;
  }
#endif

  Serial.printf("Unknown command: %s\n", line.c_str());
  Serial.println("Type help");
}

void pollSerial() {
  static String buffer;
  while (Serial.available() > 0) {
    const char ch = static_cast<char>(Serial.read());
    if (ch == '\n' || ch == '\r') {
      buffer.trim();
      if (buffer.length() > 0) {
        handleSerialLine(buffer);
      }
      buffer = "";
      continue;
    }
    buffer += ch;
  }
}

void delayWithSerialPoll(unsigned long durationMs) {
  const unsigned long endMs = millis() + durationMs;
  while (static_cast<long>(endMs - millis()) > 0) {
    pollSerial();
#if QUEUE_ENABLED && !WIFI_DISABLED
    queue::tick();
#endif
    delay(10);
  }
}

#if !WIFI_DISABLED
void pauseWifiForBle() {
  WiFi.disconnect(false, true);
  WiFi.mode(WIFI_OFF);
  delay(100);
}

void resumeWifiAfterBle() {
  Serial.println("Restoring WiFi after BLE burst...");
  WiFi.mode(WIFI_STA);
  connectWifi();
  if (wifiConnected) {
    syncTime();
    Serial.println("WiFi restored");
    return;
  }
  Serial.println("WiFi restore failed; rebooting...");
  delay(100);
  ESP.restart();
}
#endif

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
#if WIFI_DISABLED
  Serial.println("esp32-home: fan BLE test (no WiFi)");
#else
  Serial.println("esp32-home: WiZ guard + fan BLE + Alexa queue (24/7)");
#endif

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

#if !WIFI_DISABLED
  connectWifi();
  if (wifiConnected) {
    syncTime();
  }
#endif

#if WIZ_GUARD_ENABLED
  wiz::begin(BULB_IP, WIZ_PORT);
  wiz::setNightWindow(
      NIGHT_START_HOUR,
      NIGHT_START_MINUTE,
      NIGHT_END_HOUR,
      NIGHT_END_MINUTE,
      POLL_SECONDS);
#endif

#if FAN_BLE_SERIAL_ENABLED
#if !WIFI_DISABLED
  fan::setWifiHooks(pauseWifiForBle, resumeWifiAfterBle);
#else
  fan::setWifiHooks(nullptr, nullptr);
#endif
  Serial.println("Serial ready. Type help.");
  fan::printHelp();
#endif

#if !WIFI_DISABLED && QUEUE_ENABLED
  queue::begin();
#endif
}

void loop() {
  pollSerial();

#if !WIFI_DISABLED
  if (WiFi.status() != WL_CONNECTED) {
    wifiConnected = false;
    connectWifi();
    if (!wifiConnected) {
      delay(1000);
      return;
    }
    syncTime();
  }
#if QUEUE_ENABLED
  queue::tick();
#endif
#endif

#if !WIZ_GUARD_ENABLED
  delay(100);
  return;
#else
  const bool forceWindow = FORCE_NIGHT_WINDOW != 0;
  const bool windowNow = forceWindow || wiz::inNightWindow();

  if (windowNow && !inWindow) {
    wiz::beginNightWindow();
    Serial.println("Night window opened; disarmed until first off");
  }

  if (!windowNow && inWindow) {
    wiz::endNightWindow();
    digitalWrite(LED_BUILTIN, LOW);
  }

  inWindow = windowNow;

  if (windowNow) {
    digitalWrite(LED_BUILTIN, HIGH);
    wiz::runOnce(kDryRun, forceWindow);
    delayWithSerialPoll(static_cast<unsigned long>(wiz::pollIntervalSeconds()) * 1000UL);
    return;
  }

  digitalWrite(LED_BUILTIN, LOW);
  delayWithSerialPoll(1000);
#endif
}
