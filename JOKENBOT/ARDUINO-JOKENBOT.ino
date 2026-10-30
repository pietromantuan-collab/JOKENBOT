#include <Servo.h>

// ==========================================
// JOKENBOT - ARDUINO UNO
// Controle de dois servomotores via USB
// ==========================================

Servo servo1;
Servo servo2;

// PINOS
const int PINO_SERVO_1 = 9;
const int PINO_SERVO_2 = 10;

// ==========================================
// CALIBRACAO DOS SERVOS
// Ajuste conforme a sua mao robotica.
// Teste inicialmente sem os fios dos dedos.
// ==========================================

// Servo 1: indicador e medio
const int S1_ABERTO = 90;
const int S1_FECHADO = 0;

// Servo 2: polegar, anelar e mindinho
const int S2_ABERTO = 90;
const int S2_FECHADO = 0;

// Posicoes atuais
int posicao1 = S1_ABERTO;
int posicao2 = S2_ABERTO;

// Intervalo entre passos de movimento
const int VELOCIDADE_MS = 3;

// ==========================================
// MOVIMENTACAO SUAVE
// ==========================================

void moverServos(int destino1, int destino2) {
  destino1 = constrain(destino1, 0, 180);
  destino2 = constrain(destino2, 0, 180);

  while (posicao1 != destino1 || posicao2 != destino2) {
    if (posicao1 < destino1) {
      posicao1++;
    } else if (posicao1 > destino1) {
      posicao1--;
    }

    if (posicao2 < destino2) {
      posicao2++;
    } else if (posicao2 > destino2) {
      posicao2--;
    }

    servo1.write(posicao1);
    servo2.write(posicao2);

    delay(VELOCIDADE_MS);
  }
}

// ==========================================
// JOGADAS
// ==========================================

void pedra() {
  Serial.println("MOVENDO:PEDRA");
  moverServos(S1_FECHADO, S2_FECHADO);
  Serial.println("OK:PEDRA");
}

void papel() {
  Serial.println("MOVENDO:PAPEL");
  moverServos(S1_ABERTO, S2_ABERTO);
  Serial.println("OK:PAPEL");
}

void tesoura() {
  Serial.println("MOVENDO:TESOURA");
  moverServos(S1_ABERTO, S2_FECHADO);
  Serial.println("OK:TESOURA");
}

// ==========================================
// INICIALIZACAO
// ==========================================

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);

  servo1.attach(PINO_SERVO_1);
  servo2.attach(PINO_SERVO_2);

  // Comeca com a mao aberta
  servo1.write(posicao1);
  servo2.write(posicao2);

  delay(1000);

  Serial.println("JOKENBOT_PRONTO");
}

// ==========================================
// COMUNICACAO SERIAL
// ==========================================

void loop() {
  if (Serial.available() > 0) {
    String comando = Serial.readStringUntil('\n');

    comando.trim();
    comando.toUpperCase();

    if (comando == "PEDRA") {
      pedra();
    } else if (comando == "PAPEL") {
      papel();
    } else if (comando == "TESOURA") {
      tesoura();
    } else if (comando == "ABRIR") {
      papel();
    } else if (comando == "FECHAR") {
      pedra();
    } else if (comando == "PING") {
      Serial.println("PONG");
    } else {
      Serial.println("ERRO:COMANDO_INVALIDO");
    }
  }
}