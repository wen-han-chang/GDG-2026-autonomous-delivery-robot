# ESP32 Car MQTT Firmware (esp32-car-mqtt)

This branch contains the ESP32 firmware for MQTT-based motor control + line-sensor assisted turning.

## Features
- MQTT command control (topic: `car/cmd`)
- Supports JSON payload: `{"cmd":"forward","speed":160}`
- Safety: auto-stop if no command within N ms
- Turn behavior: `left/right` = turn until the first black line is detected (KSB042 2-way line sensor)

## Hardware / Wiring

### Motor Driver Pins (ESP32)
| Function | GPIO |
|---|---|
| A1A | 25 |
| A1B | 26 |
| B1A | 32 |
| B1B | 33 |

### Line Sensor (KSB042)
| Sensor | GPIO |
|---|---|
| LOT (Left tracking) | 17 |
| ROT (Right tracking) | 18 |

## MQTT API

### Subscribe
- Topic: `car/cmd`

### Payload
**Option A: raw string**
- `"forward" | "back" | "left" | "right" | "stop"`

**Option B: JSON**
```json
{ "cmd": "right", "speed": 160 }
````

* `cmd`: forward/back/left/right/stop
* `speed`: 0~255 (optional)

### Semantics (IMPORTANT)

* `left`: turn left until the first black line is detected (both LOT & ROT detect black)
* `right`: turn right until the first black line is detected (both LOT & ROT detect black)

## Configuration (DO NOT COMMIT SECRETS)

Create `firmware/config.h` based on `firmware/config.example.h`.
`config.h` contains WiFi password and broker IP, so it must NOT be committed.

## Build / Upload

### Arduino IDE

1. Install libraries: PubSubClient, ArduinoJson
2. Select board: ESP32 Dev Module
3. Open `firmware/*.ino`, upload

## Quick Test

```bash
mosquitto_pub -h <MQTT_HOST> -t car/cmd -m "{\"cmd\":\"forward\",\"speed\":160}"
mosquitto_pub -h <MQTT_HOST> -t car/cmd -m "{\"cmd\":\"right\"}"
mosquitto_pub -h <MQTT_HOST> -t car/cmd -m "{\"cmd\":\"stop\"}"
```

## Troubleshooting

* If turn never stops: check whether black line outputs HIGH or LOW (`BLACK_IS_HIGH`)
* If car keeps moving when backend stops: check CMD timeout setting

```

