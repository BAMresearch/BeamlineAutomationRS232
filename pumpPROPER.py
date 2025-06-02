#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  2 09:34:12 2025

@author: tomek
tomasz.stawski@bam.de
"""

import serial
import time

# -----------------------------------------------------------
# COMMANDS dictionary (class attribute)
# -----------------------------------------------------------
COMMANDS = {
    # No-parameter commands:
    'VER'      : "VER",        # Query firmware version
    'FUN'      : "FUN",        # Query pump status
    'RUN'      : "RUN",        # Start current program
    'STP'      : "STP",        # Emergency stop
    'REL'      : "REL",        # Resume after stop (if supported)
    'HOM'      : "HOM",        # Home (if supported)
    'RTR'      : "RTR",        # Return to ready state (if supported)
    'PRT'      : "PRT",        # Print current parameters (if supported)
    'EEP'      : "EEP",        # Read from EEPROM (if supported)
    'SAV'      : "SAV",        # Save current settings to EEPROM (if supported)
    'ALM?'     : "ALM?",       # Query alarm/status log (if supported)

    # Parameterized commands:
    'DIA'      : "DIA{param:.2f}",       # Set syringe inner diameter (mm)
    'VOL'      : "VOL{param:.3f}",       # Set volume (mL)
    'RAT'      : "RAT{param:.3f}",       # Set rate (mL/min)
    'DIR_INF'  : "DIR INF",              # Set direction to INFuse
    'DIR_WDR'  : "DIR WDR",              # Set direction to WDRaw
    'DIR_'     : "DIR {param}",          # Generic DIR: param="INF" or "WDR"
    'SAF'      : "SAF{param:d}",         # Safe-mode timeout (seconds): 0 = off
    'TMO'      : "TMO{param:d}",         # Communication timeout (if supported)
    'ADR'      : "ADR{param:02d}",       # Set pump address (00-99)
    'BAU'      : "BAU{param:d}",         # Set baud index (e.g., 4=9600)
    'BEO'      : "BEO{param:d}",         # Beep on/off: 0=off, 1=on
    'FSF'      : "FSF{param:d}",         # Flush serial FIFO (if supported)
}


class AladdinPump:
    """
    Encapsulates RS-232 communication with a WPI Aladdin syringe pump.
    """

    def __init__(
        self,
        device: str = "/dev/ttyUSB0",
        baud: int = 9600,
        timeout: float = 0.5
    ):
        """
        Initialize the pump:
        - Open the serial port with 8 data bits, no parity, 1 stop bit, no flow control.
        - Flush any buffered data.
        """
        self.device = device
        self.baud = baud
        self.timeout = timeout

        try:
            self.ser = serial.Serial(
                port=self.device,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            # Give the port a moment to initialize
            time.sleep(0.1)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"Opened {self.device} @ {self.baud} baud (8N1, no flow control)")
        except Exception as e:
            print(f"ERROR opening {self.device}: {e}")
            self.ser = None

    def close(self):
        """
        Close the serial port if open.
        """
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial port closed.")

    def send_cmd(self, cmd: str, pause: float = 0.1) -> str:
        """
        Send an ASCII command (without CR), append '\\r', then read + return the reply.
        Strips STX (0x02), ETX (0x03), and a two-digit address prefix if present.
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")
        self.ser.write((cmd + "\r").encode("ascii"))
        time.sleep(pause)
        raw = self.ser.read_all()
        text = raw.decode("ascii", errors="ignore")

        # Strip leading STX and trailing ETX if present
        if text.startswith('\x02') and text.endswith('\x03'):
            text = text[1:-1]
        # If first two chars are digits (address), drop them
        if len(text) >= 2 and text[:2].isdigit():
            text = text[2:]
        return text.strip()

    def wait_until_idle(self, timeout: float = 60.0) -> bool:
        """
        Poll 'FUN' every 0.5 s until pump reports completion or timeout expires.
        Many Aladdin pumps respond with 'END' or start with 'S' when idle.
        """
        start = time.time()
        while time.time() - start < timeout:
            resp = self.send_cmd(COMMANDS['FUN'], pause=0.05)
            if resp.startswith("END") or resp.startswith("S"):
                return True
            time.sleep(0.5)
        return False

    def verify(self) -> str:
        """
        Send 'VER' and return pump firmware response.
        Raises RuntimeError if no valid 'SNE' response is received.
        """
        resp = self.send_cmd(COMMANDS['VER'])
        if not resp.startswith("SNE"):
            raise RuntimeError(f"No valid response to VER. Got: {repr(resp)}")
        return resp

    def set_diameter(self, diameter_mm: float) -> str:
        """
        Set syringe inner diameter (mm).
        """
        cmd = COMMANDS['DIA'].format(param=diameter_mm)
        return self.send_cmd(cmd)

    def set_volume(self, volume_ml: float) -> str:
        """
        Set infusion/withdrawal volume (mL).
        """
        cmd = COMMANDS['VOL'].format(param=volume_ml)
        return self.send_cmd(cmd)

    def set_rate(self, rate_ml_per_min: float) -> str:
        """
        Set infusion/withdrawal rate (mL/min).
        """
        cmd = COMMANDS['RAT'].format(param=rate_ml_per_min)
        return self.send_cmd(cmd)

    def set_direction(self, direction: str) -> str:
        """
        Set direction to 'INF' (infuse) or 'WDR' (withdraw).
        """
        if direction not in ("INF", "WDR"):
            raise ValueError("Direction must be 'INF' or 'WDR'")
        cmd = COMMANDS['DIR_'].format(param=direction)
        return self.send_cmd(cmd)

    def run(self) -> str:
        """
        Send 'RUN' to start infusion or withdrawal.
        """
        return self.send_cmd(COMMANDS['RUN'])

    def stop(self) -> str:
        """
        Send 'STP' for an emergency stop.
        """
        return self.send_cmd(COMMANDS['STP'])

    def safe_mode(self, timeout_sec: int) -> str:
        """
        Enable or disable Safe Mode. Use timeout_sec=0 to turn off.
        """
        cmd = COMMANDS['SAF'].format(param=timeout_sec)
        return self.send_cmd(cmd)


