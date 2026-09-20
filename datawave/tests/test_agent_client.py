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
    print("test_agent_client: todos os testes passaram com sucesso.")
