# Tópico 05 - Dicionário de dados

## 1. Objetivo

Este dicionário completa o [modelo de dados definitivo](05-modelo-de-dados.md). Define o significado, tipo lógico, obrigatoriedade e principais restrições dos campos das 38 entidades conceptuais do Forma Flow.

Continua a ser uma especificação de planeamento. Os tipos indicados são independentes da base de dados e serão convertidos para campos Django apenas depois de ser autorizada a fase de código.

## 2. Convenções do dicionário

### 2.1. Notação

| Notação | Significado |
| --- | --- |
| PK | Chave primária |
| FK | Chave estrangeira para outra entidade |
| O2O | Relação um-para-um |
| M2M | Relação muitos-para-muitos através de tabela de junção |
| UUID | Identificador aleatório imutável apropriado para exposição pública |
| `S` | Campo obrigatório |
| `N` | Campo opcional |
| `C` | Campo obrigatório apenas quando se verifica a condição indicada |
| `D` | Campo derivado ou de resumo, reconstruível a partir da fonte de verdade |

### 2.2. Tipos lógicos

- `texto(n)` limita o tamanho máximo a `n` caracteres.
- `texto longo` admite observações extensas, mas não ficheiros.
- `decimal(12,2)` é usado para euros; `decimal(8,2)` para horas e quantidades.
- `data/hora` inclui fuso horário.
- `enum` aceita apenas valores do conjunto indicado.
- `JSON` é reservado a estruturas imutáveis ou versionadas que não necessitam de relações pesquisáveis.
- Identificadores portugueses, como NIF e NIPC, são texto para preservar zeros iniciais e aplicar validação própria.

### 2.3. Campos comuns

Salvo indicação em contrário, todas as entidades têm:

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `id` | inteiro longo, PK | S | Gerado automaticamente e nunca reutilizado |
| `criado_em` | data/hora | S | Preenchido na criação |
| `atualizado_em` | data/hora | S | Atualizado em cada alteração autorizada |

As entidades arquiváveis acrescentam `arquivado_em` e `arquivado_por`. Os registos históricos imutáveis têm apenas a data do acontecimento e não expõem uma falsa possibilidade de edição.

## 3. Identidade e organizações

### 3.1. `Utilizador`

Conta usada para autenticação, autorização e autoria de operações.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `email` | texto(254) | S | Normalizado em minúsculas e único; será o identificador de autenticação |
| `nome_proprio` | texto(150) | S | Nome apresentado na interface |
| `apelido` | texto(150) | S | Apelido apresentado na interface |
| `ativo` | booleano | S | Desativar impede autenticação sem apagar histórico |
| `equipa_interna` | booleano | S | Distingue contas operacionais do Forma Flow de utilizadores externos |
| `ultimo_acesso_em` | data/hora | N | Informação técnica de autenticação |
| `grupos` | M2M para grupos de autorização | N | Papéis globais definidos no Tópico 2; não substitui o âmbito por empresa |

Restrições: email vazio não é permitido; alterações de email são auditadas; palavras-passe e tokens são geridos pelo sistema de autenticação e nunca por esta entidade de negócio.

### 3.2. `PerfilCandidato`

Dados pessoais necessários quando um utilizador participa numa candidatura.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `utilizador` | O2O para `Utilizador` | S | Um utilizador tem no máximo um perfil de candidato |
| `nif` | texto(9) | S | Único depois de normalizado e validado |
| `data_nascimento` | data | S | Não pode estar no futuro |
| `telefone` | texto(30) | N | Formato normalizado, mantendo indicativo internacional |
| `nacionalidade` | texto(2) | N | Código de país quando conhecido |
| `morada` | texto(255) | N | Morada atual; snapshots preservam a versão submetida |
| `codigo_postal` | texto(20) | N | Texto para suportar formatos nacionais e internacionais |
| `localidade` | texto(120) | N | Localidade atual |
| `pais` | texto(2) | N | Código de país da morada |

Dados históricos de emprego não pertencem a este perfil; ficam em `VinculoLaboral`.

### 3.3. `Empresa`

Pessoa coletiva titular de candidaturas empresariais ou empregadora de beneficiários.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `nipc` | texto(9) | S | Único depois de normalizado e validado |
| `denominacao_legal` | texto(255) | S | Nome oficial |
| `nome_comercial` | texto(255) | N | Nome usado na interface quando diferente |
| `natureza_juridica` | texto(120) | N | Apoia verificações de elegibilidade |
| `cae_principal` | texto(10) | N | Código tratado como texto |
| `email` | texto(254) | N | Contacto institucional |
| `telefone` | texto(30) | N | Contacto institucional |
| `morada` | texto(255) | N | Sede ou endereço relevante |
| `codigo_postal` | texto(20) | N | Código postal |
| `localidade` | texto(120) | N | Localidade |
| `ativa` | booleano | S | Uma empresa inativa conserva candidaturas e histórico |

### 3.4. `AssociacaoEmpresa`

Autoriza um utilizador a consultar ou gerir dados de uma empresa. Não prova qualquer vínculo laboral.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `utilizador` | FK para `Utilizador` | S | Utilizador autorizado |
| `empresa` | FK para `Empresa` | S | Âmbito da autorização |
| `papel` | enum | S | `GESTOR`, `RECURSOS_HUMANOS` ou `CONSULTA` |
| `ativa` | booleano | S | Apenas associações ativas concedem acesso |
| `inicio_em` | data/hora | S | Momento a partir do qual a autorização vigora |
| `fim_em` | data/hora | N | Igual ou posterior a `inicio_em` |
| `concedida_por` | FK para `Utilizador` | N | Autor da concessão; `SET_NULL` se a conta for desativada |

Restrições: combinação ativa de utilizador, empresa e papel é única; terminar a associação não retira autoria de operações anteriores.

### 3.5. `VinculoLaboral`

