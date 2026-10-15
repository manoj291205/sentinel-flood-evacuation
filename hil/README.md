# Phase 28 HIL bench (local only)

The three ESP32 nodes run MicroPython 1.23 or later. Keep the Mosquitto broker on the local network with authentication configured in a local ignored file. Never expose the broker to the Internet. Flash `hil/firmware/common/` with each node's `main.py`, provision Wi-Fi and broker credentials locally, then call that node's `run(host)` from its boot configuration. The optional GSM module is not needed for the OLED vehicle terminal.

## Wiring

| Node | Part signal | ESP32 pin | Electrical note |
|---|---|---|---|
| Water level | JSN-SR04T TRIG | GPIO5 | Sensor powered by 5 V |
| Water level | JSN-SR04T ECHO | GPIO18 | 1 kΩ / 2 kΩ divider to 3.3 V; common ground |
| Shelter | Beam A output | GPIO32 | A then B means entry; pull-up |
| Shelter | Beam B output | GPIO33 | B then A means exit; pull-up |
| Shelter | Relay IN1 (green ADMIT) | GPIO26 | 5 V relay supply, common ground |
| Shelter | Relay IN2 (red REJECT) | GPIO27 | 5 V relay supply, common ground |
| Vehicle | SSD1306 SDA | GPIO21 | I²C, 3.3 V |
| Vehicle | SSD1306 SCL | GPIO22 | I²C, 3.3 V |
| Vehicle | Optional SIM800L UART RX/TX | GPIO17 / GPIO16 | Separate rated 2 A supply; confirm module voltage |

Mount the water sensor 50 cm above the container floor. Its reading is the median of five pings, with `level_cm = 50 - distance_cm`, clamped at zero. Shelter occupancy is persisted in ESP32 NVS; `sigma = 0.5 + 0.02 * count` is a counting-error model, not a measured confidence interval. Verify beam direction, relay polarity, and safe lamp state before attaching loads. The reference actuator in `src/hil/bridge.py` checks certificate ID, canonical hash, kind, action, group, and people before it acknowledges a command. An ACK alone is not proof of physical actuation.

`python -m hil.sim.publisher --steps 3` publishes reproducible simulated readings to an in-memory bus. The System page must label these SIMULATED. No simulated latency belongs in `data/eval_results/phase28/latency.json`; that file is reserved for 100 real sensor-to-ack bench trials after assembly.
