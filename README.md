# WebGuardião Video Gateway (Enterprise Edition) 🚀

Microserviço de alto desempenho projetado para ser o núcleo de ingestão, inteligência e distribuição de vídeo do ecossistema WebGuardião. Focado em escalabilidade horizontal, processamento em lote e extensibilidade por plugins.

## 🎯 Recursos Principais
- **Abstração de Hardware**: Consumo via `camera_uuid` para desacoplamento total.
- **Multisource Engine**: Ingestão de RTSP (Hikvision/Intelbras), USB e Emulação de arquivos (.mp4).
- **IA Batch Processing**: Otimizado para NVIDIA DeepStream/YOLO com processamento em lote.
- **Cluster Ready**: Arquitetura Master/Worker para escalabilidade horizontal.
- **VideoWall & Virtual Monitors**: Criação de mosaicos para inferência em massa.
- **Plugin System**: Arquitetura "acoplável" para novos módulos de análise.

## 🛠️ Stack Tecnológico
- **Linguagem**: Python 3.12+
- **Framework**: FastAPI (Gerenciamento e API)
- **Streaming**: go2rtc (WebRTC / RTSP Proxy)
- **Ingestão**: PyAV & Decord (Hardware Accelerated)
- **Discovery**: ONVIF-Zeep

## 📂 Topologia de Diretórios (Project Tree)
```text
webguardiao-gateway/
├── app.py                  # Entrypoint principal (Bootstrap FastAPI)
├── ui_app.py               # Wrapper para execução de interface local
├── README.md               # Documentação de visão geral
├── ARCHITECTURE.md         # Documentação técnica e topologia
├── cluster/
│   ├── master_node.py      # Orquestrador do cluster de processamento
│   └── worker_node.py      # Executor de tarefas em instâncias escravas
├── core/
│   ├── pipeline_manager.py  # Coordenador hot-swap de fluxos e threads
│   ├── batch_manager.py     # Gerencia lotes de frames para a GPU
│   ├── virtual_display.py   # Criação de mosaicos (VideoWall) para IA
│   └── event_bus.py         # Barramento de eventos assíncronos
├── services/
│   ├── capture_engine.py    # Motor de captura (Low-level Ingestion)
│   ├── emulation_service.py # Emulação de câmeras via arquivos locais
│   ├── discovery_service.py # Discovery automático (ONVIF)
│   └── registry_service.py  # Gestão de inventário e UUIDs
├── plugins/
│   ├── base_plugin.py       # Interface padrão para novos acoplamentos
│   └── analytics/           # Plugins específicos (Face, Fumaça, LPR)
├── integrations/
│   ├── go2rtc_client.py     # Middleware de streaming (WebRTC/RTSP)
│   └── webguardiao_api.py   # Ponte com o sistema central
└── utils/
    ├── video_tools.py       # Helpers para OpenCV e processamento de imagem
    └── logger.py            # Logs estruturados para diagnóstico


Infraestrutura de vídeo de nível industrial para o ecossistema WebGuardião.

## 🎯 Recursos Avançados
- [cite_start]**Clusterização Master/Worker**: Escalabilidade horizontal para múltiplos nós[cite: 326].
- [cite_start]**IA Batch Processing**: Otimização de GPU para processamento em lote[cite: 324].
- [cite_start]**Monitores Virtuais (VideoWall)**: Mosaicos para monitoramento em massa[cite: 327].
- [cite_start]**Sistema de Plugins**: Arquitetura desacoplada para novas análises (IA)[cite: 328].

## 📂 Topologia do Projeto (Tree)
- [cite_start]**cluster/**: Nós de orquestração e execução distribuída[cite: 326].
- [cite_start]**core/**: Inteligência de batching e criação de video-walls[cite: 324, 327].
- [cite_start]**plugins/**: Módulos acopláveis para análises específicas[cite: 328].
- [cite_start]**services/**: Motores de captura, emulação e descoberta ONVIF[cite: 319, 320].

#Evolução do sistema
# GatwayWG - Enterprise Video Gateway Context

<SystemDefinition>
  <ProjectName>GatwayWG</ProjectName>
  <Version>2.0.0-Semantic</Version>
  [cite_start]<CoreLogic>Abstração total de hardware de vídeo via UUID para o ecossistema WebGuardião[cite: 110, 452].</CoreLogic>
  [cite_start]<PrimaryMiddleware>go2rtc v1.9.14 (Jan 2026)[cite: 101, 799].</PrimaryMiddleware>
</SystemDefinition>

<AgentInstruction>
  [cite_start]<Constraint id="UUID_ONLY">Toda solicitação de vídeo deve ser processada via Camera_UUID, ignorando detalhes técnicos de IPs[cite: 110, 452].</Constraint>
  [cite_start]<Constraint id="BATCHING_DORMANT">O parâmetro de Batching deve ser aceito na estrutura, mas a implementação lógica permanece dormente nesta fase[cite: 35, 84].</Constraint>
  [cite_start]<Constraint id="COMPLIANCE_ON_PREM">O sistema deve operar 100% offline para garantir a privacidade hospitalar[cite: 185, 194, 465].</Constraint>
</AgentInstruction>

## 🎯 Recursos Principais (v1.9.14 Ready)
- [cite_start]**WebUI com Monaco Editor:** Validação e autocompletar nativo para evitar erros de sintaxe no YAML[cite: 805, 806].
- [cite_start]**ONVIF Discovery+:** Captura automática de nome e hardware (ex: Intelbras VIP na UTI 02)[cite: 104, 809].
- [cite_start]**Aceleração V4L2:** Suporte nativo para câmeras USB em H264/NV12 sem sobrecarga de CPU[cite: 10, 858].
- [cite_start]**WebRTC Listeners:** Lógica de escuta UDP/IPv6 reescrita para estabilidade total em redes virtuais[cite: 807, 808].

<ProjectTree>
  GatwayWG/
  [cite_start]├── app.py                  # Entrypoint FastAPI (Bootstrap e Orquestração)[cite: 545, 781]
  [cite_start]├── go2rtc.yaml             # Configuração do Middleware de Vídeo[cite: 564, 686]
  [cite_start]├── cadastro.html           # Interface Web de Gestão e Inventário[cite: 734, 735]
  [cite_start]├── cluster/                # Módulos para escalabilidade horizontal (Master/Worker)[cite: 433, 461]
  ├── services/
  [cite_start]│   ├── capture_engine.py   # Ingestão Low-level (PyAV/Decord/V4L2)[cite: 532, 751]
  [cite_start]│   └── registry_service.py # Gestão de inventário e Single Source of Truth[cite: 453, 544]
  ├── integrations/
  [cite_start]│   └── go2rtc_client.py    # Cliente API v1.9.14 (Discovery Automático)[cite: 701, 703]
  └── plugins/
      └── base_plugin.py       # Interface padrão para novos algoritmos de IA[cite: 440, 502]
</ProjectTree>