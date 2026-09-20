#!/usr/bin/env python3
"""Utilitario do pipeline Extra Income.

Dois comandos:
    python check_prompts.py status   -> o que ja existe / o que falta em cada produto
    python check_prompts.py check    -> valida os prompt_cena1.md / prompt_cena2.md contra
                                        as regras do prompt_sistema.yaml (checklist_final)

Cada produto tem DOIS prompts de 10s: o clipe 1 e o clipe 2, que e colado no Google Flow
como continuacao do primeiro. Alem de validar cada arquivo, o check confere o par: os
blocos compartilhados precisam ser identicos palavra por palavra e o START FRAME do clipe 2
precisa repetir o END FRAME do clipe 1.

Por padrao olha so a pasta de data mais recente em produtos/. Use --all para todas.
Sai com codigo 1 se algum prompt tiver erro (da para usar em loop de correcao).
"""

import argparse
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ_PRODUTOS = os.path.join(BASE_DIR, "produtos")
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SECOES_OBRIGATORIAS = [
    "Style & Lighting:",
    "Textures to Highlight:",
    "Scene:",
    "Subject:",
    "Camera & Framing:",
    "Continuity Anchors:",
    "Action Timeline:",
    "Audio Design:",
    "Negative Prompt:",
]

MODOS_DE_CAMERA = ["product only", "hands only", "headless model"]

ARQUIVOS = ("prompt_cena1.md", "prompt_cena2.md")
ARQUIVO_IMAGEM = "prompt_imagem.md"

# a foto estatica que vai postada junto com os dois videos
SECOES_IMAGEM = [
    "Subject:",
    "New Angle & Framing:",
    "Scene:",
    "Light & Mood:",
    "Textures to Highlight:",
    "Model & Hands:",
    "Product Fidelity:",
    "Originality:",
    "Negative Prompt:",
]
NEGATIVE_IMAGEM_OBRIGATORIO = [
    "text", "watermarks", "logos", "faces", "collage",
    "duplicated product", "catalogue white background",
]
PALAVRAS_IMAGEM_MIN, PALAVRAS_IMAGEM_MAX = 200, 330

# os 3 beats de cada clipe (tempo local, cada clipe comeca em 0s);
# juntos viram os 6 paineis numerados do storyboard
BEATS = {1: ["0-2s", "2-7s", "7-10s"], 2: ["0-2s", "2-8s", "8-10s"]}

# blocos que o clipe 2 copia palavra por palavra do clipe 1
SECOES_COMPARTILHADAS = ["Style & Lighting:", "Textures to Highlight:", "Scene:", "Subject:"]

MARCA_START = "CONTINUES FROM THE FINAL FRAME OF THE PREVIOUS CLIP"
MARCA_VISUAL_2 = "STRICT CONTINUATION FROM THE PREVIOUS CLIP"
RABICHO_START = "No cut, no new establishing shot, no time jump"

# tokens que a BASE do negative prompt precisa conter
NEGATIVE_OBRIGATORIO = [
    "text", "typography", "captions", "watermarks", "logos",
    "faces", "morphing product", "horizontal framing",
]

PALAVRAS_MIN, PALAVRAS_MAX = 330, 480  # corpo de CADA arquivo, sem o Negative Prompt


# --------------------------------------------------------------------------- #
# descoberta de pastas
# --------------------------------------------------------------------------- #
def pastas_de_data():
    """Datas em produtos/, da mais antiga para a mais recente. O nome e AAAA-MM-DD
    justamente para a ordem alfabetica ja ser a ordem cronologica."""
    if not os.path.isdir(RAIZ_PRODUTOS):
        return []
    return sorted(d for d in os.listdir(RAIZ_PRODUTOS) if DATA_RE.match(d))


def listar_produtos(todas_as_datas=False):
    """Devolve (data, nome_do_produto, caminho_absoluto)."""
    produtos = []
    datas = pastas_de_data()
    for data in (datas if todas_as_datas else datas[-1:]):
        raiz = os.path.join(RAIZ_PRODUTOS, data)
        for nome in sorted(os.listdir(raiz)):
            caminho = os.path.join(raiz, nome)
            if os.path.isdir(caminho):
                produtos.append((data, nome, caminho))
    return produtos


