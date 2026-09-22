"""Gerenciador de autenticação OAuth 2.0 e renovação de tokens para o MCP Logcomex.

Suporta:
- Leitura estruturada dos tokens em C:\\Users\\Arthur\\.gemini\\antigravity\\mcp_oauth_tokens.json
  e C:\\Users\\Arthur\\.mcp-auth\\mcp-remote-v1\\e82823be8b87682c8077bc598edc9e4c_tokens.json
- Verificação precisa de expiração de token
- Renovação automática (refresh_token grant) transparente
- Fluxo de autorização PKCE local em porta 16951 para reautenticação com 1 clique
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import threading
import time
from typing import Any, Dict, Optional, Tuple
import urllib.parse
import urllib.request
import webbrowser

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_HOME = Path.home()
ARQUIVO_PROJETO_TOKENS = Path(os.getenv("DATAWAVE_MCP_PROJECT_TOKENS", str(_HERE / "data" / "mcp_tokens.json")))
ARQUIVO_GEMINI_TOKENS = Path(os.getenv("DATAWAVE_GEMINI_TOKENS_PATH", str(_HOME / ".gemini" / "antigravity" / "mcp_oauth_tokens.json")))
ARQUIVO_MCP_REMOTE_TOKENS = Path(os.getenv("DATAWAVE_MCP_TOKENS_PATH", str(_HOME / ".mcp-auth" / "mcp-remote-v1" / "e82823be8b87682c8077bc598edc9e4c_tokens.json")))
ARQUIVO_CLIENT_INFO = Path(os.getenv("DATAWAVE_MCP_CLIENT_INFO_PATH", str(_HOME / ".mcp-auth" / "mcp-remote-v1" / "e82823be8b87682c8077bc598edc9e4c_client_info.json")))

MCP_TOKEN_ENDPOINT = "https://mcp.logcomex.ai/token"
MCP_AUTHORIZE_ENDPOINT = "https://mcp.logcomex.ai/authorize"
CALLBACK_PORT = 16951

# Resolucao de URL base para producao (Render) e desenvolvimento local
RENDER_URL_PADRAO = "https://portohack-2026-datawave.onrender.com"
BASE_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("DATAWAVE_BASE_URL") or RENDER_URL_PADRAO
DEFAULT_CALLBACK_URL = f"{BASE_URL.rstrip('/')}/oauth/callback"
LOCAL_CALLBACK_URL = f"http://127.0.0.1:{CALLBACK_PORT}/oauth/callback"
CALLBACK_URL = DEFAULT_CALLBACK_URL

DEFAULT_CLIENT_ID = "mcp_s7dB7UnpSPSDtIVZjIXB_g"

CLIENTES_CONHECIDOS: Dict[str, str] = {
    f"{RENDER_URL_PADRAO}/oauth/callback": "mcp_s7dB7UnpSPSDtIVZjIXB_g",
    "http://127.0.0.1:16951/oauth/callback": "mcp_p2JAp_zesXbtLk8FpLXfzA",
    "http://127.0.0.1:8000/oauth/callback": "mcp_s7dB7UnpSPSDtIVZjIXB_g",
    "http://localhost:8000/oauth/callback": "mcp_s7dB7UnpSPSDtIVZjIXB_g",
}

# Controle de estados PKCE pendentes em memoria para verificacao estrita no callback
_ESTADOS_OAUTH: Dict[str, Dict[str, Any]] = {}
_ESTADOS_LOCK = threading.Lock()


def salvar_estado_oauth(state: str, code_verifier: str, redirect_uri: str, client_id: str) -> None:
    """Registra estado PKCE pendente para validacao segura no callback."""
    with _ESTADOS_LOCK:
        agora = time.time()
        # Expira estados apos 10 minutos
        expirados = [s for s, dados in _ESTADOS_OAUTH.items() if agora - dados.get("criado_em", 0) > 600]
        for s in expirados:
            _ESTADOS_OAUTH.pop(s, None)
        _ESTADOS_OAUTH[state] = {
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "criado_em": agora
        }


def consumir_estado_oauth(state: str) -> Optional[Dict[str, Any]]:
    """Recupera e consome o estado PKCE pendente para troca de token (one-time use)."""
    with _ESTADOS_LOCK:
        return _ESTADOS_OAUTH.pop(state, None)


def obter_client_id_para_redirect_uri(redirect_uri: str) -> str:
    """Retorna o client_id apropriado para o redirect_uri ou registra dinamicamente via RFC 7591."""
    if redirect_uri in CLIENTES_CONHECIDOS:
        return CLIENTES_CONHECIDOS[redirect_uri]

    # Tentativa de registro dinamico via RFC 7591
    try:
        corpo = json.dumps({
            "redirect_uris": [redirect_uri],
            "client_name": "DataWave PortoHack 2026",
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"]
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://mcp.logcomex.ai/register",
            data=corpo,
            headers={"Content-Type": "application/json", "User-Agent": "DataWave-Client/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201):
                resposta = json.loads(resp.read().decode("utf-8"))
                cid = resposta.get("client_id")
                if cid:
                    CLIENTES_CONHECIDOS[redirect_uri] = cid
                    logger.info(f"Client ID registrado dinamicamente para {redirect_uri}: {cid}")
                    return cid
    except Exception as exc:
        logger.warning(f"Nao foi possivel registrar client_id dinamicamente para {redirect_uri}: {exc}")

    return DEFAULT_CLIENT_ID



def carregar_dados_tokens() -> Dict[str, Any]:
    """Carrega dados consolidados de token a partir de todas as fontes conhecidas (portátil para qualquer máquina)."""
    resultado: Dict[str, Any] = {
        "access_token": None,
        "refresh_token": None,
        "expiry": None,
        "client_id": DEFAULT_CLIENT_ID,
        "origem": None
    }

    # 0. Variáveis de ambiente diretas (Docker, CI/CD ou outras máquinas)
    env_token = os.getenv("LOGCOMEX_ACCESS_TOKEN") or os.getenv("LOGCOMEX_MCP_TOKEN")
    if env_token:
        resultado["access_token"] = env_token
        resultado["origem"] = "ENV"
        resultado["refresh_token"] = os.getenv("LOGCOMEX_REFRESH_TOKEN")
        resultado["client_id"] = os.getenv("LOGCOMEX_CLIENT_ID", DEFAULT_CLIENT_ID)
        return resultado

    # 1. Arquivo portátil no diretório do projeto (data/mcp_tokens.json)
    if ARQUIVO_PROJETO_TOKENS.exists():
        try:
            dados = json.loads(ARQUIVO_PROJETO_TOKENS.read_text(encoding="utf-8"))
            if isinstance(dados, dict):
                entry = dados.get("https://mcp.logcomex.ai") or dados.get("logcomex") or dados
                if isinstance(entry, dict):
                    tok_obj = entry.get("token") if isinstance(entry.get("token"), dict) else entry
                    acc = tok_obj.get("access_token")
                    ref = tok_obj.get("refresh_token")
                    exp = tok_obj.get("expiry")
                    cid = entry.get("client_id")
                    if acc:
                        resultado["access_token"] = acc
                        resultado["origem"] = str(ARQUIVO_PROJETO_TOKENS)
                    if ref:
                        resultado["refresh_token"] = ref
                    if exp:
                        resultado["expiry"] = exp
                    if cid:
                        resultado["client_id"] = cid
        except Exception as exc:
            logger.debug(f"Falha ao ler {ARQUIVO_PROJETO_TOKENS}: {exc}")

    # 2. Tentar arquivo Gemini / Antigravity
    if not resultado["access_token"] and ARQUIVO_GEMINI_TOKENS.exists():
        try:
            dados = json.loads(ARQUIVO_GEMINI_TOKENS.read_text(encoding="utf-8"))
            if isinstance(dados, dict):
                entry = dados.get("https://mcp.logcomex.ai") or dados.get("logcomex") or dados
                if isinstance(entry, dict):
                    tok_obj = entry.get("token") if isinstance(entry.get("token"), dict) else entry
                    acc = tok_obj.get("access_token")
                    ref = tok_obj.get("refresh_token")
                    exp = tok_obj.get("expiry")
                    cid = entry.get("client_id")
                    if acc:
                        resultado["access_token"] = acc
                        resultado["origem"] = str(ARQUIVO_GEMINI_TOKENS)
                    if ref and not resultado["refresh_token"]:
                        resultado["refresh_token"] = ref
                    if exp and not resultado["expiry"]:
                        resultado["expiry"] = exp
                    if cid:
                        resultado["client_id"] = cid
        except Exception as exc:
            logger.debug(f"Falha ao ler {ARQUIVO_GEMINI_TOKENS}: {exc}")

    # 3. Tentar arquivo mcp-remote
    if not resultado["access_token"] and ARQUIVO_MCP_REMOTE_TOKENS.exists():
        try:
            dados = json.loads(ARQUIVO_MCP_REMOTE_TOKENS.read_text(encoding="utf-8"))
            if isinstance(dados, dict):
                acc = dados.get("access_token")
                ref = dados.get("refresh_token")
                exp_in = dados.get("expires_in")
                if acc and not resultado["access_token"]:
                    resultado["access_token"] = acc
                    resultado["origem"] = str(ARQUIVO_MCP_REMOTE_TOKENS)
                if ref and not resultado["refresh_token"]:
                    resultado["refresh_token"] = ref
                if exp_in and not resultado["expiry"]:
                    mtime = ARQUIVO_MCP_REMOTE_TOKENS.stat().st_mtime
                    exp_dt = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc) + datetime.timedelta(seconds=int(exp_in))
                    resultado["expiry"] = exp_dt.isoformat()
        except Exception as exc:
            logger.debug(f"Falha ao ler {ARQUIVO_MCP_REMOTE_TOKENS}: {exc}")

    # 4. Tentar client_info do mcp-remote
    if ARQUIVO_CLIENT_INFO.exists():
        try:
            dados = json.loads(ARQUIVO_CLIENT_INFO.read_text(encoding="utf-8"))
            if isinstance(dados, dict) and dados.get("client_id"):
                resultado["client_id"] = dados["client_id"]
        except Exception:
            pass

    return resultado


def token_esta_expirado(dados: Dict[str, Any], margem_segundos: int = 60) -> bool:
    """Verifica se o token já expirou ou está prestes a expirar."""
    if not dados.get("access_token"):
        return True
    expiry_str = dados.get("expiry")
    if not expiry_str:
        return False
    try:
        dt_exp = datetime.datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        agora = datetime.datetime.now(datetime.timezone.utc)
        return (dt_exp - agora).total_seconds() < margem_segundos
    except Exception:
        return False


def salvar_tokens_renovados(
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_in: int = 3600,
    client_id: Optional[str] = None
) -> None:
    """Salva os novos tokens em todos os locais reconhecidos pelo ambiente (portátil no projeto)."""
    agora = datetime.datetime.now(datetime.timezone.utc)
    expiry_iso = (agora + datetime.timedelta(seconds=expires_in)).isoformat()
    cid = client_id or DEFAULT_CLIENT_ID

    # 1. Salvar no arquivo portátil do projeto (data/mcp_tokens.json)
    try:
        ARQUIVO_PROJETO_TOKENS.parent.mkdir(parents=True, exist_ok=True)
        dados_proj = {
            "https://mcp.logcomex.ai": {
                "client_id": cid,
                "token": {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "refresh_token": refresh_token,
                    "expiry": expiry_iso
                },
                "token_url": MCP_TOKEN_ENDPOINT
            }
        }
        ARQUIVO_PROJETO_TOKENS.write_text(json.dumps(dados_proj, indent=2), encoding="utf-8")
        logger.info(f"Tokens atualizados no arquivo do projeto: {ARQUIVO_PROJETO_TOKENS}")
    except Exception as exc:
        logger.debug(f"Erro ao salvar em {ARQUIVO_PROJETO_TOKENS}: {exc}")

    # 2. Salvar no mcp_oauth_tokens.json do Antigravity
    try:
        ARQUIVO_GEMINI_TOKENS.parent.mkdir(parents=True, exist_ok=True)
        dados_gemini = {}
        if ARQUIVO_GEMINI_TOKENS.exists():
            try:
                dados_gemini = json.loads(ARQUIVO_GEMINI_TOKENS.read_text(encoding="utf-8"))
            except Exception:
                dados_gemini = {}

        dados_gemini["https://mcp.logcomex.ai"] = {
            "client_id": cid,
            "token": {
                "access_token": access_token,
                "token_type": "Bearer",
                "refresh_token": refresh_token,
                "expiry": expiry_iso
            },
            "token_url": MCP_TOKEN_ENDPOINT
        }
        ARQUIVO_GEMINI_TOKENS.write_text(json.dumps(dados_gemini, indent=2), encoding="utf-8")
        logger.info(f"Tokens atualizados em {ARQUIVO_GEMINI_TOKENS}")
    except Exception as exc:
        logger.warning(f"Erro ao salvar em {ARQUIVO_GEMINI_TOKENS}: {exc}")

    # 3. Salvar no e82823be8b87682c8077bc598edc9e4c_tokens.json do mcp-remote
    try:
        ARQUIVO_MCP_REMOTE_TOKENS.parent.mkdir(parents=True, exist_ok=True)
        dados_remote = {
            "access_token": access_token,
            "token_type": "Bearer",
            "refresh_token": refresh_token,
            "expires_in": expires_in
        }
        ARQUIVO_MCP_REMOTE_TOKENS.write_text(json.dumps(dados_remote, indent=2), encoding="utf-8")
        logger.info(f"Tokens atualizados em {ARQUIVO_MCP_REMOTE_TOKENS}")
    except Exception as exc:
        logger.warning(f"Erro ao salvar em {ARQUIVO_MCP_REMOTE_TOKENS}: {exc}")


def renovar_token_refresh(
    refresh_token: Optional[str] = None,
    client_id: Optional[str] = None
) -> Optional[str]:
    """Executa a renovação do access_token utilizando o refresh_token."""
    dados = carregar_dados_tokens()
    rtok = refresh_token or dados.get("refresh_token")
    cid = client_id or dados.get("client_id") or DEFAULT_CLIENT_ID

    if not rtok:
        logger.warning("Nenhum refresh_token disponível para renovação automática.")
        return None

    corpo_requisicao = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": rtok,
        "client_id": cid
    }).encode("utf-8")

    req = urllib.request.Request(
        MCP_TOKEN_ENDPOINT,
        data=corpo_requisicao,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "DataWave-Client/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resposta = json.loads(resp.read().decode("utf-8"))
            novo_acc = resposta.get("access_token")
            novo_ref = resposta.get("refresh_token") or rtok
            exp_in = int(resposta.get("expires_in", 3600))
            if novo_acc:
                salvar_tokens_renovados(novo_acc, novo_ref, exp_in, cid)
                logger.info("Token OAuth Logcomex renovado com sucesso via refresh_token.")
                return novo_acc
    except Exception as exc:
        logger.warning(f"Falha ao renovar token OAuth Logcomex: {exc}")
        return None
    return None


def obter_token_valido(forcar_refresh: bool = False) -> Tuple[Optional[str], Dict[str, Any]]:
    """Recupera o token de acesso válido, renovando se necessário sem descartar credencial ativa."""
    dados = carregar_dados_tokens()
    acc = dados.get("access_token")

    if not acc:
        return None, {"status": "SEM_TOKEN", "mensagem": "Nenhum token configurado."}

    if forcar_refresh or token_esta_expirado(dados):
        logger.info("Token MCP Logcomex próximo da expiração. Tentando renovação automática...")
        novo_acc = renovar_token_refresh(dados.get("refresh_token"), dados.get("client_id"))
        if novo_acc:
            return novo_acc, {"status": "RENOVADO", "mensagem": "Token renovado com sucesso via refresh_token."}
        else:
            # Não descarta o access_token existente: mantém para validação direta em chamadas HTTP
            return acc, {"status": "VALIDO_EXISTENTE", "mensagem": "Utilizando access_token com fallback transparente."}

    return acc, {"status": "VALIDO", "mensagem": "Token ativo e válido."}


def gerar_url_autorizacao(
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None
) -> Tuple[str, str, str]:
    """Gera os parâmetros PKCE e a URL para o usuário autorizar o app no navegador.

    Retorna: (auth_url, code_verifier, state)
    """
    r_uri = redirect_uri or DEFAULT_CALLBACK_URL
    cid = client_id or obter_client_id_para_redirect_uri(r_uri)
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    state = secrets.token_hex(16)

    params = {
        "response_type": "code",
        "client_id": cid,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "redirect_uri": r_uri,
        "scope": "mcp:chat:agents mcp:chat:free offline_access",
        "state": state,
        "prompt": "consent",
        "resource": "https://mcp.logcomex.ai/"
    }
    auth_url = f"{MCP_AUTHORIZE_ENDPOINT}?{urllib.parse.urlencode(params)}"
    salvar_estado_oauth(state, code_verifier, r_uri, cid)
    return auth_url, code_verifier, state


def trocar_codigo_por_token(
    code: str,
    code_verifier: str,
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Troca o authorization code pelo par de tokens OAuth (access_token + refresh_token)."""
    r_uri = redirect_uri or DEFAULT_CALLBACK_URL
    cid = client_id or obter_client_id_para_redirect_uri(r_uri)
    corpo = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "client_id": cid,
        "redirect_uri": r_uri
    }).encode("utf-8")

    req = urllib.request.Request(
        MCP_TOKEN_ENDPOINT,
        data=corpo,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "DataWave-Client/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resposta = json.loads(resp.read().decode("utf-8"))
            acc = resposta.get("access_token")
            ref = resposta.get("refresh_token")
            exp_in = int(resposta.get("expires_in", 3600))
            if acc:
                salvar_tokens_renovados(acc, ref, exp_in, cid)
                return resposta
    except Exception as exc:
        logger.error(f"Erro ao trocar código por token OAuth: {exc}")
        return None
    return None
