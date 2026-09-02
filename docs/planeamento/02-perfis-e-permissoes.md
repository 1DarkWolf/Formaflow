# Tópico 02 - Perfis e permissões

## 1. Objetivo

Este documento define quem poderá utilizar o Forma Flow, que informação cada perfil poderá consultar ou alterar e quais as regras de autorização que deverão ser respeitadas durante a implementação.

O sistema terá três perfis principais: **Administrador**, **Gestor/RH** e **Candidato/colaborador**. O IEFP e as entidades formadoras serão registados como intervenientes, mas não serão utilizadores autenticados no MVP.

## 2. Princípios de acesso

O controlo de acesso deverá seguir estes princípios:

1. **Acesso mínimo necessário:** cada utilizador recebe apenas as permissões indispensáveis às suas funções.
2. **Negação por defeito:** uma ação que não esteja expressamente permitida deverá ser recusada.
3. **Separação por organização:** um gestor só poderá aceder aos dados das empresas às quais estiver associado.
4. **Privacidade entre candidatos:** um candidato nunca poderá consultar os dados pessoais ou documentos de outro candidato, mesmo quando ambos pertencem à mesma candidatura empresarial.
5. **Validação no servidor:** esconder botões na interface não será considerado uma medida de segurança; todas as ações serão validadas pelo Django.
6. **Rastreabilidade:** alterações sensíveis deverão guardar o autor, a data e a ação efetuada.
7. **Preservação do histórico:** candidaturas, documentos e eventos relevantes não deverão desaparecer através de uma eliminação comum.
8. **Permissões acumuladas com contexto:** um utilizador poderá ser candidato e gestor, mas as suas permissões dependerão do papel e da empresa selecionados em cada operação.

## 3. Perfis do sistema

### 3.1. Administrador

O Administrador gere o funcionamento global do Forma Flow. Terá acesso a todas as organizações e será responsável por:

- criar, ativar, desativar e desbloquear contas;
- atribuir ou retirar perfis e associações a empresas;
- gerir empresas e o catálogo de entidades formadoras;
- consultar e corrigir dados de qualquer candidatura quando necessário;
- configurar regras, limites, tipos de documentos, estados e prazos;
- consultar relatórios globais e registos de auditoria;
- intervir em situações que não possam ser resolvidas pelos gestores;
- manter os dados fictícios utilizados na demonstração.

O acesso global do Administrador não elimina a obrigação de registar as ações sensíveis no histórico.

### 3.2. Gestor ou responsável de recursos humanos

O Gestor/RH trabalha dentro de uma ou mais empresas às quais esteja associado. Poderá:

- consultar e atualizar os dados da empresa sob a sua responsabilidade;
- associar candidatos ou colaboradores à empresa;
- gerir beneficiários, formações e candidaturas da empresa;
- criar candidaturas empresariais e adicionar os respetivos trabalhadores;
- apoiar candidaturas individuais que lhe tenham sido atribuídas;
- carregar e verificar documentos dentro do seu âmbito;
- registar pedidos de elementos adicionais e respetivas respostas;
- atualizar estados com base nos acontecimentos registados no Iefponline;
- acompanhar termos de aceitação, desistências e encerramentos;
- controlar prazos, notificações, estimativas financeiras e relatórios da empresa.

Um Gestor/RH não poderá consultar empresas às quais não esteja associado, promover-se a Administrador nem alterar regras globais do sistema.

### 3.3. Candidato ou colaborador

O Candidato/colaborador terá acesso apenas à sua informação. Poderá:

- criar e acompanhar uma candidatura individual própria;
- consultar a parte que lhe diz respeito numa candidatura empresarial;
- editar uma candidatura individual enquanto estiver em rascunho;
- completar os seus dados e carregar documentos pessoais;
- responder a tarefas ou pedidos de elementos que lhe sejam dirigidos;
- consultar prazos, notificações, estados e histórico visível;
- registar a entrega do seu termo de aceitação ou um pedido de desistência;
- fornecer os elementos necessários ao encerramento;
- consultar a estimativa de apoio que lhe diga respeito.

