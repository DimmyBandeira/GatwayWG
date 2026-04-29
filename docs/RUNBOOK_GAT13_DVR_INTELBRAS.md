# RUNBOOK — Homologação GAT-13/GAT-4 (DVR Intelbras)

## 1) Objetivo

Este runbook define o passo a passo operacional para homologar a stack completa:

- go2rtc (core de vídeo)
- Gateway API principal (cadastro/provisionamento)
- onvif_bridge (resposta ONVIF para DVR)
- teste com stream de arquivo
- teste com câmera RTSP real
- validação final no DVR Intelbras

> Princípio: **primeiro validar vídeo no go2rtc/VLC**, depois validar ONVIF/DVR.

---

## 2) Matriz de portas (padrão homologação)

| Componente | Porta | Uso |
|---|---:|---|
| Gateway API | 8000 | API de gestão/cadastro/provisionamento |
| go2rtc API | 1984 | API de streams/estado |
| go2rtc RTSP | 8554 | saída RTSP (base e UUID) |
| go2rtc WebRTC | 8555 | saída WebRTC |
| onvif_bridge HTTP | 8080 | endpoint ONVIF para DVR |

---

## 3) Pré-requisitos

1. Host com `ffmpeg` disponível em PATH (para fluxos `source_type=file`).
2. Binário do go2rtc disponível no host.
3. Python/venv com dependências do GatwayWG instaladas.
4. Acesso de rede do DVR para:
   - `<gateway_ip>:8080` (ONVIF bridge)
   - `<gateway_ip>:8554` (RTSP go2rtc)

---

## 4) Sequência obrigatória de subida (NÃO inverter)

A. subir go2rtc  
B. subir Gateway  
C. cadastrar/provisionar stream  
D. validar VLC stream_base  
E. validar VLC camera_uuid  
F. subir onvif_bridge  
G. cadastrar no DVR

---

## 5) Comandos PowerShell — subida dos serviços

## 5.1 Subir go2rtc

```powershell
# Exemplo 1 (simples)
.\go2rtc.exe

# Exemplo 2 (com config explícita)
.\go2rtc.exe -c .\go2rtc.yaml
```

## 5.2 Subir Gateway API principal

```powershell
# Na pasta do projeto GatwayWG
$env:GO2RTC_API_BASE_URL="http://127.0.0.1:1984"
$env:GO2RTC_RTSP_PORT="8554"
$env:GO2RTC_WEBRTC_PORT="8555"
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## 5.3 Subir ONVIF Bridge

```powershell
# Em outro terminal, na pasta do projeto
$env:ONVIF_BRIDGE_CONFIG="onvif_bridge/onvif_bridge_config.json"
uvicorn onvif_bridge.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 6) Cadastro/provisionamento de stream — cenário A (arquivo)

> Objetivo: validar pipeline completo mesmo sem câmera física.

### 6.1 Payload de referência (Gateway)

```json
{
  "name": "Cam Arquivo 01",
  "source_type": "file",
  "streams": {
    "visible": {
      "main": {
        "stream_name": "cam_arquivo_01_main",
        "source_url": "C:/videos/demo.mp4"
      }
    }
  }
}
```

### 6.2 Resultado esperado no provisionamento

Para `source_type=file`, o Gateway deve normalizar para formato `exec` canônico:

```text
exec:ffmpeg -re -stream_loop -1 -i <file> -c copy -rtsp_transport tcp -f rtsp {output}
```

---

## 7) Cadastro/provisionamento de stream — cenário B (câmera RTSP real)

### 7.1 Exemplo de source_url base

```text
rtsp://usuario:senha@ip_camera:554/Streaming/Channels/101
```

### 7.2 Regras

- `stream_base` deve abrir no VLC primeiro.
- Alias `camera_uuid` deve abrir no VLC em seguida.
- Só então seguir para ONVIF/DVR.

---

## 8) Checklist operacional obrigatório (gates)

