# GAT 2 — Status de Consolidação do Gateway de Vídeo

## Papel do go2rtc

O **go2rtc** é o middleware principal de vídeo no GAT 2, responsável por:

- ingestão de fontes RTSP/ONVIF/USB/arquivo;
- normalização de streams;
- distribuição RTSP para consumidores externos;
- distribuição WebRTC para operação humana em baixa latência.

## Papel do Gateway Python (FastAPI)

O Gateway Python atua como **orquestrador de controle**, não como motor de IA:

- cadastro e remoção de câmeras;
- persistência local do inventário;
- health checks do próprio serviço e do go2rtc;
- entrega de metadados e URLs normalizadas por `camera_uuid`.

## Endpoints atuais

- `GET /` — UI de cadastro.
- `GET /health` — saúde do Gateway Python.
- `GET /go2rtc/health` — saúde do go2rtc (sem derrubar a aplicação em falha).
- `GET /go2rtc/streams` — inventário de streams ativos no go2rtc.
- `GET /cameras/` — lista de câmeras persistidas + URLs normalizadas.
- `GET /cameras/{uuid}` — detalhe de câmera persistida + URLs normalizadas.
- `POST /cameras/` — cadastro de câmera (com compatibilidade de contrato legado).
- `DELETE /cameras/{uuid}` — remoção persistente.
- `GET /stream/{uuid}` — fallback legado MJPEG via `CaptureEngine`.

## CaptureEngine no GAT 2

`CaptureEngine` permanece em **modo legado/fallback**:

- útil para debug local e compatibilidade temporária;
- não é o caminho principal de ingestão em produção;
- pode ser removido gradualmente quando o registro dinâmico no go2rtc estiver completo.

## Próximos passos (GAT 3)

1. Registro dinâmico real de streams no go2rtc (API/config runtime).
2. VideoWall/mosaico para operação.
3. Contratos formais para consumo do WebGuardião IA por UUID.
4. Evolução para worker nodes com distribuição de carga de controle.
5. Monitoramento e telemetria operacional (latência, disponibilidade, falhas de stream).

## GAT 2.2 — Sincronização RegistryService ↔ go2rtc

### Novos endpoints

- `GET /sync/status`
- `POST /sync/import-go2rtc`

### Conceitos operacionais

- **Cadastrado no Registry**: câmera persistida no JSON local do Gateway.
- **Existente no go2rtc**: stream presente em `/api/streams` no go2rtc.
- **Importado**: stream existente no go2rtc que foi gravado no Registry via `POST /sync/import-go2rtc`.
- **Não publicado**: câmera cadastrada no Registry cujo `stream_name` não foi encontrado no go2rtc.

### Observações de escopo

- Esta etapa não cria/edita streams no go2rtc, apenas importa estado existente.
- Câmera real/térmica continua para etapa posterior.
- `CaptureEngine` permanece legado/fallback.

## GAT 2.3 — Câmera lógica com múltiplos streams

### Modelo

- Cada câmera lógica passa a aceitar `streams.visible.main/sub` e `streams.thermal.main/sub`.
- `thermal` e substreams são opcionais.
- Compatibilidade retroativa: formato antigo (`stream_name/source_url`) é migrado para `streams.visible.main`.

### Endpoints impactados

- `POST /cameras/` aceita formato antigo e formato novo.
- `GET /cameras/` e `GET /cameras/{uuid}` retornam estrutura nova com status/URL por stream.
- `GET /sync/status` passa a considerar cada stream individualmente.

### Escopo

- Sem IA, sem YOLO, sem plugins ativos.
- Stream térmico é apenas contrato de transporte.
- `CaptureEngine` permanece legado/fallback.
