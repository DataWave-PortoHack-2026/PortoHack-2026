# Contrato de Saída JSON DataWave

Esta skill define as regras de comunicação estruturada do Agente DataWave. Como a interface de conversação não possui esquema tipado nativo na camada de transporte, o agente deve seguir rigorosamente as convenções de resposta JSON estabelecidas abaixo para permitir o parsing automático pelo cliente Pydantic do sistema.

---

## 1. Regra Fundamental de Resposta

Quando um comando ou solicitação do sistema demandar saída em formato JSON:

1. **Saída Exclusiva em JSON Puro:** A resposta deve conter unicamente o objeto JSON válido, sem qualquer texto introdutório, explicações contextuais, notas de rodapé ou saudações.
2. **Sem Delimitadores de Bloco de Código:** Não utilize cercas de markdown (como ````json` ou ````). O primeiro caractere da resposta deve ser `{` ou `[` e o último caractere deve ser `}` ou `]`.
3. **Validade Sintática:** Garanta que todas as chaves estejam entre aspas duplas, que não haja vírgulas sobrando após o último elemento de um objeto ou lista e que caracteres de escape sejam manipulados corretamente.

---

## 2. Convenções de Tipagem e Formatação

- **Datas:** Devem seguir rigorosamente a norma ISO 8601 no formato `YYYY-MM-DD` (exemplo: `"2026-03-15"`).
- **Valores Monetários e Numéricos:** Devem ser expressos como valores numéricos de ponto flutuante (`float`) ou inteiros (`int`), utilizando ponto como separador decimal (exemplo: `45200.75`). Nunca inclua símbolos monetários (`$`, `R$`, `USD`) ou separadores de milhar dentro de campos numéricos.
- **Valores Ausentes ou Não Localizados:** Quando uma informação não puder ser extraída do documento ou não estiver disponível na base de dados, utilize o valor primitivo `null`, a menos que o prompt especifique textualmente a string `"indisponível"`.
- **Listas e Conjuntos:** Listas sem itens devem ser expressas como arrays vazios (`[]`) e nunca omitidas caso o campo seja esperado no schema.

---

## 3. Contratos de Dados do Sistema

O cliente Python (`AgentClient`) valida as respostas do agente contra três esquemas fundamentais modelados em Pydantic:

### 3.1 Contrato `OperacaoExtraida` (Extração Documental — U2)
Utilizado na consolidação de dados extraídos de Conhecimentos de Embarque (BL), Faturas Comerciais e Romaneios de Carga (Packing List):

```json
{
  "ncm": "8481.80.95",
  "descricao": "Válvulas industriais de controle de fluxo em aço inoxidável",
  "valor_lote_usd": 68500.0,
  "qtd_conteineres": 1,
  "incoterm": "FOB",
  "porto_descarga": "Santos",
  "armador": "Maersk",
  "origem": "Alemanha",
  "data_chegada_prevista": "2026-04-10",
  "divergencias": [
    "Peso bruto na invoice (14.200 kg) diverge do packing list (14.150 kg)"
  ]
}
```

### 3.2 Contrato `MercadoNCM` (Inteligência de Mercado e Embarques — U1)
Utilizado para alimentar o módulo de risco e análise de permanência com o histórico real de importações em Santos:

```json
{
  "ncm": "8481.80.95",
  "periodo": "Últimos 12 meses",
  "volume_mensal": {
    "2025-04": 250000.0,
    "2025-05": 310000.0
  },
  "origens_top": [
    "Alemanha",
    "China",
    "Estados Unidos"
  ],
  "importadores_top": [
    "Indústria Mecânica Modelo S.A.",
    "Comércio e Distribuição Logística Ltda"
  ],
  "dias_chegada_desembaraco": {
    "canal_verde": 3.2,
    "canal_amarelo": 6.8,
    "canal_vermelho": 15.5
  }
}
```
*Nota: Caso o tempo por canal não esteja disponível na base consultada, defina o campo `dias_chegada_desembaraco` como `null`.*

### 3.3 Contrato `SugestaoAtributos` (Apoio ao Catálogo de Produtos — U3)
Utilizado quando o sistema solicita ao agente a identificação de atributos normativos do catálogo a partir de especificações técnicas ou descrições comerciais:

```json
{
  "sugestoes": {
    "ATT_01001": "02",
    "ATT_01045": "01",
    "ATT_01050": "A316L"
  },
  "incertos": [
    "ATT_01088"
  ]
}
```

---

## 4. Tratamento de Revalidação e Retentativas

Se a resposta não obedecer rigorosamente ao JSON solicitado, o cliente local rejeitará a mensagem e reenviará a solicitação acompanhada do erro de validação. Mantenha o formato exato nas retentativas para garantir a continuidade do fluxo.
