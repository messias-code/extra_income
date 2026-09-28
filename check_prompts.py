#!/usr/bin/env python3
"""Utilitario do pipeline Extra Income.

Dois comandos:
    python check_prompts.py status   -> o que ja existe / o que falta em cada produto
    python check_prompts.py check    -> valida os prompts contra as regras dos YAMLs

O pipeline nao gera imagem nenhuma: ele gera PROMPT. Cada produto termina com tres
arquivos de texto, um por comando do Antigravity:

    prompt_cena.md        (/start_gen_prompts)  um clipe de 10s escrito em 6 beats
    prompt_storyboard.md  (/start_gen_image)    o prompt da prancha de 6 paineis
    prompt_capa.md        (/start_gen_buy)      o prompt da capa do produto

Os tres precisam falar do mesmo produto: o storyboard traduz os 6 beats da cena em 6
paineis, e a capa copia Subject e Label & Brand da cena palavra por palavra.

Por padrao olha TODAS as datas em produtos/: dia nenhum pode ficar sem prompt, entao dia
antigo com arquivo faltando aparece como pendencia ate ser gerado de novo. Use --ultima
para olhar so a data mais recente.
Sai com codigo 1 se algum prompt tiver erro (da para usar em loop de correcao).
"""

import argparse
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ_PRODUTOS = os.path.join(BASE_DIR, "produtos")
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

ARQUIVO_CENA = "prompt_cena.md"
ARQUIVO_STORYBOARD = "prompt_storyboard.md"
ARQUIVO_CAPA = "prompt_capa.md"

SECOES_OBRIGATORIAS = [
    "Style & Lighting:",
    "Textures to Highlight:",
    "Scene:",
    "Subject:",
    "Product Lock:",
    "Label & Brand:",
    "Camera & Framing:",
    "Continuity Anchors:",
    "Storyboard Adherence:",
    "Action Timeline:",
    "Audio:",
    "Negative Prompt:",
]

MODOS_DE_CAMERA = ["product only", "hands only", "headless model"]

# a grade fixa dos 10s. Cada beat vira UM painel do storyboard: beat faltando e painel
# sem mapa, beat sobrando e painel inventado.
BEATS = ["0-1.5s", "1.5-3s", "3-5s", "5-7s", "7-8.5s", "8.5-10s"]

# sobras do pipeline antigo de dois clipes costurados: hoje e uma cena so
RESQUICIOS_DE_DOIS_CLIPES = [
    "Clip 1 of 2", "Clip 2 of 2", "END FRAME", "START FRAME",
    "CONTINUES FROM THE FINAL FRAME", "STRICT CONTINUATION", "10s-20s",
]

# tokens que a BASE do negative prompt precisa conter.
# "text", "typography" e "logos" soltos sairam de proposito: apagavam o rotulo do
# proprio produto e faziam o modelo inventar letras (o caso "Vedatudo" -> "Vecatudo")
NEGATIVE_OBRIGATORIO = [
    "captions", "watermarks", "misspelled label", "altered brand name",
    "faces", "morphing product", "horizontal framing",
    "music", "sound effects", "voiceover",
    # travas contra os dois defeitos que estragaram os primeiros videos:
    # o modelo redesenhar o produto e devolver produto parado com a camera girando
    "simplified packaging", "redesigned label artwork",
    "static product with only camera movement",
    "colour shifting product", "label text changing between frames",
]

# frases que mandam o modelo borrar o rotulo: sao elas que produzem letra embaralhada
PROIBIDO_NO_ROTULO = ("non-legible", "not legible", "illegible", "soft-focus label",
                      "label kept soft", "blurred label", "blurred out label",
                      "unreadable label", "no legible text on the label")

PALAVRAS_MIN, PALAVRAS_MAX = 480, 700  # corpo da cena, sem o Negative Prompt

