# Tópico 01 - Âmbito e objetivos

## 1. Identificação

| Campo | Definição |
| --- | --- |
| Nome | Forma Flow |
| Designação completa | Forma Flow - Sistema de Controlo e Avisos do Cheque-Formação |
| Tipo de projeto | Aplicação web para a Prova de Aptidão Profissional (PAP) |
| Tecnologia principal prevista | Python e Django |
| Idioma da interface | Português de Portugal |
| Estado | Âmbito inicial definido; implementação ainda não iniciada |

## 2. Contexto e problema

O acompanhamento de candidaturas ao Cheque-Formação pode envolver emails, folhas de cálculo, documentos locais e consultas ao portal Iefponline. Esta dispersão dificulta a consulta do estado de cada processo e aumenta o risco de:

- esquecimento de prazos;
- documentação em falta ou desatualizada;
- perda do histórico de decisões e alterações;
- dificuldade em acompanhar vários candidatos e ações de formação;
- falta de informação consolidada para gestores e departamentos de recursos humanos;
- atrasos no termo de aceitação e no pedido de encerramento;
- incumprimento das etapas necessárias ao recebimento dos apoios.

O Forma Flow pretende centralizar estes elementos e transformar o acompanhamento manual num processo organizado, rastreável e orientado por avisos.

## 3. Proposta de valor

O Forma Flow será uma plataforma de apoio à gestão. Permitirá preparar e acompanhar candidaturas, organizar os respetivos documentos, controlar estados e prazos, manter um histórico de alterações e alertar os utilizadores para ações pendentes.

A aplicação não substituirá o Iefponline nem tomará decisões oficiais em nome do IEFP. O seu propósito será ajudar empresas, gestores e candidatos a acompanhar, fora do portal oficial, toda a informação relevante para cada processo.

## 4. Objetivo geral

Desenvolver uma aplicação web segura e de utilização simples que centralize o acompanhamento das candidaturas ao Cheque-Formação e reduza falhas relacionadas com prazos, documentos, estados e comunicação.

## 5. Objetivos específicos

1. Gerir utilizadores com perfis e permissões diferentes.
2. Registar empresas, entidades formadoras e beneficiários.
3. Registar candidaturas individuais e candidaturas apresentadas por entidades empregadoras.
4. Permitir vários trabalhadores numa candidatura empresarial, até ao limite configurado.
5. Associar ações de formação e componentes CNQ, extra-CNQ ou mistas.
6. Organizar documentos por candidatura, beneficiário, tipo e fase.
7. Registar o estado atual e o histórico completo de cada candidatura.
8. Controlar prazos, suspensões, retomas e tarefas pendentes.
9. Gerar notificações sobre prazos, documentos e alterações de estado.
10. Apoiar pedidos de elementos adicionais, termos de aceitação, desistências e encerramentos.
11. Apresentar dashboards, pesquisas, filtros e relatórios de apoio à decisão.
12. Calcular estimativas de apoio financeiro sem as apresentar como decisões oficiais.

## 6. Público-alvo

### 6.1. Administrador

Responsável pela configuração e supervisão do sistema, incluindo utilizadores, permissões, entidades, regras e relatórios globais.

### 6.2. Gestor ou responsável de recursos humanos

Responsável por preparar e acompanhar processos, gerir beneficiários, validar documentos, registar alterações e controlar prazos.

### 6.3. Candidato ou colaborador

Beneficiário da formação que poderá consultar as suas candidaturas, enviar documentos e acompanhar notificações e tarefas.

### 6.4. Entidades registadas sem acesso inicial

O IEFP e as entidades formadoras serão representados como intervenientes do processo, mas não terão, na primeira versão, uma área de autenticação própria.

## 7. Âmbito funcional

Fazem parte do âmbito do projeto:

- autenticação e recuperação de acesso;
- gestão de perfis e permissões;
- gestão de empresas, representantes, candidatos e entidades formadoras;
- registo de ações e componentes de formação;
- criação progressiva de candidaturas com gravação em rascunho;
- associação de vários beneficiários a candidaturas empresariais;
- checklist de requisitos e documentos;
- upload e validação de documentos;
- fluxo controlado de estados;
- histórico de alterações e ações importantes;
- gestão de pedidos de elementos adicionais e respostas;
- controlo do termo de aceitação;
- gestão da desistência e do pedido de encerramento;
- cálculo e monitorização de prazos;
- notificações internas e preparação para notificações por email;
- dashboard com indicadores de estado, risco e documentação;
- pesquisa, filtros e relatórios;
- estimativas de apoios financeiros e registo do respetivo acompanhamento.

## 8. Fora do âmbito inicial

Não fazem parte da primeira versão:

