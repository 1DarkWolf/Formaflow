# Tópico 08 - Catálogo de casos de teste

## 1. Finalidade

Este catálogo reúne 116 cenários críticos do MVP. Cada linha é uma especificação curta que será transformada em um ou mais testes automatizados ou manuais quando a implementação for autorizada.

Os casos não substituem a cobertura parametrizada de todas as 72 regras `RN-*`, 23 transições `TR-*` e 56 ecrãs `ECR-*`. Funcionam como a base de aceitação e regressão de maior risco.

## 2. Campos de um caso

| Campo | Significado |
| --- | --- |
| `ID` | Identificador estável `CT-AREA-NNN` |
| `P` | Prioridade: `P0` crítica, `P1` alta, `P2` normal |
| `Referência` | Código ou tópico que justifica o teste |
| `Cenário` | Condição e ação essenciais |
| `Resultado esperado` | Comportamento observável necessário |

## 3. Dados fictícios comuns

| Código | Dados de teste |
| --- | --- |
| `CAN-A` | Candidato A, candidatura individual e perfil completo |
| `CAN-B` | Candidato B sem relação com A |
| `GER-A` | Gestor associado apenas à `EMP-A` |
| `GER-B` | Gestor associado apenas à `EMP-B` |
| `ADM-A` | Administrador autorizado |
| `INA-A` | Utilizador inativo |
| `EMP-A` | Empresa A com três trabalhadores fictícios |
| `EMP-B` | Empresa B sem relação com `GER-A` |
| `FOR-C` | Formadora certificada na área aplicável |
| `FOR-D` | Formadora dispensada de certificação |
| `FOR-P` | Formadora com enquadramento pendente |
| `REG-A` | Conjunto de regras publicado de referência |
| `REG-B` | Nova versão com parâmetros diferentes |

Todos os identificadores fiscais, contas, emails e ficheiros associados serão sintéticos.

## 4. Autenticação e contas

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-AUT-001` | P0 | T2 | Entrar com email normalizado e palavra-passe válida | Sessão criada e redirecionada para contexto permitido |
| `CT-AUT-002` | P0 | T2 | Entrar com palavra-passe incorreta | Acesso recusado sem indicar qual credencial falhou |
| `CT-AUT-003` | P0 | T2 | `INA-A` tenta iniciar sessão | Acesso recusado e nenhuma sessão autorizada criada |
| `CT-AUT-004` | P1 | `ECR-002` | Pedir recuperação para email existente e inexistente | Resposta pública equivalente nos dois casos |
| `CT-AUT-005` | P0 | T6 | Reutilizar token de recuperação já consumido | Nova palavra-passe não é alterada e token é recusado |
| `CT-AUT-006` | P1 | T6 | Terminar sessão e tentar reutilizar página autenticada | Sessão deixa de autorizar e página pede autenticação |
| `CT-AUT-007` | P1 | T5 | Criar emails iguais com maiúsculas diferentes | Restrição impede a segunda identidade normalizada |
| `CT-AUT-008` | P1 | T7 | Usar colar e gestor de palavras-passe no login | Controlo permite a operação e mantém etiqueta acessível |

## 5. Permissões e isolamento

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-PRM-001` | P0 | T2 | `CAN-A` abre candidatura de `CAN-B` por URL | Objeto e existência não são revelados |
| `CT-PRM-002` | P0 | T2 | `GER-A` abre candidatura da `EMP-B` | Acesso recusado e nenhuma informação é devolvida |
| `CT-PRM-003` | P0 | T2 | Associação de `GER-A` expira | Novos pedidos deixam imediatamente de ter âmbito |
| `CT-PRM-004` | P0 | T2 | Gestor sem atribuição tenta operação que a exige | Operação recusada sem alterar dados |
| `CT-PRM-005` | P0 | T2 | Candidato tenta registar decisão oficial | Operação não aparece e pedido direto é recusado |
| `CT-PRM-006` | P0 | T2 | Gestor tenta publicar regras | Operação recusada; apenas administrador autorizado publica |
| `CT-PRM-007` | P0 | T5 | Alterar `public_id` para objeto válido de outro âmbito | A resposta segura não confirma o objeto |
| `CT-PRM-008` | P0 | T7 | Consultar contagens do dashboard de `GER-A` | Métricas incluem apenas objetos autorizados de A |
| `CT-PRM-009` | P0 | T7 | Exportar lista filtrada | Exportação mantém o mesmo âmbito, filtros e campos permitidos |
| `CT-PRM-010` | P0 | T5 | Descarregar versão documental de outra empresa | Nenhum conteúdo ou endereço temporário é emitido |

