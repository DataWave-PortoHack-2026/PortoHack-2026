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

        # Valida criação do log auditável
        from datawave.pipeline import LOG_FILE
        self.assertTrue(LOG_FILE.exists())


if __name__ == "__main__":
    unittest.main()
