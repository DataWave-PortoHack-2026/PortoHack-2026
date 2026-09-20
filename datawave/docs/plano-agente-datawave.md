# Plano de Construção — Agente DataWave (Porto Hack Santos 2026)

> Documento de trabalho. Complementa o `plano-funcional-agente-datawave.md` (o **quê**) com o **como**:
> arquitetura, o que vira skill, conexões, dados, testes e ordem de construção.
>
> Legenda de status: **[OK]** confirmado (print ou sondagem) · **[TESTAR]** hipótese a validar · **[DESCARTADO]** não usar · **[FEITO]** já entregue.

---

## 0. Resumo executivo

1. O que o plano funcional descreve é um **motor de decisão determinístico com LLM nas bordas**, não um agente que decide sozinho. O fluxo é fixo: extrair → auditar cadastro → estimar permanência → calcular custo → recomendar → explicar.
2. **Engine local (Python)** faz toda conta, regra e recomendação. **Agente Logcomex** fornece dados reais de mercado/embarques, lê documentos e sugere valores de atributo. Regra do hackathon: código além do agente é permitido, mas o agente **deve** ser usado.
3. O `chat_with_agent` **não** aceita tools nem schema de saída: formato JSON só via texto da mensagem. Toda resposta do agente é validada por Pydantic, com retry.
4. O módulo A (auditoria e padronização de catálogo) já tem protótipo: regras extraídas da planilha DUIMP + validador + `padronizar()` + 31 testes passando. Com a especificação do Portal Único (Modalidade e multivalorados), 3 das 4 linhas reais da planilha são apontadas por grafia de Modalidade e ficam APROVADAS após a padronização.
5. Demo com dados simulados na camada operacional (carga, tarifas, free time) e dados reais do agente onde possível. Tudo rotulado no painel.

---

## 1. Restrições e decisões fechadas

| # | Decisão | Origem | Status |
|---|---|---|---|
| 1 | O Agente DataWave (plataforma Logcomex) deve ser usado; código adicional é permitido | Esclarecimento do usuário | [OK] |
| 2 | Interface com o agente é **MCP**, não a API HTTP da plataforma | Usuário | [OK] |
| 3 | MCP hoje conectado ao Antigravity; será conectado ao harness depois | Usuário | [OK] — fluxo OAuth em 6.1 |
| 4 | O harness será criado por eles; a LLM que raciocina é a do agente Logcomex (sem LLM externa) | Usuário | [OK] |
| 5 | Engine de custo/risco/regras roda **local** e é a fonte única de números | Sondagem (guardrail) | [OK] |
| 6 | Latência do agente (9–23 s medidos) não é preocupação | Usuário | [OK] |
| 7 | Demo com exemplos e mockups simulados, além dos 4 vinhos reais da planilha | Usuário | [OK] |
| 8 | Planilha `DUIMP_Casal_Branco_1808.xlsm` é a base para padronizar o Catálogo de Produtos | Usuário | [OK] |
| 9 | MCP em `https://mcp.logcomex.ai/`; autenticação por OAuth com navegador (como conectar Gmail em um app) | Usuário + metadados do servidor | [OK] |
| 10 | É possível criar skills de capacidade e de contexto | Usuário | [OK] — falta saber o que uma skill de capacidade pode chamar |
| 11 | Portal Único: `modalidade` = `IMPORTACAO`/`EXPORTACAO` (maiúsculas, sem acento); `atributosMultivalorados` = array de `{atributo, valores[]}` | Especificação trazida pelo usuário | [OK] — conferir uma vez na documentação oficial |
| 12 | O agente disponibiliza e consulta valores reais de mercado | Usuário | [OK] — testar formato JSON e disponibilidade de canal/datas |

---

## 2. Arquitetura

```
Usuário ──► PAINEL (UI) ──► HARNESS (código de vocês, dirige o fluxo)
                              │
       ┌──────────────────────┼─────────────────────────────────────┐
       ▼                      ▼                                     ▼
  ENGINE LOCAL          AgentClient (interface)               Templates / relatório
  A auditoria           ├─ LogcomexMCPAgent  (produção)       (texto com números do engine)
  B permanência         └─ FakeAgent         (fixtures)
  C custo/break-even            │
  D recomendação                ▼
                        MCP Logcomex ──► Agente DataWave ──► skills (Embarques, Importação,
                                                              ComexStat, Supply Chain...)
```

**Princípios**

