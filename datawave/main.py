"""Servidor e API do DataWave (FastAPI com fallback nativo HTTP).

Integra o motor determinístico em Python (simulação de Monte Carlo e matriz de custos Cais vs. Retroporto)
ao frontend executivo (index.html) e ao banco de dados SQLite.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("datawave.main")

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
    return c


def executar_simulacao_customizada(params: Dict[str, Any]) -> Dict[str, Any]:
    """Executa simulação de ponta a ponta a partir de parâmetros livres enviados pelo usuário."""
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

    return {
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


def gerar_resposta_assistente(mensagem: str, cenario_idx: int = 0) -> str:
    """Gera resposta consultiva e técnica do Agente DataWave fundamentada nos dados do cenário e cálculos."""
    cenarios = carregar_cenarios_mock()
    idx = max(0, min(cenario_idx, len(cenarios) - 1))
    c_raw = cenarios[idx]
    c = calcular_cenario_dinamico(c_raw)

    q = mensagem.lower()
    nome = c.get("cenario_nome", f"Cenário {idx+1}")
    ncm = c.get("ncm", "N/D")
    prob = c.get("prob_retencao", "N/D")
    decisao = c.get("decisao_titulo", "")
    economia = c.get("economia", "")
    cais_tot = c.get("cais_total", "")
    retro_tot = c.get("retro_total", "")

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
        (("cust", "preço", "preco", "valor", "econom", "financeir", "demurrage", "armazenag"),
         f"Na análise de custos comparativos para o {nome}, o despacho no Cais está projetado em {cais_tot}, "
         f"enquanto a remoção ao Retroporto totaliza {retro_tot}. {economia}."),
        (("risco", "retenç", "probabilidade", "canal", "fiscal"),
         f"Para o {nome} (NCM {ncm}), nosso modelo estocástico apurou probabilidade de retenção de {prob}. "
         f"Isso decorre do histórico amostral da NCM e dos intervenientes regulatórios associados à operação."),
        (("recomend", "decis", "sugest", "prescrit", "para onde", "melhor opção", "melhor opcao", "retroporto", "cais"),
         f"A recomendação prescritiva para o {nome} é: {decisao}. "
         f"Essa estratégia maximiza a eficiência operacional e protege a carga contra custos imprevistos."),
        (("ncm", "produto", "mercadoria", "classific"),
         f"A operação em análise refere-se à NCM {ncm} na rota {c.get('rota', 'Santos')}, "
         f"com lote valorado em {c.get('fob_lote', 'N/D')}."),
        (("cenário", "cenari", "trocar", "alternar"),
         f"Você está atualmente visualizando o {nome}. É possível alternar entre os cenários demonstrativos "
         f"no seletor localizado na Tela 1."),
    ]

    for palavras_chave, texto in respostas_intencao:
        if any(p in q for p in palavras_chave):
            return texto

    return (
        f"Como consultor DataWave para o {nome} (NCM {ncm}), posso esclarecer qualquer detalhe da operação: "
        f"o risco de conferência aduaneira ({prob}), a composição da matriz financeira ({cais_tot} no cais vs. {retro_tot} no retroporto) "
        f"ou orientações normativas para regularização documental."
    )


def resolver_base_url(origin: Optional[str] = None, host_header: Optional[str] = None) -> str:
    """Resolve a URL base publica para retorno do OAuth no Render ou ambiente local."""
    if origin and (origin.startswith("http://") or origin.startswith("https://")):
        return origin.rstrip("/")
    if host_header:
        proto = "https" if ("onrender.com" in host_header or (not host_header.startswith("127.0.0.1") and not host_header.startswith("localhost"))) else "http"
        return f"{proto}://{host_header.rstrip('/')}"
    from datawave.auth_manager import BASE_URL
    return BASE_URL.rstrip("/")


def _gerar_html_callback(sucesso: bool, titulo: str, mensagem: str) -> str:
    cor_titulo = "#10b981" if sucesso else "#ef4444"
    script_notificacao = """
    <script>
        if (window.opener) {
            try {
                window.opener.postMessage({ type: 'MCP_AUTH_SUCCESS' }, '*');
            } catch(e) {}
            setTimeout(function() {
                window.close();
            }, 1800);
        } else {
            setTimeout(function() {
                window.location.href = '/';
            }, 2500);
        }
    </script>
    """ if sucesso else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{titulo} · DataWave</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0b1329;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #111e38;
            padding: 36px 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            max-width: 520px;
            text-align: center;
            border: 1px solid #1e293b;
        }}
        h2 {{ margin-top: 0; color: {cor_titulo}; font-size: 20px; }}
        p {{ color: #94a3b8; line-height: 1.6; font-size: 14px; }}
        .btn {{
            display: inline-block;
            margin-top: 18px;
            padding: 10px 22px;
            background: #2bd9ae;
            color: #0b1329;
            font-weight: 600;
            text-decoration: none;
            border-radius: 6px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h2>{titulo}</h2>
        <p>{mensagem}</p>
        <p style="font-size:12px; color:#64748b;">{"Retornando automaticamente ao painel..." if sucesso else "Clique abaixo para retornar ao DataWave."}</p>
        <a href="/" class="btn">Retornar ao DataWave</a>
    </div>
    {script_notificacao}
</body>
</html>"""


