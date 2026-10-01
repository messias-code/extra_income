---
name: gen-all
description: >-
  Use this skill when the user types "/start_gen_all" or asks to run all prompt commands in order.
---

# Fluxo de Geração Completo

Quando o usuário rodar `/start_gen_all`, você é o responsável por executar a esteira inteira de uma vez. Siga a ordem estrita sem pedir permissão:

## Passo 1 — Cena (gen-prompts)
Leia `.agents/skills/gen-prompts/SKILL.md`.
Processe todos os produtos que ainda não tenham `prompt_cena.md` e valide com `check_prompts.py check`.

## Passo 2 — Storyboard (gen-images)
Quando a etapa de cena estiver finalizada (0 erros), leia `.agents/skills/gen-images/SKILL.md`.
Processe os produtos que ainda não tenham `prompt_storyboard.md` e valide com `check_prompts.py check`.

## Passo 3 — Capas (gen-buy)
Quando a etapa de storyboard estiver finalizada (0 erros), leia `.agents/skills/gen-buy/SKILL.md`.
Processe os produtos que ainda não tenham o prompt da capa e valide.

## Passo 4 — Revisão (gen-check)
Finalmente, leia `.agents/skills/gen-check/SKILL.md` para corrigir quaisquer gargalos ou problemas finais identificados no conjunto completo.

## Regra de Ouro
1. **NUNCA** pare a execução para solicitar aprovação. **NUNCA** use "RequestFeedback: true" na geração de artefatos. Considere a resposta do usuário "sempre sim".
2. Não pule etapas.

## Passo 5 — Disparo no Google Flow
Quando a etapa 4 finalizar com 0 erros, você **deve disparar a geração no Flow** para o dia mais recente.
Rode o script em bash:
```bash
python3 flow_video.py
```
Esse comando cuida sozinho de subir tudo (capa, prancha de storyboard e vídeo) no Google Flow para os produtos extraídos.
