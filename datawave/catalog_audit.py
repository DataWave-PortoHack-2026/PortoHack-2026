"""Auditoria e padronização determinísticas do Catálogo de Produtos (módulo A).

Regras vêm 100% de catalog_rules.json (gerado por build_rules.py a partir da
planilha DUIMP). Nenhum LLM aqui: mesmo input -> mesmo resultado.

Formato do produto (chaves em snake_case; ver tests/fixtures/casal_branco.json):
    codigo, denominacao, descricao, ncm, modalidade,
    atributos:                [{"atributo": "ATT_x", "valor": "..."}]
    atributos_multivalorados: [{"atributo": "ATT_x", "valores": ["...", "..."]}]

Especificação do Portal Único adotada (informada pelo usuário):
    - modalidade: exatamente IMPORTACAO ou EXPORTACAO (maiúsculas, sem acento)
    - atributosMultivalorados: array de {atributo, valores: [strings]}

Severidades:
    ERROR    bloqueia (obrigatório ausente, valor fora da lista, GTIN inválido...)
    WARNING  higiene/padronização (opcional vazio, espaços, formato de multivalorado)
    INFO     sem cobertura de regra para a NCM

Status / semáforo:
    BLOQUEADO (vermelho) | COM_ALERTAS (amarelo) | APROVADO (verde) | SEM_COBERTURA (cinza)
"""
from __future__ import annotations

import copy
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field

MODALIDADES = {"IMPORTACAO", "EXPORTACAO"}
GTIN_LENGTH = {"01": 8, "02": 12, "03": 13}  # ATT "Tipo do GTIN": 01=GTIN-8, 02=GTIN-12, 03=GTIN-13
SEMAFORO = {"BLOQUEADO": "vermelho", "COM_ALERTAS": "amarelo", "APROVADO": "verde", "SEM_COBERTURA": "cinza"}


@dataclass
class Finding:
    severity: str
    code: str
    attribute: str | None
    message: str


@dataclass
class AuditResult:
    codigo: str
    ncm: str
    status: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def semaforo(self) -> str:
        return SEMAFORO[self.status]

    def errors(self):
        return [f for f in self.findings if f.severity == "ERROR"]

    def to_dict(self):
        d = asdict(self)
        d["semaforo"] = self.semaforo
        return d


def load_rules(path: str = "catalog_rules.json") -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def norm_ncm(ncm: str) -> str:
    digits = re.sub(r"\D", "", str(ncm or ""))
    return f"{digits[:4]}.{digits[4:6]}.{digits[6:8]}" if len(digits) == 8 else str(ncm or "").strip()


def norm_modalidade(raw) -> str:
    """'importação ' -> 'IMPORTACAO' (forma canônica esperada pelo Portal Único)."""
    s = unicodedata.normalize("NFKD", str(raw or "")).encode("ascii", "ignore").decode()
    return s.strip().upper()


def gtin_valid(code: str) -> bool:
    """Dígito verificador GS1 (módulo 10) para GTIN-8/12/13/14."""
    if not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    body, check = list(map(int, code[:-1])), int(code[-1])
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def _as_list(raw):
    if raw in (None, "", []):
        return []
    return json.loads(raw) if isinstance(raw, str) else raw


def _read_values(product: dict, add):
    """Devolve (single, multi): {ATT: valor} e {ATT: [valores]}."""
    single = {}
    for item in _as_list(product.get("atributos")):
        single[item["atributo"]] = "" if item.get("valor") is None else str(item["valor"])
    multi = {}
    for item in _as_list(product.get("atributos_multivalorados")):
        att = item.get("atributo")
        if isinstance(item.get("valores"), list):
            multi[att] = [str(v) for v in item["valores"]]
        elif "valor" in item:  # formato fora da especificação: aceita, mas avisa
            v = item["valor"]
            multi[att] = [str(x) for x in (v if isinstance(v, list) else [v])]
            add("WARNING", "FORMATO_MULTIVALORADO", att, "Multivalorado deve usar 'valores' (array de strings), não 'valor'.")
        else:
            add("ERROR", "FORMATO_MULTIVALORADO", att, "Item multivalorado sem 'valores' (array de strings).")
            multi[att] = []
    return single, multi


def _cond_ok(when: dict | None, parent_value: str | None) -> bool:
    if when is None:
        return True
    if parent_value in (None, ""):
        return False
    inside = parent_value in when["values"]
    return inside if when["op"] == "in" else not inside


