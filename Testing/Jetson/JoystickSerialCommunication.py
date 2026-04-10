import threading
import time

import serial
from inputs import get_gamepad


state = {
    "left":  {"raw": 0, "duty": 0.0, "direction": "STOP"},
    "right": {"raw": 0, "duty": 0.0, "direction": "STOP"},
}
state_lock = threading.Lock()

# En la Jetson Nano, los pines 8 y 10 corresponden a /dev/ttyTHS1
serial_port = serial.Serial(
    port="/dev/ttyTHS1",
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
)

# Rango máximo del eje analógico (estándar HID)
AXIS_MAX = 32767
AXIS_MIN = -32768

# Deadzone asimétrica: zona muerta entre -1500 y +1500
DEADZONE_HIGH = 1500   # umbral para la mitad negativa (FORWARD)
DEADZONE_LOW  = 1500   # umbral para la mitad positiva (REVERSE)

# Pausa del hilo de lectura en ms
POLL_INTERVAL_MS = 20 


def raw_to_duty_and_direction(raw: int) -> tuple[float, str]:
    """
    Convierte el valor crudo del eje en (duty_cycle, dirección).
    """
    if raw < -DEADZONE_HIGH:
        # Mapear [-DEADZONE_HIGH .. AXIS_MIN] → [0 .. 1]
        duty = (abs(raw) - DEADZONE_HIGH) / (abs(AXIS_MIN) - DEADZONE_HIGH)
        duty = max(0.0, min(1.0, duty))
        return duty, "F"

    elif raw > DEADZONE_LOW:
        # Mapear [DEADZONE_LOW .. AXIS_MAX] → [0 .. 1]
        duty = (raw - DEADZONE_LOW) / (AXIS_MAX - DEADZONE_LOW)
        duty = max(0.0, min(1.0, duty))
        return duty, "R"

    else:
        return 0.0, "S"


# ──────────────────────────────────────────────
# Hilo 1: lectura de eventos del joystick
# ──────────────────────────────────────────────
def read_joystick():
    """
    Lee eventos del gamepad y actualiza el estado compartido.
    """
    print("[Joystick] Hilo de lectura iniciado. Esperando eventos...")
    poll_interval = POLL_INTERVAL_MS / 1000.0

    while True:
        try:
            events = get_gamepad()          
            for event in events:
                if event.ev_type != "Absolute":
                    continue

                raw = event.state

                with state_lock:
                    if event.code == "ABS_Y":          # Palanca izquierda Y
                        duty, direction = raw_to_duty_and_direction(raw)
                        state["left"]["raw"] = raw
                        state["left"]["duty"] = duty
                        state["left"]["direction"] = direction

                    elif event.code == "ABS_RZ":       # Palanca derecha Y
                        duty, direction = raw_to_duty_and_direction(raw)
                        state["right"]["raw"] = raw
                        state["right"]["duty"] = duty
                        state["right"]["direction"] = direction

            # Pausa: cede el hilo para no saturar la CPU
            time.sleep(poll_interval)

        except Exception as e:
            print(f"[Joystick] Error: {e}")
            time.sleep(0.5)


# ──────────────────────────────────────────────
# Hilo 2: reporte cada 100 ms
# ──────────────────────────────────────────────
def report_loop(interval_ms: int = 100):
    """Envia por serial el resumen del estado cada `interval_ms` milisegundos."""
    interval_s = interval_ms / 1000.0
    print(f"[Reporte] Iniciando reporte cada {interval_ms} ms...\n")

    while True:
        time.sleep(interval_s)

        with state_lock:
            l = state["left"]
            r = state["right"]

        # Timestamp con formato HH:MM:SS.mmm
        timestamp = time.strftime("%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}"

        print(
            f"[{timestamp}] "
            f"IZQUIERDA → duty={l['duty']:.3f}  dir={l['direction']:<7}  "
            f"| "
            f"DERECHA   → duty={r['duty']:.3f}  dir={r['direction']:<7}"
        )

        msg = f"L:{l['duty']:.2f}:{l['direction']},R:{r['duty']:.2f}:{r['direction']}\n"
        
        if serial_port.is_open:
            serial_port.write(msg.encode("utf-8"))  # Envia por serial
        else:
            print("[Reporte] Error: Puerto serial no está abierto.")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("  Joystick → Duty Cycle Controller")
    print("  Palanca ARRIBA : FORWARD  (duty 0→1)")
    print("  Palanca ABAJO  : REVERSE  (duty 0→1)")
    print(f"  Zona muerta    : -{DEADZONE_HIGH} .. +{DEADZONE_LOW}  → STOP (duty 0)")
    print(f"  Poll joystick  : cada {POLL_INTERVAL_MS} ms  ({1000//POLL_INTERVAL_MS} Hz)")
    print("  Presiona Ctrl+C para salir")
    print("=" * 65)

    # Hilo de lectura del joystick (daemon → muere con el programa)
    t_joy = threading.Thread(target=read_joystick, daemon=True)
    t_joy.start()

    # Hilo de reporte (daemon)
    t_report = threading.Thread(target=report_loop, args=(100,), daemon=True)
    t_report.start()

    # Mantener el programa vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Saliendo...")