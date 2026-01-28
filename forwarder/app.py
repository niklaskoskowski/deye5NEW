import json
import os
import time
import threading
from typing import Any, Dict, List

import requests
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_FILTER = os.getenv("MQTT_TOPIC_FILTER", "deye/#")

HTTP_ENDPOINT = os.getenv("HTTP_ENDPOINT", "").strip()
HTTP_AUTH_HEADER_NAME = os.getenv("HTTP_AUTH_HEADER_NAME", "").strip()
HTTP_AUTH_TOKEN = os.getenv("HTTP_AUTH_TOKEN", "").strip()
SITE_ID = os.getenv("SITE_ID", "").strip()

BATCH_ENABLED = os.getenv("BATCH_ENABLED", "false").lower() == "true"
BATCH_MAX_MESSAGES = int(os.getenv("BATCH_MAX_MESSAGES", "50"))
BATCH_MAX_SECONDS = int(os.getenv("BATCH_MAX_SECONDS", "5"))

if not HTTP_ENDPOINT:
    raise SystemExit("HTTP_ENDPOINT is required (e.g. https://example.com/deye_listener.php)")

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})
if HTTP_AUTH_HEADER_NAME and HTTP_AUTH_TOKEN:
    session.headers.update({HTTP_AUTH_HEADER_NAME: HTTP_AUTH_TOKEN})

lock = threading.Lock()
buffer: List[Dict[str, Any]] = []
last_flush = time.time()

def parse_payload(payload: bytes) -> Any:
    try:
        s = payload.decode("utf-8", errors="replace")
    except Exception:
        return {"raw": list(payload)}
    s_stripped = s.strip()
    if (s_stripped.startswith("{") and s_stripped.endswith("}")) or (s_stripped.startswith("[") and s_stripped.endswith("]")):
        try:
            return json.loads(s_stripped)
        except Exception:
            return s
    return s

def post_json(data: Any) -> None:
    try:
        r = session.post(HTTP_ENDPOINT, data=json.dumps(data), timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"[forwarder] HTTP error: {e}")

def flush() -> None:
    global buffer, last_flush
    with lock:
        if not buffer:
            last_flush = time.time()
            return
        payload = {
            "site_id": SITE_ID or None,
            "ts": int(time.time()),
            "messages": buffer,
        }
        buffer = []
        last_flush = time.time()
    post_json(payload)

def flush_loop() -> None:
    while True:
        time.sleep(1)
        if not BATCH_ENABLED:
            continue
        now = time.time()
        with lock:
            due = (now - last_flush) >= BATCH_MAX_SECONDS and len(buffer) > 0
        if due:
            flush()

def on_connect(client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int, properties: Any = None) -> None:
    if rc == 0:
        print(f"[forwarder] Connected to MQTT {MQTT_HOST}:{MQTT_PORT}, subscribing to {MQTT_TOPIC_FILTER}")
        client.subscribe(MQTT_TOPIC_FILTER)
    else:
        print(f"[forwarder] MQTT connect failed rc={rc}")

def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    entry = {
        "topic": msg.topic,
        "qos": msg.qos,
        "retain": bool(msg.retain),
        "ts": int(time.time()),
        "payload": parse_payload(msg.payload),
    }

    if not BATCH_ENABLED:
        post_json({"site_id": SITE_ID or None, "message": entry})
        return

    with lock:
        buffer.append(entry)
        hit_max = len(buffer) >= BATCH_MAX_MESSAGES
    if hit_max:
        flush()

def main() -> None:
    t = threading.Thread(target=flush_loop, daemon=True)
    t.start()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()
