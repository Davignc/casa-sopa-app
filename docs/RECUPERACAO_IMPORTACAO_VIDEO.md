# Recuperação de senha, importação e vídeo

## Ativar a recuperação pelo Gmail

O login agora oferece **Esqueci minha senha**. O sistema envia o link para o e-mail
da conta cadastrada; o remetente é a conta Gmail da organização configurada no servidor.
O destinatário pode usar Gmail ou outro provedor.

1. Na conta Google remetente, ative a verificação em duas etapas e crie uma senha de app,
   quando essa opção estiver disponível para a conta.
2. Preencha no `.env` do servidor, sem versionar os valores reais:

   ```dotenv
   FRONTEND_URL=https://endereco-publico-do-sistema.example
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=conta-da-organizacao@gmail.com
   SMTP_PASSWORD=senha-de-app-gerada-pelo-google
   RESET_PASSWORD_EXPIRE_MINUTES=30
   ```

3. Reinicie o backend. Em desenvolvimento, `FRONTEND_URL=http://localhost:8000`.
   A URL precisa ser acessível no dispositivo em que a pessoa abrirá o e-mail.
4. Faça um teste com uma conta ativa: solicite a recuperação, abra o e-mail, salve
   uma senha nova e confira o login. A senha anterior e os links anteriores à troca
   deixam de funcionar. O envio real depende dessas credenciais e não é validado
   pelos testes automatizados, que simulam o SMTP.

Não use a senha pessoal da conta Google em `SMTP_PASSWORD`. A porta 587 usa STARTTLS;
a porta 465, também suportada, usa TLS desde a conexão. Se a conta não oferecer
senha de app, o administrador da conta precisa avaliar a configuração permitida;
esta implementação não inclui OAuth do Google.

Sem remetente/senha configurados, a API informa indisponibilidade. Uma solicitação
aceita apresenta a mesma mensagem para contas existentes e inexistentes. Falhas do
provedor SMTP são registradas sem token ou senha nos logs; a confirmação de solicitação
não é confirmação de entrega. Confira os logs e a pasta de spam em caso de problema.

Os links expiram e são consumidos atomicamente ao trocar o hash no banco. A troca
invalida as sessões abertas. Há limites de solicitações por IP e e-mail e de tentativas
de redefinição por IP. Assim como o bloqueio de login existente, os limites ficam em
memória por processo; vários workers exigem um limitador compartilhado.

Referências oficiais:

- [Google: senhas de app](https://support.google.com/accounts/answer/185833?hl=pt-BR).
- [Google: configurações SMTP do Gmail](https://developers.google.com/workspace/gmail/imap/imap-smtp?hl=pt-BR).

## Importar clientes, produtos e vendas

Antes de usar, aplique a migração aditiva que registra referências das vendas antigas:

```powershell
.venv/Scripts/python -m alembic upgrade head
```

Entre como administradora e abra **Importar dados** no menu. Há três modelos Excel,
também disponíveis em `artifacts/importacao/`. Cada um contém uma aba de instruções.
As planilhas antigas devem ter suas colunas adaptadas ao modelo; não há reconhecimento
automático de layouts arbitrários, PDFs, fotos ou documentos em papel.

1. **Clientes:** nome e telefone com DDD. Endereço é opcional, mas deve estar completo
   quando preenchido. Clientes utilizados nas vendas precisam de endereço cadastrado,
   conforme o modelo de pedidos do sistema. Telefone identifica o cliente existente.
2. **Produtos:** nome, descrição, preço, estoque inicial e mínimo. O estoque inicial
   representa a quantidade disponível **hoje**, já considerando as vendas antigas.
   Nome existente é ignorado, inclusive se estiver inativo; não há atualização em massa.
3. **Vendas:** uma linha por produto, repetindo a referência e os dados comuns do pedido.
   Use `pedido_origem` único em todo o acervo, como `PLANILHA-2024-001`. A referência
   identifica permanentemente a venda, mesmo ao reenviar outro arquivo. O telefone
   identifica o cliente, o nome identifica o produto e o e-mail identifica a responsável.
   Deixe o e-mail vazio para atribuir à administradora que importa. Usuários inativos
   podem ser referenciados para preservar o histórico. Produtos com nomes ambíguos
   precisam ser corrigidos antes. O endereço escolhido é o principal atual do cliente
   (ou o primeiro cadastrado se não houver principal); confira-o antes de importar.

Vendas históricas aceitam `entregue` ou `cancelado`, preservam data e preço informados
e não movimentam o estoque. As entregues entram nos relatórios e no cálculo de
comissões com o percentual **atual**, conforme a regra já existente do sistema;
selecione o período histórico nos relatórios. Não se presume pagamento: só informe
`data_pagamento` quando conhecido. Pedidos antigos ainda em andamento devem ser
cadastrados no fluxo normal, que faz as movimentações de estoque.

Aceita `.xlsx` ou `.csv` (UTF-8/Windows-1252, separado por `;` ou `,`), até 5 MB e
2.000 linhas. Datas: `DD/MM/AAAA` ou `AAAA-MM-DD`; valores: `12,50` ou `12.50`.
Substitua fórmulas por valores e remova totais e cabeçalhos adicionais.

**Analisar planilha** não grava dados. A prévia mostra até cinco linhas, a contagem
de registros/pedidos novos e ignorados e os erros com o número da linha. Só é possível
confirmar um arquivo analisado sem erros. A autorização da prévia vale por 15 minutos
e está vinculada ao arquivo, ao tipo e à administradora. Na confirmação, os dados
são validados novamente; qualquer erro impede a gravação de todo o arquivo.

Clientes e produtos já existentes são preservados; vendas com referência já
importada são ignoradas. Ao corrigir uma venda importada, não altere apenas a referência
para forçar reimportação, pois isso criaria outra venda. Revise o acervo antes de confirmar.

O Excel exportado de Relatórios é um resumo de vendas, não um backup nem o mesmo
layout da importação. Para importá-lo, é necessário recompor as linhas por produto
e preencher os campos exigidos pelo modelo. A restauração completa continua sendo
feita pelo procedimento de backup descrito no README.

Rotas (somente administradora): `GET /importacoes/modelo?tipo=clientes|produtos|vendas`,
`POST /importacoes/analisar` e `POST /importacoes/confirmar` (multipart).

## Vídeo explicativo

Entrega em `artifacts/video/`:

- `casa-da-sopa-guia.mp4`: apresentação com telas reais, narração sintetizada em
  português brasileiro e legendas na imagem, além da faixa de legendas selecionável.
- `legendas.srt`: legendas separadas.
- `roteiro.md`: transcrição por capítulo.
- `capitulos.json`: tempos de início de cada capítulo.
- `capa.png` e `telas/`: material de apoio.

O vídeo usa somente registros fictícios em um banco SQLite separado. O roteiro
esclarece que a recuperação por e-mail depende da configuração do remetente Gmail.

Para regenerar no Windows, compile o frontend, tenha Chrome e a voz Microsoft Maria
Desktop (pt-BR) instalados e instale `imageio-ffmpeg` no ambiente de produção do vídeo
(não é dependência do servidor):

```powershell
npm.cmd --prefix frontend run build
uv pip install --python .venv/Scripts/python.exe imageio-ffmpeg==0.6.0
.venv/Scripts/python scripts/video/criar_video.py
```

O script captura o frontend servido pela API local e faz uma conferência de largura
da nova tela em celular. Ele não usa os cadastros reais, não envia e-mails nem publica
o vídeo. A pasta `producao-*` contém arquivos intermediários locais.