def caminho_do_prompt(caminho_produto, numero):
    return os.path.join(caminho_produto, "prompt_video", ARQUIVOS[numero - 1])


def caminho_da_imagem(caminho_produto):
    return os.path.join(caminho_produto, "prompt_video", ARQUIVO_IMAGEM)


def tem_os_clipes(caminho_produto):
    """So os dois prompts de video: e o que o storyboard precisa."""
    return all(os.path.exists(caminho_do_prompt(caminho_produto, n)) for n in (1, 2))


def todos_os_prompts(caminho_produto):
    return tem_os_clipes(caminho_produto) and os.path.exists(caminho_da_imagem(caminho_produto))


def contar_imagens(caminho):
    return len([f for f in os.listdir(caminho)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])


# --------------------------------------------------------------------------- #
# comando: status
# --------------------------------------------------------------------------- #
def cmd_status(args):
    produtos = listar_produtos(args.all)
    if not produtos:
        print("Nenhum produto encontrado. Rode o scraper.py primeiro.")
        return 0

    print(f"{'PRODUTO':<52} {'IMGS':>4} {'META':>5} {'PROMPT':>7} {'STORY':>6}")
    print("-" * 78)
    faltando_prompt, faltando_story = [], []
    for data, nome, caminho in produtos:
        imgs = contar_imagens(caminho)
        meta = "sim" if os.path.exists(os.path.join(caminho, "metadata.json")) else "-"
        story = os.path.join(caminho, "prompt_video", "storyboard.jpg")
        tem_prompt = todos_os_prompts(caminho)
        tem_story = os.path.exists(story)
        if not tem_prompt:
            faltando_prompt.append(nome)
        elif not tem_story:
            faltando_story.append(nome)
        print(f"{nome[:52]:<52} {imgs:>4} {meta:>5} "
              f"{'sim' if tem_prompt else 'FALTA':>7} {'sim' if tem_story else 'FALTA':>6}")

    print("-" * 78)
    print(f"{len(produtos)} produtos | "
          f"{len(faltando_prompt)} sem os 3 prompts | {len(faltando_story)} sem storyboard.jpg")
    if faltando_prompt:
        print("  -> rode /start_gen_prompts")
    if faltando_story:
        print("  -> rode /start_gen_image")
    return 0


