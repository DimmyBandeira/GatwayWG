# Arquitetura Técnica do Gateway

## 1. Visão Geral (Decoupled Middleware)
O Gateway atua como uma camada de isolamento entre o hardware físico e a lógica de negócio do WebGuardião. Ele é responsável por garantir que o processamento pesado de vídeo aconteça de forma otimizada antes de chegar à interface ou ao banco de dados.

## 2. Fluxo de Processamento em Lote (Batching)
Para maximizar a eficiência da GPU (NVIDIA), o sistema não processa câmeras isoladamente:
1. Os `Workers` capturam frames de múltiplas câmeras.
2. O `batch_manager.py` agrupa esses frames em um único tensor.
3. A inferência YOLO/DeepStream é executada uma única vez para o lote inteiro.
4. Os resultados são distribuídos via `event_bus.py`.

## 3. Topologia de Vídeo (Monitores Virtuais)
O recurso de **VideoWall** permite que o Gateway crie um stream composto (mosaico):
- **Entrada**: 16 streams RTSP independentes.
- **Processamento**: `virtual_display.py` monta uma grade 4x4.
- **Saída**: 1 stream de alta resolução para o VideoWall ou para a IA analisar simultaneamente.

## 4. Sistema de Plugins
A extensibilidade é garantida por uma classe abstrata em `base_plugin.py`. Qualquer novo recurso deve implementar os métodos:
- `on_frame_received()`: Para análise em tempo real.
- `on_event_triggered()`: Para comunicação com o dispatcher de alertas.

## 5. Escalabilidade (Cluster Mode)
O sistema pode operar em dois modos:
- **Standalone**: Ideal para clínicas pequenas ou servidores únicos.
- **Cluster**: O `master_node` gerencia o balanceamento de carga entre vários `workers` em rede.

## Topologia Técnica do Gateway

## 1. Fluxo de Dados e Cluster
[cite_start]O Gateway opera como um middleware desacoplado[cite: 197]. [cite_start]O `master_node` recebe as solicitações do WebGuardião e distribui o processamento entre os `worker_nodes`[cite: 299, 300].

## 2. Ingestão e Saída de Vídeo
- [cite_start]**Entrada (Input)**: Ingestão multisource (IP, USB, Arquivos) via `capture_engine.py`[cite: 320].
- [cite_start]**Processamento**: Agrupamento de frames via `batch_manager.py` para inferência rápida[cite: 296, 324].
- [cite_start]**Saída (Output)**: Entrega WebRTC para UI e RTSP Proxy para VMS/IA externo[cite: 321, 322].

## 3. Resiliência
[cite_start]Implementação de **Watchdog e Health Check** em `pipeline_manager.py` para monitorar conexões proativamente[cite: 271, 329].

## Evolução do tema

# Architecture Topology - Semantic Agent Mapping

<DataFlowTopology>
  <InboundSources>
    <Source type="IP_CAMERA">RTSP/ONVIF com Discovery+ (Informação de Hardware nativa)[cite: 94, 809].</Source>
    <Source type="USB_WEBCAM">V4L2 nativo via go2rtc para performance industrial[cite: 10, 858].</Source>
    <Source type="EMULATION">Arquivos .mp4 via Decord para testes de estresse em massa[cite: 96, 751].</Source>
  </InboundSources>

  <InternalRouting>
    <Endpoint id="API_MGMT" port="1984">Gestão, Monaco Editor e Discovery Automático[cite: 99, 108, 805].</Endpoint>
    <Endpoint id="IA_RTSP" port="8554">Stream RTSP Local. Destinado ao YOLO para garantir estabilidade de conexão[cite: 73, 100].</Endpoint>
    <Endpoint id="USER_WEBRTC" port="8555">Stream WebRTC. Ultra baixa latência para monitoramento hospitalar[cite: 68, 101, 207].</Endpoint>
  </InternalRouting>

  <ProcessLogic>
    <IA_Stream_Specialization>
      O sistema utiliza RTSP via Localhost para a IA, evitando decodificações WebRTC complexas no Python e garantindo reconexão automática[cite: 73, 76].
    </IA_Stream_Specialization>
    <User_RealTime_Specialization>
      O usuário consome WebRTC nativo do go2rtc, garantindo latência zero no monitoramento de UTIs[cite: 68, 70].
    </User_RealTime_Specialization>
  </ProcessLogic>
</DataFlowTopology>

<SecurityHardening>
  [cite_start]<Feature>Local_auth para proteção da API administrativa[cite: 12, 829].</Feature>
  [cite_start]<Feature>Allow_paths para restringir o acesso a binários e scripts do sistema[cite: 12, 829].</Feature>
</SecurityHardening>

<FutureScaleParameters>
  <Parameter name="batch_size" status="DORMANT" default="1" />
  <Parameter name="cluster_node" type="Worker" status="DORMANT" />
</FutureScaleParameters>