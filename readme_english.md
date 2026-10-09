# DataWave — Customs Intelligence and Port Logistics Optimization

> **Porto Hack Santos 2026**
>
> Integrated solution for mitigating regulatory risks in the DUIMP Product Catalog and optimizing port storage costs (Quay vs. Dry Port/Off-dock).

## 1. Overview and Problem Faced

Containerized maritime import through the Port of Santos faces two critical operational bottlenecks that lead to severe financial losses:

1. **Errors and Fiscal Demands in the DUIMP Product Catalog:** Incorrect filling of regulatory attributes, discrepancies between shipping documents (Bill of Lading/BL, Commercial Invoice, and Packing List), or formats misaligned with the Siscomex Single Window standard trigger parameterization into physical clearance channels (red channel) or blocks by intervening agencies (Federal Revenue, MAPA, Anvisa, Inmetro, Ibama).

2. **Free Time Expiry and Demurrage Costs:** Cargo retention in the primary zone (quay) subjects the importer to aggressive progressive storage tables and container demurrage (full container demurrage and empty container detention) billed in US dollars, which frequently exceed the operational margin of the entire commercial transaction.

**DataWave** solves this pain point through a high-reliability hybrid architecture: a **deterministic Python calculation, auditing, and risk engine** combined with an **Intelligent Foreign Trade Agent on the Logcomex platform** connected via MCP (*Model Context Protocol*).

## 2. Solution Architecture

The system adopts the principle of **deterministic calculation sovereignty**: language models operate at the edges (document reading, market consultation, and attribute suggestion), while all fiscal rules, normative validation, stochastic simulation, and financial calculation reside in the local engine's auditable code.

```
                  ┌──────────────────────────────────────────────────┐
                  │          EXECUTIVE / USER DASHBOARD              │
                  │         (Interactive Web Interface)              │
                  └────────────────────────┬─────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ORCHESTRATOR PIPELINE                                │
│                                (datawave/pipeline.py)                                  │
├──────────────────────────────────────────────┬─────────────────────────────────────────────────┤
│                                          │                                             │
│  DETERMINISTIC ENGINE (PYTHON)           │  LOGCOMEX AGENT (MCP CONNECTION)            │
│  - Risk Engine (Monte Carlo)             │  - U1: Market Intelligence / NCM            │
│  - Cost Engine (Quay x Dry Port)         │  - U2: BL, Invoice, and Packing List Reading│
│  - Break-Even Point Engine               │  - U3: Catalog Attribute Suggestion         │
│  - Spreadsheet Parser & Discrepancies    │  - U4: Executive Opinion Drafting           │
│  - Technical Report Generator            │                                             │
│                                          │  DECOUPLED CLIENT (agent_client.py)         │
│  AUDIT TRAIL                             │  - LogcomexMCPAgent (Live Production)       │
│  - Structured JSONL Logs (trace_id)      │  - FakeAgent (Real & Offline Fixtures)      │
└──────────────────────────────────────────────┴─────────────────────────────────────────────────┘

```

## 3. Deterministic Engine Modules (`datawave/engine/`)

### 3.1 Risk and Stay Simulation (`risk.py`)

* Stochastic Monte Carlo simulation (5,000 iterations per execution) to project cargo dwell time at the quay.

* Incorporates empirical priors of parameterization channels (Green, Yellow, Red, and Grey) and response times from consenting agencies (MAPA, Anvisa, Inmetro, Ibama, Vigiagro).

* Mathematically models the regulatory benefit of the Authorized Economic Operator (AEO) certification, reducing inspection probability and release timeframes.

* Stochastic output with percentile curves (P50, P75, P90) and objective probability of free time expiration.

### 3.2 Cost Matrix and Break-Even (`cost.py`)

* Strict separation between:

  * **Demurrage:** full container overstay until clearance or stripping in the primary zone.

  * **Detention:** empty container overstay until actual return to the empty container depot.

* Dynamic calculation of the progressive port storage tariff table for the quay in Santos by tariff periods.

* Transfer cost matrix to the secondary zone (dry port / CLIA), accounting for linear storage, local removal freight, transit insurance, Customs Transit Declaration (DTA), and dispatch fees.

* Analytical calculation of the exact break-even day and projected net savings value.

### 3.3 Normalizer and Customs Spreadsheet Parser (`spreadsheet_parser.py`)

* Resilient ingestion of broker spreadsheets in CSV, TSV, and JSON formats.

* Automatic semantic mapping of column header synonyms from Brazilian and international foreign trade.

* Secure conversion of numeric representations (Brazilian format with comma and international format with dot).

* Automated consolidation and extraction of document inconsistencies between BL gross weight and Packing List weight.

### 3.4 Executive Report and Transparency (`report.py`)

* Deterministic generation of a structured executive opinion via Pydantic model (`ParecerExecutivo`).

* Mechanical validation preventing numerical discrepancies between recommended text and values calculated by the engines.

* Explicit labeling of each data source (real Logcomex data, regulatory premise, or simulated value).

## 4. Logcomex Agent and Skills Matrix

The system connects to the Logcomex ecosystem via MCP (*Model Context Protocol*), supporting four structured operational flows:

| Flow | Objective | Involved Skill | Validation Pydantic Model | 
 | ----- | ----- | ----- | ----- | 
| **U1** | Market Intelligence / NCM | Brazil Shipment Intelligence | `MercadoNCM` | 
| **U2** | Cross-Document Review | Supply Chain / Document Analysis | `OperacaoExtraida` | 
| **U3** | DUIMP Attribute Suggestion & Audit | DUIMP Product Catalog | `SugestaoAtributos` | 
| **U4** | Executive Justification | Executive Customs Analysis | Structured validation via `report.py` | 

