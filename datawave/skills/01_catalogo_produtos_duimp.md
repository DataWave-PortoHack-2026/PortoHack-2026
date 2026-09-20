# Catálogo de Produtos da DUIMP — Regras Gerais e Anuentes

Esta skill estabelece a arquitetura normativa, as diretrizes de preenchimento e os critérios técnicos de conformidade para o Catálogo de Produtos da Declaração Única de Importação (DUIMP) no Portal Único Siscomex, abrangendo os requisitos gerais da Receita Federal do Brasil e de órgãos anuentes intervenientes (como MAPA, Anvisa, Inmetro, Ibama e outros).

---

## 1. Princípio Arquitetural do Catálogo de Produtos

No Novo Processo de Importação (NPI), o Catálogo de Produtos é o repositório central que desacopla o cadastro cadastral da mercadoria da declaração de importação:

- **Vínculo por NCM e Atributos:** Cada produto registrado vincula-se a uma classificação fiscal (NCM de 8 dígitos) e herda a árvore de atributos obrigatórios e condicionais exigida pela Receita Federal e pelos órgãos anuentes que exercem controle sobre aquela subposição.
- **Cadastramento Antecipado:** O catálogo deve ser auditado, padronizado e validado previamente ao embarque no exterior, evitando exigências fiscais, retificação de DUIMP e bloqueios em canal vermelho ou inspeção física que disparam custos de permanência no porto.

---

## 2. Padrão Oficial do Portal Único Siscomex

O payload estruturado de um produto no Catálogo de Produtos deve obedecer estritamente às especificações técnicas do Siscomex:

### 2.1 Campo Modalidade
- Preenchimento restrito aos valores canônicos: `IMPORTACAO` ou `EXPORTACAO`.
- O uso de acentuação gráfica (`IMPORTAÇÃO`), caixas mistas (`Importacao`) ou espaços marginais é rejeitado na recepção do sistema.

### 2.2 Segregação de Atributos Simples vs. Multivalorados
O Portal Único divide rigorosamente os atributos conforme sua cardinalidade:

- **Atributos Simples:** Devem residir no array `atributos`, estruturados em objetos com a chave `atributo` (código do atributo) e a chave `valor` (string com o valor ou código da opção):
  ```json
  {
    "atributo": "ATT_14200",
    "valor": "07"
  }
  ```
- **Atributos Multivalorados:** Devem residir no array `atributosMultivalorados`, utilizando obrigatoriamente a propriedade `valores` contendo uma lista de strings:
  ```json
  {
    "atributo": "ATT_14225",
    "valores": ["01", "02"]
  }
  ```
- **Regra de Consistência:** Um atributo definido no Siscomex como simples nunca pode constar em `atributosMultivalorados`, e um atributo multivalorado nunca pode ser enviado em `atributos` ou sob a propriedade `valor` no singular.

---

## 3. Dinâmica das Árvores Condicionais de Atributos

Independentemente do órgão anuente que regula a mercadoria, os atributos da DUIMP organizam-se em estruturas lógicas condicionais:

1. **Atributos Raiz e Áreas Temáticas:**
   - Atributos incondicionais no topo da hierarquia definem a área de aplicação ou a finalidade da mercadoria (por exemplo, área temática sanitária, tipo de destinação comercial ou industrial).
2. **Atributos Condicionais Dependentes:**
   - A resposta fornecida a um atributo pai ativa ou desativa ramos secundários de atributos filhos (`when: {op: "in", values: [...]}`).
   - Quando um ramo é ativado, os atributos filhos tornam-se **obrigatórios** ou **opcionais aplicáveis**.
   - Se o ramo não estiver ativo para a condição informada, os atributos filhos tornam-se **não aplicáveis**. O envio de valor para atributo não aplicável gera advertência ou inconsistência de cadastro.

---

## 4. Diretrizes de Higiene e Qualidade Cadastral

Para garantir aprovação em qualquer fiscalização documental ou aduaneira:

1. **Higienização Textual:** Os campos `denominacao`, `descricao` e valores textuais livres devem ser limpos de espaços excedentes no início e no final, bem como de repetições de múltiplos espaços internos.
2. **Omissão de Opcionais Sem Valor:** Atributos opcionais para os quais não há informação aplicável devem ser inteiramente **omitidos** do envio, evitando o envio de strings vazias (`""`) ou literais nulos.
3. **Código de Barras Comercial (GTIN):**
   - Quando informado, o atributo de tipo de código GTIN (`01` para GTIN-8, `02` para GTIN-12, `03` para GTIN-13) define o tamanho obrigatório da sequência.
   - O código informado deve possuir dígito verificador matematicamente válido de acordo com o algoritmo de módulo 10 da GS1.
4. **Denominação e Descrição Detalhada:** A descrição deve identificar claramente a mercadoria sem contradições entre a denominação comercial e as características técnicas declaradas nos atributos normativos.

---

## 5. Diretrizes para o Agente na Sugestão de Atributos

Ao atuar como assistente na leitura de faturas, fichas técnicas ou catálogos do exportador:

1. **Aderência às Listas Oficiais:** Sugira somente códigos existentes nas listas oficiais do Siscomex/órgão anuente para aquele atributo. Nunca crie valores livres para atributos tipados como lista estática.
2. **Registro de Incerteza:** Se a especificação documental não trouxer evidência inequívoca para definir um código, aponte o atributo na lista de `incertos`.
3. **Soberania do Validador Determinístico:** O motor local de auditoria (`catalog_audit.py`) é a autoridade técnica final do sistema. Todas as sugestões do agente são revalidadas pelo motor contra as regras estruturais da NCM antes da aprovação final.
