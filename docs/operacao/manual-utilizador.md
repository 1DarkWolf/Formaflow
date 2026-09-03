# Manual do utilizador

## 1. Finalidade

O Forma Flow apoia a preparação e o acompanhamento interno de candidaturas de formação. Não submete dados no Iefponline, não substitui decisões do IEFP e distingue sempre estimativas internas de valores oficiais.

O acesso depende do perfil atribuído à conta:

- **candidato:** consulta e prepara os seus próprios processos;
- **gestor de empresa:** trabalha apenas com empresas às quais está associado;
- **técnico ou analista:** acompanha candidaturas que lhe foram atribuídas;
- **administrador:** gere referências técnicas e configurações autorizadas.

## 2. Entrar e recuperar o acesso

1. Abra `/conta/entrar/` e introduza o email e a palavra-passe.
2. Se não se lembrar da palavra-passe, use `/conta/recuperar/`.
3. A mensagem de recuperação é sempre genérica, mesmo quando o email não existe.
4. Cinco falhas consecutivas no período configurado bloqueiam temporariamente novas tentativas para a mesma combinação de email e endereço de origem.

Uma conta de candidato criada em `/conta/registar/` fica inativa até ser ativada. Não partilhe credenciais nem reutilize a palavra-passe de demonstração noutros serviços.

## 3. Painel e notificações

Depois de iniciar sessão, o painel apresenta apenas os indicadores e as candidaturas permitidos pelo seu perfil. Os cartões de prazo destacam tarefas vencidas ou próximas do limite. A central `/workflow/notificacoes/` conserva os avisos internos, mesmo quando o envio por email está desligado.

Os filtros da lista de candidaturas podem ser combinados. A exportação CSV em `/candidaturas/exportar.csv` aplica o mesmo âmbito de acesso e deixa um evento de auditoria.

## 4. Preparar uma candidatura

1. Em `/candidaturas/nova/`, escolha candidatura individual ou empresarial.
2. Confirme o titular e, numa candidatura empresarial, adicione os beneficiários.
3. Associe as ações e componentes de formação.
4. Execute as verificações de elegibilidade apresentadas pelo sistema.
5. Selecione a conta de pagamento aplicável.
6. Abra a checklist documental e carregue os comprovativos pedidos em PDF.

Cada substituição de documento cria uma nova versão. A versão anterior e os snapshots de submissão não são apagados. Um ficheiro rejeitado não satisfaz o requisito documental.

## 5. Acompanhar o processo

O ecrã `/workflow/<identificador>/` apresenta o estado, a próxima ação e o histórico. As mudanças seguem as transições `TR-001` a `TR-023` documentadas no projeto.

- Na análise, um pedido de elementos suspende o prazo correspondente; a resposta completa permite retomá-lo.
- Uma decisão é registada por beneficiário e só depois origina o resultado global.
- Após uma decisão favorável, o termo de aceitação, a execução da formação e o pedido de encerramento são acompanhados separadamente.
- Revogações e correções administrativas acrescentam histórico; não substituem silenciosamente o registo original.

As ações que o utilizador não pode realizar não devem estar disponíveis. Uma tentativa por URL direta também é recusada.

## 6. Informação financeira

Os valores com a etiqueta **estimativa** são cálculos internos baseados nas regras aplicáveis. Um valor aprovado ou pago só é registado a partir de evidência oficial. Pagamentos e restituições usam chaves de idempotência para evitar duplicação acidental.

## 7. Ficheiros e dados pessoais

Os comprovativos são privados e descarregados apenas através de uma vista autorizada. Não envie dados pessoais reais no ambiente de demonstração. Termine sempre a sessão num computador partilhado e reporte acessos ou resultados inesperados ao responsável técnico.

## 8. Limites conhecidos

- Não existe integração automática com o portal do IEFP.
- O envio de email é opcional; os avisos internos são a fonte disponível na demonstração offline.
- As regras incluídas são referências fictícias para demonstração e têm de ser validadas antes de qualquer utilização real.
- O cenário de demonstração não representa uma decisão oficial nem movimenta dinheiro.
