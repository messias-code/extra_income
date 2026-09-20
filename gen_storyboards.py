#!/usr/bin/env python3
"""Plano B do /start_gen_image: gera as pranchas de 6 paineis que faltaram, por fora do Antigravity.

Usa a GEMINI_API_KEY do .env (cota separada da ferramenta interna do Antigravity),
roda em serie com backoff no erro 429 e so mexe em quem esta faltando.

    python gen_storyboards.py --dry-run     # mostra o prompt de cada um, sem chamar a API
    python gen_storyboards.py               # gera de verdade
    python gen_storyboards.py --list-models # o que a sua chave enxerga
"""

import argparse
import os
import re
import sys
import time

from dotenv import load_dotenv

from check_prompts import ARQUIVOS, caminho_do_prompt, listar_produtos, tem_os_clipes

load_dotenv()

MODELO_PADRAO = "gemini-3-pro-image"
MAX_REFERENCIAS = 3
ESPERA_ENTRE_PRODUTOS_S = 6      # o 429 veio de disparar tudo em paralelo; aqui e em fila
TENTATIVAS = 4
BACKOFF_INICIAL_S = 30

# "numbers"/"numerals" NAO entram: os numerais dos paineis sao o unico texto permitido
NEGATIVO = ("captions, sentences, titles, subtitles, overlay text, watermarks, "
            "invented logos, misspelled label, gibberish lettering, "
            "faces, heads, eyes, extra fingers, deformed hands, morphing product, "
            "different product between panels, empty panels, duplicated panels, "
            "sketch, cartoon, illustration, 3D render, oversaturation, blurry")

# Um painel por beat dos dois prompts: (rotulo, papel do beat, enquadramento sugerido).
# O tempo e local de cada clipe, por isso o rotulo traz "clip 1" / "clip 2".
PAINEIS = [
    ("clip 1, 0-2s", "hook", "wide establishing framing"),
    ("clip 1, 2-7s", "reveal", "medium shot, full product legible"),
    ("clip 1, 7-10s", "bridge", "closer angle"),
    ("clip 2, 0-2s", "pick-up", "slightly shifted angle continuing the move"),
    ("clip 2, 2-8s", "payoff", "macro close-up"),
    ("clip 2, 8-10s", "beauty shot", "composed final frame"),
]


# --------------------------------------------------------------------------- #
# prompt_cena1.md + prompt_cena2.md -> prompt de imagem
# --------------------------------------------------------------------------- #
def secao(texto, titulo):
    if titulo not in texto:
        return ""
    corpo = texto.split(titulo, 1)[1].split("\n\n", 1)[0]
    return " ".join(corpo.split())


def visual_do_clipe(texto):
    if "VISUAL:" not in texto:
        return ""
    visual = texto.split("VISUAL:", 1)[1].split("ACTION:", 1)[0]
    visual = " ".join(visual.split())
    # a marca de continuidade e instrucao de video: a imagem ja recebe isso no
    # bloco "All six panels", entao sai fora junto com a frase de recapitulacao
    visual = re.sub(r"^STRICT CONTINUATION FROM THE PREVIOUS CLIP\s*[-–]\s*", "", visual)
    return re.sub(r"^same set,[^.]*\.\s*", "", visual)


def estilo(texto):
    """Estetica e paleta do roteiro. O rabicho anti-texto ('no captions, no subtitles...')
    fica de fora: na prancha os numerais dos paineis sao texto desejado."""
    bruto = secao(texto, "Style & Lighting:").split("no captions")[0]
    return cortar(bruto, 25)


def extrair_beats(textos):
    """Os 6 momentos ja cronometrados nas linhas ACTION dos dois prompts (3 em cada).
    Sem ACTION utilizavel, cai para o VISUAL do clipe correspondente."""
    beats = []
    for texto in textos:
        acao = next((l.split("ACTION:", 1)[1] for l in texto.splitlines()
                     if l.strip().startswith("ACTION:")), "")
        pedacos = [p.strip() for p in acao.split("/") if p.strip()]
        for posicao in range(3):
            if posicao < len(pedacos):
                # o rotulo de tempo ja vai no nome do painel
                beats.append(re.sub(r"^\d+-\d+s\s*", "", pedacos[posicao]))
            else:
                beats.append(visual_do_clipe(texto))
    return beats


def cortar(texto, limite):
    """Corta por palavra sem deixar virgula solta no fim."""
    return " ".join(texto.split()[:limite]).rstrip(" ,;.")


