#include "queue_poller.h"

#include <ArduinoJson.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

#include "fan_ble.h"

#if __has_include("config.h")
#include "config.h"
#else
#include "config.example.h"
#endif

#ifndef QUEUE_ENABLED
#define QUEUE_ENABLED 0
#endif

#ifndef QUEUE_POLL_SECONDS
#define QUEUE_POLL_SECONDS 3
#endif

#ifndef QUEUE_DEBOUNCE_MS
#define QUEUE_DEBOUNCE_MS 1500
#endif

namespace {

constexpr unsigned long kPollIntervalMs = static_cast<unsigned long>(QUEUE_POLL_SECONDS) * 1000UL;
constexpr unsigned long kConnectTimeoutMs = 12000;
constexpr unsigned long kReadTimeoutMs = 12000;
constexpr unsigned long kErrorBackoffCapMs = 60000;
constexpr size_t kMaxResponseBytes = 4096;

unsigned long lastPollMs = 0;
unsigned long errorBackoffMs = kPollIntervalMs;

struct DebounceSlot {
  const char *name;
  unsigned long lastSentMs;
};

DebounceSlot debounceSlots[] = {
    {"fan-on", 0},
    {"fan-off", 0},
    {"light-on", 0},
    {"light-off", 0},
};

struct ParsedUrl {
  String host;
  uint16_t port;
  String path;
};

bool parseQueueUrl(ParsedUrl &parsed) {
  String url = QUEUE_BASE_URL;
  if (!url.startsWith("https://")) {
    return false;
  }
  url.remove(0, 8);
  const int slashIndex = url.indexOf('/');
  String hostPort = slashIndex >= 0 ? url.substring(0, slashIndex) : url;
  parsed.path = slashIndex >= 0 ? url.substring(slashIndex) : "/";
  const int colonIndex = hostPort.indexOf(':');
  if (colonIndex >= 0) {
    parsed.host = hostPort.substring(0, colonIndex);
    parsed.port = static_cast<uint16_t>(hostPort.substring(colonIndex + 1).toInt());
  } else {
    parsed.host = hostPort;
    parsed.port = 443;
  }
  if (parsed.path.length() == 0) {
    parsed.path = "/";
  }
  return parsed.host.length() > 0;
}

bool readAllRaw(WiFiClientSecure &client, String &raw) {
  raw = "";
  raw.reserve(1024);
  const unsigned long deadline = millis() + kReadTimeoutMs;

  while ((client.connected() || client.available() > 0) && static_cast<long>(deadline - millis()) > 0) {
    while (client.available() > 0) {
      if (raw.length() >= kMaxResponseBytes) {
        Serial.println("Queue: response too large");
        return false;
      }
      raw += static_cast<char>(client.read());
    }
    delay(10);
  }

  return raw.length() > 0;
}

bool headerContains(const String &headers, const char *name) {
  const String needle = String(name) + ":";
  return headers.indexOf(needle) >= 0 || headers.indexOf(String(name) + ": ") >= 0;
}

String decodeChunkedBody(const String &chunkedBody) {
  String decoded;
  decoded.reserve(chunkedBody.length());
  size_t index = 0;

  while (index < chunkedBody.length()) {
    const size_t lineEnd = chunkedBody.indexOf("\r\n", index);
    if (lineEnd < 0) {
      break;
    }

    const String sizeLine = chunkedBody.substring(index, lineEnd);
    const long chunkSize = strtol(sizeLine.c_str(), nullptr, 16);
    if (chunkSize <= 0) {
      break;
    }

    index = lineEnd + 2;
    if (index + static_cast<size_t>(chunkSize) > chunkedBody.length()) {
      break;
    }

    decoded += chunkedBody.substring(index, index + static_cast<size_t>(chunkSize));
    index += static_cast<size_t>(chunkSize) + 2;
  }

  return decoded;
}

bool readHttpResponse(WiFiClientSecure &client, int &statusCode, String &body) {
  String raw;
  if (!readAllRaw(client, raw)) {
    Serial.println("Queue: empty response");
    return false;
  }

  if (raw.length() >= 2 && static_cast<uint8_t>(raw[0]) == 0x00 && static_cast<uint8_t>(raw[1]) == 0x00) {
    Serial.println("Queue: HTTP/2 response (ALPN failed)");
    Serial.printf("Queue: response bytes:%s\n", raw.substring(0, 24).c_str());
    return false;
  }

  const int statusIndex = raw.indexOf("HTTP/");
  if (statusIndex < 0) {
    Serial.println("Queue: missing HTTP status line");
    return false;
  }

  const int spaceIndex = raw.indexOf(' ', statusIndex);
  const int nextSpace = raw.indexOf(' ', spaceIndex + 1);
  if (spaceIndex < 0) {
    return false;
  }
  statusCode = raw.substring(spaceIndex + 1, nextSpace > 0 ? nextSpace : raw.length()).toInt();

  const int headerEnd = raw.indexOf("\r\n\r\n");
  if (headerEnd < 0) {
    body = "";
    return true;
  }

  const String headers = raw.substring(statusIndex, headerEnd);
  String payload = raw.substring(headerEnd + 4);

  if (headerContains(headers, "Transfer-Encoding")) {
    body = decodeChunkedBody(payload);
  } else {
    body = payload;
  }
  body.trim();
  return true;
}

bool requestQueue(const char *method, const char *script, const char *body, int &statusCode, String &response) {
  ParsedUrl parsed;
  if (!parseQueueUrl(parsed)) {
    Serial.println("Queue: invalid QUEUE_BASE_URL");
    return false;
  }

  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(kConnectTimeoutMs / 1000);
  static const char *alpnProtocols[] = {"http/1.1", nullptr};
  client.setAlpnProtocols(alpnProtocols);

  if (!client.connect(parsed.host.c_str(), parsed.port, static_cast<int32_t>(kConnectTimeoutMs))) {
    Serial.println("Queue: HTTPS connect failed");
    return false;
  }

  String requestPath = parsed.path;
  if (!requestPath.endsWith("/")) {
    requestPath += "/";
  }
  requestPath += script;

  client.print(String(method) + " " + requestPath + " HTTP/1.1\r\n");
  client.print("Host: ");
  client.print(parsed.host);
  client.print("\r\nAuthorization: Bearer ");
  client.print(QUEUE_DEQUEUE_TOKEN);
  client.print("\r\nUser-Agent: esp32-home-poller/1.0\r\nConnection: close\r\n");
  if (body != nullptr) {
    client.print("Content-Type: application/json\r\nContent-Length: ");
    client.print(strlen(body));
    client.print("\r\n\r\n");
    client.print(body);
  } else {
    client.print("\r\n");
  }
  client.flush();
  delay(50);

  if (!readHttpResponse(client, statusCode, response)) {
    client.stop();
    return false;
  }
  client.stop();
  return true;
}

enum class DequeueResult {
  Error,
  Empty,
  Job,
};

DequeueResult dequeueJob(int &jobId, String &commandName) {
  int statusCode = 0;
  String response;
  if (!requestQueue("GET", "dequeue.php", nullptr, statusCode, response)) {
    return DequeueResult::Error;
  }
  if (statusCode == 204 || (statusCode == 200 && response.length() == 0)) {
    return DequeueResult::Empty;
  }
  if (statusCode != 200) {
    Serial.printf("Queue: dequeue HTTP %d: %s\n", statusCode, response.c_str());
    return DequeueResult::Error;
  }

  JsonDocument doc;
  const DeserializationError error = deserializeJson(doc, response);
  if (error) {
    Serial.printf("Queue: invalid dequeue JSON: %s (%s)\n", error.c_str(), response.c_str());
    return DequeueResult::Error;
  }

  jobId = doc["id"].as<int>();
  commandName = doc["command"].as<String>();
  if (jobId <= 0 || commandName.length() == 0) {
    Serial.println("Queue: dequeue missing id/command");
    return DequeueResult::Error;
  }
  return DequeueResult::Job;
}

bool ackJob(int jobId, const char *status) {
  JsonDocument doc;
  doc["id"] = jobId;
  doc["status"] = status;
  String body;
  serializeJson(doc, body);

  int statusCode = 0;
  String response;
  if (!requestQueue("POST", "ack.php", body.c_str(), statusCode, response)) {
    return false;
  }
  if (statusCode != 200) {
    Serial.printf("Queue: ack HTTP %d: %s\n", statusCode, response.c_str());
    return false;
  }
  return true;
}

bool isDebounced(const char *commandName) {
  const unsigned long nowMs = millis();
  for (DebounceSlot &slot : debounceSlots) {
    if (strcmp(slot.name, commandName) == 0) {
      if (slot.lastSentMs != 0 && static_cast<long>(nowMs - slot.lastSentMs) < static_cast<long>(QUEUE_DEBOUNCE_MS)) {
        return true;
      }
      slot.lastSentMs = nowMs;
      return false;
    }
  }
  return false;
}

void handleJob(int jobId, const String &commandName) {
  Serial.printf("Queue job %d: %s\n", jobId, commandName.c_str());

  if (isDebounced(commandName.c_str())) {
    Serial.printf("Queue job %d debounced, waiting for lease retry\n", jobId);
    return;
  }

  if (!fan::send(commandName.c_str())) {
    Serial.printf("Queue job %d failed\n", jobId);
    if (!ackJob(jobId, "failed")) {
      Serial.printf("Queue: ack failed for job %d\n", jobId);
    }
    return;
  }

  if (!ackJob(jobId, "done")) {
    Serial.printf("Queue: ack failed for job %d\n", jobId);
  }
}

}  // namespace

namespace queue {

void begin() {
#if QUEUE_ENABLED
  lastPollMs = millis();
  errorBackoffMs = kPollIntervalMs;
  Serial.printf("Queue poller: %s every %us\n", QUEUE_BASE_URL, static_cast<unsigned>(QUEUE_POLL_SECONDS));
#else
  Serial.println("Queue poller: disabled");
#endif
}

void tick() {
#if !QUEUE_ENABLED
  return;
#endif
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  const unsigned long nowMs = millis();
  if (static_cast<long>(nowMs - lastPollMs) < static_cast<long>(errorBackoffMs)) {
    return;
  }
  lastPollMs = nowMs;

  int jobId = 0;
  String commandName;
  const DequeueResult result = dequeueJob(jobId, commandName);
  if (result == DequeueResult::Empty) {
    errorBackoffMs = kPollIntervalMs;
    return;
  }
  if (result == DequeueResult::Error) {
    errorBackoffMs = min(errorBackoffMs * 2UL, kErrorBackoffCapMs);
    return;
  }

  errorBackoffMs = kPollIntervalMs;
  handleJob(jobId, commandName);
}

}  // namespace queue
