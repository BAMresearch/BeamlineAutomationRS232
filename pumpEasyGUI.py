#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  2 09:34:12 2025

@author: tomek
tomasz.stawski@bam.de

PumpGUI: A Tkinter GUI for controlling a WPI Aladdin syringe pump over RS-232.
Allows you to set syringe diameter, units, and then withdraw or dispense arbitrary
volumes (up to 50 mL) in chunks ≤ 9.999 mL, with a real‐time progress bar and
live update of current volume.

To set permissions for a serial port under Linux:
sudo usermod -a -G tty $USER
sudo usermod -a -G dialout $USER
REBOOT

Under Windows:
change 
device: str = "/dev/ttyUSB0"

to
check the port assignement in "Device Manager". Read out the port name e.g. "COM1". 
device: str = "COM1"
The port name may change upon each physical reconnection of a serial adapter.


"""

import serial
import time
import threading

import tkinter as tk
from tkinter import ttk, messagebox

# RS-232 commands per AL-1010 manual
COMMANDS = {
    'VER'       : "VER",            # Query firmware version
    'FUN'       : "FUN",            # Query pump status
    'RUN'       : "RUN",            # Start current program
    'STP'       : "STP",            # Emergency stop
    'DIA'       : "DIA{param:.2f}",  # Set syringe diameter (mm)
    'VOL'       : "VOL{param:.3f}",  # Set volume (mL)
    'RAT'       : "RAT{param:.3f}",  # Set rate (mL/min)
    'DIR_'      : "DIR {param}",     # Direction: "INF" or "WDR"
    'UNIT_VOL'  : "VOL ML",          # Units → mL
    'UNIT_RAT'  : "RAT ML/MIN",      # Units → mL/min
}


class AladdinPump:
    """
    RS-232 driver for WPI Aladdin syringe pump.
    Tracks current_volume and enforces max_capacity.
    """
    MAX_SINGLE_VOL = 9.999  # per-command volume cap (mL)

    def __init__(self,
                 device: str = "/dev/ttyUSB0",
                 baud: int = 9600,
                 timeout: float = 0.5,
                 diameter_mm: float = 26.0,
                 max_volume_ml: float = 50.0):
        self.device = device
        self.baud = baud
        self.timeout = timeout
        self.diameter_mm = diameter_mm
        self.current_volume = 0.0
        self.max_volume = max_volume_ml

        try:
            self.ser = serial.Serial(
                port=device, baudrate=baud,
                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE, timeout=timeout,
                xonxoff=False, rtscts=False, dsrdtr=False
            )
            time.sleep(0.1)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"Opened {device} @ {baud} baud (8N1)")
        except Exception as e:
            print(f"ERROR opening {device}: {e}")
            self.ser = None
            return

        # initialize units and diameter
        print("[INIT] UNIT_VOL →", self.send_cmd(COMMANDS['UNIT_VOL']))
        print("[INIT] UNIT_RAT →", self.send_cmd(COMMANDS['UNIT_RAT']))
        print("[INIT] DIA →", self.set_diameter(diameter_mm))

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial port closed.")

    def send_cmd(self, cmd: str, pause: float = 0.1) -> str:
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")
        self.ser.write((cmd + "\r").encode("ascii"))
        time.sleep(pause)
        raw = self.ser.read_all()
        txt = raw.decode("ascii", errors="ignore")
        if txt.startswith('\x02') and txt.endswith('\x03'):
            txt = txt[1:-1]
        if len(txt) >= 2 and txt[:2].isdigit():
            txt = txt[2:]
        return txt.strip()

    def set_diameter(self, d: float) -> str:
        return self.send_cmd(COMMANDS['DIA'].format(param=d))

    def set_volume(self, v: float) -> str:
        if v > self.MAX_SINGLE_VOL:
            raise ValueError(f"Chunk {v:.3f} mL > {self.MAX_SINGLE_VOL}")
        if self.current_volume + v > self.max_volume:
            raise RuntimeError("Capacity exceeded")
        resp = self.send_cmd(COMMANDS['VOL'].format(param=v))
        self.current_volume += v
        print(f"[PUMP] set_volume({v:.3f}) → {resp}")
        return resp

    def set_rate(self, r: float) -> str:
        if r <= 0 or r > 9.999:
            raise ValueError("Rate must be 0 < rate ≤ 9.999")
        resp = self.send_cmd(COMMANDS['RAT'].format(param=r))
        print(f"[PUMP] set_rate({r:.3f}) → {resp}")
        return resp

    def set_direction(self, d: str) -> str:
        resp = self.send_cmd(COMMANDS['DIR_'].format(param=d))
        print(f"[PUMP] set_direction({d}) → {resp}")
        return resp

    def run(self) -> str:
        resp = self.send_cmd(COMMANDS['RUN'])
        print(f"[PUMP] RUN → {resp}")
        return resp

    def stop(self) -> str:
        resp = self.send_cmd(COMMANDS['STP'])
        print(f"[PUMP] STP → {resp}")
        return resp

    def get_status(self) -> str:
        return self.send_cmd(COMMANDS['FUN'], pause=0.05)


class PumpGUI(tk.Tk):
    """
    Tkinter GUI around AladdinPump:
      • set & display max/current volume
      • enter move volume & rate
      • WITHDRAW, RELEASE buttons
      • progress bar & real-time current volume update
    """
    def __init__(self):
        super().__init__()
        self.title("Aladdin Pump Control")
        self.resizable(False, False)

        self.pump = AladdinPump()
        if not self.pump.ser:
            messagebox.showerror("Error", "Cannot open pump port")
            self.destroy()
            return

        # GUI variables
        self.max_vol_var     = tk.DoubleVar(self, value=self.pump.max_volume)
        self.current_vol_var = tk.DoubleVar(self, value=self.pump.current_volume)
        self.move_vol_var    = tk.DoubleVar(self, value=0.0)
        self.rate_var        = tk.DoubleVar(self, value=9.999)

        # Build UI
        r = 0
        ttk.Label(self, text="Max Volume (mL):")\
            .grid(column=0, row=r, padx=5, pady=5, sticky="e")
        ttk.Entry(self, textvariable=self.max_vol_var, width=8)\
            .grid(column=1, row=r)
        ttk.Button(self, text="Set", command=self.on_set_max)\
            .grid(column=2, row=r)

        r += 1
        ttk.Label(self, text="Current Volume (mL):")\
            .grid(column=0, row=r, padx=5, sticky="e")
        ttk.Label(self, textvariable=self.current_vol_var, width=8)\
            .grid(column=1, row=r)

        r += 1
        ttk.Label(self, text="Move Vol (mL):")\
            .grid(column=0, row=r, padx=5, sticky="e")
        ttk.Entry(self, textvariable=self.move_vol_var, width=8)\
            .grid(column=1, row=r)

        r += 1
        ttk.Label(self, text="Rate (mL/min):")\
            .grid(column=0, row=r, padx=5, sticky="e")
        ttk.Entry(self, textvariable=self.rate_var, width=8)\
            .grid(column=1, row=r)

        r += 1
        ttk.Button(self, text="WITHDRAW", command=self.on_fill)\
            .grid(column=0, row=r, padx=5, pady=10)
        ttk.Button(self, text="RELEASE",  command=self.on_release)\
            .grid(column=1, row=r)

        r += 1
        self.progress = ttk.Progressbar(self, orient='horizontal',
                                        length=300, mode='determinate')
        self.progress.grid(column=0, row=r, columnspan=3, pady=10)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_set_max(self):
        """Change the syringe’s maximum capacity."""
        try:
            mv = float(self.max_vol_var.get())
            if mv <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Max volume must be > 0")
            self.max_vol_var.set(self.pump.max_volume)
            return
        self.pump.max_volume = mv
        if self.pump.current_volume > mv:
            self.pump.current_volume = mv
        self.current_vol_var.set(self.pump.current_volume)

    def _chunked_move(self, vol, rate, direction):
        """
        Break a transfer into ≤9.999 mL chunks, updating both the
        progress bar and current volume display in real time.
        """
        total = vol
        base = self.pump.current_volume
        # For RELEASE, we decrement before starting
        if direction == "INF":
            base = self.pump.current_volume  # after pre-decrement
        done = 0.0

        chunks = []
        rem = vol
        while rem > 0:
            chunks.append(min(rem, self.pump.MAX_SINGLE_VOL))
            rem -= chunks[-1]

        self.progress['maximum'] = total

        for c in chunks:
            if direction == "WDR":
                # Withdraw: track final volume
                self.pump.set_volume(c)
            else:
                # Release: only send command; volume was pre-adjusted
                self.pump.send_cmd(COMMANDS['VOL'].format(param=c))

            self.pump.set_rate(rate)
            self.pump.set_direction(direction)
            self.pump.run()

            expected = (c / rate) * 60.0 * 1.001
            start = time.time()
            while True:
                elapsed = time.time() - start
                if elapsed >= expected:
                    break
                pumped = min(elapsed / expected, 1.0) * c
                # update progress bar
                self.progress['value'] = done + pumped
                # update displayed current volume
                self.current_vol_var.set(base + done + pumped)
                self.update_idletasks()
                time.sleep(0.1)

            self.pump.stop()
            done += c
            # final full-chunk updates
            self.progress['value'] = done
            self.current_vol_var.set(self.pump.current_volume)

        # reset progress bar
        self.progress['value'] = 0

    def on_fill(self):
        """Withdraw into the syringe (WDR)."""
        vol, rate = self.move_vol_var.get(), self.rate_var.get()
        if vol <= 0 or rate <= 0 or rate > 9.999:
            messagebox.showerror("Error", "Invalid vol/rate")
            return
        if self.pump.current_volume + vol > self.pump.max_volume:
            messagebox.showerror("Error", "Not enough capacity")
            return
        threading.Thread(
            target=self._chunked_move,
            args=(vol, rate, "WDR"),
            daemon=True
        ).start()

    def on_release(self):
        """Dispense from the syringe (INF)."""
        vol, rate = self.move_vol_var.get(), self.rate_var.get()
        if vol <= 0 or rate <= 0 or rate > 9.999:
            messagebox.showerror("Error", "Invalid vol/rate")
            return
        if vol > self.pump.current_volume:
            messagebox.showerror("Error", "Not enough volume")
            return
        # pre-decrement so pump.set_volume won't add back
        self.pump.current_volume -= vol
        threading.Thread(
            target=self._chunked_move,
            args=(vol, rate, "INF"),
            daemon=True
        ).start()

    def on_close(self):
        """Cleanup and exit."""
        try:
            self.pump.stop()
        except:
            pass
        self.pump.close()
        self.destroy()


if __name__ == "__main__":
    app = PumpGUI()
    app.mainloop()
