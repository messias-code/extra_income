---
name: gen-buy
description: >-
  Use this skill when the user types "/start_gen_buy" or "start_gen_buy" to write the two carousel prompts of each product (cover and slide 2).
---

# Fluxo do Prompt de Capa (Antigravity)

Quando o usuário enviar `/start_gen_buy`, você escreve, para cada produto pendente, **dois
arquivos de texto** — o post é um carrossel de 2 imagens:

- `<produto>/prompt_video/prompt_capa.md` — slide 1, a capa que para o scroll
- `<produto>/prompt_video/prompt_capa_2.md` — slide 2: o KIT em knolling (produto com
  várias peças) ou o detalhe que prova o benefício (produto único); regra em
  `slide_2_carrossel`

**Você NÃO gera imagem.** Este comando entrega o PROMPT; quem cola no Nano Banana 2 do
Google Flow, com as fotos do produto anexadas, é o `flow_video.py` (ou o usuário).

A capa é o **post de feed do Instagram** (4:5), gerada numa tela **3:4** (o Flow não tem
4:5): foto nova do mesmo objeto
(nunca cópia da imagem do anúncio), editada e chamativa, com cara de peça criada pela
direção de arte de uma marca real — nunca imagem genérica de IA, panfleto ou template. O
produto é o protagonista, grande, inteiro, nítido e assentado no cenário com sombra
natural; produto e texto ficam no centro, com margem folgada nos quatro lados (o feed
recorta a tela 3:4 em 4:5 e a grade do perfil recorta de novo).

Cada produto recebe **uma de duas famílias** de arte (regra em `familias`):

- **A — brand editorial**: eletro, gadget, relógio, suplemento, ferramentas, banheiro,
  moda masculina, shapewear. Tipografia de marca, color grading forte, um acento gráfico.
  Texto: **3 linhas**, até 13 palavras.
- **B — lifestyle scrapbook**: beleza, perfumaria, skincare, cabelo, moda feminina,
  livro. Doodles à mão e escrita à mão. Texto: **3 linhas + até 3 callouts** curtos
  apontando partes reais, até 20 palavras.

As 3 linhas: **título** (até 4 palavras, soletrado com hifens), **frase de benefício**
(até 6) e **CTA discreto** (até 3, ex.: `Link na bio`). Português correto e acentuado.
**Proibido** chamada apelativa, exclamação, selo, botão. **Preço nunca** e nenhum número
no texto da arte — mas número impresso no próprio produto continua como está.

Ordem dos comandos: `scraper.py` -> `/start_gen_prompts` -> `/start_gen_image` ->
`/start_gen_buy` -> `/prompt_gen_check`.

## Passo 1 — Ver a fila

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A tabela cobre **todas as datas**: **dia nenhum pode ficar sem prompt**. Trabalhe em todo
produto com `sim` na coluna CENA e `FALTA` na coluna CAPA ou CAPA2, inclusive de dias
passados. Todo produto sai com **os dois** arquivos. Se o `prompt_capa.md` já existe, escreva só o
`prompt_capa_2.md` a partir dele (mesma família e paleta), sem mexer na capa.

## Passo 2 — Carregar as regras

Leia o arquivo inteiro `/home/labs/.extra_income/prompt_gen_buy.yaml`: o que é a capa, o
bloco `instagram`, as `familias`, o texto da peça, `numeros_no_produto`, as regras
absolutas, o `gabarito_prompt_capa`, o `negative_prompt_capa`, o `slide_2_carrossel` e os
dois exemplos (um de cada família). Leia também `aprendizados_de_campo` no
`prompt_sistema.yaml`: capa aprovada pelo usuário é o modelo a seguir na categoria.

## Passo 3 — Por produto

1. **Ler o `prompt_cena.md` inteiro** e abrir a `capa.jpg` e as secundárias.
   **Escolher a família** (A ou B) pela categoria e identidade do produto.
2. **Copiar literalmente** os blocos `Subject` e `Label & Brand` do prompt da cena — palavra
   por palavra, sem reescrever. É o que garante que a capa e o vídeo mostrem o mesmo objeto.
3. **Mudar de propósito**: `Scene`, ângulo e enquadramento são **declaradamente diferentes**
   dos do vídeo e dos da foto do anúncio. Fundo contextual do nicho do produto, com um ou
   dois elementos de apoio; fundo branco de catálogo, fundo liso e ciclorama estão
   proibidos.
4. **Escrever o texto da peça**: título soletrado com hifens (`C-O-R Q-U-E F-I-C-A`),
   frase de benefício tirada do que se vê nas fotos, CTA discreto e, na família B, os
   callouts ligados por setinha a partes reais — sem chamada apelativa, sem número, sem
   preço, com acento. Releia cada palavra em voz alta: erro de português na arte é o que
   mais queima o post.
5. **Escrever o arquivo** seguindo o `gabarito_prompt_capa`: linha `Format` com
   `single still photograph`, `vertical 3:4 canvas for a 4:5 Instagram feed post` e `brand editorial` ou
   `lifestyle scrapbook` + `promotional cover shot`, linha `On camera` com o mesmo modo da
   cena + a frase de preço/números, e as seções
   `Art Direction`, `Subject`,
   `Label & Brand`, `Layout & Composition`, `Promo Copy`, `Text Style`, `Scene`,
   `Light & Mood`, `Textures to Highlight`, `Model & Hands`, `Product Fidelity`,
   `Originality` e `Negative Prompt`.
6. **Slide 2** (`prompt_capa_2.md`): conte as peças nas fotos. Duas ou mais separáveis =
   KIT: knolling com todas, cada uma uma vez, `product only`. Senão, o detalhe do
   benefício. Mesma família e paleta do slide 1, `Format` termina em
   `<família> carousel slide 2`, seção extra `Slide Focus:` depois do `Label & Brand`,
   até 5 callouts nas duas famílias (22 palavras na A, 26 na B).
7. **Arquivo limpo:** só o prompt, pronto para colar. Sem slash command.

## Passo 4 — Validar e corrigir (obrigatório)

```bash
cd /home/labs/.extra_income && python3 check_prompts.py check
```

- Corrija todo erro prefixado com `capa:` ou `capa 2:` e rode de novo, até `0 erros`.
- `'Subject' diferente do da cena` -> copie e cole, não reescreva.
- `'Scene' identica a da cena` -> a capa é outro recorte do ambiente, não o mesmo quadro.
- `a capa pede 'white background'` -> troque por um cenário real.
- `chamada apelativa` -> troque por título de marca ou CTA discreto.
- `palavras na arte` / `passa de N palavras` -> encurte a linha (13 na família A, 20 na B).
- `Negative com termo que apaga a chamada` -> tire "captions", "overlay text", "letters",
  "words", "text" e "typography" soltos: aqui o texto é pedido.
- `Negative Prompt incompleto` -> use a BASE da capa inteira (versão 4.0) + o condicional
  da família.
- `familia` -> a linha Format precisa declarar `brand editorial` ou `lifestyle scrapbook`.

## Relatório final

Para cada produto: o nome, a família escolhida, o título da capa e do slide 2 (KIT ou
PRODUTO ÚNICO), o ângulo novo e a confirmação de
que o `check` terminou com `0 erros`. Sem imagem gerada. Lembre o usuário de rodar
`/prompt_gen_check`.
