#include <Arduino.h>

// Motor Izquierdo (L)
#define PIN_PWM_L 18   // En1
#define PIN_IN1 15   // In1
#define PIN_IN2 12   // In2

// Motor Derecho (R)
#define PIN_PWM_R 5   // En2
#define PIN_IN3 13   // In3
#define PIN_IN4 14   // In4

// Encoders 1
#define PIN_ENCODER1 25
#define PIN_ENCODER1_Q 23

// Encoders 2
#define PIN_ENCODER2 27
#define PIN_ENCODER2_Q 26


const int FRECUENCIA_PWM = 2000; // 2 kHz
const int RESOLUCION_PWM = 8;    // 8 bits
const int CANAL_PWM_L = 1;     
const int CANAL_PWM_R = 0;       

void update_motor(float vel, char state, int PWM_channel, int pinIn1, int pinIn2) {
    
  int dutyCycle = (int)(vel * 255.0 );
    
    if (dutyCycle > 255) dutyCycle = 255;
    if (dutyCycle < 0) dutyCycle = 0;
    ledcWrite(PWM_channel, dutyCycle);
    // 2. Ajustar los pines digitales según el caracter (Ejemplo: Adelante, Atrás, Stop)
    Serial.print(state);
    Serial.print(" ");
    Serial.println(PWM_channel);
    switch (state) {
        case 'F': // Forward
            digitalWrite(pinIn1, HIGH);
            digitalWrite(pinIn2, LOW);
            break;
        case 'R': // Reverse
            digitalWrite(pinIn1, LOW);
            digitalWrite(pinIn2, HIGH);
            break;
        case 'S': // Stop
            digitalWrite(pinIn1, LOW);
            digitalWrite(pinIn2, LOW);
            // Opcional: forzar PWM a 0 cuando es Stop
            //ledcWrite(PWM_channel, 0); 
            break;
        default:
            break;
    }
}

// Función para decodificar el mensaje (se mantiene igual)
void decode_message(const char* mensaje) {
    float duty1 = 0.0;
    char state1 = '\0';
    float duty2 = 0.0;
    char state2 = '\0';

    int elementosLeidos = sscanf(mensaje, "L:%f:%c,R:%f:%c", &duty1, &state1, &duty2, &state2);

    if (elementosLeidos == 4) {
        update_motor(duty1, state1, CANAL_PWM_L, PIN_IN1, PIN_IN2);
        update_motor(duty2, state2, CANAL_PWM_R, PIN_IN3, PIN_IN4);
        /*Serial.print(state1);
        Serial.print(" ");
        Serial.println(state2);
        Serial.print(duty1);
        Serial.print(" ");
        Serial.println(duty2);
        Serial.print(CANAL_PWM_L);
        Serial.print(" ");
        Serial.println(CANAL_PWM_R);
        Serial.print(PIN_IN1);
        Serial.print(" ");
        Serial.println(PIN_IN2);
        Serial.print(PIN_IN3);
        Serial.print(" ");
        Serial.println(PIN_IN4);*/
    }
    else {
        Serial.println("Error");
    }
}

void setup() {
    // Inicializamos el puerto serie 0 para ver los resultados en la PC
    Serial.begin(115200);
    
    // Inicializamos Serial2 para recibir los datos del otro dispositivo
    // Formato: baudios, configuración de bits, pin RX, pin TX
    Serial2.begin(115200);
    pinMode(PIN_IN1, OUTPUT);
    pinMode(PIN_IN2, OUTPUT);
    pinMode(PIN_IN3, OUTPUT);
    pinMode(PIN_IN4, OUTPUT);

    ledcSetup(CANAL_PWM_L, FRECUENCIA_PWM, RESOLUCION_PWM);
    ledcAttachPin(PIN_PWM_L, CANAL_PWM_L);
    ledcSetup(CANAL_PWM_R, FRECUENCIA_PWM, RESOLUCION_PWM);
    ledcAttachPin(PIN_PWM_R, CANAL_PWM_R);

    update_motor(0.0, 'S', CANAL_PWM_L, PIN_IN1, PIN_IN2);
    update_motor(0.0, 'S', CANAL_PWM_R, PIN_IN3, PIN_IN4);

    delay(1000); 
    Serial.println("\nESP32 lista. Esperando datos por el Serial2 (Pines RX: 16, TX: 17)...");
}

void loop() {
    // Comprobamos si ha llegado algún dato al Serial2
    if (Serial2.available() > 0) {
        // Leemos todo el mensaje hasta encontrar un salto de línea ('\n')
        String received_message = Serial2.readStringUntil('\n');
        received_message.trim();

        // Solo procesamos si el mensaje tiene contenido después de limpiarlo
        if (received_message.length() > 0) {
            decode_message(received_message.c_str());
        }
    }

}