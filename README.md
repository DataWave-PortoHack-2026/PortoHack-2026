# DataWave — Inteligência Aduaneira e Otimização Logística Portuária

> **Porto Hack Santos 2026**  
> Solução integrada para mitigação de riscos fiscais no Catálogo de Produtos da DUIMP e otimização de custos de permanência portuária (Cais vs. Retroporto).

---

## 1. Visão Geral e Problema Enfrentado

A importação marítima de cargas conteinerizadas pelo Porto de Santos enfrenta dois gargalos operacionais críticos que acarretam prejuízos financeiros severos:

1. **Erros e Exigências Fiscais no Catálogo de Produtos da DUIMP:** O preenchimento incorreto de atributos regulatórios, divergências entre documentos de embarque (BL, Invoice e Packing List) ou grafias fora da especificação do Portal Único Siscomex geram parametrização em canais de conferência física (canal vermelho) ou bloqueios por órgãos intervenientes (Receita Federal, MAPA, Anvisa, Inmetro, Ibama).
2. **Estouro de Free Time e Custos de Sobre-estadia:** A retenção da carga na zona primária (cais) submete o importador a tabelas de armazenagem progressiva agressivas e sobre-estadia de contêineres (*demurrage* e *detention*) tarifadas em dólares americanos, que frequentemente superam a margem operacional do lote.

O **DataWave** resolve essa dor por meio de uma arquitetura híbrida: um **motor determinístico de cálculo e auditoria em Python** combinado com um **Agente Inteligente de Comércio Exterior na plataforma Logcomex** conectado via MCP (*Model Context Protocol*).

---

## 2. Arquitetura da Solução

O sistema adota o princípio de **soberania de cálculo determinístico**: modelos de linguagem operam nas bordas (leitura de documentos, consulta de mercado e sugestão de atributos), enquanto toda regra fiscal, validação normativa e cálculo financeiro reside no código auditável do motor local.

