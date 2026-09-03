# Forma Flow

Sistema web de controlo, acompanhamento e avisos para processos do Cheque-Formação, desenvolvido no âmbito da Prova de Aptidão Profissional (PAP).

## Estado do projeto

A implementação concluiu os incrementos `IMP-00` a `IMP-06`, desde a base do projeto até ao encerramento administrativo da candidatura.

Estão disponíveis autenticação por email, organizações com âmbito de acesso, regras imutáveis e candidaturas individuais ou empresariais preparadas por etapas. A checklist documental mantém PDFs privados e versões; o workflow regista `TR-001` a `TR-023`, termo de aceitação, execução das formações, snapshots, prazos, suspensões, pedidos finais, decisões por beneficiário, revogação e correções auditáveis sem executar decisões no Iefponline. O próximo incremento é o `IMP-07`, dedicado ao circuito financeiro detalhado.

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

Depois de criar a base e o utilizador PostgreSQL, ajuste as variáveis `POSTGRES_*` no ficheiro `.env` e execute:

```powershell
python manage.py migrate
python manage.py carregar_dados_demonstracao
python manage.py createsuperuser
python manage.py runserver
```

O comando `carregar_dados_demonstracao` é idempotente e cria apenas referências claramente fictícias: uma empresa, uma entidade formadora, parâmetros, tipos documentais e feriados. O conjunto de regras fica em rascunho e deve ser revisto e publicado em `/regras/` antes de criar uma candidatura. O comando `createsuperuser` cria a primeira conta com acesso à administração técnica. No ambiente local, as mensagens de ativação e recuperação são apresentadas no terminal e não são enviadas para endereços reais.

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

## Endpoints disponíveis

- `/` — página inicial;
- `/health/` — resposta de saúde da aplicação, sem dados internos;
- `/conta/registar/` — criação e ativação de conta de candidato;
- `/conta/entrar/` e `/conta/sair/` — início e fim de sessão;
- `/conta/recuperar/` — recuperação de palavra-passe;
- `/conta/painel/` — painel autenticado;
- `/candidaturas/` — candidaturas visíveis e assistente de preparação;
- `/candidaturas/nova/` — criação de rascunho individual ou empresarial;
- `/documentos/candidatura/<uuid>/` — checklist e comprovativos privados da candidatura;
- `/workflow/<uuid>/` — acompanhamento, termo, execução, encerramento e histórico imutável;
- `/organizacoes/empresas/` — empresas visíveis no âmbito do utilizador;
- `/regras/` — versões de regras visíveis e publicação autorizada;
- `/admin/` — administração técnica para contas autorizadas.
