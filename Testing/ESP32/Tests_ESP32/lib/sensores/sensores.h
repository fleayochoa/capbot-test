#ifndef SENSORES_H
#define SENSORES_H

#include <Arduino.h>
#include <Wire.h>
#include <ESP32Encoder.h>
#include <Adafruit_VL53L0X.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>

// =========================
// Estructuras
// =========================
struct Estado {
  float x;
  float y;
  float theta;
  float v;
  float omega;
  float dist1;
  float dist2;

  // Constructor para inicializar variables
  Estado() : x(0.0f), y(0.0f), theta(0.0f), v(0.0f), omega(0.0f), dist1(0.0f), dist2(0.0f) {}
};

// =========================
// Variables Globales Externas
// =========================
// Permite que otros archivos que incluyan este header puedan leer el estado actual
extern Estado estadoMedido;
extern float* distanciasMedidas;

extern bool tof1_ok;
extern bool tof2_ok;
extern bool bno_ok;

// =========================
// Prototipos de Funciones
// =========================

/**
 * @brief Inicializa las comunicaciones I2C, pines, encoders y sensores (VL53L0X y BNO055).
 */
void sensorSetup();

/**
 * @brief Pone a cero los contadores de los encoders y reinicia el tiempo de medición.
 */
void resetEncoders();

/**
 * @brief Realiza la lectura de los dos sensores TOF VL53L0X.
 */
void distancia();

/**
 * @brief Calcula la velocidad lineal y angular de cada rueda usando los encoders.
 */
void actualizarVelocidad();

/**
 * @brief Actualiza la posición odómetrica (X, Y) basada en la velocidad y orientación.
 */
void actualizarPos();

/**
 * @brief Lee los datos del IMU BNO055 para obtener la orientación y velocidad angular.
 */
void orientacionYomega();

/**
 * @brief Función principal que agrupa todas las lecturas y actualizaciones del sistema.
 * @return Estructura Estado con todas las variables actualizadas.
 */
Estado actualizarMediciones();

/**
 * @brief Imprime por puerto serie el estado actual del robot.
 */
void imprimirDebug();

#endif // SENSORES_H