# Alexa skill setup (Hall Fan Light)

Personal custom skill - no AWS Lambda. HTTPS endpoint is PHP on your hosting.

## 1. Create the skill

1. Open [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)
2. **Create Skill** → Custom → Provision your own → Host skill in Alexa-hosted (No) → Create skill manually
3. **Invocation name:** `living room` (must match [`interaction-model.json`](interaction-model.json); Alexa requires 2+ words)

## 2. Interaction model

1. **Build** → **Interaction Model** → JSON Editor
2. Paste contents of [`interaction-model.json`](interaction-model.json)
3. Save and build

## 3. Endpoint

1. **Build** → **Endpoint**
2. **HTTPS** → `https://pratikkataria.com/home-automation/fan-queue/skill.php`
3. Certificate: **My development endpoint is a sub-domain of a domain that has a wildcard certificate...**
4. Save

## 4. Test

1. **Test** tab → enable testing for **Development**
2. Type or say: *turn on the fan*
3. Expect speech: "Turning the fan on." and a queued job on hosting

## 5. Enable on your Echo

Alexa app → **More** → **Skills & Games** → **Your Skills** → **Dev** → enable **Hall Fan Light**

## Voice phrases

Custom skill phrasing (not Smart Home):

- *"Alexa, ask living room to turn on the fan"*
- *"Alexa, ask living room to turn off the fan"*
- *"Alexa, ask living room to turn on the light"*
- *"Alexa, ask living room to turn off the light"*

Natural *"Alexa, turn on living room fan"* needs a Smart Home skill (out of scope).

## Troubleshooting

| Issue | Check |
|-------|--------|
| Skill returns error | `curl https://pratikkataria.com/home-automation/fan-queue/health.php` |
| Signature verify fails | Hosting can reach `s3.amazonaws.com`; check PHP `openssl` |
| Fan does not move | Mac bridge running with `QUEUE_ENABLED = True`; check `bridge.log` |
| Job stuck | Lease expires after 30s; Mac acks `failed` on BLE errors |
