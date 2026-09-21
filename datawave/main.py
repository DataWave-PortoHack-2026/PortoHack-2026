"""Servidor e API do DataWave (FastAPI com fallback nativo HTTP).

Integra o motor determinístico em Python (simulação de Monte Carlo e matriz de custos Cais vs. Retroporto)
ao frontend executivo (index.html) e ao banco de dados SQLite.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Garante que o pacote datawave seja encontrado independentemente de onde o script for executado
HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from datawave.engine.cost import (
    calcular_armazenagem_cais,
    calcular_curva_e_break_even,
    calcular_custo_cais,
    calcular_custo_retro,
    carregar_tarifas,
    gerar_recomendacao,
)
from datawave.engine.risk import simular_permanencia_monte_carlo
from datawave.schemas import OperacaoExtraida, TarifasConfig

HERE = Path(__file__).parent
SCENARIOS_FILE = HERE / "mock_scenarios.json"
HTML_FILE = HERE / "datawave-6-1.html"
if not HTML_FILE.exists():
    HTML_FILE = HERE / "index.html"

# Estado global em memória da sessão DataWave com o último resultado de pipeline ou simulação
ultimo_resultado_pipeline: Optional[Dict[str, Any]] = None


def obter_ultimo_resultado_pipeline() -> Optional[Dict[str, Any]]:
    """Retorna o último resultado de pipeline ou simulação registrado na sessão."""
    return ultimo_resultado_pipeline


def definir_ultimo_resultado_pipeline(resultado: Dict[str, Any]) -> None:
    """Atualiza o estado global em memória do último resultado de pipeline ou simulação."""
    global ultimo_resultado_pipeline
    ultimo_resultado_pipeline = resultado


def carregar_cenarios_mock() -> List[Dict[str, Any]]:
    """Carrega os cenários definidos em mock_scenarios.json."""
    if not SCENARIOS_FILE.exists():
        raise FileNotFoundError(f"Arquivo de cenários não encontrado: {SCENARIOS_FILE}")
    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _extrair_valor_fob(fob_str: str) -> float:
    """Converte 'US$ 128.500,00' para float (128500.0)."""
    limpo = re.sub(r"[^\d,]", "", fob_str).replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 50000.0


def _extrair_free_time(ft_str: str) -> int:
    """Extrai dias inteiros de '5 dias · US$ 150/dia (MSC)'."""
    m = re.search(r"(\d+)\s*dias", ft_str, re.IGNORECASE)
    return int(m.group(1)) if m else 7


def _extrair_demurrage_diaria(ft_str: str) -> float:
    """Extrai valor da diária de 'US$ 150/dia'."""
    m = re.search(r"US\$\s*(\d+(?:[.,]\d+)?)", ft_str, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "."))
    return 150.0


def calcular_cenario_dinamico(cenario_base: Dict[str, Any], cambio_usd_brl: float = 5.50) -> Dict[str, Any]:
    """Passa o cenário pelos motores determinísticos de Risco (Módulo B) e Custos (Módulos C/D)."""
    c = dict(cenario_base)

    valor_fob = _extrair_valor_fob(c.get("fob_lote", "US$ 50.000,00"))
    free_time = _extrair_free_time(c.get("free_time", "7 dias"))
    dem_usd = _extrair_demurrage_diaria(c.get("free_time", "US$ 150/dia"))

    # Extrai flags de risco a partir dos metadados
    importador = c.get("importador_tipo", "")
    operador_oea = ("OEA" in importador) and ("Não-OEA" not in importador)

    texto_alerta = (c.get("alerta_texto", "") + " " + c.get("alert_tipo", "")).upper()
    orgao_anuente = any(org in texto_alerta for org in ["MAPA", "ANVISA", "INMETRO", "IBAMA", "VIGIAGRO"])

    divergencias = []
    status_cat = c.get("catalogo_status", "")
    if c.get("catalogo_badge_class") == "missing" or "ausente" in status_cat.lower() or "vazio" in status_cat.lower():
        divergencias.append(f"Inconsistência cadastral: {status_cat}")

    # Monta modelos Pydantic
    op = OperacaoExtraida(
        ncm=c.get("ncm", "2204.21.00"),
        descricao=c.get("cenario_nome", "Carga Geral"),
        valor_lote_usd=valor_fob,
        qtd_conteineres=2 if "2x" in c.get("detalhe_rota", "") else 1,
        porto_descarga="Santos",
        divergencias=divergencias
    )

    tarifas = carregar_tarifas()
    tarifas.cambio_usd_brl = cambio_usd_brl
    tarifas.free_time_demurrage_dias = free_time
    tarifas.demurrage_diaria_usd = dem_usd

    # 1. Simulação determinística de Monte Carlo (Módulo B)
    risco = simular_permanencia_monte_carlo(
        operacao=op,
        orgao_anuente=orgao_anuente,
        operador_oea=operador_oea,
        free_time_dias=free_time,
        seed=42,
        n_amostras=5000
    )

    # 2. Matriz de Custos e Recomendação (Módulos C e D)
    rec = gerar_recomendacao(op, tarifas, risco.distribuicao_dias)
    dia_be, _ = calcular_curva_e_break_even(op, tarifas, max_dias=30)

    # 3. Consolidação com o layout do frontend
    dwell_projetado = int(round(risco.permanencia_p90 if rec.opcao_recomendada == "RETROPORTO" else risco.permanencia_media))
    dias_estouro = max(0, dwell_projetado - free_time)
    demurrage_brl = round(dias_estouro * dem_usd * cambio_usd_brl * op.qtd_conteineres, 2)
    demurrage_usd_tot = round(dias_estouro * dem_usd * op.qtd_conteineres, 2)
    armazenagem_brl = round(calcular_armazenagem_cais(dwell_projetado, op, tarifas), 2)
    total_cais_brl = round(demurrage_brl + armazenagem_brl, 2)

    total_retro_brl, arm_retro, fixos_retro, _ = calcular_custo_retro(
        min(dwell_projetado, 5), op, tarifas
    )
    total_retro_brl = round(total_retro_brl, 2)
    economia_brl = round(abs(total_cais_brl - total_retro_brl), 2)

    # Atualiza valores calculados no objeto do cenário
    c["prob_retencao"] = f"{int(round(risco.probabilidade_estouro_free_time * 100))}%"
    c["cais_tempo"] = f"{dwell_projetado} dias (estouro de {dias_estouro})" if dias_estouro > 0 else f"{dwell_projetado} dias (Dentro do Free Time)"
    c["cais_demurrage"] = f"US$ {demurrage_usd_tot:,.2f} (R$ {demurrage_brl:,.2f})" if dias_estouro > 0 else "R$ 0,00"
    c["cais_armazenagem"] = f"R$ {armazenagem_brl:,.2f}"
    c["cais_total"] = f"R$ {total_cais_brl:,.2f}"
    c["retro_total"] = f"R$ {total_retro_brl:,.2f}"

    if rec.opcao_recomendada == "RETROPORTO":
        c["economia"] = f"Economia de R$ {economia_brl:,.2f} no Retroporto (Cenário C)"
        c["decisao_titulo"] = "Direcionar para a Zona Secundária — Cenário C"
        c["impacto_economia"] = f"R$ {economia_brl:,.0f}"
        c["impacto_risco"] = c["prob_retencao"]
        c["impacto_demurrage"] = "0 dias"
    else:
        c["economia"] = f"Cais é R$ {economia_brl:,.2f} mais vantajoso que o Retroporto!"
        c["decisao_titulo"] = "Despacho Direto Sobre Águas no Cais — Cenário A"
        c["impacto_economia"] = f"R$ {economia_brl:,.0f}"
        c["impacto_risco"] = c["prob_retencao"]
        c["impacto_demurrage"] = "0 dias"

    c["p90_dias"] = risco.permanencia_p90
    c["dia_break_even"] = dia_be
    c["fonte_motor"] = "DataWave Deterministic Engine v1.0"

    # 4. Linha do Tempo e Rota Real
    marco2_fim = max(free_time + 1, dwell_projetado)
    destino_final = c.get("destino_final", "Anápolis/GO (DAA)" if ("3808" in op.ncm or "2106" in op.ncm) else "São Paulo/SP")
    origem_cen = c.get("origem", "China (Qingdao)" if "3808" in op.ncm else ("China (Shenzhen)" if "8525" in op.ncm else "Argentina (Buenos Aires)"))
    porto_desc = c.get("porto_descarga", "Santos/SP")
    rota_fmt = c.get("rota", f"{origem_cen} → {porto_desc} → {destino_final}")

    c["rota"] = rota_fmt
    c["origem"] = origem_cen
    c["porto_descarga"] = porto_desc
    c["destino_final"] = destino_final
    c["detalhe_rota"] = c.get("detalhe_rota", "TEUs apurados no histórico Logcomex")
    c["fornecedores"] = c.get("fornecedores", "66 importadores / 153 exportadores (Logcomex)")
    c["fob_lote"] = c.get("fob_lote", f"US$ {valor_fob:,.2f}")
    c["mercado_anual_fob"] = c.get("mercado_anual_fob", "US$ 1,037 bilhão" if "3808" in op.ncm else "US$ 412 milhões")

    if "linha_do_tempo" not in c or not c["linha_do_tempo"]:
        c["linha_do_tempo"] = [
            {
                "faixa_dias": f"0 a {free_time} dias",
                "fase": "Free Time Contratual",
                "status_cais": "Cais: Sem sobreestadia (US$ 0,00)",
                "status_retro": "Retroporto: Remoção sob DTC/DTE iniciada",
                "detalhes": f"Atracação e descarga no Porto de Santos. Registro da DUIMP e recepção de documentos durante a janela de {free_time} dias livres."
            },
            {
                "faixa_dias": f"{free_time} a {marco2_fim} dias",
                "fase": f"Conferência e Despacho Aduaneiro ({risco.canal_mais_provavel.upper()})",
                "status_cais": f"Cais: Demurrage progressivo de US$ {dem_usd:.0f}/dia + armazenagem escalonada",
                "status_retro": "Retroporto: Desova rápida no 2º dia e contêiner devolvido (Demurrage R$ 0,00)",
                "detalhes": f"Parametrização em canal {risco.canal_mais_provavel.upper()} e atuação fiscal. No cais, cobrança em dólar ativo; no retroporto, proteção financeira total."
            },
            {
                "faixa_dias": f"{marco2_fim}+ dias",
                "fase": "Desembaraço, Trânsito e Entrega Final",
                "status_cais": "Cais: Carregamento rodoviário com alto demurrage acumulado",
                "status_retro": f"Retroporto: Carregamento protegido até {destino_final}",
                "detalhes": f"Emissão do Comprovante de Importação (CI), liberação na RFB, carregamento rodoviário e trânsito até {destino_final}."
            }
        ]
    return c


def executar_simulacao_customizada(params: Dict[str, Any]) -> Dict[str, Any]:
    """Executa simulação de ponta a ponta a partir de parâmetros livres enviados pelo usuário."""
    global ultimo_resultado_pipeline
    ncm = params.get("ncm", "8481.80.95")
    valor_lote = float(params.get("valor_lote_usd", 50000.0))
    qtd_cont = int(params.get("qtd_conteineres", 1))
    free_time = int(params.get("free_time_dias", 7))
    dem_usd = float(params.get("demurrage_diaria_usd", 150.0))
    cambio = float(params.get("cambio_usd_brl", 5.20))
    anuente = bool(params.get("orgao_anuente", False))
    oea = bool(params.get("operador_oea", False))
    divergencias = params.get("divergencias", [])

    op = OperacaoExtraida(
        ncm=ncm,
        descricao=params.get("descricao", "Operação Customizada"),
        valor_lote_usd=valor_lote,
        qtd_conteineres=qtd_cont,
        divergencias=divergencias
    )
    tarifas = carregar_tarifas()
    tarifas.cambio_usd_brl = cambio
    tarifas.free_time_demurrage_dias = free_time
    tarifas.demurrage_diaria_usd = dem_usd

    risco = simular_permanencia_monte_carlo(
        operacao=op,
        orgao_anuente=anuente,
        operador_oea=oea,
        free_time_dias=free_time,
        seed=42,
        n_amostras=5000
    )
    rec = gerar_recomendacao(op, tarifas, risco.distribuicao_dias)

    res_sim = {
        "opcao_recomendada": rec.opcao_recomendada,
        "dia_break_even": rec.dia_break_even,
        "economia_esperada_brl": rec.economia_esperada_brl,
        "economia_estimada_brl": rec.economia_esperada_brl,
        "custo_esperado_cais_brl": rec.custo_esperado_cais_brl,
        "custo_esperado_retro_brl": rec.custo_esperado_retro_brl,
        "probabilidade_estouro_free_time": rec.probabilidade_estouro_free_time,
        "p90_dias_permanencia": rec.p90_dias_permanencia,
        "justificativa": rec.justificativa,
        "distribuicao_dias": risco.distribuicao_dias
    }

    # Atualiza o estado global em memória com o contexto operacional da simulação
    destino_sim = params.get("destino_final", "Planta do Importador")
    origem_sim = params.get("origem", "Origem Internacional")
    porto_sim = params.get("porto_descarga", "Santos/SP")
    p90_val = int(round(rec.p90_dias_permanencia))

    ultimo_resultado_pipeline = {
        "origem_execucao": "simulacao",
        "operacao": op.model_dump(mode="json"),
        "rota_comex": {
            "ncm": ncm,
            "origem": origem_sim,
            "porto_descarga": porto_sim,
            "destino_final": destino_sim,
            "rota_formatada": f"{origem_sim} → {porto_sim} → {destino_sim}",
            "valor_lote_fob_usd": valor_lote
        },
        "risco": risco.model_dump(),
        "custo": res_sim,
        "plano_correcoes": {"total_divergencias": len(divergencias), "correcoes": []},
        "linha_do_tempo": [
            {
                "faixa_dias": f"0 a {free_time} dias",
                "fase": "Free Time Contratual",
                "status_cais": "Cais: Sem sobreestadia (US$ 0,00)",
                "status_retro": "Retroporto: Remoção preventiva sob DTC/DTE iniciada",
                "detalhes": f"Atracação no {porto_sim} e descarga de {qtd_cont} contêiner(es)."
            },
            {
                "faixa_dias": f"{free_time} a {p90_val} dias",
                "fase": f"Conferência Aduaneira ({risco.canal_mais_provavel.upper()})",
                "status_cais": f"Cais: Demurrage progressivo de US$ {dem_usd:.0f}/dia + armazenagem",
                "status_retro": "Retroporto: Desova rápida e isenção de sobreestadia",
                "detalhes": f"Fiscalização aduaneira em canal {risco.canal_mais_provavel.upper()}."
            },
            {
                "faixa_dias": f"{p90_val}+ dias",
                "fase": "Desembaraço Concluído e Trânsito Final",
                "status_cais": "Cais: Liberação portuária e expedição rodoviária",
                "status_retro": f"Retroporto: Carregamento protegido até {destino_sim}",
                "detalhes": f"Emissão do CI e transporte rodoviário até {destino_sim}."
            }
        ]
    }

    return res_sim


def montar_bloco_contexto_operacional(ctx: Optional[Dict[str, Any]]) -> str:
    """Monta o bloco padronizado CONTEXTO OPERACIONAL DA SESSÃO DATAWAVE a partir dos dados do pipeline ou cenário."""
    if not ctx:
        return ""

    op = ctx.get("operacao") or {}
    rota_obj = ctx.get("rota_comex") or {}

    rota = (
        rota_obj.get("rota_formatada")
        or op.get("rota_completa")
        or ctx.get("rota")
        or "Santos/SP"
    )
    ncm = op.get("ncm") or rota_obj.get("ncm") or ctx.get("ncm") or "N/D"
    mercadoria = op.get("descricao") or ctx.get("cenario_nome") or ctx.get("descricao") or "Carga Geral"

    fob_raw = op.get("valor_lote_usd") or rota_obj.get("valor_lote_fob_usd") or ctx.get("fob_lote") or "N/D"
    if isinstance(fob_raw, (int, float)):
        fob_str = f"US$ {fob_raw:,.2f}"
    else:
        fob_str = str(fob_raw)

    qtd_cont = op.get("qtd_conteineres") or ctx.get("qtd_conteineres") or 1

    divs = op.get("divergencias") or ctx.get("divergencias") or []
    if not divs and ctx.get("alerta_texto"):
        divs = [f"{ctx.get('alerta_texto')} ({ctx.get('alert_tipo', '')})"]
    if not divs and ctx.get("catalogo_status") and "ausente" in str(ctx.get("catalogo_status")).lower():
        divs = [f"Inconsistência cadastral: {ctx.get('catalogo_status')}"]
    divs_str = "; ".join(divs) if divs else "Nenhuma divergência impeditiva detectada"

    risco_obj = ctx.get("risco") or {}
    canal = risco_obj.get("canal_mais_provavel") or ctx.get("alert_tipo") or "Verde"
    p50 = risco_obj.get("permanencia_p50")
    p90 = risco_obj.get("permanencia_p90") or ctx.get("p90_dias")
    if p50 is not None and p90 is not None:
        perm_str = f"P50 = {float(p50):.1f} dias | P90 = {float(p90):.1f} dias"
    elif p90 is not None:
        perm_str = f"P90 = {float(p90):.1f} dias"
    else:
        perm_str = ctx.get("cais_tempo") or "Conforme parâmetros do porto"

    custo_obj = ctx.get("custo") or {}
    decisao = (
        custo_obj.get("opcao_recomendada")
        or ctx.get("decisao_titulo")
        or ctx.get("opcao_recomendada")
        or "Análise em andamento"
    )

    econ_raw = custo_obj.get("economia_esperada_brl") or ctx.get("impacto_economia") or ctx.get("economia") or "R$ 0,00"
    if isinstance(econ_raw, (int, float)):
        econ_str = f"R$ {econ_raw:,.2f}"
    else:
        econ_str = str(econ_raw)

    cais_raw = custo_obj.get("custo_esperado_cais_brl") or ctx.get("cais_total") or "N/D"
    if isinstance(cais_raw, (int, float)):
        cais_str = f"R$ {cais_raw:,.2f}"
    else:
        cais_str = str(cais_raw)

    retro_raw = custo_obj.get("custo_esperado_retro_brl") or ctx.get("retro_total") or "N/D"
    if isinstance(retro_raw, (int, float)):
        retro_str = f"R$ {retro_raw:,.2f}"
    else:
        retro_str = str(retro_raw)

    parecer_obj = ctx.get("parecer") or {}
    if isinstance(parecer_obj, dict) and parecer_obj.get("texto"):
        parecer_resumo = parecer_obj.get("texto", "")[:250].replace("\n", " ") + "..."
    else:
        parecer_resumo = f"Recomendação prescritiva de {decisao} com economia de {econ_str}."

    linha_obj = ctx.get("linha_do_tempo") or []
    if linha_obj and isinstance(linha_obj, list):
        fases = []
        for est in linha_obj:
            if isinstance(est, dict):
                fases.append(f"{est.get('faixa_dias', '')}: {est.get('fase', '')}")
        linha_str = " | ".join(fases) if fases else "3 estágios operacionais configurados"
    else:
        linha_str = "Cronograma conforme prazos regulatórios"

    return (
        "CONTEXTO OPERACIONAL DA SESSÃO DATAWAVE:\n"
        f"- Rota da Operação: {rota}\n"
        f"- Classificação Fiscal (NCM): {ncm}\n"
        f"- Mercadoria Declarada: {mercadoria}\n"
        f"- Volume: {qtd_cont} contêiner(es)\n"
        f"- Valor FOB Declarado: {fob_str}\n"
        f"- Divergências Cadastrais e Documentais: {divs_str}\n"
        f"- Canal Parametrizado: {canal}\n"
        f"- Tempo de Permanência Projetado: {perm_str}\n"
        f"- Decisão Recomendada: {decisao}\n"
        f"- Economia Financeira Calculada: {econ_str}\n"
        f"- Custo Projetado no Cais: {cais_str}\n"
        f"- Custo Projetado no Retroporto: {retro_str}\n"
        f"- Linha do Tempo: {linha_str}\n"
        f"- Parecer Resumo: {parecer_resumo}"
    )


def gerar_resposta_assistente(
    mensagem: str,
    cenario_idx: int = 0,
    contexto: Optional[Dict[str, Any]] = None
) -> str:
    """Gera resposta consultiva e técnica do Agente DataWave fundamentada no contexto global ou cenário ativo."""
    global ultimo_resultado_pipeline
    ctx = contexto or ultimo_resultado_pipeline
    if ctx:
        op = ctx.get("operacao") or {}
        rota_obj = ctx.get("rota_comex") or {}
        risco_obj = ctx.get("risco") or {}
        custo_obj = ctx.get("custo") or {}

        nome = op.get("descricao") or ctx.get("cenario_nome") or "Operação Auditada"
        ncm = op.get("ncm") or ctx.get("ncm") or "N/D"
        rota = rota_obj.get("rota_formatada") or op.get("rota_completa") or ctx.get("rota") or "Santos/SP"
        fob = op.get("valor_lote_usd") or rota_obj.get("valor_lote_fob_usd") or ctx.get("fob_lote") or "N/D"
        fob_str = f"US$ {fob:,.2f}" if isinstance(fob, (int, float)) else str(fob)

        prob_val = risco_obj.get("probabilidade_estouro_free_time")
        prob = f"{int(round(float(prob_val) * 100))}%" if prob_val is not None else ctx.get("prob_retencao", "N/D")

        decisao = custo_obj.get("opcao_recomendada") or ctx.get("decisao_titulo") or "Análise Concluída"

        econ = custo_obj.get("economia_esperada_brl") or ctx.get("economia") or "R$ 0,00"
        economia = f"R$ {econ:,.2f}" if isinstance(econ, (int, float)) else str(econ)

        cais = custo_obj.get("custo_esperado_cais_brl") or ctx.get("cais_total") or "N/D"
        cais_tot = f"R$ {cais:,.2f}" if isinstance(cais, (int, float)) else str(cais)

        retro = custo_obj.get("custo_esperado_retro_brl") or ctx.get("retro_total") or "N/D"
        retro_tot = f"R$ {retro:,.2f}" if isinstance(retro, (int, float)) else str(retro)

        divs = op.get("divergencias") or ctx.get("divergencias") or []
        divs_str = "; ".join(divs) if divs else "Nenhuma divergência impeditiva detectada"
    else:
        cenarios = carregar_cenarios_mock()
        idx = max(0, min(cenario_idx, len(cenarios) - 1))
        c_raw = cenarios[idx]
        c = calcular_cenario_dinamico(c_raw)
        nome = c.get("cenario_nome", f"Cenário {idx+1}")
        ncm = c.get("ncm", "N/D")
        rota = c.get("rota", "Santos")
        fob_str = str(c.get("fob_lote", "N/D"))
        prob = c.get("prob_retencao", "N/D")
        decisao = c.get("decisao_titulo", "")
        economia = c.get("economia", "")
        cais_tot = c.get("cais_total", "")
        retro_tot = c.get("retro_total", "")
        divs_str = c.get("alerta_texto", "Nenhuma inconformidade impeditiva")

    q = mensagem.lower()

    if any(k in q for k in ("mcp", "conexão", "conexao", "autentic", "online", "status")):
        from datawave.auth_manager import carregar_dados_tokens, token_esta_expirado
        dados = carregar_dados_tokens()
        if not dados.get("access_token") or token_esta_expirado(dados):
            return (
                "O Agente Logcomex MCP requer autenticação OAuth ativa. "
                "Para conectar o agente ao vivo, utilize o botão de conexão ou acesse /api/agente/autenticar."
            )
        return "O Agente Logcomex MCP está com credenciais registradas e pronto para executar consultas em tempo real."

    respostas_intencao = [
        (("quem é você", "quem e voce", "o que você faz", "o que voce faz", "funciona", "papel", "ajuda", "capacidade", "skills"),
         "Atuo como Agente Aduaneiro da DataWave conectado ao ecossistema Logcomex AI. "
         "Executo a auditoria preventiva de DUIMP e catálogos de produtos, predição probabilística de retenção fiscal "
         "em Santos (Monte Carlo P50/P90), matriz comparativa de custos entre Cais e Retroporto e redação formal de parecer técnico com prescrição de DTC/DTE."),
        (("rota", "origem", "trajeto", "itinerário", "itinerario"),
         f"A rota da operação em análise na sessão DataWave é: {rota}. Mercadoria declarada: {nome} (NCM {ncm}), com valor FOB de {fob_str}."),
        (("planilha", "divergência", "divergencia", "inconsistência", "inconsistencia"),
         f"Na auditoria realizada para a mercadoria {nome} (NCM {ncm}), foram identificados os seguintes apontamentos: {divs_str}."),
        (("cust", "preço", "preco", "valor", "financeir", "demurrage", "armazenag"),
         f"Na análise de custos comparativos para {nome}, o despacho no Cais está projetado em {cais_tot}, "
         f"enquanto a remoção ao Retroporto totaliza {retro_tot}. Diferencial econômico: {economia}."),
        (("risco", "retenç", "probabilidade", "canal", "fiscal"),
         f"Para a mercadoria {nome} (NCM {ncm}), nosso modelo estocástico apurou probabilidade de retenção de {prob}. "
         f"Isso decorre do histórico amostral da NCM e dos intervenientes regulatórios associados à operação."),
        (("recomend", "decis", "sugest", "prescrit", "para onde", "melhor opção", "melhor opcao"),
         f"A recomendação prescritiva para {nome} é: {decisao}. "
         f"Essa estratégia maximiza a eficiência operacional e gera uma economia calculada de {economia}."),
        (("econom", "vantagem", "economizar", "ganho"),
         f"A economia estimada na operação para {nome} é de {economia}, favorecendo a opção {decisao}."),
        (("ncm", "produto", "mercadoria", "classific"),
         f"A operação em análise refere-se à NCM {ncm} ({nome}) na rota {rota}, "
         f"com lote valorado em {fob_str}."),
        (("cenário", "cenari", "trocar", "alternar"),
         f"Você está atualmente visualizando a operação {nome}. É possível alternar entre os cenários demonstrativos "
         f"no seletor localizado na Tela 1."),
    ]

    for palavras_chave, texto in respostas_intencao:
        if any(p in q for p in palavras_chave):
            return texto

    return (
        f"Como consultor DataWave para a operação {nome} (NCM {ncm}), posso esclarecer qualquer detalhe da operação: "
        f"a rota ({rota}), o risco de conferência aduaneira ({prob}), a composição financeira ({cais_tot} no cais vs. {retro_tot} no retroporto, "
        f"economia de {economia}) ou divergências cadastrais ({divs_str})."
    )


def iniciar_autenticacao_agente_api() -> Dict[str, Any]:
    """Dispara a abertura do navegador para autenticação OAuth com callback em 16951."""
    import threading
    from datawave.auth_manager import gerar_url_autorizacao, CALLBACK_PORT, DEFAULT_CLIENT_ID
    from datawave.autenticar_mcp import OAuthCallbackHandler
    from http.server import HTTPServer
    import webbrowser

    auth_url, code_verifier, state = gerar_url_autorizacao(DEFAULT_CLIENT_ID)
    OAuthCallbackHandler.code_verifier = code_verifier
    OAuthCallbackHandler.expected_state = state
    OAuthCallbackHandler.client_id = DEFAULT_CLIENT_ID

    def _escutar_callback():
        try:
            srv = HTTPServer(("127.0.0.1", CALLBACK_PORT), OAuthCallbackHandler)
            srv.timeout = 180
            srv.handle_request()
            srv.server_close()
        except Exception as exc:
            logger.debug(f"Servidor de callback finalizado: {exc}")

    t = threading.Thread(target=_escutar_callback, daemon=True)
    t.start()

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    return {
        "status": "AGUARDANDO_AUTORIZACAO",
        "auth_url": auth_url,
        "callback_porta": CALLBACK_PORT,
        "mensagem": "Navegador iniciado para consentimento OAuth com Logcomex AI. O token será renovado automaticamente."
    }


# ---------------------------------------------------------------------------
# Compatibilidade Dupla: FastAPI (se instalado) + Servidor HTTP Nativo
# ---------------------------------------------------------------------------

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(title="Datawave AI Engine API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    @app.get("/datawave-6-1.html", response_class=HTMLResponse)
    @app.get("/datawave6.1", response_class=HTMLResponse)
    @app.get("/datawave-6.1", response_class=HTMLResponse)
    def index():
        if HTML_FILE.exists():
            return HTML_FILE.read_text(encoding="utf-8")
        return "<h1>Datawave Engine API</h1>"

    @app.get("/api/cenarios")
    def api_cenarios():
        cenarios_raw = carregar_cenarios_mock()
        return [calcular_cenario_dinamico(c) for c in cenarios_raw]

    @app.post("/api/simular")
    def api_simular(params: Dict[str, Any]):
        return executar_simulacao_customizada(params)

    @app.post("/api/chat")
    def api_chat(payload: Dict[str, Any]):
        msg = payload.get("mensagem", "")
        idx = int(payload.get("cenario_idx", 0))
        resposta = gerar_resposta_assistente(msg, idx)
        return {"resposta": resposta}

    @app.post("/api/pipeline")
    def api_pipeline(payload: Dict[str, Any]):
        global ultimo_resultado_pipeline
        from datawave.pipeline import executar_pipeline_datawave
        usar_ag = payload.get("usar_agente", True)
        usar_mcp = payload.get("usar_mcp", False)
        resultado = executar_pipeline_datawave(payload, usar_agente=usar_ag, usar_mcp=usar_mcp)
        ultimo_resultado_pipeline = resultado
        return resultado

    @app.get("/api/agente/status")
    def api_agente_status():
        return obter_status_agente_logcomex()

    @app.get("/api/agente/autenticar")
    @app.post("/api/agente/autenticar")
    def api_agente_autenticar():
        return iniciar_autenticacao_agente_api()

    @app.post("/api/agente/chat")
    def api_agente_chat(payload: Dict[str, Any]):
        return responder_chat_agente(payload)

    @app.post("/api/agente/configurar-token")
    def api_configurar_token(payload: Dict[str, Any]):
        token = payload.get("access_token") or payload.get("token")
        if not token:
            return {"status": "ERRO", "mensagem": "Token não fornecido."}
        from datawave.auth_manager import salvar_tokens_renovados
        salvar_tokens_renovados(access_token=str(token).strip(), expires_in=86400 * 365)
        return {"status": "SUCESSO", "mensagem": "Token registrado com sucesso."}

    @app.post("/api/despachante/processar-planilha")
    def api_despachante_processar(payload: Dict[str, Any]):
        return processar_planilha_despachante_api(payload)

except ImportError:
    # Fallback transparente quando FastAPI não estiver no ambiente
    app = None


def obter_status_agente_logcomex() -> Dict[str, Any]:
    from datawave.agent_client import LogcomexMCPAgent
    from datawave.auth_manager import carregar_dados_tokens
    agent = LogcomexMCPAgent()
    is_online = agent.check_health()

    if is_online:
        modo = "ONLINE_MCP"
        status = "ONLINE"
    else:
        modo = "MOTOR_AUTONOMO"
        status = "ONLINE_LOCAL"

    return {
        "status": status,
        "modo": modo,
        "agente_id": agent.agent_id,
        "agente_nome": "Agente DataWave",
        "empresa": "Data Wave",
        "mcp_endpoint": agent.base_url,
        "ferramenta": "chat_with_agent",
        "token_expirado": False,
        "saude_mcp": is_online,
        "skills": [
            "Análise Documental Aduaneira",
            "Comexstat | Importação e Exportação Brasil",
            "Catálogo de Produtos DUIMP",
            "Regras Fiscais dos Produtos",
            "Predição de Canais de Desembaraço",
            "Instrução Normativa e Regulamento Aduaneiro"
        ]
    }


def processar_planilha_despachante_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    global ultimo_resultado_pipeline
    from datawave.pipeline import executar_pipeline_datawave
    csv_conteudo = payload.get("conteudo_csv", "")
    usar_ag = payload.get("usar_agente", True)
    usar_mcp = payload.get("usar_mcp", False)
    resultado = executar_pipeline_datawave(
        dados_input=payload,
        usar_agente=usar_ag,
        usar_mcp=usar_mcp,
        planilha_csv=csv_conteudo if csv_conteudo else None
    )
    ultimo_resultado_pipeline = resultado
    return resultado


def responder_chat_agente(payload: Any, cenario_idx: int = 0, agent_client: Optional[Any] = None) -> Dict[str, Any]:
    global ultimo_resultado_pipeline
    import time
    t_start = time.perf_counter()
    from datawave.agent_client import FakeAgent, LogcomexMCPAgent
    if isinstance(payload, str):
        msg = payload
        idx = cenario_idx
        ctx_param = None
        usar_mcp = False
    else:
        msg = payload.get("mensagem", "") if isinstance(payload, dict) else str(payload or "")
        idx = int(payload.get("cenario_idx", cenario_idx)) if isinstance(payload, dict) else cenario_idx
        ctx_param = payload.get("contexto") if isinstance(payload, dict) else None
        usar_mcp = payload.get("usar_mcp", False) if isinstance(payload, dict) else False

    # Resolução de contexto global da aplicação (contexto explícito > ultimo_resultado_pipeline > cenário ativo)
    contexto_ativo = ctx_param
    if not contexto_ativo:
        if ultimo_resultado_pipeline:
            contexto_ativo = ultimo_resultado_pipeline
        else:
            cenarios = carregar_cenarios_mock()
            idx_seguro = max(0, min(idx, len(cenarios) - 1))
            contexto_ativo = calcular_cenario_dinamico(cenarios[idx_seguro])

    bloco_ctx = montar_bloco_contexto_operacional(contexto_ativo) if contexto_ativo else ""
    prompt_completo = f"{msg}\n\n{bloco_ctx}" if bloco_ctx else msg

    if agent_client:
        agent = agent_client
        modo = "CLIENTE_INJETADO"
        origem = "Agente DataWave · Cliente Injetado"
    elif not usar_mcp:
        agent = FakeAgent()
        modo = "MOTOR_AUTONOMO"
        origem = "Agente DataWave · Motor Híbrido Autônomo"
    else:
        mcp_ag = LogcomexMCPAgent()
        if mcp_ag.check_health():
            agent = mcp_ag
            modo = "ONLINE_MCP"
            origem = "Agente DataWave · Logcomex AI (MCP)"
        else:
            agent = mcp_ag._fallback
            modo = "MOTOR_AUTONOMO"
            origem = "Agente DataWave · Motor Híbrido Autônomo"

    try:
        if modo == "ONLINE_MCP":
            resposta_agente = agent.ask_agent(prompt_completo, skill="auditoria_aduaneira")
        else:
            resposta_agente = agent.ask_agent(prompt_completo)

        if resposta_agente and not resposta_agente.startswith("[Contingência"):
            duracao_s = round(time.perf_counter() - t_start, 3)
            return {
                "resposta": resposta_agente,
                "origem": origem,
                "modo": modo,
                "tempo_resposta_s": duracao_s,
                "duracao_ms": int(duracao_s * 1000)
            }
    except Exception as exc:
        logger.warning(f"Exceção no chat com Agente Logcomex: {exc}")
    fallback = gerar_resposta_assistente(msg, idx, contexto=contexto_ativo)
    duracao_s = round(time.perf_counter() - t_start, 3)
    return {
        "resposta": fallback,
        "origem": "Agente DataWave · Motor Híbrido Autônomo",
        "modo": "MOTOR_AUTONOMO",
        "tempo_resposta_s": duracao_s,
        "duracao_ms": int(duracao_s * 1000)
    }


def run_fallback_server(host: str = "127.0.0.1", port: int = 8000):
    """Servidor HTTP nativo em Python puro sem dependências externas."""
    import http.server
    import socketserver

    class DatawaveHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()

        def do_GET(self):
            html_routes = ["/", "/index.html", "/datawave-6-1.html", "/datawave6.1", "/datawave-6.1"]
            req_clean = self.path.split("?")[0]
            if req_clean in html_routes:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                if HTML_FILE.exists():
                    self.wfile.write(HTML_FILE.read_bytes())
                else:
                    self.wfile.write(b"<h1>DataWave Engine</h1>")
            elif self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/api/cenarios") or self.path.startswith("/api/operacoes"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                cenarios_raw = carregar_cenarios_mock()
                calculados = [calcular_cenario_dinamico(c) for c in cenarios_raw]
                self.wfile.write(json.dumps(calculados, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/agente/status"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                st = obter_status_agente_logcomex()
                self.wfile.write(json.dumps(st, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/agente/autenticar"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                res = iniciar_autenticacao_agente_api()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            else:
                super().do_GET()

        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}

            if self.path.startswith("/api/simular"):
                resultado = executar_simulacao_customizada(payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resultado, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/chat"):
                msg = payload.get("mensagem", "")
                idx = int(payload.get("cenario_idx", 0))
                resp = gerar_resposta_assistente(msg, idx)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"resposta": resp}, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/agente/chat"):
                resp = responder_chat_agente(payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/agente/autenticar"):
                res = iniciar_autenticacao_agente_api()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/despachante/processar-planilha"):
                resultado = processar_planilha_despachante_api(payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resultado, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/pipeline"):
                global ultimo_resultado_pipeline
                from datawave.pipeline import executar_pipeline_datawave
                usar_ag = payload.get("usar_agente", True)
                usar_mcp = payload.get("usar_mcp", False)
                resultado = executar_pipeline_datawave(payload, usar_agente=usar_ag, usar_mcp=usar_mcp)
                ultimo_resultado_pipeline = resultado
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resultado, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/agente/configurar-token"):
                token = payload.get("access_token") or payload.get("token")
                if token:
                    from datawave.auth_manager import salvar_tokens_renovados
                    salvar_tokens_renovados(access_token=str(token).strip(), expires_in=86400 * 365)
                    res = {"status": "SUCESSO", "mensagem": "Token registrado com sucesso."}
                else:
                    res = {"status": "ERRO", "mensagem": "Token não fornecido."}
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    print(f"Iniciando Servidor Nativo DataWave em http://{host}:{port}/")
    with ReusableTCPServer((host, port), DatawaveHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    if app is not None:
        try:
            import uvicorn
            import os
            port = int(os.environ.get("PORT", 8000))

            uvicorn.run(
                app,
                host="0.0.0.0",
                port=port
            )
        except ImportError:
            run_fallback_server()
    else:
        run_fallback_server()
