"""Módulo B: Simulação de Permanência e Risco (Monte Carlo).

Executa simulação de Monte Carlo determinística (com semente pseudo-aleatória fixa)
para estimar a distribuição de permanência de contêineres no Porto de Santos,
integrando dados reais de mercado da Logcomex e priors estatísticos de canais e anuentes.
"""
from __future__ import annotations

import math
import random
import statistics
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from datawave.schemas import MercadoNCM, OperacaoExtraida, ResultadoRiscoPermanencia


def carregar_priors_risco(caminho_yaml: Optional[str] = None) -> dict:
    """Carrega as premissas e priors de risco aduaneiro."""
    if caminho_yaml is None:
        caminho = Path(__file__).parent.parent / "data" / "risk_priors.yaml"
    else:
        caminho = Path(caminho_yaml)

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de priors não encontrado: {caminho}")

    with open(caminho, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _calcular_percentil(dados: List[float], percentil: float) -> float:
    """Calcula o percentil exato a partir de uma lista ordenada."""
    dados_ord = sorted(dados)
    n = len(dados_ord)
    if n == 0:
        return 0.0
    idx = (percentil / 100.0) * (n - 1)
    inf = math.floor(idx)
    sup = math.ceil(idx)
    if inf == sup:
        return dados_ord[int(idx)]
    peso = idx - inf
    return (1.0 - peso) * dados_ord[inf] + peso * dados_ord[sup]


def simular_permanencia_monte_carlo(
    operacao: OperacaoExtraida,
    mercado_ncm: Optional[MercadoNCM] = None,
    orgao_anuente: bool = False,
    operador_oea: bool = False,
    free_time_dias: int = 7,
    seed: int = 42,
    n_amostras: int = 10000,
    caminho_priors: Optional[str] = None
) -> ResultadoRiscoPermanencia:
    """Simula a permanência da carga no porto via Monte Carlo determinístico.
    
    Args:
        operacao: Dados consolidados da operação aduaneira.
        mercado_ncm: Estatísticas reais de mercado obtidas do Agente Logcomex (U1).
        orgao_anuente: Indica se há interveniência de MAPA, Anvisa, Inmetro, Ibama, etc.
        operador_oea: Indica se o importador possui certificação OEA.
        free_time_dias: Dias livres contratados de sobre-estadia (demurrage).
        seed: Semente pseudo-aleatória para reprodutibilidade matemática.
        n_amostras: Quantidade de iterações do Monte Carlo.
        caminho_priors: Caminho opcional para o arquivo risk_priors.yaml.
        
    Returns:
        ResultadoRiscoPermanencia com métricas, percentis e distribuição de dias.
    """
    # Fixar semente para garantir determinismo rigoroso
    random.seed(seed)
    priors = carregar_priors_risco(caminho_priors)

    fatores_aplicados = []
    
    # 1. Definir probabilidades basais dos canais
    p_verde = priors["canais_probabilidade_padrao"]["verde"]
    p_amarelo = priors["canais_probabilidade_padrao"]["amarelo"]
    p_vermelho = priors["canais_probabilidade_padrao"]["vermelho"]

    # Ajuste por interveniência de Órgão Anuente
    if orgao_anuente:
        mod_anuente = priors["modificadores_risco"]["orgao_anuente_presente"]
        p_vermelho = mod_anuente["prob_vermelho_ajustada"]
        p_amarelo = mod_anuente["prob_amarelo_ajustada"]
        p_verde = mod_anuente["prob_verde_ajustada"]
        fatores_aplicados.append("orgao_anuente_presente")

    # Ajuste por Divergências Documentais (U2)
    if operacao.divergencias:
        mod_div = priors["modificadores_risco"]["divergencia_documental"]
        p_vermelho += mod_div["prob_vermelho_adicional"]
        p_amarelo += mod_div["prob_amarelo_adicional"]
        p_verde = max(0.05, 1.0 - p_vermelho - p_amarelo)
        fatores_aplicados.append("divergencia_documental")

    # Ajuste por Certificação OEA
    if operador_oea:
        mod_oea = priors["modificadores_risco"]["operador_oea"]
        reducao = p_vermelho * mod_oea["reducao_prob_vermelho_pct"]
        p_vermelho -= reducao
        p_verde += reducao
        fatores_aplicados.append("operador_oea")

    # Normalizar para garantir soma estrita de 1.0
    total_p = p_verde + p_amarelo + p_vermelho
    probabilidades = {
        "verde": p_verde / total_p,
        "amarelo": p_amarelo / total_p,
        "vermelho": p_vermelho / total_p,
    }

    canal_mais_provavel = max(probabilidades, key=probabilidades.get)

    # 2. Configurar parâmetros de permanência por canal
    dados_perm = priors["permanencia_dias_por_canal"]
    fonte_parametros = "estatistica_aduaneira_santos_premissa"

    medias = {
        "verde": dados_perm["verde"]["media"],
        "amarelo": dados_perm["amarelo"]["media"],
        "vermelho": dados_perm["vermelho"]["media"],
    }
    desvios = {
        "verde": dados_perm["verde"]["desvio"],
        "amarelo": dados_perm["amarelo"]["desvio"],
        "vermelho": dados_perm["vermelho"]["desvio"],
    }
    limites = {
        "verde": (dados_perm["verde"]["min"], dados_perm["verde"]["max"]),
        "amarelo": (dados_perm["amarelo"]["min"], dados_perm["amarelo"]["max"]),
        "vermelho": (dados_perm["vermelho"]["min"], dados_perm["vermelho"]["max"]),
    }

    # Se o agente fornecer dados reais observados para a NCM (U1), calibramos as médias
    if mercado_ncm and mercado_ncm.dias_chegada_desembaraco:
        dias_agente = mercado_ncm.dias_chegada_desembaraco
        if "canal_verde" in dias_agente and dias_agente["canal_verde"] is not None:
            medias["verde"] = float(dias_agente["canal_verde"])
            fonte_parametros = "agente_logcomex"
        if "canal_amarelo" in dias_agente and dias_agente["canal_amarelo"] is not None:
            medias["amarelo"] = float(dias_agente["canal_amarelo"])
            fonte_parametros = "agente_logcomex"
        if "canal_vermelho" in dias_agente and dias_agente["canal_vermelho"] is not None:
            medias["vermelho"] = float(dias_agente["canal_vermelho"])
            fonte_parametros = "agente_logcomex"

    # Fator de aceleração por OEA ou retardo por Anuente
    fator_tempo = 1.0
    acrescimo_vermelho = 0.0
    if operador_oea:
        fator_tempo = priors["modificadores_risco"]["operador_oea"]["fator_tempo_liberacao"]
    if orgao_anuente:
        acrescimo_vermelho = priors["modificadores_risco"]["orgao_anuente_presente"]["acrescimo_dias_vermelho"]

    # 3. Execução da Simulação de Monte Carlo
    canais_sorteados = random.choices(
        ["verde", "amarelo", "vermelho"],
        weights=[probabilidades["verde"], probabilidades["amarelo"], probabilidades["vermelho"]],
        k=n_amostras
    )

    amostras_dias: List[float] = []
    contagem_dias_inteiros: Dict[int, int] = {}

    for canal in canais_sorteados:
        m = medias[canal]
        s = desvios[canal]
        min_d, max_d = limites[canal]

        if canal == "vermelho":
            m += acrescimo_vermelho
            max_d += acrescimo_vermelho

        # Simular valor com distribuição normal truncada nos limites físicos
        val = random.gauss(m, s) * fator_tempo
        val_truncado = max(min_d * fator_tempo, min(val, max_d * fator_tempo))
        amostras_dias.append(val_truncado)

        dia_int = max(1, round(val_truncado))
        contagem_dias_inteiros[dia_int] = contagem_dias_inteiros.get(dia_int, 0) + 1

    # 4. Cálculo das Métricas e Distribuição Probabilística
    media_final = round(statistics.mean(amostras_dias), 2)
    p50_final = round(statistics.median(amostras_dias), 2)
    p90_final = round(_calcular_percentil(amostras_dias, 90.0), 2)

    estouros = sum(1 for d in amostras_dias if d > free_time_dias)
    prob_estouro = round(estouros / n_amostras, 4)

    # Ordenar distribuição por dia
    distribuicao_dias: Dict[int, float] = {}
    for d in sorted(contagem_dias_inteiros.keys()):
        distribuicao_dias[d] = round(contagem_dias_inteiros[d] / n_amostras, 4)

    return ResultadoRiscoPermanencia(
        permanencia_media=media_final,
        permanencia_p50=p50_final,
        permanencia_p90=p90_final,
        probabilidade_estouro_free_time=prob_estouro,
        distribuicao_dias=distribuicao_dias,
        canal_mais_provavel=canal_mais_provavel,
        fatores_agravantes_aplicados=fatores_aplicados,
        fonte_parametros=fonte_parametros
    )
