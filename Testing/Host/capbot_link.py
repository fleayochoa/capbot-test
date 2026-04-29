#!/usr/bin/env python3
"""
capbot_link.py — Cliente Python del protocolo ESP32 <-> Jetson de Capbot.

Reemplaza a la Jetson: corre en cualquier PC (Windows/Linux/Mac), conecta al
puerto serie del ESP32 y habla el mismo framing COBS+CRC16-CCITT del firmware.

Uso rápido:
    pip install pyserial
    python capbot_link.py --list                  # lista puertos
    python capbot_link.py --port COM5             # REPL interactivo
    python capbot_link.py --port COM5 --no-hb     # sin heartbeat automático

Como librería:
    from capbot_link import CapbotLink
    link = CapbotLink("COM5", on_telemetry=print)
    link.start()
    link.send_motor(8000, 8000)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import struct
import sys
import threading
import time
from typing import Callable, Optional, Tuple

import serial
import serial.tools.list_ports

# ============================================================
# Protocolo (sincronizado con include/Config.h del firmware)
# ============================================================
BAUD_DEFAULT = 115200
DELIMITER = 0x00
MAX_PAYLOAD = 240


class MsgType:
    MOTOR_CMD = 0x10  # PC -> ESP32  (3x int16 LE)
    BRAKE_ON  = 0x11  # PC -> ESP32  (vacío)
    HEARTBEAT = 0x12  # PC -> ESP32  (vacío)
    TELEMETRY = 0x20  # ESP32 -> PC  (JSON)
    ESP_HELLO = 0x21  # ESP32 -> PC  (vacío)


_TYPE_NAME = {
    0x10: "MOTOR_CMD", 0x11: "BRAKE_ON", 0x12: "HEARTBEAT",
    0x20: "TELEMETRY", 0x21: "ESP_HELLO",
}


# ============================================================
# CRC16-CCITT  (poly 0x1021, init 0xFFFF, sin reflejar, sin XOR-out)
# Vector test: crc16_ccitt(b"123456789") == 0x29B1
# ============================================================
def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


# ============================================================
# COBS (Consistent Overhead Byte Stuffing)
# Réplica exacta del firmware: bloque 0xFF NO inserta cero.
# ============================================================
def cobs_encode(src: bytes) -> bytes:
    out = bytearray([0])   # placeholder del primer code
    code_idx = 0
    code = 1
    for b in src:
        if b == 0:
            out[code_idx] = code
            code_idx = len(out)
            out.append(0)
            code = 1
        else:
            out.append(b)
            code += 1
            if code == 0xFF:
                out[code_idx] = code
                code_idx = len(out)
                out.append(0)
                code = 1
    out[code_idx] = code
    return bytes(out)


def cobs_decode(src: bytes) -> Optional[bytes]:
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        code = src[i]
        if code == 0:
            return None  # cero embebido = stream inválido
        end = i + code
        if end > n:
            return None
        out.extend(src[i + 1:end])
        i = end
        if code < 0xFF and i < n:
            out.append(0)
    return bytes(out)


# ============================================================
# Pack / Unpack de tramas
# ============================================================
def pack_frame(msg_type: int, payload: bytes = b"") -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload {len(payload)}B > MAX {MAX_PAYLOAD}")
    header = bytes([msg_type & 0xFF, len(payload)])
    body = header + payload
    crc = crc16_ccitt(body)
    raw = body + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    return cobs_encode(raw) + bytes([DELIMITER])


def unpack_frame(encoded: bytes) -> Optional[Tuple[int, bytes]]:
    raw = cobs_decode(encoded)
    if raw is None or len(raw) < 4:
        return None
    msg_type = raw[0]
    declared = raw[1]
    if len(raw) != 2 + declared + 2:
        return None
    payload = raw[2:2 + declared]
    crc_recv = raw[2 + declared] | (raw[2 + declared + 1] << 8)
    if crc_recv != crc16_ccitt(raw[:2 + declared]):
        return None
    return msg_type, payload


# ============================================================
# Link asíncrono (reader thread + heartbeat thread)
# ============================================================
class CapbotLink:
    def __init__(
        self,
        port: str,
        baud: int = BAUD_DEFAULT,
        on_telemetry: Optional[Callable[[dict], None]] = None,
        on_hello: Optional[Callable[[], None]] = None,
        on_unknown: Optional[Callable[[int, bytes], None]] = None,
        heartbeat_period_ms: Optional[int] = 100,
        csv_path: Optional[str] = None,
    ):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.on_telemetry = on_telemetry
        self.on_hello = on_hello
        self.on_unknown = on_unknown
        self.heartbeat_period_ms = heartbeat_period_ms

        self._stop = threading.Event()
        self._tx_lock = threading.Lock()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True, name="capbot-rx")
        self._hb_thread = threading.Thread(target=self._hb_loop, daemon=True, name="capbot-hb")

        self.frames_rx = 0
        self.frames_dropped = 0

        # CSV logging
        self._csv_path = csv_path
        self._csv_file = None
        self._csv_writer = None
        self._csv_fields: Optional[list] = None
        self._csv_lock = threading.Lock()
        self._csv_rows = 0
        self._t0 = time.time()
        if csv_path:
            # append si existe; reusa headers si ya hay contenido
            exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
            self._csv_file = open(csv_path, "a", newline="", encoding="utf-8")
            if exists:
                # leemos header existente para mantener orden de columnas
                with open(csv_path, "r", encoding="utf-8") as f:
                    first = f.readline().strip()
                if first:
                    self._csv_fields = first.split(",")
                    self._csv_writer = csv.DictWriter(
                        self._csv_file, fieldnames=self._csv_fields,
                        extrasaction="ignore",
                    )

    # ---------- ciclo de vida ----------
    def start(self) -> "CapbotLink":
        self._rx_thread.start()
        if self.heartbeat_period_ms:
            self._hb_thread.start()
        return self

    def close(self):
        self._stop.set()
        try:
            self.ser.close()
        except Exception:
            pass
        with self._csv_lock:
            if self._csv_file:
                try:
                    self._csv_file.flush()
                    self._csv_file.close()
                except Exception:
                    pass
                self._csv_file = None
                self._csv_writer = None


    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    # ---------- API pública ----------
    def send_motor(self, left: int, right: int, aux: int = 0):
        # int16 LE; clamp por seguridad para no romper struct
        l = max(-32768, min(32767, int(left)))
        r = max(-32768, min(32767, int(right)))
        a = max(-32768, min(32767, int(aux)))
        self._send(MsgType.MOTOR_CMD, struct.pack("<hhh", l, r, a))

    def send_brake(self):
        self._send(MsgType.BRAKE_ON, b"")

    def send_heartbeat(self):
        self._send(MsgType.HEARTBEAT, b"")

    # ---------- internos ----------
    def _send(self, msg_type: int, payload: bytes):
        frame = pack_frame(msg_type, payload)
        with self._tx_lock:
            self.ser.write(frame)

    def _rx_loop(self):
        buf = bytearray()
        while not self._stop.is_set():
            try:
                chunk = self.ser.read(256)
            except (serial.SerialException, OSError):
                break
            if not chunk:
                continue
            for b in chunk:
                if b == DELIMITER:
                    if buf:
                        result = unpack_frame(bytes(buf))
                        if result is None:
                            self.frames_dropped += 1
                        else:
                            self.frames_rx += 1
                            self._dispatch(*result)
                        buf.clear()
                else:
                    if len(buf) > 4 * MAX_PAYLOAD:   # protección anti-runaway
                        buf.clear()
                        self.frames_dropped += 1
                    else:
                        buf.append(b)

    def _dispatch(self, msg_type: int, payload: bytes):
        if msg_type == MsgType.TELEMETRY:
            try:
                obj = json.loads(payload.decode("utf-8", errors="replace"))
            except Exception:
                obj = {"_raw_hex": payload.hex()}
            self._log_csv(obj)
            if self.on_telemetry:
                self.on_telemetry(obj)
        elif msg_type == MsgType.ESP_HELLO:
            if self.on_hello:
                self.on_hello()
        else:
            if self.on_unknown:
                self.on_unknown(msg_type, payload)

    def _log_csv(self, obj: dict):
        if not self._csv_file or not isinstance(obj, dict):
            return
        row = {"_ts": f"{time.time():.6f}",
               "_t_rel": f"{time.time() - self._t0:.6f}",
               **{k: obj[k] for k in obj}}
        with self._csv_lock:
            if self._csv_writer is None:
                # primer frame: fija columnas a partir de las keys vistas
                self._csv_fields = list(row.keys())
                self._csv_writer = csv.DictWriter(
                    self._csv_file, fieldnames=self._csv_fields,
                    extrasaction="ignore",
                )
                self._csv_writer.writeheader()
            try:
                self._csv_writer.writerow(row)
                self._csv_rows += 1
                # flush periódico para no perder datos si se mata el proceso
                if self._csv_rows % 20 == 0:
                    self._csv_file.flush()
            except Exception:
                pass

    def _hb_loop(self):
        period = self.heartbeat_period_ms / 1000.0
        # esperamos a que el puerto esté abierto
        while not self._stop.wait(period):
            try:
                self.send_heartbeat()
            except Exception:
                break


# ============================================================
# CLI / REPL
# ============================================================
HELP = """\
Comandos:
  m <L> <R> [A]    MOTOR_CMD  (int16, rango ±32767)
  b                BRAKE_ON
  h                HEARTBEAT manual
  t on|off         imprimir telemetría (default: on)
  s                stats (frames rx / dropped / csv rows)
  q                salir
  ?                ayuda