Regista a situação profissional de um candidato ao longo do tempo.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidato` | FK para `PerfilCandidato` | S | Pessoa a que a situação pertence |
| `empresa` | FK para `Empresa` | C | Obrigatória para `CONTA_OUTREM`; nula para desemprego |
| `situacao` | enum | S | `CONTA_OUTREM`, `CONTA_PROPRIA` ou `DESEMPREGADO` |
| `inicio_em` | data | S | Início conhecido da situação |
| `fim_em` | data | N | Igual ou posterior ao início; nula quando atual |
| `inscricao_iefp_em` | data | C | Necessária para avaliar o tempo de inscrição do desempregado |
| `nivel_qualificacao` | inteiro curto | N | Nível conhecido no período; não pode ser negativo |
| `confirmado_em` | data/hora | N | Data da confirmação manual |
| `confirmado_por` | FK para `Utilizador` | N | Utilizador que confirmou os dados |
| `evidencia` | FK para `VersaoDocumento` | N | Comprovativo usado na confirmação |

Restrições de serviço: sobreposições incompatíveis geram bloqueio ou aviso; a situação aplicável é a vigente na data de referência, não necessariamente a situação atual.

### 3.6. `ContaPagamento`

Conta bancária indicada para recebimento de apoios.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidato` | FK para `PerfilCandidato` | C | Preenchido quando a conta pertence a uma pessoa singular |
| `empresa` | FK para `Empresa` | C | Preenchido quando a conta pertence a uma pessoa coletiva |
| `iban_cifrado` | texto cifrado | S | Nunca pesquisado ou apresentado em claro por defeito |
| `iban_hash` | texto(64) | S | Hash usado para igualdade e prevenção de duplicados; não reversível |
| `iban_ultimos_4` | texto(4) | S | Única parte apresentada em listas |
| `nome_titular` | texto(255) | S | Deve ser coerente com o titular indicado |
| `principal` | booleano | S | No máximo uma conta principal ativa por proprietário |
| `ativa` | booleano | S | Contas antigas não são apagadas se tiverem sido usadas |
| `validada_em` | data/hora | N | Confirmação manual de titularidade |
| `validada_por` | FK para `Utilizador` | N | Autor da confirmação |
| `comprovativo` | FK para `VersaoDocumento` | N | Versão exata do comprovativo |

Restrição exclusiva: exatamente um de `candidato` ou `empresa` é preenchido.

### 3.7. `EntidadeFormadora`

Entidade responsável por ministrar ações de formação.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `nipc` | texto(9) | S | Único depois de normalizado e validado |
| `denominacao_legal` | texto(255) | S | Nome oficial |
| `nome_comercial` | texto(255) | N | Nome alternativo |
| `email` | texto(254) | N | Contacto institucional |
| `telefone` | texto(30) | N | Contacto institucional |
| `morada` | texto(255) | N | Sede ou estabelecimento relevante |
| `ativa` | booleano | S | Inativação não altera ações históricas |

### 3.8. `CertificacaoFormadora`

Regista a certificação DGERT ou o enquadramento que dispensa a entidade de certificação.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `entidade_formadora` | FK para `EntidadeFormadora` | S | Entidade verificada |
| `enquadramento` | enum | S | `CERTIFICADA_DGERT`, `DISPENSADA` ou `PENDENTE_CONFIRMACAO` |
| `area_codigo` | texto(20) | C | Obrigatório quando o enquadramento depende da área |
| `area_designacao` | texto(255) | N | Designação legível da área |
| `numero_certificacao` | texto(100) | N | Referência da certificação, quando exista |
| `valida_desde` | data | N | Início conhecido da validade |
| `valida_ate` | data | N | Igual ou posterior a `valida_desde` |
| `verificada_em` | data/hora | N | Data da consulta ou confirmação manual |
| `verificada_por` | FK para `Utilizador` | N | Utilizador responsável |
| `evidencia` | FK para `VersaoDocumento` | N | Evidência exata usada |

## 4. Regras e referências

### 4.1. `ConjuntoRegras`

Versão fechada das regras e parâmetros aplicáveis num período.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `codigo` | texto(50) | S | Identificador estável, por exemplo `CHEQUE_FORMACAO` |
| `versao` | inteiro positivo | S | Único dentro do mesmo código |
| `designacao` | texto(255) | S | Nome legível |
| `estado` | enum | S | `RASCUNHO`, `ATIVO`, `SUBSTITUIDO` ou `ARQUIVADO` |
| `vigente_desde` | data | S | Início da vigência assumida |
| `vigente_ate` | data | N | Igual ou posterior ao início |
| `referencia_demonstracao` | booleano | S | Verdadeiro enquanto as regras não forem confirmadas para uso real |
| `fonte` | texto longo | S | Identificação das fontes e data de consulta |
| `publicado_em` | data/hora | N | Ao publicar, a versão fica imutável |
| `publicado_por` | FK para `Utilizador` | N | Autor da publicação interna |

Uma candidatura submetida conserva a FK para esta versão, mesmo que surjam regras posteriores.

### 4.2. `ParametroRegra`

Valor configurável pertencente a um conjunto de regras.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `conjunto_regras` | FK para `ConjuntoRegras` | S | Versão a que o parâmetro pertence |
| `codigo` | texto(80) | S | Código do Tópico 3, como `CFG-IDADE-MIN` |
| `designacao` | texto(255) | S | Nome legível |
| `tipo_valor` | enum | S | `INTEIRO`, `DECIMAL`, `BOOLEANO`, `TEXTO`, `DATA` ou `JSON` |
| `valor` | JSON | S | Valor validado de acordo com `tipo_valor` |
| `unidade` | texto(40) | N | Por exemplo `dias_uteis`, `euros` ou `percentagem` |
| `observacoes` | texto longo | N | Limitações ou origem específica |

Restrição: `conjunto_regras` e `codigo` formam uma combinação única. Parâmetros publicados não são editados; cria-se nova versão do conjunto.

### 4.3. `Feriado`

Data não útil usada no cálculo de prazos.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `data` | data | S | Dia excluído do calendário aplicável |
| `designacao` | texto(150) | S | Nome do feriado |
| `ambito` | enum | S | `NACIONAL`, `REGIONAL` ou `MUNICIPAL` |
| `regiao` | texto(120) | C | Obrigatória fora do âmbito nacional |
| `ativo` | booleano | S | Permite corrigir calendários sem apagar histórico |
| `fonte` | texto(255) | N | Origem da informação |

Restrição: `data`, `ambito` e região normalizada são únicos em conjunto.

### 4.4. `TipoDocumento`

