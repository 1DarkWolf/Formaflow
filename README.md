# Forma Flow

Sistema web de controlo, acompanhamento e avisos para processos do Cheque-Formação, desenvolvido no âmbito da Prova de Aptidão Profissional (PAP).

## Estado do projeto

A implementação foi iniciada pelo `IMP-00 — Preparar a base do projeto`.

Estão disponíveis a estrutura Django, configurações por ambiente, página inicial, endpoint de saúde, primeiro conjunto de testes e verificações de qualidade. Os modelos de negócio e as migrações começam no `IMP-01`, com o utilizador próprio.

## Requisitos

- Python 3.12;
- PostgreSQL 17 para desenvolvimento completo;
- Git.

O ambiente usado para preparar o projeto tem Python 3.12.13, mas ainda não possui PostgreSQL instalado. O modo SQLite descrito abaixo serve apenas para executar a estrutura inicial; os testes de integração do domínio usarão PostgreSQL.

## Instalação local no Windows

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\development.txt
Copy-Item .env.example .env
```

Depois de criar a base e o utilizador PostgreSQL, ajuste as variáveis `POSTGRES_*` no ficheiro `.env`.

Ainda não execute `migrate`. O modelo de utilizador próprio será criado no `IMP-01` e tem de existir antes da primeira migração geral.

### Arranque temporário sem PostgreSQL

Para verificar apenas a página inicial e o endpoint de saúde enquanto PostgreSQL não estiver instalado:

```powershell
$env:DJANGO_DATABASE_ENGINE = "sqlite"
python manage.py runserver
```

Abra `http://127.0.0.1:8000/`. Este modo não valida restrições, bloqueios ou concorrência PostgreSQL.

## Verificações de desenvolvimento

```powershell
python -m ruff check .
python -m ruff format --check .
python manage.py check
python manage.py test --settings=config.settings.test
python -m coverage run manage.py test --settings=config.settings.test
python -m coverage report
```

O workflow do GitHub repete estas verificações com PostgreSQL 17.

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

## Endpoints iniciais

- `/` — página de confirmação da estrutura inicial;
- `/health/` — resposta de saúde da aplicação, sem dados internos.
