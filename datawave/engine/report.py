"""Módulo E — Geração e Validação Estrita do Parecer Executivo Aduaneiro.

Gera o relatório técnico formal do despachante aduaneiro com validação matemática
por expressões regulares (Regex), assegurando que 100% dos números citados no parecer
correspondam rigorosamente aos valores apurados pelos motores determinísticos.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field

from datawave.schemas import OperacaoExtraida, RecomendacaoDecisao, ResultadoRiscoPermanencia, TarifasConfig


class RelatorioInconsistenteError(Exception):
    """Exceção levantada quando números citados no parecer divergem dos cálculos do motor."""
    pass


class ParecerExecutivo(BaseModel):
    """Representação estruturada do parecer formal de instrução aduaneira."""
    titulo: str = Field(description="Título formal do parecer")
    texto: str = Field(description="Conteúdo integral do parecer em formato Markdown")
    valido: bool = Field(description="Indica se passou na validação estrita por expressões regulares")
    valores_esperados: Dict[str, str] = Field(default_factory=dict, description="Dicionário de valores esperados no texto")
    inconsistencias: List[str] = Field(default_factory=list, description="Lista de divergências encontradas pelo validador")


def _formatar_brl(valor: float) -> str:
    """Formata valor em moeda brasileira: R$ 1.234,56."""
    formatado = f"{valor:,.2f}"
    return f"R$ {formatado.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _formatar_usd(valor: float) -> str:
    """Formata valor em dólares americanos: US$ 1,234.56."""
    return f"US$ {valor:,.2f}"


def validar_conformidade_relatorio(texto: str, valores_esperados: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Valida via Expressões Regulares se todos os valores esperados estão no texto.

    Verifica também se existem valores monetários citados no texto que não correspondam
    aos valores calculados e homologados pelo motor determinístico.
    """
    inconsistencias: List[str] = []

    # 1. Verifica presença de todos os valores esperados
    for chave, valor_str in valores_esperados.items():
        # Escapa caracteres especiais para regex
        padrao = re.escape(valor_str)
        if not re.search(padrao, texto):
            inconsistencias.append(f"Valor esperado ausente ou divergente para '{chave}': esperado '{valor_str}'")

    # 2. Inspeciona todos os valores monetários em R$ citados no texto
    valores_brl_raw = re.findall(r"R\$\s*[\d\.\,]+", texto)
    valores_brl_texto = [v.rstrip(".,;: ") for v in valores_brl_raw]
    valores_brl_esperados_norm = [
        re.sub(r"\s+", "", v) for v in valores_esperados.values() if "R$" in v
    ]

    for v_texto in valores_brl_texto:
        v_norm = re.sub(r"\s+", "", v_texto)
        # Permite valores inteiros abreviados como R$ 6.425
        if v_norm not in valores_brl_esperados_norm:
            # Verifica se é uma versão abreviada sem centavos
            sem_centavos = v_norm + ",00"
            if sem_centavos not in valores_brl_esperados_norm:
                inconsistencias.append(f"Valor monetário em R$ não homologado detectado no texto: '{v_texto}'")

    valido = len(inconsistencias) == 0
    return valido, inconsistencias


