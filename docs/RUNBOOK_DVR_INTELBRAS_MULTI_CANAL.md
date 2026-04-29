# RUNBOOK — DVR Intelbras Multi-Canal (1 IP ONVIF / múltiplos canais)

## Objetivo

Preparar homologação com **1 IP ONVIF** no DVR Intelbras e múltiplos canais remotos mapeados para UUIDs distintos, preservando o contrato:

`rtsp://<gateway_ip>:8554/<camera_uuid>`

## Arquitetura operacional (regra de ouro)

- **go2rtc + Gateway**: servem vídeo real (producer/consumer RTSP)
- **ONVIF Bridge**: responde SOAP/Device/Media e entrega `GetStreamUri`
- **DVR Intelbras**: consome RTSP do go2rtc via URI retornada no ONVIF

> Para teste DVR, **não usar `/stream/<uuid>`**.
> Esse endpoint pode usar caminhos de emulação (ex.: Decord/OpenCV fallback) e não representa o fluxo RTSP real do DVR.

## Estratégia de canais (fase atual)

- 1 IP do ONVIF Bridge, ex.: `192.168.10.106`
- Canal remoto 1 -> `camera_uuid_1`
- Canal remoto 2 -> `camera_uuid_2`
- ... até 10 canais por IP (planejamento)
- Escala futura: adicionar outro IP virtual ONVIF para próximos 10 canais

## Matriz de portas (homologação)

- Gateway API: `8000`
- go2rtc API: `1984`
- go2rtc RTSP: `8554`
- go2rtc WebRTC: `8555`
- onvif_bridge HTTP/ONVIF: `8080`

## Fluxo correto de validação

1. Subir go2rtc.
2. Validar `http://127.0.0.1:1984/api/streams`.
3. Validar stream base abre no VLC.
4. Validar alias UUID abre no VLC.
5. Subir Gateway.
6. Subir ONVIF Bridge.
7. Cadastrar no DVR (canal remoto 1).
8. Verificar `consumers` no go2rtc durante visualização do DVR.

## Teste VLC obrigatório (pré-DVR)

- Base: `rtsp://admin:Conectar@<gateway_ip>:8554/<stream_base>`
- UUID: `rtsp://admin:Conectar@<gateway_ip>:8554/<camera_uuid>`

Se UUID falhar, primeiro corrigir base stream/producer antes de depurar ONVIF.

## Recomendação de limpeza de go2rtc (sem alteração automática)

No ambiente de homologação:

- remover câmeras falsas antigas
- manter somente streams necessários para teste
- garantir que **stream base existe antes do alias UUID**

## Exemplo de cadastro no DVR (conceitual)

- Dispositivo ONVIF: `<gateway_ip>:8080`
- Canal remoto 1: UUID da câmera 1
- Canal remoto 2: UUID da câmera 2
- Transporte: TCP

## Riscos comuns

1. ONVIF funciona, mas sem vídeo: base stream ausente/offline.
2. Alias UUID cadastrado sem producer ativo no base stream.
3. Teste via `/stream/<uuid>` mascarando problema real de RTSP/go2rtc.
4. Porta RTSP divergente do contrato (deve ser 8554).

## Critério de pronto para DVR

- `/api/streams` exibe base + UUID
- VLC abre base + UUID
- `consumers` cresce ao abrir no VLC
- somente então validar canal remoto no DVR
