#include "fan_ble.h"

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <host/ble_gap.h>

namespace {

constexpr unsigned long kBurstIntervalMs = 200;
constexpr unsigned long kBurstDurationMs = 2500;
constexpr unsigned long kEndHoldMs = 250;

const uint16_t kEndPacket[] = {0xCDAB, 0x7856};

struct CommandDef {
  const char *name;
  const uint16_t *packetA;
  size_t lenA;
  const uint16_t *packetB;
  size_t lenB;
};

const uint16_t kFanOnA[] = {
    0x08F0, 0x8230, 0xFEFD, 0x5993, 0xFD35, 0x8C2A, 0xC6D9, 0x5208, 0xEC92,
    0x3571, 0x696E, 0x573F, 0x9881,
};
const uint16_t kFanOnB[] = {
    0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x6394, 0x6812, 0x0A44, 0xFCFB,
    0x58EE, 0xAEF4, 0x7994, 0x3A42,
};
const uint16_t kFanOffA[] = {
    0x08F0, 0x8230, 0xFFFD, 0x5993, 0xFD35, 0x8C2A, 0xC6D9, 0x5208, 0xEA92,
    0x0C71, 0x6935, 0x573F, 0x280D,
};
const uint16_t kFanOffB[] = {
    0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x6354, 0x0812, 0x0A24, 0xFC1B,
    0x7FC9, 0x89F4, 0x80E1, 0x97A1,
};
const uint16_t kLightOnA[] = {
    0x08F0, 0x8230, 0xFEFD, 0x5993, 0xFD35, 0x8C2A, 0xE7D9, 0x5208, 0xEAB2,
    0x2271, 0x69B1, 0x573F, 0x2F9C,
};
const uint16_t kLightOnB[] = {
    0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x63D0, 0x0812, 0x0A24, 0xFCFB,
    0x07B1, 0xF1F4, 0x4D6C, 0x36E8,
};
const uint16_t kLightOffA[] = {
    0x08F0, 0x8230, 0xFFFD, 0x5993, 0xFD35, 0x8C2A, 0xE6D9, 0x5208, 0xEAB2,
    0xBC71, 0x6979, 0x573F, 0xF68F,
};
const uint16_t kLightOffB[] = {
    0xF877, 0x5FB6, 0x5E2B, 0xFC00, 0x5131, 0x6350, 0x0812, 0x0A24, 0xFC1B,
    0xB80E, 0x4EF4, 0x22BB, 0x2A11,
};

const CommandDef kCommands[] = {
    {"fan-on", kFanOnA, sizeof(kFanOnA) / sizeof(uint16_t), kFanOnB, sizeof(kFanOnB) / sizeof(uint16_t)},
    {"fan-off", kFanOffA, sizeof(kFanOffA) / sizeof(uint16_t), kFanOffB, sizeof(kFanOffB) / sizeof(uint16_t)},
    {"light-on", kLightOnA, sizeof(kLightOnA) / sizeof(uint16_t), kLightOnB, sizeof(kLightOnB) / sizeof(uint16_t)},
    {"light-off", kLightOffA, sizeof(kLightOffA) / sizeof(uint16_t), kLightOffB, sizeof(kLightOffB) / sizeof(uint16_t)},
};

bool bleReady = false;
bool advConfigured = false;
fan::HookFn pauseWifi = nullptr;
fan::HookFn resumeWifi = nullptr;

const CommandDef *findCommand(const char *name) {
  for (const CommandDef &command : kCommands) {
    if (strcmp(command.name, name) == 0) {
      return &command;
    }
  }
  return nullptr;
}

void configureAdvertising() {
  if (advConfigured) {
    return;
  }
  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->setAdvertisementType(BLE_GAP_CONN_MODE_NON);
  advertising->setMinInterval(32);
  advertising->setMaxInterval(48);
  advertising->setScanResponse(false);
  advConfigured = true;
}

bool ensureBle() {
  if (bleReady) {
    return true;
  }
  if (!BLEDevice::init("")) {
    Serial.println("BLE init failed");
    return false;
  }
  for (int attempt = 0; attempt < 30; attempt += 1) {
    if (BLEDevice::getInitialized()) {
      break;
    }
    delay(50);
  }
  delay(300);
  BLEDevice::setPower(ESP_PWR_LVL_P9, ESP_BLE_PWR_TYPE_ADV);
  configureAdvertising();
  bleReady = true;
  return true;
}

// Flags + complete 16-bit service UUID list (31-byte legacy PDU, matches iOS layout).
void advertiseWords(const uint16_t *words, size_t count) {
  if (count == 0 || count > 13) {
    return;
  }

  uint8_t ad[31];
  size_t len = 0;
  ad[len++] = 2;
  ad[len++] = 0x01;
  ad[len++] = 0x06;
  ad[len++] = static_cast<uint8_t>(1 + count * 2);
  ad[len++] = 0x03;
  for (size_t index = 0; index < count; index += 1) {
    ad[len++] = static_cast<uint8_t>(words[index] & 0xFF);
    ad[len++] = static_cast<uint8_t>((words[index] >> 8) & 0xFF);
  }

  BLEAdvertisementData advData;
  advData.addData(reinterpret_cast<char *>(ad), len);

  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->stop();
  advertising->setAdvertisementData(advData);
  BLEDevice::startAdvertising();
}

void teardownBle() {
  if (!bleReady) {
    return;
  }
  BLEDevice::getAdvertising()->stop();
  BLEDevice::deinit(true);
  bleReady = false;
  advConfigured = false;
}

void runBurst(const CommandDef &command) {
  advertiseWords(command.packetA, command.lenA);
  bool usePacketA = false;
  unsigned long nextToggleMs = millis() + kBurstIntervalMs;
  const unsigned long endMs = millis() + kBurstDurationMs;

  while (static_cast<long>(endMs - millis()) > 0) {
    if (static_cast<long>(millis() - nextToggleMs) >= 0) {
      usePacketA = !usePacketA;
      if (usePacketA) {
        advertiseWords(command.packetA, command.lenA);
      } else {
        advertiseWords(command.packetB, command.lenB);
      }
      nextToggleMs += kBurstIntervalMs;
    }
    delay(1);
  }

  advertiseWords(kEndPacket, sizeof(kEndPacket) / sizeof(uint16_t));
  delay(kEndHoldMs);
  BLEDevice::getAdvertising()->stop();
}

}  // namespace

