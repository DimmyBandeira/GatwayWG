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

## 3. Contrato de integração por UUID (padrão único)

### 3.1 Identificador canônico

- `camera_uuid` é o identificador único da câmera no GatwayWG.
- Consumidores externos **não** devem depender de IP/canal do fabricante como chave de integração.

### 3.2 Contrato de cadastro (exemplo)

**Request** (`POST /cameras/`):

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "name": "UTI-02-Leito-07",
  "type": "rtsp",
  "path": "rtsp://usuario:senha@192.168.10.20:554/Streaming/Channels/101",
  "node": "master",
  "pipeline": "go2rtc",
  "videoWall": false,
  "plugins": [],
  "createdAt": "2026-04-25T00:00:00Z"
}
```

**Response** (`201 Created`):

```json
{
  "status": "success",
  "uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 3.3 Contrato mínimo de inventário/saúde

- `GET /health` → status operacional da API de gestão.
- `GET /cameras/` → inventário de câmeras cadastradas.

### 3.4 Contrato de saída de stream por UUID

- **WebGuardião (IA externa):** `rtsp://<gateway_ip>:8554/<camera_uuid>`
- **iVMS/DVR/VMS:** `rtsp://<gateway_ip>:8554/<camera_uuid>`
- **Operação humana (baixa latência):** WebRTC (go2rtc)

### 3.5 Mapeamento mínimo de erros da API de cadastro

| Operação | Código | Quando ocorre | Ação recomendada |
|---|---|---|---|
| `POST /cameras/` | `400 Bad Request` | Payload inválido/ausente | Corrigir campos obrigatórios e formato. |
| `POST /cameras/` | `409 Conflict` | `camera_uuid` já cadastrado | Evitar duplicidade; atualizar registro existente. |
| `DELETE /cameras/{uuid}` | `404 Not Found` | UUID não encontrado no inventário | Reconciliar inventário local antes de remover. |

### 3.6 Convenção de nomenclatura (multi-site)

#### `camera_uuid`

- Deve ser estável e único globalmente (preferencialmente UUID v4).
- Não deve codificar semântica operacional mutável (ex.: ala/leito), apenas identidade técnica.

#### `name`

- Formato recomendado: `<site>-<setor>-<ponto>`.
- Exemplo: `hospital-a-uti02-leito07`.
- Usar letras minúsculas e hífen para padronizar pesquisa, filtros e inventário.

## 4. Matriz de compatibilidade de fontes (operação em campo)

| Fonte | Método de entrada | Status nesta fase | Observações operacionais |
|---|---|---|---|
| RTSP (IP Camera) | URL RTSP direta no go2rtc | Ativo (principal) | Melhor caminho para integração imediata por UUID. |
| ONVIF (IP Camera) | Descoberta/URL via ONVIF + go2rtc | Ativo | Útil para provisionamento e descoberta em rede local. |
| USB/V4L2 | Dispositivo local via FFmpeg/go2rtc | Ativo | Recomendado para câmeras locais e cenários de bancada. |
| Arquivo/Emulação | Arquivo de vídeo (loop) via FFmpeg/go2rtc | Ativo (laboratório) | Validar fluxo sem depender de hardware físico. |

## 5. Componentes não prioritários nesta fase

OpenCV, PyAV e Decord podem existir como fallback/laboratório, porém **não** definem o caminho principal de ingestão em produção.

## 6. Itens explicitamente fora do escopo atual

Os itens abaixo devem ser tratados como **roadmap**, não como comportamento ativo:

- inferência IA no gateway
- YOLO ativo
- DeepStream ativo
- processamento em lote (batching) ativo
- cluster ativo para processamento distribuído
- plugin analytics ativo
- VideoWall/monitor virtual em operação

## 7. Roadmap por fases

- **Fase 1 (atual):** go2rtc + RTSP/WebRTC + cadastro/persistência.
- **Fase 2:** integração WebGuardião por UUID.
- **Fase 3:** entrega RTSP para iVMS/DVR/VMS.
- **Fase 4:** VideoWall/monitor virtual.
- **Fase 5:** DeepStream/batching, se necessário.
