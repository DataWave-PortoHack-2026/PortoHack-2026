# Configuração Rápida de Skills — Agente Logcomex (Versão Calibrada)

Guia com os campos exatos para preenchimento no modal **Nova Skill** da plataforma Logcomex. As descrições foram calibradas com gatilhos de ativação direta para o roteador interno da plataforma.

---

## Skill 1: Catálogo de Produtos da DUIMP

- **Ícone:** Cérebro
- **Nome \*:**
```text
Catálogo de Produtos DUIMP
```
- **Descrição (Gatilho de Ativação):**
```text
Ative para qualquer solicitação envolvendo Catálogo de Produtos, DUIMP, atributos, NCM, Portal Único Siscomex, classificação técnica de produtos ou validação cadastral prévia.
```
- **Extender Capacidade:** `Nenhuma`
- **Instruções Base:**
```text
Esta skill orienta a auditoria, padronização e conferência prévia do Catálogo de Produtos da DUIMP no Portal Único Siscomex. Não procure ferramentas de API para responder a análises de catálogo; analise o texto fornecido pelo usuário e responda diretamente.

1. Padrões Canônicos do Portal Único Siscomex:
- Modalidade: Preencha estritamente com os literais IMPORTACAO ou EXPORTACAO (caixa alta, sem acento).
- Atributos Simples: Devem residir no array "atributos" no formato {"atributo": "ATT_xxxxx", "valor": "string"}.
- Atributos Multivalorados: Devem residir no array "atributosMultivalorados" no formato {"atributo": "ATT_xxxxx", "valores": ["string1", "string2"]}. Nunca use o campo "valor" no singular para multivalorados e nunca misture atributos simples nesta lista.

2. Árvores Condicionais de Atributos:
- Atributos raiz incondicionais determinam a área temática ou finalidade regulatória da carga.
- Atributos filhos só são aplicáveis quando as condições dos atributos pais forem satisfeitas. O envio de dados para atributos não aplicáveis gera alertas de preenchimento.
- Atributos opcionais para os quais não haja informação disponível devem ser omitidos do payload, nunca enviados como strings vazias.

3. Qualidade Cadastral e GTIN:
- Limpe espaços em branco excedentes nas pontas e espaços duplos intermediários de denominações e descrições.
- Códigos comerciais GTIN informados devem possuir comprimento correspondente ao tipo declarado (GTIN-8, 12 ou 13) e dígito verificador matematicamente válido pelo algoritmo GS1 (módulo 10).

4. Diretrizes de Assistência do Agente:
- Ao sugerir atributos a partir de documentos ou fichas técnicas, utilize exclusivamente códigos presentes nas listas oficiais do Siscomex ou do órgão anuente aplicável.
- Se a documentação não trouxer comprovação inequívoca para o código, marque o atributo como incerto no array "incertos".
- O motor determinístico local do sistema é a autoridade técnica final de validação cadastral.
```
- **Nome em English (opcional):** `DUIMP Product Catalog`
- **Descrição em English (opcional):** `Single Portal Siscomex guidelines, conditional attribute trees, and compliance rules for product catalog auditing.`

---

## Skill 2: Contrato de Saída JSON DataWave