Catálogo dos tipos de comprovativo aceites pelo sistema.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `codigo` | texto(80) | S | Único e estável |
| `designacao` | texto(255) | S | Nome apresentado ao utilizador |
| `categoria` | enum | S | `IDENTIDADE`, `EMPRESA`, `EMPREGO`, `FORMACAO`, `FINANCEIRO`, `DECISAO` ou `OUTRO` |
| `sensibilidade` | enum | S | `INTERNO`, `PESSOAL` ou `PESSOAL_SENSIVEL` |
| `tem_validade` | booleano | S | Indica se deve ser pedida data de validade |
| `apenas_pdf` | booleano | S | Verdadeiro na configuração inicial do projeto |
| `ativo` | booleano | S | Tipos usados historicamente não são apagados |
| `descricao` | texto longo | N | Instruções de utilização, não regras executáveis |

## 5. Candidaturas e formação

### 5.1. `Candidatura`

Raiz do processo acompanhado pelo Forma Flow.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `public_id` | UUID | S | Único, imutável e usado em endereços públicos |
| `tipo` | enum | S | `INDIVIDUAL` ou `EMPRESARIAL` |
| `titular_candidato` | FK para `PerfilCandidato` | C | Obrigatório apenas no tipo individual |
| `titular_empresa` | FK para `Empresa` | C | Obrigatório apenas no tipo empresarial |
| `conta_pagamento` | FK para `ContaPagamento` | N | Deve pertencer ao titular adequado |
| `conjunto_regras` | FK para `ConjuntoRegras` | C | Obrigatório antes de validar ou submeter; imutável depois da submissão |
| `estado_atual` | enum | D | Um dos 19 estados do Tópico 4; reflete a última transição válida |
| `resultado_decisao` | enum | D | `PENDENTE`, `DEFERIDA_TOTAL`, `DEFERIDA_PARCIAL`, `INDEFERIDA` ou `ARQUIVADA` |
| `referencia_externa` | texto(100) | N | Identificador do Iefponline, único quando preenchido |
| `submetida_em` | data/hora | N | Momento efetivo registado da submissão externa |
| `criada_por` | FK para `Utilizador` | S | Autor do rascunho |
| `versao` | inteiro positivo | S | Incrementado a cada alteração concorrente relevante |
| `idempotencia_submissao` | texto(100) | N | Impede registos repetidos da mesma submissão |

Restrições: exatamente um titular é preenchido e deve corresponder a `tipo`; uma candidatura individual terá um único beneficiário igual ao titular; o estado muda apenas pelo serviço de transições.

### 5.2. `AtribuicaoCandidatura`

Define a equipa interna autorizada a acompanhar uma candidatura.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo abrangido |
| `utilizador` | FK para `Utilizador` | S | Membro da equipa |
| `papel` | enum | S | `RESPONSAVEL`, `COLABORADOR` ou `LEITURA` |
| `principal` | booleano | S | Apenas um responsável principal ativo por candidatura |
| `ativa` | booleano | S | Controla o acesso corrente |
| `inicio_em` | data/hora | S | Início da atribuição |
| `fim_em` | data/hora | N | Igual ou posterior ao início |
| `atribuida_por` | FK para `Utilizador` | N | Autor da atribuição |

### 5.3. `BeneficiarioCandidatura`

Representa cada pessoa abrangida por uma candidatura e conserva os dados relevantes para a decisão.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Candidatura abrangente |
| `candidato` | FK para `PerfilCandidato` | S | Pessoa beneficiária |
| `e_titular` | booleano | S | Verdadeiro no único beneficiário da candidatura individual |
| `situacao_referencia` | enum | S | Cópia controlada de `CONTA_OUTREM`, `CONTA_PROPRIA` ou `DESEMPREGADO` |
| `vinculo_referencia` | FK para `VinculoLaboral` | N | Vínculo que fundamentou a situação |
| `nivel_qualificacao_referencia` | inteiro curto | N | Valor considerado na verificação |
| `inscricao_iefp_referencia` | data | N | Valor considerado para desempregados |
| `resultado` | enum | S | `PENDENTE`, `DEFERIDA`, `INDEFERIDA`, `ARQUIVADA`, `DESISTIDA`, `REVOGADA` ou `ENCERRADA` |
| `decidido_em` | data/hora | N | Data efetiva da decisão externa |
| `motivo_decisao` | texto longo | N | Obrigatório para resultado oficial não favorável |
| `referencia_decisao` | texto(100) | N | Referência da comunicação externa |

Restrição: candidatura e candidato são únicos em conjunto. Os campos de referência não acompanham alterações futuras do perfil.

### 5.4. `AcaoFormacao`

Curso ou ação concreta ministrada por uma entidade formadora.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `entidade_formadora` | FK para `EntidadeFormadora` | S | Uma entidade por ação no MVP |
| `referencia_externa` | texto(100) | N | Código da entidade ou plataforma externa |
| `designacao` | texto(255) | S | Nome da ação |
| `area_codigo` | texto(20) | N | Área de educação e formação |
| `area_designacao` | texto(255) | N | Designação legível |
| `modalidade` | texto(120) | N | Modalidade declarada |
| `tipologia` | enum | D | `CNQ`, `EXTRA_CNQ` ou `MISTA`, derivada das componentes |
| `inicio_previsto` | data | S | Não posterior ao fim previsto |
| `fim_previsto` | data | S | Igual ou posterior ao início previsto |
| `inicio_real` | data | N | Necessário para passar a `EM_CURSO` |
| `fim_real` | data | N | Necessário para um estado de conclusão |
| `local` | texto(255) | N | Local físico ou indicação de regime remoto |
| `estado` | enum | S | `PLANEADA`, `EM_CURSO`, `CONCLUIDA_COM_APROVEITAMENTO`, `CONCLUIDA_SEM_APROVEITAMENTO`, `INTERROMPIDA` ou `CANCELADA` |
| `horas_totais` | decimal(8,2) | D | Soma das componentes |

### 5.5. `ComponenteFormacao`

Unidade CNQ ou conteúdo extra-CNQ que compõe uma ação.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `acao_formacao` | FK para `AcaoFormacao` | S | Ação a que pertence |
| `ordem` | inteiro positivo | S | Única dentro da ação |
| `tipo` | enum | S | `CNQ` ou `EXTRA_CNQ` |
| `codigo_cnq` | texto(30) | C | Obrigatório para componentes CNQ |
| `designacao` | texto(255) | S | Nome da componente ou UFCD |
| `area_codigo` | texto(20) | N | Deve ser coerente com a área da ação |
| `referencial` | texto(255) | N | Referencial CNQ, quando aplicável |
| `horas` | decimal(8,2) | S | Superior a zero |
| `justificacao_extra_cnq` | texto longo | C | Obrigatória no tipo `EXTRA_CNQ` |