- **O código dirige o fluxo; o agente é chamado como função.** Loop livre do LLM só aumenta latência e não-determinismo em um pipeline fixo.
- **`AgentClient` é uma interface** com duas implementações: `LogcomexMCPAgent` (quando o MCP estiver conectado ao harness) e `FakeAgent` (reproduz respostas gravadas em `fixtures/agent/`). Assim o resto do sistema é construído e testado hoje, sem depender do MCP.
- **O agente nunca calcula.** Todo número no relatório vem do engine.
- **Toda resposta do agente é dado não confiável até ser validada** (schema Pydantic + regras do engine).

---

## 3. Papel do agente Logcomex (uso visível na demo)

O agente recusou (redirecionando a `trust.logcomex.ai`) dois pedidos nos testes: listar campos/estrutura da base e redigir justificativa a partir de JSON descrito como inventado. Regra prática: **perguntas ancoradas em dado real da Logcomex**, sem as palavras "simulado", "inventado", "não consulte a base", "campos", "schema".

| # | Uso do agente | Skill envolvida | Entrada | Saída (JSON no texto) | Alimenta | Status |
|---|---|---|---|---|---|---|
| U1 | Mercado do NCM: volumes, origens, importadores, sazonalidade; tempo chegada→desembaraço por canal, se existir | Inteligência de Embarques Brasil / Importação Brasil | NCM + porto (reais) | `MercadoNCM` | Priors do módulo B, contexto do relatório | [OK] segundo o usuário (consulta valores reais de mercado); [TESTAR] formato JSON e se há canal/datas |
| U2 | Leitura de BL, invoice e packing list (PDFs de exemplo) | Supply Chain | `attachments` (base64/url, até 10 × 25 MB) | `OperacaoExtraida` + divergências | Entrada do pipeline | [TESTAR] |
| U3 | Sugerir valores de atributo a partir de rótulo/descrição, **restritos** aos códigos da aba Listas | Supply Chain + contexto do catálogo | Descrição + opções válidas no texto | `SugestaoAtributos` | Módulo A (sempre revalidado) | [TESTAR] |
| U4 | Redação da justificativa executiva a partir dos números do engine | — | Operação real + resultados "do sistema" | Texto | Relatório | [TESTAR] — se recusar, usar **template determinístico** |

### 3.1 Contratos JSON (definir em `schemas.py`)

```python
class OperacaoExtraida(BaseModel):
    ncm: str; descricao: str; valor_lote_usd: float; qtd_conteineres: int
    incoterm: str | None; porto_descarga: str | None; armador: str | None
    origem: str | None; data_chegada_prevista: date | None
    divergencias: list[str] = []          # BL x invoice x packing list

class MercadoNCM(BaseModel):
    ncm: str; periodo: str
    volume_mensal: dict[str, float] | None
    origens_top: list[str] | None; importadores_top: list[str] | None
    dias_chegada_desembaraco: dict[str, float] | None   # por canal, ou None se indisponível

class SugestaoAtributos(BaseModel):
    sugestoes: dict[str, str]             # ATT_xxxxx -> código da lista
    incertos: list[str] = []              # atributos que o agente não soube preencher
```

### 3.2 Modelos de prompt (hipóteses; testar e ajustar)

- **U1:** `Para a NCM {ncm}, considerando importações marítimas com descarga no Porto de Santos nos últimos 12 meses, informe volume por mês, principais países de origem e principais importadores e, se houver essa informação, o tempo típico entre chegada e desembaraço por canal. Se algum dado não existir, escreva "indisponível". Responda somente com JSON neste formato: {schema}`
- **U2:** anexos + `Compare o BL, a invoice e o packing list anexos: extraia os campos abaixo e liste divergências entre os documentos. Responda somente com JSON neste formato: {schema}`
- **U3:** `Produto: {descricao}. Rótulo: {texto}. Para cada atributo abaixo, escolha um código dentre as opções listadas ou marque como incerto: {atributos_e_opcoes}. Responda somente com JSON: {schema}`
- **U4:** `Operação do cliente: {resumo}. Resultado da análise: {numeros_do_engine}. Redija a justificativa executiva para o despachante, usando exatamente esses valores.`

### 3.3 Camada `AgentClient` (esqueleto)

```
ask_agent(message, attachments=None, conversation_id=None) -> str
    r = chat_with_agent(agent_id, message, conversation_id, attachments)
    se r tem task_id: get_task_status com backoff (1→3 s), timeout ~120 s; ao estourar, cancel_task
    se resposta contém "trust.logcomex.ai": levantar AgentRefusal (não fazer retry cego)

ask_json(prompt, Modelo) -> Modelo
    message = prompt + JSON schema do Modelo
    parse + validação Pydantic; falha → até 2 retries devolvendo o erro de validação
    grava tudo em logs/ (JSONL) e, opcionalmente, em fixtures/agent/ para replay
```