## 6. Organizações e referências

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-ORG-001` | P1 | T5 | Criar empresas com o mesmo NIPC normalizado | Segunda empresa é recusada |
| `CT-ORG-002` | P1 | T5 | Criar formadoras com o mesmo NIPC normalizado | Segunda formadora é recusada no respetivo catálogo |
| `CT-ORG-003` | P1 | T5 | Associar o mesmo utilizador, empresa e papel duas vezes | Só existe uma associação ativa equivalente |
| `CT-ORG-004` | P1 | T5 | Terminar associação usada historicamente | Histórico permanece e acesso corrente termina |
| `CT-ORG-005` | P0 | `RN-CAN-004` | Associar trabalhador sem vínculo válido à empresa titular | Bloqueio ou aviso previsto é produzido sem inventar vínculo |
| `CT-ORG-006` | P1 | T5 | Criar vínculo com fim anterior ao início | Validação recusa o período |
| `CT-ORG-007` | P0 | `RN-FIN-006` | Conta de pagamento tem candidato e empresa preenchidos | Restrição exclusiva recusa o registo |
| `CT-ORG-008` | P0 | T5 | Apresentar conta bancária fora do formulário autorizado | Apenas os últimos quatro caracteres ficam visíveis |

## 7. Regras, parâmetros e calendário

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-CFG-001` | P0 | 72 `RN-*` | Executar matriz de vetores favoráveis e desfavoráveis | Cada código produz resultado e explicação esperados |
| `CT-CFG-002` | P0 | `RN-CAN-007` | Submeter com `REG-A` e publicar depois `REG-B` | Candidatura conserva `REG-A` e resultados históricos |
| `CT-CFG-003` | P0 | T5 | Editar parâmetro de conjunto publicado | Alteração recusada; exige nova versão |
| `CT-CFG-004` | P1 | T5 | Publicar períodos de vigência incoerentes | Sobreposição inválida é recusada |
| `CT-CFG-005` | P1 | `RN-PRZ-002` | Calcular prazo que atravessa fim de semana e feriado | Apenas dias úteis aplicáveis são contados |
| `CT-CFG-006` | P1 | `RN-PRZ-001` | Calcular dias consecutivos no mesmo período | Fins de semana permanecem incluídos |
| `CT-CFG-007` | P1 | T5 | Guardar parâmetro com tipo diferente de `tipo_valor` | Publicação é bloqueada com erro específico |
| `CT-CFG-008` | P1 | T3 | Usar regra marcada como referência de demonstração | Interface e cálculo conservam essa indicação |

