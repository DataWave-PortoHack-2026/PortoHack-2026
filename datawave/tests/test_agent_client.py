"""Testes unitários para o cliente do Agente DataWave (FakeAgent e parsing JSON)."""
import json

from datawave.agent_client import AgentClient, AgentRefusalError, FakeAgent
from datawave.schemas import MercadoNCM, OperacaoExtraida, SugestaoAtributos


def test_fake_agent_ask_operacao():
    client = FakeAgent()
    op = client.ask_json("Analise o Bill of Lading e a Invoice", OperacaoExtraida)
    assert isinstance(op, OperacaoExtraida)
    assert op.ncm == "8481.80.95"
    assert op.qtd_conteineres >= 1
    assert len(op.divergencias) > 0


def test_fake_agent_ask_mercado():
    client = FakeAgent()
    mercado = client.ask_json("Consulte os dados de MercadoNCM para Santos", MercadoNCM)
    assert isinstance(mercado, MercadoNCM)
    assert mercado.ncm == "8481.80.95"
    assert "Alemanha" in mercado.origens_top


def test_fake_agent_ask_atributos():
    client = FakeAgent()
    sugestao = client.ask_json("Sugira os atributos para esta NCM", SugestaoAtributos)
    assert isinstance(sugestao, SugestaoAtributos)
    assert "ATT_14200" in sugestao.sugestoes


class MockFencedAgent(AgentClient):
    """Simula um agente que insere cercas de código markdown na resposta."""
    def ask_agent(self, message, attachments=None, conversation_id=None):
        payload = {
            "ncm": "8481.80.95",
            "descricao": "Item com markdown",
            "valor_lote_usd": 10000.0,
            "qtd_conteineres": 1
        }
        return f"```json\n{json.dumps(payload)}\n```"


def test_limpeza_markdown_fences():
    client = MockFencedAgent()
    op = client.ask_json("Envie a operacao", OperacaoExtraida)
    assert op.descricao == "Item com markdown"
    assert op.valor_lote_usd == 10000.0


class MockRefusalAgent(AgentClient):
    """Simula acionamento do guardrail da Logcomex."""
    def ask_agent(self, message, attachments=None, conversation_id=None):
        return "Não posso responder a essa pergunta. Consulte trust.logcomex.ai para mais detalhes."


def test_tratamento_recusa_guardrail():
    client = MockRefusalAgent()
    recusou = False
    try:
        client.ask_json("Pergunta bloqueada", OperacaoExtraida)
    except AgentRefusalError:
        recusou = True
    assert recusou, "Deveria lançar AgentRefusalError"


class MockRetryAgent(AgentClient):
    """Simula resposta inválida na primeira tentativa e corrigida no retry."""
    def __init__(self):
        self.tentativas = 0

    def ask_agent(self, message, attachments=None, conversation_id=None):
        self.tentativas += 1
        if self.tentativas == 1:
            return "texto invalido que nao e json"
        return json.dumps({
            "ncm": "8481.80.95",
            "descricao": "Corrigido no retry",
            "valor_lote_usd": 25000.0,
            "qtd_conteineres": 1
        })


def test_retry_com_correcao():
    client = MockRetryAgent()
    op = client.ask_json("Envie operacao", OperacaoExtraida, max_retries=2)
    assert client.tentativas == 2
    assert op.descricao == "Corrigido no retry"


def test_fake_agent_resolucao_fixture_u1_mercado_vinho():
    """Valida se o FakeAgent resolve a fixture gravada de mercado para vinhos (NCM 2204.21.00)."""
    client = FakeAgent()
    mercado = client.ask_json("Consulta de mercado para vinhos NCM 2204.21.00 no Porto de Santos", MercadoNCM)
    assert mercado.ncm == "2204.21.00"
    assert "Portugal" in mercado.origens_top
    assert "Chile" in mercado.origens_top
    assert mercado.dias_chegada_desembaraco["canal_verde"] == 2.8


def test_fake_agent_resolucao_fixture_u2_conferencia_documental():
    """Valida se o FakeAgent resolve a fixture de conferência técnica documental (NCM 2905.11.00)."""
    client = FakeAgent()
    op = client.ask_json("Executar conferência técnica de documentos para importação", OperacaoExtraida)
    assert op.ncm == "2905.11.00"
    assert op.qtd_conteineres == 1
    assert any("22.400 kg" in d for d in op.divergencias)


def test_fake_agent_resolucao_fixture_u3_atributos_duimp():
    """Valida se o FakeAgent resolve a fixture de sugestão de atributos normativos do Catálogo DUIMP."""
    client = FakeAgent()
    sugestao = client.ask_json("Sugestão de atributos normativos do Catálogo DUIMP para Vinho Casal Branco", SugestaoAtributos)
    assert sugestao.sugestoes.get("ATT_14200") == "07"
    assert "ATT_14186" in sugestao.incertos


def test_fake_agent_resolucao_fixture_u4_justificativa_executiva():
    """Valida se o FakeAgent resolve a fixture de parecer executivo formal do despachante."""
    client = FakeAgent()
    resp_text = client.ask_agent("Apresente a justificativa técnica para o despachante aduaneiro")
    resp_json = json.loads(resp_text)
    assert resp_json.get("decisao_recomendada") == "RETROPORTO"
    assert "6.425" in str(resp_json)


def test_logcomex_mcp_agent_com_caller():
    """Valida invocação síncrona com mcp_caller customizado."""
    from datawave.agent_client import LogcomexMCPAgent

    def mock_mcp(tool_name, arguments, timeout):
        assert tool_name == "chat_with_agent"
        assert arguments["agent_id"] == "c2322f9c-41e2-4bf8-8fe5-3bd93f4063d4"
        return "Resposta mockada do agente via MCP."

    client = LogcomexMCPAgent(mcp_caller=mock_mcp)
    resp = client.ask_agent("Olá agente")
    assert resp == "Resposta mockada do agente via MCP."


def test_logcomex_mcp_agent_async_polling():
    """Valida resolução de resposta assíncrona com task_id e get_task_status."""
    from datawave.agent_client import LogcomexMCPAgent

    chamadas = []

    def mock_mcp_async(tool_name, arguments, timeout):
        chamadas.append(tool_name)
        if tool_name == "chat_with_agent":
            return 'A resposta está demorando mais do que o limite síncrono (18s). Use a tool get_task_status com task_id="task-12345" para obter o resultado.'
        elif tool_name == "get_task_status":
            assert arguments["task_id"] == "task-12345"
            return "Parecer técnico finalizado com sucesso."
        return ""

    client = LogcomexMCPAgent(mcp_caller=mock_mcp_async, timeout_seconds=10)
    resp = client.ask_agent("Gere parecer longo", poll_interval=0.01)
    assert resp == "Parecer técnico finalizado com sucesso."
    assert "chat_with_agent" in chamadas
    assert "get_task_status" in chamadas


if __name__ == "__main__":
    test_fake_agent_ask_operacao()
    test_fake_agent_ask_mercado()
    test_fake_agent_ask_atributos()
    test_limpeza_markdown_fences()
    test_tratamento_recusa_guardrail()
    test_retry_com_correcao()
    test_fake_agent_resolucao_fixture_u1_mercado_vinho()
    test_fake_agent_resolucao_fixture_u2_conferencia_documental()
    test_fake_agent_resolucao_fixture_u3_atributos_duimp()
    test_fake_agent_resolucao_fixture_u4_justificativa_executiva()
    test_logcomex_mcp_agent_com_caller()
    test_logcomex_mcp_agent_async_polling()
    print("test_agent_client: todos os testes passaram com sucesso.")

