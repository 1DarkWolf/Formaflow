# Tópico 03 - Regras de negócio

## 1. Objetivo

Este documento transforma a informação de referência sobre o Cheque-Formação em regras verificáveis para o Forma Flow. Define condições de elegibilidade, validações, cálculos, prazos, documentos, alertas e restrições que orientarão o modelo de dados, o fluxo da candidatura e os testes.

O Forma Flow será uma plataforma de apoio e acompanhamento. Não decidirá se uma candidatura é aprovada, não confirmará oficialmente a elegibilidade de pessoas ou entidades e não substituirá o Iefponline, o IEFP ou a regulamentação aplicável.

## 2. Validade e hierarquia das regras

Os documentos de consulta disponibilizados têm datas entre 2015 e 2023. Por esse motivo, os valores e condições neles encontrados serão usados para planear e demonstrar o sistema, mas deverão ser confirmados em fontes oficiais atualizadas antes de qualquer utilização real.

Em caso de conflito, será seguida esta ordem:

1. legislação e regulamento oficial em vigor;
2. orientações oficiais publicadas pelo IEFP;
3. manual atualizado do Iefponline;
4. decisões de configuração aprovadas pelo Administrador;
5. regras internas de organização e interface do Forma Flow.

Uma regra externa nunca deverá ser alterada silenciosamente. A configuração deverá guardar a versão, fonte, data de início de vigência, data de fim e utilizador responsável pela alteração.

## 3. Tipos de regra

Cada regra será classificada num dos seguintes tipos:

- **Bloqueio:** impede que uma operação avance no Forma Flow.
- **Aviso:** alerta para uma possível irregularidade, permitindo continuação justificada por um utilizador autorizado.
- **Cálculo:** produz um prazo, limite ou estimativa.
- **Tarefa:** cria uma ação pendente para um utilizador.
- **Registo:** exige dados ou comprovativos, mas depende de confirmação externa.

Também será identificada a origem:

- **Externa:** resulta dos documentos de referência ou de uma regra oficial.
- **Interna:** foi definida para garantir coerência, segurança ou boa utilização do Forma Flow.
- **Configurável:** possui valores que podem mudar sem alteração do código.

## 4. Regras de elegibilidade do beneficiário

### RN-ELG-001 — Idade mínima

- O beneficiário deverá ter, pelo menos, 16 anos na data de apresentação da candidatura.
- A idade será calculada a partir da data de nascimento e da data de submissão.
- A falta da data de nascimento será um bloqueio à validação da candidatura.
- O valor mínimo ficará configurável.

### RN-ELG-002 — Ativo empregado

- Um ativo empregado poderá ser beneficiário independentemente do nível de qualificação.
- A candidatura poderá ser registada pelo próprio ou pela respetiva entidade empregadora.
- A situação laboral deverá ser comprovada através do documento aplicável.

### RN-ELG-003 — Desempregado

Na data de apresentação, o desempregado deverá:

- estar inscrito no IEFP há pelo menos 90 dias consecutivos;
- ter idade igual ou superior a 16 anos;
- possuir nível de qualificação entre 3 e 6, inclusive;
- possuir Plano Pessoal de Qualificação (PPQ);
- possuir Plano Pessoal de Emprego (PPE).

Estes valores serão configuráveis. O Forma Flow poderá calcular o tempo de inscrição e validar a presença dos dados e documentos, mas a confirmação oficial continuará a pertencer ao IEFP.

### RN-ELG-004 — Procura ativa de emprego

- O desempregado deverá manter a procura ativa de emprego durante a formação.
- A procura deverá decorrer fora dos horários da formação.
- O sistema registará uma declaração ou confirmação manual; não tentará verificar automaticamente a procura de emprego.

### RN-ELG-005 — Momento da verificação

- As condições do beneficiário serão verificadas com referência à data de submissão.
- Se a situação perante o emprego mudar durante o período de apoio, os limites e apoios deverão ser reavaliados na data da alteração.
- O sistema guardará o histórico da situação profissional, evitando substituir retroativamente os dados usados numa candidatura anterior.

### RN-ELG-006 — Limites acumulados por beneficiário

- Os limites de horas e apoio serão calculados por beneficiário, incluindo candidaturas individuais e candidaturas apresentadas por entidades empregadoras.
- O período de referência será de dois anos a contar da data de submissão da primeira candidatura deferida.
- O cálculo considerará todas as candidaturas aprovadas do beneficiário dentro desse período.
- Se faltarem dados de candidaturas externas ao Forma Flow, o resultado será apresentado como estimativa incompleta e exigirá confirmação manual.

### RN-ELG-007 — Regularidade do titular

- O titular e os beneficiários diretos deverão ter a situação tributária e contributiva regularizada, quando aplicável.
- O titular não deverá apresentar processos em situação irregular perante o IEFP.
- O Forma Flow registará documentos, autorizações de consulta ou confirmações manuais, sem consultar automaticamente os sistemas oficiais no MVP.

