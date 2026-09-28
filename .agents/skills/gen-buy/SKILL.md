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

A capa é a **arte de divulgação para Instagram**, vertical **4:5**, pronta para postar em
qualquer rede: foto nova do mesmo objeto (nunca cópia da imagem do anúncio), com cara de
peça criada pela direção de arte de uma **marca real** — elegante, limpa, humana — e nunca
de imagem genérica de IA, panfleto ou template. O produto é o protagonista, em destaque,
inteiro, nítido e assentado no cenário com sombra natural; o texto fica na área limpa.

O texto são **exatamente 3 linhas**: um **título** curto com cara de marca (até 4
palavras), uma **frase de benefício** (até 6) e um **CTA discreto** (até 3, ex.:
`Confira no link`). **Proibido** chamada apelativa (`COMPRE JÁ`, `GARANTA O SEU`,
`premium`, `exclusivo`, `feito para durar`…), selo, botão, ícone e dourado exagerado.
**Preço nunca**: sem "R$", sem número, sem porcentagem, sem selo de desconto.

É o último dos quatro comandos: `scraper.py` -> `/start_gen_prompts` -> `/start_gen_image`
-> `/start_gen_buy`.

## Passo 1 — Ver a fila

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A tabela cobre **todas as datas**: **dia nenhum pode ficar sem prompt**. Trabalhe em todo
produto com `sim` na coluna CENA e `FALTA` na coluna CAPA, inclusive de dias passados.

## Passo 2 — Carregar as regras

Leia o arquivo inteiro `/home/labs/.extra_income/prompt_gen_buy.yaml`: o que é a capa, o
texto da peça, as regras absolutas, o `gabarito_prompt_capa`, o `negative_prompt_capa` e os
dois exemplos.

## Passo 3 — Por produto

1. **Ler o `prompt_cena.md` inteiro** e abrir a `capa.jpg` e as secundárias.
2. **Copiar literalmente** os blocos `Subject` e `Label & Brand` do prompt da cena — palavra
   por palavra, sem reescrever. É o que garante que a capa e o vídeo mostrem o mesmo objeto.
3. **Mudar de propósito**: `Scene`, ângulo e enquadramento são **declaradamente diferentes**
   dos do vídeo e dos da foto do anúncio. Fundo contextual do nicho do produto, com um ou
   dois elementos de apoio; fundo branco de catálogo, fundo liso e ciclorama estão
   proibidos.
4. **Escrever o texto da peça**: título de marca soletrado com hifens (`C-O-R Q-U-E F-I-C-A`),
   frase de benefício tirada do que se vê nas fotos e CTA discreto — sem chamada apelativa,
   sem superlativo, sem número, sem preço.
5. **Escrever o arquivo** seguindo o `gabarito_prompt_capa`: linha `Format` com
   `single still photograph`, `4:5` e `promotional cover shot`, linha `On camera` com o
   mesmo modo da cena + `No price, no numbers, no percentages`, e as seções
   `Art Direction`, `Subject`,
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
- `chamada apelativa` -> troque por título de marca ou CTA discreto.
- `palavras na arte` / `passa de N palavras` -> encurte a linha.
- `Negative com termo que apaga a chamada` -> tire "captions", "overlay text", "letters",
  "words", "text" e "typography" soltos: aqui o texto é pedido.
- `Negative Prompt incompleto` -> use a BASE da capa inteira, ela mudou na versão 3.0.

## Relatório final

Para cada produto: o nome, o ângulo novo escolhido, quais fotos anexar no gerador e a
confirmação de que o `check` terminou com `0 erros`. Sem imagem gerada.
