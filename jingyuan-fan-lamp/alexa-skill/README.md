# Alexa Smart Home setup (Center Fan / Center Light)

Natural voice: *"Alexa, turn on center fan"*

## 1. Deploy hosting

```bash
cd jingyuan-fan-lamp
./scripts/deploy-fan-queue.sh
./scripts/setup-oauth-config.sh
```

Save the printed **Client ID** and **Client Secret** for step 3.

## 2. Lambda (eu-west-1)

See [`lambda/README.md`](lambda/README.md). Lambda test with Discover event must return Center Fan / Center Light.

## 3. Alexa Developer Console

### Smart Home endpoint

**Build → Smart Home**:

- Payload **v3**
- Default endpoint: Lambda ARN (Ireland, no `:1`)
- **Europe, India**: same ARN
- Save

### Account linking (required)

**Build → Account linking**:

| Field | Value |
|-------|--------|
| Authorization URI | `https://pratikkataria.com/home-automation/fan-queue/oauth/authorize.php` |
| Access Token URI | `https://pratikkataria.com/home-automation/fan-queue/oauth/token.php` |
| Client ID | from `setup-oauth-config.sh` output |
| Client Secret | from `setup-oauth-config.sh` output |
| Authentication Scheme | Credentials in request body |
| Access Token Scheme | Bearer |
| Scope | (empty) |
| Domain list | `pratikkataria.com` |

Save.

## 4. Enable + link in Alexa app

1. **Skills & Games** → **Your Skills** → **Dev** → **Center Fan Light** → **Enable**
2. Tap **Link account** → **Link account** on web page
3. Wait for discover, or say *"Alexa, discover devices"*
4. Expect **Center Fan** and **Center Light**

## 5. ESP32

Flash `esp32-home` `home` env with queue config. Serial shows `Queue:` on Alexa commands.

## Troubleshooting

| Issue | Check |
|-------|--------|
| Can't find devices on enable | Account linking saved; re-run `setup-oauth-config.sh` if secrets mismatch |
| Link page error | `./scripts/deploy-fan-queue.sh` deployed `oauth/` |
| Lambda OK, app fails | `smarthome.log` on server during discover |
| Fan doesn't move | ESP queue poller |

## Legacy

Custom skill `center lamp` is deprecated.
