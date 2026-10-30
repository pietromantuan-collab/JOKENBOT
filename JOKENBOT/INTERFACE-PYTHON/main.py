import cv2
import serial
import random
import time
import math
import os
import winsound
import numpy as np
from collections import Counter, deque
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# IMPORTAÇÃO MEDIAPIPE (0.10.14+)
# ==========================================
import mediapipe as mp
try:
    import mediapipe.python.solutions.hands as mp_hands
    import mediapipe.python.solutions.drawing_utils as mp_drawing
    mp_maos = mp_hands
    mp_desenho = mp_drawing
except ImportError:
    mp_maos = mp.solutions.hands
    mp_desenho = mp.solutions.drawing_utils

# ==========================================
# CONFIGURAÇÕES DO SISTEMA
# ==========================================
PORTA_ARDUINO = "COM3"  # Altere para a porta do seu Arduino no Windows
BAUD_RATE = 115200
CAMERA_ID = 0
TEMPO_CONTAGEM = 5.0
JOGADAS = ["PEDRA", "PAPEL", "TESOURA"]

# ==========================================
# CONEXÃO COM O ARDUINO
# ==========================================
arduino = None
try:
    arduino = serial.Serial(PORTA_ARDUINO, BAUD_RATE, timeout=0.1, write_timeout=1)
    time.sleep(1.5)
    arduino.reset_input_buffer()
    print("Arduino conectado!")
except Exception as erro:
    print("Arduino não conectado / modo simulação:", erro)

def enviar_arduino(comando):
    global arduino
    if arduino is None:
        print("[SIMULAÇÃO]", comando)
        return False
    try:
        arduino.write((comando + "\n").encode("utf-8"))
        arduino.flush()
        print("Enviado ao Arduino:", comando)
        return True
    except Exception:
        arduino = None
        return False

# ==========================================
# INICIALIZAÇÃO DO MEDIAPIPE
# ==========================================
detector = mp_maos.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=1,
    min_detection_confidence=0.65,
    min_tracking_confidence=0.60
)