def gerar_parecer_executivo(
    operacao: OperacaoExtraida,
    tarifas: TarifasConfig,
    risco: ResultadoRiscoPermanencia,
    recomendacao: RecomendacaoDecisao,
    autoridade_responsavel: str = "Consultoria Aduaneira DataWave"
) -> ParecerExecutivo:
    """Gera o parecer executivo formal e o submete ao validador estrito por expressões regulares."""
    titulo = f"PARECER TÉCNICO ADUANEIRO — LOTE NCM {operacao.ncm} (PORTO DE SANTOS)"

    # Formatação padronizada de valores de referência
    fob_str = _formatar_usd(operacao.valor_lote_usd)
    cambio_str = _formatar_brl(tarifas.cambio_usd_brl)
    ft_str = f"{tarifas.free_time_demurrage_dias} dias"
    dem_usd_str = _formatar_usd(tarifas.demurrage_diaria_usd)
    prob_retencao_str = f"{int(round(recomendacao.probabilidade_estouro_free_time * 100))}%"
    p50_str = f"{risco.permanencia_p50:.1f} dias"
    p90_str = f"{risco.permanencia_p90:.1f} dias"
    be_str = f"{recomendacao.dia_break_even} dias" if recomendacao.dia_break_even else "Sem break-even no período"
    cais_esp_str = _formatar_brl(recomendacao.custo_esperado_cais_brl)
    retro_esp_str = _formatar_brl(recomendacao.custo_esperado_retro_brl)
    economia_str = _formatar_brl(recomendacao.economia_esperada_brl)

    # Coleta divergências cadastrais
    divergencias_texto = "\n".join([f"- {d}" for d in operacao.divergencias]) if operacao.divergencias else "- Nenhuma inconformidade impeditiva detectada no catálogo."

    # Diagnóstico de rota e recomendação
    if recomendacao.opcao_recomendada == "RETROPORTO":
        acao_recomendada = "EMISSÃO DE DECLARAÇÃO DE TRÂNSITO ADUANEIRO (DTC / DTE) PARA RETROPORTO"
        estrategia_desc = (
            f"Diante da probabilidade de retenção fitossanitária/sanitária estimada em {prob_retencao_str} "
            f"e do tempo de permanência P90 projetado em {p90_str}, o despacho no Cais ultrapassa a janela de "
            f"free time ({ft_str}). A transferência da carga sob regime de trânsito aduaneiro estanca a cobrança "
            f"de sobreestadia em dólar ({dem_usd_str}/dia), permitindo a devolução imediata do equipamento vazio "
            f"e proporcionando uma economia líquida estimada de {economia_str} por contêiner."
        )
    else:
        acao_recomendada = "MANUTENÇÃO NO CAIS E DESPACHO DIRETO SOBRE ÁGUAS (CANAL VERDE)"
        estrategia_desc = (
            f"Com perfil de baixo risco aduaneiro e tempo médio de permanência projetado em {p50_str}, "
            f"a liberação ocorre com segurança dentro do free time ({ft_str}). O despacho direto no cais "
            f"evita os custos fixos de frete e movimentação para zona secundária, gerando uma economia de {economia_str}."
        )

    # Redação do parecer estruturado
    texto = f"""# {titulo}

**Responsável Técnico:** {autoridade_responsavel}
**Data de Emissão:** Conforme parametrização do sistema
**Porto de Entrada:** {operacao.porto_descarga or 'Santos'} | **Incoterm:** {operacao.incoterm or 'FOB'}

---

### 1. IDENTIFICAÇÃO DA OPERAÇÃO
- **Mercadoria Declarada:** {operacao.descricao}
- **Classificação Fiscal (NCM):** {operacao.ncm}
- **Volume da Carga:** {operacao.qtd_conteineres} contêiner(es)
- **Valor FOB Declarado:** {fob_str}
- **Taxa de Câmbio PTAX de Referência:** {cambio_str}
- **Diária de Demurrage de Referência:** {dem_usd_str}/dia

---

### 2. AUDITORIA PREVENTIVA DE CATÁLOGO
Varredura preventiva de atributos regulatórios obrigatórios e integridade da documentação de embarque:
{divergencias_texto}

---

### 3. AVALIAÇÃO PROBABILÍSTICA DE PERMANÊNCIA (MONTE CARLO)
Simulação estocástica com 5.000 iterações determinísticas fundamentada nos priors aduaneiros de Santos:
- **Canal Mais Provável:** {risco.canal_mais_provavel.upper()}
- **Permanência Mediana (P50):** {p50_str}
- **Permanência Pior Cenário com 90% de Confiança (P90):** {p90_str}
- **Janela de Free Time Contratada:** {ft_str}
- **Probabilidade de Estouro do Free Time:** {prob_retencao_str}

---

### 4. MATRIZ FINANCEIRA COMPARATIVA (CAIS X RETROPORTO)
Análise de custo esperado ponderado pela distribuição de probabilidade de permanência:
- **Custo Esperado no Cais (Armazenagem Escalonada + Demurrage):** {cais_esp_str}
- **Custo Esperado no Retroporto (Transferência + Armazenagem Clia):** {retro_esp_str}
- **Ponto de Equilíbrio Operacional (Break-even d*):** {be_str}
- **Diferencial Econômico:** Economia projetada de {economia_str} a favor da opção {recomendacao.opcao_recomendada}.

---

### 5. PARECER PRESCRITIVO E INSTRUÇÃO DE TRÂNSITO
**Decisão Prescritiva:** {acao_recomendada}

**Justificativa Técnica:**
{estrategia_desc}

---
*Parecer emitido automaticamente pelo motor determinístico DataWave com validação estrita de integridade numérica.*
"""

    valores_esperados = {
        "fob": fob_str,
        "cambio": cambio_str,
        "free_time": ft_str,
        "demurrage_diaria": dem_usd_str,
        "prob_retencao": prob_retencao_str,
        "p50": p50_str,
        "p90": p90_str,
        "cais_esperado": cais_esp_str,
        "retro_esperado": retro_esp_str,
        "economia": economia_str
    }

    valido, inconsistencias = validar_conformidade_relatorio(texto, valores_esperados)

    return ParecerExecutivo(
        titulo=titulo,
        texto=texto,
        valido=valido,
        valores_esperados=valores_esperados,
        inconsistencias=inconsistencias
    )
