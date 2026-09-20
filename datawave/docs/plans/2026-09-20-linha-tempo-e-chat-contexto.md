# Plano de Implementação — Linha do Tempo Autoral e Chat com Contexto Global no DataWave

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Linha do Tempo Autoral do Agente Logcomex e o Chat da Tela 4 com Contexto Global no DataWave.

**Architecture:** Aprimorar o prompt e o cliente do agente para geração dinâmica de cronogramas em 5 campos e integrar o estado de sessão de pipelines e planilhas ao contexto do chat da Tela 4.

**Tech Stack:** Python, FastAPI / HTTP Server, Pydantic, pytest.

## Global Constraints
- Proibição absoluta de emojis em código, textos, logs e mensagens.
- Timeout do `LogcomexMCPAgent` mantido estritamente em 300 segundos.
- 100% de aprovação na suíte de testes do pytest.

---

### Task 1: Linha do Tempo Autoral no Motor de Relatórios

**Files:**
- Modify: `datawave/engine/report.py`

- [ ] **Step 1: Implementar o prompt detalhado autoral em `gerar_linha_do_tempo_via_agente_logcomex`**
- [ ] **Step 2: Garantir que todos os 5 campos (`faixa_dias`, `fase`, `status_cais`, `status_retro`, `detalhes`) sejam gerados sem moldes fixos**

---

### Task 2: Suporte a Qualquer NCM e Contexto no FakeAgent

**Files:**
- Modify: `datawave/agent_client.py`

- [ ] **Step 1: Adicionar suporte dinâmico no `FakeAgent` para NCMs genéricos com os 5 campos completos**
- [ ] **Step 2: Implementar extração e respostas precisas com base no bloco `CONTEXTO OPERACIONAL DA SESSÃO DATAWAVE`**

---

### Task 3: Contexto Global da Aplicação no Servidor e Chat da Tela 4

**Files:**
- Modify: `datawave/main.py`

- [ ] **Step 1: Implementar `ultimo_resultado_pipeline` e sua atualização contínua**
- [ ] **Step 2: Implementar `montar_bloco_contexto_operacional`**
- [ ] **Step 3: Atualizar endpoint `/api/agente/chat` e função `responder_chat_agente` para anexar o contexto operacional ao prompt**

---

### Task 4: Testes Unitários e de Integração

**Files:**
- Modify: `datawave/tests/test_report_pipeline.py`
- Modify: `datawave/tests/test_api.py`

- [ ] **Step 1: Adicionar testes de linha do tempo autoral para múltiplos NCMs e genéricos**
- [ ] **Step 2: Adicionar testes de chat com contexto global e consultas sobre rota, divergências e custos**
- [ ] **Step 3: Executar a suíte completa de testes e validar 100% de sucesso**
