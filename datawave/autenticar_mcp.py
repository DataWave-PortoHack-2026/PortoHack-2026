"""Script interativo e servidor de callback OAuth 2.0 PKCE para autenticação com o Logcomex MCP.

Permite autenticar com 1 clique: abre o navegador na página de autorização da Logcomex,
escuta na porta 16951, recebe o authorization code, efetua a troca por access_token e refresh_token,
e salva os tokens atualizados para uso transparente pelo DataWave e mcp-remote.
"""
from __future__ import annotations

import html
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging
import sys
import threading
import time
from typing import Optional
import urllib.parse
import webbrowser

from datawave.auth_manager import (
    CALLBACK_PORT,
    CALLBACK_URL,
    DEFAULT_CLIENT_ID,
    gerar_url_autorizacao,
    trocar_codigo_por_token,
    carregar_dados_tokens,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mcp_auth")

_servidor_auth: Optional[HTTPServer] = None
_auth_sucesso: bool = False
_erro_mensagem: Optional[str] = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    code_verifier: str = ""
    expected_state: str = ""
    client_id: str = DEFAULT_CLIENT_ID

    def log_message(self, format: str, *args: tuple) -> None:
        pass  # Silencia logs padrão do HTTP

    def do_GET(self) -> None:
        global _auth_sucesso, _erro_mensagem
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/oauth/callback":
            params = urllib.parse.parse_qs(parsed_url.query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                _erro_mensagem = f"Erro reportado pelo servidor de autorização: {error}"
                self._responder_html(400, "Erro na Autenticação", f"<p style='color:red;'>{html.escape(_erro_mensagem)}</p>")
                self._finalizar_servidor()
                return

            if not code or state != self.expected_state:
                _erro_mensagem = "Parâmetros inválidos ou divergência de estado (state mismatch)."
                self._responder_html(400, "Falha de Validação", f"<p style='color:red;'>{html.escape(_erro_mensagem)}</p>")
                self._finalizar_servidor()
                return

            # Efetua a troca do código por tokens
            resultado = trocar_codigo_por_token(code, self.code_verifier, self.client_id)
            if resultado and resultado.get("access_token"):
                _auth_sucesso = True
                self._responder_html(
                    200,
                    "Autenticação Concluída",
                    """
                    <h2 style='color:#10b981;'>Autenticação com Logcomex AI realizada com sucesso!</h2>
                    <p>O token de acesso e a chave de renovação foram gravados com sucesso.</p>
                    <p>Você pode fechar esta aba do navegador e retornar ao painel do <strong>DataWave</strong>.</p>
                    """
                )
            else:
                _erro_mensagem = "Não foi possível trocar o código de autorização pelo token de acesso na Logcomex."
                self._responder_html(500, "Erro ao Obter Tokens", f"<p style='color:red;'>{html.escape(_erro_mensagem)}</p>")

            self._finalizar_servidor()
        else:
            self._responder_html(404, "Não Encontrado", "<p>Endpoint não reconhecido.</p>")

    def _responder_html(self, status: int, titulo: str, corpo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{titulo} · DataWave</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #1e293b;
            padding: 32px 40px;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            max-width: 500px;
            text-align: center;
            border: 1px solid #334155;
        }}
        h2 {{ margin-top: 0; }}
        p {{ color: #94a3b8; line-height: 1.5; }}
    </style>
</head>
<body>
    <div class="card">
        {corpo}
    </div>
</body>
</html>"""
        self.wfile.write(html_content.encode("utf-8"))

    def _finalizar_servidor(self) -> None:
        def shutdown_thread():
            time.sleep(1)
            global _servidor_auth
            if _servidor_auth:
                _servidor_auth.shutdown()

        threading.Thread(target=shutdown_thread, daemon=True).start()


def executar_fluxo_autenticacao(timeout_segundos: int = 180, abrir_navegador: bool = True) -> bool:
    """Inicia o servidor de callback local e abre o navegador para autenticação do usuário."""
    global _servidor_auth, _auth_sucesso, _erro_mensagem
    _auth_sucesso = False
    _erro_mensagem = None

    auth_url, code_verifier, state = gerar_url_autorizacao(DEFAULT_CLIENT_ID)

    OAuthCallbackHandler.code_verifier = code_verifier
    OAuthCallbackHandler.expected_state = state
    OAuthCallbackHandler.client_id = DEFAULT_CLIENT_ID

    try:
        _servidor_auth = HTTPServer(("127.0.0.1", CALLBACK_PORT), OAuthCallbackHandler)
    except OSError as exc:
        logger.error(f"Porta {CALLBACK_PORT} já está em uso ou inacessível: {exc}")
        return False

    print("\n" + "=" * 70)
    print("INICIANDO FLUXO DE AUTENTICAÇÃO OAUTH COM O AGENTE LOGCOMEX")
    print("=" * 70)
    print("Caso o navegador não abra automaticamente, acesse o link abaixo:")
    print(auth_url)
    print("=" * 70 + "\n")

    if abrir_navegador:
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

    server_thread = threading.Thread(target=_servidor_auth.serve_forever, daemon=True)
    server_thread.start()

    inicio = time.time()
    while server_thread.is_alive() and (time.time() - inicio < timeout_segundos):
        time.sleep(0.5)

    if _servidor_auth:
        try:
            _servidor_auth.server_close()
        except Exception:
            pass

    if _auth_sucesso:
        print("\nAutenticação concluída com sucesso! Agente Logcomex pronto para uso.")
        return True
    else:
        print(f"\nAutenticação não concluída: {_erro_mensagem or 'Tempo limite excedido'}.")
        return False


if __name__ == "__main__":
    sucesso = executar_fluxo_autenticacao()
    sys.exit(0 if sucesso else 1)