def processar_oauth_callback(
    code: Optional[str],
    state: Optional[str],
    error: Optional[str] = None,
    base_url: Optional[str] = None
) -> Tuple[int, str]:
    """Processa o retorno do provedor OAuth Logcomex, efetuando a troca do authorization code."""
    from datawave.auth_manager import consumir_estado_oauth, trocar_codigo_por_token, DEFAULT_CALLBACK_URL

    if error:
        msg_erro = f"Autorização recusada pelo provedor: {error}"
        return 400, _gerar_html_callback(False, "Erro na Autenticação", msg_erro)

    if not code or not state:
        return 400, _gerar_html_callback(False, "Parâmetros Inválidos", "Código de autorização ou parâmetro de estado ausentes.")

    estado_armazenado = consumir_estado_oauth(state)
    if not estado_armazenado:
        logger.warning(f"Estado OAuth não encontrado ou expirado: {state}")
        return 400, _gerar_html_callback(False, "Sessão Expirada", "A sessão de autorização expirou ou é inválida. Por favor, tente reconectar novamente.")

    code_verifier = estado_armazenado["code_verifier"]
    redirect_uri = estado_armazenado.get("redirect_uri") or (f"{base_url.rstrip('/')}/oauth/callback" if base_url else DEFAULT_CALLBACK_URL)
    client_id = estado_armazenado.get("client_id")

    resultado = trocar_codigo_por_token(
        code=code,
        code_verifier=code_verifier,
        client_id=client_id,
        redirect_uri=redirect_uri
    )

    if resultado and resultado.get("access_token"):
        logger.info(f"Autenticação OAuth MCP concluída com sucesso para client_id {client_id}")
        return 200, _gerar_html_callback(True, "Autenticação Concluída", "Autenticação com Logcomex AI realizada com sucesso! O token de acesso e a chave de renovação foram gravados.")
    else:
        logger.error(f"Falha ao trocar código por token para client_id {client_id}")
        return 500, _gerar_html_callback(False, "Erro ao Obter Tokens", "Não foi possível trocar o código de autorização pelo token de acesso na Logcomex.")


def iniciar_autenticacao_agente_api(origin: Optional[str] = None, host_header: Optional[str] = None) -> Dict[str, Any]:
    """Prepara a URL de autorização OAuth 2.0 PKCE para conexão com o Agente Logcomex."""
    from datawave.auth_manager import gerar_url_autorizacao, obter_client_id_para_redirect_uri
    base_url = resolver_base_url(origin=origin, host_header=host_header)
    redirect_uri = f"{base_url}/oauth/callback"
    client_id = obter_client_id_para_redirect_uri(redirect_uri)
    auth_url, code_verifier, state = gerar_url_autorizacao(client_id=client_id, redirect_uri=redirect_uri)

    # Inicia listener secundário local apenas se estiver estritamente em loopback local
    if "127.0.0.1" in base_url or "localhost" in base_url:
        import threading
        from datawave.auth_manager import CALLBACK_PORT
        from datawave.autenticar_mcp import OAuthCallbackHandler
        from http.server import HTTPServer

        OAuthCallbackHandler.code_verifier = code_verifier
        OAuthCallbackHandler.expected_state = state
        OAuthCallbackHandler.client_id = client_id

        def _escutar_callback():
            try:
                srv = HTTPServer(("127.0.0.1", CALLBACK_PORT), OAuthCallbackHandler)
                srv.timeout = 180
                srv.handle_request()
                srv.server_close()
            except Exception as exc:
                logger.debug(f"Servidor de callback local finalizado: {exc}")

        t = threading.Thread(target=_escutar_callback, daemon=True)
        t.start()

    return {
        "status": "AGUARDANDO_AUTORIZACAO",
        "auth_url": auth_url,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "mensagem": "URL de autorização gerada com sucesso. Conclua o consentimento na Logcomex."
    }


# ---------------------------------------------------------------------------
# Compatibilidade Dupla: FastAPI (se instalado) + Servidor HTTP Nativo
# ---------------------------------------------------------------------------

