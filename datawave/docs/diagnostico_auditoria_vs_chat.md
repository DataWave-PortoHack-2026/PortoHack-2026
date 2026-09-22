# Relatório Técnico de Diagnóstico: Auditoria (Pipeline) vs. Chat com o Agente Logcomex

**Data:** 22 de Setembro de 2026  
**Sistema:** DataWave AI Aduaneira — Porto de Santos  
**Componente:** Orquestrador de Pipeline, Agente MCP Logcomex e Interface Web  

---

## 1. Sumário Executivo

Durante os testes em ambiente de produção (Render), observou-se uma discrepância no tempo de resposta e no comportamento operacional:
- O **Chat com o Agente** leva aproximadamente **31 a 33 segundos** para responder.
- A **Auditoria Cadastral da Planilha/Cenário (Pipeline)** concluía em cerca de **4 segundos**.

Este relatório documenta a causa raiz exata dessa assimetria, evidenciando por que a auditoria não estava acionando o processamento assíncrono do Agente Logcomex em tempo real, e detalha o plano de correção arquitetural para que a auditoria opere de fato o modelo cognitivo do agente.

---

## 2. Diagnóstico da Causa Raiz

### 2.1 Por que o Chat com o Agente leva ~31 a 33 segundos?
No endpoint `/api/agente/chat` (`datawave/main.py`), a chamada ao agente é executada diretamente pelo método `LogcomexMCPAgent.ask_agent(msg, skill="auditoria_aduaneira")`:
1. O backend envia uma requisição JSON-RPC `chat_with_agent` para o endpoint `https://mcp.logcomex.ai/`.
2. Como o processamento do modelo LLM é custoso e analítico, o servidor MCP da Logcomex responde inicialmente com um identificador de tarefa assíncrona:
   `task_id="2ee9a202-c2bc-43f5-8cc8-6318e779ce2e"`
3. O cliente Python entra em um laço de espera e sondagem (`polling` a cada 3 segundos via `get_task_status`).
4. Durante aproximadamente 30 a 33 segundos, o cluster de inteligência artificial da Logcomex processa o contexto aduaneiro, consulta suas fontes internas e formula a resposta.
5. Logo, os 33 segundos do chat são a prova empírica de que o agente remoto está de fato trabalhando e inferindo em tempo real.

### 2.2 Por que a Auditoria (Pipeline) terminava em apenas 4 segundos?
No endpoint `/api/pipeline` e `/api/despachante/processar-planilha` (`datawave/pipeline.py`), identificamos três travas arquiteturais que desviavam o fluxo antes que o agente real pudesse atuar:

1. **Barreira do `check_health()` prévio:**
   Antes de invocar o agente, o pipeline executava:
   ```python
   mcp_ag = LogcomexMCPAgent()
   if mcp_ag.check_health():
       client = mcp_ag
   else:
       client = FakeAgent() # Desvio imediato para mock local
   ```
   O método `check_health()` tentava listar os agentes (`list_agents`) com um timeout agressivo de apenas 2.5 segundos. Em conexões de nuvem como o Render, qualquer latência de rede fazia o health check falhar silenciosamente, forçando o pipeline a usar o `FakeAgent` (fixtures locais em disco).

2. **Tentativa de Desserialização Rígida de Schemas (`ask_json`):**
   O pipeline tentava submeter três prompts concorrentes (`OperacaoExtraida`, `MercadoNCM`, `SugestaoAtributos`) esperando blocos JSON estruturados puros. Quando o agente remoto da Logcomex respondia em linguagem natural ou com `task_id`, o validador do Pydantic falhava e imediatamente recorria ao mock local (`FakeAgent`), que respondia em 0.01 segundo.

3. **Temporizadores Cosméticos no Frontend:**
   No arquivo `index.html`, a função `executarCicloProgressoEtapas` definia timers fixos de ~750ms totalizando ~3.8 segundos. Como o backend retornava quase instantaneamente pelo desvio do `FakeAgent`, o frontend finalizava em exatos 4 segundos, dando a falsa impressão de que a auditoria havia terminado, sem ter operado o agente no servidor remoto.

---

## 3. Plano de Correção e Unificação Operacional

Para garantir que a auditoria execute e opere de verdade o Agente Logcomex, as seguintes modificações foram projetadas:

1. **Invocação Direta do Agente no Pipeline:**
   Remover o descarte prematuro do `check_health()`. O pipeline deve instanciar o `LogcomexMCPAgent` e enviar o dossiê da carga (NCM, descrição, valores FOB, pesos bruto/líquido, packing list e porto de Santos) diretamente via `agent.ask_agent(prompt_auditoria, skill="auditoria_aduaneira")`.

2. **Ajuste no Polling Assíncrono do MCP (`agent_client.py`):**
   Corrigir a condição de interrupção do loop de polling para que o cliente não retorne mensagens intermediárias (como *"Ainda processando (25s decorridos)..."*), garantindo que aguarde a emissão da síntese pericial conclusiva do agente.

3. **Integração Real do Parecer Pericial:**
   O parecer técnico e a justificativa prescritiva da Tela 3 serão alimentados diretamente pelo texto pericial emitido pelo Agente Logcomex no servidor MCP.

4. **Sincronização Visual do Frontend:**
   O indicador de progresso global (`#globalPipelineTracker`) acompanhará a execução assíncrona real da requisição (exibindo o status de consulta pericial ao Agente Logcomex durante os ~30s necessários), alinhando a percepção do usuário com o tempo de processamento genuíno da IA.