# --- prompt do storyboard --------------------------------------------------- #
PALAVRAS_STORY_MIN, PALAVRAS_STORY_MAX = 200, 360
STORY_OBRIGATORIO = [
    "6-panel storyboard sheet",
    "2 columns by 3 rows",
    "left to right and top to bottom",
    "numeral",
    "no other text anywhere",
    "product centered in each panel",
    "match the reference photos",
    "9:16",
]
# apagariam o proprio rotulo do produto ou a numeracao dos paineis
NEGATIVO_PROIBIDO_STORY = {"numbers", "numerals", "letters", "words", "labels",
                           "logos", "text", "typography"}

# --- prompt da capa (peca de divulgacao, com texto em pt-BR) ---------------- #
SECOES_CAPA = [
    "Art Direction:",
    "Subject:",
    "Label & Brand:",
    "Layout & Composition:",
    "Promo Copy",
    "Text Style:",
    "Scene:",
    "Light & Mood:",
    "Textures to Highlight:",
    "Model & Hands:",
    "Product Fidelity:",
    "Originality:",
    "Negative Prompt:",
]
# aqui o texto e PEDIDO: o negative ataca texto errado, texto demais e texto em cima do
# produto, nunca "captions"/"letters" soltos, que apagariam a chamada e o rotulo
NEGATIVE_CAPA_OBRIGATORIO = [
    "price tags", "currency symbols", "percentages", "discount badges",
    "misspelled portuguese words", "gibberish lettering", "extra words",
    "text on top of the product", "misspelled label", "faces", "collage",
    "duplicated product", "catalogue white background", "flyer layout",
    "ready-made template look", "round seals", "big buttons", "generic ai look",
    "pasted-on product",
]
NEGATIVO_PROIBIDO_CAPA = {"captions", "overlay text", "letters", "words", "typography",
                          "text", "labels"}
# arte de marca real: titulo + beneficio + CTA discreto, nunca chamada de panfleto
LIMITES_LINHAS_CAPA = [("titulo", 4), ("frase de beneficio", 6), ("CTA", 3)]
PALAVRAS_TEXTO_CAPA_MAX = 13
CHAMADAS_APELATIVAS = ["compre já", "compre ja", "compre agora", "imperdível", "imperdivel",
                       "aproveite", "garanta o seu", "garanta a sua", "premium", "exclusivo",
                       "exclusiva", "feito para durar", "última chance", "ultima chance", "!"]
PALAVRAS_CAPA_MIN, PALAVRAS_CAPA_MAX = 400, 650


# --------------------------------------------------------------------------- #
# descoberta de pastas
# --------------------------------------------------------------------------- #
def pastas_de_data():
    """Datas em produtos/, da mais antiga para a mais recente. O nome e AAAA-MM-DD
    justamente para a ordem alfabetica ja ser a ordem cronologica."""
    if not os.path.isdir(RAIZ_PRODUTOS):
        return []
    return sorted(d for d in os.listdir(RAIZ_PRODUTOS) if DATA_RE.match(d))


def listar_produtos(so_a_ultima=False):
    """Devolve (data, nome_do_produto, caminho_absoluto)."""
    produtos = []
    datas = pastas_de_data()
    for data in (datas[-1:] if so_a_ultima else datas):
        raiz = os.path.join(RAIZ_PRODUTOS, data)
        for nome in sorted(os.listdir(raiz)):
            caminho = os.path.join(raiz, nome)
            if os.path.isdir(caminho):
                produtos.append((data, nome, caminho))
    return produtos


def caminho_do_prompt(caminho_produto, arquivo):
    return os.path.join(caminho_produto, "prompt_video", arquivo)


def ler(caminho_produto, arquivo):
    """Conteudo do prompt, ou None se o comando que o escreve ainda nao rodou."""
    caminho = caminho_do_prompt(caminho_produto, arquivo)
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as fh:
        return fh.read()


def contar_imagens(caminho):
    return len([f for f in os.listdir(caminho)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])


