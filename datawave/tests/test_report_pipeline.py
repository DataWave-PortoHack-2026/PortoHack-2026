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


if __name__ == "__main__":
    unittest.main()