### 5.6. `ParticipacaoFormacao`

Entidade associativa entre beneficiário e ação, com valores específicos dessa participação.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `beneficiario` | FK para `BeneficiarioCandidatura` | S | Pessoa e candidatura abrangidas |
| `acao_formacao` | FK para `AcaoFormacao` | S | Ação frequentada |
| `estado` | enum | S | `PLANEADA`, `EM_CURSO`, `CONCLUIDA_COM_APROVEITAMENTO`, `CONCLUIDA_SEM_APROVEITAMENTO`, `INTERROMPIDA` ou `CANCELADA` |
| `horas_previstas` | decimal(8,2) | S | Positivas e não superiores às horas da ação sem justificação |
| `horas_frequentadas` | decimal(8,2) | N | Não negativa |
| `dias_tres_ou_mais_horas` | inteiro não negativo | N | Base do apoio de refeição quando aplicável |
| `custo_declarado` | decimal(12,2) | S | Não negativo |
| `custo_pago_formadora` | decimal(12,2) | N | Não negativo; valor efetivamente comprovado |
| `resultado_registado_em` | data/hora | N | Data de confirmação da frequência ou resultado |
| `motivo_resultado` | texto longo | C | Obrigatório quando a participação é interrompida ou cancelada |

Restrição: beneficiário e ação são únicos em conjunto. O candidato não é repetido porque é obtido através do beneficiário.

### 5.7. `VerificacaoElegibilidade`

Resultado de uma regra automática ou confirmação manual, sem substituir a decisão do IEFP.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo verificado |
| `beneficiario` | FK para `BeneficiarioCandidatura` | N | Preenchido quando a regra é individual |
| `participacao` | FK para `ParticipacaoFormacao` | N | Preenchido quando a regra é específica de uma ação |
| `codigo_regra` | texto(40) | S | Código `RN-*` do Tópico 3 |
| `tipo_avaliacao` | enum | S | `AUTOMATICA`, `MANUAL` ou `EXTERNA` |
| `resultado` | enum | S | `PENDENTE`, `CONFORME`, `NAO_CONFORME` ou `NAO_APLICAVEL` |
| `valor_avaliado` | JSON | N | Valores mínimos necessários para explicar o cálculo |
| `observacoes` | texto longo | N | Fundamentação ou limitação |
| `verificada_em` | data/hora | N | Momento da avaliação |
| `verificada_por` | FK para `Utilizador` | N | Nulo em verificação automática |
| `evidencia` | FK para `VersaoDocumento` | N | Documento exato usado |

Restrição: candidatura, beneficiário, participação e código da regra identificam uma verificação corrente; nova execução relevante preserva o resultado anterior por auditoria ou versionamento.

## 6. Documentos e submissões

### 6.1. `FicheiroArmazenado`

Metadados técnicos de um ficheiro privado; não representa por si só um documento de negócio.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `chave_armazenamento` | texto(500) | S | Aleatória, única e nunca exposta como URL pública |
| `nome_original` | texto(255) | S | Sanitizado para apresentação; não determina o caminho |
| `tipo_mime` | texto(100) | S | Confirmado pelo conteúdo, não apenas pela extensão |
| `tamanho_bytes` | inteiro longo não negativo | S | Sujeito ao limite do conjunto de regras |
| `sha256` | texto(64) | S | Hash de integridade |
| `estado_upload` | enum | S | `PENDENTE`, `CONCLUIDO`, `FALHOU` ou `REMOVIDO` |
| `estado_seguranca` | enum | S | `PENDENTE`, `SEGURO`, `SUSPEITO` ou `BLOQUEADO` |
| `carregado_por` | FK para `Utilizador` | S | Autor do envio |
| `carregado_em` | data/hora | S | Momento do envio concluído |
| `removido_em` | data/hora | N | Apenas segundo política de retenção |

O conteúdo nunca é guardado num campo da base de dados nem servido sem nova verificação de permissões.

### 6.2. `RequisitoDocumento`

Item da checklist dinâmica que determina o comprovativo necessário.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo a que o requisito pertence |
| `beneficiario` | FK para `BeneficiarioCandidatura` | N | Quando o comprovativo é individual |
| `participacao` | FK para `ParticipacaoFormacao` | N | Quando depende de uma ação concreta |
| `tipo_documento` | FK para `TipoDocumento` | S | Tipo exigido |
| `fase` | enum | S | `PREPARACAO`, `ANALISE`, `ACEITACAO`, `ACOMPANHAMENTO`, `ENCERRAMENTO` ou `FINANCEIRA` |
| `codigo_regra` | texto(40) | N | Regra que originou a exigência |
| `obrigatorio` | booleano | S | Distingue requisito de recomendação |
| `bloqueante` | booleano | S | Impede a operação da fase enquanto não satisfeito |
| `data_limite` | data/hora | N | Limite específico, quando exista |
| `estado` | enum | D | `EM_FALTA`, `RECEBIDO`, `EM_VALIDACAO`, `VALIDO`, `INVALIDO` ou `DISPENSADO_COM_JUSTIFICACAO` |
| `dispensado_em` | data/hora | N | Obrigatório quando dispensado |
| `dispensado_por` | FK para `Utilizador` | N | Autor autorizado da dispensa |
| `motivo_dispensa` | texto longo | C | Obrigatório quando dispensado |

### 6.3. `Documento`

Objeto documental lógico, independente das sucessivas versões de ficheiro.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `public_id` | UUID | S | Único e imutável |
| `candidatura` | FK para `Candidatura` | S | Âmbito de segurança principal |
| `beneficiario` | FK para `BeneficiarioCandidatura` | N | Quando o documento pertence a uma pessoa específica |
| `participacao` | FK para `ParticipacaoFormacao` | N | Quando comprova uma ação específica |
| `tipo_documento` | FK para `TipoDocumento` | S | Classificação de negócio |
| `requisito` | FK para `RequisitoDocumento` | N | Item satisfeito, se aplicável |
| `fase` | enum | S | Fase em que foi pedido ou criado |
| `titulo` | texto(255) | N | Descrição curta para distinguir documentos do mesmo tipo |
| `estado_atual` | enum | D | Estado da versão corrente e respetiva validação |
| `criado_por` | FK para `Utilizador` | S | Autor do objeto lógico |

