# GAT-13 — ONVIF Bridge Debug Técnico

## Objetivo do GAT-13

Permitir que DVR Intelbras MHDX consuma streams do GatwayWG via ONVIF Bridge sem quebrar o fluxo existente de WebGuardião/go2rtc.

## Relação com GAT-4

- GAT-4 consolidou o contrato canônico RTSP por UUID.
- GAT-13 complementa com camada de compatibilidade ONVIF para DVR legado.

## Arquitetura

`DVR Intelbras -> ONVIF Bridge -> go2rtc -> RTSP UUID`

## Contrato preservado

`rtsp://<gateway_ip>:8554/<camera_uuid>`

## Comandos usados

```powershell
uvicorn onvif_bridge.main:app --host 0.0.0.0 --port 8080 --reload
Invoke-RestMethod http://127.0.0.1:8080/onvif-bridge/health
Invoke-RestMethod -Method DELETE http://127.0.0.1:8080/onvif-bridge/debug/last-requests
Invoke-RestMethod http://127.0.0.1:8080/onvif-bridge/debug/last-requests
```

## Evidências de log

Exemplo validado em campo:
- `client_ip=192.168.10.136`
- `host=192.168.10.106`
- `path=/onvif/device_service`
- `method=POST`

## Sequência ONVIF identificada

- `GetSystemDateAndTime`
- `GetServices`
- `GetCapabilities`

## Diagnóstico do 401

- O bridge estava retornando `401 Unauthorized` cedo no handshake.
- Isso interrompia o avanço para operações MEDIA.

## Conclusão

Autenticação prematura no handshake ONVIF DEVICE.

## Correção aplicada

No `auth_mode=basic`, as operações iniciais abaixo passaram a ser permissivas (sem 401):
- `GetSystemDateAndTime`
- `GetServices`
- `GetCapabilities`

Mantido:
- `auth_mode=none` totalmente permissivo.
- Estrutura preparada para evolução WS-Security futura, sem validação rígida nesta etapa.

## Próximo fluxo esperado

`GetSystemDateAndTime -> GetServices -> GetCapabilities -> GetProfiles -> GetStreamUri`

## Observabilidade mantida

- `GET /onvif-bridge/health`
- `GET /onvif-bridge/debug/last-requests`
- `DELETE /onvif-bridge/debug/last-requests`

## Escopo preservado

Sem alterações em:
- `go2rtc`
- `/cameras/`
- `/cameras/{uuid}/urls`
- contrato RTSP UUID
- WebGuardião
