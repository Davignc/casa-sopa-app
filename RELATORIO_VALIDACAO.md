# Relatório de alterações e validação

Data: 16/11/2026, referência de calendário America/Sao_Paulo.

## Estado preservado e trabalho concluído

A retomada partiu dos arquivos existentes. Foram revisados os diffs dos arquivos
versionados, os fontes novos do frontend/backend, seus contratos e os resultados de
testes disponíveis. As alterações anteriores de clientes, endereços, produtos,
estoque, logo, cupom, gráficos, configuração e dependências foram preservadas.
O arquivo `.env` não foi editado e suas credenciais não foram incluídas nos resultados.

- **Relatórios:** incluem administradoras e vendedoras. Há filtros por perfil
  (todos, só vendedoras, só administradoras) e por responsável. A seleção de uma
  pessoa é limpa ao trocar de perfil. A lista de responsáveis percorre a paginação
  da API, incluindo pessoas inativas. Gráficos, totais, pedidos e exportações
  CSV/Excel usam os mesmos filtros. Administradoras não recebem comissão.
- **Pedidos:** somente a responsável e as administradoras podem editar, excluir
  e mudar o status. A API valida a autorização antes de alterar dados ou estoque.
  A interface desabilita as ações indevidas, apresenta o status sem controle de
  edição e bloqueia a URL de edição de pedido alheio.
- **Formulários e privacidade:** avisos de finalidade nos cadastros de clientes e
  usuários, nos pedidos e no login; indicação de campos obrigatórios, orientação
  para evitar dados sensíveis e para solicitar atendimento sobre dados pessoais.
  Inativação e exclusão são distinguidas nos avisos.
- **Acessibilidade:** rótulos e erros associados aos campos, indicação acessível
  de obrigatoriedade, foco no primeiro erro, foco visível, atalho ao conteúdo,
  seleção de pedido por teclado, abas com setas/Home/End e ajustes na busca de
  clientes. Diálogos e menu móvel contêm o foco, isolam o fundo, fecham por Escape
  e restauram o foco. Diálogos aninhados fecham somente a janela superior.
  Avisos continuam disponíveis durante os diálogos e animações respeitam a
  preferência por movimento reduzido.
- **Modo escuro e contraste:** tema disponível no login e no cabeçalho, salvo
  neste navegador, com preferência inicial do sistema. Foram ajustados textos,
  campos, tabelas, alertas, status, legendas e cores dos gráficos nos dois temas.
- **Suporte do frontend:** reconstruída a pasta `frontend/src/lib`, que estava
  ausente, e corrigida sua exclusão pelo padrão `lib/` do `.gitignore`. Foram
  restaurados os tipos, comunicação com a API, autenticação, permissões e
  formatação. Os testes conferem também preço brasileiro com separador de milhar,
  casas decimais excedentes e limites aceitos pelo servidor.

## Correções finalizadas após a retomada

1. Confirmada a correção do cabeçalho de cache dos arquivos estáticos no Windows:
   o reconhecimento da pasta `assets` usa os componentes do caminho, em vez de
   depender exclusivamente da barra `/`.
2. Corrigidos dois problemas de contraste encontrados em navegador real nas
   legendas dos relatórios. As legendas usam texto legível e as cores dos elementos
   gráficos se adaptam ao tema.
3. Finalizadas a revisão de tipagem, a compilação de produção e as suítes de testes.
4. Validado o fluxo completo com navegador, API real, migração e banco descartável.
   O encerramento da API de teste foi ajustado para liberar o arquivo SQLite no
   Windows; a execução final encerrou e removeu os recursos temporários.

## Resultados

| Verificação | Resultado |
| --- | --- |
| Backend: suíte completa em SQLite temporário | **778 testes aprovados** |
| Frontend: suíte completa | **270 testes aprovados**, em 19 arquivos |
| Frontend: `npm run typecheck` | Aprovado |
| Backend: `python -m mypy app/` | Aprovado, 58 arquivos sem problemas |
| Produção: `npm run build` | Aprovado; saída atualizada em `app/web` |
| Formatação dos oito arquivos Python diretamente envolvidos | Aprovada |
| `git diff --check` | Aprovado |
| Navegador Edge, pedidos e relatórios, claro/escuro | Sem falhas na checagem de contraste dos textos visíveis examinados |
| Pedidos em largura de 390 px | Sem transbordamento da página na checagem executada |
| Menu móvel em navegador real | Foco dentro do diálogo, fundo inerte e fechamento por Escape aprovados |

