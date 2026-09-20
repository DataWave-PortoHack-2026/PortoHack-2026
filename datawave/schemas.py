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
    porto_embarque: Optional[str] = Field(None, description="Porto de embarque da mercadoria (POL)")
    destino_final: Optional[str] = Field(None, description="Destino final da carga (recinto alfandegado ou planta)")
    rota_completa: Optional[str] = Field(None, description="Rota logística formatada: Origem -> Porto Descarga -> Destino Final")
    volume_teus_recorte: Optional[str] = Field(None, description="Estatística de TEUs apurados no histórico da rota")
    data_chegada_prevista: Optional[date] = Field(None, description="Data estimada de atracação/chegada (ETA)")
    divergencias: List[str] = Field(default_factory=list, description="Lista de inconsistências apuradas entre os documentos")


class MercadoNCM(BaseModel):
    """Estatísticas de mercado e prazos de permanência em Santos (U1)."""
    ncm: str = Field(..., description="NCM pesquisada")
    periodo: str = Field("Últimos 12 meses", description="Janela temporal de análise")
    volume_mensal: Optional[Dict[str, float]] = Field(None, description="Volume importado por mês (toneladas ou USD)")
    origens_top: Optional[List[str]] = Field(None, description="Principais países de origem por volume")
    importadores_top: Optional[List[str]] = Field(None, description="Principais importadores registrados")
    total_importadores: Optional[int] = Field(None, description="Quantidade de importadores mapeados pela Logcomex")
    total_exportadores: Optional[int] = Field(None, description="Quantidade de exportadores mapeados pela Logcomex")
    fob_total_mercado_usd: Optional[float] = Field(None, description="Volume total FOB anual importado no Porto de Santos")
    teus_registrados: Optional[str] = Field(None, description="Total de TEUs movimentados no recorte histórico Logcomex")
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


def _faixas_armazenagem_padrao() -> List[FaixaArmazenagem]:
    return [
        FaixaArmazenagem(dia_inicio=1, dia_fim=7, percentual_cif=0.0055, tarifa_minima_brl=950.0),
        FaixaArmazenagem(dia_inicio=8, dia_fim=14, percentual_cif=0.0120, tarifa_minima_brl=1800.0),
        FaixaArmazenagem(dia_inicio=15, dia_fim=21, percentual_cif=0.0210, tarifa_minima_brl=3200.0),
        FaixaArmazenagem(dia_inicio=22, dia_fim=30, percentual_cif=0.0350, tarifa_minima_brl=5000.0),
        FaixaArmazenagem(dia_inicio=31, dia_fim=90, percentual_cif=0.0550, tarifa_minima_brl=8500.0),
    ]


class TarifasConfig(BaseModel):
    """Estrutura paramétrica de custos portuários para o Porto de Santos."""
    cambio_usd_brl: float = Field(5.20, gt=0.0, description="Taxa de câmbio PTAX USD/BRL")
    free_time_demurrage_dias: int = Field(7, ge=0, description="Dias livres de sobre-estadia de contêiner cheio no cais")
    free_time_detention_dias: int = Field(7, ge=0, description="Dias livres de sobre-estadia de contêiner vazio após desova")
    
    # Diárias de sobre-estadia cobradas pelo armador em USD
    demurrage_diaria_usd: float = Field(150.0, ge=0.0, description="Diária de demurrage em USD por contêiner")
    detention_diaria_usd: float = Field(130.0, ge=0.0, description="Diária de detention em USD por contêiner")
    
    # Armazenagem progressiva no cais (zona primária)
    faixas_armazenagem_cais: List[FaixaArmazenagem] = Field(default_factory=_faixas_armazenagem_padrao)
    
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


class EstagioLinhaDoTempo(BaseModel):
    """Marco temporal e operacional estimado para a matriz comparativa de decisão."""
    faixa_dias: str = Field(..., description="Faixa de dias da etapa (ex.: '0 a 5 dias', '5 a 17 dias', '17+ dias')")
    fase: str = Field(..., description="Denominação da fase (ex.: 'Free Time Contratual', 'Retenção MAPA / Despacho', 'Entrega Final')")
    status_cais: str = Field(..., description="Status e impacto de custos no Cais")
    status_retro: str = Field(..., description="Status e impacto de custos no Retroporto")
    detalhes: str = Field(..., description="Detalhamento das operações aduaneiras e logísticas")


