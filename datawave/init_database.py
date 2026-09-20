import sqlite3

def criar_banco():
    conn = sqlite3.connect("datawave.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS importadores (
        cnpj TEXT PRIMARY KEY,
        razao_social TEXT NOT NULL,
        perfil_oea TEXT NOT NULL,
        score_conformidade INTEGER,
        frequencia TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS armadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        free_time_dias INTEGER,
        demurrage_usd REAL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operacoes (
        duimp TEXT PRIMARY KEY,
        importador_cnpj TEXT,
        armador_id INTEGER,
        ncm TEXT NOT NULL,
        mercadoria TEXT NOT NULL,
        fob_usd REAL,
        origem TEXT,
        destino TEXT,
        anuentes TEXT,
        atributo_ausente TEXT,
        dwell_time_cais REAL,
        custo_armazenagem_cais REAL,
        custo_remocao_retro REAL,
        custo_pacote_retro REAL,
        FOREIGN KEY (importador_cnpj) REFERENCES importadores(cnpj),
        FOREIGN KEY (armador_id) REFERENCES armadores(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria_ia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        duimp TEXT UNIQUE,
        score_risco REAL,
        nivel_risco TEXT,
        custo_total_cais REAL,
        custo_total_retro REAL,
        economia_liquida REAL,
        recomendacao TEXT,
        FOREIGN KEY (duimp) REFERENCES operacoes(duimp)
    );
    """)

    cursor.execute("DELETE FROM auditoria_ia;")
    cursor.execute("DELETE FROM operacoes;")
    cursor.execute("DELETE FROM armadores;")
    cursor.execute("DELETE FROM importadores;")

    cursor.executemany("INSERT INTO importadores VALUES (?, ?, ?, ?, ?);", [
        ("12.345.678/0001-90", "AgroQuímica do Brasil Ltda", "Não-OEA (Comum)", 58, "Recorrente"),
        ("23.456.789/0001-01", "AutoPeças Paulínia S/A", "Não-OEA (Comum)", 72, "Recorrente"),
        ("34.567.890/0001-12", "PharmaLife Biotecnologia Ltda", "Não-OEA (Comum)", 64, "Esporádico"),
        ("45.678.901/0001-23", "BraskPolímeros do Brasil S/A", "OEA-C Nível 2", 98, "Recorrente"),
        ("56.789.012/0001-34", "Adega & Empório Tejo Brasil Ltda", "Não-OEA (Comum)", 68, "Recorrente")
    ])

    cursor.executemany("INSERT INTO armadores (id, nome, free_time_dias, demurrage_usd) VALUES (?, ?, ?, ?);", [
        (1, "MSC", 5, 150.0),
        (2, "Hapag-Lloyd", 7, 180.0),
        (3, "Maersk", 5, 350.0),
        (4, "ONE", 10, 120.0),
        (5, "CMA CGM", 7, 160.0)
    ])

    cursor.executemany("INSERT INTO operacoes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", [
        ("26BR000192834-1", "12.345.678/0001-90", 1, "38089329", "Herbicidas Defensivos Agrícolas", 128500.0, "China", "Anápolis/GO", "MAPA, ANVISA", "A01-RegistroAptidao", 10.0, 4500.0, 1000.0, 1200.0),
        ("26BR000284719-5", "23.456.789/0001-01", 2, "87084080", "Caixas de Marcha Automotivas", 85400.0, "Alemanha", "Sorocaba/SP", "INMETRO", "ATT_NIMF15_MADEIRA", 9.0, 4500.0, 950.0, 1450.0),
        ("26BR000391823-9", "34.567.890/0001-12", 3, "29331990", "Insumos Farmacêuticos Reefer (2°C-8°C)", 420000.0, "Índia", "Paulínia/SP", "ANVISA", "NENHUM", 12.0, 4475.0, 1800.0, 3000.0),
        ("26BR000419283-0", "45.678.901/0001-23", 4, "39011010", "Polímeros e Resinas Termoplásticas", 63000.0, "EUA", "Piracicaba/SP", "NENHUM", "NENHUM", 1.5, 1200.0, 900.0, 1200.0),
        ("26BR000582910-8", "56.789.012/0001-34", 5, "22042100", "Vinhos Finos Casal Branco DOC Tejo", 54200.0, "Portugal", "São Paulo/SP", "MAPA (Vigiagro)", "ATT_14240-CertificadoEnologico", 11.0, 4500.0, 1100.0, 1200.0)
    ])

    cursor.executemany("INSERT INTO auditoria_ia (duimp, score_risco, nivel_risco, custo_total_cais, custo_total_retro, economia_liquida, recomendacao) VALUES (?, ?, ?, ?, ?, ?, ?);", [
        ("26BR000192834-1", 82.0, "CRÍTICO", 8625.0, 2200.0, 6425.0, "Cenário C (Retroporto / Porto Seco)"),
        ("26BR000284719-5", 65.0, "ALTO", 6480.0, 2400.0, 4080.0, "Cenário C (Retroporto / Porto Seco)"),
        ("26BR000391823-9", 78.0, "CRÍTICO", 17950.0, 4800.0, 13150.0, "Cenário C (Retroporto / Porto Seco)"),
        ("26BR000419283-0", 5.0, "BAIXO", 1200.0, 2100.0, -900.0, "Cenário A (Despacho sobre Águas / Cais)"),
        ("26BR000582910-8", 74.0, "ALTO", 8020.0, 2300.0, 5720.0, "Cenário C (Retroporto / Porto Seco)")
    ])

    conn.commit()
    conn.close()
    print("Banco de dados SQLite 'datawave.db' atualizado com 5 cenários com sucesso!")

if __name__ == "__main__":
    criar_banco()
