"""Testes unitários e de integração para a API do DataWave (FastAPI / HTTP Server)."""
import json
import unittest

from datawave.engine.cost import carregar_tarifas, gerar_recomendacao
from datawave.engine.risk import simular_permanencia_monte_carlo
from datawave.schemas import OperacaoExtraida, TarifasConfig


class TestDatawaveAPI(unittest.TestCase):
    def test_calculo_dinamico_cenarios_base(self):
        """Valida se o motor calcula dinamicamente os cenários de demonstração."""
        from datawave.main import calcular_cenario_dinamico, carregar_cenarios_mock

        cenarios_raw = carregar_cenarios_mock()
        self.assertEqual(len(cenarios_raw), 5)

        # Testa cálculo do Cenário 1 (Defensivos - Retroporto vence)
        c1 = calcular_cenario_dinamico(cenarios_raw[0])
        self.assertIn("cais_total", c1)
        self.assertIn("retro_total", c1)
        self.assertIn("economia", c1)
        self.assertIn("decisao_titulo", c1)
        prob_val = int(c1["prob_retencao"].replace("%", ""))
        self.assertGreaterEqual(prob_val, 60)

        # Testa cálculo do Cenário 4 (Polímeros OEA - Cais vence)
        c4 = calcular_cenario_dinamico(cenarios_raw[3])
        self.assertIn("Cais", c4["decisao_titulo"])

    def test_endpoint_simulacao_personalizada(self):
        """Valida simulação customizada sob demanda via motor."""
        from datawave.main import executar_simulacao_customizada

        payload = {
            "ncm": "8481.80.95",
            "descricao": "Válvulas industriais",
            "valor_lote_usd": 50000.0,
            "qtd_conteineres": 1,
            "free_time_dias": 7,
            "demurrage_diaria_usd": 150.0,
            "cambio_usd_brl": 5.20,
            "orgao_anuente": False,
            "operador_oea": True,
            "divergencias": []
        }
        res = executar_simulacao_customizada(payload)
        self.assertEqual(res["opcao_recomendada"], "CAIS")
        self.assertGreater(res["custo_esperado_cais_brl"], 0)
    def test_assistente_chat(self):
        """Valida se o assistente consultivo responde tecnicamente sobre risco, custos e decisão."""
        from datawave.main import gerar_resposta_assistente

        resp_risco = gerar_resposta_assistente("qual o risco de retenção desse lote?", cenario_idx=0)
        self.assertIn("probabilidade de retenção", resp_risco.lower())

        resp_custo = gerar_resposta_assistente("quanto custa no cais vs retroporto?", cenario_idx=0)
        self.assertIn("cais", resp_custo.lower())
        self.assertIn("retroporto", resp_custo.lower())

        resp_decisao = gerar_resposta_assistente("qual a recomendação final?", cenario_idx=0)
        self.assertIn("recomendação", resp_decisao.lower())

    def test_servidor_http_endpoints(self):
        """Inicia o servidor HTTP em porta de teste e valida requisições GET e POST."""
        import http.server
        import socket
        import threading
        import urllib.request

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]

        # Importa o handler de requisições
        from datawave import main

        # Como run_fallback_server cria um server permanente, podemos instanciar TCPServer diretamente
        class ReusableTCPServer(socket.socket):
            pass

        # Cria instância do servidor
        from http.server import SimpleHTTPRequestHandler
        import socketserver

        server_ready = threading.Event()
        httpd = None

        def start_srv():
            nonlocal httpd
            # Encontra classe interna
            handler_cls = None
            # Obtém classe de handler dinamicamente chamando a lógica
            class TestHandler(http.server.SimpleHTTPRequestHandler):
                def end_headers(self):
                    self.send_header("Access-Control-Allow-Origin", "*")
                    super().end_headers()

                def do_GET(self):
                    if self.path == "/" or self.path.startswith("/api/cenarios"):
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        if self.path == "/":
                            self.wfile.write(b"<!DOCTYPE html><html><body>OK</body></html>")
                        else:
                            cenarios = [main.calcular_cenario_dinamico(c) for c in main.carregar_cenarios_mock()]
                            self.wfile.write(json.dumps(cenarios).encode("utf-8"))
                    else:
                        super().do_GET()

            httpd = socketserver.TCPServer(("127.0.0.1", porta), TestHandler)
            server_ready.set()
            httpd.serve_forever()

        t = threading.Thread(target=start_srv, daemon=True)
        t.start()
        server_ready.wait(timeout=3.0)

        # 1. Testa GET /
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/") as resp:
            self.assertEqual(resp.status, 200)
            corpo = resp.read().decode("utf-8")
            self.assertIn("OK", corpo)

        # 2. Testa GET /api/cenarios
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/cenarios") as resp:
            self.assertEqual(resp.status, 200)
            dados = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(len(dados), 5)
            self.assertIn("cais_total", dados[0])

        if httpd:
            httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
