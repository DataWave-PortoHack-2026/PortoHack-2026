"""Testes unitários dos contratos Pydantic do DataWave."""
from pydantic import ValidationError

from datawave.schemas import (
    FaixaArmazenagem,
    MercadoNCM,
    OperacaoExtraida,
    RecomendacaoDecisao,
    SugestaoAtributos,
    TarifasConfig,
)


def test_operacao_extraida_valida():
    op = OperacaoExtraida(
        ncm="8481.80.95",
        descricao="Válvula de controle de fluxo",
        valor_lote_usd=50000.0,
        qtd_conteineres=2,
        incoterm="FOB",
        porto_descarga="Santos",
        armador="Maersk",
        divergencias=["Divergência de peso"]
    )
    assert op.ncm == "8481.80.95"
    assert op.qtd_conteineres == 2
    assert len(op.divergencias) == 1


def test_operacao_extraida_valor_negativo_erro():
    erro_disparado = False
    try:
        OperacaoExtraida(
            ncm="8481.80.95",
            descricao="Item Inválido",
            valor_lote_usd=-100.0
        )
    except ValidationError:
        erro_disparado = True
    assert erro_disparado, "Deveria lançar ValidationError para valor negativo"


def test_mercado_ncm_com_tempos_canal():
    mercado = MercadoNCM(
        ncm="8481.80.95",
        periodo="12 meses",
        origens_top=["Alemanha", "China"],
        dias_chegada_desembaraco={"canal_verde": 3.0, "canal_vermelho": 16.0}
    )
    assert mercado.ncm == "8481.80.95"
    assert mercado.dias_chegada_desembaraco["canal_verde"] == 3.0


def test_sugestao_atributos():
    sugestao = SugestaoAtributos(
        sugestoes={"ATT_14200": "07"},
        incertos=["ATT_14186"]
    )
    assert sugestao.sugestoes["ATT_14200"] == "07"
    assert "ATT_14186" in sugestao.incertos


def test_tarifas_config_defaults():
    cfg = TarifasConfig(
        cambio_usd_brl=5.20,
        free_time_demurrage_dias=7,
        demurrage_diaria_usd=150.0
    )
    assert cfg.cambio_usd_brl == 5.20
    assert cfg.free_time_demurrage_dias == 7
    assert cfg.demurrage_diaria_usd == 150.0


if __name__ == "__main__":
    test_operacao_extraida_valida()
    test_operacao_extraida_valor_negativo_erro()
    test_mercado_ncm_com_tempos_canal()
    test_sugestao_atributos()
    test_tarifas_config_defaults()
    print("test_schemas: todos os testes passaram com sucesso.")
