#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>

// Crear el objeto del sensor
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);

// Aquí almacenaremos los offsets
adafruit_bno055_offsets_t misOffsets;

// Bandera para no guardar los offsets múltiples veces
bool calibracionGuardada = false;

void setup() {
  Serial.begin(115200);
  
  if (!bno.begin()) {
    Serial.print("No se detectó el BNO055. Revisa las conexiones.");
    while (1);
  }
  
  delay(1000);
  bno.setExtCrystalUse(true);
}

void loop() {
  // 1. Variables para leer el estado (0 a 3)
  uint8_t system, gyro, accel, mag;
  system = gyro = accel = mag = 0;
  
  // 2. Obtener el estado actual de la calibración
  bno.getCalibration(&system, &gyro, &accel, &mag);
  
  // 3. Verificar si el sistema alcanzó el estado 3
  // (Recomendación: exigir que gyro, accel y mag también sean 3 para un perfil perfecto)
  if (system == 3 && gyro == 3 && accel == 3) {
    
    // 4. Extraer los offsets y guardarlos en la estructura
    if (bno.getSensorOffsets(misOffsets)) {
      Serial.println("¡Sensor completamente calibrado!");
      Serial.println("Offsets capturados exitosamente.");
      
      // Mostrar algunos datos a modo de ejemplo
      Serial.print("Offset Acelerómetro X: "); Serial.println(misOffsets.accel_offset_x);
      Serial.print("Offset Acelerómetro Y: "); Serial.println(misOffsets.accel_offset_y);
      Serial.print("Offset Acelerómetro Z: "); Serial.println(misOffsets.accel_offset_z);
        Serial.print("Offset Giroscopio X: "); Serial.println(misOffsets.gyro_offset_x);
        Serial.print("Offset Giroscopio Y: "); Serial.println(misOffsets.gyro_offset_y);
        Serial.print("Offset Giroscopio Z: "); Serial.println(misOffsets.gyro_offset_z);
        Serial.print("Offset Magnetómetro X: "); Serial.println(misOffsets.mag_offset_x);
        Serial.print("Offset Magnetómetro Y: "); Serial.println(misOffsets.mag_offset_y);
        Serial.print("Offset Magnetómetro Z: "); Serial.println(misOffsets.mag_offset_z);
      Serial.print("Radio del Magnetómetro: "); Serial.println(misOffsets.mag_radius);
      Serial.print("Radio del Acelerómetro: "); Serial.println(misOffsets.accel_radius);
      Serial.print("Estado de calibracion magnetómetro: "); Serial.println(mag);
      
      calibracionGuardada = true; // Evitar que se repita en el próximo ciclo
    }
  }

  // Tu código normal del IMU iría aquí (leer Euler, Quaternions, etc.)
  Serial.print("Calibración del sistema: "); Serial.print(system);
  Serial.print(" | Calibración del giroscopio: "); Serial.print(gyro);
  Serial.print(" | Calibración del acelerómetro: "); Serial.print(accel);
  Serial.print(" | Calibración del magnetómetro: "); Serial.println(mag);
  delay(100);
}