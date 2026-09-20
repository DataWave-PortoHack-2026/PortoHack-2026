# Glossário e Premissas Aduaneiras — Cais vs. Retroporto

Esta skill estabelece a base terminológica e as premissas conceituais sobre a logística portuária de importação pelo Porto de Santos, com foco na dinâmica de custos e permanência entre terminais portuários (cais) e recintos alfandegados em zona secundária (retroporto).

---

## 1. Zonas Aduaneiras no Complexo de Santos

A tomada de decisão logística de desova e armazenagem no Porto de Santos depende da distinção geográfica e regulatória das zonas aduaneiras:

### 1.1 Zona Primária (Cais / Terminal Portuário)
- Corresponde à área alfandegada contígua ao atracadouro onde os navios descarregam os contêineres (ex.: Santos Brasil / Tecon, Brasil Terminal Portuário - BTP, DP World Santos).
- Caracteriza-se por alta demanda de espaço físico de pátio, custo operacional elevado e estrutura tarifária progressiva agressiva concebida para forçar a rápida rotatividade da carga.

### 1.2 Zona Secundária (Retroporto / Recinto Alfandegado / CLIA)
- Corresponde a recintos alfandegados situados fora da faixa de cais, autorizados pela Receita Federal a receber mercadorias sob controle aduaneiro (ex.: Centros Logísticos e Industriais Aduaneiros - CLIAs e entrepostos aduaneiros no complexo santista).
- Oferece capacidade de armazenagem para permanências médias e longas, condições mais favoráveis de negociação de tarifas e estrutura para conferência física e desova de contêineres com menor pressão temporal.

---

## 2. A Distinção Crítica: Demurrage vs. Detention

A correta gestão de custos em importação marítima exige a modelagem segregada de duas cobranças aplicadas pelos armadores:

### 2.1 Demurrage (Sobre-estadia de Contêiner Cheio)
- Penalidade diária cobrada pelo armador pelo tempo que o contêiner carregado permanece no terminal além do período de gratuidade contratado (*Free Time de Demurrage*).
- Começa a contar logo após a atracação/descarga do navio e cessa no momento em que o contêiner cheio é retirado do terminal portuário.
- É tarifada em dólares americanos (USD/dia/contêiner) e escalona rapidamente após os primeiros dias de atraso.

### 2.2 Detention (Sobre-estadia de Contêiner Vazio)
- Penalidade diária cobrada pelo armador quando o contêiner é retirado do terminal, mas o importador demora para devolver a unidade vazia desovada no depósito designado pelo armador (*depot*) além do período contratado (*Free Time de Detention*).
- Cessa apenas com a efetiva entrega e vistoria do contêiner vazio no depósito.

### 2.3 Premissa Operacional de Transferência
A transferência da carga do cais para o retroporto (remoção em regime DTA ou trânsito aduaneiro simplificado) interrompe a contagem do demurrage no cais assim que o contêiner deixa o terminal. Contudo, **a economia projetada só se sustenta se a desova no recinto secundário e a restituição do vazio ocorrerem dentro do Free Time de Detention**. Se a devolução atrasar por pendências burocráticas ou conferência física demorada, o custo de detention em dólares continuará incidindo.

---

## 3. Armazenagem Portuária Progressiva

As tabelas de armazenagem nos terminais portuários de Santos operam por períodos escalonados:

1. **Estrutura por Períodos:** A permanência é tarifada por períodos fechados (tipicamente de 7 ou 10 dias). Ultrapassar um único dia do período anterior dispara a cobrança integral do período seguinte.
2. **Progressividade Tarifária:** As alíquotas percentuais (incidentes sobre o valor CIF da mercadoria) ou os valores fixos diários aumentam exponencialmente do 1º ao 2º período, e ainda mais drasticamente a partir do 3º período.
3. **Vantagem Comparativa do Retroporto:** Os recintos de retroporto praticam tarifas diárias mais estáveis ou períodos iniciais mais longos. Em cenários de risco de retenção, o retroporto atua como uma proteção contra o estouro de custos progressivos do cais, mesmo considerando os custos adicionais de frete rodoviário de transferência e movimentação de entrada/saída.

---

## 4. Canais de Parametrização e Órgãos Intervenientes

O tempo de permanência da carga em Santos é determinado pelo canal de conferência atribuído no registro da DUIMP e pela necessidade de fiscalização por órgãos anuentes:

- **Canal Verde:** Desembaraço aduaneiro automático sem conferência documental ou física. Liberação típica em 1 a 3 dias úteis.
- **Canal Amarelo:** Análise estritamente documental pela Receita Federal. Tempo típico de permanência de 4 a 8 dias úteis.
- **Canal Vermelho:** Análise documental e vistoria física obrigatória da mercadoria no recinto alfandegado. Tempo de permanência frequente de 10 a 25 dias, altamente suscetível a sobre-estadia se a carga estiver no cais.
- **Canal Cinza:** Fiscalização aprofundada para apuração de indícios de fraude ou valoração aduaneira.
- **Interveniência de Órgãos Anuentes:** Quando a NCM exige controle de órgãos reguladores (como Anvisa para medicamentos/cosméticos/insumos, Inmetro para conformidade técnica de bens de consumo, MAPA para produtos agropecuários/alimentos ou Ibama para controle ambiental), a concessão da Licença de Importação ou Liberação Sanitária/Técnica torna-se condicionante para o desembaraço. Qualquer divergência documental ou pendência de amostragem amplia significativamente a permanência, tornando a transferência para o retroporto uma salvaguarda contra demurrage e armazenagem astronômica no cais.

---

## 5. Princípio de Autoridade Numérica do Sistema

O Agente DataWave deve aplicar as premissas deste glossário para manter rigor técnico e coerência conceitual em seus diálogos e relatórios. No entanto, **o agente não calcula valores financeiros, não inventa tarifas e não arbitra dias de ponto de equilíbrio (break-even)**. Todos os valores numéricos, curvas de sensibilidade e recomendações finais são provenientes do motor determinístico em Python baseado nos parâmetros auditáveis do sistema (`tarifas.yaml`).
