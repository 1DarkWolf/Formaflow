# Forma Flow

Sistema web de controlo, acompanhamento e avisos para processos do Cheque-Formação, desenvolvido no âmbito da Prova de Aptidão Profissional (PAP).

## Estado do projeto

A implementação concluiu os incrementos `IMP-00` a `IMP-09`, desde a base do projeto até à robustez, demonstração e publicação reproduzível do MVP.

Estão disponíveis autenticação por email com proteção contra tentativas repetidas, organizações com âmbito de acesso, regras imutáveis e candidaturas individuais ou empresariais preparadas por etapas. A checklist documental mantém PDFs privados e versões; o workflow regista `TR-001` a `TR-023`, termo de aceitação, execução das formações, snapshots, prazos, suspensões, pedidos finais, decisões por beneficiário, revogação e correções auditáveis sem executar decisões no Iefponline. O circuito financeiro separa estimativas, decisões oficiais, movimentos efetivos e restituições. O painel é adaptado ao perfil, os avisos de prazo são idempotentes e a exportação CSV autorizada deixa um registo imutável. A entrega inclui cenário fictício offline, contentores, verificações de produção e backup PostgreSQL cifrado.

## Requisitos

- Python 3.12;
- PostgreSQL 17 para desenvolvimento completo;
- Git;
- Docker com Compose, opcional para a demonstração em contentores.

O modo SQLite descrito abaixo serve para experimentação local e para a verificação offline. A integração final, o backup e o restauro usam PostgreSQL 17 no workflow automatizado.

## Instalação local no Windows

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\development.txt
Copy-Item .env.example .env
```

Depois de criar a base e o utilizador PostgreSQL, ajuste as variáveis `POSTGRES_*` no ficheiro `.env` e execute:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

O comando `carregar_dados_demonstracao` continua disponível para criar apenas os catálogos. Para preparar o percurso completo da PAP, forneça uma palavra-passe temporária forte e execute:

```powershell
$env:FORMAFLOW_DEMO_PASSWORD = Read-Host "Palavra-passe temporária"
python manage.py carregar_cenario_demonstracao
```

O cenário completo é idempotente e usa apenas referências fictícias e endereços `example.test`. O comando `createsuperuser` cria a primeira conta com acesso à administração técnica. No ambiente local, as mensagens de ativação e recuperação são apresentadas no terminal e não são enviadas para endereços reais.

Para atualizar diariamente os avisos de prazo, execute ou agende:

```powershell
python manage.py processar_alertas
```

Os avisos internos estão sempre disponíveis. O envio adicional por email fica desativado por omissão; para o ativar, configure `NOTIFICATION_EMAIL_ENABLED=true` e um backend de email adequado ao ambiente.

Em desenvolvimento, as chaves de proteção de dados são derivadas da chave do Django quando `DATA_ENCRYPTION_KEY` e `DATA_HASH_KEY` ficam vazias. Em produção, defina valores independentes e secretos. Pode gerar valores adequados com:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use o primeiro resultado em `DATA_ENCRYPTION_KEY` e o segundo em `DATA_HASH_KEY`. Nunca os guarde no Git.

### Arranque temporário sem PostgreSQL

Para experimentar a aplicação enquanto PostgreSQL não estiver instalado:

```powershell
$env:DJANGO_DATABASE_ENGINE = "sqlite"
python manage.py migrate
python manage.py runserver
```

Abra `http://127.0.0.1:8000/`. Este modo permite testar a interface e a autenticação, mas não substitui a validação de restrições, bloqueios e concorrência em PostgreSQL.

## Verificações de desenvolvimento

```powershell
python -m ruff check .
python -m ruff format --check .
python manage.py check
python manage.py test --settings=config.settings.test
python -m coverage run manage.py test --settings=config.settings.test
python -m coverage report --fail-under=80
python -m unittest discover -s scripts/tests -v
python scripts/verify_release.py
```

O workflow do GitHub repete estas verificações com PostgreSQL 17, ensaia o backup/restauro cifrado e constrói a imagem Docker.

## Documentação

- [Tópico 01 - Âmbito e objetivos](docs/planeamento/01-ambito-e-objetivos.md)
- [Tópico 02 - Perfis e permissões](docs/planeamento/02-perfis-e-permissoes.md)
- [Tópico 03 - Regras de negócio](docs/planeamento/03-regras-de-negocio.md)
- [Tópico 04 - Fluxo e estados da candidatura](docs/planeamento/04-fluxo-e-estados.md)
- [Tópico 05 - Modelo de dados definitivo](docs/planeamento/05-modelo-de-dados.md)
  - [Dicionário de dados](docs/planeamento/05-dicionario-de-dados.md)
- [Tópico 06 - Arquitetura técnica](docs/planeamento/06-arquitetura-tecnica.md)
  - [Plano de implementação](docs/planeamento/06-plano-de-implementacao.md)
- [Tópico 07 - Interface e experiência do utilizador](docs/planeamento/07-interface-e-experiencia.md)
  - [Inventário de ecrãs e wireframes](docs/planeamento/07-inventario-e-wireframes.md)
- [Tópico 08 - Testes, validação e demonstração](docs/planeamento/08-plano-de-testes.md)
  - [Catálogo de casos de teste](docs/planeamento/08-catalogo-casos-teste.md)
- [Manual do utilizador](docs/operacao/manual-utilizador.md)
- [Instalação e publicação](docs/operacao/instalacao-publicacao.md)
- [Backup e restauro](docs/operacao/backup-restauro.md)
- [Plano de demonstração](docs/operacao/plano-demonstracao.md)
- [Revisão de segurança](docs/operacao/revisao-seguranca.md)
- [Relatório de validação](docs/operacao/relatorio-validacao.md)
- [Revisão da interface](docs/operacao/revisao-interface.md)

## Endpoints disponíveis

- `/` — página inicial;
- `/health/` — resposta de saúde da aplicação, sem dados internos;
- `/conta/registar/` — criação e ativação de conta de candidato;
- `/conta/entrar/` e `/conta/sair/` — início e fim de sessão;
- `/conta/recuperar/` — recuperação de palavra-passe;
- `/conta/painel/` — painel autenticado;
- `/candidaturas/` — candidaturas visíveis e assistente de preparação;
- `/candidaturas/exportar.csv` — relatório CSV mínimo, filtrado pelo mesmo âmbito;
- `/candidaturas/nova/` — criação de rascunho individual ou empresarial;
- `/documentos/candidatura/<uuid>/` — checklist e comprovativos privados da candidatura;
- `/workflow/<uuid>/` — acompanhamento, termo, execução, encerramento e histórico imutável;
- `/workflow/notificacoes/` — central pessoal de avisos;
- `/organizacoes/empresas/` — empresas visíveis no âmbito do utilizador;
- `/regras/` — versões de regras visíveis e publicação autorizada;
- `/admin/` — administração técnica para contas autorizadas.
