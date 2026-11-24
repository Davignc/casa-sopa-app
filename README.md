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
| Front-end (React): todas as telas, gráficos e troca de logo | — | ✅ |

## Stack

Python 3.12 · [uv](https://docs.astral.sh/uv/) · FastAPI · SQLAlchemy 2 + Alembic · PostgreSQL
(psycopg 3) · bcrypt + PyJWT · ReportLab (PDF) · openpyxl (planilhas) · APScheduler (backup) ·
pytest · Ruff · mypy. Front-end: React 19 · TypeScript · Vite · Tailwind · TanStack Query · Recharts · Vitest.

## Começando

Pré-requisitos: [uv](https://docs.astral.sh/uv/), Git e um PostgreSQL 16 (via Docker, instalado na
máquina ou, só para desenvolvimento, SQLite). O uv baixa o Python 3.12 sozinho. Node.js **não** é
necessário para rodar o sistema, só para alterar o front.

### 1. Código e dependências

```bash
git clone git@github.com:Davignc/casa-sopa-app.git && cd casa-sopa-app
git checkout dev             # o trabalho do dia a dia parte da dev
uv sync                      # cria .venv com as dependências (inclui as de dev/teste)
```

No Windows dentro do OneDrive, rode `$env:UV_LINK_MODE = "copy"` antes do `uv sync`.

### 2. Banco de dados

**Opção A — PostgreSQL no Docker (recomendada):**

```bash
docker run --name casa-sopa-db \
  -e POSTGRES_USER=casa_sopa -e POSTGRES_PASSWORD=casa_sopa -e POSTGRES_DB=casa_sopa \
  -p 5432:5432 -v casa-sopa-pgdata:/var/lib/postgresql/data -d postgres:16

# espere o PostgreSQL terminar de iniciar (na 1ª vez leva alguns segundos)
until docker exec casa-sopa-db pg_isready -U casa_sopa >/dev/null 2>&1; do sleep 1; done

# banco da suíte de testes (é recriado a cada execução do pytest)
docker exec -it casa-sopa-db psql -U casa_sopa -c "CREATE DATABASE casa_sopa_test;"
```

Nos dias seguintes basta `docker start casa-sopa-db`. O volume `casa-sopa-pgdata` mantém os dados
mesmo se o contêiner for removido.

**Opção B — PostgreSQL instalado na máquina:** crie o usuário e os bancos com o mesmo nome/senha
acima (ou ajuste as URLs no `.env`):

```sql
CREATE USER casa_sopa WITH PASSWORD 'casa_sopa';
CREATE DATABASE casa_sopa OWNER casa_sopa;
CREATE DATABASE casa_sopa_test OWNER casa_sopa;
```

**Opção C — SQLite (sem servidor, só desenvolvimento/testes):** no `.env`, use
`DATABASE_URL=sqlite:///./casa_sopa_dev.db` e `TEST_DATABASE_URL=sqlite://`. Ele não impõe o
tamanho de `VARCHAR` nem guarda fuso; a entrega deve usar PostgreSQL e a suíte deve passar nos dois.

### 3. Configuração (`.env`)

```bash
cp .env.example .env
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"   # cole em SECRET_KEY
```

As URLs do `.env.example` já apontam para o PostgreSQL da opção A. O `.env` nunca vai para o Git.

### 4. Tabelas, primeira administradora e servidor

```bash
uv run alembic upgrade head      # cria/atualiza as tabelas até a última migration
uv run python -m app.cli criar-admin --nome "Nome" --email admin@exemplo.org --telefone 16999990000
uv run fastapi dev app/main.py   # sistema em http://localhost:8000 · API em /docs
```

O `criar-admin` pede a senha no terminal (regras de senha forte valem aqui também); para uso não
interativo, defina `CASA_SOPA_ADMIN_SENHA`. Só é preciso uma vez: as demais contas são criadas pela
administradora na tela **Usuários**.

### 5. Conferir que está tudo certo

```bash
curl http://localhost:8000/health      # {"status":"ok","environment":"development"}
uv run alembic current                 # deve mostrar a mesma revisão que "uv run alembic heads"
uv run pytest                          # suíte completa (usa TEST_DATABASE_URL)
```

## Atualizar o banco local (migration mais recente)

Sempre que fizer `git pull`/merge que traga algo em `alembic/versions/` ou em `app/models/`:

```bash
git pull                       # ou merge da dev na sua branch
uv sync                        # se o uv.lock mudou
uv run alembic current         # revisão aplicada no seu banco
uv run alembic heads           # última revisão do código
uv run alembic upgrade head    # aplica o que falta, em ordem
uv run alembic check           # confirma que os modelos e o banco batem (sem diferenças)
```

Se `current` e `heads` mostrarem a mesma revisão, não há nada a aplicar. Para ver o SQL antes de
rodar: `uv run alembic upgrade <atual>:head --sql`. Para desfazer a última: `uv run alembic downgrade -1`.

As migrations usam IDs sequenciais (`0001`, `0002`…). Histórico atual:

| Revisão | O que faz |
|---|---|
| `0001` | Schema inicial conforme `casa_da_sopa_banco.sql` (8 tabelas, CHECKs, UNIQUEs, FKs) |
| `0002` | Tabela `venda_importada` (referências de vendas antigas importadas, contra duplicação). A importação foi removida do sistema; a tabela e o modelo ficam só para não perder dados de bancos já migrados |
| `0003` | **Dados de exemplo** para desenvolvimento (ver abaixo) |

**Dados de exemplo (`0003`).** Popula 4 vendedoras (1 inativa), 8 produtos (2 com estoque baixo),
18 clientes com endereços em Restinga e Franca e 70 pedidos espalhados nos últimos 4 meses, em todas
as situações, com movimentações de estoque coerentes. As datas são relativas ao dia em que a
migration roda. Login das vendedoras: `ana@exemplo.casadasopa.dev`, `beatriz@…`, `carla@…`
(`denise@…` está inativa), senha **`Exemplo@123`**. A administradora continua sendo a criada pelo
`criar-admin`.

Ela **não faz nada** com `ENVIRONMENT=production` ou se já existir algum produto cadastrado (aparece
um aviso no `upgrade`). Para tirar os dados: `uv run alembic downgrade 0002` (remove só o que ela criou).
Para gerar de novo com datas atualizadas: `uv run alembic downgrade 0002 && uv run alembic upgrade head`.

**Erro `Can't locate revision identified by 'dfa3097f5933'`:** o banco foi criado com a primeira
versão das migrations, que foi substituída pela `0001` quando os modelos foram alinhados ao script
SQL. O schema antigo é diferente, então **não** adianta só fazer `stamp`: recrie o banco local.

```bash
# PostgreSQL no Docker (apaga os dados locais)
docker exec -it casa-sopa-db psql -U casa_sopa -d postgres -c "DROP DATABASE casa_sopa;" -c "CREATE DATABASE casa_sopa;"
# SQLite
rm casa_sopa_dev.db

uv run alembic upgrade head
uv run python -m app.cli criar-admin --nome "Nome" --email admin@exemplo.org --telefone 16999990000
```

Se houver dados locais que importam, faça antes um backup (`POST /sistema/backup` ou
`pg_dump -Fc -U casa_sopa -h localhost casa_sopa > antes.dump`).

**Criar uma migration nova** (depois de alterar algo em `app/models/`):

```bash
uv run alembic revision --autogenerate --rev-id 0003 -m "descricao curta"
# revise o arquivo gerado em alembic/versions/ (o autogenerate não detecta tudo: renomeações,
# CHECKs e dados precisam de ajuste à mão), depois:
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
uv run pytest tests/test_modelagem.py
```

Modelo novo precisa ser importado em `app/models/__init__.py` (que `app/db/base.py` carrega),
senão o autogenerate não enxerga a tabela. Nunca edite uma migration que já foi para a `dev`:
crie outra.

## Front-end

O sistema já vem **compilado** em `app/web` e é servido pelo próprio backend: depois de `uv run fastapi dev app/main.py`,
abra <http://localhost:8000>. **Não precisa de Node.js** para usar. Página e API ficam na mesma origem (sem CORS).

| Tela | Quem | O que faz |
|---|---|---|
| Entrar | todos | Login com bloqueio de tentativas; logo da ONG |
| Início | todos | Administradora: resumo do mês e gráficos. Vendedora: andamento dos pedidos e atalhos. Estoque baixo e últimos pedidos |
| Clientes | todos | Cadastro, endereços (buscar um já registrado ou criar novo), histórico de compras |
| Pedidos | todos | Abas com contagem, mudança de situação com confirmação, cupom em PDF, novo pedido e edição |
| Produtos | todos | Cadastro e alerta de estoque baixo. **Administradora:** entradas, saídas e histórico de movimentações de cada produto, com filtros e gráfico |
| Relatórios | administradora | Gráficos que mudam conforme período, vendedora e agrupamento; comissões; exportar Excel/CSV |
| Usuários | administradora | Cadastro, edição, inativação e troca de senha |
| Configurações | administradora | Troca da logo e situação/execução do backup |

Pontos de comportamento:

- **Endereço:** ao cadastrar cliente ou pedido, dá para *buscar um endereço já registrado* (de qualquer cliente) ou *cadastrar um
  novo*. Ao escolher um registrado, aparece a seção "Dados deste endereço para este cliente" (número, complemento, referência
  e apelido), que é a relação cliente-endereço. No pedido, o endereço novo é guardado também no cadastro do cliente.
- **Gráficos:** vêm de `/relatorios/analise` e de `/estoque/movimentacoes/resumo`; mudar qualquer filtro refaz a consulta.
- **Logo:** a administradora troca em Configurações (PNG, JPG ou WebP, até 2 MB; o servidor confere o conteúdo e regrava o
  arquivo). Vale no menu, no login, na aba do navegador e no cupom impresso.
- **Segurança:** o token fica em `sessionStorage` (some ao fechar a aba); a página só carrega scripts do próprio servidor
  (CSP restritiva); as telas restritas também são barradas no servidor, que é quem decide.
- **Não incluído:** o protótipo mostrava *Caixa*, *taxa de entrega*, *valor recebido* e *data/hora de entrega*. Não estão nos
  requisitos nem no modelo de dados (`casa_da_sopa_banco.sql`), então não foram feitos.

### Acessibilidade, tema e LGPD

A interface oferece modo escuro no login e no cabeçalho, com preferência salva neste
navegador; sem escolha salva, acompanha o sistema. Há foco visível, atalho para o conteúdo,
abas operáveis por setas/Home/End, seleção de pedidos por teclado e diálogos/menu móvel
com foco contido e fechamento por Escape. Animações respeitam movimento reduzido.

Formulários de clientes, usuários, pedidos e login apresentam a finalidade do uso de
dados e orientações de atendimento. Esses avisos são medidas de transparência, não uma
certificação de conformidade integral com a LGPD. A administração deve definir o canal
de atendimento, a base legal aplicável e os prazos de guarda conforme suas operações.
Inativação mantém o histórico e não equivale à exclusão. Referência:
[orientações da ANPD](https://www.gov.br/anpd/pt-br/acesso-a-informacao/perguntas-frequentes).

### Alterar o front (precisa de Node.js 20+)

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, conversando com a API em :8000 (rode o backend junto)
npm test         # testes (Vitest)
npm run build    # compila para ../app/web  (commite o resultado)
```

## API

Documentação interativa em `/docs` (desligada com `ENVIRONMENT=production`). Todas as rotas,
exceto login e `/health`, exigem `Authorization: Bearer <token>`. **Admin** = administradora;
**Todos** = administradora e vendedora.

| Área | Rotas | Quem |
|---|---|---|
| Autenticação | `POST /auth/login` (form) · `POST /auth/login/json` · `POST /auth/logout` · `GET /usuarios/me` | Todos |
| Usuários | `POST/GET /usuarios` · `GET/PATCH/DELETE /usuarios/{id}` · `POST /usuarios/{id}/reativar` | Admin |
| Clientes | `POST/GET /clientes` · `GET/PATCH/DELETE /clientes/{id}` · `POST .../reativar` | Todos |
| Endereços | `GET /enderecos?busca=` (já registrados) · `POST /clientes/{id}/enderecos` (novo, ou `id_endereco` de um existente) · `PATCH/DELETE /clientes/{id}/enderecos/{id_endereco}` | Todos |
| Produtos | `POST/GET /produtos` · `GET/PATCH/DELETE /produtos/{id}` · `POST .../reativar` | Todos |
| Estoque | `GET /estoque/alertas` | Todos |
| | `POST /estoque/entradas` · `POST /estoque/saidas` · `GET /estoque/movimentacoes` · `GET /estoque/movimentacoes/resumo` | Admin |
| Pedidos | `POST/GET /pedidos` · `GET /pedidos/contagem` (por situação) · `GET/PATCH/DELETE /pedidos/{id}` · `POST /pedidos/{id}/status` · `GET /pedidos/{id}/cupom` | Todos |
| Relatórios | `GET /relatorios/dashboard` · `/relatorios/analise` (gráficos) · `/relatorios/vendas` · `/relatorios/vendas/pedidos` · `/relatorios/vendas/exportar` | Admin |
| Sistema | `GET/POST /sistema/backup` · `POST/DELETE /sistema/logo` · `GET /sistema/logo/situacao` | Admin |
| | `GET /sistema/logo` (a tela de login precisa dela) | Pública |

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
- Só a vendedora responsável pelo pedido e as administradoras podem editar, excluir ou mudar o
  status. A autorização é conferida no servidor antes de mexer em dados ou estoque, inclusive em
  chamadas diretas à API.
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
- Relatórios incluem pedidos de vendedoras e administradoras. O filtro **Perfil de usuário** escolhe
  só vendedoras, só administradoras ou todos; **Responsável** filtra uma pessoa, inclusive inativa.
  Gráficos, totais e exportações usam os mesmos filtros. Administradoras não recebem comissão. A API
  mantém `id_vendedora`, `vendedoras` e `por_vendedora` por compatibilidade; `cargo` é opcional.
- Exportação: XLSX (resumo + pedidos) ou CSV (pedidos, `;` e vírgula decimal). Textos que começam
  com `= + - @` são neutralizados contra injeção de fórmula.

## Segurança

- **Senhas novas:** mínimo de 8 caracteres, com letra maiúscula, minúscula, número e símbolo;
  máximo de 72 bytes (limite do bcrypt). Cadastro, troca de senha e criação de administradora
  pelo terminal aplicam a mesma regra. A tela mostra os requisitos durante a digitação.
  Senhas existentes continuam válidas no login. Os caracteres da senha, inclusive espaços,
  são preservados; espaços não contam como símbolo.
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

## Logo e arquivos enviados

A logo personalizada fica em `UPLOADS_DIR` (padrão `uploads/`, fora do Git). Sem ela, vale a logo padrão em
`app/assets/logo-padrao.png`. O envio aceita só PNG, JPG e WebP, confere o **conteúdo** (não o nome nem o tipo informado),
recusa SVG e imagens enormes e regrava como PNG de até 512 px, descartando metadados.

## Modelo de dados

Oito tabelas conforme `casa_da_sopa_banco.sql` (colunas em `snake_case`): `usuario`, `produto`,
`cliente`, `endereco`, `cliente_endereco`, `vendas`, `item_vendas`, `movimentacoes`, mais a
`venda_importada` (histórica, ver migration `0002`). Exclusão lógica
por `is_ativo` (nada é apagado, RM06). Lacunas conhecidas do modelo: não há data/horário de entrega
no pedido (RF11/RF14), nem usuário em `movimentacoes` (RF22, contornado na observação), nem colunas
de bloqueio de login (feito em memória).

Migrations e atualização do banco local: ver [Atualizar o banco local](#atualizar-o-banco-local-migration-mais-recente).

## Testes e qualidade

```bash
uv run pytest                                        # toda a suíte
uv run pytest --cov=app --cov-report=term-missing    # com cobertura
uv run ruff check . && uv run ruff format --check .  # lint e formatação
uv run mypy app/                                     # tipos
uv run pre-commit install                            # lint/format a cada commit
```

A suíte do backend (~760 testes) roda em PostgreSQL e em SQLite; o front tem ~315 (`npm test`).
`test_app.py` varre **todas as operações da API** (lidas do OpenAPI) e falha se alguma de dados ficar sem login.
`test_contrato_front.py` lê o código do front e falha se ele chamar uma rota que a API não tem.

## Estrutura

```
app/
├── main.py        # app, CORS, cabeçalhos, ciclo de vida (backup)
├── cli.py         # criar-admin
├── api/deps.py    # sessão, usuário atual, permissões (AdminAtual, OperadorAtual)
├── core/          # config, segurança, proteções, erros, validadores, fuso, períodos, SPA
├── models/        # tabelas  ·  schemas/ entrada e saída  ·  routers/ endpoints
└── services/      # regras de negócio (pedido, estoque, relatório, cupom, backup...)
alembic/versions/  # migrations  ·  tests/
frontend/          # código-fonte do front (React)  ·  app/web/  # front compilado, servido pelo backend
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
- **Alembic não vê tabela nova:** importe o modelo em `app/models/__init__.py`.
- **`Can't locate revision identified by 'dfa3097f5933'`:** banco criado com a migration antiga; recrie-o
  (ver [Atualizar o banco local](#atualizar-o-banco-local-migration-mais-recente)).
- **`relation ... does not exist` ao subir ou nos testes:** faltou `uv run alembic upgrade head`, ou o
  banco `casa_sopa_test` não existe.
- **`connection refused` na porta 5432:** o PostgreSQL não está rodando (`docker start casa-sopa-db`).
- **Porta 5432 ocupada** por outro PostgreSQL: publique o contêiner em outra porta (`-p 5433:5432`) e
  ajuste as URLs do `.env`.