- **Ícone:** Cérebro
- **Nome \*:**
```text
Contrato de Saída JSON DataWave
```
- **Descrição (Gatilho de Ativação):**
```text
Ative sempre que o usuário pedir resposta em formato JSON, JSON puro, formato estruturado ou dados dos esquemas OperacaoExtraida, MercadoNCM e SugestaoAtributos.
```
- **Extender Capacidade:** `Nenhuma`
- **Instruções Base:**
```text
Esta skill estabelece a sintaxe obrigatória de comunicação estruturada do agente com o cliente do sistema DataWave.

1. Regra Fundamental de Resposta em JSON:
- Quando o usuário ou sistema solicitar resposta em JSON, retorne exclusivamente o objeto JSON válido.
- Proibição absoluta de blocos markdown: nunca utilize cercas de código (como ```json ou ```). A resposta deve iniciar com "{" ou "[" e terminar com "}" ou "]".
- Não inclua preâmbulos, saudações, explicações ou notas de rodapé fora do objeto JSON.

2. Convenções de Tipagem:
- Datas: Padrão ISO 8601 no formato YYYY-MM-DD (exemplo: "2026-04-10").
- Moedas e Números: Utilize float ou int com ponto decimal (exemplo: 45200.75). Nunca inclua símbolos de moeda (R$, USD) ou separadores de milhar dentro de campos numéricos.
- Dados Indisponíveis: Se uma informação solicitada não existir nos documentos ou base de dados, utilize null ou arrays vazios ([]), ou o texto "indisponível" se solicitado pelo prompt.

3. Esquemas Principais de Saída:
- OperacaoExtraida: Objeto contendo chaves: ncm (str), descricao (str), valor_lote_usd (float), qtd_conteineres (int), incoterm (str/null), porto_descarga (str/null), armador (str/null), origem (str/null), data_chegada_prevista (str/null) e divergencias (array de strings descrevendo inconsistências entre BL, invoice e packing list).
- MercadoNCM: Objeto contendo chaves: ncm (str), periodo (str), volume_mensal (dicionário/null), origens_top (array de strings/null), importadores_top (array de strings/null) e dias_chegada_desembaraco (dicionário por canal/null).
- SugestaoAtributos: Objeto contendo chaves: sugestoes (dicionário de ATT_xxxxx para código) e incertos (array de códigos de atributos não resolvidos com certeza).
```
- **Nome em English (opcional):** `DataWave JSON Output Contract`
- **Descrição em English (opcional):** `Strict raw JSON response formatting and schema specifications for automated Pydantic parsing.`

---

## Skill 3: Glossário e Premissas Cais vs. Retroporto

- **Ícone:** Cérebro
- **Nome \*:**
```text
Glossário e Premissas Cais vs Retroporto
```
- **Descrição (Gatilho de Ativação):**
```text
Ative sempre que o usuário perguntar sobre cais, retroporto, demurrage, detention, armazenagem portuária, Santos, free time, sobre-estadia, CLIA ou canais de parametrização da DUIMP.
```
- **Extender Capacidade:** `Nenhuma`
- **Instruções Base:**
```text
Esta skill estabelece a base terminológica e as premissas aduaneiras e tarifárias do Porto de Santos para suporte à decisão logística. Responda diretamente com base neste conhecimento conceitual, sem buscar ferramentas executáveis na plataforma.

1. Zonas Portuárias de Santos:
- Zona Primária (Cais): Terminais portuários molhados (Santos Brasil, BTP, DP World). Alta demanda de pátio e tabelas de armazenagem progressivas agressivas com períodos curtos para forçar a rotação da carga.
- Zona Secundária (Retroporto / CLIA): Recintos alfandegados externos com capacidade para permanências médias e longas, tarifas diárias mais estáveis e estrutura para desova e inspeções físicas com menor pressão de custos.

2. Distinção Vital: Demurrage vs. Detention:
- Demurrage: Sobre-estadia do contêiner cheio no terminal cobrada pelo armador em dólares (USD) após o término do Free Time de Demurrage. Cessa quando o contêiner carregado sai do terminal portuário.
- Detention: Sobre-estadia do contêiner vazio cobrada pelo armador em dólares (USD) após o término do Free Time de Detention. Inicia quando o contêiner sai do terminal e cessa apenas na devolução do equipamento vazio e desovado no depot do armador.
- Premissa de Transferência: A remoção para retroporto suspende a contagem de demurrage do cais, mas a economia só se concretiza se a devolução do contêiner vazio ao depot do armador ocorrer rigorosamente dentro do Free Time de Detention acordado.

3. Dinâmica de Permanência e Canais de Parametrização:
- Canal Verde: Liberação aduaneira automática em 1 a 3 dias úteis.
- Canal Amarelo: Conferência documental com tempo médio de 4 a 8 dias úteis.
- Canal Vermelho: Conferência documental e vistoria física da mercadoria (10 a 25 dias). Apresenta altíssimo risco de sobre-estadia se mantido em zona primária.
- Interveniência de Órgãos Anuentes: Cargas reguladas por MAPA, Anvisa, Inmetro, Ibama ou outros órgãos dependem de inspeções ou laudos específicos antes do desembaraço aduaneiro, elevando o tempo de permanência e justificando a salvaguarda do retroporto.

4. Autoridade de Cálculo:
- O agente utiliza este vocabulário para fundamentar suas análises, mas nunca arbitra valores, tarifas ou dias de break-even. Todos os valores de custo e recomendações finais provêm do motor determinístico local do sistema.
```
- **Nome em English (opcional):** `Quay vs Dry Port Terminology and Assumptions`
- **Descrição em English (opcional):** `Santos customs concepts, demurrage vs detention separation, and port progressive storage dynamics.`

