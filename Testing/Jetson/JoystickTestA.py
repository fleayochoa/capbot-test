import time
from inputs import get_gamepad
import math

def leer_mando():
    print("Leyendo mando... (Ctrl+C para salir)")
    while True:
        eventos = get_gamepad()
        for evento in eventos:
            # Filtrar solo ejes del joystick y botones
            if evento.ev_type == "Absolute":
                print(f"Eje:    {evento.code:20s} | Valor: {evento.state}")
            elif evento.ev_type == "Key":
                print(f"Botón:  {evento.code:20s} | {'PRESIONADO' if evento.state else 'SOLTADO'}")
        
        #time.sleep(0.1)  # Pequeña pausa para evitar saturar la salida

if __name__ == "__main__":
    leer_mando()
