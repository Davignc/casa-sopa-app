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

## Adendo — recuperação de senha, importação e vídeo (17/11/2026)

Implementadas a recuperação de senha por e-mail via Gmail e a importação de clientes,
produtos e vendas antigas, com modelos Excel, análise e confirmação pela administradora.
Criado vídeo de 5min31s com telas reais, dados fictícios, narração em português e legendas.

Nesta entrega, o PostgreSQL local respondeu e a migração aditiva `0002` foi aplicada;
a pendência de conectividade descrita na validação anterior não se repetiu. A suíte
atual passou com **812 testes do backend em PostgreSQL e 276 do frontend**. O envio
real pelo Gmail depende das credenciais e da URL pública no `.env`; não foi realizado.

Detalhes e evidências em [entrega de 17/11/2026](artifacts/validacao/entrega-17-11-2026.md).
Configuração em [recuperação, importação e vídeo](docs/RECUPERACAO_IMPORTACAO_VIDEO.md).
Vídeo em [casa-da-sopa-guia.mp4](artifacts/video/casa-da-sopa-guia.mp4).