Todas as relações opcionais devem pertencer à mesma candidatura. Um requisito não pode ser satisfeito por documento de outro processo.

### 6.4. `VersaoDocumento`

Versão imutável do conteúdo e metadados de um documento.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `documento` | FK para `Documento` | S | Documento lógico |
| `numero` | inteiro positivo | S | Sequencial e único dentro do documento |
| `ficheiro` | O2O para `FicheiroArmazenado` | S | Um ficheiro materializa uma única versão |
| `estado_validacao` | enum | S | `RECEBIDO`, `EM_VALIDACAO`, `VALIDO`, `INVALIDO` ou `SUBSTITUIDO` |
| `corrente` | booleano | S | Apenas uma versão corrente por documento |
| `emitido_em` | data | N | Data constante do comprovativo |
| `valido_ate` | data | N | Igual ou posterior a `emitido_em` |
| `carregada_por` | FK para `Utilizador` | S | Autor da versão |
| `carregada_em` | data/hora | S | Momento de receção |
| `validada_por` | FK para `Utilizador` | N | Obrigatório quando existe decisão manual de validade |
| `validada_em` | data/hora | N | Momento da validação |
| `observacao_validacao` | texto longo | N | Obrigatória quando inválida |
| `motivo_substituicao` | texto longo | N | Explica a nova versão, quando aplicável |

Uma versão usada num snapshot, decisão ou evidência nunca é alterada nem eliminada por operações normais.

### 6.5. `SnapshotSubmissao`

Fotografia imutável dos dados e documentos usados numa operação formal.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo fotografado |
| `transicao` | FK para `TransicaoCandidatura` | N | Transição que formalizou a operação |
| `finalidade` | enum | S | `SUBMISSAO`, `TERMO`, `ENCERRAMENTO` ou `CORRECAO` |
| `sequencia` | inteiro positivo | S | Única por candidatura e finalidade |
| `capturado_em` | data/hora | S | Momento da fotografia |
| `capturado_por` | FK para `Utilizador` | S | Utilizador responsável |
| `dados` | JSON | S | Apenas os dados relevantes, com esquema versionado |
| `versao_esquema` | inteiro positivo | S | Permite interpretar snapshots antigos |
| `hash_conteudo` | texto(64) | S | Deteta alteração acidental |
| `versoes_documentos` | M2M para `VersaoDocumento` | N | Versões exatas incluídas |

Não existe `atualizado_em`: um erro é corrigido por novo snapshot e transição, nunca por edição do anterior.

## 7. Workflow

### 7.1. `TransicaoCandidatura`

Histórico imutável de cada mudança de estado administrativo.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo alterado |
| `beneficiario` | FK para `BeneficiarioCandidatura` | N | Apenas quando a transição contextualiza uma decisão individual |
| `codigo` | texto(10) | S | Um dos códigos `TR-001` a `TR-023` |
| `estado_anterior` | enum | N | Nulo apenas em `TR-001` |
| `estado_novo` | enum | S | Estado autorizado pelo Tópico 4 |
| `efetiva_em` | data/hora | S | Data real do acontecimento administrativo |
| `registada_em` | data/hora | S | Data em que entrou no Forma Flow |
| `ator` | FK para `Utilizador` | N | Nulo apenas para evento automático devidamente identificado |
| `origem` | enum | S | `UTILIZADOR`, `SISTEMA`, `IEFPONLINE` ou `COMUNICACAO_IEFP` |
| `referencia_externa` | texto(100) | N | Identificação do acontecimento oficial |
| `motivo` | texto longo | C | Obrigatório em decisões negativas, exceções e correções |
| `evidencia` | FK para `VersaoDocumento` | N | Comunicação que suporta o registo |
| `conjunto_regras` | FK para `ConjuntoRegras` | S | Regras aplicadas nesse momento |
| `versao_anterior` | inteiro não negativo | S | Versão da candidatura antes da operação |
| `versao_nova` | inteiro positivo | S | Exatamente uma unidade acima da anterior |
| `corrige_transicao` | FK para a própria entidade | N | Usada em `TR-023`; nunca apaga a transição incorreta |
| `chave_idempotencia` | texto(100) | S | Única no âmbito da candidatura |

Não existe `atualizado_em`. O estado anterior deve coincidir com o estado corrente bloqueado no início da transação.

### 7.2. `PedidoElementos`

Pedido externo de esclarecimentos ou documentos durante análise ou encerramento.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo abrangido |
| `fase` | enum | S | `ANALISE` ou `ENCERRAMENTO` |
| `referencia_externa` | texto(100) | N | Identificação oficial, única na candidatura quando preenchida |
| `recebido_em` | data/hora | S | Data efetiva da receção |
| `data_limite` | data/hora | S | Data prevista ou oficial para resposta |
| `estado` | enum | S | `ABERTO`, `RESPOSTA_RASCUNHO`, `RESPONDIDO`, `FECHADO`, `EXPIRADO` ou `CANCELADO` |
| `descricao` | texto longo | N | Contexto geral do pedido |
| `evidencia` | FK para `VersaoDocumento` | N | Comunicação recebida |
| `registado_por` | FK para `Utilizador` | S | Autor do registo |
| `fechado_em` | data/hora | N | Obrigatório em `FECHADO` |

### 7.3. `QuestaoPedido`

Questão individual dentro de um pedido de elementos.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `pedido` | FK para `PedidoElementos` | S | Pedido pai |
| `ordem` | inteiro positivo | S | Única dentro do pedido |
| `texto` | texto longo | S | Conteúdo solicitado |
| `destinatario` | enum | S | `TITULAR`, `BENEFICIARIO`, `EMPRESA`, `FORMADORA` ou `GESTOR` |
| `beneficiario` | FK para `BeneficiarioCandidatura` | C | Obrigatório quando o destinatário é um beneficiário específico |
| `exige_texto` | booleano | S | Pelo menos uma exigência deve estar ativa |
| `exige_documento` | booleano | S | Pelo menos uma exigência deve estar ativa |
| `tipo_documento_pedido` | FK para `TipoDocumento` | C | Obrigatório quando exige documento de tipo conhecido |
| `obrigatoria` | booleano | S | Questões obrigatórias bloqueiam a resposta completa |

