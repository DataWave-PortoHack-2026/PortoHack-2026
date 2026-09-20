"""
Script de Geracao de Copys Personalizados para LinkedIn - Porto Hack Santos 2026
Equipe DataWave (ABTRA / AmiGU / Fatec Rubens Lara)

Objetivo:
Ler os dados dos contatos da planilha de pesquisa de campo sobre a DUIMP no Porto de Santos,
analisar as informacoes profissionais e operacionais de cada perfil do LinkedIn e gerar um
copy de abordagem personalizado utilizando uma LLM local (Ollama, LM Studio ou qualquer API
compativel com OpenAI).
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# Diretorio base do script para gravacao padrao
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Constantes do Projeto
SPREADSHEET_ID = "1qqUuL_BPBLisC2RY3F49KLiPipvRnM7GCnJi641POes"
DEFAULT_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
FORM_URL = "https://forms.gle/PoAQ17cF3WRFpFXLA"
BASE_COPY = (
    "Olá, {nome}! Sou da Fatec e do Porto Hack 2026 (ABTRA/AmiGU). "
    "Estamos pesquisando os efeitos da DUIMP no Porto de Santos. "
    "Poderia contribuir com uma pesquisa de 3 minutos? {link}"
)

# Exemplos de leads para testes locais e demonstracao imediata
SAMPLE_LEADS = [
    {
        "Nome": "Carlos Eduardo Silveira",
        "Cargo": "Gerente de Desembaraço Aduaneiro",
        "Empresa": "Comissária Marítima Santista",
        "Senioridade": "Gerência",
        "Segmento_Inferido": "Comissária de Despacho",
        "Tamanho da Empresa": "Médio porte",
        "Conexao_Comum": "Giulia Granado",
        "Perfil LinkedIn": "https://www.linkedin.com/in/carlos-silveira-comex",
        "Canal de Abordagem": "LinkedIn Mensagem Direta",
        "Data de Envio": "",
        "Notas / Observações": "Especialista em transição Siscomex para DUIMP e cadastro de Catálogo de Produtos.",
        "Status_Envio": "Pendente",
        "Prioridade": "Alta"
    },
    {
        "Nome": "Mariana Fonseca",
        "Cargo": "Coordenadora de Logística e Armazenagem",
        "Empresa": "Terminal Retroportuário Santos",
        "Senioridade": "Coordenação",
        "Segmento_Inferido": "Terminal Retroportuário",
        "Tamanho da Empresa": "Grande porte",
        "Conexao_Comum": "",
        "Perfil LinkedIn": "https://www.linkedin.com/in/mariana-fonseca-log",
        "Canal de Abordagem": "LinkedIn InMail",
        "Data de Envio": "",
        "Notas / Observações": "Atua diretamente com agendamento de gate e movimentação de contêineres cheios e vazios.",
        "Status_Envio": "Pendente",
        "Prioridade": "Alta"
    },
    {
        "Nome": "Rodrigo Mendes",
        "Cargo": "Diretor de Supply Chain",
        "Empresa": "Importadora Nacional de Eletrônicos",
        "Senioridade": "Diretoria",
        "Segmento_Inferido": "Importador Direto",
        "Tamanho da Empresa": "Grande porte",
        "Conexao_Comum": "Arthur",
        "Perfil LinkedIn": "https://www.linkedin.com/in/rodrigo-mendes-supply",
        "Canal de Abordagem": "LinkedIn Mensagem Direta",
        "Data de Envio": "",
        "Notas / Observações": "Muito focado em fluxo de caixa, custos de armazenagem versus cais e risco de demurrage.",
        "Status_Envio": "Pendente",
        "Prioridade": "Média"
    }
]


def remover_emojis(texto: str) -> str:
    """Garante a remocao total de quaisquer caracteres de emoji no texto gerado."""
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f900-\U0001f9ff"
        "\U0001fa70-\U0001faff"
        "]+",
        flags=re.UNICODE
    )
    limpo = emoji_pattern.sub("", texto)
    return re.sub(r" +", " ", limpo).strip()


def obter_primeiro_nome(nome_completo: str) -> str:
    """Extrai o primeiro nome de forma amigavel para a saudacao."""
    if not nome_completo or not nome_completo.strip():
        return "Colega"
    partes = nome_completo.strip().split()
    return partes[0].capitalize()


def carregar_dados_planilha(fonte: str) -> List[Dict[str, str]]:
    """Carrega registros da URL publica do Google Sheets ou de um arquivo CSV local."""
    conteudo_csv = ""

    if fonte.startswith("http://") or fonte.startswith("https://"):
        url = fonte
        if "edit?usp=sharing" in url or "edit" in url:
            match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
            if match:
                sheet_id = match.group(1)
                url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

        print(f"Baixando dados da planilha online: {url}")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resposta:
                conteudo_csv = resposta.read().decode("utf-8-sig", errors="replace")
        except urllib.error.URLError as erro:
            print(f"Erro ao acessar a planilha remota: {erro}")
            return []
    else:
        print(f"Lendo arquivo CSV local: {fonte}")
        try:
            with open(fonte, "r", encoding="utf-8-sig", errors="replace") as f:
                conteudo_csv = f.read()
        except OSError as erro:
            print(f"Erro ao abrir arquivo local: {erro}")
            return []

    linhas = list(csv.reader(io.StringIO(conteudo_csv)))
    if not linhas:
        print("Planilha vazia ou sem conteudo legivel.")
        return []

    cabecalhos = [c.strip() for c in linhas[0]]
    registros: List[Dict[str, str]] = []

    for linha in linhas[1:]:
        if not any(campo.strip() for campo in linha):
            continue
        dado = {}
        for idx, col in enumerate(cabecalhos):
            valor = linha[idx].strip() if idx < len(linha) else ""
            dado[col] = valor
        registros.append(dado)

    return registros


def construir_prompt_personalizacao(lead: Dict[str, str]) -> str:
    """Monta a instrucao estruturada para a LLM local personalizar a mensagem."""
    nome = lead.get("Nome", "")
    primeiro_nome = obter_primeiro_nome(nome)
    cargo = lead.get("Cargo", "Profissional de Comércio Exterior")
    empresa = lead.get("Empresa", "")
    senioridade = lead.get("Senioridade", "")
    segmento = lead.get("Segmento_Inferido", "")
    conexao = lead.get("Conexao_Comum", "")
    notas = lead.get("Notas / Observações", "")

    instrucao = f"""Você é um pesquisador da equipe DataWave no Porto Hack Santos 2026, representando a Fatec e a iniciativa ABTRA/AmiGU.
