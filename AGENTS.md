# Regras do Projeto (Extra Income) — Carregamento Automático Antigravity

Este projeto prepara a matéria-prima para gerar vídeos de IA de produtos do TikTok Shop.
**A etapa de IA entrega os PROMPTS** e o script `flow_video.py` automatiza o envio e a geração no Google Flow.

## Mapeamento Obrigatório de Skills e Comandos no Antigravity

Sempre que o usuário digitar um dos comandos abaixo (com ou sem `/` na frente) ou pedir para executar a etapa correspondente, você **DEVE ler imediatamente o arquivo `SKILL.md` correspondente** antes de agir:

| Comando no Chat (`agy`) | Skill para Carregar (`read_file`) | O que faz | Saída |
|---|---|---|---|
| `start_gen_all` ou `/start_gen_all` | `.agents/skills/gen-all/SKILL.md` | Roda toda a esteira em sequência (Cena -> Storyboard -> Capa -> Revisão -> `flow_video.py`) | Todos os prompts + geração no Flow |
| `start_gen_prompts` ou `/start_gen_prompts` | `.agents/skills/gen-prompts/SKILL.md` | Escreve o prompt de **um** clipe de 8s (Veo 3.1 - Quality) em 6 beats cronometrados | `prompt_video/prompt_cena.md` + `raciocinio.md` |
| `start_gen_image` ou `/start_gen_image` | `.agents/skills/gen-images/SKILL.md` | Escreve o **prompt** da prancha de 6 painéis (1 por beat) | `prompt_video/prompt_storyboard.md` |
| `start_gen_buy` ou `/start_gen_buy` | `.agents/skills/gen-buy/SKILL.md` | Escreve os **prompts** do carrossel 4:5 (capa + slide 2, gerados em 3:4) | `prompt_video/prompt_capa.md` + `prompt_capa_2.md` |
| `prompt_gen_check` ou `/prompt_gen_check` | `.agents/skills/gen-check/SKILL.md` | Audita e corrige os prompts (grounding, deformação, contradição, venda, português) | prompts corrigidos + `prompt_video/revisao.md` |

## Fluxo Completo (Ordem de Execução)

| Etapa | Onde roda | Comando | O que faz |
|---|---|---|---|
| 1. Raspagem | Terminal | `python3 scraper.py` | Junta 10 produtos inéditos da Kalodata em `produtos/<AAAA-MM-DD>/<NN produto>/` |
| 2. Cena | Antigravity (`agy`) | `start_gen_prompts` | Cria `prompt_cena.md` e `raciocinio.md` |
| 3. Storyboard | Antigravity (`agy`) | `start_gen_image` | Cria `prompt_storyboard.md` |
| 4. Capa | Antigravity (`agy`) | `start_gen_buy` | Cria `prompt_capa.md` e `prompt_capa_2.md` |
| 5. Revisão | Antigravity (`agy`) | `prompt_gen_check` | Audita tudo, corrige os prompts e cria `revisao.md` |
| 6. Geração Flow | Terminal | `python3 flow_video.py` | Sobe as fotos e gera storyboard, capas e vídeo no Google Flow |

*(Dica: As etapas 2 a 6 podem ser executadas de uma só vez no Antigravity com `start_gen_all`).*

No Google Flow, o vídeo recebe **só a prancha do storyboard** como ingrediente, junto com o `prompt_cena.md`: a prancha é o mapa da encenação e a única cópia visual do produto que o Veo vê; o prompt é a direção.

## Arquivos que mandam no comportamento

- `prompt_sistema.yaml` — regras do Engenheiro de Prompts (etapa 2). Fonte única da verdade: regras absolutas R1–R16, escada de risco da ação, presets de categoria, arcos de câmera, ritmo dos seis beats, negative prompt e gabarito.
- `prompt_gen_image.yaml` — regras do Diretor de Arte (etapa 3).
- `prompt_gen_buy.yaml` — regras da capa e slide 2 (etapa 4).
- `prompt_gen_check.yaml` — as seis auditorias da revisão (etapa 5).
- `.agents/skills/gen-all|gen-prompts|gen-images|gen-buy|gen-check/SKILL.md` — instruções passo a passo de cada skill.
- `check_prompts.py` — utilitário de conferência, cobrindo **todas as datas**:
  - `python3 check_prompts.py status` → o que já existe e o que falta em cada produto
  - `python3 check_prompts.py check`  → valida os prompts e a costura entre eles

## Regras fixas

- **A API do Gemini não é mais usada via script.** Quem escreve os prompts é você (Antigravity), lendo as imagens reais do produto.
- Nunca invoque o `scraper.py` a partir de um comando do Antigravity: o usuário roda no terminal com a própria conta.
- **Dia nenhum fica sem prompt.** A fila é o histórico inteiro de `produtos/`, não só o dia de hoje: produto antigo com arquivo faltando volta para a fila e é gerado de novo.
- O vídeo é **um clipe de 8s**, vertical 9:16, em tempo real (sem câmera lenta), **sem nenhum texto na tela** e **sem nenhuma voz**. Não existe clipe 2, não existe continuação.
- A `ACTION` traz **6 beats** na grade fixa `0-1.5s / 1.5-3s / 3-4.5s / 4.5-6s / 6-7s / 7-8s`, e cada beat vira um painel do storyboard.
- Toda ação passa pela **escada de risco**: N1 seguro, N2 com encenação (no máximo uma por clipe, com `Physics & Staging` completo), N3 proibido.
- Cada beat é um **evento físico** com o enquadramento entre parênteses. Movimento de câmera não é evento: produto parado com a câmera girando em volta está proibido (R9/R13).
- O produto é travado pelo **token** do bloco `Product Lock` (cor + forma + tipo + marca), repetido literalmente em todos os beats, na linha VISUAL e nos seis painéis do storyboard. É o que impede a cor e o nome da marca de mudarem no meio do clipe (R14).
- A capa (`prompt_capa.md`) é o post de feed do Instagram (4:5, gerado em tela 3:4 porque o Flow não tem 4:5), com produto e texto no centro, em uma de duas famílias: **brand editorial** (3 linhas, até 13 palavras) ou **lifestyle scrapbook** (3 linhas + até 3 callouts, até 20 palavras). **Sem chamada apelativa, sem preço, sem número e sem porcentagem** no texto da arte. O produto é o mesmo das fotos reais; ângulo, cenário e composição mudam.
- O slide 2 (`prompt_capa_2.md`) fecha o carrossel: produto com várias peças mostra o kit inteiro em knolling (cada peça uma vez, sem mãos); produto único mostra o detalhe que prova o benefício.
- Resultado real avaliado pelo usuário manda mais que qualquer preset: siga `aprendizados_de_campo` no `prompt_sistema.yaml` (ex.: ferramenta de cabelo elétrica é unboxing, sem cabelo em quadro).
- Slash commands do Flow (`/goldenhour`, `/orbit`…) não são recurso oficial: a direção vai escrita em frase.
- Nunca invente marca, material, número ou spec que não esteja nas imagens ou no nome do produto.
- Cada comando só termina quando `python3 check_prompts.py check` retorna **0 erros**. Prompts antigos de 10s aparecem como `[LEGADO]` e ficam fora da validação.
