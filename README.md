# DataWave — Inteligência Aduaneira e Otimização Logística Portuária

> **Porto Hack Santos 2026**  
> Solução integrada para mitigação de riscos regulatórios no Catálogo de Produtos da DUIMP e otimização de custos de permanência portuária (Cais vs. Retroporto).

---
*versão em inglês:* [here](https://github.com/giuliagranado/PortoHack-2026/blob/main/readme_english.md)


## 1. Visão Geral e Problema Enfrentado

A importação marítima de cargas conteinerizadas pelo Porto de Santos enfrenta dois gargalos operacionais críticos que acarretam prejuízos financeiros severos:

1. **Erros e Exigências Fiscais no Catálogo de Produtos da DUIMP:** O preenchimento incorreto de atributos regulatórios, divergências entre documentos de embarque (Conhecimento de Embarque/BL, Fatura Comercial/Invoice e Romaneio de Carga/Packing List) ou formatações desalinhadas ao padrão do Portal Único Siscomex geram parametrização em canais de conferência física (canal vermelho) ou bloqueios por órgãos intervenientes (Receita Federal, MAPA, Anvisa, Inmetro, Ibama).
2. **Estouro de Free Time e Custos de Sobre-estadia:** A retenção da carga na zona primária (cais) submete o importador a tabelas de armazenagem progressiva agressivas e sobre-estadia de contêineres (*demurrage* do contêiner cheio e *detention* do contêiner vazio) tarifadas em dólares americanos, que frequentemente superam a margem operacional de toda a operação comercial.

O **DataWave** resolve essa dor por meio de uma arquitetura híbrida de alta confiabilidade: um **motor determinístico de cálculo, auditoria e risco em Python** combinado com um **Agente Inteligente de Comércio Exterior na plataforma Logcomex** conectado via MCP (*Model Context Protocol*).

---

## 2. Arquitetura da Solução

O sistema adota o princípio de **soberania de cálculo determinístico**: modelos de linguagem operam nas bordas (leitura de documentos, consulta de mercado e sugestão de atributos), enquanto toda regra fiscal, validação normativa, simulação estocástica e cálculo financeiro reside no código auditável do motor local.

```
                  ┌──────────────────────────────────────────────────┐
                  │          PAINEL EXECUTIVO / USUÁRIO              │
                  │         (Interface Web Interativa)               │
                  └────────────────────────┬─────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PIPELINE ORQUESTRADOR                                  │
│                                (datawave/pipeline.py)                                  │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│                                          │                                             │
│  MOTOR DETERMINÍSTICO (PYTHON)           │  AGENTE LOGCOMEX (CONEXÃO MCP)              │
│  - Engine de Risco (Monte Carlo)         │  - U1: Inteligência de Mercado / NCM        │
│  - Engine de Custos (Cais x Retroporto)  │  - U2: Leitura de BL, Invoice e Romaneio    │
│  - Engine de Ponto de Equilíbrio         │  - U3: Sugestão de Atributos do Catálogo    │
│  - Parser de Planilhas e Divergências    │  - U4: Redação de Parecer Executivo         │
│  - Gerador de Parecer Técnico            │                                             │
│                                          │  CLIENTE DESACOPLADO (agent_client.py)      │
│  TRILHA DE AUDITORIA                     │  - LogcomexMCPAgent (Produção ao vivo)      │
│  - Logs estruturados em JSONL (trace_id) │  - FakeAgent (Fixtures reais e offline)     │
└──────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 3. Módulos do Motor Determinístico (`datawave/engine/`)

### 3.1 Simulação de Risco e Permanência (`risk.py`)
- Simulação estocástica de Monte Carlo (5.000 iterações por execução) para projeção de tempo de permanência (*dwell time*) da carga no cais.
- Incorpora *priors* empíricos de canais de parametrização (Verde, Amarelo, Vermelho e Cinza) e tempo de resposta de órgãos anuentes (MAPA, Anvisa, Inmetro, Ibama, Vigiagro).
- Modela matematicamente o benefício regulatório da certificação de Operador Econômico Autorizado (OEA), reduzindo probabilidade de inspeção e prazos de liberação.
- Saída estocástica com curva percentual (P50, P75, P90) e probabilidade objetiva de estouro do período livre (*free time*).

### 3.2 Matriz de Custos e Break-Even (`cost.py`)
- Separação rigorosa entre:
  - **Demurrage:** sobre-estadia do contêiner cheio até a desova ou desembaraço na zona primária.
  - **Detention:** sobre-estadia do contêiner vazio até a devolução efetiva no terminal de vazios (*depot*).
- Cálculo dinâmico da tabela progressiva de armazenagem portuária do cais em Santos por períodos tarifários.
- Matriz de custos de transferência para zona secundária (retroporto / CLIA), contabilizando armazenagem linear, frete de remoção local, seguro de trânsito, Declaração de Trânsito Aduaneiro (DTA) e taxas de redespacho.
- Cálculo analítico do dia exato de ponto de equilíbrio (*break-even day*) e valor da economia líquida projetada.

### 3.3 Normalizador e Parser de Planilhas Aduaneiras (`spreadsheet_parser.py`)
- Ingestão resiliente de planilhas de despachantes em formatos CSV, TSV e JSON.
- Mapeamento semântico automático de sinônimos de cabeçalhos de colunas do comércio exterior brasileiro e internacional.
- Conversão segura de representações numéricas (formato brasileiro com vírgula e formato internacional com ponto).
- Consolidação e extração automatizada de inconsistências documentais entre peso bruto de BL e peso de Packing List.

### 3.4 Relatório Executivo e Transparência (`report.py`)
- Geração determinística de parecer executivo estruturado via modelo Pydantic (`ParecerExecutivo`).
- Validação mecânica que impede discrepâncias numéricas entre o texto recomendado e os valores calculados pelos motores.
- Rotulagem explícita de cada fonte de dados (dado real Logcomex, premissa regulatória ou valor simulado).

---

## 4. Agente Logcomex e Matriz de Skills

O sistema conecta-se ao ecossistema da Logcomex via MCP (*Model Context Protocol*), com suporte a quatro fluxos operacionais estruturados:

| Fluxo | Objetivo | Skill Envolvida | Modelo Pydantic de Validação |
|---|---|---|---|
| **U1** | Inteligência de Mercado / NCM | Inteligência de Embarques Brasil | `MercadoNCM` |
| **U2** | Conferência Cruzada Documental | Supply Chain / Análise Documental | `OperacaoExtraida` |
| **U3** | Sugestão e Auditoria de Atributos | Catálogo de Produtos DUIMP | `SugestaoAtributos` |
| **U4** | Justificativa Executiva | Análise Aduaneira Executiva | Validação estruturada via `report.py` |

### Resiliência e Desacoplamento (`agent_client.py`)
Para assegurar a disponibilidade total do sistema durante auditorias e demonstrações:
- **`LogcomexMCPAgent`:** Gerencia a comunicação assíncrona com os agentes em nuvem da Logcomex, executando autenticação OAuth, sanitização de respostas e reprocessamento com correção de formato caso ocorram bloqueios de guardrails.
- **`FakeAgent`:** Provedor determinístico offline alimentado por amostras reais gravadas em `fixtures/agent/`, permitindo testes unitários e execuções completas do pipeline sem necessidade de conectividade externa.

---

## 5. Interface Interativa e Servidor API

O DataWave inclui uma interface executiva interativa para tomada de decisão e validação de cenários logísticos:

- **Dashboard Executivo (`index.html`):** Painel visual completo com chaveamento dinâmico entre 4 rotas estratégicas reais e simuladas no Porto de Santos (Vinho Argentino via MSC, Fertilizantes com inspeção MAPA, Químicos OEA e Carga Geral).
- **Simulador Interativo:** Ajuste em tempo real de taxas cambiais (USD/BRL), dias de free time concedidos pelo armador, valores de diária e status de parametrização da carga.
- **Servidor Híbrido (`main.py`):** Operação sob FastAPI com suporte a endpoints REST (`/api/simular`, `/api/pipeline`, `/api/despachante/processar-planilha`, `/api/chat`) e mecanismo de fallback automático para servidor HTTP nativo em ambientes com restrição de bibliotecas.

---

## 6. Estrutura do Repositório

```
PortoHack-2026/
├── README.md                                # Documentação mestre do projeto
├── .gitignore                               # Diretivas de exclusão do Git
├── docs/                                    # Documentação técnica, pesquisa de campo e relatórios
│   ├── PH2026_E1_PESQUISA_DATAWAVE.pdf      # Relatório executivo consolidado da pesquisa de campo
│   ├── pesquisa_setorial_porto_hack_santos_2026.md # Base analítica e dados setoriais do Porto de Santos
│   └── prototipo-pesquisa-campo.md          # Documentação das entrevistas de campo com despachantes
├── scripts/                                 # Scripts utilitários de suporte e pesquisa
│   └── gerar_copies_pesquisa_porto_hack.py  # Automação de síntese da pesquisa
└── datawave/
    ├── main.py                              # Servidor da API e entrega do frontend executivo
    ├── pipeline.py                          # Pipeline orquestrador end-to-end com trilha de auditoria
    ├── schemas.py                           # Contratos formais de dados e validação Pydantic
    ├── agent_client.py                      # Cliente de integração MCP (LogcomexMCPAgent e FakeAgent)
    ├── auth_manager.py                      # Gerenciador de credenciais e fluxo OAuth do MCP
    ├── autenticar_mcp.py                    # Script utilitário para autenticação interativa
    ├── index.html                           # Painel executivo interativo e visualizador de cenários
    ├── mock_scenarios.json                  # Especificação dos cenários estratégicos do porto
    ├── catalogo_produtos_vinhos.csv         # Amostra real para auditoria de atributos da DUIMP
    ├── data/
    │   ├── risk_priors.yaml                 # Priors empíricos de canais e prazos por NCM
    │   └── tarifas.yaml                     # Tabelas vigentes de armazenagem e taxas portuárias
    ├── docs/
    │   └── plano-agente-datawave.md         # Especificação detalhada de arquitetura e guardrails
    ├── engine/
    │   ├── cost.py                          # Motor de custos de cais, retroporto e break-even
    │   ├── risk.py                          # Motor estocástico de risco (Monte Carlo)
    │   ├── report.py                        # Gerador determinístico de parecer técnico
    │   └── spreadsheet_parser.py            # Normalizador e ingestor de planilhas de despachantes
    ├── fixtures/
    │   └── agent/                           # Amostras reais para operação offline do FakeAgent
    │       ├── u1_mercado_ncm.json
    │       ├── u2_conferencia_documental.json
    │       ├── u3_sugestao_atributos.json
    │       └── u4_justificativa_executiva.json
    ├── skills/
    │   ├── 01_catalogo_produtos_duimp.md    # Skill de contexto: regras cadastrais DUIMP
    │   ├── 02_contrato_saida_json.md        # Skill de contexto: schemas e contratos de resposta
    │   ├── 03_glossario_premissas_cais_retroporto.md # Skill: premissas operacionais de Santos
    │   └── 04_playbook_extracao_documental.md # Skill: matriz de conferência cruzada
    ├── skills_prontas_para_copiar.md        # Gabarito formatado para implantação direta na Logcomex
    └── tests/                               # Suíte com testes automatizados
        ├── test_agent_client.py
        ├── test_api.py
        ├── test_cost_engine.py
        ├── test_report_pipeline.py
        ├── test_risk_engine.py
        ├── test_schemas.py
        └── test_spreadsheet_parser.py
```

---

## 7. Como Executar

### 7.1 Pré-requisitos
- Python 3.10 ou superior
- Gerenciador de pacotes `pip`

### 7.2 Instalação das Dependências
Instale as bibliotecas necessárias para execução completa:

```bash
pip install pydantic pyyaml pytest fastapi uvicorn
```

*(Nota: Caso `fastapi` e `uvicorn` não estejam instalados, o sistema ativa automaticamente seu servidor HTTP nativo).*

### 7.3 Execução da Aplicação e Painel Interativo
Para iniciar a API e a interface executiva local:

```bash
python datawave/main.py
```

Em seguida, abra o navegador e acesse:
```
http://localhost:8000
```

### 7.4 Execução dos Testes Automatizados
O projeto conta com **46 testes automatizados** cobrindo todos os módulos do motor determinístico, schemas de validação, tratamento de erros e integração do pipeline.

Para rodar a suíte completa com relatório detalhado:

**No Windows (PowerShell):**
```powershell
$env:PYTHONPATH="."; pytest -v
```

**No Linux ou macOS:**
```bash
PYTHONPATH=. pytest -v
```

---

## 8. Diretrizes de Governança e Qualidade

- **Soberania Determinística:** Nenhuma decisão financeira, cálculo de armazenagem ou recomendação de transferência é delegada a probabilidades ou alucinações de modelos de linguagem.
- **Rastreabilidade e Auditoria:** Cada execução do pipeline gera um identificador único de rastreio (`trace_id`) e grava sua respectiva trilha de eventos no formato estruturado JSONL (`datawave/logs/pipeline_runs.jsonl`).
- **Conformidade Regulatória:** Estrito alinhamento às normativas da Receita Federal do Brasil, tabelas de tarifas vigentes dos terminais de Santos e padrões de atributos do Portal Único Siscomex.
