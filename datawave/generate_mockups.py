import json
import random

CAMBIO = 5.50
TEMPLATES = [
    {"ncm": "38089329", "desc": "Defensivos Agrícolas", "cais_dias": 10, "free": 5, "dem_usd": 150, "cais_arm": 4500, "remocao": 1000, "pacote": 1200, "risco": 82},
    {"ncm": "87084080", "desc": "Autopeças & Câmbio", "cais_dias": 9, "free": 7, "dem_usd": 180, "cais_arm": 4500, "remocao": 950, "pacote": 1450, "risco": 65},
    {"ncm": "29331990", "desc": "Insumos Farma Reefer", "cais_dias": 12, "free": 5, "dem_usd": 350, "cais_arm": 4475, "remocao": 1800, "pacote": 3000, "risco": 78},
    {"ncm": "39011010", "desc": "Polímeros e Resinas", "cais_dias": 1.5, "free": 10, "dem_usd": 120, "cais_arm": 1200, "remocao": 900, "pacote": 1200, "risco": 5}
]

def gerar(n=20):
    rows = []
    for i in range(1, n + 1):
        t = random.choice(TEMPLATES)
        dem_brl = max(0, t["cais_dias"] - t["free"]) * t["dem_usd"] * CAMBIO
        total_cais = t["cais_arm"] + dem_brl
        total_retro = t["remocao"] + t["pacote"]
        rows.append({
            "id": f"SIM-{i:04d}",
            "ncm": t["ncm"],
            "descricao": t["desc"],
            "custo_cais_brl": round(total_cais, 2),
            "custo_retroporto_brl": round(total_retro, 2),
            "economia_brl": round(total_cais - total_retro, 2),
            "recomendacao": "Cenário C (Porto Seco)" if total_cais > total_retro else "Cenário A (Cais)"
        })
    return rows

if __name__ == "__main__":
    dados = gerar(50)
    with open("dataset_simulado.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    print("50 registros gerados com sucesso!")