### 7.4. `RespostaQuestao`

Versão de resposta a uma questão, preservando rascunhos submetidos anteriormente.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `questao` | FK para `QuestaoPedido` | S | Questão respondida |
| `numero` | inteiro positivo | S | Sequencial e único dentro da questão |
| `texto` | texto longo | C | Obrigatório se a questão exige texto |
| `estado` | enum | S | `RASCUNHO`, `SUBMETIDA` ou `SUBSTITUIDA` |
| `autor` | FK para `Utilizador` | S | Autor da versão |
| `submetida_em` | data/hora | N | Obrigatório no estado `SUBMETIDA` |
| `versoes_documentos` | M2M para `VersaoDocumento` | N | Obrigatório se a questão exige anexo |

Uma questão tem no máximo uma resposta submetida corrente; uma nova submissão marca a anterior como substituída.

### 7.5. `TermoAceitacao`

Controla a devolução e validação do termo associado a uma candidatura aprovada.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | O2O para `Candidatura` | S | Um termo lógico por candidatura |
| `estado` | enum | S | `NAO_APLICAVEL`, `PENDENTE`, `RECEBIDO`, `VALIDADO`, `INVALIDO`, `FORA_PRAZO` ou `DISPENSADO_COM_JUSTIFICACAO` |
| `notificado_em` | data/hora | N | Início conhecido do prazo |
| `data_limite` | data/hora | N | Derivada do prazo correspondente |
| `recebido_em` | data/hora | N | Momento real da receção |
| `validado_em` | data/hora | N | Momento da confirmação |
| `validado_por` | FK para `Utilizador` | N | Utilizador que registou a confirmação |
| `tipo_assinatura` | enum | N | `MANUSCRITA`, `DIGITAL_PESSOAL`, `DIGITAL_PROFISSIONAL_SCAP` ou `OUTRA` |
| `fora_prazo` | booleano | D | Compara receção e data limite; não decide aceitação oficial |
| `documento` | FK para `VersaoDocumento` | N | Versão exata do termo recebido |
| `justificacao` | texto longo | C | Obrigatória em dispensa ou exceção |

### 7.6. `PedidoEncerramento`

Objeto lógico que acompanha a preparação, submissão e decisão do encerramento.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | O2O para `Candidatura` | S | Um processo lógico de encerramento por candidatura |
| `estado` | enum | S | `PREPARACAO`, `SUBMETIDO`, `EM_ANALISE`, `AGUARDA_ELEMENTOS`, `CONCLUIDO` ou `NAO_ACEITE` |
| `preparacao_iniciada_em` | data/hora | S | Início interno |
| `submetido_em` | data/hora | N | Momento efetivo do envio externo |
| `analise_iniciada_em` | data/hora | N | Momento conhecido do início de análise |
| `concluido_em` | data/hora | N | Obrigatório quando concluído ou não aceite |
| `referencia_externa` | texto(100) | N | Identificação no sistema oficial |
| `resultado_final` | enum | N | `CONCLUIDO`, `CONCLUIDO_PARCIAL`, `NAO_ACEITE` ou `OUTRO` |
| `observacoes_decisao` | texto longo | N | Fundamentação do resultado |
| `snapshot_submissao` | FK para `SnapshotSubmissao` | N | Fotografia exata do pedido enviado |

### 7.7. `Prazo`

Prazo calculado ou oficial associado a uma obrigação do processo.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo abrangido |
| `beneficiario` | FK para `BeneficiarioCandidatura` | N | Quando o prazo é individual |
| `tipo` | enum | S | `DECISAO`, `RESPOSTA_ELEMENTOS`, `TERMO`, `PRIMEIRA_PRESTACAO`, `REMANESCENTE`, `ENCERRAMENTO`, `RESTITUICAO` ou `OUTRO` |
| `codigo_regra` | texto(40) | S | Regra ou parâmetro que fundamenta o cálculo |
| `conjunto_regras` | FK para `ConjuntoRegras` | S | Versão usada |
| `inicio_em` | data/hora | S | Acontecimento inicial |
| `unidade` | enum | S | `DIAS_UTEIS`, `DIAS_CONSECUTIVOS`, `MESES` ou `ANOS` |
| `duracao` | decimal(8,2) | S | Positiva |
| `limite_calculado` | data/hora | S | Resultado reproduzível do cálculo |
| `limite_oficial` | data/hora | N | Data comunicada externamente, quando diferente |
| `estado` | enum | S | `ATIVO`, `SUSPENSO`, `CUMPRIDO`, `EXPIRADO` ou `CANCELADO` |
| `transicao_origem` | FK para `TransicaoCandidatura` | N | Acontecimento que iniciou o prazo |
| `corrigido_por` | FK para `Utilizador` | N | Autor de substituição manual |
| `motivo_correcao` | texto longo | C | Obrigatório quando existe correção |
| `limite_anterior` | data/hora | C | Valor preservado quando há correção |

A data efetiva apresentada usa a data oficial quando existe e considera suspensões; é derivada e não substitui estes campos.

### 7.8. `SuspensaoPrazo`

Período durante o qual a contagem de um prazo fica suspensa.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `prazo` | FK para `Prazo` | S | Prazo afetado |
| `pedido_elementos` | FK para `PedidoElementos` | N | Pedido que originou a suspensão |
| `inicio_em` | data/hora | S | Início efetivo |
| `fim_em` | data/hora | N | Nulo enquanto a suspensão está ativa; nunca anterior ao início |
| `origem` | enum | S | `CALCULADA`, `OFICIAL` ou `CORRECAO_MANUAL` |
| `motivo` | texto longo | S | Razão da suspensão ou correção |
| `registada_por` | FK para `Utilizador` | N | Nulo apenas quando criada automaticamente |

Restrições: suspensões do mesmo prazo não se sobrepõem e apenas uma pode permanecer aberta.

### 7.9. `Tarefa`

