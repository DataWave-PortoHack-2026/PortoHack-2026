# Pesquisa Setorial V3: Gargalos Operacionais e Tomada de Decisão na Importação em Santos
**Porto Hack Santos 2026 — Roteiro Estruturado de Pesquisa de Campo (Google Forms / LinkedIn)**  
**Equipe DataWave:** Adriane, Arthur, Giulia, Gustavo e Yuri  
**Contato Institucional:** [Giulia Granado no LinkedIn](https://www.linkedin.com/in/giuliagranado)

---

## SUMÁRIO DESTE DOCUMENTO
1. [Parte 1: Especificação Técnica e Lógica de Ramificação (Para Script / Google Apps Script)](#parte-1-especificação-técnica-e-lógica-de-ramificação-para-o-script-gerador)
2. [Parte 2: Texto Completo do Formulário para os Respondentes](#parte-2-texto-do-formulário-para-os-respondentes)
3. [Parte 3: Textos de Convite para Divulgação (Sem Emojis)](#parte-3-textos-de-convite-para-divulgação-sem-emojis)
4. [Parte 4: Dicionário de Dados e Matriz de Tags para IA e Planilhas](#parte-4-dicionário-de-dados-e-mapa-de-tags-para-ia-e-planilhas)

---

# PARTE 1: Especificação Técnica e Lógica de Ramificação (Para o Script Gerador)

Esta seção documenta a arquitetura de navegação para a automação do Google Forms via Google Apps Script ou Python (Google Forms API).

### Diagrama de Fluxo / Branching Logic

```text
[ SEÇÃO 1: Identificação do Participante (Comum a Todos) ]
    |
    v
[ SEÇÃO 2: Perfil da Operação (Filtro por Cadeira) ]
    |
    |-- Q1 = "Importador..." ou "Trading..."            --> Direcionar para SEÇÃO 3
    |-- Q1 = "Despachante Aduaneiro..."                 --> Direcionar para SEÇÃO 4
    |-- Q1 = "Transportador..." ou "Agente/Terminal..." --> Direcionar para SEÇÃO 5
    |-- Q1 = "Outro"                                    --> Direcionar para SEÇÃO 6
    |
    +---> [ SEÇÃO 3: Visão Importador (Caixa/Estoque) ] ----------+
    |                                                             |
    +---> [ SEÇÃO 4: Visão Despachante (Catálogo/LPCO) ] ---------+--> [ SEÇÃO 6: Decisão e IA ]
    |                                                             |            |
    +---> [ SEÇÃO 5: Visão Operacional (Gate/Frota/LCL) ] --------+            v
                                                                   [ SEÇÃO 7: Experiência Real ]
                                                                               |
                                                                               v
                                                                           [ ENVIO ]
```

### Metadados e Validações de Campo para o Script:
- **Identificação (Seção 1):**
  - Nome Completo: Tipo `TEXT` | Obrigatória: `Sim`.
  - Empresa / Organização: Tipo `TEXT` | Obrigatória: `Sim`.
  - Cargo / Função: Tipo `TEXT` | Obrigatória: `Sim`.
  - E-mail de Contato: Tipo `TEXT` | Validação: `E-mail` | Obrigatória: `Sim`.
  - Telefone / WhatsApp ou LinkedIn: Tipo `TEXT` | Obrigatória: `Sim`.
- **Perfil Operacional (Seção 2):**
  - **Q1:** Tipo `MULTIPLE_CHOICE` | Obrigatória: `Sim` | Ação: `setGoToPage` por opção de resposta.
  - **Q2, Q3, Q4:** Tipo `MULTIPLE_CHOICE` | Obrigatória: `Sim`.
- **Perguntas Específicas por Segmento (Seções 3, 4 e 5):**
  - **Q5, Q6, Q7, Q8, Q9, Q10:** Tipo `CHECKBOX` | Validação: `Máximo 2 opções selecionadas` | Obrigatória: `Sim`.
- **Visão Geral e Tecnologia (Seção 6):**
  - **Q11, Q12, Q13:** Tipo `MULTIPLE_CHOICE` | Obrigatória: `Sim`.
- **Fechamento e Casos Reais (Seção 7):**
  - **Q14:** Tipo `PARAGRAPH_TEXT` | Obrigatória: `Não`.

---

# PARTE 2: Texto do Formulário para os Respondentes

### Título do Formulário
> **Gargalos Operacionais e Tomada de Decisão na Importação em Santos**

### Descrição Inicial
> Olá!
>
> Quem está na rotina do Porto de Santos sabe bem: entre a chegada do navio, o registro da DUIMP e a entrega efetiva da mercadoria, qualquer desalinhamento custa caro em armazenagem, sobreestadia (demurrage) e estresse na operação.
>
> Somos a equipe **DataWave** (**Adriane, Arthur, Giulia, Gustavo e Yuri**), participantes do **Porto Hack Santos 2026**. Estamos realizando este levantamento com profissionais do setor para mapear com precisão onde estão as maiores dores de cabeça de quem atua na linha de frente do comércio exterior e da logística portuária.
>
> Este formulário é dinâmico: após preencher seus dados de contato, você responderá apenas às perguntas ligadas ao seu papel específico na operação, levando cerca de **3 a 4 minutos**.
>
> As informações coletadas serão fundamentais para embasar a solução técnica que nosso time apresentará para a banca avaliadora do hackathon.
>
> Caso queira conversar com o nosso grupo ou acompanhar o projeto, você pode entrar em contato diretamente com a nossa integrante Giulia Granado pelo LinkedIn: https://www.linkedin.com/in/giuliagranado.
>
> Agradecemos muito pela sua parceria e pelo seu tempo!

---

### SEÇÃO 1: Identificação do Participante
*(Informações cadastrais para validação da amostra e contato da equipe)*

**Nome Completo:**  
`[Campo de texto curto — Obrigatório]`

**Empresa / Organização:**  
`[Campo de texto curto — Obrigatório]`

**Cargo / Função na Operação:**  
`[Campo de texto curto — Obrigatório]`

**E-mail Profissional:**  
`[Campo de texto curto — Obrigatório]`

**Telefone / WhatsApp ou Perfil do LinkedIn:**  
`[Campo de texto curto — Obrigatório]`

---

### SEÇÃO 2: Perfil da sua Operação
*(Mapeamento operacional para direcionar você para as perguntas certas)*

**1. Qual é o papel principal da sua empresa na importação por Santos?**  
*(Escolha única — define as próximas perguntas)*
- Importador direto / Indústria (Dono da carga) *(Configuração no Forms: Ir para Seção 3)*
- Trading Company *(Configuração no Forms: Ir para Seção 3)*
- Despachante Aduaneiro / Comissária de Despacho *(Configuração no Forms: Ir para Seção 4)*
- Transportador Rodoviário / Operador Logístico *(Configuração no Forms: Ir para Seção 5)*
- Agente de Carga / NVOCC / Terminal Retroportuário *(Configuração no Forms: Ir para Seção 5)*
- Outro: `[Campo de texto]` *(Configuração no Forms: Ir para Seção 6)*

**2. Qual é o volume médio anual de contêineres (TEUs) movimentados por Santos pela sua empresa ou clientes?**  
*(Escolha única)*
- Até 50 contêineres/ano (Operação pontual ou pequeno porte)
- De 51 a 500 contêineres/ano (Médio porte)
- Acima de 500 contêineres/ano (Grande porte / Grande gerador)

**3. Qual é o segmento predominante das mercadorias que você movimenta?**  
*(Escolha única)*
- Alimentos, Bebidas e Agropecuária (Sujeito a MAPA / Vigiagro)
- Químico, Farmacêutico, Cosméticos e Saúde (Sujeito a ANVISA)
- Eletroeletrônicos, Tecnologia e Bens de Capital
- Máquinas, Equipamentos, Metalurgia e Autopeças
- Bens de Consumo Geral, Têxtil e Varejo
- Outro: `[Campo de texto]`

**4. A sua empresa (ou a maior parte da sua carteira de clientes) possui certificação OEA?**  
*(Escolha única)*
- Sim, OEA-Conformidade (Nível Qualificado ou Pleno), com benefício de diferimento de tributos
- Sim, OEA-Segurança
- Não, mas está em processo de certificação
- Não operamos como OEA no momento
- Não sei informar

---

### SEÇÃO 3: Visão do Importador e Trading (Caixa, Custos e Estratégia)
*(Perguntas direcionadas para donos da carga e gestores de importação)*  
*(Configuração no Forms: Ao terminar, ir para a Seção 6)*

**5. Pensando em CUSTOS E FLUXO DE CAIXA, qual é o maior freio para tirar a carga direto no cais assim que o navio atraca?**  
*(Caixas de seleção — escolha até 2 opções)*
- Ter que pagar tributos federais e ICMS "sobre as águas" logo no registro da DUIMP desequilibra o caixa da empresa
- O medo do demurrage no cais assusta muito mais do que a tarifa fechada de armazenagem do retroporto
- Falta de clareza no custo real final (taxas extras de cais/SSE/THC2 contra pacotes previsíveis de armazenagem no porto seco)
- Lentidão e falhas na compensação e baixa de guias no Pagamento Centralizado da DUIMP (PCCE)
- Outro: `[Campo de texto]`

**6. Se a sua carga obtém Canal Verde na DUIMP antecipada, por que você ainda prefere transferi-la para o retroporto?**  
*(Caixas de seleção — escolha até 2 opções)*
- Usamos o retroporto de propósito como pulmão de estoque, pois a fábrica ou CD não tem espaço para receber tudo de uma vez
- Precisamos de serviços que o cais não faz (etiquetagem aduaneira, montagem de kits, paletização, desova ou fracionamento)
- Segurança operacional: o retroporto dá mais fôlego e prazo para programar o transporte rodoviário sem o risco das multas de pátio do cais
- Outro: `[Campo de texto]`

---

### SEÇÃO 4: Visão do Despachante Aduaneiro (Catálogo, LPCO e Burocracia)
*(Perguntas focadas em regras fiscais, sistemas e anuentes)*  
*(Configuração no Forms: Ao terminar, ir para a Seção 6)*

**7. Na transição para a DUIMP, quais têm sido as maiores dores de cabeça com o Catálogo de Produtos?**  
*(Caixas de seleção — escolha até 2 opções)*
- Dificuldade para preencher e validar atributos específicos e complexos exigidos pela Receita Federal por NCM
- Exigências e indeferimentos causados por descrições incompletas ou genéricas no cadastro prévio do item
- A NCM cadastrada não pode ser corrigida: se houver erro, é preciso inativar o produto e recadastrar do zero
- Falta de governança e alinhamento interno entre importador e despachante para validar as informações técnicas
- Outro: `[Campo de texto]`

**8. No módulo LPCO, onde estão os maiores gargalos e atrasos práticos?**  
*(Caixas de seleção — escolha até 2 opções)*
- Demora dos órgãos anuentes (Anvisa, MAPA, Inmetro) para deferir licenças antes da atracação do navio
- Fiscalização de madeira pelo MAPA/Vigiagro (exigência de expurgo ou devolução que trava o contêiner no cais)
- Exigência da ANVISA para inspeções físicas ou amostragem em áreas climatizadas, raras ou muito caras no cais
- Falhas de comunicação sistêmica entre o LPCO aprovado e o registro final da DUIMP
- Outro: `[Campo de texto]`

---

### SEÇÃO 5: Visão de Transporte e Terminal (Asfalto, Gates e LCL)
*(Perguntas focadas na tração rodoviária e na movimentação física)*  
*(Configuração no Forms: Ao terminar, ir para a Seção 6)*

**9. Em relação ao agendamento de janelas e transporte rodoviário nos terminais de cais, qual é o principal atrito?**  
*(Caixas de seleção — escolha até 2 opções)*
- Dificuldade para conseguir janelas de agendamento de gate compatíveis para retirar a carga com agilidade
- Falta de caminhões disponíveis e sincronizados para retirar o contêiner dentro da franquia gratuita de cais após a liberação
- Multas pesadas de no-show cobradas pelos terminais quando o caminhão atrasa por causa de filas e trânsito no porto
- Outro: `[Campo de texto]`

**10. Nas operações de Carga Consolidada/Fracionada (LCL), quais são os maiores problemas em Santos?**  
*(Caixas de seleção — escolha até 2 opções)*
- Demora excessiva para desovar o contêiner e separar os lotes dos conhecimentos filhotes (House BL) no recinto
- Dificuldades operacionais e de sistema para vincular cargas LCL no ambiente do CCT Importação e DUIMP
- Falta de visibilidade em tempo real sobre o status da desova e liberação junto aos NVOCCs e recintos
- Outro: `[Campo de texto]`

---

### SEÇÃO 6: Decisão de Fluxo e Tecnologias
*(Seção comum a todos os participantes)*  
*(Configuração no Forms: Ao terminar, ir para a Seção 7)*

**11. Sabendo que a grande maioria das cargas com Canal Verde na DUIMP já tem permissão legal para sair direto do cais, por que o mercado ainda manda quase tudo para o retroporto?**  
*(Escolha única)*
- Hábito e aversão ao risco: o mercado prefere manter a rotina que já funciona há décadas
- Insegurança na operação: o retroporto funciona como um seguro contra custos imprevistos de pátio e demurrage
- Falta de capacidade da infraestrutura rodoviária e dos gates para escoar tantas cargas de uma vez
- Exigências de vistoria física por órgãos anuentes que inviabilizam a liberação imediata no cais
- Outro: `[Campo de texto]`

**12. Pergunta de reflexão: se a sua operação tivesse caixa sobrando, certificação OEA plena (com tributos diferidos) e caminhões na hora que precisasse, você tiraria 100% dos contêineres direto no cais?**  
*(Escolha única)*
- Sim, com certeza: o único motivo de usarmos o retroporto hoje é a falta de fôlego financeiro ou de caminhão na hora certa
- Não, continuaríamos no retroporto: ainda precisaríamos do pátio para pulmão de estoque, serviços agregados ou proteção contra demurrage
- Apenas em parte: migraríamos somente cargas urgentes e sem incidência de órgãos anuentes, mantendo o restante no fluxo tradicional
- Não se aplica à minha operação / Não tenho certeza

**13. Se existisse uma solução inteligente pensada para a sua rotina em Santos, onde ela deveria focar para ajudar mais?**  
*(Escolha única)*
- Comparador Financeiro em Tempo Real: calcula na hora se compensa mais retirar direto ou transferir para o recinto, comparando risco de demurrage contra armazenagem
- Orquestrador de Agendamento: monitora a atracação, identifica o canal verde da DUIMP e agenda automaticamente a janela de caminhão no gate ideal
- Validador Prévio de Catálogo e DUIMP: confere atributos, NCM e regras de anuentes antes do registro para evitar multas, atrasos e canal vermelho
- Outro: `[Campo de texto]`

---

### SEÇÃO 7: Experiência Real e Fechamento
*(Seção comum a todos os participantes — Encerramento do formulário)*

**14. (Opcional) Conte em 1 ou 2 frases: qual foi o imprevisto mais caro ou dor de cabeça mais marcante que você já enfrentou ao tentar liberar uma carga em Santos?**  
`[Campo de texto longo / parágrafo]`

---

# PARTE 3: Textos de Convite para Divulgação (Sem Emojis)

### Mensagem 1: Publicação Aberta no LinkedIn
```text
Desafios reais da importação em Santos: onde a sua operação trava hoje?

Entre a atracação do navio, o registro da DUIMP, o ICMS sobre águas e a corrida contra o demurrage, quem vive a rotina do comércio exterior em Santos sabe que cada dia de atraso pesa no bolso e na operação.

Somos a equipe DataWave (Adriane, Arthur, Giulia, Gustavo e Yuri), participantes do Porto Hack Santos 2026. Estamos desenvolvendo uma solução focada nos gargalos práticos de tomada de decisão, fluxo de caixa e custos portuários.

Para construirmos algo com base na realidade prática de quem está no cais e no escritório, criamos uma pesquisa rápida de campo de 3 a 4 minutos, segmentada por área de atuação:

Link da pesquisa: [INSERIR_LINK_DO_FORMULARIO]

Se você atua como importador, despachante, transportador ou operador portuário, sua contribuição é essencial para enriquecer o diagnóstico do projeto.

Dúvidas ou interesse em trocar ideias sobre o tema? Fale diretamente com a Giulia Granado da nossa equipe: https://www.linkedin.com/in/giuliagranado

Agradecemos pelo apoio de quem puder participar ou compartilhar com a sua rede!
```

### Mensagem 2: Convite Direto no LinkedIn (1 a 1 / InMail)
```text
Olá, [Nome]! Tudo bem?

Acompanho sua atuação no comércio exterior e sei dos desafios diários para gerenciar custos, prazos e janelas logísticas no Porto de Santos.

Faço parte da equipe DataWave (formada por Adriane, Arthur, Giulia, Gustavo e eu) no Porto Hack Santos 2026. Estamos conduzindo um estudo de campo para entender os reais motivos que levam as empresas a optar entre a retirada direta no cais e o envio para o retroporto sob o modelo da DUIMP.

Preparamos uma pesquisa rápida de 3 minutos com perguntas específicas para o seu segmento de atuação:

[INSERIR_LINK_DO_FORMULARIO]

Sua visão sobre esses gargalos práticos seria muito valiosa para o nosso projeto. Se desejar saber mais sobre nossa iniciativa, o contato da Giulia Granado da nossa equipe é: https://www.linkedin.com/in/giuliagranado

Muito obrigado pelo seu tempo e colaboração!
```

### Mensagem 3: Mensagem para Grupos de WhatsApp
```text
Olá, pessoal! Tudo bem?

Nosso grupo, o DataWave (Adriane, Arthur, Giulia, Gustavo e Yuri), está participando do Porto Hack Santos 2026 desenvolvendo um projeto para desatar gargalos na importação em Santos (DUIMP, fluxo de caixa, demurrage e janelas de agendamento).

Para trazer dados reais e qualificados para a banca avaliadora, criamos uma pesquisa de campo rápida de 3 a 4 minutos com perguntas direcionadas para cada papel (importador, despachante, transportador e operador):

[INSERIR_LINK_DO_FORMULARIO]

Quem puder contribuir com a sua experiência, fortalece demais o trabalho! Caso queiram falar diretamente com o nosso grupo, o contato da Giulia Granado no LinkedIn é: https://www.linkedin.com/in/giuliagranado

Obrigado a todos pela força!
```

---

# PARTE 4: Dicionário de Dados e Mapa de Tags para IA e Planilhas

Esta matriz correlaciona as opções humanizadas do formulário às tags originais para uso no script do Google Forms, na planilha do Entregável 1 e nos prompts de análise:

| Seção | Pergunta | Alternativa Humanizada no Formulário | Tag do Projeto / IA |
| :--- | :--- | :--- | :--- |
| **Seção 1** | **Identificação** | Nome, Empresa, Cargo, E-mail e Telefone/LinkedIn | `[ID_Respondente]` |
| **Seção 3** | **Q5 (Custos & Caixa)** | Ter que pagar tributos federais e ICMS "sobre as águas" logo no registro da DUIMP... | `[B1_Caixa]` |
| | | O medo do demurrage no cais assusta muito mais do que a tarifa fechada... | `[B2_Demurrage]` |
| | | Falta de clareza no custo real final (taxas extras de cais/SSE/THC2)... | `[B3_Assimetria]` |
| | | Lentidão e falhas na compensação e baixa de guias no PCCE... | `[B4_PCCE]` |
| **Seção 3** | **Q6 (Motivo Retroporto)**| Usamos o retroporto de propósito como pulmão de estoque... | `[C1_Estoque]` |
| | | Precisamos de serviços que o cais não faz (etiquetagem, kits, desova)... | `[C2_Servicos]` |
| | | Segurança operacional: mais fôlego para programar o transporte rodoviário... | `[C3_Seguranca]` |
| **Seção 4** | **Q7 (Catálogo)** | Dificuldade para preencher e validar atributos específicos por NCM... | `[CP1_Atributos]` |
| | | Exigências e indeferimentos por descrições incompletas ou genéricas... | `[CP2_Descricao]` |
| | | A NCM cadastrada não pode ser corrigida: inativar e recadastrar do zero... | `[CP3_NCM_Erro]` |
| | | Falta de governança e alinhamento interno entre importador e despachante... | `[CP4_Representante]` |
| **Seção 4** | **Q8 (LPCO / Anuentes)** | Demora dos órgãos anuentes (Anvisa, MAPA, Inmetro) para deferir licenças... | `[LP1_Atraso_Anuente]` |
| | | Fiscalização de madeira pelo MAPA/Vigiagro (expurgo ou devolução)... | `[LP2_Madeira]` |
| | | Exigência da ANVISA para inspeções em áreas climatizadas no cais... | `[LP3_Anvisa_Fisica]` |
| | | Falhas de comunicação sistêmica entre LPCO aprovado e DUIMP... | `[LP4_Divergencia]` |
| **Seção 5** | **Q9 (Transporte & Gate)** | Dificuldade para conseguir janelas de agendamento de gate compatíveis... | `[A1_Gate]` |
| | | Falta de caminhões sincronizados para retirar dentro do prazo gratuito... | `[A2_Frota_Sinc]` |
| | | Multas pesadas de no-show quando o caminhão atrasa por filas no porto... | `[A3_NoShow]` |
| **Seção 5** | **Q10 (Carga LCL)** | Demora excessiva para desovar o contêiner e separar os House BLs... | `[E1_LCL_Desova]` |
| | | Dificuldades operacionais e de sistema para vincular no CCT Importação... | `[E2_LCL_CCT]` |
| | | Falta de visibilidade em tempo real sobre desova junto a NVOCCs... | `[E3_LCL_Visibilidade]` |
| **Seção 6** | **Q11 (Por que não 92%?)**| Hábito e aversão ao risco: manter a rotina que já funciona há décadas... | `[PX1_Cultura]` |
| | | Insegurança na operação: seguro contra custos de pátio e demurrage... | `[PX2_Inseguranca]` |
| | | Falta de capacidade da infraestrutura rodoviária e dos gates... | `[PX3_Infra]` |
| | | Exigências de vistoria física por órgãos anuentes que impedem saída rápida... | `[PX4_Anuentes]` |
| **Seção 6** | **Q12 (Pergunta de Ouro)**| Sim, com certeza: falta de fôlego financeiro ou frota é o único motivo... | `[Contrafactual_Migra]` |
| | | Não, continuaríamos no retroporto: pulmão de estoque, serviços ou seguro... | `[Contrafactual_Retem]` |
| | | Apenas em parte: somente cargas urgentes e sem anuentes... | `[Contrafactual_Parcial]` |
| **Seção 6** | **Q13 (Solução de IA)** | Comparador Financeiro em Tempo Real (demurrage vs. armazenagem)... | `[IA_Tradeoff]` |
| | | Orquestrador de Agendamento (atracação + DUIMP + gate automático)... | `[IA_Sincronia]` |
| | | Validador Prévio de Catálogo e DUIMP (atributos e NCM antes do registro)... | `[IA_Qualidade]` |
| **Seção 7** | **Q14 (Relato Aberto)** | Campo livre de relato de imprevisto/custo marcante | `[Relato_Qualitativo]` |
