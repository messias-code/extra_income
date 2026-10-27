---
name: gen-prompts
description: >-
  Use this skill when the user types "start_gen_prompts", "/start_gen_prompts", asks to load skill "gen-prompts", or asks to start generating the video prompts.
---

# Fluxo de Geração de Prompts de Vídeo (Antigravity)

Quando o usuário enviar `/start_gen_prompts`, você atua como **Engenheiro de Prompts de
vídeo** e produz, para cada produto pendente, **dois** arquivos:

- `<produto>/prompt_video/prompt_cena.md` — o prompt do único clipe (8s, Veo 3.1 Quality), em inglês
- `<produto>/prompt_video/raciocinio.md` — justificativa da direção, em português

É **uma cena só**: um take contínuo de 8s escrito em 6 beats cronometrados. Não existe
clipe 2, não existe continuação, não existe END FRAME. O `flow_video.py` cola o
`prompt_cena.md` no Google Flow (Veo 3.1 - Quality) e gera os 8s de uma vez.

**Atenção ao caminho:** no Flow, o vídeo recebe como ingrediente **só a prancha do
storyboard**, nunca as fotos do anúncio. O que o texto não descrever com precisão
(forma, cor, rótulo, estado das partes) o Veo inventa.

Os outros dois prompts do produto saem de outros comandos e não são responsabilidade sua:
`/start_gen_image` escreve o `prompt_storyboard.md` e `/start_gen_buy` escreve o
`prompt_capa.md`. Depois dos três, `/prompt_gen_check` revisa o conjunto.

O usuário **já rodou** o `scraper.py`. Você **NUNCA** invoca o scraper e **NUNCA** baixa
imagens.

## Invariantes (não negociáveis)

O prompt sai **vertical 9:16, 720p, 24fps, um único take contínuo de 8s**, tempo local
`0s-8s`, **mudo** (bloco `Audio` pedindo silêncio, sem trilha, sem SFX, sem voz), **sem
nenhum texto de overlay**, **sem rosto** e com o **rótulo do produto legível e soletrado**.
A `ACTION` traz os **6 beats na grade fixa** `0-1.5s / 1.5-3s / 3-4.5s / 4.5-6s / 6-7s /
7-8s`, porque cada beat vira um painel do storyboard. Toda ação é classificada na
**escada de risco** (N1 seguro / N2 com encenação, no máximo uma por clipe / N3 proibido)
e protegida pelo bloco `Physics & Staging`.

## Passo 1 — Ver a fila

```bash
python3 check_prompts.py status
```

A tabela mostra **todas as datas**, não só a de hoje: **dia nenhum pode ficar sem prompt**.
Trabalhe em **todo** produto marcado como `FALTA` na coluna CENA, inclusive os de dias
passados — produto antigo sem `prompt_cena.md` volta para a fila e é gerado agora. Só
regere prompt já existente se o usuário pedir.

## Passo 2 — Carregar as regras

Leia **o arquivo inteiro** `prompt_sistema.yaml` na raiz do projeto. Ele é a fonte
única da verdade: `como_o_flow_usa_este_arquivo`, `leitura_das_imagens`, regras
absolutas (R1 a R16), `escada_de_risco_da_acao`, presets de categoria, arcos de câmera,
ritmo dos seis beats, negative prompt canônico, o `gabarito_cena` e os dois exemplos
few-shot. Não escreva nada antes de ter lido o `gabarito_cena`, a
`escada_de_risco_da_acao`, a `R16_FISICA_E_ENCENACAO` e o `negative_prompt`.

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

1. **Ver as imagens de verdade.** Abra `capa.jpg` e todas as `imagem_N.jpg`. De
   infográfico, tire só geometria, peças e cor. Aplique `leitura_das_imagens`: variante
   única, conflito título x foto (as fotos vencem), duas versões de rótulo, escala, peças,
   texto impresso no produto x arte de marketing.
2. **Ler `metadata.json`** (preço, volume, fonte) e deixar que ele mude a direção.
3. **Escolher a ação** que prova o produto e classificá-la na escada de risco (N1/N2;
   N3 vira a versão N2/N1 equivalente). Só depois escolher o arco.
4. **Escrever `raciocinio.md`** com os 9 itens do `formato_de_saida`, em português.
5. **Escrever `prompt_cena.md`** seguindo o `gabarito_cena` ao pé da letra: linha `Format`
   com `Single continuous shot of 8s | Single clip`, linha `On camera` com um dos modos,
   as seções `Style & Lighting`, `Textures to Highlight`, `Scene`, `Subject`,
   `Product Lock`, `Label & Brand` (marca soletrada com hifens), `Camera & Framing`,
   `Physics & Staging`, `Continuity Anchors`, `Storyboard Adherence`, `Action Timeline`
   (`[Clip - ... | 0s-8s | Shot: ...]` + VISUAL + ACTION com os 6 beats), `Audio` e o
   `Negative Prompt` = BASE completa + condicionais.
6. **Conferir cada beat (R13).** Cada um descreve um **evento físico** — alguma coisa no
   mundo muda de estado — e termina com o **enquadramento entre parênteses**. Nenhum beat
   começa com "the camera". Teste: congele a câmera; se não sobrou nada acontecendo, o beat
   está errado.
7. **Conferência de física (obrigatória).** Leia os 6 beats contra o `Physics & Staging`:
   todo objeto, mão, porta, prato ou névoa que aparece nos beats está declarado em 0s? a
   parte que não pode se mexer está travada? existe só uma ação N2?
8. **Conferência de grounding (obrigatória).** Reabra a `capa.jpg` com o prompt ao lado:
   a cor declarada é a da foto? as peças descritas existem? a escala do cenário cabe no
   produto? afirmou algum material ou número que não viu? Corrija antes de seguir.

## Passo 5 — Validar e corrigir (obrigatório)

```bash
python3 check_prompts.py check
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
- **Relatório final:** tabela com produto | modo de câmera | ação (N1/N2) | arco usado,
  os conflitos de grounding registrados, e a linha final do `check` com `0 erros`.
  Lembre o usuário de rodar `/start_gen_image`, `/start_gen_buy` e depois
  `/prompt_gen_check`.