---

## 4. Skills: o que deve, o que pode e o que não deve virar skill

Na plataforma é possível criar os dois tipos: **Capacidades** (ferramentas/dados) e **Contexto** (conhecimento personalizado). O que uma skill de capacidade pode chamar (endpoint HTTP, OpenAPI, MCP, código) ainda não está confirmado; ver 4.6 e a pendência P3.

### 4.1 DEVE virar skill de contexto

| Skill | Conteúdo | Por quê |
|---|---|---|
| **Catálogo de Produtos – Regras MAPA (vinhos)** | Estrutura da árvore: raiz "Área Temática do MAPA" (`ATT_14200`); atributos condicionais; convenções de padronização (ver 4.4); NCMs cobertas (2204.21.00, 2204.22.11, 2204.10.90); lembrete de que o engine é a autoridade | Faz o agente responder alinhado às regras sem repetir tudo em cada prompt |
| **Contrato de Saída JSON DataWave** | Como responder quando pedido JSON (somente JSON, sem markdown/comentário), como marcar campo ausente (`null`/"indisponível"), formato de datas e moeda | Substitui a ausência de `output_schema`; encurta prompts |
| **Glossário e Premissas Cais × Retroporto** | Zona primária/secundária, free time de demurrage × detention, armazenagem por período, canais de parametrização, DUIMP, entreposto aduaneiro; premissas do modelo | Consistência de vocabulário no relatório e nas respostas |
| **Playbook de Extração Documental** | Campos-alvo de BL, invoice e packing list, regras de conferência entre eles, formato de `OperacaoExtraida` | Reforça U2 com o padrão esperado |

### 4.2 PODE virar skill de contexto (avaliar depois)

| Skill | Observação |
|---|---|
| **Tarifário Santos (simulado)** | Só para o agente responder perguntas de apoio. **A fonte de verdade é `tarifas.yaml` no engine.** Rotular como simulado |
| **Persona do consultor DataWave** | Pode ficar nas Instruções do agente em vez de skill |
| **Exemplos de relatório executivo** | Ajuda U4 se a redação passar no guardrail |

### 4.3 Fica em código (a implementação nunca vira prompt)

A lógica continua em Python. Ela pode ser **exposta** ao agente por uma skill de capacidade (4.6), mas nunca reimplementada em texto de skill.

| Item | Motivo |
|---|---|
| Custo total, demurrage, armazenagem, break-even | Deve ser exato, reproduzível e testado |
| Estimador de permanência (Monte Carlo) | Determinístico com semente fixa |
| Validador do catálogo (árvore de condições, listas, GTIN, tamanho) | Já implementado e testado |
| Tarifas, free time, câmbio, priors | Parâmetros em YAML com `fonte` explícita |
| Template do relatório | Garante que só números do engine apareçam |

### 4.4 Convenções de padronização a registrar na skill de catálogo

Itens 1 e 6 seguem a especificação do Portal Único informada pelo usuário; 2–5 são **convenções observadas na planilha**, não regras oficiais:

1. `Modalidade` exatamente `IMPORTACAO` ou `EXPORTACAO` (maiúsculas, sem acento). Na planilha, 3 de 4 linhas estão como `IMPORTAÇÃO`.
2. `Denominação` sem espaços nas pontas.
3. Atributos opcionais sem valor devem ser **omitidos**, não enviados vazios (ex.: Safra).
4. `ATT_14211` (Denominação conforme legislação) começa com a Denominação do produto; tratamento da indicação geográfica precisa de regra única (hoje: removida nos DOC DO TEJO, mantida nos REGIONAL TEJO).
5. `ATT_14186` (variedade de uva na embalagem) deve refletir o rótulo; descrição citando casta com "Não consta" é candidato a revisão humana.
6. Atributos multivalorados vão em `atributosMultivalorados` como `{atributo, valores[]}`; nunca em `atributos`.

### 4.5 Skills nativas: uso e ajustes sugeridos

| Skill existente | Uso no projeto | Ação sugerida |
|---|---|---|
| Inteligência de Embarques Brasil | U1 | Manter |
| Inteligência de Importação Brasil | U1 | Manter |
| Comexstat (ranking, tabela, série, panorama, preço) | Contexto de mercado | Manter |
| Supply Chain | U2, U3 | Manter |
| Análise de Competitividade de Preços | Fora do escopo | Avaliar desativar; hoje é a **skill padrão** (estrela), o que pode enviesar respostas |
| LATAM Trade Intelligence V2 | Fora do escopo | Avaliar desativar para reduzir respostas fora de foco |

