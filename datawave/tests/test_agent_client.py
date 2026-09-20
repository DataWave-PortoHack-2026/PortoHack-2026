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


if __name__ == "__main__":
    test_fake_agent_ask_operacao()
    test_fake_agent_ask_mercado()
    test_fake_agent_ask_atributos()
    test_limpeza_markdown_fences()
    test_tratamento_recusa_guardrail()
    test_retry_com_correcao()
    print("test_agent_client: todos os testes passaram com sucesso.")