---

## Skill 4: Playbook de Extração Documental

- **Ícone:** Cérebro
- **Nome \*:**
```text
Playbook de Extração Documental
```
- **Descrição (Gatilho de Ativação):**
```text
Ative sempre que o usuário fornecer dados de documentos de embarque, Bill of Lading, BL, Commercial Invoice, fatura comercial, Packing List, romaneio de carga ou solicitar conferência de divergências.
```
- **Extender Capacidade:** `Nenhuma`
- **Instruções Base:**
```text
Esta skill orienta a extração estruturada de dados operacionais e a conferência cruzada entre os três documentos essenciais da instrução aduaneira de importação marítima. Não procure ferramentas externas para analisar textos de documentos fornecidos no prompt; compare os dados diretamente e aponte as inconsistências.

1. Documentos e Campos Críticos de Extração:
- Conhecimento de Embarque (Bill of Lading - BL): Número do BL, armador marítimo, navio e viagem, porto de embarque (POL), porto de descarga (POD), numeração dos contêineres e respectivos lacres (seals), tipo/dimensão do contêiner, peso bruto total (kg), cubagem (CBM) e modalidade de frete (Freight Prepaid ou Freight Collect).
- Fatura Comercial (Commercial Invoice): Número da fatura e data de emissão, exportador/fabricante e país de origem, importador/comprador (CNPJ), descrição comercial dos itens, NCM de cada produto, valor unitário e total do lote (USD/EUR), condições de pagamento e Incoterm (ex.: FOB, CIF, CFR, FCA).
- Romaneio de Carga (Packing List): Quantidade e tipo de volumes/embalagens (caixas, pallets, tambores), peso líquido total (kg), peso bruto total (kg) e plano de estufagem por contêiner.

2. Matriz de Conferência Cruzada e Detecção de Divergências:
- Eixo de Classificação Fiscal: Compare a NCM indicada na fatura comercial com as referências no BL e verifique a conformidade com as regras de catálogo.
- Eixo de Pesos: O peso bruto do BL deve coincidir rigorosamente com o somatório dos pesos brutos informados no Packing List e na Fatura Comercial. O peso líquido deve ser estritamente inferior ao peso bruto.
- Eixo de Volumes: A quantidade total de embalagens no Packing List deve bater exatamente com os volumes discriminados no BL e na fatura comercial.
- Eixo Incoterm vs. Frete: Faturas com Incoterm dos grupos C ou D exigem BL com frete Prepaid. Faturas com Incoterm dos grupos E ou F exigem BL com frete Collect. Divergências inviabilizam o cálculo tributário da DUIMP.

3. Formatação da Lista de Divergências:
- Registre cada inconsistência identificada de forma direta, clara e fundamentada no array "divergencias" do objeto OperacaoExtraida.
- Caso os três documentos estejam em perfeita conformidade mútua, retorne o array "divergencias" vazio ([]).
```
- **Nome em English (opcional):** `Document Extraction and Cross-Checking Playbook`
- **Descrição em English (opcional):** `Guidelines for extracting and cross-checking data across Bill of Lading, Commercial Invoice, and Packing List.`