```
                  ┌──────────────────────────────────────────────────┐
                  │                 PAINEL / USUÁRIO                 │
                  └────────────────────────┬─────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   HARNESS / PIPELINE                                   │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│                                          │                                             │
│  MOTOR DETERMINÍSTICO (PYTHON)           │  AGENTE LOGCOMEX (CONEXÃO MCP)              │
│  - Módulo A: Auditoria e Padronização    │  - U1: Inteligência de Mercado / NCM        │
│  - Módulo B: Estimador de Permanência    │  - U2: Leitura de BL, Invoice e Romaneio    │
│  - Módulo C: Custos de Cais x Retroporto │  - U3: Sugestão de Atributos do Catálogo    │
│  - Módulo D: Break-Even e Recomendação   │  - U4: Redação de Parecer Executivo         │
│  - Módulo E: Relatório Técnico           │                                             │
└──────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 3. Módulos do Sistema

### 3.1 Módulo A — Auditoria e Padronização do Catálogo de Produtos
- Validação determinística de regras extraídas do Portal Único Siscomex.
- Verificação de hierarquias de atributos condicionais, campos obrigatórios, tipos de dados e listas autorizadas.
- Validação estrita do padrão Siscomex:
  - `modalidade`: estritamente `IMPORTACAO` ou `EXPORTACAO`.
  - `atributosMultivalorados`: estruturados com array `valores`.
- Algoritmo de validação de código GTIN pelo algoritmo GS1 (módulo 10).
- Função `padronizar()`: correção mecânica, segura e idempotente de desvios de formatação antes do embarque.

### 3.2 Módulo B — Análise de Risco e Permanência
- Estimativa estocástica de permanência a partir de canais de parametrização e complexidade documental da NCM no Porto de Santos.

### 3.3 Módulo C e D — Custos e Ponto de Equilíbrio (Break-Even)
- Separação rigorosa entre:
  - **Demurrage:** sobre-estadia do contêiner cheio até a retirada da zona primária.
  - **Detention:** sobre-estadia do contêiner vazio até a devolução efetiva no terminal de vazios (*depot*).
- Análise comparativa entre armazenagem progressiva no cais e custos de remoção para zona secundária (retroporto / CLIA).
- Determinação matemática do dia ótimo de transferência e cálculo de economia líquida por contêiner.

### 3.4 Módulo E — Relatório Executivo e Transparência
- Resumo consolidado para o despachante aduaneiro com rotulagem clara entre dados reais de mercado e premissas operacionais simuladas.

---

## 4. Skills e Configurações do Agente Logcomex

O Agente DataWave é capacitado com skills de contexto especializadas estruturadas para o ambiente da Logcomex:

- **[Instruções do Agente (System Prompt)](datawave/instrucoes_agente.md):** Diretrizes mestras de persona, ancoragem em dados reais, respeito estrito aos números do motor local e conformidade com os guardrails da Logcomex.
- **[Catálogo de Produtos DUIMP](datawave/skills/01_catalogo_produtos_duimp.md):** Regras gerais da DUIMP, funcionamento de árvores lógicas condicionais e padrões normativos de preenchimento.
- **[Contrato de Saída JSON DataWave](datawave/skills/02_contrato_saida_json.md):** Sintaxe obrigatória para retorno em JSON puro, integrada aos modelos Pydantic (`OperacaoExtraida`, `MercadoNCM` e `SugestaoAtributos`).
- **[Glossário e Premissas Cais vs. Retroporto](datawave/skills/03_glossario_premissas_cais_retroporto.md):** Terminologia aduaneira de Santos, diferenciação entre demurrage e detention e dinâmica de armazenagem escalonada.
- **[Playbook de Extração Documental](datawave/skills/04_playbook_extracao_documental.md):** Matriz de conferência cruzada para detecção de divergências entre BL, Fatura Comercial e Romaneio de Carga.
- **[Guia Rápido de Preenchimento](datawave/skills_prontas_para_copiar.md):** Blocos prontos para cópia e colagem direta no modal de criação de skills da plataforma.

---

## 5. Estrutura do Repositório

```
PortoHack-2026/
├── README.md                                # Documentação principal da solução
├── .gitignore                               # Exclusões de arquivos de compilação e testes
├── pesquisa_setorial_porto_hack_santos_2026.md # Base de inteligência de mercado do porto
├── gerar_copies_pesquisa_porto_hack.py      # Utilitário de automação de pesquisa setorial
└── datawave/
    ├── catalog_audit.py                     # Motor determinístico de auditoria e padronização
    ├── instrucoes_agente.md                 # System Prompt mestre do Agente Logcomex
    ├── skills_prontas_para_copiar.md        # Gabarito de preenchimento na plataforma
    ├── docs/
    │   └── plano-agente-datawave.md         # Documento completo de arquitetura e planejamento
    ├── skills/
    │   ├── 01_catalogo_produtos_duimp.md    # Skill de contexto: regras de catálogo
    │   ├── 02_contrato_saida_json.md        # Skill de contexto: contratos de dados JSON
    │   ├── 03_glossario_premissas_cais_retroporto.md # Skill: premissas cais x retroporto
    │   └── 04_playbook_extracao_documental.md # Skill: conferência cruzada de documentos
    └── tests/
        └── test_catalog_audit.py            # Suíte de testes do validador de catálogo
```

---

## 6. Como Executar

### Pré-requisitos
- Python 3.10 ou superior
- Gerenciador de pacotes `pip`

### Execução dos Testes Automatizados
Para rodar a suíte de testes unitários do motor de catálogo:

```bash
pytest datawave/tests/test_catalog_audit.py -v
```

---

## 7. Diretrizes de Governança e Qualidade

- **Determinismo:** Nenhuma decisão financeira ou bloqueio cadastral é arbitrado exclusivamente por probabilidade de LLM.
- **Transparência de Dados:** Toda informação apresentada em tela carrega explicitamente sua fonte (*agente*, *premissa* ou *simulado*).
- **Conformidade Regulatória:** Alinhamento estrito às normas do Portal Único Siscomex e Receita Federal do Brasil.