namespace fan {

void setWifiHooks(HookFn pause, HookFn resume) {
  pauseWifi = pause;
  resumeWifi = resume;
}

bool send(const char *commandName) {
  const CommandDef *command = findCommand(commandName);
  if (command == nullptr) {
    Serial.printf("Unknown BLE command: %s\n", commandName);
    return false;
  }

#if FAN_BLE_SERIAL_ENABLED
  if (pauseWifi != nullptr) {
    pauseWifi();
  }
#endif
  if (!ensureBle()) {
#if FAN_BLE_SERIAL_ENABLED
    if (resumeWifi != nullptr) {
      resumeWifi();
    }
#endif
    return false;
  }

  Serial.printf("BLE burst: %s (2.5s)\n", commandName);
  for (int attempt = 0; attempt < 2; attempt += 1) {
    runBurst(*command);
    if (attempt == 0) {
      delay(400);
    }
  }
  Serial.println("BLE burst done");

#if FAN_BLE_SERIAL_ENABLED
  if (resumeWifi != nullptr) {
    teardownBle();
    resumeWifi();
  }
#endif
  return true;
}

void printHelp() {
  Serial.println("Serial commands:");
  Serial.println("  help");
  Serial.println("  status");
  Serial.println("  fan-on | fan-off | light-on | light-off");
}

}  // namespace fan