## Gate 1 — Saúde dos serviços

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/go2rtc/health
Invoke-RestMethod http://127.0.0.1:8080/onvif-bridge/health
```

Critério:
- Gateway responde 200
- go2rtc online=true
- onvif_bridge responde 200

## Gate 2 — Estado de streams no go2rtc

```powershell
Invoke-RestMethod http://127.0.0.1:1984/api/streams
```

Critério:
- `stream_base` existe
- `camera_uuid` existe
- pelo menos um producer válido por stream

## Gate 3 — Diagnóstico consolidado por UUID

```powershell
Invoke-RestMethod http://127.0.0.1:8000/go2rtc/diagnostics/<camera_uuid>
```

Critério:
- `checks.base_stream_ok = true`
- `checks.alias_ok = true`

## Gate 4 — VLC (vídeo real)

Testar no VLC:

1. `rtsp://<gateway_ip>:8554/<stream_base>`
2. `rtsp://<gateway_ip>:8554/<camera_uuid>`
3. Se RTSP auth estiver ativa no go2rtc: `rtsp://admin:Conectar@<gateway_ip>:8554/<stream_base>`
4. Se RTSP auth estiver ativa no go2rtc: `rtsp://admin:Conectar@<gateway_ip>:8554/<camera_uuid>`

Critério:
- ambos devem abrir com vídeo antes de prosseguir

## Gate 5 — Debug ONVIF

```powershell
# limpar buffer
Invoke-RestMethod -Method DELETE http://127.0.0.1:8080/onvif-bridge/debug/last-requests

# ler buffer
Invoke-RestMethod http://127.0.0.1:8080/onvif-bridge/debug/last-requests
```

Critério:
- operações ONVIF aparecem no debug sem 401 prematuro no handshake inicial

## Gate 6 — Consumers no go2rtc (durante teste DVR)

```powershell
Invoke-RestMethod http://127.0.0.1:1984/api/streams
```

Critério:
- durante conexão do DVR, stream de destino apresenta consumer ativo (não nulo)

## Gate 7 — Checklist Intelbras específico (pré-DVR)

1. Subir go2rtc.
2. Consultar `http://127.0.0.1:1984/api/streams`.
3. Validar `cam_uti_01-file-main` existe.
4. Validar `3226ea01-0954-44bb-b782-506534f1a94a` existe.
5. Testar no VLC:
   - `rtsp://admin:Conectar@<gateway_ip>:8554/cam_uti_01-file-main`
   - `rtsp://admin:Conectar@<gateway_ip>:8554/3226ea01-0954-44bb-b782-506534f1a94a`
6. Só depois testar DVR Intelbras.

---

## 9) Cadastro no DVR Intelbras (somente após gates)

1. Adicionar dispositivo ONVIF apontando para `<gateway_ip>:8080`.
2. Confirmar descoberta e seleção do canal.
3. Validar visualização ao vivo.

Se não houver vídeo:
- voltar ao Gate 2/3/4 (go2rtc + VLC) antes de investigar ONVIF.

---

## 10) Troubleshooting rápido

## Sintoma: ONVIF chega em GetStreamUri, mas sem vídeo

Ações:
1. Verificar `GET /go2rtc/diagnostics/<camera_uuid>`.
2. Verificar `/api/streams` para producer/consumer.
3. Validar VLC base e UUID.
4. Só então revisar payload ONVIF.

## Sintoma: UUID abre, mas base não abre

Ações:
1. Rever source_url original cadastrado.
2. Rever disponibilidade da câmera/arquivo de origem.
3. Rever conectividade do host para origem RTSP.

## Sintoma: stream file não inicia

Ações:
1. Confirmar caminho do arquivo no host.
2. Confirmar `ffmpeg` no PATH.
3. Confirmar comando normalizado com `{output}`.

---

## 11) Regra de ouro da homologação

- **Quem serve vídeo é o go2rtc**.
- **Quem responde ONVIF é o onvif_bridge**.
- **Quem gerencia cadastro/provisionamento é o Gateway API**.

Sem os três serviços ativos e consistentes, o DVR pode negociar ONVIF, mas não exibirá vídeo.