# --------------------------------------------------------------------------- #
# comando: status
# --------------------------------------------------------------------------- #
def cmd_status(args):
    produtos = listar_produtos(args.ultima)
    if not produtos:
        print("Nenhum produto encontrado. Rode o scraper.py primeiro.")
        return 0

    print(f"{'DATA':<11}{'PRODUTO':<50} {'IMGS':>4} {'META':>5} {'CENA':>6} {'STORY':>6} {'CAPA':>5}")
    print("-" * 93)
    sem_cena, sem_story, sem_capa = [], [], []
    pendentes_por_data = {}
    for data, nome, caminho in produtos:
        imgs = contar_imagens(caminho)
        meta = "sim" if os.path.exists(os.path.join(caminho, "metadata.json")) else "-"
        tem = {a: os.path.exists(caminho_do_prompt(caminho, a))
               for a in (ARQUIVO_CENA, ARQUIVO_STORYBOARD, ARQUIVO_CAPA)}
        if not tem[ARQUIVO_CENA]:
            sem_cena.append(nome)
        else:
            # storyboard e capa leem a cena: so falta de verdade quem ja podia ter sido feito
            if not tem[ARQUIVO_STORYBOARD]:
                sem_story.append(nome)
            if not tem[ARQUIVO_CAPA]:
                sem_capa.append(nome)
        if not all(tem.values()):
            pendentes_por_data[data] = pendentes_por_data.get(data, 0) + 1
        print(f"{data:<11}{nome[:50]:<50} {imgs:>4} {meta:>5} "
              f"{'sim' if tem[ARQUIVO_CENA] else 'FALTA':>6} "
              f"{'sim' if tem[ARQUIVO_STORYBOARD] else 'FALTA':>6} "
              f"{'sim' if tem[ARQUIVO_CAPA] else 'FALTA':>5}")

    print("-" * 93)
    print(f"{len(produtos)} produtos | {len(sem_cena)} sem {ARQUIVO_CENA} | "
          f"{len(sem_story)} sem {ARQUIVO_STORYBOARD} | {len(sem_capa)} sem {ARQUIVO_CAPA}")
    if sem_cena:
        print("  -> rode /start_gen_prompts")
    if sem_story:
        print("  -> rode /start_gen_image")
    if sem_capa:
        print("  -> rode /start_gen_buy")
    # dia nenhum pode ficar sem prompt: dia antigo incompleto volta para a fila
    if pendentes_por_data:
        print("dias com pendencia (gerar de novo, nao so o dia de hoje):")
        for data in sorted(pendentes_por_data):
            print(f"  {data}: {pendentes_por_data[data]} produto(s) incompleto(s)")
    else:
        print("todos os dias completos")
    return 0


# --------------------------------------------------------------------------- #
# comando: check
# --------------------------------------------------------------------------- #
def extrair_secao(texto, titulo):
    """Conteudo de uma secao ate a proxima secao/linha em branco dupla."""
    if titulo not in texto:
        return ""
    resto = texto.split(titulo, 1)[1]
    return resto.split("\n\n", 1)[0]


def beats_da_acao(acao):
    """Devolve (rotulo, texto) de cada beat da linha ACTION."""
    partes = []
    for trecho in acao.split(" / "):
        trecho = trecho.strip()
        for beat in BEATS:
            if trecho.startswith(beat):
                partes.append((beat, trecho[len(beat):].strip()))
                break
    return partes


def normalizar(texto):
    return " ".join(texto.split()).strip(" -.")


def sujeira_de_geracao(texto):
    """Lixo que o LLM deixa cair no arquivo e quebra o copiar-e-colar."""
    erros = []
    if "```" in texto:
        erros.append("o arquivo contem cerca de codigo (```)")
    if re.search(r"<[a-zA-Z][^>]{2,}>", texto):
        erros.append("sobrou placeholder '<...>' do gabarito")
    if "<IMAGE_" in texto.upper():
        erros.append("referencia '<IMAGE_n>' proibida (o prompt precisa ser autossuficiente)")
    return erros