## 8. Candidaturas e formação

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-CAN-001` | P0 | `RN-CAN-001` | Criar candidatura individual | Titular candidato preenchido, empresa nula e um beneficiário igual |
| `CT-CAN-002` | P0 | `RN-CAN-001` | Criar candidatura empresarial | Empresa preenchida, candidato titular nulo e beneficiários separados |
| `CT-CAN-003` | P0 | T5 | Preencher ambos os titulares ou nenhum | Restrição recusa a candidatura incoerente |
| `CT-CAN-004` | P0 | `RN-CAN-003` | Adicionar exatamente o limite empresarial | Operação aceite |
| `CT-CAN-005` | P0 | `RN-CAN-003` | Adicionar um beneficiário acima do limite | Operação recusada sem remover os existentes |
| `CT-CAN-006` | P1 | T5 | Adicionar o mesmo candidato duas vezes | Unicidade recusa a repetição |
| `CT-CAN-007` | P0 | T5 | Dois utilizadores editam a mesma versão | Segundo gravação recebe conflito e não substitui dados |
| `CT-CAN-008` | P1 | `RN-FOR-002` | Ação contém componentes CNQ e extra-CNQ | Tipologia derivada é `MISTA` |
| `CT-CAN-009` | P1 | `RN-FOR-002` | Componente extra-CNQ não tem justificação | Validação bloqueia a preparação |
| `CT-CAN-010` | P1 | T5 | Horas ou custos negativos numa participação | Base de dados ou serviço recusa os valores |

## 9. Documentos e ficheiros

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-DOC-001` | P0 | `RN-DOC-001` | Gerar checklist para condições diferentes | Só os requisitos aplicáveis são criados e explicados |
| `CT-DOC-002` | P1 | `RN-DOC-002` | Carregar PDF exatamente no limite configurado | Ficheiro aceite se restantes validações passarem |
| `CT-DOC-003` | P0 | `RN-DOC-002` | Carregar ficheiro um byte acima do limite | Upload recusado e não cria versão válida |
| `CT-DOC-004` | P0 | `RN-DOC-002` | Carregar executável renomeado para `.pdf` | Assinatura e MIME incompatíveis bloqueiam o ficheiro |
| `CT-DOC-005` | P0 | T5 | Nome original contém tentativa de caminho | Chave aleatória segura é usada e nome é sanitizado |
| `CT-DOC-006` | P0 | `RN-DOC-007` | Substituir versão corrente válida | Nova versão fica corrente e anterior preservada como substituída |
| `CT-DOC-007` | P0 | T5 | Duas versões tentam ficar correntes | Restrição permite apenas uma |
| `CT-DOC-008` | P0 | T5 | Substituir documento depois de snapshot | Snapshot continua ligado à versão originalmente submetida |
| `CT-DOC-009` | P0 | T6 | Storage falha durante upload | Transação não cria documento válido e temporário é tratável |
| `CT-DOC-010` | P0 | T2 | Pedido direto ao ficheiro sem autorização | Conteúdo, caminho e metadados sensíveis não são devolvidos |

## 10. Workflow, prazos e histórico

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-WFL-001` | P0 | `TR-001`–`TR-023` | Executar cada transição a partir de origem válida | Destino, histórico, versão e efeitos correspondem à matriz |
| `CT-WFL-002` | P0 | `TR-001`–`TR-023` | Executar cada transição a partir de origem inválida | Operação integralmente recusada |
| `CT-WFL-003` | P0 | T4 | Executar transição com papel não autorizado | Estado e efeitos permanecem inalterados |
| `CT-WFL-004` | P0 | `TR-004` | Registar submissão com bloqueio documental | Não cria snapshot nem muda para `SUBMETIDA` |
| `CT-WFL-005` | P0 | `TR-004` | Repetir a mesma chave de submissão | Existe uma transição e um snapshot |
| `CT-WFL-006` | P0 | `TR-007` | Registar pedido com questões e prazo | Estado, pedido, prazo, suspensão e tarefas são criados atomicamente |
| `CT-WFL-007` | P0 | `TR-008` | Responder com questão obrigatória incompleta | Rascunho mantém-se e candidatura continua a aguardar elementos |
| `CT-WFL-008` | P0 | `TR-008` | Confirmar resposta completa | Versões são preservadas, suspensão termina e análise retoma |
| `CT-WFL-009` | P0 | `TR-009` | Registar decisão parcial válida | Resultados individuais e global ficam coerentes |
| `CT-WFL-010` | P1 | `RN-PRZ-003` | Suspender duas vezes períodos sobrepostos | Segunda suspensão é recusada |
| `CT-WFL-011` | P1 | `RN-PRZ-004` | Corrigir data limite sem motivo | Alteração recusada |
| `CT-WFL-012` | P0 | `TR-013` | Confirmar termo sem versão válida | Transição para acompanhamento é recusada |
| `CT-WFL-013` | P0 | `TR-021` | Encerrar com movimentos pendentes sem decisão | Estado `ENCERRADA` é recusado |
| `CT-WFL-014` | P0 | `TR-023` | Administrador corrige transição terminal errada | Original permanece, correção liga-se a ela e motivo é auditado |

## 11. Financeiro

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-FIN-001` | P0 | `RN-FIN-002` | Calcular ativo empregado abaixo de todos os limites | Estimativa corresponde ao custo e parâmetros aplicáveis |
| `CT-FIN-002` | P0 | `RN-FIN-002` | Valor por hora ultrapassa percentagem ou máximo | Aplica o menor limite correto e explica a decomposição |
| `CT-FIN-003` | P0 | `RN-FIN-003` | Desempregado atinge limite de horas ou montante | Resultado usa exatamente o limite configurado |
| `CT-FIN-004` | P1 | `RN-FIN-004` | Dia tem menos de três horas de formação | Não conta para subsídio de refeição |
| `CT-FIN-005` | P0 | `RN-FIN-005` | Existe financiamento de terceiros | Valor elegível evita dupla comparticipação |
| `CT-FIN-006` | P0 | T5 | Guardar valor oficial sem data, origem ou autor | Operação recusada |
| `CT-FIN-007` | P0 | T5 | Repetir movimento com mesma chave | Valor é registado uma única vez |
| `CT-FIN-008` | P0 | `RN-INC-003` | Existe apenas risco de restituição | Gera alerta, mas não cria restituição oficial |

