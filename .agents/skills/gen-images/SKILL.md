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
e não copia artefato. Ele entrega o PROMPT; quem cola no gerador, com as fotos do produto
anexadas, é o usuário.

A prancha tem 6 painéis porque o `prompt_cena.md` tem 6 beats cronometrados. Um painel por
beat, na ordem, com o mesmo enquadramento que está entre parênteses no beat. A prancha é
jogada no Google Flow junto com o prompt da cena: ela é o mapa do vídeo.

## Passo 1 — Ver a fila

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A tabela cobre **todas as datas**: **dia nenhum pode ficar sem prompt**. Trabalhe em todo
produto com `sim` na coluna CENA e `FALTA` na coluna STORY, inclusive de dias passados.
Produto sem `prompt_cena.md` ainda não é seu — ele precisa de `/start_gen_prompts` antes.

## Passo 2 — Carregar as regras

Leia o arquivo inteiro `/home/labs/.extra_income/prompt_gen_image.yaml`: layout, mapa dos
painéis, regras R1 a R10, o `formato_do_prompt_de_storyboard` e o exemplo. Não escreva nada
antes de ter lido o formato e o bloco Negative.

## Passo 3 — Por produto

1. **Ler o `prompt_cena.md` inteiro.** Dele saem: os 6 beats com os tempos e os
   enquadramentos, o `Scene`, o `Style & Lighting`, o modo de câmera da linha `On camera`,
   o `Label & Brand` e, principalmente, o **token do bloco `Product Lock`**.
2. **Copiar o token** (ex.: "wine-red LUMINE glass tube") e usá-lo nos **seis** painéis,
   literalmente. É essa repetição que impede a cor e o nome da marca de mudarem de painel
   para painel — e, depois, de segundo para segundo no vídeo.
3. **Traduzir cada beat em uma frase visual** de até 20 palavras: o que está acontecendo +
   o elemento em foco, no **mesmo plano** declarado entre parênteses no beat. Nunca cole o
   prompt de vídeo dentro do prompt de imagem.
4. **Escrever o arquivo** seguindo `formato_do_prompt_de_storyboard`: cabeçalho da prancha,
   PANEL 1 a PANEL 6 com os rótulos de tempo, a linha "All six panels", o bloco de
   fidelidade às fotos, a linha Style com `vertical 9:16` e o bloco Negative.
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

## Relatório final

Para cada produto: o nome, **quais fotos anexar** no gerador (`capa.jpg` primeiro, depois as
2 secundárias mais nítidas) e a confirmação de que o `check` terminou com `0 erros`.
Sem imagem gerada, sem arquivo `.jpg` criado.
