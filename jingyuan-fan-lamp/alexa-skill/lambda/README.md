# Alexa Smart Home Lambda proxy

Alexa Smart Home skills require a Lambda ARN. This function forwards directives to `smarthome.php` on your hosting.

## Region

Use **Europe (Ireland) `eu-west-1`** - Alexa "Europe, India" maps here.

Do not use `ap-south-1` or `eu-north-1` for the Alexa endpoint.

## 1. Create Lambda (eu-west-1)

1. [Lambda Console](https://eu-west-1.console.aws.amazon.com/lambda/home?region=eu-west-1) - confirm region is **Ireland**
2. **Create function** → Author from scratch
3. Name: `center-fan-light-alexa`
4. Runtime: **Node.js 22.x**
5. Create function
6. Paste `index.mjs` into the code editor
7. **Configuration** → **Environment variables**:

| Key | Value |
|-----|--------|
| `LAMBDA_PROXY_TOKEN` | same token as hosting `config.local.php` |
| `TARGET_HOST` | `pratikkataria.com` (optional) |
| `TARGET_PATH` | `/home-automation/fan-queue/smarthome.php` (optional) |

8. **Deploy**

## 2. Hosting token

On server, add to `config.local.php`:

```php
'LAMBDA_PROXY_TOKEN' => '<random-hex-from-openssl-rand-hex-24>',
```

Redeploy if needed: `./scripts/deploy-fan-queue.sh`

## 3. Alexa console

**Build → Smart Home**:

- Payload: **v3**
- Default endpoint: paste Lambda ARN from Ireland
- Check **Europe, India** → paste same ARN
- **SAVE**

Skip account linking only after OAuth is configured (see `../README.md`).

## 4. $1 billing alert

1. [Billing → Budgets](https://console.aws.amazon.com/billing/home#/budgets)
2. **Create budget** → **Zero spend budget** or **Custom**
3. Amount: **$1.00** monthly
4. Alert threshold: **100%** (actual spend >= $1)
5. Email: your address
6. Create

Also: **Billing → Billing preferences** → enable **Receive Billing Alerts**.

## ARN format

```
arn:aws:lambda:eu-west-1:<ACCOUNT_ID>:function:center-fan-light-alexa
```

Copy from Lambda → **Copy ARN** (top right on function page).