### RN-ELG-008 — Âmbito territorial

- O conjunto inicial de regras corresponde ao regulamento indicado para Portugal Continental.
- Um processo de outra região deverá usar um conjunto de regras próprio ou ficar sinalizado para verificação manual.
- O sistema não aplicará automaticamente regras de Portugal Continental a processos das Regiões Autónomas.

## 5. Regras da entidade empregadora

### RN-EMP-001 — Tipo de entidade

Poderão apresentar candidaturas empresariais pessoas coletivas ou singulares de direito privado, com ou sem fins lucrativos, relativamente aos seus trabalhadores.

### RN-EMP-002 — Condições da entidade

A entidade deverá declarar e comprovar, quando aplicável, que:

1. está regularmente constituída e registada;
2. tem a situação tributária e contributiva regularizada;
3. cumpre os requisitos legais para exercer a atividade ou iniciou o processo aplicável;
4. não está em incumprimento relativamente a apoios financeiros do IEFP;
5. dispõe de contabilidade organizada;
6. não foi condenada por factos relacionados com fundos estruturais;
7. não apresenta salários em atraso, sem prejuízo das exceções previstas;
8. não foi condenada por violações graves da legislação laboral sobre discriminação no período aplicável;
9. não foi condenada por despedimento ilegal de grávidas, puérperas ou lactantes no período aplicável.

Estas condições constituirão uma checklist declarativa e documental. O Forma Flow não fará validação jurídica, fiscal ou criminal automática.

### RN-EMP-003 — Manutenção das condições

- As condições da entidade deverão existir na apresentação e manter-se durante o apoio financeiro.
- Uma alteração relevante criará um alerta e uma tarefa de revisão.

### RN-EMP-004 — Situações de recuperação

- Se a entidade indicar um Processo Especial de Revitalização (PER/CIRE), será exigido o comprovativo correspondente.
- Se indicar um processo SREVE, será exigido o respetivo comprovativo.
- A seleção de uma destas situações mudará dinamicamente a checklist de documentos.

## 6. Regras da candidatura

### RN-CAN-001 — Tipos de candidatura

O sistema suportará:

- candidatura individual de ativo empregado;
- candidatura individual de desempregado;
- candidatura de entidade empregadora para os seus trabalhadores.

O tipo escolhido determinará os campos, limites, documentos, apoios e permissões aplicáveis.

### RN-CAN-002 — Preenchimento progressivo

- A candidatura poderá ser guardada como rascunho em várias etapas.
- A gravação de um rascunho não exigirá que todos os campos estejam completos.
- A validação final verificará todos os campos e documentos obrigatórios.
- Sair sem gravar não conservará alterações posteriores à última gravação.

### RN-CAN-003 — Candidatura empresarial

- Uma candidatura empresarial poderá incluir entre 1 e 20 trabalhadores.
- O limite de 20 ficará configurável.
- Cada trabalhador terá a sua própria formação, entidade formadora, documentos, custos, horas e estimativa de apoio.
- Trabalhadores diferentes poderão frequentar ações e entidades formadoras diferentes dentro da mesma candidatura.
- O total da candidatura será a soma dos resultados individuais dos beneficiários.

### RN-CAN-004 — Associação do trabalhador

- O trabalhador deverá estar previamente identificado e associado à entidade empregadora.
- O registo do identificador externo do Iefponline será uma confirmação manual opcional no MVP.
- O mesmo trabalhador não poderá ser adicionado duas vezes à mesma candidatura e ação de formação.
- Possíveis duplicações entre candidaturas ou formações sobrepostas originarão um aviso.

### RN-CAN-005 — Validação antes da submissão

Uma candidatura só poderá ser marcada como pronta para submissão quando:

- o titular estiver identificado;
- todos os beneficiários cumprirem as validações internas de elegibilidade;
- existir pelo menos uma ação de formação por beneficiário;
- as entidades formadoras estiverem identificadas;
- custos, horas e datas forem coerentes;
- todos os campos e documentos obrigatórios para essa fase estiverem preenchidos;
- as declarações de compromisso e veracidade tiverem sido aceites.

Uma regra dependente de confirmação externa poderá manter a candidatura em “pronta com avisos”, desde que exista justificação e autorização do perfil adequado.

### RN-CAN-006 — Registo da submissão externa

- O Forma Flow não submeterá dados diretamente ao Iefponline.
- O utilizador registará manualmente a data de submissão e, quando exista, o número da candidatura ou processo externo.
- A data registada acionará os prazos de análise e bloqueará alterações estruturais comuns.
- Uma correção posterior exigirá motivo e ficará no histórico.

### RN-CAN-007 — Preservação da versão aplicada

No momento da submissão, o sistema guardará uma referência à versão das regras e configurações utilizadas. Uma alteração futura de limites não deverá modificar silenciosamente cálculos históricos.