Ação de trabalho atribuível a um utilizador; não é um estado da candidatura.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo abrangido |
| `beneficiario` | FK para `BeneficiarioCandidatura` | N | Âmbito individual, quando aplicável |
| `atribuida_a` | FK para `Utilizador` | N | Pode ficar numa fila antes da atribuição |
| `tipo` | texto(80) | S | Código estável da ação esperada |
| `titulo` | texto(255) | S | Resumo apresentado no dashboard |
| `descricao` | texto longo | N | Instruções operacionais |
| `estado` | enum | S | `ABERTA`, `EM_EXECUCAO`, `CONCLUIDA` ou `CANCELADA` |
| `prioridade` | enum | S | `BAIXA`, `NORMAL`, `ALTA` ou `CRITICA` |
| `data_limite` | data/hora | N | Pode refletir um prazo sem o substituir |
| `concluida_em` | data/hora | N | Obrigatório em `CONCLUIDA` |
| `concluida_por` | FK para `Utilizador` | N | Autor da conclusão |
| `prazo_origem` | FK para `Prazo` | N | Uma possível origem |
| `requisito_origem` | FK para `RequisitoDocumento` | N | Uma possível origem |
| `pedido_origem` | FK para `PedidoElementos` | N | Uma possível origem |
| `termo_origem` | FK para `TermoAceitacao` | N | Uma possível origem |
| `encerramento_origem` | FK para `PedidoEncerramento` | N | Uma possível origem |
| `chave_deduplicacao` | texto(150) | N | Única enquanto a tarefa equivalente estiver aberta |

No máximo uma origem automática é preenchida; tarefas manuais podem não ter nenhuma.

### 7.10. `Notificacao`

Mensagem interna criada por um evento, tarefa ou aproximação de prazo.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `destinatario` | FK para `Utilizador` | S | Utilizador que recebe a mensagem |
| `candidatura` | FK para `Candidatura` | N | Contexto, quando aplicável |
| `tarefa` | FK para `Tarefa` | N | Tarefa relacionada |
| `prazo` | FK para `Prazo` | N | Prazo relacionado |
| `codigo` | texto(80) | S | Tipo estável de notificação |
| `titulo` | texto(255) | S | Texto curto |
| `mensagem` | texto longo | S | Não inclui NIF, IBAN ou conteúdo sensível |
| `prioridade` | enum | S | `INFORMATIVA`, `ATENCAO`, `URGENTE` ou `CRITICA` |
| `estado` | enum | S | `PENDENTE`, `ENVIADA`, `LIDA`, `RESOLVIDA` ou `FALHOU` |
| `limiar` | texto(40) | N | Por exemplo `10_DIAS`, distinguindo alertas do mesmo prazo |
| `chave_deduplicacao` | texto(180) | S | Única por destinatário, evento e limiar |
| `enviada_em` | data/hora | N | Momento de disponibilização |
| `lida_em` | data/hora | N | Momento da leitura |
| `resolvida_em` | data/hora | N | Momento em que deixou de exigir atenção |

## 8. Financeiro

### 8.1. `ApoioFinanceiro`

Linha de apoio calculada ou confirmada para um beneficiário.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `beneficiario` | FK para `BeneficiarioCandidatura` | S | Pessoa abrangida |
| `participacao` | FK para `ParticipacaoFormacao` | N | Preenchida quando o apoio é específico de uma ação |
| `tipo` | enum | S | `FORMACAO`, `BOLSA`, `REFEICAO` ou `TRANSPORTE` |
| `custo_declarado` | decimal(12,2) | N | Não negativo |
| `financiamento_terceiros` | decimal(12,2) | N | Valor a excluir para evitar dupla comparticipação |
| `valor_elegivel` | decimal(12,2) | N | Base considerada pelo cálculo |
| `valor_estimado` | decimal(12,2) | N | Estimativa do Forma Flow |
| `valor_aprovado` | decimal(12,2) | N | Valor oficial conhecido |
| `valor_final` | decimal(12,2) | N | Valor final após encerramento |
| `moeda` | texto(3) | S | `EUR` no projeto inicial |
| `estado` | enum | D | Derivado: `SEM_APOIO`, `ESTIMADO`, `APROVADO`, estados de pagamento, restituição ou regularização |
| `conjunto_regras` | FK para `ConjuntoRegras` | S | Versão usada no cálculo |
| `decomposicao_calculo` | JSON | N | Fórmula, limites e valores intermédios reproduzíveis |
| `calculado_em` | data/hora | N | Momento da estimativa |
| `calculado_por` | FK para `Utilizador` | N | Nulo quando automático |
| `confirmado_em` | data/hora | N | Momento do registo do valor oficial |
| `confirmado_por` | FK para `Utilizador` | N | Autor do registo oficial |

Restrição: beneficiário, participação e tipo identificam a linha lógica. Para apoios sem participação, aplica-se unicidade parcial por beneficiário e tipo.

### 8.2. `MovimentoFinanceiro`

Prestação, ajuste ou devolução prevista ou efetivamente registada.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `apoio` | FK para `ApoioFinanceiro` | S | Linha de apoio movimentada |
| `tipo` | enum | S | `PRIMEIRA_PRESTACAO`, `REMANESCENTE`, `AJUSTE` ou `DEVOLUCAO` |
| `direcao` | enum | S | `CREDITO` para pagamento; `DEBITO` para redução ou devolução |
| `valor` | decimal(12,2) | S | Estritamente positivo; a direção determina o sinal contabilístico |
| `previsto_para` | data/hora | N | Data estimada |
| `efetivado_em` | data/hora | N | Data real conhecida |
| `estado` | enum | S | `PREVISTO`, `CONFIRMADO`, `FALHOU`, `CANCELADO` ou `REGULARIZADO` |
| `referencia_externa` | texto(100) | N | Identificação do pagamento oficial |
| `comprovativo` | FK para `VersaoDocumento` | N | Evidência exata |
| `registado_por` | FK para `Utilizador` | S | Autor do registo |
| `chave_idempotencia` | texto(100) | S | Única no âmbito do apoio |

Totais pagos consideram apenas movimentos confirmados e a respetiva direção.

### 8.3. `Restituicao`