### 4.6 Skills de capacidade (opcional; alto valor se viável)

Se uma skill de capacidade puder chamar um endpoint externo, o **engine** pode ser exposto ao agente por ela. O agente passa a orquestrar de verdade (os números vêm de uma ferramenta dele), o que também tende a contornar a recusa de redação com números "avulsos" no prompt.

| Skill de capacidade | Chama | Entrada → saída | Prioridade |
|---|---|---|---|
| `auditar_catalogo` | `audit_product` + `padronizar` | Produto JSON → achados + produto padronizado | Alta |
| `comparar_cais_retro` | Engine C/D | Operação + cenário → break-even, custos, recomendação | Alta |
| `estimar_permanencia` | Módulo B | NCM, canal, perfil → distribuição de permanência | Média |

Requisitos: engine hospedado com URL HTTPS (túnel ou deploy) e autenticação simples; contrato em OpenAPI se a plataforma aceitar. O **harness continua sendo o caminho principal** (código dirige o fluxo, seção 3); o modo "agente chama o engine" é a camada de consultor/chat e reforça o uso do agente na demo.

---

## 5. Configuração do agente na plataforma

### 5.1 Instruções (substituir o template genérico)

Rascunho para colar em "Instruções para o Agente":

```
Você é o Agente DataWave, consultor de comércio exterior para importadores e despachantes
em Santos. Seu foco: (1) padronização e auditoria do Catálogo de Produtos antes do embarque,
(2) leitura de documentos de importação, (3) dados de mercado e embarques do Brasil.

Regras:
- Use somente dados das suas skills; se um dado não existir, responda "indisponível".
- Quando o usuário pedir JSON, responda apenas com JSON válido no formato indicado.
- Quando receber resultados de cálculo do sistema DataWave, use-os literalmente; não recalcule.
- Para atributos com lista de opções, escolha somente códigos da lista fornecida; se não
  souber, marque como incerto.
- Seja direto; sem opinião fora do escopo de comércio exterior.
```

### 5.2 Permissões

| Item | Estado atual (prints) | Recomendação |
|---|---|---|
| Dados internos: Workflows, Empresas, Produtos (C/E/D) | Tudo ligado, inclusive D (vermelho) | Desligar **D** em todos; desligar **E** em Empresas/Produtos se não for necessário |
| Estrutura: criar workflows, etapas, campos personalizados | Ligado | Desligar, a menos que a demo use |
| Fontes externas (ComexStat BR, México, Colômbia, Chile, Paraguai, Uruguai) | Todas ligadas (somente leitura) | Manter BR; desligar as demais se causarem respostas fora de foco |

### 5.3 Conectores

| Conector | Recomendação |
|---|---|
| Certificados (e-CNPJ/e-CPF, "sistemas da aduana") | **Não subir certificado real.** Se subir algum, ligar "Exclusivo deste agente" (padrão compartilha com todos os agentes da empresa) |
| Integrações | Verificar se aceita chamada HTTP/MCP externa (ver P2) |
| E-mail / Inbox | **Desligar**, salvo se a demo mostrar entrada por e-mail |
| WhatsApp | Desligar |

### 5.4 Missão agendada de inbox (segurança)

`Leitura automática do inbox` (id `6d2a0fba-24ec-48c2-8c20-02f311b24014`) lê e responde e-mails **sem confirmação humana**. É vetor de prompt injection e de vazamento. **Desativar** junto com o inbox.

### 5.5 Memória do agente

Hoje com 0 memórias e "aprende automaticamente durante as conversas". Risco: dados simulados da demo virarem "memória" e contaminarem respostas. Conferir a aba de memórias antes de cada ensaio e limpar se necessário.

---

## 6. Conexões necessárias