Os testes de backend incluem autorização, integridade de estoque, filtros por
cargo/responsável, exportações, contratos de rotas do frontend, clientes, endereços,
produtos, cupom, logo, autenticação, proteção e entrega dos arquivos estáticos.

No fluxo integrado, a migração Alembic `0001` foi aplicada em um banco novo e
descartável. A interface compilada foi servida pelo FastAPI e acessada pelo Edge:

- A confirmação de pedido pela tela persistiu o status e baixou o estoque para
  **95 unidades**, conforme as quantidades fictícias preparadas.
- O filtro de administradoras exibiu somente sua responsável e o total esperado
  de **R$ 30,00**, consistente com a API e o banco.
- Outra vendedora recebeu **403** em edição, mudança de status e exclusão de
  pedidos alheios. Os controles da tela ficaram bloqueados e o estoque continuou
  em **95 unidades**.
- Não foram capturadas exceções JavaScript no percurso verificado.

Logs, imagem da interface e inventário final dos arquivos modificados/novos:
[artifacts/validacao](artifacts/validacao/).
Comandos principais para repetição das suítes:

```powershell
# Na raiz: banco em memória, sem usar os dados configurados no .env.
$env:TEST_DATABASE_URL = 'sqlite://'
.\.venv\Scripts\python.exe -m pytest -ra
.\.venv\Scripts\python.exe -m mypy app/

# Na pasta frontend:
npm.cmd run typecheck
npm.cmd run build
npm.cmd test -- --maxWorkers=2 --reporter=dot
```

## Pendências e limites da validação

- **PostgreSQL local configurado no `.env`:** a tentativa de conexão somente de
  leitura retornou `OperationalError` por esgotamento do prazo de conexão. Não foi
  possível confirmar nesse servidor a conectividade, o esquema ou as migrações.
  A causa do servidor não responder não foi determinada.
  A integração e as suítes foram validadas com SQLite; isso não substitui a
  validação posterior no PostgreSQL do ambiente, inclusive da concorrência de
  atualizações de estoque. Não foram feitas alterações nesse PostgreSQL.
