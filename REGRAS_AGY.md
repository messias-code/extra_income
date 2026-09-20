# Regras do Projeto (Extra Income)

Este projeto prepara a matéria-prima para gerar vídeos de IA de produtos do TikTok Shop.
O fluxo tem três etapas, nesta ordem:

| Etapa | Onde roda | O que faz | Saída |
|---|---|---|---|
| 1. Raspagem | terminal: `python scraper.py` | junta 10 produtos inéditos da Kalodata, de várias listas | `produtos/<AAAA-MM-DD>/<NN produto>/` com `capa.jpg`, `imagem_N.jpg` e `metadata.json` |
| 2. Prompts | Antigravity: `/start_gen_prompts` | escreve os dois prompts de vídeo de 10s (o 2º é continuação do 1º no Google Flow) e o prompt da foto de post | `prompt_video/prompt_cena1.md` + `prompt_cena2.md` + `prompt_imagem.md` + `raciocinio.md` |
| 3. Storyboards | Antigravity: `/start_gen_image` | gera a prancha-guia de 6 painéis numerados (1 por beat do roteiro) | `prompt_video/storyboard.jpg` |

## Arquivos que mandam no comportamento

- `prompt_sistema.yaml` — regras do Engenheiro de Prompts (etapa 2). Fonte única da verdade:
  regras absolutas, presets de categoria, pares de planos, ritmo, negative prompt e gabarito.
- `prompt_gen_image.yaml` — regras do Diretor de Arte (etapa 3).
- `.agents/skills/gen-prompts/SKILL.md` e `.agents/skills/gen-images/SKILL.md` — como executar
  cada comando dentro do Antigravity.
- `check_prompts.py` — utilitário de conferência:
  - `python check_prompts.py status` → o que já existe e o que falta em cada produto
  - `python check_prompts.py check`  → valida os três prompts (e a costura entre eles) contra o `checklist_final`
- `gen_storyboards.py` — plano B da etapa 3 (mesma prancha de 6 painéis), para quando a cota
  de imagem do Antigravity
  estourar (erro 429). Usa a `GEMINI_API_KEY` do `.env`, gera só o que falta, em fila e com
  backoff: `python gen_storyboards.py --dry-run` para conferir, sem `--dry-run` para gerar.

## Regras fixas

- **A API do Gemini não é mais usada.** Quem escreve os prompts é você (Antigravity),
  lendo as imagens reais do produto.
- Nunca invoque o `scraper.py` a partir de um comando do Antigravity: o usuário roda na mão.
- Todo prompt de vídeo é **um clipe de 10s**, vertical 9:16, **sem nenhum texto na tela** e
  **sem nenhuma voz**. São dois por produto: o clipe 2 é continuação exata do clipe 1.
- A foto de post (`prompt_imagem.md`) mantém o produto idêntico ao das fotos reais e muda
  ângulo, cenário e pessoa em quadro — é uma foto nova, não uma cópia da imagem do anúncio.
- Nunca invente marca, material, número ou spec que não esteja nas imagens ou no nome do produto.
- `/start_gen_prompts` só termina quando `python check_prompts.py check` retorna **0 erros**.