| # | Conexão | Para quê | Status | Pendência |
|---|---|---|---|---|
| C1 | Harness ↔ MCP Logcomex (cliente Python, `chat_with_agent`, `get_task_status`, `cancel_task`) | U1–U4 | Adiado até o harness existir | Fluxo OAuth conhecido (6.1); falta implementar e ensaiar login e renovação |
| C2 | Antigravity ↔ MCP Logcomex | Sondagem e gravação de respostas reais para `fixtures/agent/` | [OK] funcional | — |
| C3 | Harness ↔ `FakeAgent` (fixtures) | Desenvolver e testar sem MCP; rede de segurança da demo | A construir | Gravar respostas reais no Antigravity |
| C4 | Portal Único Siscomex (via certificado digital) | Catálogo/atributos oficiais | **Fora do MVP** | Exige e-CNPJ/e-CPF válido; sem ele, usar a planilha como base |
| C5 | Fonte de câmbio | USD→BRL para demurrage | Opcional | Fixar no YAML na demo; API pública do Banco Central é opcional |
| C6 | UI | Painel lado a lado + relatório | A definir | Sugestão: Streamlit (Python, mesmo processo do engine) |
| C7 | Armazenamento | Cenários, tarifas, logs | Arquivos locais (JSON/YAML/JSONL) | Sem banco de dados no MVP |
| C8 | LLM externo | — | [DESCARTADO] | A LLM é a do agente Logcomex |
| C9 | API HTTP da plataforma (chaves + endpoints por prompt) | — | [DESCARTADO] | Decisão do usuário: usar MCP |

### 6.1 MCP Logcomex: como conectar o harness

- **URL:** `https://mcp.logcomex.ai/`. A raiz devolve JSON com `protocolVersion: 2025-06-18`, o endereço dos metadados OAuth e a página de documentação (que é um app JavaScript, sem texto legível por fetch simples).
- **Metadados OAuth** (`/.well-known/oauth-authorization-server`): grants `authorization_code` e `refresh_token`; PKCE `S256`; **registro dinâmico de cliente** em `/register`; autenticação do cliente no token endpoint `none`, `client_secret_post` ou `client_secret_basic` (cliente público funciona); scopes `mcp:chat:free`, `mcp:chat:agents` e `offline_access`.
- **Implementação (SDK Python v2):** `OAuthClientProvider` (um `httpx.Auth`) com (a) `TokenStorage` em **arquivo** (tokens + `client_info`), (b) `redirect_handler` que abre o navegador, (c) `callback_handler` que recebe o código em um servidor local (`http://localhost:PORTA/callback`). Passar o cliente httpx ao transporte Streamable HTTP. Pedir os três scopes; `offline_access` habilita o refresh token. Fixar a versão do SDK e conferir a assinatura exata na documentação dela.
- **Operação:** login **uma vez** antes dos ensaios; depois o token renova sozinho, sem navegador. Testar a renovação antes da demo. O SDK v2 atende revisões anteriores do protocolo, incluindo a 2025-06-18 anunciada pelo servidor.
- **Cuidado conhecido:** há relato aberto no repositório do SDK de cliente preso em `invalid_client` quando o secret registrado expira. Remédio: apagar o `client_info` salvo e registrar de novo.
- **Créditos:** a plataforma trabalha com créditos (a landing anuncia 5.000 grátis). Confirmar o limite da conta do hackathon; usar `FakeAgent`/fixtures nos ensaios.

**Ferramentas MCP disponíveis (8):** `chat_free`, `list_agents`, `chat_with_agent`, `get_task_status`, `cancel_task`, `list_missions`, `search_missions`, `get_mission`.

- `chat_with_agent(agent_id, message, conversation_id?, attachments?)` — `agent_id` do DataWave: `c2322f9c-41e2-4bf8-8fe5-3bd93f4063d4`. Tarefas longas devolvem `task_id`; status: `pending | completed | cancelled | error`.
- `list_missions` sem filtro e com `source=library` falha com erro SQL do lado da Logcomex (`ORDER BY expressions must appear in select list`); com `source=scheduled` funciona. Não depender de missões.
- Missões são prompts agendáveis com `input_schema`/`output_schema`; não há tool para executá-las. Fora do escopo.
- `chat_free`: provavelmente chat sem agente/skills. [TESTAR] como alternativa para redação (U4).

---

## 7. Módulos do plano funcional: como e onde cada um roda

| Módulo | Onde | Como | Status |
|---|---|---|---|
| **A. Auditoria cadastral** | Engine + agente (U3) | `catalog_rules.json` gerado da planilha; validador determinístico; agente só propõe valores | **[FEITO]** protótipo, 17 testes |
| **B. Risco e permanência** | Engine + agente (U1) | Probabilidade de canal × distribuição de permanência por canal; Monte Carlo (10 000 amostras, semente fixa) | A construir |
| **C. Custo e break-even** | Engine | `tarifas.yaml`; varredura de 0–90 dias; curvas para o gráfico | A construir |
| **D. Recomendação** | Engine | Menor custo esperado; empate → menor P90; mostra P(D > free time) | A construir |
| **E. Painel e relatório** | UI + template (+ agente U4) | Semáforo verde/amarelo/vermelho/cinza; resumo executivo | A construir |

