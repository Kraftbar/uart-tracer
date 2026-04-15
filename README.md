# uart-tracer

Small UART log tracer for local serial debugging.

Current behavior:

- reads from `/dev/ttyUSB0`
- uses `115200` baud
- keeps `DTR` and `RTS` off
- prints live output to stdout
- writes `esp8266.log` in the directory where it is run

Usage:

```bash
python3 serial_read_min.py
```