### RN-CAN-008 — Eliminação e desistência

- Um rascunho sem histórico oficial poderá ser arquivado pelo utilizador autorizado.
- Uma candidatura submetida não poderá ser eliminada pelas operações normais.
- A desistência será uma ação registada, nunca uma eliminação.
- Remover um participante depois da submissão exigirá um acontecimento de exclusão ou desistência com motivo.

### RN-CAN-009 — Regime aberto e dotação

- As fontes descrevem o Cheque-Formação como uma medida de candidatura aberta.
- A criação de novas candidaturas no Forma Flow dependerá de uma configuração que indique se a medida está ativa.
- A aprovação oficial continuará limitada pela dotação orçamental aplicável ao ano e não será prevista automaticamente.

### RN-CAN-010 — Registo no Iefponline

- O titular deverá possuir o registo necessário no Iefponline para realizar a submissão oficial.
- O registo pessoal no portal é responsabilidade do próprio e não deverá ser delegado.
- O Forma Flow nunca solicitará nem guardará a palavra-passe do Iefponline.
- Poderá existir uma tarefa para confirmar que o registo externo foi realizado.

## 7. Regras da formação

### RN-FOR-001 — Entidade formadora

A formação deverá ser ministrada por:

- entidade certificada pela DGERT na área aplicável; ou
- entidade legalmente dispensada de certificação devido à sua natureza e âmbito de atuação.

O sistema guardará o tipo de enquadramento, a evidência, a data da verificação e quem a confirmou. Não consultará automaticamente a DGERT no MVP.

### RN-FOR-002 — Tipologia da formação

Cada formação será classificada como:

- **CNQ**, composta por UFCD do Catálogo Nacional de Qualificações;
- **extra-CNQ**, composta por conteúdos fora do catálogo;
- **mista**, com componentes CNQ e extra-CNQ.

A formação extra-CNQ ou a componente extra-CNQ exigirá fundamentação sobre a sua relevância para a empregabilidade ou requalificação.

### RN-FOR-003 — Organização das UFCD

- Uma ação poderá incluir várias UFCD.
- As UFCD poderão pertencer a um ou mais referenciais, desde que estejam integradas na mesma área de educação e formação.
- A área, código, designação e carga horária de cada componente deverão ser registados separadamente.

### RN-FOR-004 — Modalidade

A formação poderá decorrer presencialmente, a distância ou em regime misto.

### RN-FOR-005 — Datas

- A data de início não poderá ser anterior à data de submissão da candidatura.
- A data de fim não poderá ser anterior à data de início.
- A formação não deverá abranger mais de três anos civis, segundo a regra apresentada no manual de 2023.
- Datas anormalmente distantes da data atual originarão aviso para detetar erros de digitação.
- Quando a candidatura ainda for um rascunho, a comparação será feita com a data prevista de submissão e deverá ser repetida na submissão real.

### RN-FOR-006 — Formação anterior

Não será incluída no apoio formação frequentada antes da data de submissão da candidatura ou antes da vigência aplicável da medida.

### RN-FOR-007 — Pertinência

A análise da pertinência deverá considerar se a formação:

- melhora competências e desempenho individual;
- contribui para a produtividade;
- responde às necessidades do mercado de trabalho e à empregabilidade;
- se enquadra em áreas prioritárias aplicáveis;
- respeita o PPQ e, no caso de desempregados, a articulação com o PPE.

O Forma Flow apresentará esta lista para fundamentação e revisão, mas não emitirá uma decisão automática sobre a pertinência.

## 8. Regras de cálculo financeiro

Todos os resultados financeiros do Forma Flow serão identificados como **estimativas**. Os valores aprovados e pagos pelo IEFP, quando conhecidos, serão registados separadamente e prevalecerão sobre a estimativa.

### RN-FIN-001 — Janela de apoio

- Cada beneficiário terá uma janela de dois anos iniciada na submissão da primeira candidatura deferida.
- Dentro da janela, as horas e os montantes aprovados serão acumulados.
- Uma nova candidatura utilizará apenas o saldo de horas e montante ainda disponível.

### RN-FIN-002 — Ativo empregado

Valores de referência do regulamento de 2021:

- máximo de 50 horas no período de dois anos;
- valor de referência de 4 euros por hora;
- máximo acumulado de 175 euros;
- apoio não superior a 90% do custo total comprovadamente pago.

Estimativa por beneficiário:

```text
horas_elegíveis = horas_da_formação, se não exceder o saldo_de_horas
apoio_base = horas_elegíveis × valor_por_hora
apoio_estimado = mínimo(
    apoio_base,
    percentagem_máxima × custo_declarado_ou_pago,
    saldo_do_montante_máximo
)
```

