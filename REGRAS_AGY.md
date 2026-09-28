# Regras do Projeto (Extra Income)

Este projeto prepara a matéria-prima para gerar vídeos de IA de produtos do TikTok Shop.
**Tudo o que o pipeline entrega é PROMPT.** Nenhum comando gera imagem ou vídeo: o usuário
cola os prompts no Google Flow / no gerador de imagens, com as fotos do produto anexadas.

O fluxo tem quatro etapas, nesta ordem:

| Etapa | Onde roda | O que faz | Saída |
|---|---|---|---|
| 1. Raspagem | terminal: `python scraper.py` | junta 10 produtos inéditos da Kalodata, de várias listas | `produtos/<AAAA-MM-DD>/<NN produto>/` com `capa.jpg`, `imagem_N.jpg` e `metadata.json` |
| 2. Cena | Antigravity: `/start_gen_prompts` | escreve o prompt de **um** clipe de 10s em 6 beats cronometrados | `prompt_video/prompt_cena.md` + `raciocinio.md` |
| 3. Storyboard | Antigravity: `/start_gen_image` | escreve o **prompt** da prancha de 6 painéis (1 por beat) | `prompt_video/prompt_storyboard.md` |
| 4. Capa | Antigravity: `/start_gen_buy` | escreve o **prompt** da capa do produto | `prompt_video/prompt_capa.md` |

No Google Flow, o usuário joga a prancha do storyboard **junto** com o `prompt_cena.md`:
a prancha é o mapa da encenação, o prompt é a direção.

## Arquivos que mandam no comportamento

- `prompt_sistema.yaml` — regras do Engenheiro de Prompts (etapa 2). Fonte única da verdade:
  regras absolutas R1–R14, presets de categoria, arcos de câmera, ritmo dos seis beats,
  negative prompt e gabarito.
- `prompt_gen_image.yaml` — regras do Diretor de Arte (etapa 3).
- `prompt_gen_buy.yaml` — regras da capa (etapa 4).
- `.agents/skills/gen-prompts|gen-images|gen-buy/SKILL.md` — como executar cada comando
  dentro do Antigravity.
- `check_prompts.py` — utilitário de conferência, cobrindo **todas as datas**:
  - `python check_prompts.py status` → o que já existe e o que falta em cada produto
  - `python check_prompts.py check`  → valida os três prompts e a costura entre eles

## Regras fixas

- **A API do Gemini não é mais usada.** Quem escreve os prompts é você (Antigravity),
  lendo as imagens reais do produto.
- Nunca invoque o `scraper.py` a partir de um comando do Antigravity: o usuário roda na mão.
- **Dia nenhum fica sem prompt.** A fila é o histórico inteiro de `produtos/`, não só o dia
  de hoje: produto antigo com arquivo faltando volta para a fila e é gerado de novo.
- O vídeo é **um clipe de 10s**, vertical 9:16, **sem nenhum texto na tela** e **sem nenhuma
  voz**. Não existe clipe 2, não existe continuação.
- A `ACTION` traz **6 beats** na grade fixa `0-1.5s / 1.5-3s / 3-5s / 5-7s / 7-8.5s /
  8.5-10s`, e cada beat vira um painel do storyboard.
- Cada beat é um **evento físico** com o enquadramento entre parênteses. Movimento de câmera
  não é evento: produto parado com a câmera girando em volta está proibido (R9/R13).
- O produto é travado pelo **token** do bloco `Product Lock` (cor + forma + tipo + marca),
  repetido literalmente em todos os beats, na linha VISUAL e nos seis painéis do storyboard.
  É o que impede a cor e o nome da marca de mudarem no meio do clipe (R14).
- A capa (`prompt_capa.md`) é a arte de divulgação para Instagram, vertical **4:5**, com
  cara de peça de marca real e nunca de panfleto ou template: título curto de marca, frase
  de benefício e CTA discreto (3 linhas, até 13 palavras), **sem chamada apelativa, sem
  preço, sem número e sem porcentagem**. O produto é o mesmo das fotos reais; ângulo,
  cenário e composição mudam.
- Nunca invente marca, material, número ou spec que não esteja nas imagens ou no nome do
  produto.
- Cada comando só termina quando `python check_prompts.py check` retorna **0 erros**.
