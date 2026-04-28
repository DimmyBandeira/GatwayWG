# GatwayWG — Video Gateway baseado em go2rtc

O **GatwayWG** é o gateway de vídeo do ecossistema WebGuardião.

> **Escopo atual (Fase 1):** o GatwayWG **não executa IA** nesta fase.
> A IA permanece no **WebGuardião**, que consome streams RTSP publicados pelo gateway.

## Objetivo

Fornecer uma camada estável de ingestão, normalização, proxy e redistribuição de vídeo com base no **go2rtc**, desacoplando fontes físicas do restante do ecossistema por `camera_uuid`.

## Arquitetura atual (estado implementado)

- **Entrada (ingestão)**
  - RTSP
  - ONVIF
  - USB/V4L2 via FFmpeg/go2rtc
  - Arquivo/emulação para laboratório
- **Core de streaming:** go2rtc
- **API de gestão (FastAPI):** cadastro, health check, inventário e exposição de URLs
- **Saída para IA (WebGuardião):** RTSP local
- **Saída para operador:** WebRTC
- **Saída para VMS/DVR/iVMS:** RTSP limpo

## Contrato de consumo de stream

- **WebGuardião consome:** `rtsp://<gateway_ip>:8554/<stream_name>`
- **iVMS/DVR/VMS consomem:** `rtsp://<gateway_ip>:8554/<stream_name>`

## Provisionamento go2rtc no cadastro (GAT-12)

- `POST /cameras/` persiste a câmera no Registry **e tenta publicar cada stream válido**
  (`visible/thermal` `main/sub`) no go2rtc via API runtime.
- Resposta inclui `go2rtc_provisioning` com resultado por stream:
  - `ok=true` quando stream foi criado/atualizado;
  - `ok=false` quando houve falha de publicação (sem perder o cadastro no Registry).
- Falhas de publicação entram em retentativa assíncrona com backoff exponencial.
- Endpoint operacional: `POST /cameras/{uuid}/publish` para republicar streams sob demanda.
- Para `source_type=file`, não há provisionamento no go2rtc; o modo legado `/stream/{uuid}`
  continua disponível para laboratório/debug.

## Escopo técnico nesta fase

### Em produção (agora)
- go2rtc como caminho principal de ingestão e distribuição.
- FastAPI para operações administrativas e inventário.
- Exposição de streams RTSP e WebRTC por câmera (UUID).

### Fora de escopo nesta fase
- Execução de IA no próprio gateway.
- YOLO ativo no gateway.
- DeepStream ativo no gateway.
- Batch processing ativo no gateway.
- Plugin analytics ativo no gateway.

## OpenCV, PyAV e Decord

**OpenCV/PyAV/Decord não são o caminho principal de ingestão**.
Podem permanecer como fallback/laboratório, mas o core operacional do projeto é o **go2rtc**.

## Roadmap por fases

- **Fase 1:** go2rtc + RTSP/WebRTC + cadastro/persistência.
- **Fase 2:** integração WebGuardião por UUID.
- **Fase 3:** entrega RTSP para iVMS/DVR/VMS.
- **Fase 4:** VideoWall/monitor virtual.
- **Fase 5:** DeepStream/batching, se necessário.

## Estrutura de diretórios (resumo)

```text
GatwayWG/
├── app.py
├── README.md
├── ARCHITECTURE.md
├── go2rtc.yaml
├── services/
├── integrations/
├── core/
└── plugins/
```

> Componentes de cluster, batching, VideoWall e plugins analíticos são mantidos como referência de evolução arquitetural (roadmap), não como recursos ativos desta fase.


## Discovery operacional (GAT-12)

- Endpoint: `GET /go2rtc/discovery`
- Objetivo: listar streams já existentes no go2rtc em formato normalizado para preencher cadastro por tipo (`visible/thermal` e `main/sub`) na UI.
- Fora de escopo: ONVIF real, alteração dinâmica de `go2rtc.yaml`, IA/YOLO/DeepStream.


## Discovery ONVIF via go2rtc

- go2rtc oferece endpoint de discovery ONVIF real: `GET /api/onvif` (com `src` opcional).
- O Gateway expõe wrappers:
  - `GET /go2rtc/discovery/streams` (streams já cadastrados)
  - `GET /go2rtc/discovery/onvif` (descoberta ONVIF na rede)
- Exemplo de busca direcionada:
  - `/go2rtc/discovery/onvif?src=onvif://admin:senha@192.168.1.50:80`

> Importante: streams cadastrados e dispositivos ONVIF descobertos são conceitos distintos na UI operacional.


### Busca ONVIF recomendada

- Priorize busca direcionada por IP: `GET /go2rtc/discovery/onvif?src=onvif://user:pass@ip:porta`.
- `GET /go2rtc/discovery/onvif` sem `src` é tratado como experimental/lento e retorna orientação amigável para busca direcionada.


### Hint de rede local (sem scan pesado)

- `GET /network/local-base` sugere IP/base local e portas ONVIF/RTSP comuns para facilitar busca direcionada.
- Não realiza scan de rede pesada e não adiciona dependência Python ONVIF neste GAT.


### ONVIF scan por sub-rede local

- `GET /network/local-networks` lista redes locais privadas detectadas.
- `GET /go2rtc/discovery/onvif/scan` faz varredura controlada por faixa (ex.: `192.168.1.100-110`) usando go2rtc `src=onvif://...`.
- `0.0.0.0` não é alvo de câmera; é apenas wildcard de interface local.
- Limites: pode demorar e depende de ONVIF habilitado, firewall e credencial informada pelo operador.