def audit_product(product: dict, rules: dict) -> AuditResult:
    codigo = product.get("codigo", "?")
    ncm = norm_ncm(product.get("ncm"))
    F: list[Finding] = []

    def add(sev, code, attr, msg):
        F.append(Finding(sev, code, attr, msg))

    # --- cabeçalho do produto ------------------------------------------------
    den = str(product.get("denominacao") or "")
    if den != den.strip() or "  " in den:
        add("WARNING", "ESPACOS_DENOMINACAO", None, f"Denominação com espaços sobrando: {den!r}")
    mod_raw = str(product.get("modalidade") or "")
    if mod_raw not in MODALIDADES:
        canon = norm_modalidade(mod_raw)
        if canon in MODALIDADES:
            add("ERROR", "MODALIDADE_GRAFIA", None, f"Modalidade {mod_raw!r} fora da grafia esperada; use {canon!r}.")
        else:
            add("ERROR", "MODALIDADE_INVALIDA", None, f"Modalidade não reconhecida: {mod_raw!r} (esperado IMPORTACAO ou EXPORTACAO).")

    sid = rules["ncms"].get(ncm)
    if sid is None:
        add("INFO", "SEM_COBERTURA", None, f"NCM {ncm} sem regras na base de atributos; auditoria de atributos não executada.")
        return AuditResult(codigo, ncm, "BLOQUEADO" if any(f.severity == "ERROR" for f in F) else "SEM_COBERTURA", F)

    schema = rules["schemas"][sid]
    single, multi = _read_values(product, add)

    def value_of(att):
        return single.get(att, "") or ""

    def has_value(att):
        return bool(value_of(att).strip()) or any(v.strip() for v in multi.get(att, []))

    # --- aplicabilidade (árvore de condições) -------------------------------
    memo: dict[str, bool] = {}

    def applicable(att: str, seen=()) -> bool:
        if att in memo:
            return memo[att]
        spec = schema[att]
        parent = spec["parent"]
        if parent is None:
            res = True
        elif parent in seen or parent not in schema:
            res = False
        else:
            res = applicable(parent, seen + (att,)) and _cond_ok(spec["when"], value_of(parent) or None)
        memo[att] = res
        return res

    for att in single.keys() | multi.keys():
        if att not in schema:
            add("ERROR", "ATRIBUTO_INEXISTENTE", att, f"{att} não existe no esquema da NCM {ncm}.")
    for att in single:
        if att in schema and schema[att]["multi"]:
            add("ERROR", "ATRIBUTO_COLUNA_ERRADA", att, f"'{schema[att]['name']}' é multivalorado: informe em atributosMultivalorados com 'valores'.")
    for att in multi:
        if att in schema and not schema[att]["multi"]:
            add("ERROR", "ATRIBUTO_COLUNA_ERRADA", att, f"'{schema[att]['name']}' não é multivalorado: informe em atributos com 'valor'.")

    for att, spec in schema.items():
        ap = applicable(att)
        provided = att in single or att in multi
        if ap and spec["required"] and not has_value(att):
            parent = f" (exigido porque {spec['parent']} {spec['when']['op']} {spec['when']['values']})" if spec["parent"] else ""
            add("ERROR", "OBRIGATORIO_AUSENTE", att, f"Falta '{spec['name']}'{parent}.")
        if not ap and has_value(att):
            add("WARNING", "NAO_APLICAVEL", att, f"'{spec['name']}' informado, mas as condições da árvore não o exigem para este produto.")
        if ap and provided and not has_value(att) and not spec["required"]:
            add("WARNING", "OPCIONAL_VAZIO", att, f"'{spec['name']}' enviado vazio; omita o atributo.")

    # --- validação de valores -----------------------------------------------
    all_vals = {a: [v] for a, v in single.items() if v.strip()}
    for a, vs in multi.items():
        all_vals.setdefault(a, []).extend(v for v in vs if v.strip())
    for att, vals in all_vals.items():
        spec = schema.get(att)
        if spec is None:
            continue
        for v in vals:
            if v != v.strip():
                add("WARNING", "ESPACOS_VALOR", att, f"'{spec['name']}' com espaços nas pontas: {v!r}")
            if spec["type"] in ("LISTA_ESTATICA", "BOOLEANO") and spec["options"] and v not in spec["options"]:
                add("ERROR", "VALOR_FORA_DA_LISTA", att, f"'{spec['name']}': {v!r} não está entre as opções válidas.")
            if spec["type"] == "NUMERO_REAL":
                try:
                    float(v.replace(",", "."))
                except ValueError:
                    add("ERROR", "NUMERO_INVALIDO", att, f"'{spec['name']}': {v!r} não é numérico.")
            if spec["max_len"] and len(v) > spec["max_len"]:
                add("ERROR", "EXCEDE_TAMANHO", att, f"'{spec['name']}': {len(v)} caracteres (máx. {spec['max_len']}).")
            if spec.get("semantic") == "gtin_code":
                tipo = value_of(spec["gtin_type_attr"])
                want = GTIN_LENGTH.get(tipo)
                if want and len(v) != want:
                    add("ERROR", "GTIN_TAMANHO", att, f"GTIN de tipo {tipo} deve ter {want} dígitos; veio {len(v)}.")
                elif not gtin_valid(v):
                    add("ERROR", "GTIN_DIGITO_VERIFICADOR", att, f"GTIN {v} com dígito verificador inválido.")
            if spec.get("semantic") == "denominacao_legal" and den.strip() and not v.startswith(den.strip()):
                add("WARNING", "DENOMINACAO_LEGAL_DIVERGE", att, "Denominação conforme legislação não começa com a Denominação do produto (convenção observada na planilha).")

    status = "BLOQUEADO" if any(f.severity == "ERROR" for f in F) else ("COM_ALERTAS" if F else "APROVADO")
    return AuditResult(codigo, ncm, status, F)


