---
name: gen-check
description: >-
  Use this skill when the user types "/prompt_gen_check" or "prompt_gen_check" to review and fix the generated prompts of each product.
---

# Fluxo de Revisão dos Prompts (Antigravity)

Quando o usuário enviar `/prompt_gen_check`, você atua como **diretor de criação e
controle de qualidade**: revisa os três prompts de cada produto — `prompt_cena.md`,
`prompt_storyboard.md` e `prompt_capa.md` —, corrige o que estiver errado **nos próprios
arquivos** e grava um relatório curto:

- `<produto>/prompt_video/revisao.md` — veredito, riscos por beat, ajustes feitos, pendências

É o último comando do fluxo: `scraper.py` -> `/start_gen_prompts` -> `/start_gen_image` ->
`/start_gen_buy` -> `/prompt_gen_check`.

O `check_prompts.py` confere a **forma** (seções, beats, negative). Este comando confere o
que script nenhum confere: se o vídeo vai sair **sem deformação**, se o roteiro **faz
sentido**, se há **contradição** entre blocos ou entre arquivos, se a peça **vende** e se o
**português** da capa está certo.

## Passo 1 — Ver a fila

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status --ultima
```

Revise todo produto da data mais recente com CENA, STORY e CAPA = `sim`. Produto com
arquivo faltando não entra: aponte no relatório qual comando falta rodar. Se o usuário
indicar outra data ou um produto específico, revise só esses.

## Passo 2 — Carregar as regras

Leia **inteiros**:

1. `/home/labs/.extra_income/prompt_gen_check.yaml` — as seis auditorias, a política de
   correção e o formato do `revisao.md`;
2. `/home/labs/.extra_income/prompt_sistema.yaml` — principalmente
   `como_o_flow_usa_este_arquivo`, `escada_de_risco_da_acao`, `R16_FISICA_E_ENCENACAO` e o
   `negative_prompt`;
3. `/home/labs/.extra_income/prompt_gen_image.yaml` e
   `/home/labs/.extra_income/prompt_gen_buy.yaml`.

## Passo 3 — Por produto

1. **Abrir as fotos** (`capa.jpg` e todas as `imagem_N.jpg`), o `metadata.json` e os quatro
   arquivos de `prompt_video/`.
2. **Rodar as seis auditorias** do `prompt_gen_check.yaml`, na ordem: grounding,
   deformação beat a beat, contradições, força comercial, português e forma.
3. **Corrigir cirurgicamente** cada problema, propagando cena -> storyboard -> capa.
   Nunca corrija tirando a ação: troque por uma ação mais segura que prove o mesmo
   benefício.
4. **Gravar `revisao.md`** no formato `formato_da_revisao`.

## Passo 4 — Validar (obrigatório)

```bash
cd /home/labs/.extra_income && python3 check_prompts.py check --ultima
```

Repita correção + check até `0 erros`. Zero erros é necessário, não suficiente: a peça
só está aprovada quando as seis auditorias passaram.

## Regras de lote

- **Autonomia:** não peça confirmação produto a produto. Revise tudo e só então reporte.
- **Paralelismo:** com mais de ~6 produtos, distribua em lotes com `invoke_subagent`,
  passando o caminho dos quatro YAMLs; cada subagente lê as regras por conta própria.
- **Conferência:** no fim, todo produto revisado tem `revisao.md`.

## Relatório final

Tabela produto | veredito | risco do vídeo | nº de ajustes, seguida das **pendências para o
usuário** (conflitos que só o usuário decide) e da linha final do `check` com `0 erros`.