def validar_cena(texto):
    """Devolve (erros, avisos) do prompt_cena.md: o unico clipe, de 10s em 6 beats."""
    erros, avisos = [], []
    linhas = [l.strip() for l in texto.strip().splitlines()]
    if not linhas:
        return ["arquivo vazio"], []

    # 1. linha Format
    f = linhas[0]
    if not f.startswith("Format:"):
        erros.append("primeira linha nao e a linha 'Format:'")
    else:
        for exigido in ["9:16", "720p", "24fps", "10s", "Single clip"]:
            if exigido not in f:
                erros.append(f"linha Format sem '{exigido}'")

    # 2. linha On camera
    on_camera = next((l for l in linhas[:4] if l.startswith("On camera:")), None)
    if not on_camera:
        erros.append("falta a linha 'On camera:'")
    elif not any(m in on_camera.lower() for m in MODOS_DE_CAMERA):
        erros.append("linha 'On camera:' sem um dos modos: product only / hands only / headless model")

    # 3. secoes
    for secao in SECOES_OBRIGATORIAS:
        if secao not in texto:
            erros.append(f"falta a secao '{secao}'")

    # 4. cabecalho do clipe unico
    cabecalho = next((l for l in linhas if l.startswith("[Clip")), None)
    if not cabecalho:
        erros.append("falta o cabecalho '[Clip - ... | 0s-10s | Shot: ...]'")
    else:
        if "0s-10s" not in cabecalho:
            erros.append("cabecalho sem a marcacao de tempo '0s-10s'")
        if "Shot:" not in cabecalho:
            erros.append("cabecalho sem 'Shot:'")

    # 5. e uma cena so: nada de costura com um segundo clipe
    for resquicio in RESQUICIOS_DE_DOIS_CLIPES:
        if resquicio in texto:
            erros.append(f"sobra do pipeline de dois clipes: '{resquicio}' (hoje e uma cena so)")

    for marcador in ("VISUAL:", "ACTION:"):
        if marcador not in texto:
            erros.append(f"falta a linha '{marcador}'")

    # 6. os 6 beats viram os 6 paineis do storyboard: sem eles o /start_gen_image nao tem mapa
    acao = extrair_secao(texto, "ACTION:")
    for beat in BEATS:
        if beat not in acao:
            erros.append(f"falta o beat '{beat}' na linha ACTION")
    if acao and len([p for p in acao.split("/") if p.strip()]) != len(BEATS):
        avisos.append("a linha ACTION nao tem exatamente 6 trechos separados por ' / '")

    # cada beat e um EVENTO com enquadramento, nao um movimento de camera (R13).
    # e daqui que vinha o video de produto parado com a camera girando em volta
    for rotulo, corpo_do_beat in beats_da_acao(acao):
        if not corpo_do_beat:
            erros.append(f"beat '{rotulo}' vazio")
            continue
        if not re.search(r"\([^)]+\)\s*\.?$", corpo_do_beat):
            erros.append(f"beat '{rotulo}' sem o enquadramento entre parenteses no fim")
        if re.match(r"(?:the )?camera\b", corpo_do_beat, re.I):
            erros.append(f"beat '{rotulo}' comeca pela camera: o beat descreve um evento "
                         "fisico, nao o movimento da lente")

    # 7. texto de overlay proibido, rotulo do produto obrigatorio e exato
    trava = extrair_secao(texto, "Product Lock:")
    token = re.search(r"the product is the same (.+?):", trava)
    if not token:
        erros.append("Product Lock sem o token do produto "
                     "('the product is the same <cor + forma + tipo + marca>:')")
    else:
        token = token.group(1).strip().lower()
        beats = beats_da_acao(acao)
        com_token = [r for r, corpo in beats if token in corpo.lower()]
        if len(com_token) < 4:
            erros.append(f"o token '{token}' aparece em so {len(com_token)} dos 6 beats: "
                         "sem repetir a identidade, o modelo troca cor e rotulo no meio do "
                         "clipe (R14)")
        if beats and BEATS[-1] not in com_token:
            erros.append(f"o beauty shot ({BEATS[-1]}) nao nomeia o token '{token}'")
        if token not in extrair_secao(texto, "VISUAL:").lower():
            avisos.append(f"a linha VISUAL nao repete o token '{token}'")

    adesao = extrair_secao(texto, "Storyboard Adherence:").lower()
    if adesao and "stage them exactly as written" not in adesao:
        avisos.append("Storyboard Adherence sem a ordem de encenar os beats como escritos")
    ancoras = extrair_secao(texto, "Continuity Anchors:").lower()
    if ancoras and "never restyled" not in ancoras and "restyled" not in ancoras:
        avisos.append("Continuity Anchors sem a trava contra o produto ser redesenhado")

    estilo = extrair_secao(texto, "Style & Lighting:").lower()
    if "no captions" not in estilo:
        erros.append("Style & Lighting sem 'no captions, no subtitles'")

    rotulo = extrair_secao(texto, "Label & Brand:")
    sem_marca = "no visible branding" in rotulo.lower()
    if not sem_marca and not re.search(r"\b(?:[A-Za-z]-){2,}[A-Za-z]\b", rotulo):
        erros.append("Label & Brand sem a marca soletrada com hifens (ex: V-E-D-A-T-U-D-O): "
                     "sem soletrar, o modelo troca as letras")
    if not sem_marca and "exactly" not in rotulo.lower():
        avisos.append("Label & Brand sem 'reads exactly': a exigencia precisa ser literal")

    # 8. o clipe e mudo
    audio = extrair_secao(texto, "Audio:").lower()
    if "no audio" not in audio:
        erros.append("bloco Audio sem 'No audio. Silent clip'")
    for som in ("no music", "no sound effects", "no voiceover"):
        if som not in audio:
            erros.append(f"bloco Audio sem '{som}'")
    if "SFX:" in texto:
        erros.append("sobrou linha 'SFX:': o clipe e mudo, nada de som descrito")

    # 9. negative prompt
    negativo = extrair_secao(texto, "Negative Prompt:").lower()
    faltantes = [x for x in NEGATIVE_OBRIGATORIO if x not in negativo]
    if faltantes:
        erros.append("Negative Prompt incompleto, falta: " + ", ".join(faltantes))
    if "hands only" in texto.lower() and "deformed hands" not in negativo:
        avisos.append("modo 'hands only' sem os condicionais de mao no Negative Prompt")
    if "headless model" in texto.lower() and "head" not in negativo:
        avisos.append("modo 'headless model' sem os condicionais de rosto no Negative Prompt")

    # 10. nada de voz nem texto vazando para dentro do roteiro
    corpo = texto.split("Negative Prompt:")[0].lower()
    for proibido in ("narrator", "voice-over:", "voiceover:", "dialogue:",
                     "on-screen text", "caption reads", "title card",
                     "instrumental", "soundtrack", "background music"):
        if proibido in corpo:
            erros.append(f"o roteiro pede voz, musica ou texto na tela: '{proibido}'")
    for frase in PROIBIDO_NO_ROTULO:
        if frase in corpo:
            erros.append(f"o roteiro manda borrar o rotulo ('{frase}'): e exatamente isso "
                         "que faz o modelo embaralhar as letras da marca")

    erros += sujeira_de_geracao(texto)

    # 11. tamanho (so o corpo criativo; o Negative Prompt e lista, nao prosa)
    palavras = len(texto.split("Negative Prompt:")[0].split())
    if palavras < PALAVRAS_MIN:
        avisos.append(f"curto demais: {palavras} palavras (alvo {PALAVRAS_MIN}-{PALAVRAS_MAX})")
    elif palavras > PALAVRAS_MAX:
        avisos.append(f"longo demais: {palavras} palavras (alvo {PALAVRAS_MIN}-{PALAVRAS_MAX})")

    return erros, avisos


