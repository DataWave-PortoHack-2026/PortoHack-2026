# Pesquisa Setorial: Gargalos Operacionais e Tomada de Decisão na Importação em Santos
**Porto Hack Santos 2026 — Roteiro Estruturado de Pesquisa de Campo (Google Forms / LinkedIn)**

---

### Instruções para Configuração no Google Forms
* **Objetivo:** Levantamento empírico de dados primários para o Entregável 1 e Planilha de Evidências.
* **Tempo estimado de resposta:** 3 a 4 minutos.
* **Lógica de tags:** Cada alternativa contém rótulos padronizados (ex: `[B1_Caixa]`, `[A1_Gate]`) para facilitar a exportação, análise gráfica e treinamento de agentes de IA.

---

### Descrição Inicial do Formulário
> *Esta pesquisa setorial tem como objetivo mapear os gargalos operacionais, tributários e logísticos enfrentados por importadores, despachantes, transportadores e operadores no Porto de Santos diante do Novo Processo de Importação (DUIMP/OEA). As respostas levam cerca de 3 a 4 minutos e serão tratadas em conformidade com as diretrizes acadêmicas do Porto Hack Santos 2026.*

---

## BLOCO 1: Perfil do Respondente e da Carga (Classificação da Amostra)

**1. Qual é o papel principal da sua empresa na importação marítima por Santos?** *(Múltipla Escolha - 1 opção)*
* [ ] Importador direto / Indústria / Dono da Carga
* [ ] Trading Company
* [ ] Despachante Aduaneiro / Comissária de Despacho
* [ ] Transportador Rodoviário / Operador Logístico
* [ ] Agente de Carga / NVOCC
* [ ] Outro: __________________________________

**2. Qual é o volume médio anual de contêineres (TEUs) movimentados pela sua empresa (ou seus principais clientes) por Santos?** *(Múltipla Escolha - 1 opção)*
* [ ] Até 50 contêineres/ano (Pequeno porte)
* [ ] De 51 a 500 contêineres/ano (Médio porte)
* [ ] Acima de 500 contêineres/ano (Grande porte)

**3. Qual é o segmento predominante das mercadorias importadas?** *(Múltipla Escolha - 1 opção)*
* [ ] Alimentos, Bebidas e Agropecuária (Forte controle MAPA/Vigiagro)
* [ ] Químico, Farmacêutico e Cosméticos (Forte controle ANVISA)
* [ ] Eletroeletrônicos e Tecnologia
* [ ] Máquinas, Equipamentos e Autopeças
* [ ] Bens de Consumo Gerais / Têxtil / Varejo
* [ ] Outro: __________________________________

**4. A sua empresa (ou a maioria de seus clientes) possui certificação OEA (Operador Econômico Autorizado)?** *(Múltipla Escolha - 1 opção)*
* [ ] Sim, OEA-Conformidade (Nível 1 ou 2) – usufrui de diferimento de tributos
* [ ] Sim, OEA-Segurança
* [ ] Não, mas está em processo de certificação
* [ ] Não, operamos como Não-OEA
* [ ] Não sei informar

---

## BLOCO 2: Mapeamento de Cenários na Prática

**5. Na rotina operacional em Santos, qual é o destino mais frequente das cargas conteinerizadas após a atracação do navio?** *(Múltipla Escolha - 1 opção)*
* [ ] **Cenário A:** Retirada Direta no Cais (Porto → Destino Final sem passar por recinto seco)
* [ ] **Cenário B:** Recinto Retroportuário por gestão de caixa (não antecipa tributos na DUIMP)
* [ ] **Cenário C:** Recinto Retroportuário por falta de estrutura logística/CD para recebimento imediato
* [ ] **Cenário D:** Recinto Retroportuário sob regime de Entreposto Aduaneiro (nacionalização fracionada)
* [ ] **Cenário E:** Recinto Retroportuário obrigatoriamente por ser carga consolidada fracionada (LCL)
* [ ] **Cenário F:** Recinto Retroportuário por parametrização em Canal Amarelo ou Vermelho (vistoria RFB)
* [ ] **Operamos com distribuição equilibrada entre múltiplos cenários** *(especifique no campo "Outro" abaixo quais cenários você mais divide, ex: A e C, A e B, etc.)*
* [ ] **Outro (ou especificar equilíbrio entre cenários):** __________________________________

---

## BLOCO 3: Mapeamento Detalhado de Gargalos e Dores (Tags Estruturadas)

