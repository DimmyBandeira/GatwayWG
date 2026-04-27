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
- `GET /go2rtc/streams` — inventário raw/compatível de streams ativos no go2rtc.
- `GET /go2rtc/discovery` — compatibilidade (retorna streams cadastrados no go2rtc).
- `GET /go2rtc/discovery/streams` — streams já cadastrados no go2rtc (`/api/streams`).
- `GET /go2rtc/discovery/onvif` — discovery ONVIF real via go2rtc (`/api/onvif`).
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

## GAT 2.4 — UX de discovery e fontes por tipo (cadastro.html)

- UI passa a expor claramente:
  - **Buscar streams do go2rtc** (`GET /go2rtc/streams`)
  - **Importar streams do go2rtc** (`POST /sync/import-go2rtc`)
- Formulário reage por `source_type`:
  - `rtsp`: campos multi-stream (`visible/thermal` + `main/sub`)
  - `file`: apenas stream principal (visible ou thermal)
  - `go2rtc`: seleção de stream descoberto
- Sem IA/YOLO/plugin ativo por padrão (`plugins: []`).
- Limitação atual para `file`: sem upload real no backend; `source_url` usa nome/caminho do arquivo informado no navegador.


### Dependências operacionais relevantes

- `python-multipart` é obrigatório para `POST /upload/video` (upload via `multipart/form-data`).
- Stack legado/fallback de vídeo permanece (`opencv-python`, `av`, `decord`) para rota `GET /stream/{uuid}` em cenários de debug/compatibilidade.

### Fluxo operacional recomendado (fase atual)

1. Verificar saúde: `GET /health` e `GET /go2rtc/health`.
2. Descobrir streams existentes: `GET /go2rtc/streams` (botão **Buscar streams do go2rtc**).
3. No `cadastro.html`, usar ações por stream (**Usar como visível** / **Usar como térmico**) para pré-preencher cadastro lógico.
4. Opcionalmente importar inventário já existente via `POST /sync/import-go2rtc`.
5. Cadastrar/ajustar câmera em `POST /cameras/` e validar saída RTSP por UUID.

### ONVIF/discovery (estado real)

- `services/discovery_service.py` está em estado placeholder nesta fase (sem fluxo operacional real exposto na UI).
- Portanto, o painel de produção não deve prometer descoberta ONVIF automática real neste momento.
- Status recomendado: **experimental/simulação** até implementação real (não usar como promessa de produção nesta fase).

### Modularização mínima do app.py

- GAT 2.4 iniciou modularização pontual com `services/camera_normalizer.py` para sanitização/validação de payload (incluindo bloqueio de `C:\\fakepath`).
- Sem refactor amplo de rotas nesta etapa para manter diff controlado.

## GAT 2.4.1 — Upload mínimo para source_type=file

- Endpoint adicionado: `POST /upload/video` (multipart/form-data, campo `file`).
- Arquivos são salvos em `data/media/` com nome sanitizado e sufixo único.
- Extensões permitidas: `.mp4`, `.avi`, `.mkv`.
- Limite simples de tamanho: `200MB`.
- `cadastro.html` envia arquivo automaticamente ao selecionar e usa `file_path` retornado como `source_url`.
- `C:\\fakepath` continua bloqueado no frontend e backend.


## GAT 2.4.2 — Discovery ONVIF real via go2rtc

- Gateway usa endpoint real do go2rtc: `GET /api/onvif` (com `src` opcional).
- Wrapper no Gateway:
  - `GET /go2rtc/discovery/streams`
  - `GET /go2rtc/discovery/onvif`
  - `GET /go2rtc/discovery/onvif?src=onvif://admin:senha@192.168.1.50:80`
- Diferença operacional:
  - **streams cadastrados**: já existem no go2rtc e aparecem em `/api/streams`;
  - **câmeras ONVIF**: descobertas em rede via `/api/onvif`.
- Segurança: UI e logs devem mascarar senha quando exibirem URL.

- Operação recomendada: discovery ONVIF **direcionado por IP** (via `src`), evitando varredura geral de rede.
- `GET /go2rtc/discovery/onvif` sem `src` retorna aviso amigável para usar `onvif://user:pass@ip:porta`.


## GAT 2.4.3 — Hint de rede local (referência do legado sem dependência ONVIF)

- O arquivo legado `onvif_discovery.py` foi usado apenas como referência conceitual para obter base de rede local.
- A biblioteca Python `onvif` **não** é dependência obrigatória nesta fase.
- Endpoint adicionado: `GET /network/local-base` para sugerir `base_ip` e portas comuns ONVIF/RTSP, sem scan pesado.
- Discovery principal continua via go2rtc `GET /api/onvif` com busca direcionada por `src`.
- Scan por faixa e fallback com biblioteca Python ONVIF ficam para etapa futura.


## GAT 2.4.4 — ONVIF scan controlado por sub-rede local

- `GET /network/local-networks` detecta sub-redes locais privadas (sem usar `0.0.0.0` como alvo).
- `GET /go2rtc/discovery/onvif/scan` varre faixa de IP controlada, host a host, chamando go2rtc `GET /api/onvif?src=...`.
- Diferença de fluxos:
  - ONVIF por IP (`src`) = recomendado;
  - ONVIF scan de rede = avançado/lento, depende de firewall/ONVIF ativo/credencial informada.
- `0.0.0.0` representa todas as interfaces locais, não um IP de câmera.
- Senha não é retornada no JSON do scan e não deve aparecer em logs.
