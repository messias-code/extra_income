---
name: gen-images
description: >-
  Use this skill when the user types "/start_gen_image" or "start_gen_image" to create storyboard images based on the generated video prompts.
---

# Fluxo de Geração de Storyboards (Antigravity)

Quando o usuário enviar `/start_gen_image`, você atua como **Diretor de Arte** e gera, para cada
produto que já tem roteiro, UMA prancha de storyboard de **6 painéis numerados** salva em
`<produto>/prompt_video/storyboard.jpg`.

Seis painéis porque os dois prompts trazem **3 beats cronometrados cada** (0-2s, 2-7s, 7-10s no
`prompt_cena1.md` e 0-2s, 2-8s, 8-10s no `prompt_cena2.md` — o tempo é local, cada clipe começa
em 0s). Um painel por beat mostra a ação caminhando inteira, não só onde começa e onde termina.

## Passo 1 — Ver o lote

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

Trabalhe apenas nos produtos com `PROMPT = sim` e `STORY = FALTA`.
Produto sem os dois prompts é ignorado (rode `/start_gen_prompts` antes).

## Passo 2 — Carregar as regras

Leia **o arquivo inteiro** `/home/labs/.extra_income/prompt_gen_image.yaml` com `view_file`:
layout dos 2 painéis, regra de fidelidade ao produto, bloco negativo e o exemplo pronto.

## Passo 3 — Por produto

1. **Ler o roteiro:** `view_file` em `prompt_video/prompt_cena1.md` e em
   `prompt_video/prompt_cena2.md` (os blocos compartilhados são idênticos nos dois).
   Extraia: `Scene` (ambiente e props), `Style & Lighting` (luz e paleta), `Subject`
   (forma, variante de cor, acabamento), o `VISUAL` de cada clipe, o modo da linha `On camera`
   e — o mais importante — **os 6 beats das linhas `ACTION` dos dois arquivos** (3 + 3), que
   viram os 6 painéis. O painel 4 é o `START FRAME` do clipe 2, ou seja, o mesmo quadro do
   painel 3 alguns instantes depois: ele continua o movimento, não recomeça a cena.
2. **Selecionar referências:** até 3 caminhos absolutos das imagens do produto,
   **`capa.jpg` sempre em primeiro**, depois as 2 secundárias mais nítidas.
   Nunca use infográfico/banner como referência.
3. **Montar o prompt de imagem** exatamente no formato de `formato_do_prompt_de_imagem`:
   6 painéis em 2 colunas x 3 linhas, um por beat (`mapa_dos_paineis`), numerais 1 a 6 no canto
   de cada painel e nenhum outro texto, progressão de enquadramento entre eles
   (`progressao_de_enquadramento`), mesma luz e mesma variante nos seis, bloco de fidelidade às
   referências, bloco `Style:` e bloco `Negative:` — este **sem** a palavra "numbers", senão o
   modelo apaga a numeração. Entre 180 e 300 palavras. **Não cole os prompts de vídeo.**
   O produto fica centralizado em cada painel: assim qualquer painel continua legível quando
   você recortar para 9:16 na hora de usar como referência de vídeo.
4. **Gerar:** chame `generate_image` com o prompt montado, `AspectRatio: "9:16"`
   (mesmo formato do vídeo), os caminhos absolutos em `ImagePaths` e `ImageName: "storyboard"`.
5. **Salvar na pasta do produto:** a ferramenta grava na pasta de artefatos. Use `run_command`
   para copiar para o destino final e **confirme que o arquivo chegou inteiro**:

   ```bash
   cp "<caminho_do_artefato>" "<pasta_do_produto>/prompt_video/storyboard.jpg" && \
   ls -l "<pasta_do_produto>/prompt_video/storyboard.jpg"
   ```

   Arquivo ausente ou com menos de ~10 KB = cópia falhou: refaça.
   (Storyboard que fica só na pasta de artefatos é storyboard perdido: já aconteceu no lote anterior.)
6. **Conferir a imagem gerada.** Abra o `storyboard.jpg` e verifique:
   seis painéis preenchidos, em 2 colunas x 3 linhas; numerais 1 a 6 legíveis; nenhum painel
   repetido (cada um avança a ação); produto igual ao das fotos de referência em todos;
   mesma luz em todos; nenhum rosto; **nenhuma letra ou legenda além dos numerais**.
   Falhou em algum ponto → regere reforçando o item que falhou.

## Passo 4 — Conferir o lote

```bash
cd /home/labs/.extra_income && python3 check_prompts.py status
```

A coluna `STORY` precisa estar `sim` em todos os produtos que tinham os dois prompts.

## Regras de lote

- **Geração Interna Exclusiva:** A partir de agora, **VOCÊ (Antigravity) é o único responsável** por gerar as imagens. Não delegue para scripts externos (como `gen_storyboards.py`).
- **Lotes Controlados:** Para não esbarrar em limites, chame a ferramenta interna `generate_image` em pequenos lotes (ex: 3 produtos de cada vez simultaneamente). Espere o lote terminar, copie as imagens geradas para as respectivas pastas usando `cp`, e em seguida inicie o próximo lote.
- **Autonomia:** Processe a fila inteira de 10 produtos de forma ininterrupta, informando o usuário sobre o andamento dos lotes. 
- **Relatório final:** Após gerar todos, rode `python3 check_prompts.py status` para confirmar se a coluna `STORY` está preenchida (`sim`) em todos os 10 produtos. Só declare sucesso final se o script atestar `0 sem storyboard.jpg`.