## 12. Notificações e tarefas

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-NOT-001` | P1 | `RN-NOT-001` | Acontecimento configurado ocorre após commit | Notificação interna é criada para destinatários corretos |
| `CT-NOT-002` | P0 | `RN-NOT-004` | Comando de alertas corre duas vezes no mesmo limiar | Não existem notificações duplicadas |
| `CT-NOT-003` | P1 | `RN-NOT-002` | Prazo atravessa vários limiares | Cria aviso distinto apenas em cada limiar aplicável |
| `CT-NOT-004` | P1 | `RN-NOT-005` | Marcar mensagem como lida | Tarefa relacionada não é marcada como concluída |
| `CT-NOT-005` | P1 | T6 | Email falha depois do commit | Operação de negócio mantém-se e envio fica falhado ou pendente |
| `CT-NOT-006` | P0 | T7 | Mensagem é construída para ação sensível | Não contém NIF, IBAN, anexo ou detalhe excessivo |

## 13. Interface e acessibilidade

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-UIA-001` | P1 | `ECR-001`–`ECR-056` | Abrir cada ecrã com perfil autorizado | Título, navegação, ação e estado apropriados são apresentados |
| `CT-UIA-002` | P0 | T7 | Abrir ecrã com perfil recusado | Não apresenta ação nem dados alheios |
| `CT-UIA-003` | P1 | T7 | Submeter formulário com vários erros | Resumo liga aos campos, dados válidos permanecem e foco é adequado |
| `CT-UIA-004` | P1 | T7 | Navegar percurso crítico só com teclado | Todas as ações são alcançáveis e foco permanece visível |
| `CT-UIA-005` | P1 | WCAG 2.2 AA | Ver estados com cores removidas | Texto e ícone continuam a transmitir significado |
| `CT-UIA-006` | P1 | WCAG 2.2 AA | Usar viewport de 320 píxeis CSS | Não há perda de conteúdo ou função essencial |
| `CT-UIA-007` | P1 | T7 | Mostrar botão indisponível | Motivo é visível e conduz à correção quando possível |
| `CT-UIA-008` | P1 | T7 | Apresentar data, hora, moeda e campo desconhecido | Formato PT-PT e “Por confirmar” são usados corretamente |
| `CT-UIA-009` | P0 | T7 | Confirmar acontecimento externo | Página distingue registo interno de decisão oficial |
| `CT-UIA-010` | P1 | W3C WAI | Executar análise automática sem erros detetados | Resultado é complementado por verificação humana, não tratado como conformidade total |