def validar_storyboard(texto):
    """Devolve (erros, avisos) do prompt_storyboard.md: o prompt da prancha de 6 paineis."""
    erros, avisos = [], []
    if not texto.strip():
        return ["arquivo vazio"], []

    baixo = texto.lower()
    for exigido in STORY_OBRIGATORIO:
        if exigido.lower() not in baixo:
            erros.append(f"o prompt nao pede '{exigido}'")

    # um painel por beat, na ordem e com o rotulo de tempo certo
    for numero, beat in enumerate(BEATS, start=1):
        marcador = f"PANEL {numero}"
        if marcador not in texto:
            erros.append(f"falta o {marcador}")
        elif beat not in texto.split(marcador, 1)[1].split("\n", 1)[0]:
            erros.append(f"{marcador} sem o beat '{beat}' do prompt_cena.md")
    if "PANEL 7" in texto:
        erros.append("tem PANEL 7: a prancha e de 6 paineis, um por beat")

    # o negative nao pode apagar a numeracao dos paineis nem o rotulo do produto
    if "negative:" not in baixo and "negative prompt:" not in baixo:
        erros.append("falta o bloco 'Negative:'")
    else:
        marca = "Negative:" if "Negative:" in texto else "Negative Prompt:"
        negativo = texto.split(marca, 1)[1]
        itens = {normalizar(i).lower().rstrip(".") for i in negativo.split(",")}
        proibidos = sorted(itens & NEGATIVO_PROIBIDO_STORY)
        if proibidos:
            erros.append("Negative com termo que apaga a numeracao ou o rotulo do produto: "
                         + ", ".join(proibidos))
        if "faces" not in negativo.lower():
            avisos.append("Negative sem 'faces'")

    if any(m in baixo for m in ("sketch:", "cartoon style", "illustration style")):
        erros.append("o prompt pede desenho: a prancha e fotografica")

    for frase in PROIBIDO_NO_ROTULO:
        if frase in baixo.split("negative")[0]:
            erros.append(f"o prompt manda borrar o rotulo ('{frase}')")

    erros += sujeira_de_geracao(texto)

    palavras = len(texto.split())
    if palavras < PALAVRAS_STORY_MIN:
        avisos.append(f"curto demais: {palavras} palavras "
                      f"(alvo {PALAVRAS_STORY_MIN}-{PALAVRAS_STORY_MAX})")
    elif palavras > PALAVRAS_STORY_MAX:
        avisos.append(f"longo demais: {palavras} palavras "
                      f"(alvo {PALAVRAS_STORY_MIN}-{PALAVRAS_STORY_MAX})")

    return erros, avisos