O Candidato não poderá consultar outros trabalhadores, validar os próprios documentos, alterar decisões oficiais, modificar regras ou aceder a relatórios internos da empresa.

### 3.4. Intervenientes sem autenticação no MVP

As entidades seguintes existirão como dados de referência, sem conta própria:

- IEFP e respetivas delegações regionais;
- entidades formadoras;
- outros serviços externos referidos no processo.

Os seus atos serão registados manualmente por um Administrador ou Gestor/RH, sempre identificados como acontecimentos externos. Uma área própria para estes intervenientes ficará reservada para uma fase posterior.

## 4. Identidade e associações

- Cada pessoa terá uma única conta de utilizador, identificada por email único.
- O Administrador será um perfil global e não dependerá de uma empresa.
- Um Gestor/RH poderá estar associado a uma ou mais empresas.
- Um Candidato poderá estar associado a uma empresa como colaborador e continuar a ter candidaturas individuais.
- A associação a uma empresa terá estado ativo ou inativo e datas de início e fim.
- A desativação de uma associação impedirá novos acessos aos dados da empresa sem apagar o histórico anterior.
- Uma candidatura empresarial pertencerá a uma empresa; uma candidatura individual pertencerá ao candidato.
- Um gestor só poderá apoiar uma candidatura individual quando existir uma atribuição explícita.
- As permissões serão calculadas a partir do utilizador, do perfil, da associação à empresa, da relação com o objeto e do estado atual do processo.

## 5. Criação e ciclo de vida das contas

### 5.1. Administrador

A primeira conta de Administrador será criada por um comando de administração do Django. Apenas outro Administrador poderá criar ou promover novas contas administrativas.

### 5.2. Gestor/RH

As contas de Gestor/RH serão criadas ou convidadas por um Administrador e associadas explicitamente às empresas que poderão gerir.

### 5.3. Candidato

O Candidato poderá:

- efetuar um registo individual com email único; ou
- receber um convite de um Gestor/RH para ficar associado a uma empresa.

Aceitar um convite empresarial não dará ao candidato acesso aos restantes colaboradores da empresa.

### 5.4. Estados da conta

Uma conta poderá estar:

- **pendente**, quando ainda aguarda ativação ou confirmação;
- **ativa**, quando pode iniciar sessão;
- **inativa**, quando o acesso foi suspenso sem apagar os dados;
- **bloqueada**, após um evento de segurança ou intervenção administrativa.

A eliminação definitiva de contas com histórico associado não estará disponível nas operações normais do MVP.

## 6. Matriz de permissões

Legenda:

- **Global:** acesso a todos os registos.
- **Empresa:** acesso limitado às empresas associadas ao gestor.
- **Próprio:** acesso limitado aos dados do próprio candidato.
- **Atribuído:** acesso apenas quando existe uma relação explícita com o processo.
- **Não:** ação não permitida.