## 14. Segurança

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-SEC-001` | P0 | ASVS 5.0 | Enviar alteração de estado por `GET` | Pedido não altera dados |
| `CT-SEC-002` | P0 | ASVS 5.0 | Enviar `POST` sem token CSRF válido | Operação recusada |
| `CT-SEC-003` | P0 | ASVS 5.0 | Introduzir HTML ou script em campo textual | Conteúdo é validado e nunca executado na apresentação |
| `CT-SEC-004` | P0 | ASVS 5.0 | Manipular identificador de empresa no formulário | Âmbito é recalculado no servidor e alteração recusada |
| `CT-SEC-005` | P0 | ASVS 5.0 | Provocar erro inesperado em produção | Resposta não revela stack, segredo, SQL ou caminho |
| `CT-SEC-006` | P0 | T6 | Procurar segredos e dados pessoais no repositório | Nenhum valor real ou segredo é encontrado |
| `CT-SEC-007` | P0 | T5 | Consultar logs depois de operações financeiras | NIF, IBAN e conteúdo documental estão ausentes |
| `CT-SEC-008` | P0 | ASVS 5.0 | Alterar cookie de sessão ou usar sessão expirada | Acesso não é concedido |
| `CT-SEC-009` | P1 | ASVS 5.0 | Verificar configuração publicada | HTTPS, cookies seguros, hosts e debug cumprem configuração planeada |
| `CT-SEC-010` | P1 | WSTG | Executar revisão autorizada contra ambiente próprio | Resultados são registados sem testar terceiros |

## 15. Operação, instalação e recuperação

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-OPS-001` | P0 | `IMP-00` | Instalar a partir de checkout limpo e documentação | Projeto inicia sem passos secretos |
| `CT-OPS-002` | P0 | T6 | Aplicar migrações numa base vazia | Esquema completo é criado sem ciclo |
| `CT-OPS-003` | P0 | T6 | Atualizar base da onda anterior | Dados preservados e nova migração aplicada |
| `CT-OPS-004` | P0 | T6 | Criar backup e restaurar em base separada | Candidaturas, versões e histórico permanecem coerentes |
| `CT-OPS-005` | P1 | T6 | Reexecutar comando de dados fictícios | Não duplica catálogos nem cenários |
| `CT-OPS-006` | P0 | T6 | Executar demonstração sem Internet | Percurso principal continua disponível localmente |

## 16. Percursos ponta a ponta

| ID | P | Referência | Cenário | Resultado esperado |
| --- | --- | --- | --- | --- |
| `CT-E2E-001` | P0 | `FL-01` | Candidato cria e retoma candidatura individual | Processo chega a pronta sem ser marcado como submetido |
| `CT-E2E-002` | P0 | `FL-02` | Titular regista submissão já feita no Iefponline | Snapshot, transição e prazo são criados uma vez |
| `CT-E2E-003` | P0 | `FL-03` | Gestor prepara candidatura empresarial com três beneficiários | Dados, formações e documentos permanecem separados por pessoa |
| `CT-E2E-004` | P0 | `FL-04` | Gestor regista pedido, guarda rascunho e confirma resposta | Prazo suspende e retoma sem perder questões ou versões |
| `CT-E2E-005` | P0 | `FL-05` | Gestor regista decisão parcial comunicada | Estado e resultado parcial aparecem separadamente |
| `CT-E2E-006` | P0 | `FL-06` | Termo é recebido, validado e formação acompanhada | Processo avança apenas após condições e mantém datas reais |
| `CT-E2E-007` | P0 | `FL-07` | Encerramento é preparado, registado e concluído | Documentos finais, decisão e fluxo financeiro permanecem coerentes |
| `CT-E2E-008` | P0 | `FL-08` | Administrador publica nova versão de regras | Novas candidaturas usam a versão nova; históricas não mudam |

## 17. Testes exploratórios orientados

Além dos casos anteriores, cada incremento reserva uma sessão curta para explorar:

- valores e sequências não antecipados;
- voltar, atualizar e abrir duas janelas;
- sessões expiradas durante formulários;
- conteúdo muito longo e listas vazias;
- combinações de filtros;
- interrupção durante upload;
- ações repetidas pelo utilizador;
- mudança de âmbito durante a navegação;
- mensagens que possam confundir ação interna e externa.

Os resultados úteis transformam-se em caso permanente ou melhoria documentada.

## 18. Ordem mínima de execução

1. testes rápidos de unidade;
2. modelos e restrições;
3. serviços e permissões;
4. views do incremento;
5. integração PostgreSQL e storage;
6. regressão das áreas afetadas;
7. percurso ponta a ponta aplicável;
8. checklist manual de interface e acessibilidade;
9. segurança e instalação antes de demonstração ou publicação.

## 19. Critério de manutenção

O catálogo é atualizado quando:

- uma regra, transição ou ecrã muda;
- um defeito revela cenário ausente;
- um risco deixa de ser aplicável;
- uma integração ou ambiente é adicionado;
- a versão da referência de segurança ou acessibilidade muda.

Casos obsoletos não são apagados sem explicação; ficam substituídos ou não aplicáveis com referência à decisão.

## 20. Resultado

O catálogo fornece 116 cenários críticos para autenticação, isolamento, regras, candidaturas, documentos, workflow, finanças, notificações, interface, segurança, operação e oito percursos completos. A implementação futura deverá expandi-los com os vetores de todas as regras, transições e ecrãs referenciados.
