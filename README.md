# Casa da Sopa de Restinga — Sistema de Gestão

API do sistema de gestão da **Casa da Sopa de Restinga**, organização social que arrecada
recursos para suas ações de assistência à comunidade por meio da venda de sacos de lixo.
O sistema informatiza o controle de clientes, produtos, estoque e pedidos, e é de **uso
interno**: só a administradora e as vendedoras acessam.

> Projeto semestral — Fatec Franca. Documentação de referência: Documento de Requisitos,
> Diagrama de Casos de Uso, Documento de Modelagem de Dados (v5) e `casa_da_sopa_banco.sql`.

## Módulos

| Módulo | Requisitos | Situação |
|---|---|---|
| S0 — Alinhamento ao modelo de dados, RBAC base, erros centralizados | — | ✅ |
| M1 — Autenticação e usuários | RF01–RF06 | 🟡 login, `/me` e cadastro (admin) prontos |
| M2 — Clientes | RF07–RF10 | ⬜ |
| M4 — Produtos e estoque | RF17–RF25 | ⬜ |
| M3 — Pedidos | RF11–RF16, RF26 | ⬜ |
| M5 — Relatórios e dashboard | RF27–RF28 | ⬜ |

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| Gerenciador de pacotes | [uv](https://docs.astral.sh/uv/) |
| API | FastAPI |
| ORM / migrations | SQLAlchemy 2.x / Alembic |
| Banco | PostgreSQL (driver psycopg 3) |
| Testes | pytest |
| Lint / formatação / tipos | Ruff / mypy |

## Começando

Pré-requisitos: [uv](https://docs.astral.sh/uv/getting-started/installation/), Git e um PostgreSQL
(local ou Docker). O uv baixa o Python correto sozinho (`.python-version`).

```bash
git clone <url-do-repositorio>
cd casa-sopa-app
uv sync                      # cria o .venv e instala as dependências travadas
cp .env.example .env         # depois edite o .env (veja "Variáveis de ambiente")
```

### Banco de dados

```bash
docker run --name casa-sopa-db \
  -e POSTGRES_USER=casa_sopa -e POSTGRES_PASSWORD=casa_sopa -e POSTGRES_DB=casa_sopa \
  -p 5432:5432 -d postgres:16

# banco usado pelos testes
docker exec casa-sopa-db psql -U casa_sopa -c "CREATE DATABASE casa_sopa_test;"

uv run alembic upgrade head  # aplica as migrations
```

### Primeira administradora

Só uma administradora cadastra usuários (RN03), então a primeira é criada por comando:

```bash
uv run python -m app.cli criar-admin --nome "Nome" --email admin@exemplo.org --telefone 16999990000
```

A senha é pedida no terminal (mínimo 8 caracteres).

### Rodando

```bash
uv run fastapi dev app/main.py
```

API em <http://localhost:8000> · Swagger em `/docs` · ReDoc em `/redoc`
(a documentação interativa fica desligada com `ENVIRONMENT=production`).

## Modelo de dados

Oito tabelas, conforme o script `casa_da_sopa_banco.sql` (os nomes das colunas estão em
`snake_case`): `usuario`, `produto`, `cliente`, `endereco`, `cliente_endereco`, `vendas`,
`item_vendas`, `movimentacoes`.

- **Exclusão lógica:** usuários, clientes, produtos e endereços são inativados (`is_ativo`),
  nunca apagados — o histórico de vendas e movimentações é preservado (RM06).
- **Endereço de entrega:** `vendas (id_cliente, id_endereco)` referencia `cliente_endereco`;
  o banco recusa um endereço que não seja do cliente da venda (RM05).
- **Preço no item:** `item_vendas.preco_unitario_v` guarda o preço praticado; reajustar o
  produto não altera vendas antigas.
- **Fora do modelo:** fornecedores (RM03), comprovante de PIX e integração bancária.
- Os `CHECK`s do script (valores não negativos, subtotal coerente, comissão de 0 a 100,
  coerência entre tipo de referência e venda) fazem parte da migration.

### Migrations

```bash
uv run alembic revision --autogenerate -m "descricao"   # após alterar app/models/
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic check                                      # modelos e banco estão iguais?
```

Revise o arquivo gerado antes de commitar. Todo modelo novo precisa ser importado em
`app/db/base.py`, senão o Alembic não o enxerga.

## Permissões (RN01, RNF04)

O cargo (`administradora` ou `vendedora`) é lido do banco **a cada requisição**: rebaixar ou
inativar uma usuária vale na hora, sem esperar o token expirar. Rotas restritas usam as
dependências de `app/api/deps.py` (`AdminAtual`, `exige_cargo(...)`).

## Testes e qualidade

```bash
uv run pytest                                       # toda a suíte (usa TEST_DATABASE_URL)
uv run pytest --cov=app --cov-report=term-missing   # com cobertura
uv run ruff check . && uv run ruff format --check . # lint e formatação
uv run mypy app/                                    # tipos
uv run pre-commit install                           # lint/format automáticos a cada commit
```

`tests/test_modelagem.py` verifica que o **próprio banco** recusa dados inválidos (CHECKs,
UNIQUEs, chave composta de endereço, RESTRICT/CASCADE), independentemente da API.

## Estrutura

```
app/
├── main.py            # instância do FastAPI e registro dos routers
├── cli.py             # comandos (criar-admin)
├── core/              # config, segurança (hash/JWT), erros, validadores
├── db/                # Base declarativa, sessão
├── models/            # tabelas (SQLAlchemy)
├── schemas/           # entrada/saída (Pydantic)
├── routers/           # endpoints
├── services/          # regras de negócio
└── api/deps.py        # dependências: sessão, usuário atual, permissões
alembic/versions/      # migrations (versionadas!)
tests/
```

| Preciso de... | Vai em... |
|---|---|
| Uma nova tabela | `app/models/` + importar em `app/db/base.py` + migration |
| Validação de entrada/saída | `app/schemas/` |
| Um endpoint | `app/routers/` (e registrar em `app/main.py`) |
| Regra de negócio | `app/services/` (lançar subclasses de `ErroDeNegocio`) |
| Configuração nova | `app/core/config.py` + `.env.example` |

## Variáveis de ambiente

Ficam no `.env` (**nunca** versionado). Use o `.env.example` como referência.

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Conexão do PostgreSQL |
| `TEST_DATABASE_URL` | Banco da suíte de testes (recriado a cada execução) |
| `SECRET_KEY` | Assinatura dos JWT — **obrigatória, mínimo 32 caracteres** |
| `ALGORITHM` | Algoritmo do JWT (padrão `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do token (padrão 60) |
| `ENVIRONMENT` | `development`, `staging` ou `production` |

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"   # gera uma SECRET_KEY
```

## Fluxo de trabalho com Git

```bash
git checkout dev && git pull
git checkout -b feat/nome-da-funcionalidade
# desenvolva, rodando uv run pytest
git add . && git commit -m "feat: adiciona cadastro de clientes"
git push -u origin feat/nome-da-funcionalidade   # e abra o Pull Request para dev
```

Prefixos de commit: `feat:` · `fix:` · `refactor:` · `test:` · `docs:` · `chore:`.

Devem ser commitados: `pyproject.toml` + `uv.lock` (sempre juntos), `.python-version`,
`alembic/versions/*.py` e o `.env.example`.

## Solução de problemas

- **`uv sync` reclama da versão do Python** — rode `uv python install`.
- **Erro de conexão com o banco** — confira se o Postgres está no ar (`docker ps`) e se a
  `DATABASE_URL` do `.env` bate com as credenciais.
- **Alembic não vê uma tabela nova** — importe o modelo em `app/db/base.py`.
- **A aplicação não sobe e cita `SECRET_KEY`** — ela está vazia ou tem menos de 32 caracteres.