#############################################################################
#                                    EXAMPLE OF INFUSION
#############################################################################

    def run_infusion_test(
        self,
        diameter_mm: float = 4.61,
        volume_ml: float = 20.000,
        rate_ml_per_min: float = 5.0,
        max_wait: float = 60.0
    ):
        """
        1) Verify pump with 'VER'
        2) Set default units to mL/mL-min
        3) Home and wait for 'HOM' to finish
        4) Set diameter, volume, rate
        5) Set direction INF and RUN
        6) Poll status; if no 'END' after timeout, stop and cleanup
        """
        try:
            fw = self.verify()
            print("Pump firmware:", fw)
        except RuntimeError as e:
            print(e)
            return

        # Set default units to mL and mL/min
        resp = self.send_cmd("VOL ML")
        print("VOL ML →", resp)
        resp = self.send_cmd("RAT 0 MM")
        print("RAT 0 MM →", resp)

        # Homing
        print("Sending HOM")
        resp = self.send_cmd(COMMANDS['HOM'])
        print("HOM →", resp)
        print("Waiting for homing to complete")
        if not self.wait_until_idle(timeout=30.0):
            print("WARNING: Homing did not complete within 30 s. Check syringe/drive.")
            self.stop()
            return
        print("Homing complete")

        # Set syringe diameter
        print(f"Setting diameter to {diameter_mm:.2f} mm")
        resp = self.set_diameter(diameter_mm)
        print(f"DIA{diameter_mm:.2f} → {resp}")

        # Set volume (20 mL)
        print(f"Setting volume to {volume_ml:.3f} mL")
        resp = self.set_volume(volume_ml)
        print(f"VOL{volume_ml:.3f} → {resp}")

        # Set rate
        print(f"Setting rate to {rate_ml_per_min:.3f} mL/min")
        resp = self.set_rate(rate_ml_per_min)
        print(f"RAT{rate_ml_per_min:.3f} → {resp}")

        # Set direction → INFuse
        print("Setting direction to INF")
        resp = self.set_direction("INF")
        print("DIR INF →", resp)

        # Run infusion
        print("Starting infusion (RUN)")
        resp = self.run()
        print("RUN →", resp)

        # Poll status every 0.5 s, up to max_wait
        print(f"Waiting for infusion to complete (up to {max_wait:.0f} s)")
        start = time.time()
        while time.time() - start < max_wait:
            status = self.send_cmd(COMMANDS['FUN'], pause=0.05)
            if status.startswith("END") or status.startswith("S"):
                print("Pump is idle (infusion complete)")
                break
            time.sleep(0.5)
        else:
            print("WARNING: Timeout waiting for infusion. Pump may be stuck or ticking without motion.")
            print("Check syringe seating, diameter, and rate.")
            self.stop()
            print("STP sent due to timeout")
            self.close()
            return

        # Cleanup: emergency stop
        self.stop()
        print("Emergency stop sent")
        self.close()