def validar_texto_da_peca(texto):
    """As 3 linhas em portugues: titulo, beneficio e CTA discreto, escritos exatos e
    sem preco nem chamada apelativa."""
    erros = []
    copy = texto.split("Promo Copy", 1)[1].split("Text Style:", 1)[0] if "Promo Copy" in texto else ""
    linhas = re.findall(r'"([^"]+)"', copy)
    if not linhas:
        erros.append("bloco Promo Copy sem nenhuma linha entre aspas")
        return erros
    if len(linhas) != 3:
        erros.append(f"{len(linhas)} linhas de texto na peca: precisa ser exatamente 3 "
                     "(titulo, frase de beneficio, CTA)")
    palavras = sum(len(l.split()) for l in linhas)
    if palavras > PALAVRAS_TEXTO_CAPA_MAX:
        erros.append(f"{palavras} palavras na arte: o limite e {PALAVRAS_TEXTO_CAPA_MAX} "
                     "(gerador erra texto longo)")
    for linha, (nome, limite) in zip(linhas, LIMITES_LINHAS_CAPA):
        if len(linha.split()) > limite:
            erros.append(f"{nome} '{linha}' passa de {limite} palavras")
    for l in linhas:
        for termo in CHAMADAS_APELATIVAS:
            if termo in l.lower():
                erros.append(f"chamada apelativa no texto da peca ('{termo}' em '{l}')")

    # preco nunca: nem no texto da arte, nem pedido em outro lugar do prompt
    corpo = texto.split("Negative Prompt:")[0]
    for marca in ("R$", "%", "R $"):
        if marca in corpo:
            erros.append(f"o prompt pede '{marca}' na imagem: a peca nao mostra preco")
    for l in linhas:
        if re.search(r"\d", l):
            erros.append(f"numero no texto da peca ('{l}'): proibido")
    for termo in ("desconto", "off", "promoção", "promocao", "preço", "preco"):
        if termo in " ".join(linhas).lower():
            erros.append(f"o texto da peca fala de preco/desconto ('{termo}')")
    if "spelled" not in copy:
        erros.append("o titulo nao esta soletrado com hifens: sem isso o modelo escreve errado")
    return erros