### Resilience and Decoupling (`agent_client.py`)

To ensure full system availability during audits and demonstrations:

* **`LogcomexMCPAgent`:** Manages asynchronous communication with Logcomex cloud agents, performing OAuth authentication, response sanitization, and reprocessing with format correction if guardrails blockages occur.

* **`FakeAgent`:** Offline deterministic provider fed with real samples recorded in `fixtures/agent/`, allowing unit testing and full pipeline executions without external connectivity.

## 5. Interactive Interface and API Server

DataWave includes an interactive executive interface for decision-making and logistics scenario validation:

* **Executive Dashboard (`index.html`):** Complete visual panel with dynamic switching between 4 real and simulated strategic routes at the Port of Santos (Argentine Wine via MSC, Fertilizers with MAPA inspection, AEO Chemicals, and General Cargo).

* **Interactive Simulator:** Real-time adjustment of exchange rates (USD/BRL), free time days granted by the shipowner, daily rates, and cargo parameterization status.

* **Hybrid Server (`main.py`):** Operation under FastAPI with support for REST endpoints (`/api/simular`, `/api/pipeline`, `/api/despachante/processar-planilha`, `/api/chat`) and an automatic fallback mechanism to the native HTTP server in environments with library restrictions.

## 6. Repository Structure

```
PortoHack-2026/
├── README.md                                # Master project documentation
├── .gitignore                               # Git exclusion directives
├── docs/                                    # Technical documentation, field research, and reports
│   ├── PH2026_E1_PESQUISA_DATAWAVE.pdf      # Consolidated executive field research report
│   ├── pesquisa_setorial_porto_hack_santos_2026.md # Analytical base and sector data of the Port of Santos
│   └── prototipo-pesquisa-campo.md          # Documentation of field interviews with customs brokers
├── scripts/                                 # Support utility scripts and research
│   └── gerar_copies_pesquisa_porto_hack.py  # Research synthesis automation
└── datawave/
    ├── main.py                              # API server and executive frontend delivery
    ├── pipeline.py                          # End-to-end orchestrator pipeline with audit trail
    ├── schemas.py                           # Formal data contracts and Pydantic validation
    ├── agent_client.py                      # MCP integration client (LogcomexMCPAgent and FakeAgent)
    ├── auth_manager.py                      # Credential manager and MCP OAuth flow
    ├── autenticar_mcp.py                    # Utility script for interactive authentication
    ├── index.html                           # Interactive executive panel and scenario viewer
    ├── mock_scenarios.json                  # Specification of strategic port scenarios
    ├── catalogo_produtos_vinhos.csv         # Real sample for DUIMP attribute auditing
    ├── data/
    │   ├── risk_priors.yaml                 # Empirical channel and deadline priors by NCM
    │   └── tarifas.yaml                     # Current storage tables and port fees
    ├── docs/
    │   └── plano-agente-datawave.md         # Detailed architecture and guardrails specification
    ├── engine/
    │   ├── cost.py                          # Quay, dry port, and break-even cost engine
    │   ├── risk.py                          # Stochastic risk engine (Monte Carlo)
    │   ├── report.py                        # Deterministic technical opinion generator
    │   └── spreadsheet_parser.py            # Normalizer and ingestion tool for broker spreadsheets
    ├── fixtures/
    │   └── agent/                           # Real samples for offline FakeAgent operation
    │       ├── u1_mercado_ncm.json
    │       ├── u2_conferencia_documental.json
    │       ├── u3_sugestao_atributos.json
    │       └── u4_justificativa_executiva.json
    ├── skills/
    │   ├── 01_catalogo_produtos_duimp.md    # Context skill: DUIMP registration rules
    │   ├── 02_contrato_saida_json.md        # Context skill: response schemas and contracts
    │   ├── 03_glossario_premissas_cais_retroporto.md # Skill: Santos operational premises
    │   └── 04_playbook_extracao_documental.md # Skill: cross-check matrix
    ├── skills_prontas_para_copiar.md        # Formatted template for direct deployment in Logcomex
    └── tests/                               # Suite with automated tests
        ├── test_agent_client.py
        ├── test_api.py
        ├── test_cost_engine.py
        ├── test_report_pipeline.py
        ├── test_risk_engine.py
        ├── test_schemas.py
        └── test_spreadsheet_parser.py

```

## 7. How to Run

### 7.1 Prerequisites

* Python 3.10 or higher

* `pip` package manager

### 7.2 Installing Dependencies

Install the required libraries for full execution:

```
pip install pydantic pyyaml pytest fastapi uvicorn

```

*(Note: If `fastapi` and `uvicorn` are not installed, the system automatically activates its native HTTP server).*

### 7.3 Running the Application and Interactive Panel

To start the API and local executive interface:

```
python datawave/main.py

```

Then, open your browser and navigate to:

```
http://localhost:8000

```

### 7.4 Running Automated Tests

The project features **46 automated tests** covering all modules of the deterministic engine, validation schemas, error handling, and pipeline integration.

To run the complete suite with a detailed report:

**On Windows (PowerShell):**

```
$env:PYTHONPATH="."; pytest -v

```

**On Linux or macOS:**

```
PYTHONPATH=. pytest -v

```

## 8. Governance and Quality Guidelines

* **Deterministic Sovereignty:** No financial decisions, storage calculations, or transfer recommendations are delegated to language model probabilities or hallucinations.

* **Traceability and Auditability:** Each pipeline execution generates a unique trace identifier (`trace_id`) and records its respective event trail in structured JSONL format (`datawave/logs/pipeline_runs.jsonl`).

* **Regulatory Compliance:** Strict alignment with Brazilian Federal Revenue regulations, current tariff tables of Santos terminals, and Siscomex Single Window attribute standards.