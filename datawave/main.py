from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI(title="Datawave AI Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect("datawave.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/operacoes")
def listar_operacoes():
    conn = get_db()
    cursor = conn.cursor()
    query = """
    SELECT 
        o.duimp, o.ncm, o.mercadoria, o.fob_usd, o.origem, o.destino,
        o.anuentes, o.atributo_ausente, o.dwell_time_cais,
        i.razao_social, i.perfil_oea, i.score_conformidade,
        a.nome AS armador, a.free_time_dias, a.demurrage_usd,
        ia.score_risco, ia.nivel_risco, ia.custo_total_cais, 
        ia.custo_total_retro, ia.economia_liquida, ia.recomendacao
    FROM operacoes o
    JOIN importadores i ON o.importador_cnpj = i.cnpj
    JOIN armadores a ON o.armador_id = a.id
    JOIN auditoria_ia ia ON o.duimp = ia.duimp;
    """
    rows = cursor.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
