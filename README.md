# BeamlineAutomationRS232

A collection of Python drivers for RS-232 control of common beamline components at BAM:

- **WPI Aladdin syringe pump**  
- **VICI 10+1 selector valve** (MU actuator)  
- **IKA RET control-visc & RCT digital stirring/heating plates**  

Each driver is encapsulated in its own class; all share a common RS-232 communication layer with 8-bit, no-parity, 1-stop, no flow control settings.

---

## Repository Structure

```
BeamlineAutomationRS232/
├── aladdin_pump.py         # AladdinPump class
├── vici_actuator.py        # ViciActuator class
├── ikalab_device.py        # IkaLabDevice class (RET/RCT plates)
├── README.md               # This file
└── examples/               
    ├── pump_test.py        # Example: infusion & withdrawal tests
    ├── valve_test.py       # Example: set valve to port 5
    └── plate_test.py       # Example: temperature & stirring control
```

---

## Requirements

- Python 3.7 or higher  
- [pySerial](https://pypi.org/project/pyserial/)  
- A USB-RS232 adapter or built-in COM port  

On Linux, grant your user access to serial ports:

```bash
sudo usermod -a -G dialout $USER
# then log out and back in
```

---

## Installation

1. Clone the repo:
   ```bash
   git clone https://github.com/BAMresearch/BeamlineAutomationRS232.git
   cd BeamlineAutomationRS232
   ```
2. Install dependencies:
   ```bash
   pip install pyserial
   ```

---

## Usage

### 1. AladdinPump (WPI syringe pump)

```python
from aladdin_pump import AladdinPump

pump = AladdinPump(device="/dev/ttyUSB0", baud=9600)
if pump.ser:
    pump.run_infusion_test(
        diameter_mm=4.61,     # syringe bore in mm
        volume_ml=20.0,       # 20 mL
        rate_ml_per_min=5.0,  # 5 mL/min
        max_wait=60.0         # seconds
    )
    pump.run_withdrawal_test(
        diameter_mm=4.61, 
        volume_ml=20.0,
        rate_ml_per_min=5.0,
        max_wait=60.0
    )
    pump.close()
else:
    print("Failed to open pump serial port.")
```

### 2. ViciActuator (10+1 selector valve)

```python
from vici_actuator import ViciActuator

valve = ViciActuator(port="/dev/ttyUSB1", baud=9600)
if valve.ser:
    valve.set_mode(3)    # multiposition
    valve.set_np(10)     # 10 ports
    valve.home()         # go to position 1
    valve.go(5)          # rotate so common ↔ port 5
    print("Position:", valve.get_position())
    valve.close()
else:
    print("Failed to open valve serial port.")
```

### 3. IkaLabDevice (IKA RET / RCT plates)

```python
from ikalab_device import IkaLabDevice

plate = IkaLabDevice(device="/dev/ttyUSB2", baud=9600)
if plate.ser:
    model = plate.detect_model()  # e.g. “IKARET” or “RCT…”

    # Stirring example (function 4):
    print("Speed (rpm):", plate.get_actual(4))
    plate.set_setpoint(4, 300)     # set 300 rpm
    plate.remote_on(4)             # start stirring
    time.sleep(5)
    plate.remote_off(4)

    # Heating example (function 2):
    print("Current temp:", plate.get_actual(2))
    plate.set_setpoint(2, 80.0)    # set 80 °C
    plate.remote_on(2)
    time.sleep(10)
    plate.remote_off(2)

    plate.reset()
    plate.close()
else:
    print("Failed to open plate serial port.")
```

---

## Extending & Troubleshooting

- **Add new commands** by editing the `COMMANDS` dict in each module.  
- **Permission errors**: on Linux, ensure your user is in the `dialout` group.  
- **Pump “ticking”**: verify homing, syringe seating, correct diameter, and rate.  
- **Valve stalls**: ensure correct mode (`AM3`) and NP value.  
- **Plate no-response**: confirm 7E1 framing and correct NAMUR channel codes.

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Author

**Tomasz Stawski**  
tomasz.stawski@bam.de  
BAM Research – June 2025
