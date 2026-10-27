# Casa da Sopa de Restinga — Sistema de Gestão (API)

API do sistema de gestão da **Casa da Sopa de Restinga**, organização social que arrecada
recursos para suas ações de assistência à comunidade por meio da venda de sacos de lixo.
O sistema informatiza clientes, produtos, estoque, pedidos e relatórios, e é de **uso
interno**: só a administradora e as vendedoras acessam.

> Projeto semestral — Fatec Franca. Referências: Documento de Requisitos, Diagrama de Casos de
> Uso, Documento de Modelagem de Dados (v5) e `casa_da_sopa_banco.sql`.

## Situação

| Módulo | Requisitos | Situação |
|---|---|---|
| Autenticação e usuários | RF01–RF06 | ✅ |
| Clientes e endereços | RF07–RF10 | ✅ |
| Produtos e estoque | RF17–RF25 | ✅ |
| Pedidos, status e cupom em PDF | RF11–RF16, RF26 | ✅ |
| Dashboard e relatórios | RF27–RF28 | ✅ |
| Backup semanal | RNF03 | ✅ |
| Front-end | — | ⬜ próxima etapa |

## Stack

Python 3.12 · [uv](https://docs.astral.sh/uv/) · FastAPI · SQLAlchemy 2 + Alembic · PostgreSQL
(psycopg 3) · bcrypt + PyJWT · ReportLab (PDF) · openpyxl (planilhas) · APScheduler (backup) ·
pytest · Ruff · mypy.

## Começando

Pré-requisitos: uv, Git e um PostgreSQL (ou use o SQLite, abaixo). O uv baixa o Python certo.

```bash
git clone <url-do-repositorio> && cd casa-sopa-app
uv sync                      # no Windows/OneDrive: $env:UV_LINK_MODE = "copy" antes
cp .env.example .env         # edite: SECRET_KEY (mín. 32 caracteres) e o banco
uv run alembic upgrade head  # cria as tabelas
uv run python -m app.cli criar-admin --nome "Nome" --email admin@exemplo.org --telefone 16999990000
uv run fastapi dev app/main.py   # http://localhost:8000/docs
```

**Banco com Docker:**
`docker run --name casa-sopa-db -e POSTGRES_USER=casa_sopa -e POSTGRES_PASSWORD=casa_sopa -e POSTGRES_DB=casa_sopa -p 5432:5432 -d postgres:16`
(e `CREATE DATABASE casa_sopa_test;` para os testes).

**Sem Docker nem PostgreSQL (SQLite, só desenvolvimento/testes):** no `.env`, use
`DATABASE_URL=sqlite:///./casa_sopa_dev.db` e `TEST_DATABASE_URL=sqlite://`. Ele não impõe o
tamanho de `VARCHAR` nem guarda fuso; a entrega deve usar PostgreSQL e a suíte deve passar nos dois.

## API

Documentação interativa em `/docs` (desligada com `ENVIRONMENT=production`). Todas as rotas,
exceto login e `/health`, exigem `Authorization: Bearer <token>`. **Admin** = administradora;
**Todos** = administradora e vendedora.

| Área | Rotas | Quem |
|---|---|---|
| Autenticação | `POST /auth/login` (form) · `POST /auth/login/json` · `POST /auth/logout` · `GET /usuarios/me` | Todos |
| Usuários | `POST/GET /usuarios` · `GET/PATCH/DELETE /usuarios/{id}` · `POST /usuarios/{id}/reativar` | Admin |
| Clientes | `POST/GET /clientes` · `GET/PATCH/DELETE /clientes/{id}` · `POST .../reativar` | Todos |
| Endereços | `POST /clientes/{id}/enderecos` · `PATCH/DELETE /clientes/{id}/enderecos/{id_endereco}` | Todos |
| Produtos | `POST/GET /produtos` · `GET/PATCH/DELETE /produtos/{id}` · `POST .../reativar` | Todos |
| Estoque | `GET /estoque/alertas` | Todos |
| | `POST /estoque/entradas` · `POST /estoque/saidas` · `GET /estoque/movimentacoes` | Admin |
| Pedidos | `POST/GET /pedidos` · `GET/PATCH/DELETE /pedidos/{id}` · `POST /pedidos/{id}/status` · `GET /pedidos/{id}/cupom` | Todos |
| Relatórios | `GET /relatorios/dashboard` · `/relatorios/vendas` · `/relatorios/vendas/pedidos` · `/relatorios/vendas/exportar` | Admin |
| Sistema | `GET/POST /sistema/backup` | Admin |

Listagens são paginadas (`limit` até 100, `offset`) e devolvem `{itens, total, limit, offset}`.
Erros vêm como `{"detail": "mensagem em português"}`; 401 sem login, 403 sem permissão, 404 não
encontrado, 409 conflito com o estado atual, 422 dado inválido, 429 muitas tentativas de login.

## Regras de negócio adotadas

Pontos que os documentos não detalham e que ficaram definidos assim (mudam em um só lugar):

**Pedidos**
- Status: `em_aberto → confirmado → entregue`; `cancelado` vale a partir de em aberto ou confirmado.
  `entregue` e `cancelado` são finais.
- O cliente da API envia só produtos e quantidades. **Preço, subtotal e total são calculados no
  servidor** com o preço do cadastro; o preço do item fica gravado e não muda com reajustes.
- O estoque **só muda na confirmação** (baixa; `409` listando o que falta) e no **cancelamento de
  pedido confirmado** (devolução). Tudo vira registro em `movimentacoes`. Pedido em aberto pode
  ser criado sem estoque suficiente.
- Edição: em aberto, tudo; confirmado, só pagamento, endereço e observação; entregue/cancelado,
  nada. A vendedora responsável não muda (RN10). Só pedido em aberto pode ser excluído (RN11).
- O endereço de entrega precisa ser um endereço **ativo do próprio cliente** (RM05).
- Cupom (PDF A5, uma página por via): `via=interna|entregador|cliente|todas`. Pedido cancelado não gera cupom.

**Estoque e produtos**
- A quantidade só muda por entrada, saída ou venda, nunca por edição do produto, então a soma do
  histórico sempre bate com o estoque. A quantidade inicial entra como 1ª movimentação.
- Alerta (RN14): ativo e `estoque_atual <= estoque_minimo`.
- Entradas e saídas manuais são da administradora. Como `movimentacoes` não tem coluna de usuário,
  o responsável vai no final da observação (`[por Nome]`).

**Clientes**
- Telefone único, gravado só com dígitos. Endereço físico igual (CEP, cidade, bairro, logradouro) é
  reaproveitado entre clientes; número, complemento e referência são de cada cliente.
- Remover endereço: nunca usado em pedido, é apagado; usado, é inativado; usado e compartilhado com
  outro cliente, recusa. Para corrigir rua/CEP, cadastre o novo e remova o antigo.

**Relatórios**
- "Venda" = pedido confirmado ou entregue, pela data da venda no fuso `TIMEZONE`. Dashboard = últimos 30 dias.
- Comissão = valor × percentual **atual** da vendedora: «a receber» sobre os entregues, «pendente»
  sobre os confirmados. (O modelo não guarda o percentual da época da venda.)
- Exportação: XLSX (resumo + pedidos) ou CSV (pedidos, `;` e vírgula decimal). Textos que começam
  com `= + - @` são neutralizados contra injeção de fórmula.

## Segurança

- **Login:** após `LOGIN_MAX_TENTATIVAS` erros (5) a resposta vira `429` por `LOGIN_BLOQUEIO_MINUTOS`
  (15), por par IP+e-mail e por IP; mensagem e tempo iguais para e-mail inexistente (sem enumerar contas).
- **Sessão:** JWT (HS256) com id único; o logout o revoga; trocar a senha de um usuário derruba as
  sessões dele; o cargo e a situação ativa são lidos do banco a cada requisição.
- **Entrada:** campos desconhecidos são recusados (sem *mass assignment*); e-mail/telefone/CEP normalizados.
- **Banco:** CHECKs, UNIQUEs e FKs do script SQL valem mesmo se a API falhar (`tests/test_modelagem.py`);
  linhas de pedido e produto são bloqueadas (`FOR UPDATE`) contra confirmação/venda simultânea.
- **HTTP:** `nosniff`, `X-Frame-Options`, `no-store`; CORS só para `CORS_ORIGINS`; erros 500 não vazam detalhes.
- **Limite conhecido:** bloqueio de login e tokens revogados ficam **em memória** (valem por processo e
  zeram ao reiniciar). Com um único servidor atende; se crescer, mover para Redis. Atrás de proxy
  reverso, rode o uvicorn com `--proxy-headers`.

## Backup (RNF03)

Com `BACKUP_ENABLED=true`, o servidor roda `pg_dump` toda semana (`BACKUP_DIA_SEMANA`, `BACKUP_HORA`,
no fuso configurado), mantém os `BACKUP_RETENCAO` mais recentes em `BACKUP_DIR` e, se o servidor estava
desligado na hora, roda ao voltar. `GET /sistema/backup` mostra o resultado; o campo **`alerta`**
acende se a última tentativa falhou, se passou de 8 dias sem backup ou se está desligado em produção
(o front deve exibir `motivo_alerta` em destaque). `POST /sistema/backup` faz um backup na hora.
Requer o `pg_dump` instalado (ou `PG_DUMP_PATH`). A senha vai por variável de ambiente, nunca na linha de comando.

**Restaurar** (testado): crie um banco vazio e rode
`pg_restore --no-owner -h <host> -U <usuario> -d <banco_vazio> backups/casa_sopa_AAAAMMDD_HHMMSS.dump`

Os arquivos têm **todos os dados**, inclusive os hashes de senha: proteja a pasta e copie-os para fora do servidor.

## Modelo de dados

Oito tabelas conforme `casa_da_sopa_banco.sql` (colunas em `snake_case`): `usuario`, `produto`,
`cliente`, `endereco`, `cliente_endereco`, `vendas`, `item_vendas`, `movimentacoes`. Exclusão lógica
por `is_ativo` (nada é apagado, RM06). Lacunas conhecidas do modelo: não há data/horário de entrega
no pedido (RF11/RF14), nem usuário em `movimentacoes` (RF22, contornado na observação), nem colunas
de bloqueio de login (feito em memória).

```bash
uv run alembic revision --autogenerate -m "descricao"   # após alterar app/models/
uv run alembic upgrade head | downgrade -1 | check
```

## Testes e qualidade

```bash
uv run pytest                                        # toda a suíte
uv run pytest --cov=app --cov-report=term-missing    # com cobertura
uv run ruff check . && uv run ruff format --check .  # lint e formatação
uv run mypy app/                                     # tipos
uv run pre-commit install                            # lint/format a cada commit
```

A suíte (~620 testes) roda em PostgreSQL e em SQLite. `test_app.py` varre todas as rotas e falha se
alguma de dados ficar sem login.

## Estrutura

```
app/
├── main.py        # app, CORS, cabeçalhos, ciclo de vida (backup)
├── cli.py         # criar-admin
├── api/deps.py    # sessão, usuário atual, permissões (AdminAtual, OperadorAtual)
├── core/          # config, segurança, proteções, erros, validadores, fuso, formatação
├── models/        # tabelas  ·  schemas/ entrada e saída  ·  routers/ endpoints
└── services/      # regras de negócio (pedido, estoque, relatório, cupom, backup...)
alembic/versions/  # migrations  ·  tests/
```

## Variáveis de ambiente

Ficam no `.env` (**nunca** versionado); o `.env.example` lista todas, com comentários.
Obrigatórias: `DATABASE_URL` e `SECRET_KEY` (≥ 32 caracteres). Gere a chave com
`uv run python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Git

Branch `feat/...` a partir de `dev`, commits `feat: / fix: / refactor: / test: / docs: / chore:`, Pull
Request para `dev`. Versione `pyproject.toml` + `uv.lock`, `.python-version`, `alembic/versions/*.py` e `.env.example`.

## Problemas comuns

- **`uv sync` com `os error 396`** (pasta no OneDrive): `$env:UV_LINK_MODE = "copy"`.
- **Não sobe e cita `SECRET_KEY`:** vazia ou com menos de 32 caracteres.
- **Backup falha com "pg_dump não encontrado":** instale o cliente do PostgreSQL ou defina `PG_DUMP_PATH`.
- **Alembic não vê tabela nova:** importe o modelo em `app/db/base.py`.
