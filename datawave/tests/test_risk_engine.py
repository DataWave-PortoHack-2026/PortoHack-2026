"""Testes unitários para o motor determinístico de risco e permanência (Módulo B)."""
from datawave.engine.risk import (
    carregar_priors_risco,
    simular_permanencia_monte_carlo,
)
from datawave.schemas import MercadoNCM, OperacaoExtraida


def criar_operacao(divergencias=None):
    return OperacaoExtraida(
        ncm="8481.80.95",
        descricao="Válvulas industriais",
        valor_lote_usd=50000.0,
        qtd_conteineres=1,
        incoterm="FOB",
        porto_descarga="Santos",
        divergencias=divergencias or []
    )


def test_carregar_priors_risco():
    priors = carregar_priors_risco()
    assert "canais_probabilidade_padrao" in priors
    assert priors["canais_probabilidade_padrao"]["verde"] == 0.88
    assert "permanencia_dias_por_canal" in priors
    assert "modificadores_risco" in priors


def test_monte_carlo_semente_fixa_reprodutibilidade():
    op = criar_operacao()
    # Duas execuções com a mesma semente devem gerar exatamente o mesmo resultado
    res1 = simular_permanencia_monte_carlo(op, seed=42, n_amostras=5000)
    res2 = simular_permanencia_monte_carlo(op, seed=42, n_amostras=5000)

    assert res1.permanencia_media == res2.permanencia_media
    assert res1.permanencia_p50 == res2.permanencia_p50
    assert res1.permanencia_p90 == res2.permanencia_p90
    assert res1.probabilidade_estouro_free_time == res2.probabilidade_estouro_free_time
    assert res1.distribuicao_dias == res2.distribuicao_dias


def test_monte_carlo_cenario_padrao_verde():
    op = criar_operacao()
    res = simular_permanencia_monte_carlo(op, free_time_dias=7, seed=42, n_amostras=5000)

    # No cenário padrão (sem anuente e sem divergência), a maior parte é canal verde
    assert res.canal_mais_provavel == "verde"
    assert 2.0 <= res.permanencia_media <= 4.5
    # Risco de estourar 7 dias de free time no padrão deve ser baixo (< 10%)
    assert res.probabilidade_estouro_free_time < 0.10
    # A soma das probabilidades da distribuição de dias deve ser 1.0 (tolerância de arredondamento)
    assert abs(sum(res.distribuicao_dias.values()) - 1.0) < 0.01


def test_monte_carlo_com_orgao_anuente():
    op = criar_operacao()
    res_padrao = simular_permanencia_monte_carlo(op, free_time_dias=7, seed=42, n_amostras=5000)
    res_anuente = simular_permanencia_monte_carlo(
        op, orgao_anuente=True, free_time_dias=7, seed=42, n_amostras=5000
    )

    # Com órgão anuente, a permanência média e a probabilidade de estouro aumentam significativamente
    assert res_anuente.permanencia_media > res_padrao.permanencia_media
    assert res_anuente.permanencia_p90 > res_padrao.permanencia_p90
    assert res_anuente.probabilidade_estouro_free_time > res_padrao.probabilidade_estouro_free_time
    assert res_anuente.probabilidade_estouro_free_time > 0.20
    assert "orgao_anuente_presente" in res_anuente.fatores_agravantes_aplicados


def test_monte_carlo_com_operador_oea():
    op = criar_operacao()
    res_comum = simular_permanencia_monte_carlo(op, orgao_anuente=True, seed=42, n_amostras=5000)
    res_oea = simular_permanencia_monte_carlo(
        op, orgao_anuente=True, operador_oea=True, seed=42, n_amostras=5000
    )

    # Certificação OEA mitiga o risco e reduz a permanência média
    assert res_oea.permanencia_media < res_comum.permanencia_media
    assert res_oea.probabilidade_estouro_free_time < res_comum.probabilidade_estouro_free_time
    assert "operador_oea" in res_oea.fatores_agravantes_aplicados


def test_monte_carlo_com_dados_reais_agente():
    op = criar_operacao()
    # Dados simulando retorno de U1 do Agente Logcomex
    mercado_real = MercadoNCM(
        ncm="8481.80.95",
        periodo="Últimos 12 meses",
        dias_chegada_desembaraco={
            "canal_verde": 1.8,
            "canal_amarelo": 4.5,
            "canal_vermelho": 14.0
        }
    )
    res = simular_permanencia_monte_carlo(op, mercado_ncm=mercado_real, seed=42, n_amostras=5000)
    assert res.fonte_parametros == "agente_logcomex"
    # Como as médias reais são menores que as premissas padrão (1.8 vs 2.5), a permanência média deve ser menor
    res_premissa = simular_permanencia_monte_carlo(op, seed=42, n_amostras=5000)
    assert res.permanencia_media < res_premissa.permanencia_media


def test_integracao_risco_e_custo():
    from datawave.engine.cost import carregar_tarifas, gerar_recomendacao

    op = criar_operacao()
    tarifas = carregar_tarifas()

    # 1. No cenário padrão, Monte Carlo gera concentração em canal verde -> CAIS
    risco_verde = simular_permanencia_monte_carlo(op, free_time_dias=7, seed=42, n_amostras=5000)
    rec_verde = gerar_recomendacao(op, tarifas, risco_verde.distribuicao_dias)
    assert rec_verde.opcao_recomendada == "CAIS"

    # 2. No cenário com órgão anuente e divergência documental, risco migra para retenção -> RETROPORTO
    op_divergente = criar_operacao(divergencias=["Divergência de 450 kg no peso"])
    risco_retencao = simular_permanencia_monte_carlo(
        op_divergente, orgao_anuente=True, free_time_dias=7, seed=42, n_amostras=5000
    )
    rec_retencao = gerar_recomendacao(op_divergente, tarifas, risco_retencao.distribuicao_dias)
    assert rec_retencao.opcao_recomendada == "RETROPORTO"
    assert rec_retencao.probabilidade_estouro_free_time > 0.30


if __name__ == "__main__":
    test_carregar_priors_risco()
    test_monte_carlo_semente_fixa_reprodutibilidade()
    test_monte_carlo_cenario_padrao_verde()
    test_monte_carlo_com_orgao_anuente()
    test_monte_carlo_com_operador_oea()
    test_monte_carlo_com_dados_reais_agente()
    test_integracao_risco_e_custo()
    print("test_risk_engine: todos os testes passaram com sucesso.")
