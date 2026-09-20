"""Testes unitários e de integração para o Módulo E (Parecer Executivo) e Pipeline Orquestrador."""
import json
import unittest
from pathlib import Path

from datawave.engine.cost import carregar_tarifas, gerar_recomendacao
from datawave.engine.risk import simular_permanencia_monte_carlo
from datawave.schemas import OperacaoExtraida, TarifasConfig


class TestReportAndPipeline(unittest.TestCase):
    def setUp(self):
        self.operacao = OperacaoExtraida(
            ncm="3808.93.29",
            descricao="Defensivos Agrícolas",
            valor_lote_usd=128500.0,
            qtd_conteineres=1,
            incoterm="FOB",
            porto_descarga="Santos",
            divergencias=["Inconsistência cadastral: A01 · Registro de Aptidão ausente"]
        )
        self.tarifas = TarifasConfig(
            cambio_usd_brl=5.50,
            free_time_demurrage_dias=5,
            demurrage_diaria_usd=150.0
        )
        self.risco = simular_permanencia_monte_carlo(
            operacao=self.operacao,
            orgao_anuente=True,
            operador_oea=False,
            free_time_dias=5,
            seed=42,
            n_amostras=5000
        )
        self.recomendacao = gerar_recomendacao(
            op=self.operacao,
            tarifas=self.tarifas,
            distribuicao_permanencia=self.risco.distribuicao_dias
        )

    def test_gerar_parecer_executivo_estrutura_e_validacao(self):
        """Valida se o parecer executivo é gerado com todas as seções e passa no validador estrito."""
        from datawave.engine.report import gerar_parecer_executivo, validar_conformidade_relatorio

        parecer = gerar_parecer_executivo(
            operacao=self.operacao,
            tarifas=self.tarifas,
            risco=self.risco,
            recomendacao=self.recomendacao
        )

        self.assertIn("PARECER TÉCNICO ADUANEIRO", parecer.texto)
        self.assertIn("1. IDENTIFICAÇÃO DA OPERAÇÃO", parecer.texto)
        self.assertIn("2. AUDITORIA PREVENTIVA DE CATÁLOGO", parecer.texto)
        self.assertIn("3. AVALIAÇÃO PROBABILÍSTICA DE PERMANÊNCIA", parecer.texto)
        self.assertIn("4. MATRIZ FINANCEIRA COMPARATIVA", parecer.texto)
        self.assertIn("5. PARECER PRESCRITIVO E INSTRUÇÃO DE TRÂNSITO", parecer.texto)
        self.assertTrue(parecer.valido)

        # O validador estrito deve aprovar sem erros
        valido, inconsistencias = validar_conformidade_relatorio(parecer.texto, parecer.valores_esperados)
        self.assertTrue(valido)
        self.assertEqual(len(inconsistencias), 0)

    def test_validador_regex_detecta_divergencia_injetada(self):
        """Valida se o validador por expressões regulares barra números alterados no texto."""
        from datawave.engine.report import (
            RelatorioInconsistenteError,
            gerar_parecer_executivo,
            validar_conformidade_relatorio,
        )

        parecer = gerar_parecer_executivo(
            operacao=self.operacao,
            tarifas=self.tarifas,
            risco=self.risco,
            recomendacao=self.recomendacao
        )

        # Injeta um valor monetário corrompido no texto
        texto_corrompido = parecer.texto.replace("R$ 5,50", "R$ 9,99")
        valido, inconsistencias = validar_conformidade_relatorio(texto_corrompido, parecer.valores_esperados)
        self.assertFalse(valido)
        self.assertGreater(len(inconsistencias), 0)

    def test_pipeline_orquestrador_execucao_completa(self):
        """Valida o encadeamento ponta a ponta do pipeline DataWave."""
        from datawave.pipeline import executar_pipeline_datawave

        payload = {
            "ncm": "38089329",
            "descricao": "Defensivos Agrícolas Anápolis",
            "valor_lote_usd": 128500.0,
            "qtd_conteineres": 1,
            "porto_descarga": "Santos",
            "free_time_dias": 5,
            "demurrage_diaria_usd": 150.0,
            "cambio_usd_brl": 5.50,
            "orgao_anuente": True,
            "operador_oea": False,
            "divergencias": ["A01 ausente"]
        }

        resultado = executar_pipeline_datawave(payload)

        self.assertIn("trace_id", resultado)
        self.assertIn("operacao", resultado)
        self.assertIn("risco", resultado)
        self.assertIn("custo", resultado)
        self.assertIn("parecer", resultado)
        self.assertEqual(resultado["custo"]["opcao_recomendada"], "RETROPORTO")
        self.assertTrue(resultado["parecer"]["valido"])

    def test_pipeline_com_agente_integrado(self):
        """Valida se o pipeline executa com o cliente do agente integrado (U1-U4) e registra trilha."""
        from datawave.pipeline import executar_pipeline_datawave

        payload = {
            "ncm": "2204.21.00",
            "descricao": "Vinho Fino Casal Branco Fernão Pires",
            "valor_lote_usd": 65000.0,
            "qtd_conteineres": 1,
            "porto_descarga": "Santos",
            "free_time_dias": 7,
            "demurrage_diaria_usd": 150.0,
            "cambio_usd_brl": 5.50,
            "orgao_anuente": True,
            "operador_oea": False
        }

        resultado = executar_pipeline_datawave(payload, usar_agente=True)
        self.assertIn("trace_id", resultado)
        self.assertIn("modo_agente", resultado)
        self.assertIn("agente_dados", resultado)
        self.assertIn("mercado", resultado["agente_dados"])
        self.assertIn("atributos", resultado["agente_dados"])
        self.assertTrue(resultado["parecer"]["valido"])
        self.assertIn("plano_correcoes", resultado)
        self.assertGreaterEqual(resultado["plano_correcoes"]["total_pendencias"], 1)

    def test_pipeline_com_planilha_csv(self):
        """Valida se o pipeline processa uma planilha CSV completa com auditoria documental."""
        from datawave.pipeline import executar_pipeline_datawave

        csv_data = """ncm,descricao,quantidade,valor_total_usd,peso_bruto_bl_kg,peso_bruto_packing_kg,incoterm,porto_descarga
2204.21.00,Vinho Casal Branco,1200,68500.0,14500.0,14050.0,FOB,Santos
"""
        payload = {}
        resultado = executar_pipeline_datawave(payload, planilha_csv=csv_data, usar_agente=True)
        self.assertEqual(resultado["operacao"]["ncm"], "2204.21.00")
        self.assertEqual(resultado["operacao"]["valor_lote_usd"], 68500.0)
        self.assertTrue(any("450" in d for d in resultado["operacao"]["divergencias"]))
        self.assertIn("plano_correcoes", resultado)
        correcoes = resultado["plano_correcoes"]["correcoes"]
        self.assertTrue(any(c["categoria"] == "Documental" for c in correcoes))

    def test_pipeline_com_rota_comex_e_linha_do_tempo(self):
        """Valida se o pipeline constrói o objeto rota_comex e a linha_do_tempo com 3 estágios operacionais."""
        from datawave.pipeline import executar_pipeline_datawave

        payload = {
            "ncm": "38089329",
            "descricao": "Herbicidas para lavoura",
            "valor_lote_usd": 128500.0,
            "free_time_dias": 5
        }
        resultado = executar_pipeline_datawave(payload, usar_agente=True)
        self.assertIn("rota_comex", resultado)
        rota = resultado["rota_comex"]
        self.assertIn("origem", rota)
        self.assertIn("porto_descarga", rota)
        self.assertIn("destino_final", rota)
        self.assertIn("rota_formatada", rota)
        self.assertTrue("China" in rota["origem"] or "China" in rota["rota_formatada"])
        self.assertTrue("Santos" in rota["porto_descarga"] or "Santos" in rota["rota_formatada"])
        self.assertTrue("Anápolis" in rota["destino_final"] or "Anápolis" in rota["rota_formatada"])

        self.assertIn("linha_do_tempo", resultado)
        timeline = resultado["linha_do_tempo"]
        self.assertEqual(len(timeline), 3)
        self.assertEqual(timeline[0]["faixa_dias"], "0 a 5 dias")
        self.assertIn("Free Time", timeline[0]["fase"])
        self.assertTrue(any(term in timeline[1]["fase"] for term in ["Conferência", "Retenção", "Inspeção", "MAPA"]))
        self.assertTrue(any(term in timeline[2]["fase"] for term in ["Entrega Final", "Desembaraço", "Trânsito"]))

    def test_linha_do_tempo_gerada_pelo_agente_logcomex_dinamica(self):
        """Valida que a linha do tempo gerada pelo agente varia conforme o NCM e perfil, sem 7 em 7 dias fixos."""
        from datawave.agent_client import FakeAgent
        from datawave.engine.report import gerar_linha_do_tempo_via_agente_logcomex
        from datawave.schemas import OperacaoExtraida, ResultadoRiscoPermanencia, TarifasConfig, RecomendacaoDecisao

        client = FakeAgent()

        # Teste 1: NCM 3808 (Defensivos Agrícolas / MAPA)
        op_3808 = OperacaoExtraida(
            ncm="3808.93.29",
            descricao="Herbicida glifosato",
            valor_lote_usd=128500.0,
            porto_descarga="Santos",
            destino_final="Anápolis/GO (DAA)"
        )
        risco_3808 = ResultadoRiscoPermanencia(
            canal_mais_provavel="vermelho",
            permanencia_media=14.5,
            permanencia_p50=12.0,
            permanencia_p90=17.0,
            probabilidade_estouro_free_time=0.82,
            distribuicao_dias={10: 0.1, 14: 0.4, 17: 0.5},
            fonte_parametros="agente"
        )
        tarifas_3808 = TarifasConfig(free_time_demurrage_dias=5, demurrage_diaria_usd=120.0)
        rec_3808 = RecomendacaoDecisao(
            opcao_recomendada="RETROPORTO",
            custo_esperado_cais_brl=69271.12,
            custo_esperado_retro_brl=4235.12,
            economia_esperada_brl=65036.0,
            probabilidade_estouro_free_time=0.82,
            p90_dias_permanencia=17.0,
            justificativa="Retenção crítica fitossanitária."
        )

        timeline_3808 = gerar_linha_do_tempo_via_agente_logcomex(client, op_3808, risco_3808, tarifas_3808, rec_3808)
        self.assertEqual(len(timeline_3808), 3)
        self.assertEqual(timeline_3808[0].faixa_dias, "0 a 5 dias")
        self.assertEqual(timeline_3808[1].faixa_dias, "5 a 17 dias")
        self.assertEqual(timeline_3808[2].faixa_dias, "17+ dias")
        self.assertTrue("MAPA" in timeline_3808[1].fase or "Vermelho" in timeline_3808[1].fase)

        # Teste 2: NCM 8525 (Eletrônicos / Canal Amarelo RFB)
        op_8525 = OperacaoExtraida(
            ncm="8525.80.90",
            descricao="Câmeras digitais",
            valor_lote_usd=412000.0,
            porto_descarga="Santos",
            destino_final="São Paulo/SP"
        )
        risco_8525 = ResultadoRiscoPermanencia(
            canal_mais_provavel="amarelo",
            permanencia_media=5.5,
            permanencia_p50=4.2,
            permanencia_p90=11.0,
            probabilidade_estouro_free_time=0.45,
            distribuicao_dias={4: 0.3, 6: 0.5, 11: 0.2},
            fonte_parametros="agente"
        )
        tarifas_8525 = TarifasConfig(free_time_demurrage_dias=7, demurrage_diaria_usd=100.0)
        rec_8525 = RecomendacaoDecisao(
            opcao_recomendada="CAIS",
            custo_esperado_cais_brl=3000.0,
            custo_esperado_retro_brl=3800.0,
            economia_esperada_brl=800.0,
            probabilidade_estouro_free_time=0.45,
            p90_dias_permanencia=11.0,
            justificativa="Liberação rápida no cais."
        )

        timeline_8525 = gerar_linha_do_tempo_via_agente_logcomex(client, op_8525, risco_8525, tarifas_8525, rec_8525)
        self.assertEqual(len(timeline_8525), 3)
        self.assertEqual(timeline_8525[0].faixa_dias, "0 a 7 dias")
        self.assertEqual(timeline_8525[1].faixa_dias, "7 a 11 dias")
        self.assertEqual(timeline_8525[2].faixa_dias, "11+ dias")
        self.assertNotEqual(timeline_3808[1].faixa_dias, timeline_8525[1].faixa_dias)


if __name__ == "__main__":
    unittest.main()