# --------------------------------------------------------------------------- #
# comando: check
# --------------------------------------------------------------------------- #
def validar_clipe(texto, numero):
    """Devolve (erros, avisos) de um prompt_cenaN.md isolado."""
    erros, avisos = [], []
    linhas = [l.strip() for l in texto.strip().splitlines()]
    if not linhas:
        return ["arquivo vazio"], []

    # 1. linha Format
    f = linhas[0]
    if not f.startswith("Format:"):
        erros.append("primeira linha nao e a linha 'Format:'")
    else:
        for exigido in ["9:16", "720p", "24fps", "10s", f"Clip {numero} of 2"]:
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

    # 4. cabecalho do clipe e tempo LOCAL (cada clipe comeca em 0s)
    cabecalho = next((l for l in linhas if l.startswith(f"[Clip {numero}")), None)
    if not cabecalho:
        erros.append(f"falta o cabecalho '[Clip {numero} - ...]'")
    else:
        if "0s-10s" not in cabecalho:
            erros.append("cabecalho sem a marcacao de tempo '0s-10s'")
        if "Shot:" not in cabecalho:
            erros.append("cabecalho sem 'Shot:'")
    if "10s-20s" in texto:
        erros.append("marcacao antiga '10s-20s': no Flow cada clipe tem tempo local 0s-10s")

    # 5. handoff entre os clipes
    if numero == 1:
        if "END FRAME:" not in texto:
            erros.append("falta a linha 'END FRAME:' (o clipe 2 retoma esse quadro)")
    else:
        inicio = extrair_secao(texto, "START FRAME:")
        if not inicio:
            erros.append("falta a linha 'START FRAME:'")
        else:
            if MARCA_START not in inicio:
                erros.append(f"START FRAME sem '{MARCA_START}'")
            if RABICHO_START not in inicio:
                avisos.append("START FRAME sem o lembrete 'No cut, no new establishing shot...'")
        if MARCA_VISUAL_2 not in texto:
            erros.append(f"VISUAL do clipe 2 nao comeca com '{MARCA_VISUAL_2}'")

    for marcador in ("VISUAL:", "ACTION:", "SFX:"):
        if marcador not in texto:
            erros.append(f"falta a linha '{marcador}'")

    # os 3 beats viram 3 dos 6 paineis do storyboard: sem eles o /start_gen_image nao tem mapa
    for beat in BEATS[numero]:
        if beat not in texto:
            erros.append(f"falta o beat '{beat}' na linha ACTION")

    # 6. regras de texto e voz
    estilo = extrair_secao(texto, "Style & Lighting:")
    if "textless" not in estilo.lower():
        erros.append("Style & Lighting sem 'textless'")

    audio = extrair_secao(texto, "Audio Design:")
    if "no voiceover" not in audio.lower():
        erros.append("Audio Design sem 'STRICTLY NO VOICEOVER'")
    if "no lyrics" not in audio.lower():
        erros.append("Audio Design sem 'instrumental only, no lyrics'")
    if numero == 2 and "continuing from the previous clip" not in audio.lower():
        avisos.append("Audio Design sem 'same instrumental track continuing from the previous clip'")

    # 7. negative prompt
    negativo = extrair_secao(texto, "Negative Prompt:").lower()
    faltantes = [x for x in NEGATIVE_OBRIGATORIO if x not in negativo]
    if faltantes:
        erros.append("Negative Prompt incompleto, falta: " + ", ".join(faltantes))
    if "hands only" in texto.lower() and "deformed hands" not in negativo:
        avisos.append("modo 'hands only' sem os condicionais de mao no Negative Prompt")
    if "headless model" in texto.lower() and "head" not in negativo:
        avisos.append("modo 'headless model' sem os condicionais de rosto no Negative Prompt")

    # 8. nada de voz nem texto vazando para dentro do roteiro
    corpo = texto.split("Negative Prompt:")[0].lower()
    for proibido in ("narrator", "voice-over:", "voiceover:", "dialogue:",
                     "on-screen text", "caption reads", "title card"):
        if proibido in corpo:
            erros.append(f"o roteiro pede voz ou texto na tela: '{proibido}'")

    # 9. sujeira de geracao
    if "```" in texto:
        erros.append("o arquivo contem cerca de codigo (```)")
    if re.search(r"<[a-zA-Z][^>]{2,}>", texto):
        erros.append("sobrou placeholder '<...>' do gabarito")
    if "<IMAGE_" in texto.upper():
        erros.append("referencia '<IMAGE_n>' proibida (o prompt precisa ser autossuficiente)")

    # 10. tamanho (so o corpo criativo; o Negative Prompt e lista, nao prosa)
    palavras = len(texto.split("Negative Prompt:")[0].split())
    if palavras < PALAVRAS_MIN:
        avisos.append(f"curto demais: {palavras} palavras (alvo {PALAVRAS_MIN}-{PALAVRAS_MAX})")
    elif palavras > PALAVRAS_MAX:
        avisos.append(f"longo demais: {palavras} palavras (alvo {PALAVRAS_MIN}-{PALAVRAS_MAX})")

    return erros, avisos


