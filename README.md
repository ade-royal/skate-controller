# skate-controller

Minimal scaffold for a sensor-driven skate controller project.

Devpost here: https://devpost.com/software/skatecontroller#submission-history

## Project layout

```text
skate-controller/
├── sensor/
│   ├── mpu6050.py
│   └── calibration.py
├── controller/
│   ├── movement.py
│   └── mappings.py
├── laptop/
│   └── keyboard_output.py
├── tests/
├── requirements.txt
└── README.md
```
## Connecting to the Raspberry Pi

The Raspberry Pi runs headless and is accessed from a Windows laptop over SSH.

### 1. Start the network

1. Turn on the phone hotspot.
2. Connect the Windows laptop to the hotspot.
3. Power on the Raspberry Pi.
4. Wait until the hotspot shows both devices connected.

Both devices must be reachable on the same local network for direct SSH access. Raspberry Pi supports SSH for remote terminal access over a local network. 

### 2. Find the Raspberry Pi's IP address

The Pi's IP address may change between connections.

From PowerShell, populate the ARP table:

```powershell
1..14 | ForEach-Object { ping -n 1 -w 150 "172.20.10.$_" | Out-Null }