Sua missão é adaptar a mensagem de abordagem direta no LinkedIn para o profissional abaixo.

MENSAGEM BASE PADRÃO:
"Olá, {primeiro_nome}! Sou da Fatec e do Porto Hack 2026 (ABTRA/AmiGU). Estamos pesquisando os efeitos da DUIMP no Porto de Santos. Poderia contribuir com uma pesquisa de 3 minutos? {FORM_URL}"

DADOS DO PROFISSIONAL:
- Nome Completo: {nome}
- Primeiro Nome: {primeiro_nome}
- Cargo: {cargo}
- Empresa: {empresa}
- Senioridade: {senioridade}
- Segmento Operacional: {segmento}
- Conexão em Comum: {conexao if conexao else "Nenhuma informada"}
- Observações Específicas: {notas if notas else "Nenhuma"}

DIRETRIZES DE PERSONALIZAÇÃO:
1. Mantenha a essência, concisão e o objetivo da mensagem base. Não a torne longa nem corporativa demais.
2. Tamanho máximo: 3 a 4 frases curtas (ideal para mensagem direta no LinkedIn ou InMail).
3. Adapte uma frase para mostrar por que a perspectiva dele é valiosa (ex: com base no cargo de {cargo}, no segmento de {segmento} ou na empresa {empresa}, mencionando desafios como desembaraço aduaneiro, catálogo de produtos, fluxo de caixa, agendamento de gate ou demurrage).
4. Se houver conexão em comum ({conexao}), mencione de forma breve e natural.
5. O link ({FORM_URL}) e as entidades (Fatec, Porto Hack 2026, ABTRA/AmiGU, DUIMP, Porto de Santos) DEVEM estar presentes.
6. RESTRIÇÃO ABSOLUTA: NÃO UTILIZE EMOJIS EM NENHUMA HIPÓTESE.
7. Retorne APENAS o texto final da mensagem, sem aspas e sem comentários adicionais."""

    return instrucao


def gerar_copy_regras_fallback(lead: Dict[str, str]) -> str:
    """Gera uma versao personalizada de alta qualidade caso a LLM local esteja indisponivel."""
    primeiro_nome = obter_primeiro_nome(lead.get("Nome", ""))
    cargo = lead.get("Cargo", "")
    empresa = lead.get("Empresa", "")
    segmento = lead.get("Segmento_Inferido", "")
    conexao = lead.get("Conexao_Comum", "").strip()

    saudacao = f"Olá, {primeiro_nome}!"
    if conexao:
        saudacao += f" Vi que temos contato em comum com {conexao}."

    frase_contexto = ""
    if any(k in cargo.lower() for k in ["despach", "aduaneir"]) or "comiss" in segmento.lower():
        frase_contexto = (
            "Acompanhando os desafios da transição para a DUIMP e do Catálogo de Produtos "
            "no desembaraço aduaneiro em Santos, sua visão prática na linha de frente é fundamental."
        )
    elif any(k in cargo.lower() for k in ["armazen", "logíst", "terminal", "porto"]) or "terminal" in segmento.lower():
        frase_contexto = (
            "Como sua atuação lida diretamente com os gargalos operacionais, janelas de gate e "
            "movimentação física no Porto de Santos, sua experiência trará um diagnóstico muito rico."
        )
    elif any(k in cargo.lower() for k in ["supply", "diret", "compr", "import"]) or "import" in segmento.lower():
        frase_contexto = (
            "Considerando os impactos da DUIMP no fluxo de caixa, recolhimento de tributos e na "
            "decisão entre cais direto e retroporto, sua perspectiva estratégica é indispensável."
        )
    else:
        frase_contexto = (
            "Estamos mapeando gargalos reais de custos, prazos e processos operacionais com quem "
            "vive o comércio exterior na prática."
        )

    copy = (
        f"{saudacao} Sou da Fatec e da equipe DataWave no Porto Hack Santos 2026 (ABTRA/AmiGU). "
        f"Estamos pesquisando os impactos práticos da DUIMP no Porto de Santos. "
        f"{frase_contexto} "
        f"Poderia contribuir com nossa pesquisa de campo de 3 minutos? {FORM_URL}"
    )

    return remover_emojis(copy)


def chamar_llm_local(
    prompt: str,
    provider: str = "ollama",
    model: str = "llama3",
    endpoint: Optional[str] = None,
    timeout: int = 40
) -> Optional[str]:
    """Realiza chamada HTTP para o backend de LLM local configurado."""
    if provider == "ollama":
        url = endpoint or "http://localhost:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.6,
                "top_p": 0.9
            }
        }
    elif provider in ("lmstudio", "openai", "vllm", "localai"):
        url = endpoint or "http://localhost:1234/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um assistente especializado em redação de mensagens profissionais para LinkedIn. Nunca utilize emojis."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.6
        }
    else:
        print(f"Provedor '{provider}' nao suportado.")
        return None

    dados_json = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=dados_json,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resultado = json.loads(resp.read().decode("utf-8"))
            if provider == "ollama":
                texto = resultado.get("response", "")
            else:
                texto = resultado.get("choices", [{}])[0].get("message", {}).get("content", "")
            return remover_emojis(texto).strip()
    except Exception:
        return None


def salvar_resultados(
    registros_com_copy: List[Dict[str, Any]],
    arquivo_csv: Optional[str] = None,
    arquivo_md: Optional[str] = None
) -> None:
    """Salva os resultados em formato CSV e gera um relatorio Markdown estruturado."""
    if not registros_com_copy:
        print("Nenhum registro para salvar.")
        return

    caminho_csv = arquivo_csv or os.path.join(SCRIPT_DIR, "copies_gerados_pesquisa_porto_hack.csv")
    caminho_md = arquivo_md or os.path.join(SCRIPT_DIR, "copies_gerados_pesquisa_porto_hack.md")

    # 1. Gravacao do CSV
    todas_colunas = list(registros_com_copy[0].keys())
    if "Copy_Personalizado" not in todas_colunas:
        todas_colunas.append("Copy_Personalizado")

    with open(caminho_csv, "w", newline="", encoding="utf-8-sig") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=todas_colunas)
        writer.writeheader()
        writer.writerows(registros_com_copy)
    print(f"Arquivo CSV salvo com sucesso: {caminho_csv}")

    # 2. Gravacao do Relatorio Markdown
    linhas_md = [
        "# Relatório de Abordagens de Pesquisa de Campo - Porto Hack Santos 2026",
        "",
        "**Equipe:** DataWave (ABTRA / AmiGU / Fatec Rubens Lara)  ",
        f"**Formulário da Pesquisa:** {FORM_URL}  ",
        f"**Total de Contatos Processados:** {len(registros_com_copy)}  ",
        "",
        "---",
        ""
    ]

    for idx, reg in enumerate(registros_com_copy, start=1):
        nome = reg.get("Nome", "Contato")
        cargo = reg.get("Cargo", "Nao informado")
        empresa = reg.get("Empresa", "Nao informada")
        segmento = reg.get("Segmento_Inferido", "Nao informado")
        linkedin = reg.get("Perfil LinkedIn", "")
        status = reg.get("Status_Envio", "Pendente")
        copy = reg.get("Copy_Personalizado", "")

        linhas_md.append(f"### {idx}. {nome} ({empresa})")
        linhas_md.append(f"- **Cargo:** {cargo}")
        linhas_md.append(f"- **Segmento:** {segmento}")
        if linkedin:
            linhas_md.append(f"- **Perfil no LinkedIn:** [{linkedin}]({linkedin})")
        linhas_md.append(f"- **Status de Envio:** {status}")
        linhas_md.append("")
        linhas_md.append("**Copy de Abordagem Sugerido:**")
        linhas_md.append("```text")
        linhas_md.append(copy)
        linhas_md.append("```")
        linhas_md.append("")
        linhas_md.append("---")
        linhas_md.append("")

    with open(caminho_md, "w", encoding="utf-8") as f_md:
        f_md.write("\n".join(linhas_md))
    print(f"Relatório Markdown salvo com sucesso: {caminho_md}")


def main():
    parser = argparse.ArgumentParser(
        description="Gera copys de abordagem no LinkedIn para a pesquisa do Porto Hack Santos 2026 via LLM local."
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SHEET_URL,
        help="URL publica da planilha Google ou caminho para arquivo CSV local."
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "lmstudio", "openai"],
        default="ollama",
        help="Provedor do modelo local (ollama, lmstudio ou openai)."
    )
    parser.add_argument(
        "--model",
        default="llama3",
        help="Nome do modelo local na sua instancia (ex: llama3, mistral, qwen2.5)."
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="URL customizada do endpoint da LLM local (ex: http://localhost:11434/api/generate)."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Usa dados de exemplo para demonstracao e teste imediato do script."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nao conecta na LLM; gera os copys personalizados diretamente pelo motor de regras deterministico."
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Gerador de Copys para LinkedIn - Pesquisa Porto Hack Santos 2026")
    print("=" * 60)

    # 1. Carregamento dos dados
    registros = []
    if args.sample:
        print("Modo de demonstracao ativado: utilizando dados simulados de contatos.")
        registros = SAMPLE_LEADS.copy()
    else:
        registros = carregar_dados_planilha(args.source)
        if not registros:
            print("Aviso: Nenhum contato registrado ainda na planilha online. Utilizando dados de exemplo para demonstracao.")
            registros = SAMPLE_LEADS.copy()

    print(f"Total de registros a processar: {len(registros)}")

    # 2. Processamento de cada lead
    registros_processados = []
    llm_ativa = not args.dry_run

    for i, lead in enumerate(registros, start=1):
        nome = lead.get("Nome", f"Contato #{i}")
        cargo = lead.get("Cargo", "")
        print(f"\n[{i}/{len(registros)}] Processando: {nome} ({cargo})...")

        copy_gerado = None

        if llm_ativa:
            prompt = construir_prompt_personalizacao(lead)
            print(f"Solicitando geracao a LLM local ({args.provider} / {args.model})...")
            resposta_llm = chamar_llm_local(
                prompt=prompt,
                provider=args.provider,
                model=args.model,
                endpoint=args.endpoint
            )
            if resposta_llm:
                copy_gerado = resposta_llm
                print("Copy gerado com sucesso via LLM local.")
            else:
                print("LLM local indisponivel no momento. Utilizando gerador inteligente de regras.")
                copy_gerado = gerar_copy_regras_fallback(lead)
        else:
            print("Modo dry-run: gerando copy pelo motor deterministico.")
            copy_gerado = gerar_copy_regras_fallback(lead)

        lead_com_copy = dict(lead)
        lead_com_copy["Copy_Personalizado"] = copy_gerado
        registros_processados.append(lead_com_copy)

    # 3. Exportacao dos arquivos
    print("\nSalvando arquivos de saida...")
    salvar_resultados(registros_processados)

    print("\nProcesso concluido com sucesso.")


if __name__ == "__main__":
    main()