- submissão automática de candidaturas ao Iefponline;
- integração direta com sistemas do IEFP, DGERT, SIGO, Autoridade Tributária ou Segurança Social;
- decisão automática sobre aprovação ou indeferimento;
- confirmação oficial da certificação de entidades formadoras;
- validação jurídica ou fiscal dos documentos;
- realização de pagamentos ou transferências bancárias;
- substituição dos regulamentos ou orientações oficiais;
- utilização de dados pessoais reais durante a demonstração escolar;
- aplicação móvel nativa;
- chat em tempo real entre utilizadores e serviços externos.

Estas funcionalidades poderão ser consideradas numa evolução futura, caso existam APIs, autorizações, tempo e condições de segurança adequadas.

## 9. Produto mínimo viável

O Produto Mínimo Viável (MVP) deverá demonstrar o valor central do Forma Flow e incluir:

1. Login e controlo de acesso por perfil.
2. Gestão de empresas, entidades formadoras e beneficiários.
3. Registo de formações.
4. Criação e consulta de candidaturas.
5. Suporte para candidaturas empresariais com vários trabalhadores.
6. Gestão de documentos e documentos em falta.
7. Mudança controlada de estado com histórico.
8. Registo e cálculo de prazos.
9. Geração automática de notificações internas.
10. Dashboard de processos, riscos e tarefas pendentes.
11. Pesquisa e filtros de candidaturas.
12. Dados fictícios suficientes para uma demonstração completa.

A monitorização automática de prazos será a principal funcionalidade além das operações tradicionais de criação, consulta, alteração e eliminação.

## 10. Funcionalidades posteriores ao MVP

- envio de emails reais;
- cálculo financeiro completo e configurável;
- exportação avançada para Excel ou PDF;
- modelos configuráveis de documentos e notificações;
- armazenamento externo protegido;
- relatórios estatísticos avançados;
- integração com serviços externos autorizados;
- configuração de fluxos diferentes para novas medidas de formação;
- autenticação multifator;
- aplicação móvel ou Progressive Web App.

## 11. Premissas e restrições

- A aplicação acompanhará manualmente acontecimentos registados no Iefponline.
- As regras recolhidas nos documentos de 2015 a 2023 serão consideradas referências e não uma garantia de vigência atual.
- Prazos, limites financeiros, tamanhos de ficheiro e quantidades máximas deverão ser configuráveis.
- O desenvolvimento deverá ser adequado ao calendário e aos objetivos académicos da PAP.
- A interface deverá ser responsiva e utilizável num computador ou telemóvel.
- Os dados de demonstração serão fictícios e não conterão informação pessoal real.
- A segurança e a separação dos dados por perfil e empresa serão requisitos obrigatórios.
- O código, a documentação e os testes serão mantidos neste repositório Git.

## 12. Critérios de sucesso

O projeto será considerado funcionalmente bem-sucedido quando:

- cada perfil visualizar apenas os dados e ações permitidos;
- for possível criar uma candidatura individual e uma candidatura empresarial;
- uma candidatura empresarial aceitar vários beneficiários;
- os documentos obrigatórios e em falta forem claramente identificados;
- todas as mudanças de estado ficarem registadas no histórico;
- os prazos forem calculados e originarem avisos automáticos;
- o dashboard apresentar informação coerente com os dados registados;
- o pedido de encerramento só puder avançar quando as condições definidas forem cumpridas;
- os fluxos principais forem cobertos por testes;
- a aplicação puder ser demonstrada sem erros bloqueadores.

## 13. Critérios de qualidade

- Estrutura de código clara e adequada às convenções do Django.
- Base de dados coerente, normalizada e preparada para evolução.
- Formulários com validações e mensagens compreensíveis.
- Interface consistente e acessível.
- Ficheiros carregados protegidos contra acesso indevido.
- Ausência de palavras-passe, chaves ou outros segredos no repositório.
- Testes para permissões, estados, documentos, prazos e notificações.
- Documentação suficiente para instalação, utilização e apresentação da PAP.

## 14. Entregáveis finais previstos

- código-fonte da aplicação Django;
- base de dados e migrações;
- conjunto de testes;
- dados fictícios para demonstração;
- manual de instalação;
- manual de utilizador;
- documentação técnica;
- relatório e apresentação atualizados;
- aplicação preparada para demonstração local ou publicação.

## 15. Dependências dos próximos tópicos

Este documento define a fronteira do projeto. Os tópicos seguintes deverão detalhar, por esta ordem:

1. perfis e permissões;
2. regras de negócio;
3. fluxo e estados da candidatura;
4. modelo de dados definitivo;
5. estrutura técnica e implementação Django.

Qualquer alteração futura ao âmbito deverá ser registada neste documento para evitar que funcionalidades importantes sejam adicionadas ou removidas sem uma decisão explícita.
