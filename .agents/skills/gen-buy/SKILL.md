---
name: gen-buy
description: >-
  Use this skill when the user types "/start_gen_buy" or "start_gen_buy" to write the product cover prompt.
---

# Fluxo do Prompt de Capa (Antigravity)

Quando o usuário enviar `/start_gen_buy`, você escreve, para cada produto pendente, **um
arquivo de texto**:

- `<produto>/prompt_video/prompt_capa.md` — o prompt que gera a capa do produto

**Você NÃO gera imagem.** Este comando entrega o PROMPT; quem cola no gerador, com as fotos
do produto anexadas, é o usuário.

A capa é a **peça de divulgação** do produto: foto nova do mesmo objeto (nunca cópia da
imagem do anúncio), com **o produto de um lado** da vertical, inteiro e nítido, e **a
chamada em português do outro lado**, na área limpa.

O texto é curto: uma chamada da lista fechada (`COMPRE JÁ`, `COMPRE AGORA`,
`OFERTA IMPERDÍVEL`, `APROVEITE AGORA`, `GARANTA O SEU`), uma segunda chamada opcional e
uma descrição de até 6 palavras. No máximo 3 linhas e 12 palavras. **Preço nunca**: sem
"R$", sem número, sem porcentagem, sem selo de desconto.

É o último dos quatro comandos: `scraper.py` -> `/start_gen_prompts` -> `/start_gen_image`
-> `/start_gen_buy`.

## Passo 1 — Ver a fila

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A tabela cobre **todas as datas**: **dia nenhum pode ficar sem prompt**. Trabalhe em todo
produto com `sim` na coluna CENA e `FALTA` na coluna CAPA, inclusive de dias passados.

## Passo 2 — Carregar as regras

Leia o arquivo inteiro `/home/labs/.extra_income/prompt_gen_buy.yaml`: o que é a capa, as
regras absolutas, o `gabarito_prompt_capa`, o `negative_prompt_capa` e os dois exemplos.

## Passo 3 — Por produto

1. **Ler o `prompt_cena.md` inteiro** e abrir a `capa.jpg` e as secundárias.
2. **Copiar literalmente** os blocos `Subject` e `Label & Brand` do prompt da cena — palavra
   por palavra, sem reescrever. É o que garante que a capa e o vídeo mostrem o mesmo objeto.
3. **Mudar de propósito**: `Scene`, ângulo e enquadramento são **declaradamente diferentes**
   dos do vídeo e dos da foto do anúncio. Cenário real e vivo; fundo branco de catálogo,
   fundo liso e ciclorama estão proibidos.
4. **Escrever o texto da peça**: chamada da lista fechada, soletrada com hifens
   (`C-O-M-P-R-E J-Á`), e descrição curta em português tirada do que se vê nas fotos —
   sem superlativo, sem número, sem preço.
5. **Escrever o arquivo** seguindo o `gabarito_prompt_capa`: linha `Format` com
   `single still photograph`, `9:16` e `promotional cover shot`, linha `On camera` com o
   mesmo modo da cena + `No price, no numbers, no percentages`, e as seções `Subject`,
   `Label & Brand`, `Layout & Composition`, `Promo Copy`, `Text Style`, `Scene`,
   `Light & Mood`, `Textures to Highlight`, `Model & Hands`, `Product Fidelity`,
   `Originality` e `Negative Prompt`.
6. **Arquivo limpo:** só o prompt, pronto para colar.

## Passo 4 — Validar e corrigir (obrigatório)

```bash
cd /home/labs/.extra_income && python3 check_prompts.py check
```

- Corrija todo erro prefixado com `capa:` e rode de novo, até `0 erros`.
- `'Subject' diferente do da cena` -> copie e cole, não reescreva.
- `'Scene' identica a da cena` -> a capa é outro recorte do ambiente, não o mesmo quadro.
- `a capa pede 'white background'` -> troque por um cenário real.
- `chamada ... fora da lista fechada` / `palavras na arte` -> encurte e use a lista.
- `Negative com termo que apaga a chamada` -> tire "captions", "overlay text", "letters",
  "words", "text" e "typography" soltos: aqui o texto é pedido.

## Relatório final

Para cada produto: o nome, o ângulo novo escolhido, quais fotos anexar no gerador e a
confirmação de que o `check` terminou com `0 erros`. Sem imagem gerada.