Na preparação da candidatura será usado o custo declarado; no apuramento final será usado o custo comprovadamente pago. Se o saldo de horas for insuficiente para a ação completa, a candidatura ficará bloqueada para validação até correção ou confirmação externa justificada.

### RN-FIN-003 — Desempregado

Valores de referência do regulamento de 2021:

- máximo de 150 horas no período de dois anos;
- apoio correspondente ao custo total comprovadamente pago;
- máximo acumulado de 500 euros.

Estimativa por beneficiário:

```text
horas_elegíveis = horas_da_formação, se não exceder o saldo_de_horas
apoio_estimado = mínimo(custo_declarado_ou_pago, saldo_do_montante_máximo)
```

Na preparação será usado o custo declarado e no apuramento final o custo comprovadamente pago. Se a ação ultrapassar o saldo de horas, deverá ser revista antes da validação.

### RN-FIN-004 — Apoios sociais para desempregados

Os apoios sociais só serão considerados quando forem pedidos na candidatura e não forem atribuídos pela entidade formadora:

- bolsa de formação;
- subsídio de refeição;
- despesas de transporte coletivo.

A bolsa de formação seguirá a fórmula de referência:

```text
bolsa = horas_frequentadas × valor_base_da_bolsa × 12 / (52 × 30)
valor_base_da_bolsa = 35% do IAS aplicável
```

O subsídio de refeição será considerado apenas nos dias com três ou mais horas de formação. O transporte dependerá dos custos comprovados e dos dias de frequência. O IAS, o valor diário de refeição e outros limites ficarão configuráveis por vigência.

### RN-FIN-005 — Não acumulação de financiamento

- A formação não poderá já beneficiar de cofinanciamento público.
- O Cheque-Formação não deverá financiar formação exigida no âmbito de outro apoio público ao emprego.
- A aplicação recolherá declarações e comprovativos, mas não confirmará automaticamente todos os financiamentos externos.

### RN-FIN-006 — Titularidade bancária

- O pagamento será associado ao titular da candidatura.
- O titular deverá ser também titular da conta bancária indicada.
- IBAN e comprovativo de titularidade serão tratados como dados sensíveis.

### RN-FIN-007 — Prestações

Segundo as fontes de referência:

- a primeira prestação, correspondente a 50%, é processada após a entrega do termo de aceitação e do comprovativo do pagamento total da formação, com prazo de referência de cinco dias úteis contado da entrega do último desses documentos;
- o valor remanescente é processado depois da confirmação da frequência e conclusão, com prazo de referência de dez dias úteis;
- os apoios sociais são pagos no final do processo, após os comprovativos aplicáveis.

O sistema acompanhará documentos, datas, valores previstos e valores efetivos, sem considerar automaticamente um pagamento como realizado.

## 9. Regras documentais

### RN-DOC-001 — Checklist dinâmica

A lista de documentos obrigatórios dependerá de:

- tipo de candidatura;
- situação profissional de cada beneficiário;
- tipo de formação;
- fase do processo;
- apoios sociais pedidos;
- existência de PER/CIRE ou SREVE;
- pedidos de elementos adicionais.

### RN-DOC-002 — Formato e tamanho

- Para preparar compatibilidade com o manual do Iefponline de 2023, o formato inicial permitido será PDF.
- O tamanho máximo inicial será 2 MB por ficheiro.
- Formato e tamanho serão configuráveis, pois correspondem a regras de uma plataforma externa que podem mudar.
- O sistema validará extensão, tipo real do ficheiro e tamanho, e não apenas o nome.

### RN-DOC-003 — Documentos da entidade empregadora

Consoante a fase e situação, poderão ser exigidos:

- pacto social ou declaração de início de atividade;
- comprovativos ou autorizações de consulta da situação tributária e contributiva;
- último mapa de pessoal aplicável;
- PPQ dos trabalhadores, quando aplicável;
- comprovativo de pagamento discriminado por ação e trabalhador;
- documentos de PER/CIRE ou SREVE, quando aplicável;
- comprovativo de titularidade bancária e IBAN;
- declaração da entidade formadora;
- certificados emitidos através do SIGO.

### RN-DOC-004 — Documentos do ativo empregado

Consoante a fase, poderão ser exigidos:

- PPQ, quando aplicável;
- declaração da entidade patronal ou declaração de início de atividade;
- comprovativos ou autorizações de consulta da situação tributária e contributiva;
- curriculum vitae;
- comprovativo de pagamento da formação;
- comprovativo de titularidade bancária e IBAN;
- declaração da entidade formadora;
- certificado de qualificações ou de formação profissional.

### RN-DOC-005 — Documentos do desempregado

Consoante a fase, poderão ser exigidos:

- curriculum vitae;
- PPE emitido pelo Serviço de Emprego;
- PPQ emitido por um Centro Qualifica;
- comprovativos ou autorizações de consulta da situação tributária e contributiva;
- comprovativo de pagamento da formação;
- comprovativos de transporte, quando pedido;
- comprovativo de titularidade bancária e IBAN;
- declaração da entidade formadora;
- certificado de qualificações ou de formação profissional.