try:
    from fastapi import FastAPI, Request
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

    @app.get("/oauth/callback", response_class=HTMLResponse)
    def oauth_callback_endpoint(
        request: Request,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None
    ):
        base_url = str(request.base_url).rstrip("/")
        status_code, html_content = processar_oauth_callback(
            code=code,
            state=state,
            error=error,
            base_url=base_url
        )
        return HTMLResponse(content=html_content, status_code=status_code)

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
        from datawave.pipeline import executar_pipeline_datawave
        usar_ag = payload.get("usar_agente", True)
        usar_mcp = payload.get("usar_mcp", True)
        return executar_pipeline_datawave(payload, usar_agente=usar_ag, usar_mcp=usar_mcp)

    @app.get("/api/agente/status")
    def api_agente_status():
        return obter_status_agente_logcomex()

    @app.get("/api/agente/autenticar")
    @app.post("/api/agente/autenticar")
    def api_agente_autenticar(request: Request):
        orig = request.query_params.get("origin") or request.headers.get("origin")
        host_header = request.headers.get("host")
        return iniciar_autenticacao_agente_api(origin=orig, host_header=host_header)

    @app.post("/api/agente/chat")
    def api_agente_chat(payload: Dict[str, Any]):
        return responder_chat_agente(payload)

    @app.post("/api/agente/configurar-token")
    def _fastapi_configurar_token(payload: Dict[str, Any]):
        return api_configurar_token(payload)

    @app.post("/api/despachante/processar-planilha")
    def api_despachante_processar(payload: Dict[str, Any]):
        return processar_planilha_despachante_api(payload)

except ImportError:
    # Fallback transparente quando FastAPI não estiver no ambiente
    app = None


def api_configurar_token(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Cadastra token de acesso nas credenciais locais."""
    token = payload.get("access_token") or payload.get("token")
    if not token or not str(token).strip():
        return {"status": "ERRO", "mensagem": "Token não fornecido."}
    from datawave.auth_manager import salvar_tokens_renovados
    salvar_tokens_renovados(access_token=str(token).strip(), expires_in=86400 * 365)
    return {"status": "ok", "mensagem": "Token registrado com sucesso."}


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
    from datawave.pipeline import executar_pipeline_datawave
    csv_conteudo = payload.get("conteudo_csv", "")
    usar_ag = payload.get("usar_agente", True)
    usar_mcp = payload.get("usar_mcp", True)
    return executar_pipeline_datawave(
        payload=payload,
        usar_agente=usar_ag,
        usar_mcp=usar_mcp,
        planilha_csv=csv_conteudo if csv_conteudo else None
    )


def responder_chat_agente(payload: Any, cenario_idx: int = 0) -> Dict[str, Any]:
    import time
    t_start = time.perf_counter()
    from datawave.agent_client import LogcomexMCPAgent
    if isinstance(payload, str):
        msg = payload
        idx = cenario_idx
    else:
        msg = payload.get("mensagem", "") if isinstance(payload, dict) else str(payload or "")
        idx = int(payload.get("cenario_idx", cenario_idx)) if isinstance(payload, dict) else cenario_idx
    agent = LogcomexMCPAgent()
    modo = "ONLINE_MCP" if agent.check_health() else "MOTOR_AUTONOMO"
    origem = "Agente DataWave · Logcomex AI (MCP)" if modo == "ONLINE_MCP" else "Agente DataWave · Motor Híbrido Autônomo"

    try:
        resposta_agente = agent.ask_agent(msg, skill="auditoria_aduaneira")
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
    fallback = gerar_resposta_assistente(msg, idx)
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
            elif self.path.startswith("/oauth/callback"):
                import urllib.parse
                parsed_url = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed_url.query)
                code = params.get("code", [None])[0]
                state = params.get("state", [None])[0]
                error = params.get("error", [None])[0]
                host_header = self.headers.get("Host")
                base_url = resolver_base_url(host_header=host_header)
                status_code, html_content = processar_oauth_callback(
                    code=code,
                    state=state,
                    error=error,
                    base_url=base_url
                )
                self.send_response(status_code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))
            elif self.path.startswith("/api/agente/status"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                st = obter_status_agente_logcomex()
                self.wfile.write(json.dumps(st, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/agente/autenticar"):
                import urllib.parse
                parsed_url = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed_url.query)
                orig = params.get("origin", [None])[0]
                host_header = self.headers.get("Host")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                res = iniciar_autenticacao_agente_api(origin=orig, host_header=host_header)
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
                orig = payload.get("origin")
                host_header = self.headers.get("Host")
                res = iniciar_autenticacao_agente_api(origin=orig, host_header=host_header)
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
                from datawave.pipeline import executar_pipeline_datawave
                usar_ag = payload.get("usar_agente", True)
                usar_mcp = payload.get("usar_mcp", False)
                resultado = executar_pipeline_datawave(payload, usar_agente=usar_ag, usar_mcp=usar_mcp)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resultado, ensure_ascii=False).encode("utf-8"))
            elif self.path.startswith("/api/agente/configurar-token"):
                token = payload.get("access_token") or payload.get("token")
                if token:
                    from datawave.auth_manager import salvar_tokens_renovados
                    salvar_tokens_renovados(access_token=str(token).strip(), expires_in=86400 * 365)
                    res = {"status": "ok", "mensagem": "Token registrado com sucesso."}
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
    import os
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    if app is not None:
        try:
            import uvicorn
            uvicorn.run(app, host=host, port=port)
        except ImportError:
            run_fallback_server(host=host, port=port)
    else:
        run_fallback_server(host=host, port=port)

