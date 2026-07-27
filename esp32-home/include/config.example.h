#pragma once

// Copy to include/config.h and edit (config.h is gitignored).

#define WIFI_SSID "your-wifi"
#define WIFI_PASSWORD "your-password"

#define BULB_IP "192.168.0.103"
#define WIZ_PORT 38899

// 24-hour clock. Same calendar day; no cross-midnight window.
#define NIGHT_START_HOUR 1
#define NIGHT_START_MINUTE 0
#define NIGHT_END_HOUR 10
#define NIGHT_END_MINUTE 0

#define POLL_SECONDS 30
#define PAUSE_DEFAULT_MINUTES 60

// Set 1 to ignore clock and stay in guard mode (serial testing).
#define FORCE_NIGHT_WINDOW 0

// 1 = run WiZ night guard in main loop; 0 = skip (fan BLE serial testing).
#define WIZ_GUARD_ENABLED 1

// 1 = accept fan/light commands on serial monitor.
#define FAN_BLE_SERIAL_ENABLED 1