def validar_imagem(texto):
    """Devolve (erros, avisos) do prompt_imagem.md: a foto de post."""
    erros, avisos = [], []
    linhas = [l.strip() for l in texto.strip().splitlines()]
    if not linhas:
        return ["arquivo vazio"], []

    f = linhas[0]
    if not f.startswith("Format:"):
        erros.append("primeira linha nao e a linha 'Format:'")
    else:
        for exigido in ["single still photograph", "9:16"]:
            if exigido not in f:
                erros.append(f"linha Format sem '{exigido}'")

    on_camera = next((l for l in linhas[:4] if l.startswith("On camera:")), None)
    if not on_camera:
        erros.append("falta a linha 'On camera:'")
    elif not any(m in on_camera.lower() for m in MODOS_DE_CAMERA):
        erros.append("linha 'On camera:' sem um dos modos: product only / hands only / headless model")

    for secao in SECOES_IMAGEM:
        if secao not in texto:
            erros.append(f"falta a secao '{secao}'")

    negativo = extrair_secao(texto, "Negative Prompt:").lower()
    faltantes = [x for x in NEGATIVE_IMAGEM_OBRIGATORIO if x not in negativo]
    if faltantes:
        erros.append("Negative Prompt incompleto, falta: " + ", ".join(faltantes))

    corpo = texto.split("Negative Prompt:")[0]
    # so a parte criativa: os blocos Product Fidelity e Originality citam o fundo branco
    # justamente para PROIBI-lo, e nao podem disparar o alarme
    criativo = corpo.split("Product Fidelity:")[0].lower()
    for fundo in ("white background", "plain background", "studio backdrop",
                  "seamless backdrop", "grey background", "gray background"):
        if fundo in criativo:
            erros.append(f"a foto pede '{fundo}': o cenario tem que ser real e diferente do anuncio")
    if "```" in texto:
        erros.append("o arquivo contem cerca de codigo (```)")
    if re.search(r"<[a-zA-Z][^>]{2,}>", texto):
        erros.append("sobrou placeholder '<...>' do gabarito")
    if "<IMAGE_" in texto.upper():
        erros.append("referencia '<IMAGE_n>' proibida (o prompt precisa ser autossuficiente)")

    palavras = len(corpo.split())
    if palavras < PALAVRAS_IMAGEM_MIN:
        avisos.append(f"curto demais: {palavras} palavras "
                      f"(alvo {PALAVRAS_IMAGEM_MIN}-{PALAVRAS_IMAGEM_MAX})")
    elif palavras > PALAVRAS_IMAGEM_MAX:
        avisos.append(f"longo demais: {palavras} palavras "
                      f"(alvo {PALAVRAS_IMAGEM_MIN}-{PALAVRAS_IMAGEM_MAX})")

    return erros, avisos


def normalizar(texto):
    return " ".join(texto.split()).strip(" -.")


def validar_conjunto(texto1, texto2, texto_imagem=None):
    """O que so da para conferir com os arquivos lado a lado: a costura entre eles."""
    erros, avisos = [], []

    for secao in SECOES_COMPARTILHADAS:
        a, b = normalizar(extrair_secao(texto1, secao)), normalizar(extrair_secao(texto2, secao))
        if a and b and a != b:
            erros.append(f"'{secao[:-1]}' diferente entre os clipes (precisa ser copia literal)")

    a, b = normalizar(extrair_secao(texto1, "On camera:")), normalizar(extrair_secao(texto2, "On camera:"))
    if a and b and a != b:
        erros.append("linha 'On camera:' diferente entre os clipes")

    fim = normalizar(extrair_secao(texto1, "END FRAME:"))
    inicio = extrair_secao(texto2, "START FRAME:")
    if RABICHO_START in inicio:
        inicio = inicio.split(RABICHO_START)[0]
    if MARCA_START in inicio:
        inicio = inicio.split(MARCA_START, 1)[1]
    inicio = normalizar(inicio)
    if fim and inicio and fim != inicio:
        erros.append("START FRAME do clipe 2 nao repete o END FRAME do clipe 1 palavra por palavra")

    a, b = normalizar(extrair_secao(texto1, "Camera & Framing:")), normalizar(extrair_secao(texto2, "Camera & Framing:"))
    if a and a == b:
        erros.append("Camera & Framing igual nos dois clipes: o clipe 2 e o segundo plano do par")

    a, b = normalizar(extrair_secao(texto1, "Negative Prompt:")), normalizar(extrair_secao(texto2, "Negative Prompt:"))
    if a and b and a != b:
        avisos.append("Negative Prompt diferente entre os clipes")

    if texto_imagem is not None:
        a, b = normalizar(extrair_secao(texto1, "Subject:")), normalizar(extrair_secao(texto_imagem, "Subject:"))
        if a and b and a != b:
            erros.append("imagem: 'Subject' diferente do clipe 1 (precisa ser copia literal)")
        a = normalizar(extrair_secao(texto1, "On camera:"))
        b = normalizar(extrair_secao(texto_imagem, "On camera:"))
        if a and b and a.split(".")[0] != b.split(".")[0]:
            avisos.append("imagem: modo da linha 'On camera:' diferente do dos videos")
        cena_video = normalizar(extrair_secao(texto1, "Scene:"))
        cena_foto = normalizar(extrair_secao(texto_imagem, "Scene:"))
        if cena_video and cena_video == cena_foto:
            erros.append("imagem: 'Scene' identica a do clipe 1 (a foto e outro recorte do ambiente)")

    return erros, avisos


