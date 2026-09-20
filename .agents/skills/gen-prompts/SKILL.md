---
name: gen-prompts
description: >-
  Use this skill when the user types "/start_gen_prompts" or asks to start generating video prompts.
---

# Fluxo de Geração de Prompts de Vídeo (Antigravity)

Quando o usuário enviar `/start_gen_prompts`, você atua como **Engenheiro de Prompts de vídeo**
e produz, para cada produto do lote do dia, quatro arquivos:

- `<produto>/prompt_video/prompt_cena1.md` — o prompt do clipe 1 (10s), em inglês
- `<produto>/prompt_video/prompt_cena2.md` — o prompt do clipe 2 (10s), continuação do clipe 1
- `<produto>/prompt_video/prompt_imagem.md` — o prompt da foto estática que vai no post
- `<produto>/prompt_video/raciocinio.md`   — a justificativa da direção, em português

São **prompts separados** porque o usuário cola um de cada vez no Google Flow: gera o clipe 1,
depois cola o clipe 2 no modo de continuação (partindo do último frame gerado) e, por fim,
cola o prompt da imagem para gerar a foto do post. Cada arquivo precisa funcionar sozinho na
caixa de texto do Flow.

O usuário **já rodou** o `scraper.py`. Você **NUNCA** invoca o scraper e **NUNCA** baixa imagens.

## Invariantes (não negociáveis)

Cada prompt sai **vertical 9:16, 720p, 24fps, um único take contínuo de 10s** (os dois
juntos fazem 20s), com **tempo local `0s-10s` nos dois arquivos**,
**sem nenhuma voz** (nada de voiceover, fala, narração ou vocal na trilha) e
**sem nenhum texto na tela** (nada de legenda, letreiro, número ou marca d'água).
Esses três pontos não se negociam com o produto: se algo no roteiro conflitar, o roteiro muda.

## Passo 1 — Ver o lote

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A tabela mostra cada produto do lote mais recente das duas tabelas
(pasta `produtos/<AAAA-MM-DD>/`), quantas imagens tem, se tem `metadata.json`
e se já tem os **dois** prompts. **Trabalhe apenas nos produtos marcados como `FALTA` na
coluna PROMPT.** Só regere prompts existentes se o usuário pedir explicitamente.

## Passo 2 — Carregar as regras

Leia **o arquivo inteiro** `/home/labs/.extra_income/prompt_sistema.yaml` com `view_file`.
Ele é a fonte única da verdade: regras absolutas, presets de categoria, pares de planos,
ritmo por clipe, negative prompt canônico, os gabaritos (`gabarito_cena1` e `gabarito_cena2`)
e os dois exemplos few-shot.
Não escreva nenhum prompt antes de ter lido os dois gabaritos e o `negative_prompt`.

## Passo 3 — Distribuir os pares de planos (antes de escrever)

Monte a lista dos produtos a processar em ordem alfabética e numere a partir de 0.
Cada produto recebe um par inicial: **par sugerido = (índice mod 8) + 1** de `pares_de_planos`.

- Use o par sugerido sempre que ele servir ao produto.
- Se o produto pedir outro (um sérum não combina com dolly-in heroico), troque —
  mas escolha um par que ainda não tenha sido usado 2 vezes no lote.
- Ao delegar para subagentes, passe para cada um **o produto E o par atribuído**.
  É isso que impede o lote clonado quando vários subagentes trabalham em paralelo.

## Passo 4 — Por produto

1. **Ver as imagens de verdade.** Abra `capa.jpg` (aparência canônica) e até 4 `imagem_N.jpg`.
   Grounding é visual: não deduza o produto pelo nome da pasta.
   - Pasta sem nenhuma imagem → **pule** e anote no relatório final.
   - Imagem que é infográfico/banner/tabela de medidas → use só a geometria, ignore o resto.
2. **Ler `metadata.json`** se existir (preço, unidades, comissão, categoria, URL).
   Métrica vira decisão de direção, nunca conteúdo de tela.
3. **Travar uma variante de cor** e mantê-la nos dois clipes e na foto.
4. **Escrever `raciocinio.md`** com as 8 seções exigidas em `formato_de_saida`.
5. **Escrever `prompt_cena1.md`** seguindo o `gabarito_cena1` ao pé da letra: linha `Format`
   (`Clip 1 of 2`), linha `On camera`, as 9 seções, `[Clip 1 ... | 0s-10s | Shot: ...]` com
   VISUAL/ACTION/SFX, a linha `END FRAME` descrevendo o último quadro, e o Negative Prompt =
   BASE completa + condicionais do modo escolhido.
6. **Escrever `prompt_cena2.md`** seguindo o `gabarito_cena2`: `Style & Lighting`, `Textures`,
   `Scene` e `Subject` são **copiados e colados** do clipe 1 sem trocar uma palavra; o
   `START FRAME` repete o `END FRAME` do clipe 1 palavra por palavra; só `Camera & Framing` e a
   `Action Timeline` (`0s-10s`, beats `0-2s / 2-8s / 8-10s`) são novos.
7. **Escrever `prompt_imagem.md`** seguindo o `gabarito_prompt_imagem`: é a foto que vai
   postada junto com os vídeos. O `Subject` é **copiado e colado** do clipe 1; o ângulo, o
   enquadramento, o recorte do cenário e a pessoa em quadro são **declaradamente diferentes
   dos da foto do anúncio** (é uma foto nova do mesmo objeto, não uma cópia do material de
   terceiro). Leia a seção `imagem_de_post` do YAML antes de escrever.
8. **Conferência de grounding (obrigatória).** Reabra a `capa.jpg` com os prompts ao lado e
   responda: a cor declarada é a da foto? as peças descritas existem mesmo? a escala do cenário
   cabe no produto? tem algum material/número que você afirmou sem ver? Corrija antes de seguir.

## Passo 5 — Validar e corrigir (obrigatório)

```bash
cd /home/labs/.extra_income && python3 check_prompts.py check
```

- Cada linha `[ERRO]` aponta a regra quebrada: **corrija o arquivo e rode de novo**.
- Repita até o comando terminar com `0 erros`. Sem isso o comando não está concluído.
- Se aparecer `[AVISO] par de planos repetido`, reescreva a `Camera & Framing` e a
  `Action Timeline` dos produtos repetidos com outro par.
- Erros de par (`copia literal`, `START FRAME ... nao repete o END FRAME`) são costura quebrada:
  o Flow vai mostrar a emenda. Copie e cole em vez de reescrever.
- Avisos de tamanho (`curto demais` / `longo demais`) valem correção: prompt fora da faixa
  perde direção no fim.

## Regras de lote

- **Autonomia:** não peça confirmação produto a produto. Processe a fila inteira e só então reporte.
- **Paralelismo:** com mais de ~6 produtos, distribua em lotes com `invoke_subagent`, passando
  para cada subagente estas mesmas regras, o caminho do `prompt_sistema.yaml` e o par atribuído.
  Cada subagente lê o YAML por conta própria — não repasse o conteúdo resumido.
- **Conferência de fila:** quando os subagentes terminarem, rode `python3 check_prompts.py status`
  de novo e confirme que **nenhum** produto ficou com `FALTA` na coluna PROMPT. Subagente que
  falha em silêncio deixa buraco na fila — já aconteceu: o lote foi reportado como completo
  com 18 de 19 prontos. O `status` é a fonte da verdade, não o relatório dos subagentes.
- **Relatório final:** tabela com produto | modo de câmera | par de planos | status
  (gerado / pulado por falta de imagem), seguida da saída final do `check` com `0 erros`.
