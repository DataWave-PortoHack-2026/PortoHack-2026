import copy
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from catalog_audit import audit_batch, audit_product, gtin_valid, load_rules, padronizar
RULES = load_rules(str(HERE.parent / "catalog_rules.json"))
BASE = json.loads((HERE / "fixtures" / "casal_branco.json").read_text(encoding="utf-8"))
SCHEMA = next(iter(RULES["schemas"].values()))


def product(i=0, **changes):
    p = copy.deepcopy(BASE[i])
    p.update(changes)
    return p


def set_attr(p, att, value):
    for a in p["atributos"]:
        if a["atributo"] == att:
            a["valor"] = value
            return p
    p["atributos"].append({"atributo": att, "valor": value})
    return p


def drop_attr(p, att):
    p["atributos"] = [a for a in p["atributos"] if a["atributo"] != att]
    return p


def codes(res):
    return {f.code for f in res.findings}


def error_codes(res):
    return {f.code for f in res.errors()}


def opt(att, n):
    return list(SCHEMA[att]["options"])[n]


# ------------------------------------------------------------ baseline real (planilha)
def test_baseline_bruto_planilha():
    r0 = audit_product(BASE[0], RULES)
    assert not r0.errors() and r0.status == "COM_ALERTAS"          # só Safra vazia
    for i in (1, 2, 3):                                             # 'IMPORTAÇÃO' com acento
        r = audit_product(BASE[i], RULES)
        assert error_codes(r) == {"MODALIDADE_GRAFIA"}, (BASE[i]["codigo"], r.findings)
        assert r.status == "BLOQUEADO" and r.semaforo == "vermelho"


def test_baseline_alertas_de_higiene_conhecidos():
    assert "OPCIONAL_VAZIO" in codes(audit_product(BASE[0], RULES))       # Safra vazia
    assert "ESPACOS_DENOMINACAO" in codes(audit_product(BASE[1], RULES))  # espaço sobrando


def test_padronizar_aprova_os_quatro_vinhos():
    for p in BASE:
        novo, changes = padronizar(p, RULES)
        res = audit_product(novo, RULES)
        assert res.status == "APROVADO" and res.semaforo == "verde", (p["codigo"], res.findings)
        assert changes  # todos tinham ao menos a Safra vazia


def test_padronizar_nao_muta_entrada_e_e_idempotente():
    original = copy.deepcopy(BASE[1])
    novo, changes = padronizar(BASE[1], RULES)
    assert BASE[1] == original
    assert any("modalidade" in c for c in changes) and any("espaços" in c for c in changes)
    novo2, changes2 = padronizar(novo, RULES)
    assert changes2 == [] and novo2 == novo


# ------------------------------------------------------------ Modalidade
def test_modalidade_canonica_ok():
    assert "MODALIDADE_GRAFIA" not in codes(audit_product(product(0, modalidade="IMPORTACAO"), RULES))
    assert "MODALIDADE_GRAFIA" not in codes(audit_product(product(0, modalidade="EXPORTACAO"), RULES))


@pytest.mark.parametrize("raw", ["Importação", "importacao", "IMPORTAÇÃO", "IMPORTACAO "])
def test_modalidade_grafia_errada(raw):
    assert "MODALIDADE_GRAFIA" in error_codes(audit_product(product(0, modalidade=raw), RULES))


def test_modalidade_invalida():
    assert "MODALIDADE_INVALIDA" in error_codes(audit_product(product(0, modalidade="TRANSITO"), RULES))


# ------------------------------------------------------------ erros injetados
def test_obrigatorio_ausente():
    p = drop_attr(product(0), "ATT_14245")  # Teor de açúcar
    res = audit_product(p, RULES)
    assert res.status == "BLOQUEADO"
    assert any(f.code == "OBRIGATORIO_AUSENTE" and f.attribute == "ATT_14245" for f in res.findings)


def test_valor_fora_da_lista():
    assert "VALOR_FORA_DA_LISTA" in codes(audit_product(set_attr(product(0), "ATT_14251", "99"), RULES))  # Cor


def test_lista_longa_vem_da_aba_listas():
    assert "VALOR_FORA_DA_LISTA" in codes(audit_product(set_attr(product(0), "ATT_14233", "9999"), RULES))


def test_gtin_digito_verificador():
    good = "5602424800010"
    assert gtin_valid(good)
    assert "GTIN_DIGITO_VERIFICADOR" in codes(audit_product(set_attr(product(0), "ATT_14262", good[:-1] + "9"), RULES))


def test_gtin_tamanho_conforme_tipo():
    assert "GTIN_TAMANHO" in codes(audit_product(set_attr(product(0), "ATT_14262", "56024248"), RULES))


