# ONVIF Bridge (PoC) — GatwayWG

## Objetivo

Este módulo cria um **serviço ONVIF isolado** para compatibilidade com DVR (ex.: Intelbras MHDX) via **IP virtual**, sem alterar o fluxo principal do Gateway.

- Não substitui o go2rtc.
- Não altera `/cameras/` do FastAPI principal.
- Não altera o contrato RTSP canônico já existente:
  - `rtsp://<gateway_ip>:8554/<camera_uuid>`

## Arquitetura

- **go2rtc** continua sendo o core de vídeo/RTSP.
- **Gateway principal (FastAPI)** continua como cadastro/inventário.
- **onvif_bridge** responde SOAP ONVIF mínimo por IP virtual.

## Configuração

1. Copie `onvif_bridge_config.example.json` para `onvif_bridge_config.json`.
2. Ajuste os campos:
   - `gateway_ip`
   - `rtsp_port` (8554)
   - `http_port` (8080 no PoC)
   - `auth_user` / `auth_pass`
   - `devices[]` com `virtual_ip` -> `camera_uuid`

Pode definir caminho por variável:

```bash
export ONVIF_BRIDGE_CONFIG=onvif_bridge/onvif_bridge_config.json
```

## Subir o serviço

```bash
uvicorn onvif_bridge.main:app --host 0.0.0.0 --port 8080
```

## Endpoints internos

- `GET /onvif-bridge/health`
- `GET /onvif-bridge/devices`
- `POST /onvif/device_service`
- `POST /onvif/media_service`

## IP virtual

### Windows (exemplo)

- Painel de rede -> adaptador -> IPv4 -> Avançado -> adicionar IP secundário.
- Alternativa PowerShell (como admin), conforme política local de rede.

### Linux (exemplo)

```bash
sudo ip addr add 192.168.10.201/24 dev eth0
```

> Ajuste interface e máscara conforme sua rede.

## Cadastro no DVR Intelbras

- Protocolo: **ONVIF**
- IP: `<virtual_ip>`
- Porta HTTP: `8080` (PoC)
- Porta RTSP: `8554` (ou auto-adaptativo)
- Usuário: `auth_user`
- Senha: `auth_pass`
- Canal remoto: `1`
- Tipo de servidor: `TCP`

## Nota sobre porta 80

Não usar 80 como padrão no PoC.

- Porta 80 pode exigir privilégio/admin e conflitar no host.
- Se DVR exigir 80, avaliar execução com privilégio ou portproxy/NAT.
