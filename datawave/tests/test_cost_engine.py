"""Testes unitários para o motor determinístico de custos e recomendação."""
from datawave.engine.cost import (
    calcular_armazenagem_cais,
    calcular_curva_e_break_even,
    calcular_custo_cais,
    calcular_custo_retro,
    calcular_demurrage_cais,
    carregar_tarifas,
    gerar_recomendacao,
)
from datawave.schemas import OperacaoExtraida


def criar_operacao():
    return OperacaoExtraida(
        ncm="8481.80.95",
        descricao="Válvulas industriais",
        valor_lote_usd=50000.0,
        qtd_conteineres=1,
        incoterm="FOB",
        porto_descarga="Santos"
    )


def test_armazenagem_cais_progressiva():
    op = criar_operacao()
    tarifas = carregar_tarifas()

    # Dia 5: Faixa 1 (1 a 7 dias)
    custo_5d = calcular_armazenagem_cais(5, op, tarifas)
    assert custo_5d > 0

    # Dia 10: Faixa 1 + Faixa 2 (cumulativa pelos períodos atingidos)
    custo_10d = calcular_armazenagem_cais(10, op, tarifas)
    assert custo_10d > custo_5d

    # Dia 20: Faixas 1 + 2 + 3
    custo_20d = calcular_armazenagem_cais(20, op, tarifas)
    assert custo_20d > custo_10d


def test_demurrage_cais_free_time():
    op = criar_operacao()
    tarifas = carregar_tarifas()

    # Até o free time (7 dias), demurrage é zero
    assert calcular_demurrage_cais(7, op, tarifas) == 0.0
    assert calcular_demurrage_cais(5, op, tarifas) == 0.0

    # No dia 10 (3 dias de excesso): 3 * 150 USD * 5.20 = 2340.0 BRL
    esperado = round(3 * tarifas.demurrage_diaria_usd * tarifas.cambio_usd_brl, 2)
    assert calcular_demurrage_cais(10, op, tarifas) == esperado


def test_custo_retro_fixo_e_linear():
    op = criar_operacao()
    tarifas = carregar_tarifas()

    # Custos fixos de transferência: frete (1300) + mov_terminal (900) + mov_retro (500) = 2700 BRL
    total_1d, arm_1d, fixos, det = calcular_custo_retro(1, op, tarifas)
    assert fixos == 2700.0
    assert det == 0.0
    assert total_1d > fixos

    # Acréscimo linear por dia de armazenagem
    total_5d, arm_5d, _, _ = calcular_custo_retro(5, op, tarifas)
    assert total_5d > total_1d


def test_curva_e_break_even():
    op = criar_operacao()
    tarifas = carregar_tarifas()

    dia_be, curva = calcular_curva_e_break_even(op, tarifas, max_dias=40)
    assert len(curva) == 40
    # Deve existir um dia de corte onde o cais supera o retroporto
    assert dia_be is not None
    assert 1 < dia_be < 30

    # No dia anterior ao break-even, cais deve ser mais barato ou igual
    if dia_be > 1:
        assert curva[dia_be - 2].diferenca_economia_brl <= 0
    # No dia do break-even, retroporto deve ser mais barato (diferenca positiva)
    assert curva[dia_be - 1].diferenca_economia_brl > 0


def test_recomendacao_cenario_rapido_cais():
    op = criar_operacao()
    tarifas = carregar_tarifas()

    # Cenário canal verde: permanência concentrada em 2 a 4 dias
    distribuicao_verde = {2: 0.6, 3: 0.3, 4: 0.1}
    rec = gerar_recomendacao(op, tarifas, distribuicao_verde)
    assert rec.opcao_recomendada == "CAIS"
    assert rec.probabilidade_estouro_free_time == 0.0
    assert "MANTER E DESEMBARAÇAR NO CAIS" in rec.justificativa


def test_recomendacao_cenario_retencao_retroporto():
    op = criar_operacao()
    tarifas = carregar_tarifas()

    # Cenário canal vermelho com retenção: permanência de 15 a 25 dias
    distribuicao_vermelho = {15: 0.2, 18: 0.4, 22: 0.3, 25: 0.1}
    rec = gerar_recomendacao(op, tarifas, distribuicao_vermelho)
    assert rec.opcao_recomendada == "RETROPORTO"
    assert rec.probabilidade_estouro_free_time == 1.0
    assert "TRANSFERIR PARA O RETROPORTO" in rec.justificativa
    assert rec.economia_esperada_brl > 0


if __name__ == "__main__":
    test_armazenagem_cais_progressiva()
    test_demurrage_cais_free_time()
    test_custo_retro_fixo_e_linear()
    test_curva_e_break_even()
    test_recomendacao_cenario_rapido_cais()
    test_recomendacao_cenario_retencao_retroporto()
    print("test_cost_engine: todos os testes passaram com sucesso.")