### 7.1 Módulo A — detalhes do que existe

- 3 NCMs de vinho compartilham **um único schema** de 117 atributos (idêntico entre as NCMs); 345 de 351 linhas são condicionais; raiz incondicional: `ATT_14200`.
- Checagens: obrigatório ausente (segundo a árvore), atributo não aplicável, atributo inexistente, valor fora da lista (listas longas vêm da aba Listas), tamanho máximo, tipo booleano/numérico, GTIN (tamanho por tipo + dígito verificador GS1), espaços, opcional vazio, grafia de `Modalidade`, coluna correta (`atributos` × `atributosMultivalorados`), formato de multivalorado, `ATT_14211` × Denominação e código duplicado no lote.
- Status: `BLOQUEADO` (vermelho), `COM_ALERTAS` (amarelo), `APROVADO` (verde), `SEM_COBERTURA` (cinza, NCM sem regras).
- **Especificação adotada (Portal Único, trazida pelo usuário):** `modalidade` = `IMPORTACAO`|`EXPORTACAO`; `atributosMultivalorados` = `[{atributo, valores[]}]`. Regras derivadas: grafia errada de Modalidade é ERROR; multivalorado fora de `atributosMultivalorados` (ou o contrário) é ERROR; `valor` no lugar de `valores` é WARNING. **Conferir uma vez na documentação oficial.**
- **Premissa ainda em aberto:** atributo informado mas não aplicável é `WARNING`, não `ERROR`.
- **`padronizar(produto)`:** correções mecânicas e seguras (grafia de Modalidade, espaços, NCM com pontos, omissão de opcionais vazios, atributo na coluna correta). Devolve produto novo + lista de alterações; é idempotente e não inventa valores. Nas 4 linhas reais: antes 1 COM_ALERTAS + 3 BLOQUEADO (Modalidade); depois 4 APROVADO.
- **Limite:** só MAPA e só 3 NCMs de vinho. Outros anuentes (Anvisa, Inmetro, ANP) não têm regra; o sistema deve responder "sem cobertura" em vez de chutar.

### 7.2 Módulo C — modelo de custo

```
custo_cais(d)  = armazenagem_cais(d) + max(0, d − free_time_demurrage) × diária_usd × câmbio
custo_retro(d) = frete_transferência + movimentação + armazenagem_retro(d)
                 + max(0, d_devolução_vazio − free_time_detention) × diária_detention × câmbio
d*             = menor d em que custo_cais(d) > custo_retro(d)
E[custo]       = Σ P(D = d) · custo(d)     # por opção
```

- **Premissa crítica a validar com despachante:** em contratos típicos, demurrage conta até a saída do contêiner cheio do terminal e depois começa *detention* até a devolução do vazio. Transferir a carga **só elimina** a cobrança se o vazio voltar dentro do free time. Modelar os dois free times como parâmetros separados.
- Tarifas por faixa (armazenagem progressiva) → sem otimizador; varredura simples.
- Entreposto aduaneiro: **fase 2**; no MVP, apenas flag "elegível? avaliar".

### 7.3 Módulo B — parâmetros com procedência

Cada parâmetro (P(canal), média/desvio de permanência por canal, ajuste por anuente, ajuste por OEA) carrega `fonte: agente | premissa | simulado`. O relatório exibe a fonte. Se U1 não trouxer canal/datas, B usa **priors declarados como premissa**, sem prometer "modelo treinado".

### 7.4 Módulo E — relatório

Template determinístico em português com condicionais (ex.: "Recomendação: transferir ao retroporto. Economia estimada: R$ X por contêiner. P(estouro de free time no cais): Y%"). U4 (redação pelo agente) é melhoria opcional, e os números do texto são conferidos contra o engine por regex antes de exibir.

---

## 8. Dados e cenários da demo

### 8.1 Regra de ouro dos mocks

- **Simulado:** carga, tarifas, free time, câmbio, priors sem fonte real. Sempre rotulado no painel ("dados simulados").
- **Real:** consultas ao agente sobre NCM/porto reais; os 4 vinhos da planilha como baseline limpo.
- Perguntas ao agente **nunca** contêm a palavra "simulado".

### 8.2 Cenários (`scenarios/*.json`, com resultado esperado calculado à mão)

