#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 17 13:30:24 2025

@author: tomaszstawski
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IkaLabDevice.py

A unified driver for IKA RET control-visc and IKA Plate RCT digital (RCT 5)
over RS-232, using NAMUR commands.

Detects model via IN_TYPE, then allows:
 - reading actual and set values (temperature, speed, etc.)
 - starting/stopping stirring or heating remotely
 - configuring watchdog (data-flow monitor)
"""

import serial
import time
from typing import Union

class IkaLabDevice:
    NAMUR_CMDS = {
        # Identification
        'IN_TYPE': 'IN_TYPE',
        'IN_NAME': 'IN_NAME',
        'IN_SOFTWARE_ID': 'IN_SOFTWARE_ID',
        # Read actual value
        'IN_PV':    'IN_PV_{x}',    # x = 1;2;3;4;5;7;80;90
        # Read setpoint
        'IN_SP':    'IN_SP_{x}',
        # Write setpoint
        'OUT_SP':   'OUT_SP_{x}@{val}',
        # Remote on/off for functions x
        'START':    'START_{x}',    # x = 1;2;4;5;7;80;90
        'STOP':     'STOP_{x}',
        # Watchdog modes
        'OUT_WD1':  'OUT_WD1@{sec}',
        'OUT_WD2':  'OUT_WD2@{sec}',
        # Reset device (turn off functions)
        'RESET':    'RESET',
        # Status (for e.g. scale)
        'STATUS_90':'STATUS_90',
    }

    def __init__(self, device: str = '/dev/ttyUSB0', baud: int = 9600, timeout: float = 0.5):
        """Open serial port (9600, 7E1, no flow control)."""
        self.device = device
        try:
            self.ser = serial.Serial(
                port=self.device, baudrate=baud,
                bytesize=serial.SEVENBITS, parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE, timeout=timeout,
                xonxoff=False, rtscts=False, dsrdtr=False
            )
            time.sleep(0.1)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"Opened {self.device} @ {baud} baud (7E1, no flow control)")
        except Exception as e:
            print(f"ERROR opening {self.device}: {e}")
            self.ser = None

    def close(self):
        """Close the serial port."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial port closed.")

    def _send(self, cmd: str, pause: float = 0.1) -> str:
        """Send ASCII command+CRLF, return stripped reply."""
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")
        full = cmd + "\r\n"
        self.ser.write(full.encode('ascii'))
        time.sleep(pause)
        raw = self.ser.read_all()
        text = raw.decode('ascii', errors='ignore').strip()
        # Strip leading STX/ETX if present
        if text.startswith('\x02') and text.endswith('\x03'):
            text = text[1:-1]
        return text

    def detect_model(self) -> str:
        """
        Ask the device to identify itself.
        Returns e.g. 'IKARET' for RET control-visc or 'RCT...' for the RCT plate.
        """
        name = self._send(self.NAMUR_CMDS['IN_TYPE'])
        print("Detected device model:", name)
        return name

    def get_actual(self, channel: Union[int, str]) -> str:
        """
        Read current value from channel X.
        channel: 1=temp medium, 2=plate temp, 4=speed, 5=viscosity trend, 7=carrier temp,
                 80=pH, 90=weight
        """
        cmd = self.NAMUR_CMDS['IN_PV'].format(x=channel)
        return self._send(cmd)

    def get_setpoint(self, channel: Union[int, str]) -> str:
        """Read setpoint for channel X."""
        cmd = self.NAMUR_CMDS['IN_SP'].format(x=channel)
        return self._send(cmd)

    def set_setpoint(self, channel: Union[int, str], value: Union[int, float]) -> str:
        """Set target for channel X to value."""
        cmd = self.NAMUR_CMDS['OUT_SP'].format(x=channel, val=value)
        return self._send(cmd)

    def remote_on(self, function: Union[int, str]) -> str:
        """Enable remote function X (e.g. stirring=4, heating=2, scale=90)."""
        cmd = self.NAMUR_CMDS['START'].format(x=function)
        return self._send(cmd)

    def remote_off(self, function: Union[int, str]) -> str:
        """Disable remote function X."""
        cmd = self.NAMUR_CMDS['STOP'].format(x=function)
        return self._send(cmd)

    def reset(self) -> str:
        """Emergency reset: turn off all remote functions."""
        return self._send(self.NAMUR_CMDS['RESET'])

    def set_watchdog(self, mode: int, timeout_s: int) -> str:
        """
        Configure watchdog:
          mode=1 → OUT_WD1@timeout (turns off both stirring/heating on timeout)
          mode=2 → OUT_WD2@timeout (on timeout, moves to safe limits)
        timeout_s: 20–1500 s
        """
        if mode == 1:
            return self._send(self.NAMUR_CMDS['OUT_WD1'].format(sec=timeout_s))
        elif mode == 2:
            return self._send(self.NAMUR_CMDS['OUT_WD2'].format(sec=timeout_s))
        else:
            raise ValueError("Watchdog mode must be 1 or 2")

    def get_scale_status(self) -> str:
        """Read scale status bits (if supported)."""
        return self._send(self.NAMUR_CMDS['STATUS_90'])

# ----------------------
# Example usage
# ----------------------
if __name__ == "__main__":
    dev = IkaLabDevice("/dev/ttyUSB0", 9600)
    if not dev.ser:
        print("Could not open serial port.")
        exit(1)

    model = dev.detect_model()

    # Common operations
    print("Current stirring speed:", dev.get_actual(4))
    print("Setting speed →", dev.set_setpoint(4, 500))    # 500 rpm
    print("Start stirring →", dev.remote_on(4))
    time.sleep(5)
    print("Stop stirring →", dev.remote_off(4))

    # Temperature control example
    print("Current medium temp:", dev.get_actual(1))
    print("Set plate temp →", dev.set_setpoint(2, 100.0))  # 100 °C
    print("Start heating →", dev.remote_on(2))
    time.sleep(10)
    print("Stop heating →", dev.remote_off(2))

    # Clean up
    dev.reset()
    dev.close()