### RN-DOC-006 — Declaração da entidade formadora

A declaração deverá permitir registar, por formando e ação:

- entidade formadora e NIPC;
- formação e códigos CNQ aplicáveis;
- carga horária e horas efetivamente frequentadas;
- local e datas reais de início e fim;
- número de dias com pelo menos três horas;
- valor pago;
- apoios sociais atribuídos pela entidade formadora;
- declaração de inexistência de outro financiamento aplicável;
- data, identificação e assinatura do responsável.

### RN-DOC-007 — Estado e versões

Um requisito documental poderá estar **em falta**, **recebido**, **em validação**, **válido**, **inválido**, **substituído** ou **dispensado com justificação**.

- Um candidato não poderá validar os seus próprios documentos.
- Substituir um ficheiro preservará a versão anterior e o motivo.
- A dispensa de um documento obrigatório exigirá autorização e justificação.
- A validação guardará o utilizador, data e observação.

## 10. Regras de análise e elementos adicionais

### RN-ANA-001 — Prazo de decisão

- O prazo máximo de referência para decisão será de 30 dias úteis após a submissão.
- A aprovação dependerá também da dotação orçamental oficial, que não será conhecida automaticamente pelo Forma Flow.
- A data calculada será apresentada como previsão, não como compromisso assumido pelo Forma Flow.

### RN-ANA-002 — Pedido de elementos adicionais

- Um pedido poderá conter uma ou mais questões.
- Cada questão terá texto, destinatário, prazo, estado e eventual tipo de documento pedido.
- A resposta textual será obrigatória quando a questão assim o exigir.
- Será possível guardar respostas em rascunho.
- O envio será considerado completo apenas quando todas as questões obrigatórias estiverem respondidas e os documentos exigidos tiverem sido anexados.

### RN-ANA-003 — Suspensão e retoma

- O pedido de elementos adicionais suspenderá a contagem do prazo de decisão.
- O prazo de referência para resposta será de 10 dias úteis.
- Para efeitos de acompanhamento interno, o relógio retomará quando a resposta completa for registada como enviada.
- Como a data oficial de retoma pode depender do IEFP, um Gestor/RH ou Administrador poderá corrigi-la mediante justificação.
- Pedidos sucessivos serão tratados como períodos de suspensão separados e não poderão sobrepor-se sem validação.

### RN-ANA-004 — Resultados da análise

O resultado oficial será registado manualmente como aprovação, indeferimento, arquivamento ou outro resultado previsto no fluxo. A decisão deverá guardar data, origem, observação e documento de notificação.

Entre os motivos de indeferimento de referência encontram-se:

- incumprimento das condições de acesso ou financiamento;
- documentação obrigatória em falta;
- falta de pertinência da formação;
- entidade formadora sem certificação ou dispensa aplicável;
- indisponibilidade de dotação orçamental, tratada nas fontes como arquivamento.

O sistema poderá assinalar riscos, mas não escolherá o resultado oficial.

## 11. Regras do termo de aceitação

### RN-ACE-001 — Prazo

- Após notificação de aprovação, o termo de aceitação deverá ser devolvido no prazo de 10 dias úteis.
- O prazo começa na data registada da notificação.
- A ausência da data de notificação impedirá o cálculo e criará uma tarefa de correção.

### RN-ACE-002 — Forma

- O termo deverá ser assinado pelo titular e devidamente autenticado nos termos aplicáveis.
- Em situações excecionais poderão ser aceites assinaturas digitais.
- Para pessoas coletivas, a assinatura digital deverá usar o mecanismo profissional aplicável, referido nas fontes como SCAP.
- O sistema registará o tipo de assinatura e a confirmação manual; não validará criptograficamente a assinatura no MVP.

### RN-ACE-003 — Incumprimento do prazo

A falta de devolução atempada poderá provocar caducidade da aprovação e extinção por incumprimento, salvo fundamentação aceite pelo IEFP. O Forma Flow deverá:

- gerar alertas antes do limite;
- marcar o prazo como ultrapassado;
- permitir registar uma justificação e a decisão externa;
- nunca declarar automaticamente a caducidade oficial.

## 12. Regras de desistência

### RN-DES-001 — Momento permitido

- A desistência normal será permitida antes da análise ou validação do processo pelo IEFP.
- Para candidaturas empresariais, as fontes indicam que a desistência total é possível enquanto ainda não existir número de processo.
- Para candidaturas individuais, o manual associa a operação ao estado externo “Em verificação de candidatura”.

### RN-DES-002 — Registo

- A desistência exigirá confirmação e motivo.
- O estado anterior, autor, data e observações serão preservados.
- Depois do ponto permitido, o sistema criará um pedido para tratamento manual em vez de executar uma desistência comum.