def audit_batch(products: list[dict], rules: dict) -> dict:
    """Audita um lote e acrescenta checagens entre produtos (hoje: código duplicado)."""
    results = [audit_product(p, rules) for p in products]
    batch_findings, seen = [], {}
    for p in products:
        c = p.get("codigo")
        seen[c] = seen.get(c, 0) + 1
    for c, n in seen.items():
        if n > 1:
            batch_findings.append(Finding("ERROR", "CODIGO_DUPLICADO", None, f"Código {c!r} aparece {n} vezes no lote."))
    return {"results": results, "batch_findings": batch_findings}


def padronizar(product: dict, rules: dict) -> tuple[dict, list[str]]:
    """Aplica correções mecânicas e seguras; devolve (produto_novo, lista_de_alterações).

    Não inventa valores: só normaliza grafia/espaços, omite opcionais vazios e move
    atributos para a coluna correta (atributos x atributosMultivalorados).
    """
    p = copy.deepcopy(product)
    changes: list[str] = []
    sid = rules["ncms"].get(norm_ncm(p.get("ncm")))
    schema = rules["schemas"].get(sid, {}) if sid else {}

    def clean(text):
        return re.sub(r"\s+", " ", str(text)).strip()

    for key in ("denominacao", "descricao"):
        if p.get(key) is not None and clean(p[key]) != p[key]:
            changes.append(f"{key}: espaços normalizados")
            p[key] = clean(p[key])
    canon = norm_modalidade(p.get("modalidade"))
    if canon in MODALIDADES and canon != p.get("modalidade"):
        changes.append(f"modalidade: {p.get('modalidade')!r} -> {canon!r}")
        p["modalidade"] = canon
    if p.get("ncm") and norm_ncm(p["ncm"]) != p["ncm"]:
        changes.append(f"ncm: {p['ncm']!r} -> {norm_ncm(p['ncm'])!r}")
        p["ncm"] = norm_ncm(p["ncm"])

    single, multi = _read_values(p, lambda *a: None)
    new_single, new_multi = [], []
    for att, v in single.items():
        spec = schema.get(att)
        v2 = v.strip()
        if v2 != v:
            changes.append(f"{att}: espaços nas pontas removidos")
        if spec and not v2 and not spec["required"]:
            changes.append(f"{att}: opcional vazio omitido")
            continue
        if spec and spec["multi"]:
            changes.append(f"{att}: movido para atributosMultivalorados")
            multi.setdefault(att, []).append(v2)
            continue
        new_single.append({"atributo": att, "valor": v2})
    for att, vals in multi.items():
        spec = schema.get(att)
        vals2 = [x.strip() for x in vals if x.strip()]
        if spec and not spec["multi"]:
            if len(vals2) == 1:
                changes.append(f"{att}: movido para atributos")
                new_single.append({"atributo": att, "valor": vals2[0]})
                continue
        if not vals2 and spec and not spec["required"]:
            changes.append(f"{att}: multivalorado vazio omitido")
            continue
        new_multi.append({"atributo": att, "valores": vals2})
    p["atributos"], p["atributos_multivalorados"] = new_single, new_multi
    return p, changes