"""


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("(sin puertos serie detectados)")
        return
    for p in ports:
        print(f"  {p.device:12s}  {p.description}")


def repl(port: str, baud: int, hb_ms: Optional[int], csv_path: Optional[str]):
    print_telem = {"on": True}
    last_telem = {"obj": None, "t": 0.0}

    def on_telem(obj):
        last_telem["obj"] = obj
        last_telem["t"] = time.time()
        if print_telem["on"]:
            sys.stdout.write(f"\r[TELEM] {json.dumps(obj, separators=(',', ':'))}\n> ")
            sys.stdout.flush()

    def on_hello():
        sys.stdout.write("\r[HELLO] ESP32 booted\n> ")
        sys.stdout.flush()

    def on_unknown(t, p):
        sys.stdout.write(f"\r[?] type=0x{t:02X} len={len(p)} hex={p.hex()}\n> ")
        sys.stdout.flush()

    try:
        link = CapbotLink(port, baud,
                          on_telemetry=on_telem,
                          on_hello=on_hello,
                          on_unknown=on_unknown,
                          heartbeat_period_ms=hb_ms,
                          csv_path=csv_path).start()
    except serial.SerialException as e:
        print(f"ERROR abriendo {port}: {e}", file=sys.stderr)
        sys.exit(1)

    if csv_path:
        print(f"CSV log: {csv_path}")

    print(f"Conectado a {port} @ {baud} baud. Heartbeat: "
          f"{'cada ' + str(hb_ms) + ' ms' if hb_ms else 'OFF'}")
    print(HELP)

    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                continue
            cmd, *args = line.split()
            cmd = cmd.lower()
            try:
                if cmd in ("q", "quit", "exit"):
                    break
                elif cmd in ("?", "help"):
                    print(HELP)
                elif cmd == "m":
                    if len(args) < 2:
                        print("uso: m <L> <R> [A]")
                        continue
                    L = int(args[0]); R = int(args[1])
                    A = int(args[2]) if len(args) >= 3 else 0
                    link.send_motor(L, R, A)
                elif cmd == "b":
                    link.send_brake()
                elif cmd == "h":
                    link.send_heartbeat()
                elif cmd == "t":
                    if args and args[0] in ("on", "off"):
                        print_telem["on"] = (args[0] == "on")
                    else:
                        print_telem["on"] = not print_telem["on"]
                    print(f"telemetry print: {'on' if print_telem['on'] else 'off'}")
                elif cmd == "s":
                    age = time.time() - last_telem["t"] if last_telem["t"] else None
                    print(f"rx={link.frames_rx} dropped={link.frames_dropped} "
                          f"csv_rows={link._csv_rows} "
                          f"last_telem={'%.2fs' % age if age else 'never'}")
                else:
                    print(f"comando desconocido: {cmd!r}  ('?' para ayuda)")
            except Exception as e:
                print(f"err: {e}")
    finally:
        link.close()
        print("\nbye.")


def main():
    ap = argparse.ArgumentParser(description="Capbot ESP32 link (PC <-> firmware).")
    ap.add_argument("--port", "-p", help="puerto serie (ej. COM5, /dev/ttyUSB0)")
    ap.add_argument("--baud", "-b", type=int, default=BAUD_DEFAULT)
    ap.add_argument("--no-hb", action="store_true",
                    help="desactiva heartbeat automático (el ESP frenará a los 200 ms)")
    ap.add_argument("--hb-ms", type=int, default=100,
                    help="periodo de heartbeat en ms (default 100)")
    ap.add_argument("--list", "-l", action="store_true", help="lista puertos y sale")
    ap.add_argument("--csv", default=None,
                    help="archivo CSV donde registrar la telemetría (append). "
                         "Si se pasa 'auto', genera capbot_<timestamp>.csv")
    args = ap.parse_args()

    if args.list:
        list_ports()
        return
    if not args.port:
        print("Falta --port. Puertos disponibles:")
        list_ports()
        sys.exit(2)

    csv_path = args.csv
    if csv_path == "auto":
        csv_path = time.strftime("capbot_%Y%m%d_%H%M%S.csv")

    hb = None if args.no_hb else args.hb_ms
    repl(args.port, args.baud, hb, csv_path)


# ============================================================
# Self-test mínimo (sin hardware): pack/unpack round-trip
# ============================================================
def _selftest():
    assert crc16_ccitt(b"123456789") == 0x29B1, "CRC vector falla"
    for payload in [b"", b"\x00", b"\x00\x00\x00", b"hola mundo",
                    bytes(range(256))[:MAX_PAYLOAD]]:
        f = pack_frame(MsgType.TELEMETRY, payload)
        assert f.endswith(b"\x00") and f.count(b"\x00") == 1, "delimitador único"
        t, p = unpack_frame(f[:-1])
        assert t == MsgType.TELEMETRY and p == payload, "round-trip falla"
    # MOTOR_CMD round-trip
    f = pack_frame(MsgType.MOTOR_CMD, struct.pack("<hhh", -1234, 5678, 0))
    t, p = unpack_frame(f[:-1])
    assert t == MsgType.MOTOR_CMD and struct.unpack("<hhh", p) == (-1234, 5678, 0)
    print("selftest OK")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        _selftest()
    else:
        main()
