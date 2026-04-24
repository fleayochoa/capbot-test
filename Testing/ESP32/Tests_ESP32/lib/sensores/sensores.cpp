#include "sensores.h"
#define ENC_DER_A 27
#define ENC_DER_B 26
#define ENC_IZQ_A 33
#define ENC_IZQ_B 32

#define DIAMETRO_RUEDA_M 0.067f
#define CPR 910

#define TOF1_XSHUT 23
#define TOF2_XSHUT 25

bool tof1_ok = true;
bool tof2_ok = true;
bool bno_ok = true;

// =========================
// Objetos globales
// =========================
ESP32Encoder encoder_der;
ESP32Encoder encoder_izq;
Adafruit_VL53L0X tof1;
Adafruit_VL53L0X tof2;
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28, &Wire);

// =========================
// Muestreo
// =========================
const unsigned long TS_MS = 20;
const unsigned long DEBUG_MS = 150;
unsigned long tLoop = 0;
unsigned long tDebug = 0;

// =========================
// Variables medidas
// =========================
float velocidadDer = 0.0f;
float velocidadIzq = 0.0f;
float velocidadMedida = 0.0f;
float orientacionMedida = 0.0f;
float velAngularMedida = 0.0f;
float posX = 0.0f;
float posY = 0.0f;

float* distanciasMedidas = new float[2];

// =========================
// Variables encoder
// =========================
long prevCountDer = 0;
long prevCountIzq = 0;
unsigned long prevVelMs = 0;
unsigned long prevPosMs = 0;

// =========================
// Sensor distancia
// =========================
void distancia() {
  VL53L0X_RangingMeasurementData_t measure1, measure2;
  tof1.rangingTest(&measure1, false);
  tof2.rangingTest(&measure2, false);

  if (measure1.RangeStatus == 0 || measure1.RangeStatus == 1) {
    distanciasMedidas[0] = measure1.RangeMilliMeter * 0.1f;
  } else {
    distanciasMedidas[0] = -1.0f;
  }
  
  if (measure2.RangeStatus == 0 || measure2.RangeStatus == 1) {
    distanciasMedidas[1] = measure2.RangeMilliMeter * 0.1f;
  } else {
    distanciasMedidas[1] = -1.0f;
  }
}

// =========================
// Encoders y velocidad
// =========================
void resetEncoders() {
  encoder_der.clearCount();
  encoder_izq.clearCount();
  prevCountDer = 0;
  prevCountIzq = 0;
  prevVelMs = millis();
}

void actualizarVelocidad() {
  unsigned long now = millis();
  float dt = (now - prevVelMs) * 0.001f;
  if (dt <= 0.0f) return;

  long countDer = encoder_der.getCount();
  long countIzq = encoder_izq.getCount();

  long deltaDer = countDer - prevCountDer;
  long deltaIzq = countIzq - prevCountIzq;

  float revDer = (float)deltaDer / CPR;
  float revIzq = (float)deltaIzq / CPR;

  velocidadDer = (PI * DIAMETRO_RUEDA_M * revDer) / dt;
  velocidadIzq = -(PI * DIAMETRO_RUEDA_M * revIzq) / dt;
  velocidadMedida = 0.5f * (velocidadDer + velocidadIzq);

  prevCountDer = countDer;
  prevCountIzq = countIzq;
  prevVelMs = now;
}

void actualizarPos() {
  unsigned long now = millis();
  float dt = (now - prevPosMs) * 0.001f;
  if (dt <= 0.0f) return;

  posX = posX + velocidadMedida * cos(orientacionMedida * PI / 180.0f) * dt;
  posY = posY + velocidadMedida * sin(orientacionMedida * PI / 180.0f) * dt;
  prevPosMs = now;
}

void orientacionYomega() {
    sensors_event_t orientationData, gyroData;
    bno.getEvent(&orientationData, Adafruit_BNO055::VECTOR_EULER);
    orientacionMedida = orientationData.orientation.x;
    bno.getEvent(&gyroData, Adafruit_BNO055::VECTOR_GYROSCOPE);
    velAngularMedida = gyroData.gyro.z;
}

// =========================
// Mediciones
// =========================
Estado actualizarMediciones() {
  actualizarVelocidad();
  distancia();
  actualizarPos();
  orientacionYomega();
  
  estadoMedido.x = posX;
  estadoMedido.y = posY;
  estadoMedido.theta = orientacionMedida;
  estadoMedido.v = velocidadMedida;
  estadoMedido.omega = velAngularMedida;
  estadoMedido.dist1 = distanciasMedidas[0];
  estadoMedido.dist2 = distanciasMedidas[1];

  return estadoMedido;
}
// =========================
// Debug
// =========================
void imprimirDebug() {
  Serial.print("Pos X: ");
  Serial.print(estadoMedido.x);
  Serial.print("  Pos Y: ");
  Serial.print(estadoMedido.y);
  Serial.print("  Theta: ");
  Serial.print(estadoMedido.theta);
  Serial.print("  V: ");
  Serial.print(estadoMedido.v);
  Serial.print("  Omega: ");
  Serial.print(estadoMedido.omega);

  Serial.print("  Dist: ");
  Serial.print(distanciasMedidas[0]);
  Serial.print(", ");
  Serial.println(distanciasMedidas[1]);
}

// =========================
// Setup
// =========================
void sensorSetup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  Wire.setClock(100000);

  ESP32Encoder::useInternalWeakPullResistors = puType::up;

  encoder_der.attachFullQuad(ENC_DER_A, ENC_DER_B);
  encoder_izq.attachFullQuad(ENC_IZQ_A, ENC_IZQ_B);

  resetEncoders();

  // if (!vl53.begin()) {
  //   Serial.println("VL53L0X no detectado");
  // }

  if (!bno.begin()) {
    Serial.println("BNO055 no detectado");
    bno_ok = false;
  }
  // 1. Keep both in reset
  pinMode(TOF1_XSHUT, OUTPUT);
  pinMode(TOF2_XSHUT, OUTPUT);
  digitalWrite(TOF1_XSHUT, LOW);
  digitalWrite(TOF2_XSHUT, LOW);
  delay(10);

  // 2. Wake up TOF 1
  digitalWrite(TOF1_XSHUT, HIGH);
  delay(10);

  if(!tof1.begin(0x30)) { 
    Serial.println("Failed to boot first VL53L0X");
    tof1_ok = false;
  }

  // 3. Wake up TOF 2
  digitalWrite(TOF2_XSHUT, HIGH);
  delay(10);
  if (!tof2.begin(0x29)) { 
    Serial.println("Failed to boot second VL53L0X");
    tof2_ok = false;
  }

  tLoop = millis();
  tDebug = millis();
}
