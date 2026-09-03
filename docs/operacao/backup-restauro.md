# Backup e restauro

## 1. Âmbito

Um backup completo junta o dump PostgreSQL e a pasta de uploads privados. O pacote contém um manifesto SHA-256 e é cifrado integralmente com Fernet. A chave do backup deve ser diferente das chaves da aplicação e guardada fora do servidor e do repositório.

O utilitário é adequado ao volume académico do projeto porque cifra o pacote em memória. Para conjuntos de dados grandes deve ser substituído por uma solução de cópia cifrada em fluxo e armazenamento gerido.

## 2. Pré-requisitos

- `pg_dump` e `pg_restore` da mesma versão principal do servidor ou mais recente;
- variáveis `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` e `POSTGRES_PORT`;
- `BACKUP_ENCRYPTION_KEY` com uma chave Fernet válida;
- acesso de leitura a `PRIVATE_UPLOAD_ROOT`.

Gerar uma chave no PowerShell:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 3. Criar um backup

```powershell
python scripts/backup_restore.py backup --output D:\Backups\formaflow-2026-09-03.ffbackup
```

O utilitário recusa substituir um ficheiro existente. Depois da criação, copie o pacote para armazenamento separado, registe a data e confirme que a chave de restauro continua acessível. Nunca envie a chave junto do pacote.

## 4. Ensaio de restauro

Crie uma base PostgreSQL vazia e uma pasta de destino vazia. Nunca comece por restaurar sobre a base ativa.

```powershell
createdb --host=127.0.0.1 --username=formaflow formaflow_restore
python scripts/backup_restore.py restore `
  --input D:\Backups\formaflow-2026-09-03.ffbackup `
  --target-database formaflow_restore `
  --uploads-target D:\Restauros\formaflow_uploads
```

O restauro valida a cifra, impede caminhos que escapem da pasta temporária e compara cada ficheiro com o manifesto antes de chamar `pg_restore`.

Quando a aplicação corre com o `compose.yaml`, a base fica acessível apenas em `127.0.0.1` e os uploads estão num volume. Copie primeiro os uploads para uma pasta local e indique essa pasta ao backup:

```powershell
docker compose cp web:/data/private_uploads D:\BackupInput\private_uploads
python scripts/backup_restore.py backup `
  --uploads D:\BackupInput\private_uploads `
  --output D:\Backups\formaflow-contentor.ffbackup
```

O Python e o cliente PostgreSQL 17 usados pelo comando são os do computador anfitrião. Se alterar `POSTGRES_HOST_PORT` no Compose, use o mesmo valor em `POSTGRES_PORT` ao executar o backup.

## 5. Validação e recuperação

1. Aponte uma instância isolada da aplicação para `formaflow_restore` e para a pasta restaurada.
2. Execute `python manage.py check --settings=config.settings.production`.
3. Confirme contagens de candidaturas, utilizadores, transições, documentos e notificações.
4. Inicie sessão com uma conta de teste autorizada.
5. Abra uma candidatura, consulte o histórico e descarregue um documento privado.
6. Registe a data, duração e resultado do ensaio.
7. Só depois de validação e autorização promova a base restaurada ou altere o tráfego.

Se a validação falhar, mantenha a aplicação original sem alterações, preserve o pacote para diagnóstico e repita o restauro numa nova base vazia. A opção `--allow-source-database` existe apenas para uma recuperação deliberadamente autorizada e não deve ser usada num ensaio normal.

## 6. Periodicidade recomendada

Para uma demonstração escolar, crie um backup antes de cada ensaio geral e antes de qualquer migração. Numa utilização contínua, defina uma política proporcional ao volume de alterações, automatize a cópia para outro local e teste regularmente um restauro completo. Um ficheiro criado mas nunca restaurado não constitui uma estratégia de recuperação validada.