def test_excede_tamanho_maximo():
    p = set_attr(product(0), "ATT_14211", product(0)["denominacao"] + " - " + "X" * 200)
    assert "EXCEDE_TAMANHO" in codes(audit_product(p, RULES))


def test_muda_area_tematica_ativa_outro_ramo_da_arvore():
    res = audit_product(set_attr(product(0), "ATT_14200", "01"), RULES)  # Agrotóxico
    assert res.status == "BLOQUEADO"
    assert "NAO_APLICAVEL" in codes(res)
    assert any(f.code == "OBRIGATORIO_AUSENTE" and f.attribute == "ATT_14217" for f in res.findings)


def test_atributo_inexistente():
    assert "ATRIBUTO_INEXISTENTE" in codes(audit_product(set_attr(product(0), "ATT_99999", "x"), RULES))


def test_denominacao_legal_diverge():
    assert "DENOMINACAO_LEGAL_DIVERGE" in codes(audit_product(set_attr(product(0), "ATT_14211", "OUTRA COISA - 750ML"), RULES))


# ------------------------------------------------------------ multivalorados (spec: {atributo, valores[]})
def agro(**extra):
    """Ramo Agrotóxico: ATT_14200=01, ATT_14224=01 habilitam ATT_14225 (multivalorado)."""
    p = product(0)
    set_attr(p, "ATT_14200", "01")
    set_attr(p, "ATT_14224", "01")
    p.update(extra)
    return p


def test_multivalorado_valido():
    p = agro(atributos_multivalorados=[{"atributo": "ATT_14225", "valores": [opt("ATT_14225", 0), opt("ATT_14225", 1)]}])
    res = audit_product(p, RULES)
    assert not any(f.attribute == "ATT_14225" and f.severity == "ERROR" for f in res.findings)
    assert not any(f.code == "OBRIGATORIO_AUSENTE" and f.attribute == "ATT_14225" for f in res.findings)


def test_multivalorado_valor_fora_da_lista():
    p = agro(atributos_multivalorados=[{"atributo": "ATT_14225", "valores": [opt("ATT_14225", 0), "ZZZ"]}])
    assert any(f.code == "VALOR_FORA_DA_LISTA" and f.attribute == "ATT_14225" for f in audit_product(p, RULES).findings)


def test_multivalorado_na_coluna_errada():
    p = set_attr(agro(), "ATT_14225", opt("ATT_14225", 0))  # multivalorado dentro de 'atributos'
    assert any(f.code == "ATRIBUTO_COLUNA_ERRADA" and f.attribute == "ATT_14225" for f in audit_product(p, RULES).findings)


def test_simples_na_coluna_de_multivalorados():
    p = product(0, atributos_multivalorados=[{"atributo": "ATT_14251", "valores": ["02"]}])
    assert "ATRIBUTO_COLUNA_ERRADA" in codes(audit_product(p, RULES))


def test_multivalorado_com_chave_valor_gera_aviso_de_formato():
    p = agro(atributos_multivalorados=[{"atributo": "ATT_14225", "valor": opt("ATT_14225", 0)}])
    assert any(f.code == "FORMATO_MULTIVALORADO" and f.severity == "WARNING" for f in audit_product(p, RULES).findings)


def test_padronizar_move_atributo_para_a_coluna_correta():
    p = set_attr(agro(), "ATT_14225", opt("ATT_14225", 0))
    novo, changes = padronizar(p, RULES)
    assert any("movido para atributosMultivalorados" in c for c in changes)
    assert {"atributo": "ATT_14225", "valores": [opt("ATT_14225", 0)]} in novo["atributos_multivalorados"]
    assert not any(a["atributo"] == "ATT_14225" for a in novo["atributos"])


# ------------------------------------------------------------ cobertura e lote
def test_ncm_sem_cobertura():
    res = audit_product(product(0, ncm="8517.13.00"), RULES)
    assert res.status == "SEM_COBERTURA" and res.semaforo == "cinza"
    assert "SEM_COBERTURA" in codes(res)


def test_ncm_aceita_formato_sem_pontos():
    assert audit_product(product(0, ncm="22042100"), RULES).status != "SEM_COBERTURA"


@pytest.mark.parametrize("ncm", ["2204.21.00", "2204.22.11", "2204.10.90"])
def test_tres_ncms_cobertas(ncm):
    assert audit_product(product(0, ncm=ncm), RULES).status != "SEM_COBERTURA"


def test_lote_com_codigo_duplicado():
    out = audit_batch([BASE[0], BASE[0]], RULES)
    assert [f.code for f in out["batch_findings"]] == ["CODIGO_DUPLICADO"]
    assert audit_batch(BASE, RULES)["batch_findings"] == []
