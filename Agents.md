# AGENTS.md — GatwayWG (Strict Execution Contract)

## 🎯 SYSTEM ROLE (NON-NEGOTIABLE)

O GatwayWG é um **Video Gateway**.

Ele NÃO executa:
- IA
- YOLO
- DeepStream
- análise de frames
- lógica de detecção

Toda IA pertence EXCLUSIVAMENTE ao sistema **WebGuardião**.

---

## 🧱 CORE ARCHITECTURE

### Fonte única de vídeo

O sistema deve usar obrigatoriamente:

- go2rtc como camada central de ingestão e distribuição

NÃO usar como core:
- OpenCV (cv2.VideoCapture)
- PyAV
- Decord

Esses só podem existir como:
- fallback experimental
- ambiente de teste

---

## 🔌 VIDEO CONTRACT (MANDATORY)

Toda câmera deve ser acessada via:


rtsp://<gateway_ip>:8554/<camera_uuid>


Esse contrato deve servir para:

- WebGuardião (IA)
- iVMS
- DVRs
- VMS externos

---

## 📡 OUTPUT CHANNELS

O Gateway deve fornecer:

| Tipo        | Destino           |
|------------|------------------|
| RTSP       | IA / DVR / VMS   |
| WebRTC     | Interface usuário|
| MJPEG      | Debug            |

---

## 🚫 HARD PROHIBITIONS

O agente NÃO pode:

- Implementar IA no Gateway
- Ativar YOLO ou qualquer inferência
- Integrar DeepStream nesta fase
- Criar lógica de detecção
- Processar bounding box
- Alterar fluxo para análise de imagem

Se qualquer tarefa envolver análise de imagem → REJEITAR.

---

## ⚙️ API RESPONSIBILITY

O FastAPI deve apenas:

- cadastrar câmeras
- listar câmeras
- fornecer status
- expor URLs de stream

NÃO deve:
- processar frames
- manipular imagem
- rodar inferência

---

## 🧠 CAMERA ABSTRACTION

Toda câmera deve ser tratada como:


camera_uuid


Nunca depender de:
- IP diretamente
- credenciais hardcoded
- lógica fora do registry

---

## 📂 FILE MODIFICATION RULES

- Sempre aplicar **DIFF MÍNIMO**
- NÃO refatorar arquivos grandes sem solicitação explícita
- NÃO mover arquivos sem necessidade
- NÃO quebrar estrutura existente

---

## 🧪 CURRENT PHASE (MANDATORY)

### Fase 1 — MVP Gateway

Implementar apenas:

- integração com go2rtc
- cadastro de câmeras
- persistência (json)
- health check
- entrega RTSP funcional

---

## 🧭 FUTURE (DO NOT IMPLEMENT NOW)

Permitido apenas documentar:

- DeepStream
- batching
- cluster
- VideoWall
- monitor virtual

PROIBIDO implementar qualquer um deles.

---

## 🔍 VALIDATION RULES

Toda mudança deve garantir:

1. RTSP continua funcionando
2. go2rtc permanece como core
3. Nenhuma IA foi adicionada
4. API continua leve
5. WebGuardião consegue consumir stream

---

## 🧨 FAILURE MODE

Se a tarefa violar qualquer regra acima:

→ NÃO IMPLEMENTAR  
→ EXPLICAR POR QUE  
→ SUGERIR ALTERNATIVA DENTRO DO ESCOPO  

---

## 📌 SUMMARY

GatewayWG = transporte de vídeo  
WebGuardião = inteligência  

Nunca misturar responsabilidades.