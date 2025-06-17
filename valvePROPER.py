# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import serial
import time

class ViciActuator:
    """
    Control a VICI 10-position + common (10+1) MU actuator via RS-232/485.
    See VICI MU Actuator User Manual (V2, April 2023) for details :contentReference[oaicite:0]{index=0}.
    """

    def __init__(self, port: str = "/dev/ttyUSB1", baud: int = 9600, timeout: float = 0.5):
        """
        Open serial port (8N1, no flow control) and flush buffers.
        """
        self.port = port
        try:
            self.ser = serial.Serial(port, baud, bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE,
                                     stopbits=serial.STOPBITS_ONE,
                                     timeout=timeout,
                                     xonxoff=False, rtscts=False, dsrdtr=False)
            time.sleep(0.1)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception as e:
            print(f"ERROR opening {port}: {e}")
            self.ser = None

    def close(self):
        """Close serial port if open."""
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_cmd(self, cmd: str, expect_response: bool = True) -> str:
        """
        Send cmd + CR. If expect_response, read until CR and return stripped string.
        Some commands (e.g. LRN, CC without stops) return no response.
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")
        self.ser.write((cmd + "\r").encode('ascii'))
        if not expect_response:
            time.sleep(0.05)
            return ""
        resp = self.ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
        return resp

    # — Basic actuator commands —

    def align(self) -> str:
        """AL: move to reference position before valve install."""
        return self.send_cmd("AL")

    def home(self) -> str:
        """HM: move to position 1 (home)."""
        return self.send_cmd("HM")

    def get_position(self) -> str:
        """CP: display current position."""
        return self.send_cmd("CP")

    def get_status(self) -> str:
        """STAT: display full actuator status (mode, NP, SO, position)."""
        return self.send_cmd("STAT")

    def get_firmware(self, board: int = None) -> str:
        """
        VR: firmware of main PCB
        VR2: firmware of interface PCB.
        """
        cmd = "VR" if board is None else f"VR{board}"
        return self.send_cmd(cmd)

    # — Mode and configuration —

    def get_mode(self) -> str:
        """AM: display current actuator mode."""
        return self.send_cmd("AM")

    def set_mode(self, mode: int) -> str:
        """
        AMn: set mode: 1 = two-pos w/ stops, 2 = two-pos w/o stops,
             3 = multiposition.
        """
        return self.send_cmd(f"AM{mode}")

    def get_np(self) -> str:
        """NP: display number of positions."""
        return self.send_cmd("NP")

    def set_np(self, n: int) -> str:
        """NPnn: set number of positions (2–96)."""
        return self.send_cmd(f"NP{n}")

    def get_offset(self) -> str:
        """SO: display offset value."""
        return self.send_cmd("SO")

    def set_offset(self, offset: int) -> str:
        """SOnn: set offset (1–96 – NP)."""
        return self.send_cmd(f"SO{offset}")

    def get_baud(self) -> str:
        """SB: display serial baud rate."""
        return self.send_cmd("SB")

    def set_baud(self, br: int) -> str:
        """
        SBnnnn: set baud to one of
        4800, 9600, 19200, 38400, 57600, 115200.
        """
        return self.send_cmd(f"SB{br}")

    # — Movement commands —

    def cw(self, pos: int = None) -> str:
        """
        CWnn: move in “positive” (up) direction to nn.
        CW: step up one (or toggle B→A in two-pos mode).
        """
        cmd = "CW" if pos is None else f"CW{pos}"
        # typically no response on CW
        return self.send_cmd(cmd, expect_response=False)

    def cc(self, pos: int = None) -> str:
        """
        CCnn: move in “negative” (down) direction to nn.
        CC: step down one (or toggle A→B in two-pos mode).
        """
        cmd = "CC" if pos is None else f"CC{pos}"
        return self.send_cmd(cmd, expect_response=False)

    def go(self, pos) -> str:
        """
        GOnn: move to position nn via shortest route (multiposition mode),
               or GO toggles (two-pos).
        """
        cmd = "GO" if pos is None else f"GO{pos}"
        return self.send_cmd(cmd, expect_response=False)

    def toggle(self) -> str:
        """TO: toggle to opposite position (two-pos only)."""
        return self.send_cmd("TO", expect_response=False)

    def timed_toggle(self) -> str:
        """TT: toggle, wait preset delay (DT), then return."""
        return self.send_cmd("TT", expect_response=False)

    # — Counters & timers —

    def get_counter(self) -> str:
        """CNT: display actuation counter."""
        return self.send_cmd("CNT")

    def reset_counter(self, value: int = 0) -> str:
        """CNTnnnnn: set counter (0–65535)."""
        return self.send_cmd(f"CNT{value}")

    def get_delay(self) -> str:
        """DT: display preset delay (ms)."""
        return self.send_cmd("DT")

    def set_delay(self, ms: int) -> str:
        """DTnnnnn: set delay time (0–65000 ms)."""
        return self.send_cmd(f"DT{ms}")

    def get_move_time(self) -> str:
        """TM: display time required by previous move (ms)."""
        return self.send_cmd("TM")

    # — Response & format —

    def get_response_mode(self) -> str:
        """IFM: display response mode."""
        return self.send_cmd("IFM")

    def set_response_mode(self, mode: int) -> str:
        """
        IFMn: response strings:
         0 = none
         1 = basic (on end of move)
         2 = extended (motor + error status)
        """
        return self.send_cmd(f"IFM{mode}")

    def get_format(self) -> str:
        """LG: display serial response format."""
        return self.send_cmd("LG")

    def set_format(self, fmt: int) -> str:
        """
        LGn: 0 = limited, 1 = extended (default).
        """
        return self.send_cmd(f"LG{fmt}")

    # — Utility commands —

    def learn_stops(self) -> None:
        """
        LRN: learn A & B mechanical stops (two-pos with stops only).
        No serial response.
        """
        self.send_cmd("LRN", expect_response=False)

    def set_motor(self, asm: str) -> str:
        """
        MAaaa: set motor assembly type:
        EMH | EMD | EMT.
        """
        return self.send_cmd(f"MA {asm}")

    def identify(self, id_: str) -> str:
        """
        IDa/n: set or display device ID (0–9, A–Z, * for broadcast).
        """
        return self.send_cmd(f"ID{id_}")

    def help(self) -> str:
        """?: display list of valid commands."""
        return self.send_cmd("?", expect_response=True)



if __name__ == "__main__":
    valve = ViciActuator(port="/dev/ttyUSB0", baud=9600)
    if valve.ser:
        # Configure for a 10-position valve in multiposition mode
        print(valve.set_mode(3))   # AM3 → multiposition
        print(valve.set_np(10))    # NP10 → 10 positions
        print(valve.home())        # HM → go to position 1
        # Move to port 5 (common plus port 5)
        valve.go(1)
        # Confirm position
        print(valve.get_position())  # CP → should return “Position is = 5”
        valve.close()
    else:
        print("Failed to open actuator serial port.")