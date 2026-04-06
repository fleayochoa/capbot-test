import pygame
import sys

def inicializar():
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No se detectó ningún mando.")
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(f"Mando detectado: {joystick.get_name()}")
    print(f"  Ejes:    {joystick.get_numaxes()}")
    print(f"  Botones: {joystick.get_numbuttons()}")
    return joystick

def leer_mando():
    joystick = inicializar()
    clock = pygame.time.Clock()

    # Umbral para ignorar ruido en los ejes (dead zone)
    DEAD_ZONE = 0.1

    print("\nLeyendo mando... (Ctrl+C para salir)\n")
    try:
        while True:
            pygame.event.pump()  # Actualiza el estado interno

            # --- Leer ejes del joystick ---
            for i in range(joystick.get_numaxes()):
                valor = joystick.get_axis(i)
                if abs(valor) > DEAD_ZONE:  # Ignorar valores pequeños (ruido)
                    print(f"Eje {i}: {valor:+.3f}")

            # --- Leer botones ---
            for i in range(joystick.get_numbuttons()):
                if joystick.get_button(i):
                    print(f"Botón {i}: PRESIONADO")

            # --- Leer D-Pad (hat) si existe ---
            for i in range(joystick.get_numhats()):
                hat = joystick.get_hat(i)
                if hat != (0, 0):
                    print(f"D-Pad {i}: {hat}")

            clock.tick(30)  # 30 lecturas por segundo

    except KeyboardInterrupt:
        print("\nSaliendo...")
        pygame.quit()

if __name__ == "__main__":
    leer_mando()