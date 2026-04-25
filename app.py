# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import cv2
import os

# Importando seu motor de captura
from services.capture_engine import CaptureEngine

app = FastAPI(title="WebGuardião Gateway Master", version="2.0.0")

# Liberar CORS para que o navegador permita o "aperto de mão" entre portas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Banco de dados em memória (Dicionário)
camera_registry = {}
active_engines = {}


class CameraPayload(BaseModel):
    uuid: str
    name: str
    type: str
    path: str
    node: str
    pipeline: str
    videoWall: bool
    plugins: List[str]
    createdAt: str

# ---------------------------------------------------------
# 🏥 MONITORAMENTO E INTERFACE
# ---------------------------------------------------------


@app.get("/")
def serve_ui():
    """Serve o arquivo HTML real que você criou."""
    return FileResponse("cadastro.html")


@app.get("/health")
def health_check():
    """Endpoint que o seu HTML usa para mostrar 'Master Node: Online'."""
    return {"status": "online", "version": "2.0.0"}

# ---------------------------------------------------------
# 📹 GESTÃO DE CÂMERAS
# ---------------------------------------------------------


@app.get("/cameras/")
def get_all_cameras():
    """Retorna a lista real de câmeras para preencher a sua lista lateral."""
    return list(camera_registry.values())


@app.post("/cameras/", status_code=201)
def add_camera(payload: CameraPayload):
    """Recebe o cadastro do formulário HTML."""
    cam_id = payload.uuid
    camera_registry[cam_id] = payload.dict()

    # Inicia o motor de captura em background
    engine = CaptureEngine(
        camera_uuid=cam_id,
        source_type=payload.type,
        source_path=payload.path
    )
    active_engines[cam_id] = engine

    return {"status": "success", "uuid": cam_id}


@app.delete("/cameras/{uuid}")
def remove_camera(uuid: str):
    """Para o motor e remove do registro."""
    if uuid in active_engines:
        active_engines[uuid].stop()
        del active_engines[uuid]

    if uuid in camera_registry:
        del camera_registry[uuid]
        return {"status": "deleted"}

    raise HTTPException(status_code=404, detail="Câmera não encontrada")

# ---------------------------------------------------------
# 🎥 STREAMING ENGINE
# ---------------------------------------------------------


def frame_generator(uuid: str):
    engine = active_engines.get(uuid)
    if not engine:
        return

    # O start() do seu CaptureEngine retorna o generator de frames
    stream = engine.start()
    if not stream:
        return

    try:
        for frame in stream:
            # Converte BGR (OpenCV) para JPEG para o navegador entender
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    finally:
        engine.stop()


@app.get("/stream/{uuid}")
def video_feed(uuid: str):
    """O endpoint que o seu botão '▶️ Testar Stream' chama."""
    if uuid not in active_engines:
        raise HTTPException(status_code=404, detail="Stream não encontrado")

    return StreamingResponse(
        frame_generator(uuid),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn
    # Roda na 8000 para o HTML conseguir acessar
    uvicorn.run(app, host="0.0.0.0", port=8000)