| Área ou ação | Administrador | Gestor/RH | Candidato |
| --- | --- | --- | --- |
| Iniciar e terminar sessão | Próprio | Próprio | Próprio |
| Alterar o próprio perfil e palavra-passe | Próprio | Próprio | Próprio |
| Criar e gerir Administradores | Global | Não | Não |
| Criar, ativar ou desativar Gestores/RH | Global | Não | Não |
| Convidar ou associar candidatos | Global | Empresa | Não |
| Atribuir perfis e permissões | Global | Não | Não |
| Consultar empresas | Global | Empresa | Apenas identificação da empresa associada |
| Criar, editar ou arquivar empresas | Global | Apenas dados permitidos da própria empresa | Não |
| Gerir catálogo de entidades formadoras | Global | Criar proposta e consultar | Apenas entidade ligada à sua formação |
| Gerir beneficiários | Global | Empresa | Próprio |
| Gerir formações empresariais | Global | Empresa | Consultar as suas |
| Gerir formação de candidatura individual | Global | Atribuído | Próprio, enquanto permitido pelo estado |
| Criar candidatura empresarial | Global | Empresa | Não |
| Criar candidatura individual | Global | Para candidato da empresa ou atribuído | Próprio |
| Consultar candidatura empresarial | Global | Empresa | Apenas a sua participação |
| Consultar candidatura individual | Global | Atribuído | Próprio |
| Editar candidatura em rascunho | Global | Empresa ou atribuído | Próprio, apenas individual |
| Adicionar trabalhadores a candidatura | Global | Empresa | Não |
| Consultar dados de outros candidatos | Global | Empresa, quando necessário ao processo | Não |
| Carregar documentos | Global | Empresa ou atribuído | Apenas documentos próprios solicitados |
| Consultar documentos | Global | Empresa ou atribuído | Apenas documentos próprios e partilhados consigo |
| Validar ou rejeitar documentos | Global | Empresa ou atribuído | Não |
| Eliminar definitivamente documentos | Apenas operação administrativa excecional | Não | Não |
| Registar submissão no Iefponline | Global | Empresa ou atribuído | Próprio, em candidatura individual |
| Alterar estados administrativos | Global | Empresa ou atribuído | Não |
| Consultar histórico | Global | Empresa ou atribuído | Apenas histórico visível do próprio processo |
| Gerir pedidos de elementos adicionais | Global | Empresa ou atribuído | Responder aos pedidos que lhe forem dirigidos |
| Registar termo de aceitação | Global | Empresa ou atribuído | Próprio |
| Registar ou pedir desistência | Global | Empresa ou atribuído | Próprio |
| Gerir pedido de encerramento | Global | Empresa ou atribuído | Fornecer os seus elementos |
| Configurar regras e prazos | Global | Não | Não |
| Consultar prazos e tarefas | Global | Empresa ou atribuído | Próprio |
| Justificar uma alteração manual de prazo | Global | Empresa ou atribuído | Não |
| Consultar notificações | Global | Empresa ou atribuído | Próprio |
| Marcar notificações como lidas | Próprio | Próprio | Próprio |
| Consultar estimativas financeiras | Global | Empresa ou atribuído | Apenas valores próprios |
| Consultar relatórios | Global | Empresa | Apenas resumo pessoal |
| Consultar auditoria técnica | Global | Não | Não |
| Configurar o sistema | Global | Não | Não |

As ações indicadas como “atribuído” exigem uma relação registada entre o gestor e a candidatura. A permissão nunca deverá ser concedida apenas porque o utilizador conhece o endereço de uma página ou o identificador de um registo.

## 7. Regras especiais de privacidade

### 7.1. Candidaturas empresariais

Numa candidatura com vários trabalhadores:

- o Gestor/RH poderá consultar os participantes necessários à gestão do processo;
- cada Candidato verá apenas os seus dados, documentos, tarefas e valores;
- informação comum, como entidade formadora, formação e estado geral, poderá ser partilhada com todos os participantes;
- um documento pessoal nunca será apresentado a outro candidato;
- listagens destinadas a candidatos não revelarão nomes, emails, NIF, NISS ou outros identificadores dos colegas.

### 7.2. Documentos

- Os ficheiros não deverão ser publicados através de endereços públicos previsíveis.
- Cada visualização ou download deverá voltar a verificar a autorização do utilizador.
- O sistema deverá guardar o autor do envio, a data, o tipo de documento e o respetivo estado de validação.
- Substituir um documento deverá preservar a referência à versão anterior quando esta fizer parte do histórico do processo.
- Dados sensíveis não deverão ser incluídos em mensagens de erro, URLs ou registos técnicos.

### 7.3. Relatórios e exportações

- Um relatório deverá aplicar o mesmo âmbito de acesso utilizado nas páginas normais.
- Um Gestor/RH só poderá exportar dados das empresas que gere.
- Um Candidato só poderá exportar ou imprimir informação relativa a si próprio.
- As exportações deverão incluir apenas os campos necessários ao objetivo do relatório.

## 8. Regras de autorização por estado

Ter permissão sobre uma candidatura não significa poder executar qualquer ação em todos os momentos. O estado do processo também deverá ser verificado.

