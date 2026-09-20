"""Camada de abstração e clientes do Agente DataWave.

Define a interface abstrata AgentClient e implementações:
- FakeAgent: Reprodução de fixtures e mocks para testes determinísticos offline.
- LogcomexMCPAgent: Integração com o servidor MCP da Logcomex (chat_with_agent, polling e retries).
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AgentRefusalError(Exception):
    """Lançada quando a resposta do agente aciona o guardrail (ex.: trust.logcomex.ai)."""
    pass


class AgentClient(ABC):
    """Interface abstrata para comunicação com o Agente DataWave."""

    @abstractmethod
    def ask_agent(
        self,
        message: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """Envia mensagem textual ao agente e retorna a resposta textual bruta."""
        pass

    def ask_json(
        self,
        prompt: str,
        model_cls: Type[T],
        max_retries: int = 2,
        attachments: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Optional[str] = None
    ) -> T:
        """Solicita ao agente uma resposta em JSON estruturado, validando contra o modelo Pydantic.

        Aplica limpeza de eventuais delimitadores markdown e executa retentativas informando o erro.
        """
        schema_json = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
        formatted_prompt = (
            f"{prompt}\n\n"
            f"Responda EXCLUSIVAMENTE com o objeto JSON correspondente ao esquema abaixo, "
            f"sem blocos markdown (sem ```json), sem texto introdutório ou saudações:\n"
            f"{schema_json}"
        )

        current_message = formatted_prompt
        last_error = None

        for attempt in range(max_retries + 1):
            raw_response = self.ask_agent(
                current_message,
                attachments=attachments,
                conversation_id=conversation_id
            )

            # Verificação de recusa do guardrail da Logcomex
            if "trust.logcomex.ai" in raw_response:
                raise AgentRefusalError(
                    f"O agente recusou a solicitação com redirecionamento para trust.logcomex.ai: {raw_response}"
                )

            # Limpeza preventiva de cercas markdown (ex.: ```json ... ```)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

            try:
                data = json.loads(cleaned)
                return model_cls.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                logger.warning(
                    f"Tentativa {attempt + 1}/{max_retries + 1} de parsing JSON falhou para {model_cls.__name__}: {exc}"
                )
                if attempt < max_retries:
                    current_message = (
                        f"Sua resposta anterior continha o seguinte erro de validação JSON/esquema:\n"
                        f"{str(exc)}\n\n"
                        f"Por favor, corrija e retorne unicamente o JSON válido para o modelo {model_cls.__name__}."
                    )

        raise ValueError(
            f"Falha ao validar resposta do agente para o modelo {model_cls.__name__} após {max_retries + 1} tentativas. "
            f"Último erro: {last_error}. Resposta bruta: {raw_response!r}"
        )


class FakeAgent(AgentClient):
    """Cliente mock para testes offline, benchmark e contingência na demo."""

    def __init__(self, fixtures_dir: Optional[str | Path] = None):
        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir else Path(__file__).parent / "fixtures" / "agent"
        self.recorded_calls: List[Dict[str, Any]] = []

    def ask_agent(
        self,
        message: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        self.recorded_calls.append({
            "message": message,
            "attachments": attachments,
            "conversation_id": conversation_id,
            "timestamp": time.time()
        })

        # 1. Tentar localizar fixture gravada
        if self.fixtures_dir.exists():
            # Priorizar o prompt original do usuário antes do schema JSON appended pelo ask_json
            prompt_user = message.split("\n\nResponda EXCLUSIVAMENTE")[0].strip()
            alvo_busca = prompt_user if prompt_user else message

            for fix_file in sorted(self.fixtures_dir.glob("*.json")):
                try:
                    fix_data = json.loads(fix_file.read_text(encoding="utf-8"))
                    kw = fix_data.get("match_keyword")
                    keywords = fix_data.get("match_keywords", [kw] if kw else [])
                    
                    matched = False
                    for k in keywords:
                        if not k:
                            continue
                        pattern = rf"(?:\b|_){re.escape(k.lower())}(?:\b|_)"
                        if re.search(pattern, alvo_busca.lower()):
                            matched = True
                            break

                    if matched:
                        resp = fix_data["response"]
                        return json.dumps(resp, ensure_ascii=False) if not isinstance(resp, str) else resp
                except Exception:
                    continue

        # 2. Mock determinístico de resposta com base no conteúdo da mensagem
        msg_lower = message.lower()
        if "operacaoextraida" in msg_lower or "bill of lading" in msg_lower or "invoice" in msg_lower:
            return json.dumps({
                "ncm": "8481.80.95",
                "descricao": "Válvulas industriais de controle de fluxo em aço inox",
                "valor_lote_usd": 68500.0,
                "qtd_conteineres": 1,
                "tipo_conteiner": "40HC",
                "incoterm": "FOB",
                "porto_descarga": "Santos",
                "armador": "Maersk",
                "origem": "Alemanha",
                "data_chegada_prevista": "2026-04-10",
                "divergencias": [
                    "Divergência de peso bruto: BL indica 14.500 kg, enquanto o Packing List indica 14.150 kg."
                ]
            })

        if "mercadoncm" in msg_lower or "mercado" in msg_lower:
            return json.dumps({
                "ncm": "8481.80.95",
                "periodo": "Últimos 12 meses",
                "volume_mensal": {"2025-04": 250000.0, "2025-05": 310000.0},
                "origens_top": ["Alemanha", "China", "Estados Unidos"],
                "importadores_top": ["Indústria Mecânica Modelo S.A."],
                "dias_chegada_desembaraco": {"canal_verde": 3.2, "canal_amarelo": 6.8, "canal_vermelho": 15.5}
            })

        if "sugestaoatributos" in msg_lower or "atributo" in msg_lower:
            return json.dumps({
                "sugestoes": {"ATT_14200": "07", "ATT_14245": "01"},
                "incertos": ["ATT_14186"]
            })

        return "Resposta mock do agente DataWave para consulta geral."


class LogcomexMCPAgent(AgentClient):
    """Cliente para invocação direta do servidor MCP da Logcomex (Agente DataWave)."""

    def __init__(
        self,
        agent_id: str = "c2322f9c-41e2-4bf8-8fe5-3bd93f4063d4",
        mcp_caller: Optional[Any] = None,
        timeout_seconds: int = 120,
        base_url: str = "https://mcp.logcomex.ai/"
    ):
        self.agent_id = agent_id
        self.mcp_caller = mcp_caller
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url

    def _obter_token_acesso(self, forcar_refresh: bool = False) -> Optional[str]:
        """Recupera o Bearer token OAuth2 dos arquivos locais, renovando automaticamente se expirado."""
        try:
            from datawave.auth_manager import obter_token_valido
            token, _ = obter_token_valido(forcar_refresh=forcar_refresh)
            return token
        except Exception as exc:
            logger.debug(f"Falha ao obter token pelo auth_manager: {exc}")
            return None

    def check_health(self) -> bool:
        """Verifica se o servidor MCP remoto está acessível e com credencial válida."""
        if self.mcp_caller is not None:
            return True
        token = self._obter_token_acesso()
        if not token:
            return False
        try:
            from datawave.auth_manager import carregar_dados_tokens, token_esta_expirado
            dados = carregar_dados_tokens()
            if token_esta_expirado(dados):
                token = self._obter_token_acesso(forcar_refresh=True)
                if not token:
                    return False
            return True
        except Exception:
            return False

    def _invocar_ferramenta(self, tool_name: str, arguments: Dict[str, Any], _tentativa_retry: bool = False) -> str:
        """Invoca a ferramenta MCP via mcp_caller ou requisição HTTPS JSON-RPC nativa com retry automático em 401."""
        if self.mcp_caller is not None:
            try:
                return self.mcp_caller(tool_name, arguments, self.timeout_seconds)
            except TypeError:
                return self.mcp_caller(tool_name=tool_name, arguments=arguments, timeout=self.timeout_seconds)

        import urllib.request
        import urllib.error
        token = self._obter_token_acesso()
        if not token:
            raise RuntimeError("Token de autorização MCP não encontrado para Logcomex. Execute a autenticação para conectar.")

        payload_rpc = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": f"dw-{int(time.time()*1000)}"
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload_rpc).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                corpo = json.loads(resp.read().decode("utf-8"))
                if "error" in corpo:
                    raise RuntimeError(f"Erro retornado pelo MCP Logcomex: {corpo['error']}")
                resultado = corpo.get("result", {})
                conteudo = resultado.get("content", [])
                textos = [item.get("text", "") for item in conteudo if isinstance(item, dict) and item.get("type") == "text"]
                return "\n".join(textos) if textos else str(resultado)
        except urllib.error.HTTPError as http_err:
            if http_err.code == 401 and not _tentativa_retry:
                logger.info("HTTP 401 retornado pelo MCP Logcomex. Tentando renovação automática de token...")
                novo_token = self._obter_token_acesso(forcar_refresh=True)
                if novo_token:
                    return self._invocar_ferramenta(tool_name, arguments, _tentativa_retry=True)
            raise RuntimeError(f"Erro HTTP na chamada ao MCP Logcomex ({http_err.code} {http_err.reason}).")

    def ask_agent(
        self,
        message: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Optional[str] = None,
        skill: Optional[str] = None,
        poll_interval: float = 3.0
    ) -> str:
        args = {
            "agent_id": self.agent_id,
            "message": message
        }
        if conversation_id:
            args["conversation_id"] = conversation_id
        if attachments:
            args["attachments"] = attachments
        if skill:
            args["skill"] = skill

        resposta = self._invocar_ferramenta("chat_with_agent", args)

        # Polling assíncrono caso o agente retorne task_id de processamento longo
        m = re.search(r'task_id=["\']?([^"\'\s,]+)["\']?', resposta)
        if m:
            task_id = m.group(1).rstrip(".")
            logger.info(f"Processamento assíncrono acionado no MCP. task_id={task_id}. Iniciando polling...")
            inicio = time.time()
            while time.time() - inicio < self.timeout_seconds:
                time.sleep(poll_interval)
                status_res = self._invocar_ferramenta("get_task_status", {"task_id": task_id})
                if status_res and not any(term in status_res.lower() for term in ["processing", "pendente", "aguardando"]):
                    return status_res
            logger.warning(f"Timeout aguardando conclusão da task {task_id}.")

        return resposta