Obrigação oficial de devolver valores, separada dos alertas de risco.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `candidatura` | FK para `Candidatura` | S | Processo afetado |
| `beneficiario` | FK para `BeneficiarioCandidatura` | N | Quando a obrigação é individual |
| `notificada_em` | data/hora | S | Data da comunicação oficial |
| `data_limite` | data/hora | S | Prazo oficial ou calculado para restituição |
| `valor` | decimal(12,2) | S | Estritamente positivo |
| `motivo` | texto longo | S | Fundamentação comunicada |
| `estado` | enum | S | `PENDENTE`, `PARCIAL`, `PAGA`, `DISPENSADA` ou `REGULARIZADA` |
| `valor_restituido` | decimal(12,2) | S | Não negativo e não superior ao valor sem justificação oficial |
| `regularizada_em` | data/hora | N | Obrigatório em estado final resolvido |
| `referencia_externa` | texto(100) | N | Identificação oficial |
| `evidencia` | FK para `VersaoDocumento` | N | Comunicação ou comprovativo |
| `registada_por` | FK para `Utilizador` | S | Autor do registo |

Um simples risco de incumprimento cria tarefa ou notificação; só uma comunicação oficial cria `Restituicao`.

## 9. Auditoria

### 9.1. `RegistoAuditoria`

Registo técnico imutável de operações relevantes, distinto do histórico administrativo de transições.

| Campo | Tipo | Obrig. | Regra |
| --- | --- | --- | --- |
| `utilizador` | FK para `Utilizador` | N | Nulo em operação automática |
| `acao` | texto(100) | S | Código estável, como `DOCUMENTO_DESCARREGADO` |
| `tipo_objeto` | texto(100) | S | Tipo lógico do objeto afetado |
| `id_objeto` | texto(100) | N | Identificador interno representado como texto |
| `public_id_objeto` | UUID | N | Quando o objeto possui identificador público |
| `ocorrido_em` | data/hora | S | Momento do acontecimento |
| `resultado` | enum | S | `SUCESSO`, `RECUSADO` ou `ERRO` |
| `id_pedido` | texto(100) | N | Correlação com o pedido técnico |
| `id_correlacao` | texto(100) | N | Liga várias ações da mesma operação |
| `hash_ip` | texto(64) | N | Hash com segredo e retenção limitada; evita guardar IP em claro |
| `metadados` | JSON | N | Lista branca de dados não sensíveis; nunca conteúdo documental ou credenciais |

Não existem `atualizado_em`, edição ou eliminação normal. O acesso aos registos é restrito a administradores autorizados.

## 10. Relações e políticas de eliminação

| Relação de origem | Dependência | Política planeada | Justificação |
| --- | --- | --- | --- |
| Utilizador → perfil | Forte antes de existir histórico | `PROTECT` ou inativação | Preservar identidade de candidaturas |
| Empresa → candidaturas | Histórica | `PROTECT` | Não destruir o titular oficial |
| Candidatura → beneficiários e workflow | Agregado histórico | `PROTECT` após submissão | Preservar o processo completo |
| Ação → componentes | Composição | `CASCADE` apenas em rascunho | Componentes não existem sem ação |
| Documento → versões | Composição histórica | `PROTECT` após utilização | Preservar versões submetidas |
| Utilizador → autoria | Referência histórica | `SET_NULL` quando permitido | Manter o acontecimento mesmo com conta inativa |
| Catálogos e regras → utilização | Referência versionada | `PROTECT` | Evitar alterar significado histórico |
| Tarefa/notificação → origem | Operacional | `SET_NULL` ou `PROTECT` conforme histórico | Uma mensagem enviada deve permanecer explicável |

As políticas exatas serão transformadas em opções de relação apenas durante a implementação e testadas com dados representativos.

## 11. Regras transversais de validação

1. Todas as FK opcionais que contextualizem uma candidatura devem apontar para objetos da mesma candidatura.
2. NIF, NIPC, email, IBAN e referências externas são normalizados antes de validar unicidade.
3. Datas finais nunca antecedem datas iniciais, salvo registo de correção explicitamente auditado.
4. Montantes, horas, dias e versões não aceitam valores negativos.
5. Um valor oficial exige data, origem e autor; um cálculo automático nunca é apresentado como decisão do IEFP.
6. Alterar dados mestres não modifica snapshots, versões, transições ou cálculos históricos.
7. Estados derivados não são editados diretamente.
8. Operações sensíveis verificam simultaneamente papel global, associação à empresa e atribuição à candidatura.
9. Campos JSON têm esquema e versão documentados; não recebem relações que necessitem de pesquisa ou integridade referencial.
10. Restrições que a base de dados não consiga exprimir ficam em serviços transacionais e testes, nunca apenas na interface.

## 12. Classificação e proteção de dados

| Classe | Exemplos | Tratamento mínimo |
| --- | --- | --- |
| Público ou catálogo | Designação de tipo documental, códigos de regras | Leitura controlada; alterações auditadas |
| Interno | Estados, tarefas, observações operacionais | Apenas utilizadores autorizados no âmbito |
| Pessoal | Nome, email, telefone, morada, situação profissional | Minimização, controlo por candidatura e retenção definida |
| Pessoal sensível para o processo | NIF, IBAN, comprovativos, decisões e valores individuais | Cifragem quando aplicável, mascaramento, downloads autorizados e auditoria |

Os dados usados na apresentação académica serão fictícios. Antes de qualquer utilização real serão definidas a base legal, a política de retenção, os direitos dos titulares e os procedimentos de incidente.

## 13. Decisões adiadas para a arquitetura técnica

Este modelo não decide ainda:

- a divisão exata das entidades por aplicações Django;
- o motor definitivo de base de dados e a infraestrutura de ficheiros;
- os nomes físicos de tabelas e índices;
- a biblioteca de cifragem do IBAN;
- o mecanismo de tarefas assíncronas e envio de email;
- a integração futura com Iefponline, DGERT, SIGO ou outros serviços;
- a política legal definitiva de retenção para utilização com dados reais.

Estas decisões não alteram o significado das entidades e serão tratadas nos tópicos técnicos seguintes.

## 14. Critérios de conclusão do dicionário

O dicionário está pronto para orientar a implementação quando:

1. cada uma das 38 entidades do modelo tem finalidade e campos essenciais definidos;
2. todas as relações indicam o seu âmbito e obrigatoriedade;
3. estados, valores oficiais e campos derivados têm uma fonte de verdade identificada;
4. documentos, transições, snapshots e auditoria preservam histórico imutável;
5. as restrições exclusivas, unicidades e coerência temporal estão explícitas;
6. não existem campos genéricos usados para substituir relações essenciais;
7. dados pessoais e financeiros têm tratamento planeado desde a modelação;
8. as decisões ainda abertas estão separadas das regras já fixadas.
