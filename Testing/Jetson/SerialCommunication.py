import serial
import time

# En la Jetson Nano, los pines 8 y 10 corresponden a /dev/ttyTHS1
serial_port = serial.Serial(
    port="/dev/ttyTHS1",
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
)

try:
    print("Enviando mensaje al ESP32...")
    while True:
        # Enviar datos
        serial_port.write("Hola ESP32\n".encode())
        
        # Leer si hay respuesta
        if serial_port.in_waiting > 0:
            data = serial_port.readline().decode('utf-8').strip()
            print(f"Recibido del ESP32: {data}")
            
        time.sleep(1)

except KeyboardInterrupt:
    print("\nFinalizando...")
finally:
    serial_port.close()