def validar_capa(texto):
    """Devolve (erros, avisos) do prompt_capa.md: a foto que abre o post."""
    erros, avisos = [], []
    linhas = [l.strip() for l in texto.strip().splitlines()]
    if not linhas:
        return ["arquivo vazio"], []

    f = linhas[0]
    if not f.startswith("Format:"):
        erros.append("primeira linha nao e a linha 'Format:'")
    else:
        for exigido in ["single still photograph", "4:5", "promotional cover shot"]:
            if exigido not in f:
                erros.append(f"linha Format sem '{exigido}'")

    on_camera = next((l for l in linhas[:4] if l.startswith("On camera:")), None)
    if not on_camera:
        erros.append("falta a linha 'On camera:'")
    else:
        if not any(m in on_camera.lower() for m in MODOS_DE_CAMERA):
            erros.append("linha 'On camera:' sem um dos modos de camera")
        if "no price" not in on_camera.lower():
            erros.append("linha 'On camera:' sem 'No price, no numbers, no percentages'")

    for secao in SECOES_CAPA:
        if secao not in texto:
            erros.append(f"falta a secao '{secao}'")

    erros += validar_texto_da_peca(texto)

    negativo = extrair_secao(texto, "Negative Prompt:").lower()
    faltantes = [x for x in NEGATIVE_CAPA_OBRIGATORIO if x not in negativo]
    if faltantes:
        erros.append("Negative Prompt incompleto, falta: " + ", ".join(faltantes))
    itens = {normalizar(i).lower().rstrip(".") for i in negativo.split(",")}
    proibidos = sorted(itens & NEGATIVO_PROIBIDO_CAPA)
    if proibidos:
        erros.append("Negative com termo que apaga a chamada em portugues ou o rotulo: "
                     + ", ".join(proibidos))

    corpo = texto.split("Negative Prompt:")[0]
    rotulo = extrair_secao(texto, "Label & Brand:")
    sem_marca = "no visible branding" in rotulo.lower()
    if not sem_marca and not re.search(r"\b(?:[A-Za-z]-){2,}[A-Za-z]\b", rotulo):
        erros.append("Label & Brand sem a marca soletrada com hifens")
    for frase in PROIBIDO_NO_ROTULO:
        if frase in corpo.lower():
            erros.append(f"a capa manda borrar o rotulo ('{frase}')")

    # so a parte criativa: os blocos Product Fidelity e Originality citam o fundo branco
    # justamente para PROIBI-lo, e nao podem disparar o alarme
    criativo = corpo.split("Product Fidelity:")[0].lower()
    for fundo in ("white background", "plain background", "studio backdrop",
                  "seamless backdrop", "grey background", "gray background"):
        if fundo in criativo:
            erros.append(f"a capa pede '{fundo}': o cenario tem que ser real e diferente do anuncio")

    erros += sujeira_de_geracao(texto)

    palavras = len(corpo.split())
    if palavras < PALAVRAS_CAPA_MIN:
        avisos.append(f"curto demais: {palavras} palavras "
                      f"(alvo {PALAVRAS_CAPA_MIN}-{PALAVRAS_CAPA_MAX})")
    elif palavras > PALAVRAS_CAPA_MAX:
        avisos.append(f"longo demais: {palavras} palavras "
                      f"(alvo {PALAVRAS_CAPA_MIN}-{PALAVRAS_CAPA_MAX})")

    return erros, avisos


