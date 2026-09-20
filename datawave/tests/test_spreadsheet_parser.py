"""Testes para o parser geral de planilhas aduaneiras."""
import pytest
from datawave.engine.spreadsheet_parser import (
    parsear_csv_planilha,
    consolidar_operacao_de_planilha,
    normalizar_registro_planilha
)


def test_parsear_csv_virgula_padrao():
    csv_conteudo = """ncm,descricao,quantidade,valor_unitario_usd,valor_total_usd,peso_bruto_bl_kg,peso_bruto_packing_kg,incoterm,porto_descarga
2204.21.00,Vinho Fino Tinto,1200,57.08,68500.0,14500.0,14150.0,FOB,Santos
"""
    itens = parsear_csv_planilha(csv_conteudo)
    assert len(itens) == 1
    item = itens[0]
    assert item.ncm == "2204.21.00"
    assert item.peso_bruto_bl_kg == 14500.0
    assert item.peso_bruto_packing_kg == 14150.0
    assert item.porto_descarga == "Santos"

    op, divergencias = consolidar_operacao_de_planilha(itens)
    assert op.valor_lote_usd == 68500.0
    assert len(divergencias) == 1
    assert "diferença de 350.0 kg" in divergencias[0] or "350" in divergencias[0]


def test_parsear_csv_ponto_e_virgula_brasileiro():
    csv_conteudo = """Classificação Fiscal;Descrição Mercadoria;Quantidade;Preço Unitário;Valor Total;Peso BL;Peso PL;Termo Venda;Porto Destino;ATT_14200
8481.80.95;Válvulas Industriais de Controle;10;6850,00;68500,00;14.500,0;14.050,0;FOB;Santos;07
"""
    itens = parsear_csv_planilha(csv_conteudo)
    assert len(itens) == 1
    item = itens[0]
    assert item.ncm == "8481.80.95"
    assert item.peso_bruto_bl_kg == 14500.0
    assert item.peso_bruto_packing_kg == 14050.0
    assert item.atributos_declarados.get("ATT_14200") == "07"

    op, divergencias = consolidar_operacao_de_planilha(itens)
    assert op.valor_lote_usd == 68500.0
    assert len(divergencias) == 1
    assert "450" in divergencias[0]


def test_consolidar_operacao_vazia_lanca_erro():
    with pytest.raises(ValueError, match="não contém itens"):
        consolidar_operacao_de_planilha([])
