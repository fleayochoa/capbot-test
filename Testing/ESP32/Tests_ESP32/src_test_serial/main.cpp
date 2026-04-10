#include <Arduino.h>

void setup() {
  // Serial para monitorizar en la PC
  Serial.begin(115200); 
  // Serial2 para la Jetson Nano (TX=17, RX=16 por defecto en muchos modelos)
  Serial2.begin(115200); 
  Serial.println("ESP32 listo para recibir datos de Jetson...");
}

void loop() {
  if (Serial2.available()) {
    String data = Serial2.readStringUntil('\n');
    Serial.println("J: " + data);
    
    // Responder a la Jetson
    //Serial2.println("Mensaje recibido, Jetson!");
  }
  delay(50); // Pequeña pausa para evitar saturar el loop
}