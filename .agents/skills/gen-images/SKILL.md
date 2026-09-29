---
name: gen-images
description: >-
  Use this skill when the user types "/start_gen_image" or "start_gen_image" to write the storyboard prompt for each product.
---

# Fluxo do Prompt de Storyboard (Antigravity)

Quando o usuário enviar `/start_gen_image`, você atua como **Diretor de Arte** e escreve,
para cada produto pendente, **um arquivo de texto**:

- `<produto>/prompt_video/prompt_storyboard.md` — o prompt que gera a prancha de 6 painéis

**Você NÃO gera imagem.** Este comando não chama gerador de imagem nenhum, não salva `.jpg`
e não copia artefato. Ele entrega o PROMPT; quem cola no Nano Banana 2 do Google Flow, com
as fotos do produto anexadas, é o `flow_video.py` (ou o usuário).

A prancha tem 6 painéis porque o `prompt_cena.md` tem 6 beats cronometrados. Um painel por
beat, na ordem, com o mesmo enquadramento que está entre parênteses no beat. No Flow, a prancha é o
**único ingrediente visual do vídeo** (o Veo 3.1 não vê as fotos do anúncio): ela é ao
mesmo tempo o mapa do vídeo e a cópia fiel do produto. Produto pequeno, genérico ou com
rótulo ilegível na prancha vira produto errado no vídeo. Texto de ajuda escrito na prancha
vaza para o vídeo como letreiro: por isso ela leva **só os numerais** dos painéis.

## Passo 1 — Ver a fila

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A tabela cobre **todas as datas**: **dia nenhum pode ficar sem prompt**. Trabalhe em todo
produto com `sim` na coluna CENA e `FALTA` na coluna STORY, inclusive de dias passados.
Produto sem `prompt_cena.md` ainda não é seu — ele precisa de `/start_gen_prompts` antes.

## Passo 2 — Carregar as regras

Leia o arquivo inteiro `/home/labs/.extra_income/prompt_gen_image.yaml`: layout, mapa dos
painéis, regras R1 a R9, o `formato_do_prompt_de_storyboard` e o exemplo. Não escreva nada
antes de ter lido o formato e o bloco Negative.

## Passo 3 — Por produto

1. **Ler o `prompt_cena.md` inteiro.** Dele saem: os 6 beats com os tempos e os
   enquadramentos, o `Scene`, o `Style & Lighting`, o modo de câmera da linha `On camera`,
   o `Label & Brand`, o `Physics & Staging` (estado de portas, mãos, props em cada
   instante) e, principalmente, o **token do bloco `Product Lock`**.
2. **Copiar o token** (ex.: "wine-red LUMINE glass tube") e usá-lo nos **seis** painéis,
   literalmente. É essa repetição que impede a cor e o nome da marca de mudarem de painel
   para painel — e, depois, de segundo para segundo no vídeo.
3. **Traduzir cada beat em uma frase visual** de 25 a 45 palavras, escrita como direção de
   foto: o **mesmo plano** do parêntese do beat + a ação congelada no meio do movimento +
   posição da mão/modelo + estado da parte móvel + onde está o rótulo. Nunca cole o beat
   literalmente.
4. **Escrever o arquivo** seguindo `formato_do_prompt_de_storyboard`: cabeçalho da prancha,
   PANEL 1 a PANEL 6 com os rótulos de tempo, a linha "All six panels", o bloco de
   fidelidade às fotos (rótulo soletrado e virado para a lente nos painéis 2 e 6), a linha
   Style com `vertical 9:16` e o bloco Negative. Nada de helper text, seta ou slash
   command.
5. **Arquivo limpo:** só o prompt, pronto para colar. Sem cerca de código, sem título
   markdown, sem "aqui está o prompt", sem placeholder `<...>`, sem nome de arquivo de
   referência.

## Passo 4 — Validar e corrigir (obrigatório)

```bash
cd /home/labs/.extra_income && python3 check_prompts.py check
```

- Corrija todo erro prefixado com `storyboard:` e rode de novo, até `0 erros`.
- `Negative com termo que apaga a numeracao ou o rotulo` -> tire "numbers", "numerals",
  "letters", "words", "labels", "logos" e "text" soltos do Negative: eles apagam a
  numeração dos painéis e o rótulo impresso no produto.
- `nao repete o token do produto` -> copie o token do `Product Lock` para os seis painéis.
- `modo de camera diferente do da cena` -> repita exatamente o modo da linha `On camera`.
- `helper text` / `slash command` -> tire: a prancha leva só os numerais dos painéis.

## Relatório final

Para cada produto: o nome e a confirmação de que o `check` terminou com `0 erros`. As fotos
anexadas são todas as do produto (o `flow_video.py` já faz isso).
Sem imagem gerada, sem arquivo `.jpg` criado.