def extrair_secao(texto, titulo):
    """Conteudo de uma secao ate a proxima secao/linha em branco dupla."""
    if titulo not in texto:
        return ""
    resto = texto.split(titulo, 1)[1]
    return resto.split("\n\n", 1)[0]


def planos_do_prompt(texto):
    return [m.strip().rstrip("]").lower()
            for m in re.findall(r"Shot:\s*([^\]]+)", texto)]


def cmd_check(args):
    produtos = listar_produtos(args.all)
    total_erros = 0
    verificados = 0
    pares_de_planos = {}

    for _data, nome, caminho in produtos:
        textos, faltando = {}, []
        for numero in (1, 2):
            arquivo = caminho_do_prompt(caminho, numero)
            if os.path.exists(arquivo):
                with open(arquivo, encoding="utf-8") as fh:
                    textos[numero] = fh.read()
            else:
                faltando.append(ARQUIVOS[numero - 1])

        imagem = None
        arquivo_imagem = caminho_da_imagem(caminho)
        if os.path.exists(arquivo_imagem):
            with open(arquivo_imagem, encoding="utf-8") as fh:
                imagem = fh.read()
        else:
            faltando.append(ARQUIVO_IMAGEM)

        if not textos and imagem is None:
            print(f"[ - ] {nome[:60]}: sem prompt")
            continue

        verificados += 1
        erros = [f"falta o arquivo {a}" for a in faltando]
        avisos = []
        for numero in sorted(textos):
            e, a = validar_clipe(textos[numero], numero)
            erros += [f"clipe {numero}: {x}" for x in e]
            avisos += [f"clipe {numero}: {x}" for x in a]

        if imagem is not None:
            e, a = validar_imagem(imagem)
            erros += [f"imagem: {x}" for x in e]
            avisos += [f"imagem: {x}" for x in a]

        if len(textos) == 2:
            e, a = validar_conjunto(textos[1], textos[2], imagem)
            erros += e
            avisos += a
            par = " -> ".join(planos_do_prompt(textos[1]) + planos_do_prompt(textos[2]))
            if par:
                pares_de_planos.setdefault(par, []).append(nome)

        if erros:
            total_erros += len(erros)
            print(f"[ERRO] {nome[:60]}")
            for e in erros:
                print(f"       - {e}")
        else:
            print(f"[ ok ] {nome[:60]}")
        for a in avisos:
            print(f"       ~ {a}")

    for par, nomes in pares_de_planos.items():
        if len(nomes) > 2:
            print(f"[AVISO] par de planos repetido {len(nomes)}x no lote ({par}):")
            for n in nomes:
                print(f"        - {n[:60]}")

    print("-" * 78)
    print(f"{verificados} produtos verificados | {total_erros} erros")
    return 1 if total_erros else 0


# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando")

    p_status = sub.add_parser("status", help="mostra o que falta em cada produto")
    p_status.add_argument("--all", action="store_true", help="todas as datas, nao so a mais recente")
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("check", help="valida os dois prompts de cada produto")
    p_check.add_argument("--all", action="store_true", help="todas as datas, nao so a mais recente")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    if not args.comando:
        args = parser.parse_args(["status"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