## 13. Regras de encerramento

### RN-ENC-001 — Prazo de entrega

O pedido e os documentos finais deverão ser submetidos até dois meses após o fim da formação, de acordo com as fontes de referência. O sistema calculará a data limite a partir da data real de fim.

### RN-ENC-002 — Documentos finais

Serão necessários, conforme o caso:

- comprovativo de frequência;
- certificado de qualificações para componentes CNQ;
- certificado de formação profissional para componentes extra-CNQ;
- ambos os certificados numa formação mista;
- declaração da entidade formadora;
- comprovativo do pagamento total;
- comprovativos dos apoios sociais pedidos.

Numa candidatura empresarial, os requisitos serão controlados por trabalhador e ação deferida.

### RN-ENC-003 — Condições de certificação

- A formação CNQ deverá ser associada ao certificado de qualificações emitido através do SIGO.
- A formação extra-CNQ deverá ser associada ao certificado de formação profissional.
- Uma formação mista exigirá os comprovativos correspondentes às duas componentes.
- A conclusão deverá ser registada com aproveitamento quando essa condição for aplicável.

### RN-ENC-004 — Submissão do pedido

- O pedido de encerramento só ficará disponível quando os documentos obrigatórios estiverem presentes e válidos.
- Para entidades empregadoras, o carregamento dos documentos antecederá a submissão do pedido.
- A submissão guardará uma fotografia dos documentos incluídos, evitando que uma substituição posterior altere silenciosamente o pedido enviado.

## 14. Incumprimento e restituição

### RN-INC-001 — Registo de risco

Situações como falta de certificado, incumprimento de obrigações ou impossibilidade de frequência poderão originar restituição total ou parcial. O Forma Flow gerará um risco e uma tarefa de análise, mas apenas registará uma restituição como efetiva depois de existir decisão externa.

### RN-INC-002 — Responsabilidade

- Numa candidatura empresarial, a restituição poderá ser total ou parcial por trabalhador.
- Uma impossibilidade superveniente, absoluta e definitiva poderá conduzir a restituição proporcional.
- Numa candidatura individual, o incumprimento poderá implicar restituição total.
- A falta do certificado até dois meses após a formação é identificada nas fontes como causa de restituição dos apoios recebidos.

### RN-INC-003 — Prazo de restituição

- O prazo de referência será de 60 dias consecutivos após a notificação.
- A falta de restituição poderá impedir novas candidaturas a iniciativas do IEFP nos dois anos seguintes.
- Juros, impedimentos e valores efetivos serão registados a partir da comunicação oficial e não calculados como decisão jurídica pelo sistema.

## 15. Prazos e calendário

### RN-PRZ-001 — Unidade do prazo

Cada tipo de prazo indicará expressamente se utiliza dias úteis, dias consecutivos ou meses de calendário.

### RN-PRZ-002 — Dias úteis

- O calendário excluirá fins de semana e feriados nacionais configurados.
- Feriados regionais ou municipais poderão ser adicionados quando relevantes.
- A regra exata de inclusão do dia inicial e final será configurável e documentada, porque deverá acompanhar a interpretação oficial em vigor.

### RN-PRZ-003 — Suspensões

Um prazo poderá ter vários períodos de suspensão. A data prevista será recalculada a partir da duração efetiva de cada suspensão, preservando os cálculos anteriores no histórico.

### RN-PRZ-004 — Alteração manual

Uma data limite calculada só poderá ser substituída por Gestor/RH dentro do seu âmbito ou por Administrador, sempre com motivo, autor, valor anterior e novo valor.

## 16. Notificações e prioridades

Estas são regras internas do Forma Flow, destinadas a concretizar a funcionalidade principal de monitorização automática.

### RN-NOT-001 — Eventos que geram avisos

Serão gerados avisos quando:

- um prazo se aproximar ou for ultrapassado;
- faltar um documento obrigatório;
- um documento for rejeitado ou estiver prestes a perder validade;
- existir um pedido de elementos adicionais sem resposta;
- um estado mudar;
- uma candidatura estiver pronta para a próxima etapa;
- os limites de horas ou apoio estiverem perto de ser atingidos;
- existir uma inconsistência de dados ou confirmação externa pendente.

### RN-NOT-002 — Limites de alerta

- Prazos em dias úteis terão avisos iniciais a cinco e dois dias úteis e no último dia.
- O encerramento terá avisos iniciais a 30, 15, 7, 3 e 1 dias consecutivos da data limite.
- Um prazo ultrapassado criará um aviso urgente e uma tarefa pendente.
- Todos os limites serão configuráveis por tipo de prazo.

### RN-NOT-003 — Destinatários

- O candidato receberá avisos relativos apenas aos seus dados, documentos e tarefas.
- O Gestor/RH receberá avisos dos processos que gere.
- O Administrador receberá avisos técnicos ou globais e poderá consultar os restantes no âmbito de supervisão.

