# Casa de Sopa — Sistema de Gestão de Vendas

Sistema de gestão de vendas desenvolvido para a **Casa de Sopa**, ONG que promove o desenvolvimento social de crianças e adolescentes por meio de projetos culturais e esportivos, e que também distribui sopa a pessoas em situação de vulnerabilidade.

A ONG financia suas atividades por meio da venda de sacos de lixo. Este sistema centraliza o controle dessas vendas, do estoque e dos valores recebidos, dando à equipe visibilidade sobre a verba arrecadada para sustentar os projetos sociais.

---

## Índice

- [Funcionalidades](#funcionalidades)
- [Stack](#stack)
- [Pré-requisitos](#pré-requisitos)
- [Configuração do ambiente](#configuração-do-ambiente)
- [Banco de dados](#banco-de-dados)
- [Rodando o projeto](#rodando-o-projeto)
- [Testes](#testes)
- [Qualidade de código](#qualidade-de-código)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Fluxo de trabalho com Git](#fluxo-de-trabalho-com-git)
- [Comandos úteis](#comandos-úteis)

---

## Funcionalidades

- Registro e acompanhamento de vendas
- Controle de estoque de produtos
- Acompanhamento dos valores recebidos
- Anexo de comprovantes de PIX
- Relatórios financeiros e de estoque

---

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| Gerenciador de pacotes | uv |
| API | FastAPI |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Banco de dados | PostgreSQL |
| Driver | psycopg 3 |
| Testes | pytest |
| Lint / Format | Ruff |
| Storage de arquivos | Cloudflare R2 (compatível com S3) |

---

## Pré-requisitos

- **uv** — gerenciador de pacotes e versões do Python
- **PostgreSQL** — local ou em nuvem
- **Git**

### Instalando o uv

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Confirme a instalação:

```bash
uv --version
```

> Não é necessário instalar o Python manualmente. O `uv` cuida disso a partir do arquivo `.python-version` do projeto.

---

## Configuração do ambiente

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd casa_sopa
```

### 2. Instale as dependências

```bash
uv sync
```

Este comando cria o ambiente virtual em `.venv/`, baixa a versão correta do Python e instala todas as dependências travadas no `uv.lock`.

> **Não é preciso ativar o `.venv` manualmente.** Use `uv run <comando>` e o uv resolve o ambiente automaticamente.

### 3. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com os valores do seu ambiente local. Veja a seção [Variáveis de ambiente](#variáveis-de-ambiente).

---

## Banco de dados

### Subindo um Postgres local com Docker

```bash
docker run --name casa-sopa-db \
  -e POSTGRES_USER=casa_sopa \
  -e POSTGRES_PASSWORD=casa_sopa \
  -e POSTGRES_DB=casa_sopa \
  -p 5432:5432 \
  -d postgres:16
```

A `DATABASE_URL` correspondente:

```
postgresql+psycopg://casa_sopa:casa_sopa@localhost:5432/casa_sopa
```

### Aplicando as migrations

```bash
uv run alembic upgrade head
```

### Criando uma nova migration

Sempre que alterar ou criar um modelo em `app/models/`:

```bash
uv run alembic revision --autogenerate -m "descricao da mudanca"
uv run alembic upgrade head
```

> Revise o arquivo gerado em `alembic/versions/` antes de commitar. O autogenerate não detecta tudo (renomeações de coluna, mudanças de tipo em alguns casos).

### Desfazendo a última migration

```bash
uv run alembic downgrade -1
```

---

## Rodando o projeto

```bash
uv run fastapi dev app/main.py
```

A API sobe em `http://localhost:8000` com reload automático.

Documentação interativa:

- Swagger UI — http://localhost:8000/docs
- ReDoc — http://localhost:8000/redoc

---

## Testes

```bash
# rodar toda a suíte
uv run pytest

# com relatório de cobertura
uv run pytest --cov=app --cov-report=term-missing

# um arquivo específico
uv run pytest tests/test_vendas.py

# um teste específico
uv run pytest tests/test_vendas.py::test_criar_venda
```

---

## Qualidade de código

```bash
# verificar problemas
uv run ruff check .

# corrigir automaticamente o que for possível
uv run ruff check . --fix

# formatar
uv run ruff format .

# checagem de tipos
uv run mypy app/
```

### Hooks de pre-commit

Instale uma única vez após clonar:

```bash
uv run pre-commit install
```

A partir daí, lint e format rodam automaticamente a cada commit.

---

## Estrutura do projeto

```
casa_sopa/
├── alembic/
│   └── versions/          # migrations (versionadas!)
├── app/
│   ├── main.py            # instância do FastAPI
│   ├── core/
│   │   └── config.py      # settings via pydantic-settings
│   ├── db/
│   │   ├── base.py        # Base declarativa do SQLAlchemy
│   │   └── session.py     # engine e sessão
│   ├── models/            # modelos SQLAlchemy (tabelas)
│   ├── schemas/           # schemas Pydantic (entrada/saída)
│   ├── routers/           # endpoints da API
│   └── services/          # regras de negócio
├── tests/
├── .env.example
├── .python-version
├── alembic.ini
├── pyproject.toml
└── uv.lock
```

### Onde colocar cada coisa

| Preciso de... | Vai em... |
|---|---|
| Uma nova tabela | `app/models/` |
| Validação de request/response | `app/schemas/` |
| Um novo endpoint | `app/routers/` |
| Regra de negócio, cálculo | `app/services/` |
| Uma configuração nova | `app/core/config.py` + `.env.example` |

---

## Variáveis de ambiente

Todas ficam no `.env` (que **não** é versionado). Use o `.env.example` como referência.

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | String de conexão do PostgreSQL |
| `SECRET_KEY` | Chave para assinatura dos tokens JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Tempo de expiração do token de acesso |
| `S3_ENDPOINT_URL` | Endpoint do bucket (Cloudflare R2) |
| `S3_ACCESS_KEY_ID` | Chave de acesso do bucket |
| `S3_SECRET_ACCESS_KEY` | Segredo de acesso do bucket |
| `S3_BUCKET_NAME` | Nome do bucket dos comprovantes |
| `ENVIRONMENT` | `development`, `staging` ou `production` |

> Nunca commite o `.env`. Se adicionar uma variável nova, adicione também ao `.env.example` (sem o valor real) para o resto da equipe saber que ela existe.

Para gerar uma `SECRET_KEY`:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Fluxo de trabalho com Git

1. Atualize a `main` e crie sua branch:

   ```bash
   git checkout main
   git pull
   git checkout -b feat/nome-da-funcionalidade
   ```

2. Desenvolva, rodando os testes conforme avança:

   ```bash
   uv run pytest
   ```

3. Commit e push:

   ```bash
   git add .
   git commit -m "feat: adiciona registro de vendas"
   git push -u origin feat/nome-da-funcionalidade
   ```

4. Abra o Pull Request.

### Prefixos de commit

| Prefixo | Quando usar |
|---|---|
| `feat:` | Nova funcionalidade |
| `fix:` | Correção de bug |
| `refactor:` | Mudança de código sem alterar comportamento |
| `test:` | Adição ou ajuste de testes |
| `docs:` | Documentação |
| `chore:` | Configuração, dependências, tarefas de manutenção |

### Arquivos que devem ser commitados

- `pyproject.toml` e `uv.lock` — sempre juntos, ao adicionar ou remover dependências
- `.python-version`
- `alembic/versions/*.py` — as migrations são parte do código
- `.env.example` — sempre que uma variável nova for adicionada

---

## Comandos úteis

| Ação | Comando |
|---|---|
| Instalar dependências | `uv sync` |
| Adicionar uma lib | `uv add <pacote>` |
| Adicionar lib de desenvolvimento | `uv add --dev <pacote>` |
| Remover uma lib | `uv remove <pacote>` |
| Atualizar dependências | `uv sync --upgrade` |
| Ver árvore de dependências | `uv tree` |
| Rodar a API | `uv run fastapi dev app/main.py` |
| Rodar os testes | `uv run pytest` |
| Aplicar migrations | `uv run alembic upgrade head` |
| Abrir um shell Python no projeto | `uv run python` |

---

## Solução de problemas

**`uv sync` reclama da versão do Python**

O projeto está pinado no `.python-version`. Rode `uv python install` para que o uv baixe a versão correta.

**Erro de conexão com o banco**

Verifique se o Postgres está rodando (`docker ps`) e se a `DATABASE_URL` no `.env` bate com as credenciais do container.

**Alembic não encontra os modelos no autogenerate**

Todo modelo novo precisa ser importado em `app/db/base.py`, senão o Alembic não enxerga a tabela.