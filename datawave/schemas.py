"""Modelos de dados e contratos Pydantic para o sistema DataWave.

Padroniza contratos de integração com o Agente Logcomex, parâmetros tarifários,
resultados de simulação de permanência e recomendação logística (Cais vs. Retroporto).
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Contratos de Comunicação com o Agente Logcomex
# ---------------------------------------------------------------------------

class OperacaoExtraida(BaseModel):
    """Dados consolidados extraídos de BL, Invoice e Packing List (U2)."""
    ncm: str = Field(..., description="NCM da mercadoria (com ou sem formatação de pontos)")
    descricao: str = Field(..., description="Descrição resumida do produto")
    valor_lote_usd: float = Field(..., ge=0.0, description="Valor aduaneiro ou total do lote em USD")
    qtd_conteineres: int = Field(1, ge=1, description="Quantidade de contêineres envolvidos")
    tipo_conteiner: str = Field("40HC", description="Tipo do contêiner (ex.: 20DRY, 40DRY, 40HC, REEFER)")
    incoterm: Optional[str] = Field(None, description="Termo de comércio internacional (FOB, CIF, CFR, etc.)")
    porto_descarga: Optional[str] = Field("Santos", description="Porto de descarga da carga")
    armador: Optional[str] = Field(None, description="Companhia de navegação marítima emitente do BL")
    origem: Optional[str] = Field(None, description="País de procedência/origem da mercadoria")
    data_chegada_prevista: Optional[date] = Field(None, description="Data estimada de atracação/chegada (ETA)")
    divergencias: List[str] = Field(default_factory=list, description="Lista de inconsistências apuradas entre os documentos")


class MercadoNCM(BaseModel):
    """Estatísticas de mercado e prazos de permanência em Santos (U1)."""
    ncm: str = Field(..., description="NCM pesquisada")
    periodo: str = Field("Últimos 12 meses", description="Janela temporal de análise")
    volume_mensal: Optional[Dict[str, float]] = Field(None, description="Volume importado por mês (toneladas ou USD)")
    origens_top: Optional[List[str]] = Field(None, description="Principais países de origem por volume")
    importadores_top: Optional[List[str]] = Field(None, description="Principais importadores registrados")
    dias_chegada_desembaraco: Optional[Dict[str, float]] = Field(
        None, description="Tempo médio de liberação em dias por canal de parametrização"
    )


class SugestaoAtributos(BaseModel):
    """Mapeamento de atributos normativos do Catálogo DUIMP sugeridos pelo agente (U3)."""
    sugestoes: Dict[str, str] = Field(default_factory=dict, description="Código do atributo -> código da opção oficial")
    incertos: List[str] = Field(default_factory=list, description="Atributos que necessitam de revisão documental humana")


# ---------------------------------------------------------------------------
# 2. Modelos de Configuração Tarifária (Cais vs. Retroporto)
# ---------------------------------------------------------------------------

class FaixaArmazenagem(BaseModel):
    """Faixa progressiva de armazenagem portuária no cais."""
    dia_inicio: int = Field(..., ge=1, description="Dia inicial do período")
    dia_fim: int = Field(..., ge=1, description="Dia final do período")
    percentual_cif: float = Field(..., ge=0.0, description="Alíquota percentual sobre o valor CIF da carga para o período")
    tarifa_minima_brl: float = Field(0.0, ge=0.0, description="Valor mínimo cobrado em BRL caso a alíquota resulte inferior")


class TarifasConfig(BaseModel):
    """Estrutura paramétrica de custos portuários para o Porto de Santos."""
    cambio_usd_brl: float = Field(5.20, gt=0.0, description="Taxa de câmbio PTAX USD/BRL")
    free_time_demurrage_dias: int = Field(7, ge=0, description="Dias livres de sobre-estadia de contêiner cheio no cais")
    free_time_detention_dias: int = Field(7, ge=0, description="Dias livres de sobre-estadia de contêiner vazio após desova")
    
    # Diárias de sobre-estadia cobradas pelo armador em USD
    demurrage_diaria_usd: float = Field(150.0, ge=0.0, description="Diária de demurrage em USD por contêiner")
    detention_diaria_usd: float = Field(130.0, ge=0.0, description="Diária de detention em USD por contêiner")
    
    # Armazenagem progressiva no cais (zona primária)
    faixas_armazenagem_cais: List[FaixaArmazenagem] = Field(default_factory=list)
    
    # Armazenagem em recinto alfandegado de retroporto / CLIA (zona secundária)
    retro_diaria_brl_por_conteiner: float = Field(85.0, ge=0.0, description="Tarifa diária média de armazenagem no retroporto em BRL")
    retro_seguro_percentual_cif: float = Field(0.0015, ge=0.0, description="Seguro aduaneiro sobre o valor CIF no recinto secundário")
    
    # Custos operacionais fixos de transferência para retroporto
    frete_transferencia_dta_brl: float = Field(1200.0, ge=0.0, description="Frete rodoviário de transferência cais -> retroporto em BRL")
    movimentacao_terminal_brl: float = Field(850.0, ge=0.0, description="Taxa de movimentação portuária de saída (THC/Capatazia) em BRL")
    movimentacao_retro_brl: float = Field(450.0, ge=0.0, description="Taxa de recepção e movimentação interna no retroporto em BRL")


# ---------------------------------------------------------------------------
# 3. Modelos de Resultado e Recomendação Decisória
# ---------------------------------------------------------------------------

class ResultadoCustoDiario(BaseModel):
    """Custo acumulado projetado para um número específico de dias de permanência."""
    dias: int
    custo_cais_brl: float
    custo_retro_brl: float
    armazenagem_cais_brl: float
    demurrage_cais_brl: float
    armazenagem_retro_brl: float
    custos_fixos_transferencia_brl: float
    detention_retro_brl: float
    diferenca_economia_brl: float  # Custo Cais - Custo Retro (positivo indica que retroporto é mais barato)


class RecomendacaoDecisao(BaseModel):
    """Recomendação estratégica final gerada pelo motor determinístico."""
    opcao_recomendada: str = Field(..., description="'RETROPORTO' ou 'CAIS'")
    dia_break_even: Optional[int] = Field(None, description="Dia de corte em que transferir para o retroporto passa a ser mais barato")
    economia_esperada_brl: float = Field(..., description="Economia líquida estimada em BRL considerando a curva probabilística")
    probabilidade_estouro_free_time: float = Field(..., ge=0.0, le=1.0, description="Probabilidade acumulada P(Permanência > Free Time)")
    custo_esperado_cais_brl: float = Field(..., description="Valor esperado E[Custo Cais] ponderado pela probabilidade")
    custo_esperado_retro_brl: float = Field(..., description="Valor esperado E[Custo Retroporto] ponderado pela probabilidade")
    p90_dias_permanencia: int = Field(..., description="Percentil 90 do tempo estimado de permanência")
    justificativa: str = Field(..., description="Explicação técnica com números auditados para o despachante aduaneiro")
    curva_sensibilidade: List[ResultadoCustoDiario] = Field(default_factory=list, description="Projeção dia a dia para gráficos de decisão")


class ResultadoRiscoPermanencia(BaseModel):
    """Métricas probabilísticas geradas pela simulação de Monte Carlo de permanência (Módulo B)."""
    permanencia_media: float = Field(..., ge=0.0, description="Média ponderada dos dias de permanência")
    permanencia_p50: float = Field(..., ge=0.0, description="Mediana (Percentil 50) dos dias de permanência")
    permanencia_p90: float = Field(..., ge=0.0, description="Percentil 90 (pior cenário com 90% de confiança)")
    probabilidade_estouro_free_time: float = Field(..., ge=0.0, le=1.0, description="P(Permanência > Free Time de Demurrage)")
    distribuicao_dias: Dict[int, float] = Field(..., description="Distribuição de probabilidade por dia de permanência")
    canal_mais_provavel: str = Field(..., description="'verde', 'amarelo' ou 'vermelho'")
    fatores_agravantes_aplicados: List[str] = Field(default_factory=list, description="Lista de modificadores de risco ativados")
    fonte_parametros: str = Field(..., description="Origem dos parâmetros (agente | premissa | simulado)")
