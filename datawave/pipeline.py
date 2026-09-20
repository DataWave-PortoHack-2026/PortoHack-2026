"""Pipeline Orquestrador do DataWave.

Encadeia todo o ciclo de vida do motor determinístico:
Entrada Documental -> Auditoria Cadastral -> Simulação de Risco (Monte Carlo) ->
Matriz de Custos & Break-even -> Parecer Executivo Validado -> Trilha de Auditoria (JSONL).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from datawave.engine.cost import carregar_tarifas, gerar_recomendacao
from datawave.engine.report import ParecerExecutivo, gerar_parecer_executivo
from datawave.engine.risk import simular_permanencia_monte_carlo
from datawave.schemas import OperacaoExtraida, TarifasConfig

HERE = Path(__file__).resolve().parent
LOGS_DIR = HERE / "logs"
LOG_FILE = LOGS_DIR / "pipeline_runs.jsonl"


def executar_pipeline_datawave(
    payload: Dict[str, Any],
    tarifas_override: Optional[TarifasConfig] = None
) -> Dict[str, Any]:
    """Executa o pipeline completo de decisão aduaneira e salva a execução em log."""
    trace_id = f"DW-{uuid.uuid4().hex[:8].upper()}"
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    # 1. Normalização de Entrada Documental
    op = OperacaoExtraida(
        ncm=payload.get("ncm", "38089329"),
        descricao=payload.get("descricao", "Carga Geral"),
        valor_lote_usd=float(payload.get("valor_lote_usd", 50000.0)),
        qtd_conteineres=int(payload.get("qtd_conteineres", 1)),
        incoterm=payload.get("incoterm", "FOB"),
        porto_descarga=payload.get("porto_descarga", "Santos"),
        divergencias=payload.get("divergencias", [])
    )

    # 2. Configuração de Tarifas
    if tarifas_override is not None:
        tarifas = tarifas_override
    else:
        tarifas = TarifasConfig(
            cambio_usd_brl=float(payload.get("cambio_usd_brl", 5.50)),
            free_time_demurrage_dias=int(payload.get("free_time_dias", 7)),
            demurrage_diaria_usd=float(payload.get("demurrage_diaria_usd", 150.0))
        )

    # 3. Simulação Estocástica de Risco e Permanência (Módulo B)
    orgao_anuente = bool(payload.get("orgao_anuente", False))
    operador_oea = bool(payload.get("operador_oea", False))

    risco = simular_permanencia_monte_carlo(
        operacao=op,
        orgao_anuente=orgao_anuente,
        operador_oea=operador_oea,
        free_time_dias=tarifas.free_time_demurrage_dias,
        seed=42,
        n_amostras=5000
    )

    # 4. Matriz Financeira Cais vs. Retroporto e Recomendação (Módulos C e D)
    recomendacao = gerar_recomendacao(
        op=op,
        tarifas=tarifas,
        distribuicao_permanencia=risco.distribuicao_dias
    )

    # 5. Geração e Validação Estrita do Parecer Executivo (Módulo E)
    parecer = gerar_parecer_executivo(
        operacao=op,
        tarifas=tarifas,
        risco=risco,
        recomendacao=recomendacao
    )

    # 6. Trilha de Auditoria (Registro em JSONL)
    registro_log = {
        "trace_id": trace_id,
        "timestamp": timestamp_iso,
        "payload_entrada": payload,
        "operacao": op.model_dump(),
        "risco": {
            "canal_mais_provavel": risco.canal_mais_provavel,
            "permanencia_media": risco.permanencia_media,
            "permanencia_p50": risco.permanencia_p50,
            "permanencia_p90": risco.permanencia_p90,
            "probabilidade_estouro_free_time": risco.probabilidade_estouro_free_time
        },
        "decisao": {
            "opcao_recomendada": recomendacao.opcao_recomendada,
            "dia_break_even": recomendacao.dia_break_even,
            "economia_esperada_brl": recomendacao.economia_esperada_brl,
            "custo_esperado_cais_brl": recomendacao.custo_esperado_cais_brl,
            "custo_esperado_retro_brl": recomendacao.custo_esperado_retro_brl
        },
        "parecer_valido": parecer.valido,
        "inconsistencias": parecer.inconsistencias
    }

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro_log, ensure_ascii=False) + "\n")

    return {
        "trace_id": trace_id,
        "timestamp": timestamp_iso,
        "operacao": op.model_dump(),
        "risco": risco.model_dump(),
        "custo": recomendacao.model_dump(),
        "parecer": parecer.model_dump()
    }
