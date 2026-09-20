"""Parser e normalizador geral de planilhas aduaneiras.

Ingere planilhas em formato CSV, TSV ou JSON enviadas por despachantes aduaneiros,
normaliza nomenclaturas heterogêneas de colunas e consolida as operações e
divergências documentais para auditoria pelo Agente Logcomex DataWave.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from datawave.schemas import ItemPlanilhaAduaneira, OperacaoExtraida

logger = logging.getLogger(__name__)

# Sinônimos comuns de cabeçalhos de planilhas de comércio exterior
MAPA_COLUNAS: Dict[str, List[str]] = {
    "ncm": ["ncm", "classificacao_fiscal", "sh", "codigo_ncm", "ncm_code", "posicao_fiscal"],
    "descricao": ["descricao", "mercadoria", "descricao_mercadoria", "item", "produto", "description", "goods_description"],
    "quantidade": ["quantidade", "qtd", "qtde", "quantity", "volume_unidades", "volume"],
    "unidade_medida": ["unidade", "unidade_medida", "uom", "un", "unit"],
    "valor_unitario_usd": ["valor_unitario_usd", "valor_unitario", "preco_unitario", "unit_price", "unit_value_usd"],
    "valor_total_usd": ["valor_total_usd", "valor_total", "valor_fob", "fob_usd", "valor_aduaneiro_usd", "total_usd", "fob", "valor_lote_usd"],
    "peso_liquido_kg": ["peso_liquido_kg", "peso_liquido", "net_weight", "net_weight_kg", "liquid_weight"],
    "peso_bruto_bl_kg": ["peso_bruto_bl_kg", "peso_bruto_bl", "peso_bl", "bl_gross_weight", "bl_weight", "peso_conhecimento", "peso_bruto_conhecimento", "gross_weight_bl"],
    "peso_bruto_packing_kg": ["peso_bruto_packing_kg", "peso_bruto_packing", "peso_packing", "peso_pl", "pl_gross_weight", "packing_weight", "peso_romaneio", "gross_weight_pl"],
    "incoterm": ["incoterm", "termo_venda", "condicao_venda", "terms"],
    "porto_descarga": ["porto", "porto_descarga", "porto_destino", "port_of_discharge", "pod", "recinto"],
    "origem": ["origem", "pais_origem", "pais_procedencia", "procedencia", "country_of_origin", "origin", "procedencia_pais"],
    "porto_embarque": ["porto_embarque", "pol", "port_of_loading", "porto_origem", "loading_port"],
    "destino_final": ["destino_final", "destino", "cidade_destino", "uf_destino", "final_destination", "destination", "recinto_destino", "planta_destino"],
    "consignatario": ["consignatario", "importador", "consignee", "comprador", "empresa_importadora"],
    "armador": ["armador", "carrier", "shipping_line", "transportador_maritimo"],
    "tipo_conteiner": ["tipo_conteiner", "container_type", "equipamento", "tipo_equipamento"],
    "free_time_dias": ["free_time", "free_time_dias", "freetime", "dias_free_time", "demurrage_free_time"],
    "observacoes": ["observacoes", "obs", "notes", "comentarios"]
}


def _normalizar_chave(chave: str) -> str:
    """Remove acentos, espaços e caracteres especiais para comparação flexível."""
    chave_limpa = chave.strip().lower()
    chave_limpa = re.sub(r"[áàãâä]", "a", chave_limpa)
    chave_limpa = re.sub(r"[éèêë]", "e", chave_limpa)
    chave_limpa = re.sub(r"[íìîï]", "i", chave_limpa)
    chave_limpa = re.sub(r"[óòõôö]", "o", chave_limpa)
    chave_limpa = re.sub(r"[úùûü]", "u", chave_limpa)
    chave_limpa = re.sub(r"[ç]", "c", chave_limpa)
    chave_limpa = re.sub(r"[^\w\s]", "_", chave_limpa)
    return re.sub(r"\s+", "_", chave_limpa).strip("_")


def _converter_float(valor: Any, default: float = 0.0) -> float:
    """Converte números textuais brasileiros (1.234,56) ou internacionais (1,234.56)."""
    if valor is None:
        return default
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return default
    s = s.replace("US$", "").replace("R$", "").replace("$", "").replace("kg", "").replace("KG", "").strip()
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


def normalizar_registro_planilha(row: Dict[str, Any]) -> Dict[str, Any]:
    """Mapeia as colunas de uma linha para o dicionário canônico de ItemPlanilhaAduaneira."""
    row_norm = {_normalizar_chave(k): v for k, v in row.items()}
    dados_finais: Dict[str, Any] = {}

    for campo_padrao, sinonimos in MAPA_COLUNAS.items():
        for sin in sinonimos:
            sin_norm = _normalizar_chave(sin)
            if sin_norm in row_norm:
                dados_finais[campo_padrao] = row_norm[sin_norm]
                break

    # Trata atributos declarados (qualquer coluna iniciando em att_ ou atributo_)
    atributos: Dict[str, str] = {}
    for k, v in row_norm.items():
        if (k.startswith("att_") or k.startswith("atributo_")) and v is not None and str(v).strip():
            codigo_att = k.upper().replace("ATRIBUTO_", "ATT_")
            atributos[codigo_att] = str(v).strip()
    dados_finais["atributos_declarados"] = atributos

    return dados_finais


def parsear_csv_planilha(conteudo_ou_caminho: Union[str, Path]) -> List[ItemPlanilhaAduaneira]:
    """Lê CSV de arquivo ou string de texto com auto-detecção de delimitador (, ou ;)."""
    if isinstance(conteudo_ou_caminho, Path) or (isinstance(conteudo_ou_caminho, str) and "\n" not in conteudo_ou_caminho and Path(conteudo_ou_caminho).is_file()):
        caminho = Path(conteudo_ou_caminho)
        texto = caminho.read_text(encoding="utf-8-sig")
    else:
        texto = str(conteudo_ou_caminho)

    primeira_linha = texto.splitlines()[0] if texto.splitlines() else ""
    delimitador = ";" if ";" in primeira_linha and primeira_linha.count(";") > primeira_linha.count(",") else ","

    f = io.StringIO(texto)
    reader = csv.DictReader(f, delimiter=delimitador)

    itens: List[ItemPlanilhaAduaneira] = []
    for row in reader:
        norm = normalizar_registro_planilha(row)
        ncm = str(norm.get("ncm", "0000.00.00")).strip()
        descricao = str(norm.get("descricao", "Mercadoria não especificada")).strip()

        qtd = _converter_float(norm.get("quantidade"), 1.0)
        v_unit = _converter_float(norm.get("valor_unitario_usd"), 0.0)
        v_tot = _converter_float(norm.get("valor_total_usd"), 0.0)
        if v_tot == 0.0 and v_unit > 0.0 and qtd > 0.0:
            v_tot = v_unit * qtd

        p_liq = _converter_float(norm.get("peso_liquido_kg"), None) if norm.get("peso_liquido_kg") is not None else None
        p_bl = _converter_float(norm.get("peso_bruto_bl_kg"), None) if norm.get("peso_bruto_bl_kg") is not None else None
        p_pl = _converter_float(norm.get("peso_bruto_packing_kg"), None) if norm.get("peso_bruto_packing_kg") is not None else None

        free_time_raw = norm.get("free_time_dias")
        free_time = int(_converter_float(free_time_raw, 5.0)) if free_time_raw is not None else 5

        item = ItemPlanilhaAduaneira(
            ncm=ncm,
            descricao=descricao,
            quantidade=qtd,
            unidade_medida=str(norm.get("unidade_medida", "UN")).strip(),
            valor_unitario_usd=v_unit,
            valor_total_usd=v_tot,
            peso_liquido_kg=p_liq,
            peso_bruto_bl_kg=p_bl,
            peso_bruto_packing_kg=p_pl,
            incoterm=str(norm.get("incoterm", "FOB")).strip().upper(),
            porto_descarga=str(norm.get("porto_descarga", "Santos")).strip(),
            origem=str(norm.get("origem")).strip() if norm.get("origem") else None,
            porto_embarque=str(norm.get("porto_embarque")).strip() if norm.get("porto_embarque") else None,
            destino_final=str(norm.get("destino_final")).strip() if norm.get("destino_final") else None,
            consignatario=str(norm.get("consignatario")).strip() if norm.get("consignatario") else None,
            armador=str(norm.get("armador")).strip() if norm.get("armador") else None,
            tipo_conteiner=str(norm.get("tipo_conteiner", "40HC")).strip(),
            free_time_dias=free_time,
            atributos_declarados=norm.get("atributos_declarados", {}),
            observacoes=str(norm.get("observacoes")).strip() if norm.get("observacoes") else None
        )
        itens.append(item)

    return itens


def consolidar_operacao_de_planilha(itens: List[ItemPlanilhaAduaneira]) -> Tuple[OperacaoExtraida, List[str]]:
    """Consolida uma lista de itens em uma OperacaoExtraida com divergências documentais pré-auditadas."""
    if not itens:
        raise ValueError("A planilha não contém itens válidos para processamento.")

    primeiro = itens[0]
    ncm_principal = primeiro.ncm
    descricao_principal = primeiro.descricao
    porto_descarga = primeiro.porto_descarga or "Santos"
    armador = primeiro.armador or "Maersk"
    tipo_conteiner = primeiro.tipo_conteiner or "40HC"

    valor_total_usd = sum(item.valor_total_usd for item in itens)
    qtd_conteineres = max(1, len(set(getattr(item, "tipo_conteiner", "40HC") for item in itens)))

    # Extrai procedencia real e destino final
    origem_resolvida = primeiro.origem or primeiro.porto_embarque or "Origem Internacional"
    porto_embarque = primeiro.porto_embarque or (primeiro.origem if primeiro.origem else None)
    destino_final = primeiro.destino_final or primeiro.consignatario or "Destino Nacional"
    porto_fmt = "Santos/SP" if "santos" in porto_descarga.lower() else porto_descarga
    rota_formatada = f"{origem_resolvida} → {porto_fmt} → {destino_final}"

    divergencias: List[str] = []

    # Auditoria cruzada de pesos em cada item
    for idx, item in enumerate(itens, 1):
        if item.peso_bruto_bl_kg is not None and item.peso_bruto_packing_kg is not None:
            dif_peso = abs(item.peso_bruto_bl_kg - item.peso_bruto_packing_kg)
            if dif_peso > 0.01:
                divergencias.append(
                    f"Divergência de peso bruto no item {idx} ({item.descricao}): "
                    f"BL indica {item.peso_bruto_bl_kg:,.1f} kg, enquanto o Packing List indica {item.peso_bruto_packing_kg:,.1f} kg "
                    f"(diferença de {dif_peso:,.1f} kg)."
                )

        # Divergência de Incoterm
        if item.incoterm and item.incoterm not in ("FOB", "CIF", "CFR", "EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP"):
            divergencias.append(f"Incoterm irregular ou não homologado no item {idx}: '{item.incoterm}'")

    op = OperacaoExtraida(
        ncm=ncm_principal,
        descricao=descricao_principal if len(itens) == 1 else f"{descricao_principal} (+ {len(itens) - 1} itens adicionais)",
        valor_lote_usd=round(valor_total_usd, 2),
        qtd_conteineres=qtd_conteineres,
        tipo_conteiner=tipo_conteiner,
        incoterm=primeiro.incoterm or "FOB",
        porto_embarque=porto_embarque,
        porto_descarga=porto_descarga,
        armador=armador,
        origem=origem_resolvida,
        destino_final=destino_final,
        rota_completa=rota_formatada,
        divergencias=divergencias
    )

    return op, divergencias