Exemplos:

- um rascunho poderá ser editado, mas uma candidatura marcada como submetida ficará bloqueada para alterações estruturais;
- um documento validado não poderá ser substituído sem reabrir a respetiva tarefa ou registar uma nova versão;
- uma candidatura encerrada ficará disponível para consulta, sem edição normal;
- uma desistência será uma transição registada e não uma eliminação da candidatura;
- mudanças excecionais feitas por um Administrador exigirão uma justificação no histórico.

As transições concretas serão definidas no Tópico 4 — Fluxo e estados da candidatura.

## 9. Ordem de verificação de uma ação

Para cada pedido, o sistema deverá verificar:

1. se o utilizador iniciou sessão;
2. se a conta está ativa;
3. qual é o perfil usado naquela ação;
4. se o objeto pertence ao âmbito global, empresarial, atribuído ou pessoal do utilizador;
5. se o perfil permite a ação pretendida;
6. se o estado atual do processo permite essa ação;
7. se a ação exige confirmação, motivo ou documento;
8. se deve ser criado um registo no histórico ou na auditoria.

Se uma destas verificações falhar, a operação deverá terminar sem alterar dados.

## 10. Comportamento perante acessos recusados

- Um visitante sem sessão será encaminhado para o início de sessão.
- Um utilizador autenticado sem permissão receberá uma resposta de acesso recusado.
- Quando a própria existência do registo for informação sensível, o sistema deverá responder como se o registo não existisse.
- As tentativas relevantes de acesso indevido deverão poder ser registadas para análise administrativa.
- A mensagem apresentada ao utilizador não deverá revelar dados internos nem informação de outras empresas.

## 11. Decisões para a futura implementação Django

Sem iniciar ainda a programação, ficam estabelecidas as seguintes decisões técnicas:

- será utilizado um modelo de utilizador personalizado desde a primeira migração;
- os perfis globais serão suportados pelo sistema de grupos e permissões do Django;
- as associações entre utilizadores, empresas e candidaturas serão representadas explicitamente na base de dados;
- as consultas à base de dados serão filtradas de acordo com o âmbito do utilizador;
- as verificações serão aplicadas nas páginas, formulários, downloads e restantes endpoints;
- a interface mostrará apenas as ações disponíveis, mas a segurança não dependerá da interface;
- operações sensíveis serão executadas através de regras de serviço reutilizáveis, evitando decisões contraditórias em páginas diferentes;
- alterações de perfis, estados, documentos e prazos ficarão registadas;
- contas inativas perderão imediatamente o acesso, mantendo os registos criados anteriormente.

## 12. Critérios de aceitação do Tópico 2

Na implementação futura, este tópico será considerado cumprido quando existirem testes que demonstrem que:

1. um Administrador consegue gerir utilizadores e organizações;
2. um Gestor/RH da Empresa A não consegue consultar ou alterar dados da Empresa B;
3. um Candidato consegue consultar os seus processos e documentos;
4. um Candidato não consegue consultar os dados de colegas da mesma candidatura;
5. um Candidato não consegue validar os próprios documentos nem alterar decisões administrativas;
6. um utilizador não obtém acesso através da introdução direta de um endereço proibido;
7. os downloads de documentos respeitam as mesmas permissões das páginas;
8. uma conta inativa ou bloqueada não consegue iniciar sessão;
9. uma mudança de perfil ou associação fica registada;
10. uma candidatura encerrada não pode ser editada por operações normais;
11. relatórios e pesquisas nunca devolvem registos fora do âmbito do utilizador;
12. todas as tentativas recusadas deixam os dados inalterados.

## 13. Resultado e ligação aos próximos tópicos

Ficam definidos os três perfis autenticados do MVP e as respetivas fronteiras de acesso. Estas decisões serão usadas para:

- atribuir responsabilidades às regras de negócio do Tópico 3;
- limitar as transições de estado definidas no Tópico 4;
- criar as relações entre utilizadores, empresas e candidaturas no modelo de dados do Tópico 5;
- orientar os testes de segurança e permissões durante a implementação.