def montar_prompt(prompt_cena1, prompt_cena2):
    on_camera = ""
    for linha in prompt_cena1.splitlines():
        if linha.startswith("On camera:"):
            on_camera = linha.replace("On camera:", "").split(".")[0].strip().lower()
            break

    beats = extrair_beats((prompt_cena1, prompt_cena2))
    linhas = [
        "A 6-panel storyboard sheet, one single image, 2 columns by 3 rows, thin clean "
        "gutters, read left to right and top to bottom. A small plain numeral from 1 to 6 "
        "in the top-left corner of each panel, and no other text anywhere.",
    ]
    for idx, (rotulo, papel, enquadramento) in enumerate(PAINEIS):
        acao = cortar(beats[idx], 22) if idx < len(beats) else ""
        linhas.append(f"PANEL {idx + 1} ({rotulo}, {papel}): {enquadramento}, {acao}.")

    linhas += [
        f"All six panels: same set, same lighting, same product, {on_camera}. "
        "Product centered in each panel.",
        "The product must match the reference photos exactly: same shape, same color "
        "variant, same finish, same proportions, and every word printed on it spelled "
        "exactly as in the references.",
        "Style: high-end commercial product photography, photoreal, cinematic lighting, "
        f"shallow depth of field, {estilo(prompt_cena1)}, vertical 9:16.",
        f"Negative: {NEGATIVO}.",
    ]
    return "\n".join(linhas)


def referencias(pasta):
    caminhos = []
    capa = os.path.join(pasta, "capa.jpg")
    if os.path.exists(capa):
        caminhos.append(capa)
    for nome in sorted(os.listdir(pasta)):
        if len(caminhos) >= MAX_REFERENCIAS:
            break
        if re.fullmatch(r"imagem_\d+\.jpg", nome):
            caminhos.append(os.path.join(pasta, nome))
    return caminhos


# --------------------------------------------------------------------------- #
# geracao
# --------------------------------------------------------------------------- #
def gerar(cliente, modelo, prompt, imagens, destino):
    from google.genai import types

    partes = [prompt]
    for caminho in imagens:
        with open(caminho, "rb") as f:
            partes.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))

    espera = BACKOFF_INICIAL_S
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = cliente.models.generate_content(model=modelo, contents=partes)
            for parte in resposta.candidates[0].content.parts:
                dados = getattr(getattr(parte, "inline_data", None), "data", None)
                if dados:
                    with open(destino, "wb") as f:
                        f.write(dados)
                    return True
            print("      [!] a resposta nao trouxe imagem")
            return False
        except Exception as e:
            erro = str(e)
            if ("429" in erro or "RESOURCE_EXHAUSTED" in erro) and tentativa < TENTATIVAS:
                print(f"      cota estourada, esperando {espera}s (tentativa {tentativa}/{TENTATIVAS})...")
                time.sleep(espera)
                espera *= 2
                continue
            print(f"      [!] falhou: {erro[:160]}")
            return False
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="so mostra os prompts")
    parser.add_argument("--model", default=MODELO_PADRAO)
    parser.add_argument("--list-models", action="store_true", help="modelos de imagem da sua chave")
    parser.add_argument("--all", action="store_true", help="todas as datas, nao so a mais recente")
    args = parser.parse_args()

    chave = os.getenv("GEMINI_API_KEY")
    cliente = None
    if not args.dry_run:
        if not chave:
            print("Erro: GEMINI_API_KEY nao encontrada no .env")
            return 1
        from google import genai
        cliente = genai.Client(api_key=chave)

    if args.list_models:
        for m in cliente.models.list():
            if "image" in m.name:
                print(m.name)
        return 0

    pendentes = []
    for _data, nome, pasta in listar_produtos(args.all):
        storyboard = os.path.join(pasta, "prompt_video", "storyboard.jpg")
        if tem_os_clipes(pasta) and not os.path.exists(storyboard):
            caminhos_md = [caminho_do_prompt(pasta, n) for n in (1, 2)]
            pendentes.append((nome, pasta, caminhos_md, storyboard))

    if not pendentes:
        print(f"Nada pendente: todo produto com {ARQUIVOS[0]} + {ARQUIVOS[1]} "
              "ja tem storyboard.jpg")
        return 0

    print(f"{len(pendentes)} storyboard(s) faltando"
          f"{' (dry-run)' if args.dry_run else f' | modelo {args.model}'}\n")

    feitos = 0
    for idx, (nome, pasta, caminhos_md, destino) in enumerate(pendentes, start=1):
        print(f"{idx}. {nome[:60]}")
        roteiros = []
        for caminho_md in caminhos_md:
            with open(caminho_md, encoding="utf-8") as f:
                roteiros.append(f.read())
        prompt = montar_prompt(*roteiros)
        imagens = referencias(pasta)

        if args.dry_run:
            print(f"   referencias: {[os.path.basename(i) for i in imagens]}")
            print("   " + prompt.replace("\n", "\n   ") + "\n")
            continue

        if gerar(cliente, args.model, prompt, imagens, destino):
            print(f"   salvo: {destino}")
            feitos += 1
        if idx < len(pendentes):
            time.sleep(ESPERA_ENTRE_PRODUTOS_S)

    if not args.dry_run:
        print(f"\n{feitos}/{len(pendentes)} gerados. Confira com: python check_prompts.py status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
