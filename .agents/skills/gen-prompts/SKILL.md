---
name: gen-prompts
description: >-
  Use this skill when the user types "/start_gen_prompts" or asks to start generating the video prompts.
---

# Fluxo de Geração de Prompts de Vídeo (Antigravity)

Quando o usuário enviar `/start_gen_prompts`, você atua como **Engenheiro de Prompts de
vídeo** e produz, para cada produto pendente, **dois** arquivos:

- `<produto>/prompt_video/prompt_cena.md` — o prompt do único clipe (10s), em inglês
- `<produto>/prompt_video/raciocinio.md` — justificativa da direção, em português

É **uma cena só**: um take contínuo de 10s escrito em 6 beats cronometrados. Não existe
clipe 2, não existe continuação, não existe END FRAME. O usuário cola o `prompt_cena.md` no
Google Flow e gera os 10s de uma vez.

Os outros dois prompts do produto saem de outros comandos e não são responsabilidade sua:
`/start_gen_image` escreve o `prompt_storyboard.md` e `/start_gen_buy` escreve o
`prompt_capa.md`.

O usuário **já rodou** o `scraper.py`. Você **NUNCA** invoca o scraper e **NUNCA** baixa
imagens.

## Invariantes (não negociáveis)

O prompt sai **vertical 9:16, 720p, 24fps, um único take contínuo de 10s**, tempo local
`0s-10s`, **mudo** (bloco `Audio` pedindo silêncio, sem trilha, sem SFX, sem voz), **sem
nenhum texto de overlay**, **sem rosto** e com o **rótulo do produto legível e soletrado**.
A `ACTION` traz os **6 beats na grade fixa** `0-1.5s / 1.5-3s / 3-5s / 5-7s / 7-8.5s /
8.5-10s`, porque cada beat vira um painel do storyboard.

## Passo 1 — Ver a fila

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A tabela mostra **todas as datas**, não só a de hoje: **dia nenhum pode ficar sem prompt**.
Trabalhe em **todo** produto marcado como `FALTA` na coluna CENA, inclusive os de dias
passados — produto antigo sem `prompt_cena.md` volta para a fila e é gerado agora. Só
regere prompt já existente se o usuário pedir.

## Passo 2 — Carregar as regras

Leia **o arquivo inteiro** `/home/labs/.extra_income/prompt_sistema.yaml`. Ele é a fonte
única da verdade: regras absolutas (R1 a R13), presets de categoria, arcos de câmera, ritmo
dos seis beats, negative prompt canônico, o `gabarito_cena` e os dois exemplos few-shot.
Não escreva nada antes de ter lido o `gabarito_cena`, a `R13_EVENTO_EM_CADA_BEAT` e o
`negative_prompt`.

## Passo 3 — Distribuir os arcos de câmera (antes de escrever)

Liste os produtos a processar em ordem alfabética e numere a partir de 0.
**Arco sugerido = (índice mod 8) + 1** de `arcos_de_camera`.

- Use o arco sugerido sempre que ele servir ao produto.
- Se o produto pedir outro, troque — mas não use o mesmo arco mais de 2x no lote.
- Ao delegar para subagentes, passe **o produto E o arco atribuído**. É isso que impede
  lote clonado quando vários subagentes trabalham em paralelo.

Atenção à ordem de decisão: **primeiro o que acontece na cena, depois o arco que mostra
esse acontecimento**. Arco escolhido antes da ação devolve produto parado com a câmera
girando em volta — o pior resultado que este pipeline já produziu.

## Passo 4 — Por produto

1. **Ver as imagens de verdade.** Abra `capa.jpg` e até 4 `imagem_N.jpg`. Ignore
   infográfico, banner e tabela de medidas.
2. **Ler `metadata.json`** (preço, volume, fonte) e deixar que ele mude a direção.
3. **Escrever `raciocinio.md`** com as 8 seções, em português.
4. **Escrever `prompt_cena.md`** seguindo o `gabarito_cena` ao pé da letra: linha `Format`
   com `Single clip`, linha `On camera` com um dos três modos, as seções `Style & Lighting`,
   `Textures to Highlight`, `Scene`, `Subject`, `Label & Brand` (marca soletrada com
   hifens), `Camera & Framing`, `Continuity Anchors`, `Storyboard Adherence`,
   `Action Timeline` (`[Clip - ... | 0s-10s | Shot: ...]` + VISUAL + ACTION com os 6 beats),
   `Audio` e o `Negative Prompt` = BASE completa + condicionais do modo.
5. **Conferir cada beat (R13).** Cada um descreve um **evento físico** — alguma coisa no
   mundo muda de estado — e termina com o **enquadramento entre parênteses**. Nenhum beat
   começa com "the camera". Teste: congele a câmera; se não sobrou nada acontecendo, o beat
   está errado.
6. **Conferência de grounding (obrigatória).** Reabra a `capa.jpg` com o prompt ao lado:
   a cor declarada é a da foto? as peças descritas existem? a escala do cenário cabe no
   produto? afirmou algum material ou número que não viu? Corrija antes de seguir.

## Passo 5 — Validar e corrigir (obrigatório)

```bash
cd /home/labs/.extra_income && python3 check_prompts.py check
```

- Cada linha `[ERRO]` aponta uma regra quebrada: **corrija o arquivo e rode de novo**.
- Repita até terminar com `0 erros`. Sem isso o comando não está concluído.
- `beat ... sem o enquadramento entre parenteses` e `beat ... comeca pela camera` são o
  defeito que gera vídeo de catálogo: reescreva o beat com um evento, não com a lente.
- `[AVISO] arco de camera repetido` -> reescreva `Camera & Framing` e `Action Timeline`
  dos produtos repetidos com outro arco.
- Os erros de storyboard e de capa só aparecem depois que os outros dois comandos rodarem;
  ignore-os aqui, mas não ignore nenhum erro prefixado com `cena:`.

## Regras de lote

- **Autonomia:** não peça confirmação produto a produto. Processe a fila inteira e só então
  reporte.
- **Cobertura:** a fila é o histórico inteiro, não só o dia de hoje. Terminou o dia mais
  recente e sobrou dia antigo com `FALTA`? Continue por ele.
- **Paralelismo:** com mais de ~6 produtos, distribua em lotes com `invoke_subagent`,
  passando as mesmas regras, o caminho do `prompt_sistema.yaml` e o arco atribuído. Cada
  subagente lê o YAML por conta própria — não repasse conteúdo resumido.
- **Conferência de fila:** quando os subagentes terminarem, rode `status` de novo e confirme
  que **nenhum** produto ficou com `FALTA` na coluna CENA. Subagente que falha em silêncio
  deixa buraco na fila — já aconteceu: o lote foi reportado como completo com 18 de 19.
  O `status` é a fonte da verdade, não o relatório dos subagentes.
- **Relatório final:** tabela com produto | modo de câmera | arco usado, e a linha final do
  `check` com `0 erros`.
