# go2rtc_client.py: Middleware de streaming (WebRTC/RTSP) 
# integrations/go2rtc_client.py
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Go2RTC_Client")

class Go2RTCClient:
    """
    Cliente para consumir a API REST nativa do go2rtc.
    Atua como a ponte entre o Gateway (Python) e o Middleware (C/Go).
    """
    def __init__(self, base_url: str = "http://localhost:1984"):
        self.base_url = base_url

    def get_active_streams(self):
        """
        Consulta o go2rtc para listar todas as câmeras (RTSP/ONVIF/Emuladas)
        que estão atualmente online e configuradas no go2rtc.yaml.
        """
        try:
            url = f"{self.base_url}/api/streams"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            # O go2rtc retorna um dicionário onde a chave é o nome da câmera
            streams_data = response.json()
            
            active_cameras = []
            for stream_name, details in streams_data.items():
                active_cameras.append({
                    "name": stream_name,
                    "producers": details.get("producers", []),
                    "webrtc_url": f"ws://localhost:8555/api/ws?src={stream_name}",
                    "rtsp_url": f"rtsp://localhost:8554/{stream_name}"
                })
                
            logger.info(f"Encontradas {len(active_cameras)} câmeras ativas no go2rtc.")
            return active_cameras
            
        except requests.RequestException as e:
            logger.error(f"Falha ao conectar na API do go2rtc: {e}")
            return []

# --- Teste isolado do módulo ---
if __name__ == "__main__":
    client = Go2RTCClient()
    cameras = client.get_active_streams()
    print("Câmeras disponíveis para o WebGuardião:")
    for cam in cameras:
        print(f"- {cam['name']} (RTSP: {cam['rtsp_url']})")