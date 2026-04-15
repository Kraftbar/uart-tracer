#!/usr/bin/env python3

import re
import time
from datetime import datetime
from pathlib import Path

import serial


PORT = "/dev/ttyUSB0"
BAUD = 115200
TIMEOUT = 1.0
LOG_FILE = Path.cwd() / "esp8266.log"
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CONTROL_NAMES = {
    0x00: "NUL",
    0x01: "SOH",
    0x02: "STX",
    0x03: "ETX",
    0x04: "EOT",
    0x05: "ENQ",
    0x06: "ACK",
    0x07: "BEL",
    0x08: "BS",
    0x0B: "VT",
    0x0C: "FF",
    0x0E: "SO",
    0x0F: "SI",
    0x10: "DLE",
    0x11: "DC1",
    0x12: "DC2",
    0x13: "DC3",
    0x14: "DC4",
    0x15: "NAK",
    0x16: "SYN",
    0x17: "ETB",
    0x18: "CAN",
    0x19: "EM",
    0x1A: "SUB",
    0x1B: "ESC",
    0x1C: "FS",
    0x1D: "GS",
    0x1E: "RS",
    0x1F: "US",
    0x7F: "DEL",
}


def timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def control_token(byte):
    return f"<{CONTROL_NAMES.get(byte, f'{byte:02X}')}>"


def render_text_bytes(data):
    text = data.decode("utf-8", errors="surrogateescape")
    rendered = []
    index = 0
    while index < len(text):
        char = text[index]
        codepoint = ord(char)
        if char == "\x1b" and index + 1 < len(text) and text[index + 1] == "[":
            end = index + 2
            while end < len(text):
                terminator = ord(text[end])
                if 0x40 <= terminator <= 0x7E:
                    rendered.append(text[index : end + 1])
                    index = end + 1
                    break
                end += 1
            else:
                rendered.append(control_token(codepoint))
                index += 1
        elif 0xDC80 <= codepoint <= 0xDCFF:
            rendered.append(f"<{codepoint - 0xDC00:02X}>")
            index += 1
        elif char == "\t":
            rendered.append("\t")
            index += 1
        elif codepoint < 0x20 or codepoint == 0x7F:
            rendered.append(control_token(codepoint))
            index += 1
        else:
            rendered.append(char)
            index += 1
    return "".join(rendered)


def sanitize_log_text_line(line):
    return ANSI_ESCAPE_RE.sub("", line)


class TextStreamFormatter:
    def __init__(self):
        self.pending = bytearray()

    def feed(self, data):
        self.pending.extend(data)
        lines = []
        while True:
            line, terminator_len = self._extract_line()
            if line is None:
                return lines
            lines.append(f"({timestamp()}) {render_text_bytes(line)}")
            del self.pending[: len(line) + terminator_len]

    def flush(self):
        if not self.pending:
            return []
        tail = bytes(self.pending)
        self.pending.clear()
        return [f"({timestamp()}) {render_text_bytes(tail)}"]

    def _extract_line(self):
        for index, byte in enumerate(self.pending):
            if byte not in (0x0A, 0x0D):
                continue
            terminator_len = 1
            if byte == 0x0D and index + 1 < len(self.pending) and self.pending[index + 1] == 0x0A:
                terminator_len = 2
            return bytes(self.pending[:index]), terminator_len
        return None, 0


def emit(lines, log_handle):
    for line in lines:
        print(line, flush=True)
        print(sanitize_log_text_line(line), file=log_handle, flush=True)


def main():
    formatter = TextStreamFormatter()

    try:
        with open(LOG_FILE, "w", encoding="utf-8") as log_handle:
            with serial.Serial(port=None, baudrate=BAUD, timeout=TIMEOUT) as ser:
                ser.dtr = False
                ser.rts = False
                ser.port = PORT
                ser.open()
                print(f"Opened {PORT} @ {BAUD} baud, logging to {LOG_FILE}", flush=True)
                while True:
                    waiting = ser.in_waiting
                    if not waiting:
                        time.sleep(0.05)
                        continue
                    data = ser.read(waiting)
                    if data:
                        emit(formatter.feed(data), log_handle)
    except KeyboardInterrupt:
        pass
    except serial.SerialException as exc:
        print(f"Failed to open/read {PORT}: {exc}", flush=True)
        return 1
    finally:
        if "log_handle" in locals() and not log_handle.closed:
            emit(formatter.flush(), log_handle)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