| # | Cenário | O que demonstra |
|---|---|---|
| S1 | Cais vence, canal verde | Recomendação "retirar no cais" |
| S2 | Retroporto vence, alto risco de retenção | Estouro de free time evitado |
| S3 | Perto do break-even | Sensibilidade, mostra P90 |
| S4 | Free time curto + câmbio alto | Risco em dólar |
| S5 | Cadastro com erro injetado numa linha real da Casal Branco | Alerta **antes** do embarque (obrigatório ausente, código fora da lista, GTIN inválido, texto acima do máximo) |
| S6 | NCM sem regra | "Sem cobertura" (cinza), sem chute |

### 8.3 Arquivos de parâmetros

| Arquivo | Conteúdo |
|---|---|
| `data/tarifas.yaml` | Free time demurrage/detention, diárias em USD, faixas de armazenagem (cais e retro), frete de transferência, movimentação, câmbio; `fonte` por item |
| `data/risk_priors.yaml` | P(canal) por grupo, distribuição de permanência por canal, ajustes por anuente e OEA; `fonte` por item |
| `catalog_rules.json` | Gerado por `build_rules.py` a partir da planilha DUIMP |

---

## 9. Estrutura do repositório e status

```
datawave/
├─ build_rules.py            [FEITO]  planilha DUIMP → catalog_rules.json
├─ catalog_rules.json        [FEITO]  3 NCMs → 1 schema de 117 atributos
├─ catalog_audit.py          [FEITO]  módulo A (validador + padronizar)
├─ tests/
│  ├─ test_catalog_audit.py  [FEITO]  31 testes passando
│  └─ fixtures/casal_branco.json [FEITO]  4 produtos reais
├─ schemas.py                         Pydantic: Operacao, MercadoNCM, SugestaoAtributos, Resultado...
├─ agent_client.py                    AgentClient + LogcomexMCPAgent + FakeAgent
├─ engine/
│  ├─ risk.py                         módulo B
│  ├─ cost.py                         módulos C e D
│  └─ report.py                       módulo E (template + conferência de números)
├─ pipeline.py                        ordem dos passos + log por passo
├─ data/ (tarifas.yaml, risk_priors.yaml)
├─ scenarios/ (S1..S6.json + esperados)
├─ fixtures/agent/                    respostas gravadas do agente (replay)
├─ logs/                              JSONL: entrada/saída de cada passo, com trace id
└─ app.py                             painel (UI)
```

---

## 10. Testes e critérios de aceite

- **Engine:** cada cenário S1–S6 reproduz o resultado esperado (calculado à mão em planilha). Break-even confere com cálculo manual em pelo menos 3 casos.
- **Validador de catálogo:** suíte atual verde (31 testes); ao adicionar NCMs, adicionar casos.
- **Conexão MCP:** login OAuth feito uma vez; o harness chama `list_agents` e `chat_with_agent` sem interação de navegador; renovação de token testada.
- **Agente:** para U1–U4, saída passa no schema Pydantic em ≥ 90 % das chamadas de ensaio (com até 2 retries); recusa (`trust.logcomex.ai`) tratada sem quebrar o fluxo.
- **Relatório:** 100 % dos valores citados no texto batem com os do engine (checagem automática).
- **Demo offline:** com `FakeAgent`, o fluxo completo roda sem rede.

---

## 11. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Login OAuth/expiração de token no dia da demo | Médio | Login prévio com `offline_access`, tokens em arquivo, renovação testada; `FakeAgent` como plano B |
| Consumo de créditos da conta no hackathon | Baixo/Médio | Confirmar limite; usar fixtures nos ensaios |
| Guardrail recusa U1/U3/U4 | Médio | Reformular prompts ancorados em dado real; U4 tem fallback em template |
| Saída JSON só via texto | Médio | Skill de contrato JSON + validação Pydantic + retry |
| Agente não traz canal/datas | Médio | Priors declarados como premissa, com `fonte` visível |
| Premissa demurrage × detention errada | Alto | Validar com despachante; parâmetros separados |
| Memória do agente polui com dados simulados | Baixo | Conferir/limpar antes dos ensaios |
| Missão de inbox responde e-mails sozinha | Alto | Desativar missão e inbox |
| Escopo do catálogo limitado a 3 NCMs de vinho | Médio | Deixar explícito; "sem cobertura" no restante |
| Mock confundido com dado real | Alto (credibilidade) | Rótulo "dados simulados" no painel e no relatório |

---

## 12. Pendências e perguntas em aberto