### RN-NOT-004 — Prevenção de duplicados

Para o mesmo processo, regra e limite, será criada apenas uma notificação ativa. Uma alteração da data recalculará os avisos futuros sem apagar o histórico dos já emitidos.

### RN-NOT-005 — Estado do aviso

Uma notificação poderá estar não lida, lida, resolvida ou dispensada com motivo. Marcar uma notificação como lida não concluirá automaticamente a tarefa que lhe deu origem.

## 17. Regras de integridade e auditoria

### RN-INT-001 — Identificadores e duplicados

- NIF, NIPC, email e referências externas terão validação de formato e regras de unicidade adequadas ao respetivo âmbito.
- A aplicação alertará para possíveis duplicados antes de criar pessoas, entidades ou candidaturas.
- Um identificador válido em formato não será apresentado como confirmação oficial da identidade.

### RN-INT-002 — Valores e datas

- Horas, custos e montantes não poderão ser negativos.
- Uma quantidade de horas igual a zero não será válida para uma ação submetida.
- O custo pago não poderá exceder o custo declarado sem justificação.
- Datas reais de fim, frequência e pagamento não poderão ser inventadas pelo sistema.
- Valores desconhecidos permanecerão nulos, não serão substituídos por zero.

### RN-INT-003 — Histórico imutável

Mudanças de estado, regras aplicadas, documentos, prazos, decisões, valores oficiais e ações sensíveis gerarão entradas de histórico que não poderão ser editadas pelas operações normais.

### RN-INT-004 — Ações externas

Qualquer acontecimento ocorrido no Iefponline ou comunicado pelo IEFP deverá guardar:

- data do acontecimento;
- data em que foi registado no Forma Flow;
- utilizador que o registou;
- origem ou documento comprovativo;
- observação, quando necessária.

## 18. Parâmetros configuráveis iniciais

| Código | Parâmetro | Valor inicial de referência | Unidade |
| --- | --- | --- | --- |
| CFG-IDADE-MIN | Idade mínima | 16 | anos |
| CFG-DESEMP-INSCRICAO | Inscrição mínima do desempregado | 90 | dias consecutivos |
| CFG-DESEMP-NIVEL-MIN | Qualificação mínima do desempregado | 3 | nível |
| CFG-DESEMP-NIVEL-MAX | Qualificação máxima do desempregado | 6 | nível |
| CFG-JANELA-APOIO | Período de acumulação | 2 | anos |
| CFG-EMP-HORAS | Horas máximas do ativo empregado | 50 | horas |
| CFG-EMP-VALOR-HORA | Valor por hora do ativo empregado | 4 | euros/hora |
| CFG-EMP-MONTANTE | Apoio máximo do ativo empregado | 175 | euros |
| CFG-EMP-PERCENTAGEM | Percentagem máxima do custo | 90 | percentagem |
| CFG-DESEMP-HORAS | Horas máximas do desempregado | 150 | horas |
| CFG-DESEMP-MONTANTE | Apoio máximo do desempregado | 500 | euros |
| CFG-EMPRESA-BENEFICIARIOS | Trabalhadores por candidatura | 20 | trabalhadores |
| CFG-FICHEIRO-TAMANHO | Tamanho máximo de documento | 2 | MB |
| CFG-ANALISE-PRAZO | Decisão da candidatura | 30 | dias úteis |
| CFG-ELEMENTOS-PRAZO | Resposta a elementos adicionais | 10 | dias úteis |
| CFG-ACEITACAO-PRAZO | Devolução do termo de aceitação | 10 | dias úteis |
| CFG-PRIMEIRA-PRESTACAO | Processamento da primeira prestação | 5 | dias úteis |
| CFG-REMANESCENTE | Processamento do remanescente | 10 | dias úteis |
| CFG-ENCERRAMENTO | Entrega após o fim da formação | 2 | meses |
| CFG-RESTITUICAO | Restituição após notificação | 60 | dias consecutivos |
| CFG-IMPEDIMENTO | Impedimento referido após não restituição | 2 | anos |

O formato PDF permitido, o IAS, a percentagem do IAS, o valor diário do subsídio de refeição, os feriados e os limites de alerta também serão configurados com datas de vigência.

## 19. Matriz de aplicação das regras

| Grupo | Automático | Confirmação manual | Decisão externa |
| --- | --- | --- | --- |
| Idade, datas, horas e limites registados | Sim | Quando faltarem dados externos | Não |
| Presença de campos e documentos | Sim | Dispensas e exceções | Não |
| Situação fiscal, contributiva e laboral | Não | Sim | Entidade competente |
| Certificação ou dispensa da formadora | Não no MVP | Sim | DGERT ou enquadramento legal |
| Pertinência da formação | Checklist e avisos | Sim | IEFP |
| Estimativa financeira | Sim | Correção justificada | IEFP define o valor oficial |
| Prazos previstos | Sim | Ajustes e datas externas | IEFP confirma os efeitos oficiais |
| Aprovação, indeferimento e arquivamento | Não | Registo no sistema | IEFP |
| Restituição ou impedimento | Apenas alerta | Registo da comunicação | IEFP ou entidade competente |

