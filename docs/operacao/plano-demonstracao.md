# Plano de demonstração da PAP

## 1. Preparação

1. Arranque a aplicação local e confirme `/health/`.
2. Execute `carregar_cenario_demonstracao` com uma palavra-passe temporária.
3. Tenha abertas as contas fictícias `admin.demo@example.test`, `gestor.demo@example.test`, `candidato.demo@example.test` e `beneficiario.demo@example.test`.
4. Confirme que existem as referências `DEMO-IND-001` e `DEMO-EMP-001`.
5. Mantenha uma cópia de segurança recente e evite qualquer dependência de Internet durante a apresentação.

## 2. Percurso principal, cerca de 10 minutos

| Tempo | Perfil | Ação | Evidência a destacar |
| ---: | --- | --- | --- |
| 1 min | candidato | Entrar e abrir o painel | Indicadores limitados ao próprio âmbito e aviso de prazo |
| 2 min | candidato | Abrir `DEMO-IND-001` e a checklist | Formação, verificações e requisitos documentais no mesmo processo |
| 2 min | gestor | Abrir `DEMO-EMP-001` | Beneficiário empresarial e isolamento por empresa |
| 2 min | técnico/admin | Mostrar análise e histórico | Transições imutáveis, pedido de elementos e suspensão de prazo |
| 1 min | técnico/admin | Mostrar decisão e termo | Decisão oficial separada do cálculo interno |
| 1 min | gestor | Mostrar encerramento e financeiro | Estimativa, movimentos e restituição identificados separadamente |
| 1 min | utilizador autorizado | Exportar CSV e abrir notificações | Relatório mínimo auditado e alertas idempotentes |

## 3. Robustez a demonstrar

- repita `python manage.py processar_alertas`: não surgem avisos duplicados;
- tente abrir por URL uma candidatura fora do âmbito: o acesso é recusado;
- mostre que a substituição de um PDF mantém a versão anterior;
- explique que cinco falhas de autenticação causam bloqueio temporário sem revelar se a conta existe;
- apresente o resultado de cobertura e o ensaio de instalação limpa;
- mostre o procedimento de backup e o restauro sempre para uma base isolada.

## 4. Plano de contingência

- Se o email não estiver disponível, use as notificações internas.
- Se a Internet falhar, toda a demonstração continua com os dados locais fictícios.
- Se a instância principal falhar, use a cópia previamente restaurada e validada, não um restauro improvisado durante a apresentação.
- Se não houver Docker, use o ambiente virtual e SQLite apenas para a apresentação; identifique que PostgreSQL é o ambiente alvo.

## 5. Mensagem final

O Forma Flow é um sistema de controlo e rastreabilidade do processo. Organiza pessoas, formação, documentos, prazos, decisões e movimentos financeiros sem se apresentar como substituto do portal oficial nem como origem de decisões do IEFP.
