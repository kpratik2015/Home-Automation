# Skroman touch panel (SKIT*)

Old Skroman WiFi touch panel. SoftAP SSID looks like `SKIT58xxxx`.

## Local config (secrets)

Device-specific SSIDs and passwords live in **`local.env`** (gitignored). Template:

```bash
cp local.env.example local.env
# edit SKIT_SOFTAP_* and HOME_WIFI_*
```

## APK facts (Skroman iTouch 1.7)

| Item | Value |
|------|-------|
| SoftAP password | device-specific (see `local.env`; APK text "password 8" is often wrong) |
| SoftAP SSIDs | `SKIT*` (eg. `SKIT6982Y0`) |
| Panel IPs | `192.168.4.1`, `192.168.41.1`, `192.168.43.1` |
| Local paths | `/command`, `/status` |
| WiFi upload | `configw-...`, `config-...` |
| Switch cmds | `M:L:0;`, `M:L:1;` |
| Cloud | MQTT `e-stree.com:1883`, HTTPS `e-stree.com:6000` |
| Stack | Custom e-stree / kitouch - **not Tuya** |

## Provision onto home WiFi

```bash
# 1. Join panel SoftAP (values from local.env)
source local.env
networksetup -setairportnetwork en0 "$SKIT_SOFTAP_SSID" "$SKIT_SOFTAP_PASSWORD"

# 2. Confirm Mac is 192.168.4.x
ipconfig getifaddr en0

# 3. Push home 2.4 GHz creds
python3 kitouch_provision.py --ssid "$HOME_WIFI_SSID" --password "$HOME_WIFI_PASSWORD"

# If SoftAP drops: rejoin home WiFi, then:
python3 discover.py --full-scan
python3 kitouch_control.py --scan
```

## Control after LAN join

```bash
python3 kitouch_control.py --host <panel-ip> --status
python3 kitouch_control.py --host <panel-ip> --cmd 'M:L:1;'
```

## Older / fallback tools

```bash
python3 softap_provision.py --ssid "$HOME_WIFI_SSID" --password "$HOME_WIFI_PASSWORD"
python3 smartconfig.py --ssid "$HOME_WIFI_SSID" --password "$HOME_WIFI_PASSWORD"
```

## Packet capture

```bash
sudo tcpdump -i en0 -w skit-prov.pcap host 192.168.4.1 or udp
```

## Hardware fallback

WiFi daughterboard swap / Shelly on loads if SoftAP never accepts config.

## Dead ends (evidence)

- Ora Matter IDs, Tuya SoftAP, HTTP on `:80`
- SoftAP app-protocol push (`kitouch_provision.py` + pcap):
  - UDP config/discovery → **0 replies from gateway**
  - TCP probes → **0 SYN-ACK**, only RST
  - SoftAP is DHCP-only; no kitouch listener in SoftAP mode
