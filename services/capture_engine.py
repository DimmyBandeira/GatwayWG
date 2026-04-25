# services/capture_engine.py
import time
import logging
import av
import cv2
from decord import VideoReader, cpu

# Configuração de Watchdog/Log
logger = logging.getLogger("CaptureEngine")
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - [%(levelname)s] - %(message)s')


class CaptureEngine:
    """
    Motor de Ingestão Multisource do WebGuardião Gateway.
    Abstrai a complexidade do hardware e fornece um stream de frames padronizado (BGR),
    pronto para processamento em lote (Batching) no DeepStream/YOLO.
    """

    def __init__(self, camera_uuid: str, source_type: str, source_path: str):
        self.camera_uuid = camera_uuid
        self.source_type = source_type.lower()
        self.source_path = source_path
        self.running = False

        # Resiliência: Configuração de Watchdog e Backoff
        self.max_retries = 5
        self.retry_delay = 2.0

    def _stream_rtsp(self):
        """Captura RTSP via PyAV para máxima estabilidade em redes instáveis."""
        retries = 0
        while self.running and retries < self.max_retries:
            try:
                logger.info(
                    f"[{self.camera_uuid}] Conectando ao RTSP (PyAV): {self.source_path}")
                # Timeout de 5s evita travamento de thread se a câmera "sumir" da rede
                container = av.open(self.source_path, options={
                                    'rtsp_transport': 'tcp'}, timeout=5)
                stream = container.streams.video[0]

                # Zera as tentativas após conexão bem-sucedida
                retries = 0

                for frame in container.decode(stream):
                    if not self.running:
                        break
                    # Converte diretamente para BGR24 (Padrão nativo do OpenCV/YOLO)
                    yield frame.to_ndarray(format='bgr24')

            except Exception as e:
                logger.warning(
                    f"[{self.camera_uuid}] Erro RTSP: {e}. Reconectando em {self.retry_delay}s...")
                retries += 1
                time.sleep(self.retry_delay)

        if retries >= self.max_retries:
            logger.error(
                f"[{self.camera_uuid}] Falha crítica: Limite de reconexões atingido. Notificando WebGuardião.")
            # Aqui entrará a notificação para o Event Bus no futuro

    def _stream_file(self):
        """Emulação de arquivo via Decord simulando um stream contínuo (Loop Infinito)."""
        logger.info(
            f"[{self.camera_uuid}] Iniciando Emulação (Decord): {self.source_path}")
        try:
            # Decord extrai frames extremamente rápido, ideal para testes de IA
            vr = VideoReader(self.source_path, ctx=cpu(0))
            total_frames = len(vr)

            while self.running:
                for i in range(total_frames):
                    if not self.running:
                        break

                    # Decord extrai em RGB, convertemos para BGR para manter o pipeline uniforme
                    frame_rgb = vr[i].asnumpy()
                    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                    # Emula ~30 FPS (0.033s) para não asfixiar a CPU durante os testes de laboratório
                    time.sleep(0.033)
                    yield frame_bgr

        except Exception as e:
            logger.error(
                f"[{self.camera_uuid}] Falha na emulação de arquivo: {e}")

    def _stream_usb(self):
        """Captura local via OpenCV para hardwares USB / V4L2."""
        logger.info(
            f"[{self.camera_uuid}] Iniciando captura local (OpenCV): {self.source_path}")

        # Converte o source_path para inteiro se for um índice (ex: "0")
        source = int(self.source_path) if str(
            self.source_path).isdigit() else self.source_path
        cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            logger.error(
                f"[{self.camera_uuid}] Falha ao abrir dispositivo USB: {self.source_path}")
            return

        while self.running:
            ret, frame = cap.read()
            if not ret:
                logger.warning(
                    f"[{self.camera_uuid}] Frame USB corrompido ou perdido. Tentando novamente...")
                time.sleep(1)
                continue

            yield frame

        cap.release()

    def start(self):
        """Inicia a ingestão roteando para o worker correto. Retorna um Generator."""
        self.running = True

        if self.source_type == 'rtsp':
            return self._stream_rtsp()
        elif self.source_type == 'file':
            return self._stream_file()
        elif self.source_type == 'usb':
            return self._stream_usb()
        else:
            logger.error(
                f"[{self.camera_uuid}] Tipo de fonte não suportado pelo Gateway: {self.source_type}")
            return None

    def stop(self):
        """Encerra graciosamente a thread de captura."""
        logger.info(
            f"[{self.camera_uuid}] Sinal de interrupção recebido. Desligando motor...")
        self.running = False
