# Arquitetura Técnica — GatwayWG

## 1. Diretriz arquitetural

O GatwayWG é um **Gateway de Vídeo** baseado em **go2rtc**.

Nesta fase, o GatwayWG **não executa IA**. A execução de IA permanece no **WebGuardião**, que consome os streams RTSP disponibilizados pelo gateway.

## 2. Escopo funcional atual

### 2.1 Entradas suportadas

- RTSP (câmeras IP)
- ONVIF (descoberta e conexão)
- USB/V4L2 via FFmpeg/go2rtc
- Arquivo/emulação para testes controlados

### 2.2 Core

- **go2rtc** como núcleo de ingestão, normalização, proxy e redistribuição.

### 2.3 API de gestão

- **FastAPI** somente para:
  - cadastro de câmeras
  - health checks
  - inventário
  - exposição de URLs por `camera_uuid`

## 3. Contrato de saída de vídeo

### 3.1 Saída para IA (WebGuardião)

- Endpoint de consumo: `rtsp://<gateway_ip>:8554/<camera_uuid>`

### 3.2 Saída para operação humana

- Consumo principal: **WebRTC** para baixa latência.

### 3.3 Saída para iVMS/DVR/VMS

- Endpoint de consumo: `rtsp://<gateway_ip>:8554/<camera_uuid>`

## 4. Componentes não prioritários nesta fase

OpenCV, PyAV e Decord podem existir como fallback/laboratório, porém **não** definem o caminho principal de ingestão em produção.

## 5. Itens explicitamente fora do escopo atual

Os itens abaixo devem ser tratados como **roadmap**, não como comportamento ativo:

- inferência IA no gateway
- YOLO ativo
- DeepStream ativo
- processamento em lote (batching) ativo
- cluster ativo para processamento distribuído
- plugin analytics ativo
- VideoWall/monitor virtual em operação

## 6. Roadmap por fases

- **Fase 1 (atual):** go2rtc + RTSP/WebRTC + cadastro/persistência.
- **Fase 2:** integração WebGuardião por UUID.
- **Fase 3:** entrega RTSP para iVMS/DVR/VMS.
- **Fase 4:** VideoWall/monitor virtual.
- **Fase 5:** DeepStream/batching, se necessário.
