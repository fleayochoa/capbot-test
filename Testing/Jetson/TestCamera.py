import cv2

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1280,
    capture_height=720,
    display_width=640,
    display_height=360,
    framerate=30,
    flip_method=0,
):
    """
    Construye el string del pipeline de GStreamer para cv2.VideoCapture
    """
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )

def test_camera():
    print("Iniciando cámara CSI...")
    # Se inicializa VideoCapture usando el backend de GStreamer
    cap = cv2.VideoCapture(gstreamer_pipeline(flip_method=0), cv2.CAP_GSTREAMER)

    if cap.isOpened():
        window_handle = cv2.namedWindow("Test Camara CSI", cv2.WINDOW_AUTOSIZE)
        while cv2.getWindowProperty("Test Camara CSI", 0) >= 0:
            ret, img = cap.read()
            if not ret:
                print("No se pudo recibir el frame.")
                break
            
            cv2.imshow("Test Camara CSI", img)
            
            # Presiona la tecla 'ESC' para salir
            keyCode = cv2.waitKey(30) & 0xFF
            if keyCode == 27:
                break
                
        cap.release()
        cv2.destroyAllWindows()
    else:
        print("Error: No se pudo abrir la cámara. Verifica la conexión o procesos en segundo plano.")

if __name__ == "__main__":
    test_camera()