class CronogramaLinhaDoTempo(BaseModel):
    """Conjunto de marcos operacionais apurados e estimados pelo Agente Logcomex."""
    ncm: str = Field(..., description="NCM analisada")
    canal_esperado: str = Field("verde", description="Canal estimado de conferência")
    justificativa_prazos: Optional[str] = Field(None, description="Explicação técnica dos prazos apurados pelo agente")
    estagios: List[EstagioLinhaDoTempo] = Field(default_factory=list, description="Lista de estágios operacionais da carga")


# ---------------------------------------------------------------------------
# 4. Modelos de Planilha do Despachante e Auditoria Prescritiva
# ---------------------------------------------------------------------------

class ItemPlanilhaAduaneira(BaseModel):
    """Representação canônica de um item extraído de planilha de despacho aduaneiro."""
    ncm: str = Field(..., description="Classificação fiscal NCM")
    descricao: str = Field(..., description="Descrição da mercadoria")
    quantidade: float = Field(1.0, ge=0.0, description="Quantidade comercializada")
    unidade_medida: str = Field("UN", description="Unidade estatística ou de medida")
    valor_unitario_usd: float = Field(0.0, ge=0.0, description="Valor unitário em USD")
    valor_total_usd: float = Field(0.0, ge=0.0, description="Valor total em USD")
    peso_liquido_kg: Optional[float] = Field(None, ge=0.0, description="Peso líquido em kg")
    peso_bruto_bl_kg: Optional[float] = Field(None, ge=0.0, description="Peso bruto no conhecimento BL")
    peso_bruto_packing_kg: Optional[float] = Field(None, ge=0.0, description="Peso bruto no Packing List")
    incoterm: str = Field("FOB", description="Termo internacional de comércio")
    porto_descarga: str = Field("Santos", description="Porto de atracação/descarga")
    origem: Optional[str] = Field(None, description="País ou procedência da mercadoria")
    porto_embarque: Optional[str] = Field(None, description="Porto de embarque (POL)")
    destino_final: Optional[str] = Field(None, description="Destino final da carga ou planta")
    consignatario: Optional[str] = Field(None, description="Importador consignatário")
    armador: Optional[str] = Field(None, description="Companhia de navegação marítima")
    tipo_conteiner: str = Field("40HC", description="Tipo de equipamento")
    free_time_dias: int = Field(5, ge=0, description="Dias livres de demurrage")
    atributos_declarados: Dict[str, str] = Field(default_factory=dict, description="Atributos DUIMP declarados na planilha")
    observacoes: Optional[str] = Field(None, description="Comentários adicionais")


class CorrecaoAduaneira(BaseModel):
    """Ação prescritiva de correção aduaneira recomendada pelo Agente Logcomex."""
    id: Optional[str] = Field(None, description="Identificador único da recomendação corretiva")
    item_index: Optional[int] = Field(None, description="Número ordinal do item na planilha")
    categoria: str = Field(..., description="Tipo de inconsistência (Peso, DUIMP, Incoterm, etc.)")
    problema_identificado: Optional[str] = Field(None, description="Descrição objetiva da divergência")
    problema_detectado: Optional[str] = Field(None, description="Sinônimo de problema_identificado")
    acao_corretiva_sugerida: Optional[str] = Field(None, description="Instrução normativa de correção")
    acao_prescrita: Optional[str] = Field(None, description="Sinônimo de acao_corretiva_sugerida")
    prazo_limite: Optional[str] = Field(None, description="Momento limite para cumprimento da instrução")
    fundamento_legal: Optional[str] = Field(None, description="Dispositivo legal ou portaria aplicável")
    risco_mitigado: Optional[str] = Field(None, description="Penalidade ou auto de infração prevenido")


class PlanoCorrecoesAduaneiras(BaseModel):
    """Plano prescritivo consolidado de correções emitido pelo Agente Logcomex."""
    total_divergencias: int = Field(0, ge=0, description="Quantidade de inconformidades apontadas")
    total_pendencias: Optional[int] = Field(None, ge=0, description="Sinônimo de total_divergencias")
    bloqueia_duimp: bool = Field(False, description="Indica se há pendência impeditiva de registro da DUIMP")
    correcoes: List[CorrecaoAduaneira] = Field(default_factory=list, description="Lista de orientações de retificação")
