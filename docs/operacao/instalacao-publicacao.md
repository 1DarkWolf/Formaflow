# Instalação e publicação

## 1. Instalação de desenvolvimento

Requisitos: Python 3.12, Git e PostgreSQL 17. No PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\development.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py check
python manage.py runserver
```

Preencha primeiro as variáveis `POSTGRES_*` no `.env`. SQLite pode ser usado para uma demonstração temporária, mas a validação final de restrições e concorrência deve usar PostgreSQL.

## 2. Cenário offline de demonstração

Defina uma palavra-passe temporária forte apenas na sessão atual e carregue o cenário:

```powershell
$env:FORMAFLOW_DEMO_PASSWORD = Read-Host "Palavra-passe temporária"
python manage.py carregar_cenario_demonstracao
python manage.py processar_alertas
```

O comando pode ser repetido sem duplicar os objetos principais. Cria quatro contas com domínio reservado `example.test`, uma candidatura empresarial com pedido de elementos e decisão parcial, uma candidatura individual encerrada com pagamentos fictícios, formação, documentos, histórico e prazo urgente. A palavra-passe não é apresentada no terminal nem guardada no repositório.

## 3. Verificação de entrega

Com as dependências de desenvolvimento e produção instaladas:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m coverage run manage.py test --settings=config.settings.test
python -m coverage report --fail-under=80
python -m unittest discover -s scripts/tests -v
python scripts/verify_release.py
```

O último comando cria uma base SQLite temporária, aplica todas as migrações, carrega duas vezes o cenário fictício, processa alertas e executa `check --deploy` com configuração de produção descartável. A pasta temporária é removida no fim.

## 4. Demonstração local com contentores

1. Copie `.env.example` para `.env`.
2. Substitua todas as chaves e palavras-passe de exemplo por valores aleatórios.
3. Mantenha o `.env` fora do Git.
4. Execute:

```powershell
docker compose up --build -d
docker compose exec web python manage.py carregar_cenario_demonstracao
docker compose ps
```

Abra `http://127.0.0.1:8000/`. O `compose.yaml` desativa HTTPS apenas para esta demonstração local. Os dados PostgreSQL e os uploads privados ficam em volumes persistentes.

Para parar sem apagar dados:

```powershell
docker compose down
```

Não use `docker compose down --volumes` sem um backup confirmado, porque essa opção remove os volumes locais.

## 5. Publicação atrás de HTTPS

A imagem executa Gunicorn como utilizador sem privilégios e serve os ficheiros estáticos com WhiteNoise. O PostgreSQL e os uploads privados devem usar armazenamento persistente. No ambiente final:

- use `config.settings.production`;
- defina `DJANGO_SECRET_KEY`, `DATA_ENCRYPTION_KEY`, `DATA_HASH_KEY` e credenciais PostgreSQL independentes;
- defina `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` com o domínio real;
- mantenha o redirecionamento HTTPS, cookies seguros e HSTS ativos;
- ative `DJANGO_TRUST_PROXY_HEADERS=true` apenas quando um proxy controlado substituir corretamente `X-Forwarded-Proto`;
- mantenha uploads fora de qualquer diretório público;
- execute as migrações uma única vez por publicação controlada;
- confirme `/health/`, autenticação, upload privado e uma transição autorizada.

Antes de publicar:

```powershell
python manage.py check --deploy --fail-level WARNING --settings=config.settings.production
python manage.py migrate --noinput --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production
```

O alojamento público, DNS, certificado e eventuais custos continuam a exigir uma decisão explícita do responsável pelo projeto.
