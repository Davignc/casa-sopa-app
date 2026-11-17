"""Gera MP4 narrado, SRT e roteiro usando telas reais e banco fictício isolado.

Windows: .venv/Scripts/python scripts/video/criar_video.py
Requer imageio-ffmpeg (somente ferramenta de produção do vídeo), Chrome,
Pillow, websockets e a voz Microsoft Maria Desktop (pt-BR).
"""

import base64
import json
import math
import secrets
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from websockets.sync.client import connect

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "artifacts" / "video"
TRABALHO = SAIDA / ("producao-" + secrets.token_hex(4))
LARGURA, ALTURA, FPS = 1600, 900, 15
CENAS = json.loads(Path(__file__).with_name("cenas.json").read_text(encoding="utf8"))


class Navegador:
    def __init__(self, porta):
        self.processo = subprocess.Popen(
            [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--headless=new",
                f"--remote-debugging-port={porta}",
                f"--user-data-dir={TRABALHO / 'chrome'}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-gpu",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        limite = time.monotonic() + 30
        while True:
            try:
                dados = json.load(
                    urllib.request.urlopen(f"http://127.0.0.1:{porta}/json/version", timeout=1)
                )
                break
            except OSError:
                if time.monotonic() > limite:
                    raise RuntimeError("Chrome não iniciou.") from None
                time.sleep(0.2)
        self.ws = connect(dados["webSocketDebuggerUrl"], max_size=20_000_000, proxy=None)
        self.numero = 0
        self.sessao = None
        alvo = self.chamar("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.sessao = self.chamar("Target.attachToTarget", {"targetId": alvo, "flatten": True})[
            "sessionId"
        ]
        self.chamar("Page.enable")
        self.chamar(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False},
        )

    def chamar(self, metodo, params=None):
        self.numero += 1
        pacote = {"id": self.numero, "method": metodo, "params": params or {}}
        if self.sessao:
            pacote["sessionId"] = self.sessao
        self.ws.send(json.dumps(pacote))
        while True:
            resposta = json.loads(self.ws.recv(timeout=30))
            if resposta.get("id") == self.numero:
                if "error" in resposta:
                    raise RuntimeError(resposta["error"])
                return resposta.get("result", {})

    def js(self, codigo):
        resposta = self.chamar(
            "Runtime.evaluate", {"expression": codigo, "returnByValue": True, "awaitPromise": True}
        )
        if "exceptionDetails" in resposta:
            raise RuntimeError(resposta["exceptionDetails"])
        return resposta.get("result", {}).get("value")

    def esperar(self, texto):
        limite = time.monotonic() + 20
        while texto not in (self.js("document.body?.innerText") or ""):
            if time.monotonic() > limite:
                raise RuntimeError(f"Tela não carregou: {texto}")
            time.sleep(0.1)
        time.sleep(1.0)

    def foto(self, nome):
        self.js("document.activeElement?.blur()")
        dados = self.chamar("Page.captureScreenshot", {"format": "png"})["data"]
        (SAIDA / "telas" / f"{nome}.png").write_bytes(base64.b64decode(dados))

    def fechar(self):
        try:
            self.chamar("Browser.close")
        finally:
            self.ws.close()
            self.processo.wait(timeout=15)


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def capturar():
    porta, porta_chrome = porta_livre(), porta_livre()
    log = (TRABALHO / "servidor.log").open("w", encoding="utf8")
    servidor = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("demo.py")), str(TRABALHO), str(porta)],
        cwd=RAIZ,
        stdout=log,
        stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    browser = None
    try:
        origem = f"http://127.0.0.1:{porta}"
        for _ in range(100):
            try:
                urllib.request.urlopen(origem + "/health", timeout=1).close()
                break
            except OSError:
                if servidor.poll() is not None:
                    raise RuntimeError(
                        (TRABALHO / "servidor.log").read_text(encoding="utf8")
                    ) from None
                time.sleep(0.1)
        browser = Navegador(porta_chrome)
        browser.chamar("Page.navigate", {"url": origem})
        browser.esperar("Esqueci minha senha")
        browser.foto("entrada")
        browser.js(
            "[...document.querySelectorAll('button')]"
            ".find(b=>b.textContent==='Esqueci minha senha').click()"
        )
        browser.esperar("Recuperar senha")
        browser.foto("recuperar")
        browser.js("location.hash='/redefinir-senha?token=demonstracao'")
        browser.esperar("Redefinir senha")
        browser.foto("redefinir")
        requisicao = urllib.request.Request(
            origem + "/auth/login/json",
            data=json.dumps({"email": "admin@example.org", "senha": "Demonstracao123"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        token = json.load(urllib.request.urlopen(requisicao))["access_token"]
        browser.js(
            f"sessionStorage.setItem('casa-sopa-token', {json.dumps(token)}); "
            "location.hash='/'; location.reload()"
        )
        browser.esperar("Pedidos")
        time.sleep(1)
        browser.foto("inicio")
        for nome, rota, texto in [
            ("clientes", "clientes", "Cliente Exemplo"),
            ("novo_pedido", "pedidos/novo", "Novo pedido"),
            ("pedidos", "pedidos", "Em aberto"),
            ("produtos", "produtos", "Saco de lixo"),
            ("movimentacoes", "produtos/1/movimentacoes", "Estoque inicial"),
            ("relatorios", "relatorios", "Faturamento"),
            ("importar", "importacoes", "Traga suas planilhas antigas"),
        ]:
            browser.js(f"location.hash={json.dumps('/' + rota)}")
            browser.esperar(texto)
            browser.foto(nome)
        csv_demo = (
            "nome;telefone\nCliente da planilha A;16990000040\nCliente da planilha B;16990000041\n"
        )
        browser.js(
            """(() => {
          const campo = document.querySelector('input[type=file]');
          const dt = new DataTransfer();
          dt.items.add(new File([CSV_DEMO], 'clientes_antigos.csv', {type:'text/csv'}));
          campo.files = dt.files; campo.dispatchEvent(new Event('change', {bubbles:true}));
        })()""".replace("CSV_DEMO", json.dumps(csv_demo))
        )
        browser.js(
            "[...document.querySelectorAll('button')]"
            ".find(b=>b.textContent.includes('Analisar planilha')).click()"
        )
        browser.esperar("Confira antes de importar")
        browser.js("window.scrollTo(0,document.body.scrollHeight)")
        time.sleep(0.3)
        browser.foto("previa")
        for nome, texto in [
            ("usuarios", "Usuários"),
            ("configuracoes", "Logo da ONG"),
            ("fim", "Pedidos"),
        ]:
            browser.js(
                f"location.hash={json.dumps('/' if nome == 'fim' else '/' + nome)}; "
                "window.scrollTo(0,0)"
            )
            browser.esperar(texto)
            browser.foto(nome)
        # Verifica a adaptação das novas telas para celular.
        browser.chamar(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
        )
        browser.js("location.hash='/importacoes'")
        browser.esperar("Traga suas planilhas antigas")
        if browser.js("document.documentElement.scrollWidth > innerWidth"):
            raise RuntimeError("Rolagem horizontal inesperada no celular.")
        browser.foto("importar-celular")
        print(
            "Capturas reais concluídas; importação também conferida em tela de celular.", flush=True
        )
    finally:
        if browser:
            browser.fechar()
        servidor.terminate()
        servidor.wait(timeout=10)
        log.close()


def fonte(tamanho, negrito=False):
    return ImageFont.truetype(
        r"C:\Windows\Fonts\segoeuib.ttf" if negrito else r"C:\Windows\Fonts\segoeui.ttf", tamanho
    )


def linhas(texto, largura, f):
    resultado, linha = [], ""
    for palavra in texto.split():
        tentativa = (linha + " " + palavra).strip()
        if f.getlength(tentativa) > largura and linha:
            resultado.append(linha)
            linha = palavra
        else:
            linha = tentativa
    return resultado + [linha]


def timestamp(segundos):
    milis = round(segundos * 1000)
    return (
        f"{milis // 3600000:02}:{milis // 60000 % 60:02}:{milis // 1000 % 60:02},{milis % 1000:03}"
    )


def narrar(nome, narracao):
    pasta = SAIDA / "narracao"
    pasta.mkdir(exist_ok=True)
    wav = pasta / f"{nome}.wav"
    texto = pasta / f"{nome}.txt"
    if not wav.exists() or not texto.exists() or texto.read_text(encoding="utf8") != narracao:
        texto.write_text(narracao, encoding="utf8")
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(Path(__file__).with_name("narrar.ps1")),
                "-TextoPath",
                str(texto),
                "-SaidaPath",
                str(wav),
            ],
            check=True,
            capture_output=True,
        )
    with wave.open(str(wav)) as audio:
        duracao = audio.getnframes() / audio.getframerate()
    return wav, duracao


def produzir():
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    legendas, roteiro, total, capitulos = [], [], 0.0, []
    f_titulo, f_texto, f_pequena, f_legenda = fonte(48, True), fonte(26), fonte(20, True), fonte(29)
    for indice, (nome, titulo, subtitulo, pontos, narracao) in enumerate(CENAS):
        wav, duracao_audio = narrar(nome, narracao)
        quadros = math.ceil((duracao_audio + 0.8) * FPS)
        duracao = quadros / FPS
        palavras = narracao.split()
        blocos = textwrap.wrap(narracao, 104, break_long_words=False)
        intervalos, inicio = [], 0.0
        for bloco in blocos:
            fim = inicio + duracao_audio * len(bloco.split()) / len(palavras)
            intervalos.append((inicio, fim, bloco))
            legendas.append(
                f"{len(legendas) + 1}\n{timestamp(total + inicio)} --> {timestamp(total + fim)}\n"
                + "\n".join(linhas(bloco, 1400, f_legenda))
                + "\n"
            )
            inicio = fim
        capitulos.append({"inicio": round(total, 3), "titulo": titulo})
        roteiro.append(f"## {timestamp(total)[:-4]} — {titulo}\n\n{narracao}\n")
        foto = (
            Image.open(SAIDA / "telas" / f"{nome}.png")
            .convert("RGB")
            .resize((1104, 690), Image.Resampling.LANCZOS)
        )
        base = Image.new("RGB", (LARGURA, ALTURA), "#160f25")
        d = ImageDraw.Draw(base)
        d.rounded_rectangle((28, 30, 420, 754), radius=28, fill="#231534")
        d.text((54, 57), "CASA DA SOPA", font=f_pequena, fill="#e9d5ff")
        d.text((54, 90), "GUIA DO SISTEMA", font=fonte(15), fill="#a898b9")
        d.rounded_rectangle((54, 148, 142, 185), radius=12, fill="#a855f7")
        d.text((69, 151), f"{indice + 1:02} / {len(CENAS):02}", font=fonte(18, True), fill="white")
        y = 213
        for linha in linhas(titulo, 325, f_titulo):
            d.text((54, y), linha, font=f_titulo, fill="white")
            y += 57
        y += 25
        for linha in linhas(subtitulo, 320, fonte(22)):
            d.text((54, y), linha, font=fonte(22), fill="#c4b5fd")
            y += 30
        y += 30
        posicoes = []
        for ponto in pontos:
            inicio_ponto = y
            d.ellipse((54, y + 10, 64, y + 20), fill="#d8b4fe")
            for linha in linhas(ponto, 280, f_texto):
                d.text((80, y), linha, font=f_texto, fill="#e2d9ed")
                y += 34
            y += 16
            posicoes.append((inicio_ponto, y - 12, ponto))
        d.rounded_rectangle((445, 31, 1567, 753), radius=18, fill="#e2d9ed")
        d.text(
            (464, 37),
            "●  ●  ●     Demonstração com dados fictícios",
            font=fonte(15),
            fill="#4b3b60",
        )
        base.paste(foto, (454, 64))
        if indice == 0:
            base.save(SAIDA / "capa.png")
        saida = TRABALHO / f"cena-{indice:02}.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{LARGURA}x{ALTURA}",
            "-r",
            str(FPS),
            "-i",
            "pipe:0",
            "-i",
            str(wav),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "24",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "44100",
            "-af",
            "apad",
            "-t",
            str(duracao),
            "-movflags",
            "+faststart",
            str(saida),
        ]
        log = (TRABALHO / "render.log").open("ab")
        processo = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            for quadro in range(quadros):
                t = quadro / FPS
                frame = base.copy()
                draw = ImageDraw.Draw(frame)
                # Destaca cada etapa em sequência ao longo da fala.
                ativo = min(len(posicoes) - 1, int(t / duracao * len(posicoes)))
                inicio_ponto, fim_ponto, ponto = posicoes[ativo]
                draw.rounded_rectangle(
                    (44, inicio_ponto - 6, 407, fim_ponto + 6), radius=12, fill="#50316e"
                )
                draw.ellipse((54, inicio_ponto + 10, 64, inicio_ponto + 20), fill="#86efac")
                for j, linha in enumerate(linhas(ponto, 280, f_texto)):
                    draw.text((80, inicio_ponto + j * 34), linha, font=f_texto, fill="white")
                # Progressão e pulso suaves mantêm a apresentação em movimento.
                draw.rounded_rectangle((454, 750, 1558, 755), radius=2, fill="#4b2d66")
                draw.rounded_rectangle(
                    (454, 750, 454 + max(1, int(1104 * t / duracao)), 755), radius=2, fill="#c084fc"
                )
                raio = 7 + int(3 * math.sin(t * 2))
                draw.ellipse((1534 - raio, 39 - raio, 1534 + raio, 39 + raio), fill="#a855f7")
                bloco = next((s for a, b, s in intervalos if a <= t < b), "")
                draw.rounded_rectangle((28, 779, 1567, 883), radius=18, fill="#08050e")
                for j, linha in enumerate(linhas(bloco, 1450, f_legenda)):
                    largura = f_legenda.getlength(linha)
                    draw.text(
                        ((LARGURA - largura) / 2, 793 + j * 36), linha, font=f_legenda, fill="white"
                    )
                processo.stdin.write(frame.tobytes())
            processo.stdin.close()
            if processo.wait() != 0:
                raise RuntimeError("Falha ao codificar vídeo. Confira render.log.")
        finally:
            log.close()
        total += duracao
        print(f"Cena {indice + 1}/{len(CENAS)} pronta: {titulo}", flush=True)
    lista = TRABALHO / "cenas.txt"
    lista.write_text(
        "".join(f"file 'cena-{i:02}.mp4'\n" for i in range(len(CENAS))), encoding="utf8"
    )
    (SAIDA / "legendas.srt").write_text("\n".join(legendas), encoding="utf8")
    (SAIDA / "roteiro.md").write_text(
        "# Casa da Sopa — roteiro do vídeo\n\nNarração sintetizada em português brasileiro. "
        "Todas as telas usam dados fictícios.\n\n" + "\n".join(roteiro),
        encoding="utf8",
    )
    destino = SAIDA / "casa-da-sopa-guia.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lista),
            "-i",
            str(SAIDA / "legendas.srt"),
            "-map",
            "0:v",
            "-map",
            "0:a",
            "-map",
            "1:0",
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=por",
            "-movflags",
            "+faststart",
            str(destino),
        ],
        check=True,
    )
    (SAIDA / "capitulos.json").write_text(
        json.dumps(
            {"duracao_segundos": round(total, 2), "capitulos": capitulos},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    # Decodificação completa confere áudio, vídeo e concatenação.
    subprocess.run([ffmpeg, "-v", "error", "-i", str(destino), "-f", "null", "-"], check=True)
    print(
        f"MP4 validado: {destino} | {total:.1f}s | {destino.stat().st_size / 1024 / 1024:.1f} MB",
        flush=True,
    )


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "telas").mkdir(exist_ok=True)
    TRABALHO.mkdir()
    if "--somente-audio" in sys.argv:
        for nome, _, _, _, narracao in CENAS:
            wav, duracao = narrar(nome, narracao)
            print(f"Narração pronta: {nome} ({duracao:.1f}s)", flush=True)
        sys.exit(0)
    if "--usar-capturas" not in sys.argv:
        capturar()
    if "--somente-capturas" not in sys.argv:
        produzir()