# ==========================================
# FUNÇÕES DE RECONHECIMENTO DE GESTOS
# ==========================================
def distancia(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

def dedo_aberto(pontos, ponta, articulacao):
    punho = pontos[0]
    return distancia(pontos[ponta], punho) > distancia(pontos[articulacao], punho) * 1.10

def identificar_jogada(mao):
    pontos = mao.landmark
    indicador = dedo_aberto(pontos, 8, 6)
    medio = dedo_aberto(pontos, 12, 10)
    anelar = dedo_aberto(pontos, 16, 14)
    mindinho = dedo_aberto(pontos, 20, 18)
    qtd = sum([indicador, medio, anelar, mindinho])
    if qtd == 0: return "PEDRA"
    if qtd == 4: return "PAPEL"
    if indicador and medio and not anelar and not mindinho: return "TESOURA"
    return None

def escolher_jogada_maquina():
    return random.choice(JOGADAS)

def verificar_vencedor(jogador, maquina):
    if jogador == maquina: return "EMPATE"
    comb = {("PEDRA", "TESOURA"), ("PAPEL", "PEDRA"), ("TESOURA", "PAPEL")}
    return "VOCÊ VENCEU!" if (jogador, maquina) in comb else "JOKENBOT VENCEU!"

def tocar_som_pontuacao(resultado):
    sons = {"VOCÊ VENCEU!": "SystemAsterisk", "JOKENBOT VENCEU!": "SystemExclamation", "EMPATE": "SystemQuestion"}
    try: winsound.PlaySound(sons.get(resultado, ""), winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception: pass

# ==========================================
# INTERFACE GRÁFICA (OPENCV + PIL)
# ==========================================
def escrever(imagem, texto, x, y, tamanho=0.8, cor=(255, 255, 255), espessura=2):
    cv2.putText(imagem, texto, (x, y), cv2.FONT_HERSHEY_SIMPLEX, tamanho, cor, espessura, cv2.LINE_AA)

def cartao_arredondado(imagem, inicio, fim, cor, raio=18):
    x1, y1 = inicio
    x2, y2 = fim
    cv2.rectangle(imagem, (x1 + raio, y1), (x2 - raio, y2), cor, -1)
    cv2.rectangle(imagem, (x1, y1 + raio), (x2, y2 - raio), cor, -1)
    for centro in ((x1 + raio, y1 + raio), (x2 - raio, y1 + raio), (x1 + raio, y2 - raio), (x2 - raio, y2 - raio)):
        cv2.circle(imagem, centro, raio, cor, -1, cv2.LINE_AA)

@lru_cache(maxsize=12)
def carregar_emoji(emoji, tamanho):
    caminho_fonte = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguiemj.ttf")
    fonte = ImageFont.truetype(caminho_fonte, tamanho - 8)
    imagem = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    limites = desenho.textbbox((0, 0), emoji, font=fonte, embedded_color=True)
    desenho.text(((tamanho - (limites[2] - limites[0])) // 2 - limites[0], (tamanho - (limites[3] - limites[1])) // 2 - limites[1]), emoji, font=fonte, embedded_color=True)
    rgba = np.array(imagem)
    return cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR), rgba[:, :, 3]

def desenhar_emoji(imagem, emoji, centro, tamanho=82):
    try:
        figura, mascara = carregar_emoji(emoji, tamanho)
        x, y = centro
        x1, y1 = max(0, x - tamanho // 2), max(0, y - tamanho // 2)
        x2, y2 = min(imagem.shape[1], x1 + tamanho), min(imagem.shape[0], y1 + tamanho)
        if x1 >= x2 or y1 >= y2: return
        recorte_figura = figura[:y2 - y1, :x2 - x1]
        alpha = mascara[:y2 - y1, :x2 - x1, np.newaxis].astype(np.float32) / 255
        recorte = imagem[y1:y2, x1:x2]
        imagem[y1:y2, x1:x2] = (recorte.astype(np.float32) * (1 - alpha) + recorte_figura.astype(np.float32) * alpha).astype(np.uint8)
    except Exception: pass

def desenhar_interface(imagem, gesto, estado, restante, jogada_jogador, jogada_maquina, resultado, pontos_jogador, pontos_maquina, empates, vencedor_partida, resultado_visivel):
    largura_tela, altura_tela = 1280, 720
    cor_fundo, cor_painel, cor_cartao, cor_destaque = (35, 23, 20), (51, 35, 31), (67, 48, 43), (244, 220, 74)
    emojis = {"PEDRA": "✊", "PAPEL": "✋", "TESOURA": "✌"}

    tela = np.full((altura_tela, largura_tela, 3), cor_fundo, dtype=np.uint8)
    cv2.rectangle(tela, (0, 0), (largura_tela, 76), (46, 31, 27), -1)
    cv2.rectangle(tela, (0, 74), (largura_tela, 77), cor_destaque, -1)
    escrever(tela, "JOKENBOT", 30, 43, 0.95, (245, 248, 255), 2)
    escrever(tela, "PEDRA | PAPEL | TESOURA", 210, 41, 0.55, (164, 174, 197))
    escrever(tela, "CAMERA + ROBOT", 1082, 40, 0.5, (164, 174, 197))

    video_x, video_y = 28, 100
    video_largura, video_altura = 790, 592
    if imagem is not None and imagem.size > 0:
        video = cv2.resize(imagem, (video_largura, video_altura))
        tela[video_y:video_y + video_altura, video_x:video_x + video_largura] = video
    else:
        cv2.rectangle(tela, (video_x, video_y), (video_x + video_largura, video_y + video_altura), (20, 20, 20), -1)
        escrever(tela, "CONECTANDO WEBCAM...", video_x + 220, video_y + 300, 0.8, (245, 248, 255), 2)

    cartao_arredondado(tela, (44, 115), (183, 153), (46, 31, 27), 12)
    escrever(tela, "WEBCAM", 61, 140, 0.52, (245, 248, 255), 1)
    cv2.circle(tela, (166, 134), 5, (95, 235, 149), -1, cv2.LINE_AA)

    painel_x = 842
    cartao_arredondado(tela, (painel_x, 100), (1252, 692), cor_painel, 22)
    escrever(tela, "PLACAR", 862, 137, 0.62, (185, 194, 215), 1)

    placar = (("VOCE", pontos_jogador, (93, 220, 153)), ("ROBO", pontos_maquina, (112, 177, 255)), ("EMPATES", empates, (190, 195, 211)))
    for indice, (rotulo, pontos, cor) in enumerate(placar):
        x = 860 + indice * 124
        cartao_arredondado(tela, (x, 151), (x + 112, 220), cor_cartao, 12)
        escrever(tela, rotulo, x + 12, 174, 0.39, (177, 186, 207), 1)
        escrever(tela, str(pontos), x + 12, 207, 0.92, cor, 2)

    mostrar_ultima_jogada = resultado_visivel or estado == "FIM_PARTIDA"
    jogada_exibida = jogada_jogador if mostrar_ultima_jogada else gesto
    emoji_jogador = emojis.get(jogada_exibida, "👋")
    texto_jogador = jogada_exibida or "Mostre a mao"

    if mostrar_ultima_jogada and jogada_maquina:
        jogada_robo = jogada_maquina
        texto_robo = jogada_maquina
    elif estado == "CONTAGEM":
        jogada_robo = JOGADAS[int(time.monotonic() * 5) % len(JOGADAS)]
        texto_robo = "Pensando..."
    else:
        jogada_robo = None
        texto_robo = "Aguardando rodada"

    cartao_arredondado(tela, (860, 233), (1234, 366), cor_cartao, 16)
    escrever(tela, "SUA JOGADA", 960, 263, 0.48, (185, 194, 215), 1)
    desenhar_emoji(tela, emoji_jogador, (907, 306), 78)
    escrever(tela, texto_jogador, 960, 309, 0.68, (245, 248, 255) if jogada_exibida else (177, 186, 207), 2)

    cartao_arredondado(tela, (860, 378), (1234, 511), cor_cartao, 16)
    escrever(tela, "JOKENBOT", 960, 408, 0.48, (185, 194, 215), 1)
    desenhar_emoji(tela, emojis[jogada_robo] if jogada_robo else "🤖", (907, 451), 78)
    escrever(tela, texto_robo, 960, 454, 0.65, (245, 248, 255), 2)

    cartao_arredondado(tela, (860, 523), (1234, 608), (37, 43, 60), 14)
    if estado == "FIM_PARTIDA":
        cor_vendedor = (93, 220, 153) if vencedor_partida == "VOCE" else (112, 177, 255)
        escrever(tela, f"{vencedor_partida} VENCEU!", 880, 559, 0.61, cor_vendedor, 2)
        escrever(tela, "ESPACO para jogar de novo", 880, 586, 0.4, (177, 186, 207), 1)
    elif resultado_visivel:
        escrever(tela, resultado, 880, 555, 0.58, (245, 248, 255), 2)
        escrever(tela, f"PLACAR: {pontos_jogador} x {pontos_maquina}", 880, 585, 0.48, (177, 186, 207), 1)
    elif estado == "CONTAGEM":
        escrever(tela, f"RODADA EM {restante}s", 880, 559, 0.58, cor_destaque, 2)
        escrever(tela, "Prepare sua jogada!", 880, 586, 0.43, (177, 186, 207), 1)
    else:
        escrever(tela, "PRIMEIRO A 3 PONTOS VENCE", 880, 559, 0.55, cor_destaque, 2)
        escrever(tela, "Pressione ESPACO para iniciar", 880, 586, 0.43, (177, 186, 207), 1)

    escrever(tela, "ESPACO iniciar | R reiniciar | Q sair", 860, 650, 0.41, (177, 186, 207), 1)
    escrever(tela, "1, 2, 3: testar movimentos do robo", 860, 674, 0.38, (132, 145, 171), 1)
    return tela

# ==========================================
# INICIALIZAÇÃO DA CÂMERA E JANELA
# ==========================================
NOME_JANELA = "JOKENBOT - ROBOTIC EDITION"
cv2.namedWindow(NOME_JANELA, cv2.WINDOW_NORMAL)
cv2.resizeWindow(NOME_JANELA, 1280, 720)

print("Tentando inicializar captura de vídeo...")
camera = None
for idx in [0, 1]:
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if cap.isOpened():
        camera = cap
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print(f"Câmera inicializada com sucesso no índice {idx}!")
        break
    cap.release()

if camera is None:
    print("Tentando backend padrão...")
    camera = cv2.VideoCapture(0)

# ==========================================
# VARIÁVEIS DE ESTADO DO JOGO
# ==========================================
estado = "PRONTO"
inicio_contagem = 0
inicio_ultimo_resultado = 0
jogada_jogador, jogada_maquina = None, None
resultado, vencedor_partida = "", ""
pontos_jogador, pontos_maquina, empates = 0, 0, 0
historico_gestos = deque(maxlen=8)

def finalizar_rodada(jogada):
    global estado, inicio_contagem, inicio_ultimo_resultado, jogada_jogador, jogada_maquina, resultado, vencedor_partida, pontos_jogador, pontos_maquina, empates
    jogada_jogador = jogada
    jogada_maquina = escolher_jogada_maquina()
    resultado = verificar_vencedor(jogada_jogador, jogada_maquina)
    enviar_arduino(jogada_maquina)
    if resultado == "VOCÊ VENCEU!": pontos_jogador += 1
    elif resultado == "JOKENBOT VENCEU!": pontos_maquina += 1
    else: empates += 1
    tocar_som_pontuacao(resultado)
    agora = time.monotonic()
    inicio_ultimo_resultado = agora
    historico_gestos.clear()

    if pontos_jogador >= 3:
        vencedor_partida, estado = "VOCE", "FIM_PARTIDA"
    elif pontos_maquina >= 3:
        vencedor_partida, estado = "JOKENBOT", "FIM_PARTIDA"
    else:
        estado, inicio_contagem = "CONTAGEM", agora

# ==========================================
# LOOP PRINCIPAL DO SISTEMA
# ==========================================
print("================================")
print("JOKENBOT ROBOTIC EDITION")
print("================================")
print("ESPACO = iniciar partida (melhor de 3 pontos)")
print("1, 2, 3 = testar movimentos do robo")
print("R = zerar placar | Q = sair")

try:
    while True:
        frame = None
        if camera is not None and camera.isOpened():
            sucesso, frame_raw = camera.read()
            if sucesso and frame_raw is not None:
                frame = cv2.flip(frame_raw, 1)

        gesto = None
        if frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            deteccao = detector.process(rgb)
            rgb.flags.writeable = True
            if deteccao.multi_hand_landmarks:
                mao = deteccao.multi_hand_landmarks[0]
                mp_desenho.draw_landmarks(frame, mao, mp_maos.HAND_CONNECTIONS)
                gesto = identificar_jogada(mao)

        if estado == "CONTAGEM":
            historico_gestos.append(gesto)

        agora = time.monotonic()
        restante = 0
        if estado == "CONTAGEM":
            decorrido = agora - inicio_contagem
            restante = max(0, math.ceil(TEMPO_CONTAGEM - decorrido))
            if decorrido >= TEMPO_CONTAGEM:
                validos = [g for g in historico_gestos if g in JOGADAS]
                if len(validos) >= 2:
                    finalizar_rodada(Counter(validos).most_common(1)[0][0])
                else:
                    inicio_contagem = agora
                    historico_gestos.clear()

        # Renderiza a tela completa no OpenCV
        tela_final = desenhar_interface(
            frame, gesto, estado, restante,
            jogada_jogador, jogada_maquina, resultado,
            pontos_jogador, pontos_maquina, empates,
            vencedor_partida, agora - inicio_ultimo_resultado < 1.2
        )

        cv2.imshow(NOME_JANELA, tela_final)
        
        # Mantém a janela atualizada
        tecla = cv2.waitKey(10) & 0xFF

        if tecla == 32 and estado in ("PRONTO", "FIM_PARTIDA"):
            pontos_jogador, pontos_maquina, empates = 0, 0, 0
            jogada_jogador, jogada_maquina, resultado, vencedor_partida = None, None, "", ""
            estado, inicio_contagem = "CONTAGEM", time.monotonic()
            historico_gestos.clear()
            print("Nova partida iniciada!")
        elif tecla == ord("1") and estado == "PRONTO": enviar_arduino("PEDRA")
        elif tecla == ord("2") and estado == "PRONTO": enviar_arduino("PAPEL")
        elif tecla == ord("3") and estado == "PRONTO": enviar_arduino("TESOURA")
        elif tecla == ord("r"):
            pontos_jogador, pontos_maquina, empates = 0, 0, 0
            estado = "PRONTO"
            print("Placar reiniciado!")
        elif tecla == ord("q") or tecla == 27:
            break
finally:
    if camera is not None: camera.release()
    detector.close()
    cv2.destroyAllWindows()
    if arduino is not None: arduino.close()
    print("JOKENBOT encerrado.")