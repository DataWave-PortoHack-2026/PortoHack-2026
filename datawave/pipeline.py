"""Pipeline Orquestrador do DataWave.

Encadeia todo o ciclo de vida do motor determinístico e do Agente Logcomex:
Entrada Documental (U2) -> Inteligência de Mercado (U1) -> Auditoria Cadastral (U3) ->
Simulação de Risco (Monte Carlo) -> Matriz de Custos & Break-even ->
Parecer Executivo Validado (U4) -> Trilha de Auditoria (JSONL).
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from datawave.agent_client import AgentClient, FakeAgent, LogcomexMCPAgent
from datawave.engine.cost import carregar_tarifas, gerar_recomendacao
from datawave.engine.report import ParecerExecutivo, gerar_parecer_executivo
from datawave.engine.risk import simular_permanencia_monte_carlo
from datawave.schemas import MercadoNCM, OperacaoExtraida, SugestaoAtributos, TarifasConfig

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
LOGS_DIR = HERE / "logs"
LOG_FILE = LOGS_DIR / "pipeline_runs.jsonl"


def executar_pipeline_datawave(
    payload: Optional[Dict[str, Any]] = None,
    tarifas_override: Optional[TarifasConfig] = None,
    usar_agente: bool = False,
    usar_mcp: bool = False,
    agent_client: Optional[AgentClient] = None,
    planilha_csv: Optional[str] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """Executa o pipeline completo de decisão aduaneira e salva a auditoria em log."""
    if payload is None:
        payload = {}
    t_start = time.perf_counter()
    trace_id = f"DW-{uuid.uuid4().hex[:8].upper()}"
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    csv_data = planilha_csv or payload.get("planilha_csv")
    divergencias = list(payload.get("divergencias", []))
    ncm = payload.get("ncm", "38089329")
    descricao = payload.get("descricao", "Carga Geral")
    valor_lote_usd = float(payload.get("valor_lote_usd", 128500.0))
    qtd_conteineres = int(payload.get("qtd_conteineres", 1))
    incoterm = payload.get("incoterm", "FOB")
    porto_descarga = payload.get("porto_descarga", "Santos")

    # Ingestão e consolidação prévia se planilha tabular foi fornecida
    if csv_data:
        from datawave.engine.spreadsheet_parser import parsear_csv_planilha, consolidar_operacao_de_planilha
        itens_planilha = parsear_csv_planilha(csv_data)
        op_extraida, divs_planilha = consolidar_operacao_de_planilha(itens_planilha)
        ncm = op_extraida.ncm
        descricao = op_extraida.descricao
        valor_lote_usd = op_extraida.valor_lote_usd
        qtd_conteineres = op_extraida.qtd_conteineres
        incoterm = op_extraida.incoterm or incoterm
        porto_descarga = op_extraida.porto_descarga or porto_descarga
        for d in divs_planilha:
            if d not in divergencias:
                divergencias.append(d)

    agente_dados: Dict[str, Any] = {}
    modo_agente = "DESATIVADO"

    # 1. Integração com o Agente Logcomex (U1, U2 e U3)
    client = agent_client
    if usar_agente or agent_client is not None or usar_mcp:
        if client is None:
            if usar_mcp:
                try:
                    client = LogcomexMCPAgent()
                    modo_agente = "ONLINE_MCP"
                except Exception as exc:
                    logger.warning(f"MCP remoto indisponível ({exc}), ativando contingência com fixtures gravadas.")
                    client = FakeAgent()
                    modo_agente = "CONTINGENCIA_FIXTURES"
            else:
                client = FakeAgent()
                modo_agente = "CONTINGENCIA_FIXTURES"
        else:
            modo_agente = "ONLINE_MCP" if isinstance(client, LogcomexMCPAgent) else "CONTINGENCIA_FIXTURES"

        # U2 - Conferência Documental
        try:
            op_agente = client.ask_json(
                f"Executar conferência técnica de documentos para importação NCM {ncm}: {descricao}",
                OperacaoExtraida
            )
            for div in op_agente.divergencias:
                if div not in divergencias:
                    divergencias.append(div)
            agente_dados["analise_documental_aduaneira"] = op_agente.model_dump()
            agente_dados["conferencia_documental"] = op_agente.model_dump()
        except Exception as exc:
            logger.debug(f"Agente U2 fallback: {exc}")

        # U1 - Inteligência de Mercado (Santos)
        try:
            mercado = client.ask_json(
                f"Consulta de mercado para vinhos NCM {ncm} no Porto de Santos" if "2204" in ncm else f"Consulte os dados de MercadoNCM para NCM {ncm} Santos",
                MercadoNCM
            )
            agente_dados["mercado"] = mercado.model_dump()
        except Exception as exc:
            logger.debug(f"Agente U1 fallback: {exc}")

        # U3 - Sugestão de Atributos DUIMP / MAPA
        try:
            atributos = client.ask_json(
                f"Sugestão de atributos normativos do Catálogo DUIMP para {descricao} NCM {ncm}",
                SugestaoAtributos
            )
            agente_dados["atributos"] = atributos.model_dump()
            if atributos.incertos:
                divergencias.append(
                    f"Alerta regulatório de catálogo: atributos com necessidade de revisão documental ({', '.join(atributos.incertos)})"
                )
        except Exception as exc:
            logger.debug(f"Agente U3 fallback: {exc}")

    # 2. Normalização da Operação
    op = OperacaoExtraida(
        ncm=ncm,
        descricao=descricao,
        valor_lote_usd=valor_lote_usd,
        qtd_conteineres=qtd_conteineres,
        incoterm=incoterm,
        porto_descarga=porto_descarga,
        divergencias=divergencias
    )

    # 3. Configuração de Tarifas
    if tarifas_override is not None:
        tarifas = tarifas_override
    else:
        tarifas = carregar_tarifas()
        tarifas.cambio_usd_brl = float(payload.get("cambio_usd_brl", 5.50))
        tarifas.free_time_demurrage_dias = int(payload.get("free_time_dias", 7))
        tarifas.demurrage_diaria_usd = float(payload.get("demurrage_diaria_usd", 150.0))

    # 4. Simulação Estocástica de Permanência (Monte Carlo - Módulo B)
    risco = simular_permanencia_monte_carlo(
        operacao=op,
        orgao_anuente=bool(payload.get("orgao_anuente", False)),
        operador_oea=bool(payload.get("operador_oea", False)),
        free_time_dias=tarifas.free_time_demurrage_dias,
        seed=42,
        n_amostras=5000
    )

    # 5. Matriz Financeira Cais vs. Retroporto e Recomendação (Módulos C e D)
    recomendacao = gerar_recomendacao(
        op=op,
        tarifas=tarifas,
        distribuicao_permanencia=risco.distribuicao_dias
    )

    # 6. Geração do Plano de Correções e Parecer Executivo (Módulo E)
    from datawave.engine.report import (
        gerar_parecer_executivo,
        gerar_parecer_via_agente_logcomex,
        gerar_plano_correcoes,
    )
    plano_correcoes = gerar_plano_correcoes(divergencias, ncm=ncm, descricao=descricao)

    if (usar_agente or usar_mcp) and client:
        parecer = gerar_parecer_via_agente_logcomex(
            client=client,
            op=op,
            tarifas=tarifas,
            risco=risco,
            rec=recomendacao,
            trace_id=trace_id,
            plano_correcoes=plano_correcoes
        )
    else:
        parecer = gerar_parecer_executivo(
            operacao=op,
            tarifas=tarifas,
            risco=risco,
            recomendacao=recomendacao
        )

    # 7. Trilha de Auditoria Auditável (Registro em JSONL)
    t_end = time.perf_counter()
    duracao_s = round(t_end - t_start, 3)
    duracao_ms = int(duracao_s * 1000)

    registro_log = {
        "trace_id": trace_id,
        "timestamp": timestamp_iso,
        "duracao_ms": duracao_ms,
        "tempo_resposta_s": duracao_s,
        "modo_agente": modo_agente,
        "agente_dados": agente_dados,
        "payload_entrada": payload,
        "operacao": op.model_dump(),
        "plano_correcoes": plano_correcoes.model_dump(),
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

    custo_dict = recomendacao.model_dump()
    custo_dict["economia_estimada_brl"] = recomendacao.economia_esperada_brl
    custo_dict["economia_esperada_brl"] = recomendacao.economia_esperada_brl
    return {
        "trace_id": trace_id,
        "timestamp": timestamp_iso,
        "duracao_ms": duracao_ms,
        "tempo_resposta_s": duracao_s,
        "modo_agente": modo_agente,
        "agente_dados": agente_dados,
        "operacao": op.model_dump(),
        "risco": risco.model_dump(),
        "custo": custo_dict,
        "plano_correcoes": plano_correcoes.model_dump(),
        "parecer": parecer.model_dump()
    }
