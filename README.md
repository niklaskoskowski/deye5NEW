# Deye SUN-800-G3 -> MQTT -> HTTP (PHP listener)

## What it does
- Reads inverter data via Modbus/TCP (Deye proprietary `tcp`) from:
  - IP: `192.168.0.137`
  - Port: `8899`
  - Serial: `3927602827`
- Publishes metrics to a local MQTT broker (mosquitto)
- Forwards MQTT messages to your webhosting via HTTP POST to a PHP listener

## Install on Raspberry Pi (Docker)
1. Copy `config/deye.env` and `config/forwarder.env` and set:
   - `HTTP_ENDPOINT=https://YOURDOMAIN.TLD/deye_listener.php`
   - `HTTP_AUTH_TOKEN=...` (and implement the same secret check server-side)
2. Start:
   ```bash
   docker compose up -d
   ```
3. Logs:
   ```bash
   docker logs -f deye-inverter-mqtt
   docker logs -f deye-mqtt-sql-forwarder
   ```

## Arcane Docker Manager
- Create a new stack/project
- Paste `docker-compose.yml`
- Upload/add the env files from `config/` (or paste their contents)
- Deploy

## Payload format sent to PHP
If batching enabled:
```json
{
  "site_id": "raspi-1",
  "ts": 1730000000,
  "messages": [
    { "topic": "deye/...", "ts": 1730000000, "payload": {...} }
  ]
}
```

If batching disabled:
```json
{ "site_id": "raspi-1", "message": { "topic": "deye/...", "payload": ... } }
```

## Build/publish images to GHCR
- Push to `main` builds and pushes:
  - `ghcr.io/niklaskoskowski/deye-mqtt-sql-forwarder:latest`
  - `ghcr.io/niklaskoskowski/deye-inverter-mqtt:2026.01.1`
- Tagging:
  - `git tag v2026.01.1 && git push --tags` pushes version-tagged forwarder image too.