## 20. Critérios de aceitação do Tópico 3

Na implementação futura, este tópico será considerado cumprido quando os testes demonstrarem que:

1. cada tipo de candidato recebe a checklist e os limites corretos;
2. idade e condições mensuráveis são avaliadas na data de submissão;
3. candidaturas empresariais não aceitam mais beneficiários do que o limite configurado;
4. horas e apoios são acumulados por beneficiário na janela aplicável;
5. as estimativas de empregados e desempregados respeitam os tetos definidos;
6. formações anteriores à submissão são bloqueadas;
7. formações CNQ, extra-CNQ e mistas exigem os dados e certificados adequados;
8. documentos inválidos em formato ou tamanho são recusados;
9. pedidos de elementos suspendem e retomam corretamente o prazo previsto;
10. dias úteis, dias consecutivos e meses são calculados de forma distinta;
11. o termo de aceitação e o encerramento geram avisos nos limites configurados;
12. um pedido de encerramento incompleto não pode ser submetido;
13. alterações manuais exigem motivo e ficam no histórico;
14. uma decisão externa nunca é criada apenas por um cálculo automático;
15. alterações de configuração não modificam resultados históricos já submetidos.

## 21. Fontes de referência utilizadas

### 21.1. Rastreabilidade por grupo de regras

| Grupo de regras | Referências principais consultadas |
| --- | --- |
| Beneficiários e elegibilidade | Regulamento de 2021, páginas 4 e 5; manual de 2023, páginas 3 e 6 |
| Entidades empregadoras | Regulamento de 2021, páginas 5, 13, 14 e 15 |
| Formação e entidades formadoras | Regulamento de 2021, página 6; manual de 2023, páginas 13 a 15, 19 e 22 a 24; Anexo 1 |
| Limites e cálculos financeiros | Regulamento de 2021, páginas 6 a 9 e 13; ficha síntese de 2019 |
| Submissão, análise e aceitação | Regulamento de 2021, páginas 10 a 13; manual de 2023, páginas 11 e 27 a 36 |
| Elementos adicionais e desistência | Manual de 2023, páginas 28 a 40; regulamento de 2021, páginas 11 e 12 |
| Documentos, certificação e encerramento | Regulamento de 2021, páginas 13 a 16; manual de 2023, páginas 16, 20, 25 e 40 a 46; Anexo 2 |

### 21.2. Ficheiros consultados

- `Cheque-formação_Regulamento específico - Cheque_Formacao_1_revisao_Regulamento_Especifico.pdf`, 1.ª revisão aprovada em 16 de dezembro de 2021.
- `Cheque-Formação - Manual utilizador - titular da candidatura.pdf`, edição identificada como abril/maio de 2023.
- `2019-03-28_Cheque-Formação - Ficha síntese_IEFPonline.pdf`, ficha síntese de 28 de março de 2019.
- `2015-09-15_Anexo 1_Entidades formadoras.pdf`, entidades dispensadas de certificação pela DGERT.
- `2015-09-15_Anexo 2_Declaracao_entidade_formadora.pdf`, modelo de declaração da entidade formadora.
- `informação_projeto.docx`, descrição e objetivos académicos do Forma Flow.
- `relatorio.docx` e `tabelas_final.xls`, modelo lógico desenvolvido nos módulos anteriores.
- Diagramas de casos de uso, classes e fases fornecidos para o projeto.

## 22. Confirmações pendentes antes de utilização real

Antes de utilizar o Forma Flow com processos reais, será obrigatório confirmar:

- se a medida e o respetivo regime continuam ativos;
- os beneficiários, condições de elegibilidade e documentos atualmente exigidos;
- os limites de horas, valores, percentagens, IAS e apoios sociais em vigor;
- os prazos e a forma oficial de os contar;
- os formatos, tamanhos e meios de entrega aceites pelo Iefponline;
- as entidades dispensadas de certificação e os meios atuais de confirmação;
- o tratamento atual de PER/CIRE, SREVE, assinaturas digitais e SCAP;
- os efeitos jurídicos de incumprimento, restituição e impedimento.

Até essa confirmação, todas as regras externas deste documento terão o estado **referência para demonstração académica**.

## 23. Resultado e ligação aos próximos tópicos

As regras ficam organizadas de modo a poderem ser implementadas e testadas sem confundir estimativas internas com decisões oficiais. O Tópico 4 utilizará estas regras para definir o fluxo e as transições de estado. O Tópico 5 transformará os intervenientes, configurações, comprovativos, períodos de suspensão e históricos aqui identificados em entidades e relações da base de dados.