def validar_conjunto(cena, storyboard, capa):
    """O que so da para conferir com os arquivos lado a lado: a costura entre eles."""
    erros, avisos = [], []
    modo_cena = next((m for m in MODOS_DE_CAMERA
                      if m in extrair_secao(cena, "On camera:").lower()), None)

    if storyboard is not None and modo_cena and modo_cena not in storyboard.lower():
        erros.append(f"storyboard: modo de camera diferente do da cena ('{modo_cena}')")

    token = re.search(r"the product is the same (.+?):", extrair_secao(cena, "Product Lock:"))
    token = token.group(1).strip().lower() if token else ""
    if storyboard is not None and token and token not in storyboard.lower():
        erros.append(f"storyboard: nao repete o token do produto ('{token}'): a prancha vai "
                     "para o Flow junto com a cena e precisa descrever o mesmo objeto")

    if capa is not None:
        a = normalizar(extrair_secao(cena, "Subject:"))
        b = normalizar(extrair_secao(capa, "Subject:"))
        if a and b and a != b:
            erros.append("capa: 'Subject' diferente do da cena (precisa ser copia literal)")
        a = normalizar(extrair_secao(cena, "Label & Brand:").split("This is the only text")[0])
        b = normalizar(extrair_secao(capa, "Label & Brand:").split("The product label and")[0])
        if a and b and a != b:
            erros.append("capa: 'Label & Brand' diferente do da cena (precisa ser copia literal)")
        if modo_cena and modo_cena not in extrair_secao(capa, "On camera:").lower():
            avisos.append(f"capa: modo de camera diferente do da cena ('{modo_cena}')")
        cena_video = normalizar(extrair_secao(cena, "Scene:"))
        cena_capa = normalizar(extrair_secao(capa, "Scene:"))
        if cena_video and cena_video == cena_capa:
            erros.append("capa: 'Scene' identica a da cena (a capa e outro recorte do ambiente)")

    return erros, avisos


def arco_do_prompt(texto):
    """O movimento declarado no cabecalho, para caçar lote clonado."""
    achados = re.findall(r"Shot:\s*([^\]]+)", texto)
    return normalizar(achados[0]).lower() if achados else ""


def cmd_check(args):
    produtos = listar_produtos(args.ultima)
    total_erros = 0
    verificados = 0
    arcos = {}

    for _data, nome, caminho in produtos:
        cena = ler(caminho, ARQUIVO_CENA)
        storyboard = ler(caminho, ARQUIVO_STORYBOARD)
        capa = ler(caminho, ARQUIVO_CAPA)

        if cena is None and storyboard is None and capa is None:
            print(f"[ - ] {nome[:60]}: sem prompt")
            continue

        verificados += 1
        erros, avisos = [], []

        if cena is None:
            erros.append(f"falta o arquivo {ARQUIVO_CENA} (rode /start_gen_prompts)")
        else:
            e, a = validar_cena(cena)
            erros += [f"cena: {x}" for x in e]
            avisos += [f"cena: {x}" for x in a]
            arco = arco_do_prompt(cena)
            if arco:
                arcos.setdefault(arco, []).append(nome)

        if storyboard is None:
            erros.append(f"falta o arquivo {ARQUIVO_STORYBOARD} (rode /start_gen_image)")
        else:
            e, a = validar_storyboard(storyboard)
            erros += [f"storyboard: {x}" for x in e]
            avisos += [f"storyboard: {x}" for x in a]

        if capa is None:
            erros.append(f"falta o arquivo {ARQUIVO_CAPA} (rode /start_gen_buy)")
        else:
            e, a = validar_capa(capa)
            erros += [f"capa: {x}" for x in e]
            avisos += [f"capa: {x}" for x in a]

        if cena is not None:
            e, a = validar_conjunto(cena, storyboard, capa)
            erros += e
            avisos += a

        if erros:
            total_erros += len(erros)
            print(f"[ERRO] {nome[:60]}")
            for e in erros:
                print(f"       - {e}")
        else:
            print(f"[ ok ] {nome[:60]}")
        for a in avisos:
            print(f"       ~ {a}")

    for arco, nomes in arcos.items():
        if len(nomes) > 2:
            print(f"[AVISO] arco de camera repetido {len(nomes)}x no lote ({arco}):")
            for n in nomes:
                print(f"        - {n[:60]}")

    print("-" * 82)
    print(f"{verificados} produtos verificados | {total_erros} erros")
    return 1 if total_erros else 0


# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando")

    p_status = sub.add_parser("status", help="mostra o que falta em cada produto")
    p_status.add_argument("--ultima", action="store_true",
                          help="so a data mais recente (o padrao e o historico inteiro)")
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("check", help="valida os tres prompts de cada produto")
    p_check.add_argument("--ultima", action="store_true",
                          help="so a data mais recente (o padrao e o historico inteiro)")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    if not args.comando:
        args = parser.parse_args(["status"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