**6. Sobre CUSTOS FINANCEIROS E TRIBUTÁRIOS (Cenário B), quais são os maiores gargalos enfrentados?** *(Caixas de Seleção - até 2 opções)*
* [ ] `[B1_Caixa]` O desembolso antecipado de tributos federais e ICMS sobre águas desequilibra o fluxo de caixa
* [ ] `[B2_Demurrage]` O risco financeiro de sobreestadia de contêiner (*demurrage*) no cais é muito mais perigoso do que a tarifa de armazenagem do retroporto
* [ ] `[B3_Assimetria]` Dificuldade de prever o custo real (taxas de segregação/THC2 do cais vs. pacotes fechados de armazenagem)
* [ ] `[B4_PCCE]` Falhas, lentidão ou demora na conciliação e baixa bancária de guias no Pagamento Centralizado da DUIMP
* [ ] Outro: __________________________________

**7. Sobre TRANSPORTE, PÁTIO E CENTRO DE DISTRIBUIÇÃO (Cenários A e C), quais são os principais atritos?** *(Caixas de Seleção - até 2 opções)*
* [ ] `[A1_Gate]` Dificuldade extrema de obter janelas de agendamento compatíveis nos gates dos terminais molhados
* [ ] `[A2_Frota]` Falta de caminhões disponíveis e sincronizados no exato momento da liberação da carga
* [ ] `[C1_CD]` O armazém ou fábrica do cliente não tem capacidade de receber múltiplos contêineres de uma vez (precisa de pulmão de estoque)
* [ ] `[C2_Servicos]` Necessidade indispensável de serviços de pátio (etiquetagem aduaneira, montagem de kits, desova, paletização)
* [ ] Outro: __________________________________

**8. Sobre FISCALIZAÇÃO, REGIMES ESPECIAIS E CARGA LCL (Cenários D, E e F), onde ocorrem os maiores atrasos?** *(Caixas de Seleção - até 2 opções)*
* [ ] `[D1_Entreposto]` Dificuldade operacional ou morosidade na gestão de admissões e nacionalizações fracionadas em entreposto aduaneiro
* [ ] `[D2_Anuentes]` Lentidão em inspeção física, coleta de amostras ou análise de LPCO por MAPA/Vigiagro ou ANVISA
* [ ] `[E1_LCL]` Morosidade e falta de visibilidade no processo de desunitização e entrega pelo NVOCC no recinto
* [ ] `[F1_CanalVermelho]` Prazos longos e custo elevado de movimentação/posicionamento para conferência física da Receita Federal
* [ ] Outro: __________________________________

---

## BLOCO 4: A "Pergunta de Ouro" (O Teste Contrafactual)

**9. Se sua empresa tivesse CAIXA SOBRANDO, certificação OEA plena (com diferimento de tributos) e FROTAS DE CAMINHÕES disponíveis na hora, você migraria 100% para o Cenário A (Retirada Direta no Cais)?** *(Múltipla Escolha - 1 opção)*
* [ ] **Sim, migraria 100%:** O único motivo de usar o retroporto hoje é a falta de caixa ou caminhão.
* [ ] **Não, manteria no retroporto:** Ainda precisaria do recinto para pulmão de estoque, serviços agregados ou proteção contra custos imprevistos de demurrage.
* [ ] **Parcialmente:** Migraria apenas cargas estratégicas/urgentes, mantendo o restante no fluxo tradicional.
* [ ] Não se aplica à minha operação.

---

## BLOCO 5: Visão de Futuro, Automação e Casos Reais

**10. Se uma solução de IA ou automação existisse hoje, qual destas funcionalidades geraria MAIOR impacto na sua operação?** *(Múltipla Escolha - 1 opção)*
* [ ] `[IA_Custos]` Simulador preditivo em tempo real: compara armazenagem vs. demurrage vs. custo de caixa e indica a rota mais barata (Cais vs. Recinto)
* [ ] `[IA_Agendamento]` Orquestrador automático: cruza atracação do navio, canal verde da DUIMP e reserva automática de janelas de caminhão no gate
* [ ] `[IA_Risco]` Alerta preditivo de parametrização e travas de órgãos anuentes antes da atracação do navio
* [ ] `[IA_Documental]` Automação total de conciliação de guias, pagamentos portuários e baixa de BL sem manuseio de planilhas manuais
* [ ] Outro: __________________________________

**11. (Opcional) Conte em 1 ou 2 frases: qual foi o imprevisto mais caro ou burocrático que você já enfrentou ao tentar retirar uma carga no Porto de Santos?**
* `[Campo de texto aberto / parágrafo]`

---

## BLOCO 6: Termo de Consentimento (LGPD e Avaliação da Banca)

**12. Você autoriza a utilização das informações consolidadas desta pesquisa para fins estritamente analíticos e acadêmicos no âmbito do Porto Hack Santos 2026?** *(Múltipla Escolha - 1 opção)*
* [ ] Sim, autorizo de forma anônima (apenas dados estatísticos / código da pesquisa).
* [ ] Sim, e autorizo contato posterior para validação da solução (deixar e-mail/WhatsApp no campo abaixo se desejar).
* [ ] Não autorizo.

**Contato opcional (LinkedIn, E-mail ou WhatsApp):**
* `[Campo de texto curto]`
