const TARGET_HOST = process.env.TARGET_HOST ?? "pratikkataria.com";
const TARGET_PATH =
  process.env.TARGET_PATH ?? "/home-automation/fan-queue/smarthome.php";
const PROXY_TOKEN = process.env.LAMBDA_PROXY_TOKEN ?? "";

export const handler = async (event) => {
  if (!PROXY_TOKEN) {
    throw new Error("LAMBDA_PROXY_TOKEN env var is not set");
  }

  const body = JSON.stringify(event);
  const response = await fetch(`https://${TARGET_HOST}${TARGET_PATH}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${PROXY_TOKEN}`,
      "X-Lambda-Proxy-Token": PROXY_TOKEN,
    },
    body,
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Backend ${response.status}: ${text}`);
  }

  return JSON.parse(text);
};