#############################################################################
#                                    EXAMPLE OF WITHDRAWING
#############################################################################

    def run_withdrawal_test(
        self,
        diameter_mm: float = 4.61,
        volume_ml: float = 20.000,
        rate_ml_per_min: float = 5.0,
        max_wait: float = 60.0
    ):
        """
        1) Verify pump with 'VER'
        2) Set default units to mL/mL-min
        3) Home and wait for 'HOM' to finish
        4) Set diameter, volume, rate
        5) Set direction WDR and RUN
        6) Poll status; if no 'END' after timeout, stop and cleanup
        """
        try:
            fw = self.verify()
            print("Pump firmware:", fw)
        except RuntimeError as e:
            print(e)
            return

        # Set default units to mL and mL/min
        resp = self.send_cmd("VOL ML")
        print("VOL ML →", resp)
        resp = self.send_cmd("RAT 0 MM")
        print("RAT 0 MM →", resp)

        # Homing
        print("Sending HOM")
        resp = self.send_cmd(COMMANDS['HOM'])
        print("HOM →", resp)
        print("Waiting for homing to complete")
        if not self.wait_until_idle(timeout=30.0):
            print("WARNING: Homing did not complete within 30 s. Check syringe/drive.")
            self.stop()
            return
        print("Homing complete")

        # Set syringe diameter
        print(f"Setting diameter to {diameter_mm:.2f} mm")
        resp = self.set_diameter(diameter_mm)
        print(f"DIA{diameter_mm:.2f} → {resp}")

        # Set volume (20 mL)
        print(f"Setting volume to {volume_ml:.3f} mL")
        resp = self.set_volume(volume_ml)
        print(f"VOL{volume_ml:.3f} → {resp}")

        # Set rate
        print(f"Setting rate to {rate_ml_per_min:.3f} mL/min")
        resp = self.set_rate(rate_ml_per_min)
        print(f"RAT{rate_ml_per_min:.3f} → {resp}")

        # Set direction → WDRaw
        print("Setting direction to WDR")
        resp = self.set_direction("WDR")
        print("DIR WDR →", resp)

        # Run withdrawal
        print("Starting withdrawal (RUN)")
        resp = self.run()
        print("RUN →", resp)

        # Poll status every 0.5 s, up to max_wait
        print(f"Waiting for withdrawal to complete (up to {max_wait:.0f} s)")
        start = time.time()
        while time.time() - start < max_wait:
            status = self.send_cmd(COMMANDS['FUN'], pause=0.05)
            if status.startswith("END") or status.startswith("S"):
                print("Pump is idle (withdrawal complete)")
                break
            time.sleep(0.5)
        else:
            print("WARNING: Timeout waiting for withdrawal. Pump may be stuck or ticking without motion.")
            print("Verify syringe seating, diameter, and rate.")
            self.stop()
            print("STP sent due to timeout")
            self.close()
            return

        # Cleanup: emergency stop
        self.stop()
        print("Emergency stop sent")
        self.close()


# -----------------------------------------------------------
# Example usage
# -----------------------------------------------------------
if __name__ == "__main__":
    pump = AladdinPump(device="/dev/ttyUSB0", baud=9600)
    if pump.ser:
        pump.run_infusion_test(
            diameter_mm=10.00,     # 10 mm syringe diameter
            volume_ml=2.000,      # 20 mL
            rate_ml_per_min=5.0,  # 20 mL/min
            max_wait=60.0
        )
    else:
        print("Failed to open serial port. Exiting.")

    pump = AladdinPump(device="/dev/ttyUSB0", baud=9600)
    if pump.ser:
        pump.run_withdrawal_test(
            diameter_mm=10.00,     # 10 mm syringe diameter
            volume_ml=2.000,      # 20 mL
            rate_ml_per_min=5.0,  # 20 mL/min
            max_wait=60.0
        )
    else:
        print("Failed to open serial port. Exiting.")