| # | Pergunta | Quem responde | Impacto |
|---|---|---|---|
| P1 | ~~Como o MCP autentica?~~ **Resolvida:** OAuth 2.1 com navegador, registro dinâmico e refresh token (6.1). Falta implementar e ensaiar | — | — |
| P2 | A aba **Integrações** aceita chamar um endpoint externo (ou MCP)? Se sim, o agente poderia chamar o engine hospedado | Plataforma / organizadores | Habilita uso mais "nativo" do agente (opcional) |
| P3 | Ambos os tipos são possíveis. **Nova pergunta:** o que uma skill de capacidade pode chamar (endpoint HTTP, OpenAPI, MCP, código)? | Plataforma | Define se o engine pode ser exposto ao agente (4.6) |
| P4 | Os dados do agente incluem canal de parametrização e datas (atracação, registro, desembaraço)? | Reteste de U1 (valores, não estrutura) | Define se B é estatística real ou prior |
| P5 | A demo cobrirá só as 3 NCMs de vinho ou vocês receberão mais NCMs? | Equipe | Escopo do módulo A |
| P6 | O agente aceita redação a partir de números do sistema (U4) com enquadramento real? | Reteste em `chat_with_agent` e `chat_free` | Onde o texto do relatório é gerado |
| P7 | ~~Formato de multivalorados~~ **Resolvida:** `[{atributo, valores[]}]` (conferir na documentação oficial) | — | — |
| P8 | ~~Grafia de Modalidade~~ **Resolvida:** `IMPORTACAO`/`EXPORTACAO`, sem acento | — | — |
| P9 | Interface (Streamlit ou outra) e formato de entrega da demo | Equipe | Módulo E |

---

## 13. Ordem de construção

**Fase 0 — Preparação do agente (na plataforma)**
- [ ] Reescrever Instruções (seção 5.1)
- [ ] Ajustar permissões, desligar inbox/missão de inbox/WhatsApp (5.2–5.4)
- [ ] Criar as 4 skills de contexto obrigatórias (4.1)
- [ ] Descobrir o que uma skill de capacidade pode chamar (P3) e, se possível, criar `auditar_catalogo` (4.6)
- [ ] Avaliar desativar skills fora de escopo (4.5)

**Fase 1 — Sem depender do MCP**
- [x] Módulo A: regras + validador + `padronizar()` + testes (31)
- [ ] `schemas.py`, `AgentClient` + `FakeAgent`
- [ ] Engine C/D com `tarifas.yaml` e cenários S1–S4
- [ ] Cenários S5 (erros injetados) e S6 (sem cobertura)

**Fase 2 — Sondagem no Antigravity (gravar fixtures)**
- [ ] Reteste U1 (valores reais, sem palavras-gatilho); anotar se há canal/datas
- [ ] Teste U2 com BL/invoice/packing list de exemplo
- [ ] Teste U3 (sugestão de atributos restrita a lista)
- [ ] Teste U4 em `chat_with_agent` e `chat_free`
- [ ] Gravar respostas em `fixtures/agent/`

**Fase 3 — Integração**
- [ ] Implementar `LogcomexMCPAgent`: OAuth (login único + refresh, tokens em arquivo) + submit + polling + cancel
- [ ] Módulo B com priors (vindos de U1 ou premissas com fonte)
- [ ] Pipeline completo com logs por passo

**Fase 4 — Apresentação**
- [ ] Painel lado a lado com semáforo e "dados simulados"
- [ ] Relatório executivo (template + conferência de números)
- [ ] Ensaio da demo online e offline (`FakeAgent`)

---

## 14. Roteiro da demo (5–6 min)

1. **Problema:** cadastro errado gera exigência; exigência estoura free time; estouro custa em dólar.
2. **Módulo A (dado real):** produto da Casal Branco aprovado; em seguida a mesma linha com erro injetado → semáforo vermelho com a causa exata, **antes do embarque**.
3. **Documentos (agente):** BL + invoice + packing list → operação extraída e divergências.
4. **Mercado (agente):** dados reais do NCM em Santos alimentando o risco.
5. **Decisão (engine):** cais × retroporto lado a lado, break-even, P(estouro) e economia por contêiner.
6. **Relatório:** resumo executivo para o despachante; nota de transparência sobre o que é simulado.

---

## Apêndice — Premissas conhecidas e limites

- Regras de catálogo vêm exclusivamente da planilha `DUIMP_Casal_Branco_1808.xlsm` (3 NCMs de vinho, atributos MAPA). O sistema não verifica se a **NCM está correta** para o produto, apenas se os atributos exigidos para aquela NCM estão coerentes.
- Não há acesso ao Portal Único no MVP (exige certificado digital).
- Nenhum número do relatório é gerado pelo agente; se o agente redigir texto, os valores são conferidos contra o engine.
