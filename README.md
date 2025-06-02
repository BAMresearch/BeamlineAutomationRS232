# AladdinPump Control Script

A Python script to control a WPI Aladdin syringe pump over RS-232.  
Provides methods to initialize the pump, send commands, and run predefined infusion/withdrawal tests.

## Features

- **RS-232 communication** with 8 data bits, no parity, 1 stop bit, no flow control  
- **COMMANDS** dictionary containing all standard pump commands  
- Encapsulated in an `AladdinPump` class with methods to:
  - Verify firmware (`VER`)  
  - Home (`HOM`)  
  - Set diameter (`DIA`), volume (`VOL`), rate (`RAT`), direction (`DIR`)  
  - Run (`RUN`), Stop (`STP`), Safe Mode (`SAF`)  
- Example test routines:
  - `run_infusion_test(...)`: homes, sets units to mL/mL-min, loads 20 mL, infuses at 5 mL/min, polls until complete, then emergency stops  
  - `run_withdrawal_test(...)`: same sequence for withdrawal  

## Requirements

- Python 3.7+  
- [pySerial](https://pyserial.readthedocs.io/) (`pip install pyserial`)  
- Aladdin pump configured for RS-232 (address 00, baud 9600)  
- Linux (add user to `dialout` group) or Windows with a free COM port  

## Installation

1. Clone this repository or copy the script to your project folder.  
2. Install dependencies:
   ```bash
   pip install pyserial
