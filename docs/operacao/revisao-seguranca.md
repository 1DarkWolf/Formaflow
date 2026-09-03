# Revisão de segurança e permissões

## 1. Resultado

A revisão final cobre autenticação, autorização por objeto, ficheiros, dados sensíveis, operação e publicação. Os controlos são comprovados por testes automatizados e devem continuar a ser revistos quando o âmbito mudar.

| Área | Controlo implementado | Evidência |
| --- | --- | --- |
| Autenticação | Email normalizado, mensagens genéricas, política mínima de 12 caracteres e bloqueio temporário por chave HMAC | Testes de autenticação positivos, negativos e de limite |
| Âmbito | Seletores filtrados por candidato, empresa ou atribuição; a interface não é a barreira de segurança | Testes de acesso direto a objetos de outro âmbito |
| Sessão e navegador | Cookies seguros em produção, CSRF, HSTS, CSP, `frame-ancestors`, `X-Frame-Options` e política de permissões | `check --deploy` e testes de cabeçalhos |
| Ficheiros | Apenas PDF validado, limite configurado, permissões restritivas, storage privado e download autorizado | Testes de upload, versão e acesso negado |
| Dados sensíveis | IBAN cifrado, identificadores pesquisáveis por HMAC, mascaramento e ausência de valores em URLs | Testes de segurança das organizações |
| Integridade | Transições, snapshots e auditoria imutáveis; chaves idempotentes; bloqueio transacional | Testes de workflow, concorrência e repetição |
| Erros | Páginas genéricas sem repetir o caminho ou detalhes técnicos | Teste da resposta 404 com `DEBUG=False` |
| Segredos | Configuração por ambiente, valores de exemplo não operacionais e ficheiro `.env` ignorado | Verificação do repositório e configuração de produção fail-fast |
| Recuperação | Dump e uploads no mesmo pacote cifrado, manifesto SHA-256 e restauro isolado | Testes unitários e ensaio PostgreSQL no CI |

## 2. Decisões operacionais

- O limite de tentativas é local à base de dados e adequado à entrega atual. Uma publicação distribuída deve usar um limitador partilhado no proxy ou numa cache central.
- A CSP não permite scripts externos. Uma nova integração visual exige revisão explícita da política.
- `DJANGO_TRUST_PROXY_HEADERS` fica desligado por omissão para não confiar em cabeçalhos enviados diretamente por clientes.
- O health check revela apenas nome e estado do serviço.
- O cenário de demonstração usa apenas o domínio reservado `example.test` e dados marcados como fictícios.

## 3. Verificações antes de cada publicação

1. Executar a suíte completa e `check --deploy --fail-level WARNING`.
2. Procurar segredos, bases locais, uploads e dados pessoais no diff.
3. Rever alterações a seletores, permissões, downloads e transições.
4. Criar e restaurar um backup numa base separada.
5. Confirmar HTTPS, cabeçalhos, cookies e proxy no domínio final.
6. Rodar chaves imediatamente se existir suspeita de exposição.

## 4. Fora do âmbito atual

Não foram realizados testes de intrusão externos, análise dinâmica num domínio público ou auditoria independente. Não existem recursos públicos criados por este incremento; a publicação real mantém-se sujeita a autorização própria.
