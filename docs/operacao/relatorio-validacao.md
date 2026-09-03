# Relatório de validação da entrega

## 1. Ambiente local

- Data: 3 de setembro de 2026.
- Python: 3.12.13.
- Django: 5.2.17.
- Base usada na suíte local: SQLite temporária.
- PostgreSQL 17: configurado no CI e no Docker Compose.
- Docker: não disponível na máquina da validação local; a construção fica a cargo do CI.

## 2. Resultados obtidos

| Verificação | Resultado |
| --- | --- |
| Ruff, regras de código | passou |
| Ruff, formatação | passou |
| Verificação de dependências Python | passou |
| Migrações por gerar | nenhuma |
| Suíte Django | 199 testes passaram |
| Cobertura combinada | 84,4%, acima do mínimo de 80% |
| Testes do utilitário de backup | 5 testes passaram |
| Instalação limpa e migrações | passou numa pasta temporária |
| Cenário executado duas vezes | passou sem duplicar candidaturas ou avisos |
| `check --deploy --fail-level WARNING` | passou sem avisos |
| Integração PostgreSQL 17 e Docker no GitHub | passou |

As mensagens `404`, `403`, `400` e de falha de email observadas na suíte pertencem a casos negativos intencionais e os testes respetivos passaram.

## 3. Verificações no GitHub

O workflow `.github/workflows/ci.yml` repete qualidade, testes e migrações sobre PostgreSQL 17. Também cria um backup cifrado, restaura-o numa segunda base, confirma as duas candidaturas fictícias e constrói a imagem Docker. Um erro em qualquer passo impede o sucesso do job.

A [execução 33799105775](https://github.com/1DarkWolf/Formaflow/actions/runs/33799105775), relativa ao commit `9491d66`, terminou com sucesso em todos os passos.

## 4. Limitações da evidência

- A validação local usa SQLite; a evidência complementar sobre PostgreSQL 17 foi obtida no GitHub Actions.
- A imagem Docker não foi construída localmente porque o executável não está instalado nesta máquina.
- Não foi criado alojamento público, domínio ou certificado; essa alteração continua sujeita a autorização própria.
- Não foram usados dados reais nem efetuadas chamadas ao Iefponline.
- O relatório Word e a apresentação PowerPoint originais estão fora do repositório e devem ser sincronizados com o plano de demonstração antes da entrega escolar final.

## 5. Aceitação técnica

A entrega satisfaz os portões automatizados definidos para o repositório, incluindo o workflow PostgreSQL/Docker. Antes da entrega escolar final permanece necessária a revisão humana do percurso de demonstração e dos artefactos académicos externos.
