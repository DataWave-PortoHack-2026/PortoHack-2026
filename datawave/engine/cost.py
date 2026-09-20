"""Motor determinístico de custos e recomendação de permanência (Módulos C e D).

Calcula os custos diários comparativos de permanência no cais (zona primária)
versus retroporto (zona secundária), determina o ponto de equilíbrio (break-even)
e gera a recomendação ótima para o importador e despachante.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from datawave.schemas import (
    OperacaoExtraida,
    RecomendacaoDecisao,
    ResultadoCustoDiario,
    TarifasConfig,
)


def carregar_tarifas(caminho: Optional[str | Path] = None) -> TarifasConfig:
    """Carrega o arquivo tarifas.yaml em um objeto TarifasConfig validado."""
    if caminho is None:
        caminho = Path(__file__).parent.parent / "data" / "tarifas.yaml"
    p = Path(caminho)
    with open(p, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return TarifasConfig.model_validate(raw)


def calcular_armazenagem_cais(
    dias: int,
    op: OperacaoExtraida,
    tarifas: TarifasConfig
) -> float:
    """Calcula a armazenagem progressiva portuária no cais para o número de dias."""
    if dias <= 0:
        return 0.0

    valor_cif_brl = op.valor_lote_usd * tarifas.cambio_usd_brl
    total_armazenagem = 0.0

    for faixa in tarifas.faixas_armazenagem_cais:
        if dias >= faixa.dia_inicio:
            custo_faixa = max(
                faixa.tarifa_minima_brl,
                faixa.percentual_cif * valor_cif_brl
            ) * op.qtd_conteineres
            total_armazenagem += custo_faixa

    return round(total_armazenagem, 2)


def calcular_demurrage_cais(
    dias: int,
    op: OperacaoExtraida,
    tarifas: TarifasConfig
) -> float:
    """Calcula a sobre-estadia de contêiner cheio no cais após o free time."""
    dias_excedentes = max(0, dias - tarifas.free_time_demurrage_dias)
    custo_usd = dias_excedentes * tarifas.demurrage_diaria_usd * op.qtd_conteineres
    custo_brl = custo_usd * tarifas.cambio_usd_brl
    return round(custo_brl, 2)


def calcular_custo_cais(
    dias: int,
    op: OperacaoExtraida,
    tarifas: TarifasConfig
) -> Tuple[float, float, float]:
    """Retorna (custo_total_cais, armazenagem, demurrage)."""
    armazenagem = calcular_armazenagem_cais(dias, op, tarifas)
    demurrage = calcular_demurrage_cais(dias, op, tarifas)
    total = round(armazenagem + demurrage, 2)
    return total, armazenagem, demurrage


def calcular_custo_retro(
    dias: int,
    op: OperacaoExtraida,
    tarifas: TarifasConfig,
    dias_devolucao_vazio: Optional[int] = None
) -> Tuple[float, float, float, float]:
    """Retorna (custo_total_retro, armazenagem_retro, custos_fixos_transferencia, detention)."""
    if dias <= 0:
        return 0.0, 0.0, 0.0, 0.0

    valor_cif_brl = op.valor_lote_usd * tarifas.cambio_usd_brl

    # 1. Custos fixos operacionais de remoção/transferência
    fixos_por_conteiner = (
        tarifas.frete_transferencia_dta_brl
        + tarifas.movimentacao_terminal_brl
        + tarifas.movimentacao_retro_brl
    )
    custos_fixos = round(fixos_por_conteiner * op.qtd_conteineres, 2)

    # 2. Armazenagem diária e seguro aduaneiro no retroporto
    seguro = tarifas.retro_seguro_percentual_cif * valor_cif_brl * op.qtd_conteineres
    diarias = dias * tarifas.retro_diaria_brl_por_conteiner * op.qtd_conteineres
    armazenagem_retro = round(diarias + seguro, 2)

    # 3. Detention (sobre-estadia do vazio após desova)
    # Premissa operacional: na transferência para o retroporto, a desova ocorre em até 4 dias,
    # respeitando o free time padrão, salvo se especificado atraso na devolução do vazio.
    tempo_vazio = dias_devolucao_vazio if dias_devolucao_vazio is not None else min(dias, 4)
    dias_excedentes_vazio = max(0, tempo_vazio - tarifas.free_time_detention_dias)
    detention_usd = dias_excedentes_vazio * tarifas.detention_diaria_usd * op.qtd_conteineres
    detention = round(detention_usd * tarifas.cambio_usd_brl, 2)

    total = round(custos_fixos + armazenagem_retro + detention, 2)
    return total, armazenagem_retro, custos_fixos, detention


def calcular_curva_e_break_even(
    op: OperacaoExtraida,
    tarifas: TarifasConfig,
    max_dias: int = 60
) -> Tuple[Optional[int], List[ResultadoCustoDiario]]:
    """Gera a projeção dia a dia de custos e localiza o dia do break-even (d*)."""
    curva: List[ResultadoCustoDiario] = []
    dia_break_even: Optional[int] = None

    for d in range(1, max_dias + 1):
        total_cais, arm_cais, dem_cais = calcular_custo_cais(d, op, tarifas)
        total_retro, arm_retro, fixos_transf, det_retro = calcular_custo_retro(d, op, tarifas)
        diferenca = round(total_cais - total_retro, 2)

        curva.append(
            ResultadoCustoDiario(
                dias=d,
                custo_cais_brl=total_cais,
                custo_retro_brl=total_retro,
                armazenagem_cais_brl=arm_cais,
                demurrage_cais_brl=dem_cais,
                armazenagem_retro_brl=arm_retro,
                custos_fixos_transferencia_brl=fixos_transf,
                detention_retro_brl=det_retro,
                diferenca_economia_brl=diferenca
            )
        )

        # O break-even ocorre no primeiro dia em que o custo do cais supera o retroporto
        if dia_break_even is None and diferenca > 0:
            dia_break_even = d

    return dia_break_even, curva


def gerar_recomendacao(
    op: OperacaoExtraida,
    tarifas: TarifasConfig,
    distribuicao_permanencia: Dict[int, float],
    max_dias: int = 60
) -> RecomendacaoDecisao:
    """Calcula a recomendação ótima com base no valor esperado e percentil P90."""
    dia_break_even, curva = calcular_curva_e_break_even(op, tarifas, max_dias=max_dias)

    # 1. Normalizar distribuição de probabilidades e calcular valores esperados
    soma_prob = sum(distribuicao_permanencia.values())
    if soma_prob <= 0:
        raise ValueError("Distribuição de permanência com soma de probabilidades inválida.")

    p_norm = {d: prob / soma_prob for d, prob in distribuicao_permanencia.items()}

    custo_esp_cais = 0.0
    custo_esp_retro = 0.0
    prob_estouro_free_time = 0.0

    # P90
    prob_acumulada = 0.0
    p90 = max_dias
    p90_definido = False

    for d in sorted(p_norm.keys()):
        prob = p_norm[d]
        custo_c, _, _ = calcular_custo_cais(d, op, tarifas)
        custo_r, _, _, _ = calcular_custo_retro(d, op, tarifas)

        custo_esp_cais += prob * custo_c
        custo_esp_retro += prob * custo_r

        if d > tarifas.free_time_demurrage_dias:
            prob_estouro_free_time += prob

        prob_acumulada += prob
        if not p90_definido and prob_acumulada >= 0.90:
            p90 = d
            p90_definido = True

    custo_esp_cais = round(custo_esp_cais, 2)
    custo_esp_retro = round(custo_esp_retro, 2)
    prob_estouro_free_time = round(prob_estouro_free_time, 4)

    # 2. Decisão estratégica
    if custo_esp_retro < custo_esp_cais:
        opcao = "RETROPORTO"
        economia = round(custo_esp_cais - custo_esp_retro, 2)
        justificativa = (
            f"Recomendação: TRANSFERIR PARA O RETROPORTO. "
            f"O ponto de equilíbrio (break-even) ocorre no dia {dia_break_even}. "
            f"Com probabilidade de {prob_estouro_free_time * 100:.1f}% de exceder o free time ({tarifas.free_time_demurrage_dias} dias) "
            f"e P90 estimado em {p90} dias, a transferência evita as faixas progressivas do cais e o demurrage em dólares, "
            f"gerando uma economia esperada de R$ {economia:,.2f} no lote."
        )
    else:
        opcao = "CAIS"
        economia = round(custo_esp_retro - custo_esp_cais, 2)
        justificativa = (
            f"Recomendação: MANTER E DESEMBARAÇAR NO CAIS. "
            f"O tempo de permanência estimado (P90 de {p90} dias) indica baixa probabilidade de sobre-estadia. "
            f"Os custos fixos de remoção rodoviária e movimentação para o retroporto (R$ {curva[0].custos_fixos_transferencia_brl:,.2f}) "
            f"superam o custo de armazenagem portuária no cais para o período previsto, com economia estimada de R$ {economia:,.2f}."
        )

    return RecomendacaoDecisao(
        opcao_recomendada=opcao,
        dia_break_even=dia_break_even,
        economia_esperada_brl=economia,
        probabilidade_estouro_free_time=prob_estouro_free_time,
        custo_esperado_cais_brl=custo_esp_cais,
        custo_esperado_retro_brl=custo_esp_retro,
        p90_dias_permanencia=p90,
        justificativa=justificativa,
        curva_sensibilidade=curva
    )