- **LGPD:** falta definir o e-mail/telefone oficial para solicitações sobre dados.
  Os avisos orientam procurar a administração pelos canais habituais. Base legal,
  prazos de guarda e procedimentos operacionais devem ser definidos pela
  organização. Os ajustes implementam medidas de transparência e acesso; não
  representam certificação de conformidade jurídica integral. Referência:
  [orientações da ANPD](https://www.gov.br/anpd/pt-br/acesso-a-informacao/perguntas-frequentes).
- **Acessibilidade:** a verificação automatizada cobre os componentes e os
  percursos descritos, não uma auditoria integral de conformidade nem testes com
  leitor de tela real. A medição de contraste não avaliou todos os estados,
  conteúdos possíveis ou fundos com gradiente.
- **Avisos das ferramentas:** o backend emite dois avisos de descontinuação de
  dependências do TestClient. O ambiente jsdom dos testes do frontend emite
  avisos de dimensões de gráficos e avisos pontuais do ambiente de teste; os
  gráficos renderizaram no navegador real. Não houve falhas nas suítes finais.

O trabalho permanece no diretório local, incluindo os fontes novos e o frontend
compilado. Os arquivos que já estavam modificados ou sem rastreamento antes desta
tarefa continuam preservados.

## Versão 2

O login orienta o contato com a administradora para redefinir senhas.
A importação de planilhas foi removida da interface e da API.
A exportação de relatórios em Excel/CSV foi mantida.
A tabela histórica de controle de importações e sua migração foram preservadas
para manter compatibilidade com bancos existentes, sem apagar registros.

Após essa remoção, passaram 75 testes selecionados do backend (permissões,
contrato, API e relatórios) e os 270 testes da interface. A compilação de produção
foi atualizada. Evidências em `artifacts/validacao/backend-versao-2.txt`,
`frontend-versao-2.txt` e `build-versao-2.txt`.

## Senhas fortes — 17/11/2026

- Cadastro e troca de senha exigem pelo menos 8 caracteres, letra maiúscula,
  letra minúscula, número e símbolo, com limite de 72 bytes para o bcrypt.
  A criação da primeira administradora pelo terminal usa a mesma validação.
- O formulário exibe uma lista de requisitos que se atualiza durante a digitação,
  associada ao campo para tecnologias assistivas. Espaços não contam como símbolo.
- Os caracteres da senha são preservados, inclusive espaços nas extremidades.
  O login continua aceitando senhas antigas. Editar outros dados sem informar
  uma nova senha mantém a credencial existente.
- Erros de validação da API retornam tipo, localização e mensagem, sem repetir os
  valores enviados nem o contexto que poderia incluir senhas ou o formulário inteiro.
- Os testes abrangem requisitos ausentes, confirmação, cadastro, troca, CLI,
  compatibilidade com senhas antigas, Unicode e limites em caracteres/bytes.
- Validação do backend: **814 testes aprovados**, usando `TEST_DATABASE_URL=sqlite://`
  e uma pasta `--basetemp` exclusiva dentro de `.pytest_cache`, pois a pasta
  temporária padrão do Windows não estava acessível neste ambiente.
- Tela de usuários: **23 testes aprovados** na execução final, com preenchimento
  por colagem nos cenários de formulário e digitação no teste dos requisitos ao vivo.
- Compilação de produção e TypeScript aprovados; saída atualizada em `app/web`.
  `mypy app/` aprovado (59 arquivos) e Ruff aprovado nos arquivos Python alterados.
- A execução completa do frontend terminou com **273/277 testes aprovados**.
  Os dois casos de usuários dessa execução foram resolvidos pelo ajuste do
  preenchimento de teste e passaram na suíte final de 23 testes. As falhas
  restantes envolveram seleção de cliente/endereço em pedidos e reativação de
  produto após filtros. Uma execução separada desses dois arquivos terminou
  com **45/47 aprovados**, com falhas nesses fluxos de interação; os fontes
  dessas funcionalidades e seus testes não foram alterados nesta tarefa.
  Na conferência pontual final, os dois cenários de pedidos passaram e o caso de
  reativação de produto continuou falhando, inclusive com uma repetição automática.
  A suíte geral do frontend, portanto, não está integralmente aprovada.

## Retomada da validação — 18/11/2026

- A execução inicial completa do frontend passou: **277 testes em 19 arquivos**.
  As falhas anteriores de pedidos não se reproduziram nesta execução.
- Foi identificado e reproduzido um problema de interação na tela de produtos:
  o componente dos botões de ação era declarado dentro da página e recriado a
  cada renderização. Atualizações da busca podiam substituir o botão durante
  um clique, removendo seu foco e impedindo a reativação.
- O componente foi movido para o escopo do módulo para preservar os botões
  durante as atualizações. Um teste de regressão pressiona o botão, aguarda uma
  atualização da busca e só então solta o mouse, verificando a preservação do
  elemento, do foco e o envio de uma única requisição de reativação.
  O teste falhou antes da correção, confirmando a substituição do elemento.
- Após a correção, a suíte completa do frontend passou: **278 testes em 19
  arquivos**, incluindo a regressão de produtos e os fluxos de pedidos.
  A pendência de aprovação da suíte registrada em 17/11 está encerrada nesta
  execução. Permanecem os avisos já descritos do ambiente de testes.
- Backend: **814 testes aprovados**, com `TEST_DATABASE_URL=sqlite://` e
  `--basetemp=.pytest_cache/retomada-2026-11-18`.
- `mypy app/`: **59 arquivos sem problemas**. Ruff aprovado nos dez arquivos
  Python alterados/novos. A compilação de produção, que inclui a verificação
  TypeScript, passou e atualizou `app/web`.
- `git diff --check`: aprovado.

Evidências desta retomada em `artifacts/validacao/`: `backend-retomada-2026-11-18.txt`,
`frontend-retomada-2026-11-18.txt`, `produtos-regressao-antes-2026-11-18.txt`,
`frontend-final-2026-11-18.txt` e `build-retomada-2026-11-18.txt`.
Os limites anteriores de validação com PostgreSQL e navegador real continuam
aplicáveis; esta retomada executou testes automatizados e compilação local.
