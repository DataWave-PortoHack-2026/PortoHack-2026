# Playbook de Extração Documental — Conferência Aduaneira

Esta skill orienta o Agente DataWave na leitura, extração de entidades operacionais e conferência cruzada dos três documentos fundamentais que compõem o dossiê de importação marítima: o Conhecimento de Embarque (*Bill of Lading* - BL), a Fatura Comercial (*Commercial Invoice*) e o Romaneio de Carga (*Packing List*).

---

## 1. Documentos-Alvo e Campos de Extração

Ao receber arquivos anexos ou transcrições dos documentos de embarque, o agente deve extrair e validar os seguintes atributos específicos:

### 1.1 Conhecimento de Embarque Marítimo (Bill of Lading - BL)
- **Identificadores:** Número do BL (*B/L Number*), transportador ou armador marítimo emitente.
- **Rota e Logística:** Porto de embarque (*Port of Loading* - POL), porto de descarga (*Port of Discharge* - POD), navio (*Vessel*) e número de viagem (*Voyage*).
- **Carga e Equipamentos:** Identificação alfanumérica de cada contêiner e respectivo número de lacre (*Seal*), tipo/dimensão do contêiner (ex.: 20' Dry, 40' Dry, 40' High Cube, Reefer, Open Top).
- **Massa e Frete:** Peso bruto total da carga em quilogramas (*Gross Weight*), cubagem em metros cúbicos (*Measurement* / CBM) e condição de frete (*Prepaid* ou *Collect*).

### 1.2 Fatura Comercial (Commercial Invoice)
- **Identificadores:** Número da fatura comercial e data de emissão.
- **Partes Intervenientes:** Exportador/Vendedor (*Shipper* / *Exporter*), país de procedência e fabricante; Importador/Comprador (*Consignee* / *Importer*) e dados cadastrais.
- **Dados da Mercadoria:** Descrição comercial detalhada de cada item, código da Nomenclatura Comum do Mercosul (NCM) associado a cada produto.
- **Valores e Condições Comerciais:** Moeda da transação (ex.: USD, EUR), preço unitário, valor total do lote, condições de pagamento e termo internacional de comércio (*Incoterm* — ex.: FOB, CIF, CFR, FCA).

### 1.3 Romaneio de Carga (Packing List)
- **Detalhamento de Volumes:** Quantidade total e tipos de embalagem (ex.: caixas, pallets, tambores, fardos, engradados).
- **Massa e Dimensões:** Peso líquido total (*Net Weight*) e peso bruto total (*Gross Weight*) expressos em quilogramas.
- **Estufagem:** Distribuição física dos volumes e embalagens no interior de cada contêiner especificado no BL.

---

## 2. Matriz de Conferência Cruzada e Detecção de Divergências

A discrepância entre os documentos de instrução da DUIMP é uma das maiores causas de exigências fiscais, retificações e retenção de carga no cais. O agente deve realizar a conferência cruzada obrigatória nos seguintes eixos:

### 2.1 Eixo NCM e Classificação Fiscal
- Compare a NCM informada na Fatura Comercial com eventuais referências no BL e com os atributos do Catálogo de Produtos.
- *Divergência típica:* Fatura indicando classificação fiscal específica e BL referenciando subposição genérica ou divergente.

### 2.2 Eixo de Pesos (Líquido e Bruto)
- O peso bruto informado no BL pelo armador deve ser rigorosamente coincidente com o somatório dos pesos brutos informados no Packing List e na Fatura Comercial.
- *Tolerância aceitável:* Nenhuma. Variações superiores a frações decimais decorrentes de arredondamento devem ser apontadas como inconsistência.
- O peso líquido deve ser estritamente menor que o peso bruto no Packing List.

### 2.3 Eixo de Quantidade de Volumes e Contêineres
- A quantidade total de unidades de embalagem (ex.: número de caixas, pallets ou tambores) no Packing List deve coincidir com os volumes discriminados no corpo do BL e na fatura.
- A quantidade de contêineres físicos e respectivos lacres listados no BL deve corresponder ao plano de estufagem do romaneio.

### 2.4 Eixo Incoterm e Frete
- Se a Fatura Comercial indica Incoterm do grupo C ou D (ex.: CIF, CIP, DAP), o frete marítimo no BL deve constar obrigatoriamente como *Prepaid* (pago na origem).
- Se a fatura indica Incoterm do grupo E ou F (ex.: FOB, FCA), o frete marítimo no BL deve figurar como *Collect* (a pagar no destino).
- Divergências entre o Incoterm da fatura e a condição de frete do BL inviabilizam o cálculo correto da base tributária dos impostos de importação.

---

## 3. Formatação da Saída (`divergencias`)

Todas as inconsistências identificadas devem ser sintetizadas em frases diretas, objetivas e tecnicamente fundamentadas dentro do array `divergencias` do contrato `OperacaoExtraida`:

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
    "Divergência de peso bruto: BL indica 14.500 kg, enquanto o Packing List totaliza 14.150 kg (diferença de 350 kg).",
    "Condição de frete incongruente: Fatura Comercial estabelece Incoterm FOB, mas o BL registra frete como Freight Prepaid.",
    "Quantidade de volumes diverge: Romaneio especifica 48 pallets, ao passo que o BL menciona 45 pallets."
  ]
}
```

Caso não exista nenhuma divergência entre os três documentos analisados, o campo `divergencias` deve retornar um array vazio (`[]`), sinalizando conformidade documental prévia.
