# Extra Income - Automação de Vídeos UGC (TikTok Shop)

Este projeto automatiza a pesquisa de produtos em alta no TikTok Shop e a roteirização de vídeos curtos de vendas (UGC) utilizando a inteligência artificial do **Antigravity (AGY)** para criar prompts perfeitos para geradores de vídeo de última geração (hoje o **Veo 3.1 - Quality** no Google Flow).

O objetivo final é simples: no fim da rotina você tem, para cada produto, **as imagens do anúncio + quatro prompts prontos e revisados**: a cena do vídeo, a prancha de storyboard e as duas imagens do carrossel (capa e slide 2). Daí é só levar para o Google Flow (o `flow_video.py` automatiza isso), jogar as imagens e colar o prompt.

**O pipeline só produz texto.** Nenhum comando gera imagem ou vídeo: tudo o que fazemos é criar prompts bons, que entregam ótimos resultados no gerador.

## 🚀 O Fluxo de Trabalho (Ordem de Execução)

A rotina é composta de seis passos, executados em sequência. E **dia nenhum fica sem prompt**: a fila é o histórico inteiro de `produtos/`, então produto de dia passado que ficou sem algum arquivo volta para a fila e é gerado de novo.

### 1. Extração dos Produtos
**Comando no Terminal:**
```bash
python3 scraper.py
```
**O que faz:**
Usa o Playwright (modo Stealth) para fazer login na plataforma Kalodata e varrer as listas de produtos em alta (Sales Growth Rapidly).
**Resultado:** `produtos/<AAAA-MM-DD>/` com as pastas dos 10 produtos, suas fotos e o `metadata.json` de cada um.

#### 🎯 A meta: 10 produtos inéditos por dia

A constante `META_DIARIA = 10` no `scraper.py` define a regra do jogo: terminar o dia com **10 produtos novos**. O funil de vídeos precisa de 10 boas oportunidades todos os dias, e o script só para quando chega lá (ou quando as contas acabam).

**Passo a passo do que o código faz:**

**1) Leitura do histórico (`extracted_products.txt`)**
Antes de começar, o script carrega o arquivo de histórico com todos os títulos já baixados — em qualquer dia e em qualquer lista. A deduplicação é **global de propósito**: o mesmo produto aparece na lista geral e nas faixas de comissão, e o funil só quer ele uma vez.

**2) Conta o que o dia já tem**
Se `produtos/<hoje>/` já tiver 4 pastas de uma rodada anterior, a meta da rodada vira 6. A meta é **do dia**, não da execução — rodar o script duas vezes no mesmo dia não gera 20 produtos.

**3) Cascata de fontes**
A conta *Prova* só enxerga a **página 1** (10 linhas) de cada busca. Para chegar aos 10 inéditos, o script varia a **busca**, não a página: cada faixa de comissão devolve outras 10 linhas. A lista `FONTES` define a ordem de preferência:

| # | Fonte | Filtro aplicado |
|---|---|---|
| 1 | Top 10 geral | nenhum |
| 2 | Comissão 15-20 | `15% ~ 20%` |
| 3 | Comissão 20-30 | `20% ~ 30%` |
| 4 | Comissão acima de 30 | `>30%` |
| 5 | Comissão 10-15 | `10% ~ 15%` |
| 6 | Comissão abaixo de 10 | `<10%` |

Primeiro o top 10 absoluto do dia; depois as comissões mais gordas, que é onde está a margem. Em cada fonte o script desce linha por linha: título inédito → entra na página, baixa as imagens, grava o `metadata.json` e conta +1; título repetido → pula. **Assim que a meta é atingida, ele para no meio da lista** e nem abre a próxima fonte.

Entre uma fonte e outra a página é **recarregada** (`page.goto`) antes de aplicar o novo filtro. Isso é de propósito: sem recarregar, o filtro anterior poderia continuar somado ao novo e a busca devolveria a interseção em vez da faixa pedida.

**4) Troca de conta sem perder o progresso**
`run_scraper()` devolve **quantos produtos conseguiu** e nunca deixa exceção vazar. Se a conta 1 travar no limite depois de 6 produtos, o `main()` soma esses 6 e chama a conta 2 pedindo só os **4 que faltam**. O teto real do dia é `nº de contas × 10 visitas`.

> ⚠️ **Paginação existe, mas é paga.** Os botões de página estão no DOM (`button[data-slot="pagination-link"]`, com "1 2 3 … 155144"), mas clicar na página 2 não faz nada: a conta *Prova* recebe *"Membership Required — Upgrade to Professional or above to view the data"*. Por isso a estratégia é trocar de busca, não de página.

#### 📋 Exemplo prático

Meta do dia = 10 produtos. Histórico já tem bastante coisa.

**Conta 1 — Fonte "Top 10 geral":**

| Linha | Produto | Situação | Total |
|---|---|---|---|
| 1 | Perfume X | Novo ✅ | 1 |
| 2 | Fone de Ouvido Y | Já no histórico ❌ | — |
| 3 | Relógio Z | Novo ✅ | 2 |
| 4 | Microfone W | Já no histórico ❌ | — |
| 5 | Creme de Rosto | Novo ✅ | 3 |
| 6–10 | … | todos já no histórico ❌ | — |

> Fonte esgotada com 3 produtos. **Faltam 7.** O script recarrega a página e aplica o filtro `15% ~ 20%`.

**Conta 1 — Fonte "Comissão 15-20":**

| Linha | Produto | Situação | Total |
|---|---|---|---|
| 1 | Fone Bluetooth | Já no histórico ❌ | — |
| 2 | Mouse Gamer | Novo ✅ | 4 |
| 3 | Teclado | Novo ✅ | 5 |
| … | … | … | … |
| 9 | Luminária | Novo ✅ | 10 |

> Meta atingida na linha 9. O script **não olha a linha 10**, não abre as fontes 3 a 6, não chama a conta 2, salva tudo e encerra.

Se em vez disso a conta 1 tivesse travado no limite de visitas com 6 produtos, o `main()` abriria a conta 2 pedindo 4 — e a numeração das pastas continuaria em `07`, `08`, `09`, `10`.

#### 🚧 Os dois limites da conta *Prova*

| Limite | Quanto | Como o script lida |
|---|---|---|
| Visitas à página de detalhe | 10 por dia | `LimitReachedException` (timeout ao carregar a imagem) → troca de conta |
| Buscas (cada `Enviar` de filtro) | 10 por dia | as 5 faixas de comissão gastam no máximo 5 |
| Linhas por busca | 10 (página 1) | contornado variando a busca |

Com 2 contas no `KALODATA_LOGINS`, o orçamento do dia é de **20 visitas** para uma meta de 10 — folga de 2×.

**Quando o dia fecha com menos de 10:** acontece se todas as 6 fontes já estiverem cobertas pelo histórico. O script avisa no final (`[!] Fim das contas com N de 10`) em vez de mentir "sucesso". Nesse caso as saídas são: assinar um plano que libere a paginação, adicionar outra tabela da Kalodata como fonte, ou aceitar menos produtos no dia.

#### 🛡️ O modal que bloqueia tudo

A Kalodata abre um modal *"Dicas de segurança da conta"* por cima da tabela alguns segundos **depois** do carregamento. Ele não tem botão de fechar (só sai com **Escape**) e sua máscara intercepta todos os cliques — inclusive o clique na linha do produto, que é como o scraper abre cada página.

Por isso `fechar_modais()` é chamado em três pontos: ao carregar a tabela (aguardando o modal *surgir*), antes de aplicar o filtro de comissão, e antes de cada clique de linha — com uma nova tentativa de clique se ainda assim for interceptado. **Se o scraper voltar a extrair 0 produtos com pastas vazias sendo removidas, suspeite deste modal primeiro.**

#### 🔁 Rodízio de contas

O `.env` aceita várias contas em `KALODATA_LOGINS` (separadas por vírgula, mesma senha em `KALODATA_PASSWORD`). Falha de login levanta `LoginFailedException` e salva `debug_login.png`; qualquer erro inesperado salva `debug_erro.png`. Nenhum dos dois derruba a rodada: o script registra o que já conseguiu e segue para a próxima conta.

### 2. Geração de Roteiros (Prompts de Vídeo)
**Comando no chat do Antigravity:**
```text
/start_gen_prompts
```
**O que faz:**
Aciona uma *Skill* nativa do Antigravity. A IA varre os produtos recém-baixados, visualiza as fotos de cada um, e usa *Subagentes* em paralelo para criar os roteiros de vídeo profissionais.
**Regras de Roteiro (`prompt_sistema.yaml`):**
- **Duração:** **uma cena só** — um take contínuo de **8s** (Veo 3.1 - Quality), escrito em **6 beats cronometrados** (`0-1.5s / 1.5-3s / 3-4.5s / 4.5-6s / 6-7s / 7-8s`). Cada beat vira um painel do storyboard. Ritmo de comercial de feed: tempo real, sem câmera lenta.
- **Ação, não câmera:** cada beat descreve um **evento físico** (a mão entra e gira o frasco, o tecido cai, o swatch é riscado) e termina com o enquadramento entre parênteses. Produto parado com a câmera girando em volta é proibido.
- **Ação sem deformação:** toda ação é classificada numa **escada de risco** — N1 seguro (girar, deslizar, alisar, andar), N2 com encenação (abrir uma porta, borrifar um spray, água caindo, celular entrando no bolso; no máximo uma por clipe) e N3 proibido (rosquear, zíper, encaixar acessório, digitar, comer). O bloco `Physics & Staging` declara o estado de tudo em 0s, quem mexe e o que nunca se mexe.
- **Adaptativo:** cenário real com 1 a 3 props e paleta tirada da identidade do próprio produto; arquétipos para casos difíceis (tela com conteúdo fixo, produto instalado, livro, ferramenta de cabelo elétrica (vira **unboxing**: a embalagem real se abre e mostra o kit, sem cabelo em quadro), shapewear, suplemento, rótulo em escrita não latina, conflito título x foto).
- **Identidade travada:** o bloco `Product Lock` define um **token** do produto (cor + forma + tipo + marca) repetido em todos os beats. É o que impede o gerador de trocar a cor ou reescrever a marca lá pelo segundo 5.
- **Formato:** Vídeo focado apenas em interações visuais orgânicas (mãos ou *headless models* para roupas).
- **Sem áudio:** Os clipes saem **mudos** — sem trilha, sem efeito sonoro, sem voz. O som entra depois, na edição.
- **Sem texto na tela:** Zero legenda, letreiro ou marca d'água. O **rótulo do produto**, ao contrário, vai legível e escrito **exatamente** como nas fotos (bloco `Label & Brand`, com a marca soletrada letra a letra).
**Resultado:** `prompt_video/prompt_cena.md` (o prompt pronto para colar) e `raciocinio.md` (a justificativa das escolhas do diretor) em cada produto.
*(Nota: O script `check_prompts.py` garante a qualidade e impede que a IA repita os mesmos enquadramentos de câmera o tempo todo).*

### 3. Prompt do Storyboard
**Comando no chat do Antigravity:**
```text
/start_gen_image
```
**O que faz:**
Lê o `prompt_cena.md` de cada produto e escreve **o prompt que gera a prancha** de storyboard. Não gera a imagem: entrega o texto, e você cola no gerador com as fotos do produto anexadas.
**Regras de Imagem (`prompt_gen_image.yaml`):**
- Uma única prancha, **6 painéis numerados**, 2 colunas x 3 linhas.
- Um painel por beat do roteiro, no mesmo enquadramento declarado no beat.
- Cada painel mostra **ação acontecendo**, não o produto parado em seis ângulos, e repete o token do `Product Lock` para o produto não mudar de painel para painel.
- **Só os numerais** dos painéis: nada de texto de ajuda, que vazaria para o vídeo como letreiro.
- Produto grande, fiel às fotos, rótulo legível e virado para a lente nos painéis 2 e 6.
**Resultado:** `prompt_video/prompt_storyboard.md`. No Google Flow a prancha é o **único ingrediente visual do vídeo** (o Veo não vê as fotos do anúncio): ela é ao mesmo tempo o mapa da encenação e a cópia fiel do produto.

### 4. Prompt da Capa
**Comando no chat do Antigravity:**
```text
/start_gen_buy
```
**O que faz:**
Escreve **os prompts do carrossel de 2 imagens** do post — a capa que abre o post e o slide 2. Também não gera imagem.
**Regras da Capa (`prompt_gen_buy.yaml`):**
- **Post de feed do Instagram (4:5), gerado em tela 3:4** (o Flow não tem 4:5), editado e chamativo, com cara de peça de marca real e nunca de IA genérica, panfleto ou template. Produto e texto no centro, com margem nos quatro lados (o feed recorta para 4:5 e a grade do perfil recorta de novo).
- **Slide 2 do carrossel (`prompt_capa_2.md`):** mesma família e paleta da capa. Produto com várias peças -> o **kit inteiro em knolling**, cada peça uma vez; produto único -> o detalhe que prova o benefício. Até 5 callouts.
- **Duas famílias, escolhidas por produto:** **brand editorial** (eletro, gadget, relógio, suplemento, ferramentas, moda masculina, shapewear — tipografia de marca e color grading forte) ou **lifestyle scrapbook** (beleza, perfumaria, cabelo, moda feminina, livro — doodles e escrita à mão).
- Texto: **3 linhas** — título (até 4 palavras, soletrado com hifens) + frase de benefício (até 6) + CTA discreto (até 3, ex.: `Link na bio`); o scrapbook ganha até 3 callouts curtos apontando partes reais. Português correto e acentuado. Proibido chamada apelativa (`COMPRE JÁ`, `GARANTA O SEU`, `premium`, `exclusivo`…), exclamação, selo e botão.
- **Preço nunca**: sem "R$", sem número, sem porcentagem no texto da arte. Número impresso no próprio produto (display, "90 CAPS") continua como está.
- Mesmo produto e mesmo rótulo do vídeo (`Subject` e `Label & Brand` copiados palavra por palavra do `prompt_cena.md`), mas **ângulo, enquadramento e cenário diferentes** dos do vídeo e da foto do anúncio.
- Fundo branco de catálogo e colagem proibidos; texto nunca por cima do produto.
**Resultado:** `prompt_video/prompt_capa.md` e `prompt_video/prompt_capa_2.md`.

### 5. Revisão dos Prompts
**Comando no chat do Antigravity:**
```text
/prompt_gen_check
```
**O que faz:**
Roda depois dos três comandos. Lê os três prompts de cada produto **como o modelo vai lê-los** e corrige o que estiver errado nos próprios arquivos. O `check_prompts.py` confere a forma; este comando confere o que script nenhum confere.
**Regras da Revisão (`prompt_gen_check.yaml`) — seis auditorias por produto:**
1. **Grounding:** cor, peças, rótulo e escala batem com as fotos; nada inventado.
2. **Deformação beat a beat:** nível de risco de cada ação, objetos declarados desde 0s, partes que não se mexem travadas, mãos, tela fixa, rosto fora de quadro.
3. **Contradições:** entre blocos da cena (On camera x Negative, Scene x beats, Physics x beats) e entre os três arquivos.
4. **Força comercial:** hook no primeiro frame, prova real, ritmo, beauty shot, capa chamativa e da família certa.
5. **Português e texto:** ortografia e acento da capa letra por letra, soletrado igual ao título, limites de palavras, sem preço nem promessa.
6. **Forma:** `check_prompts.py check --ultima` com 0 erros.
**Resultado:** os prompts corrigidos no lugar + `prompt_video/revisao.md` (veredito, risco por beat, ajustes feitos e pendências que só você decide). A coluna `REV` do `status` mostra quem já foi revisado.

### 6. Geração no Google Flow
**Comando no Terminal:**
```bash
python3 flow_video.py            # só o dia mais recente (padrão do dia a dia)
python3 flow_video.py tudo       # todos os produtos, de todos os dias
python3 flow_video.py 7          # só o produto 7
python3 flow_video.py 7 9        # a faixa do produto 7 ao 9
```
**O que faz:**
Abre o Flow (headless, perfil `.flow_profile/`), entra no projeto "renda extra" e, para cada produto, cria a coleção `produto N`, sobe as fotos e gera, nesta ordem: **storyboard** (Nano Banana 2, 9:16) -> **capa** (3:4) -> **capa 2** (3:4, se existir o `prompt_capa_2.md`) -> **vídeo** (Veo 3.1 - Quality, 9:16, 720p, 8s, com a prancha como único ingrediente).
- **Numeração global:** `N` é a posição do produto na fila inteira, em ordem de data: os 10 de `2026-09-18` são 1–10, os de `2026-09-19` são 11–20, e assim por diante. É o mesmo `N` do nome da coleção no Flow.
- **Retomável:** se a coleção `produto N` já existe, ele entra nela e pula o que já foi gerado. Para **refazer** um produto do zero, renomeie ou apague a coleção antiga no Flow antes de rodar — senão ele vê as imagens antigas e pula.
- Produto sem `prompt_cena.md`, `prompt_storyboard.md` ou `prompt_capa.md` é pulado e aparece em `Falhas` no fim, sem criar coleção vazia.
- "Alta demanda" no Flow não cobra: o script espera 5 min e tenta de novo (até 8 vezes).

---

## 📂 Estrutura gerada pelo scraper

```
produtos/
└── 2026-09-18/
    ├── 01 Nome Do Produto Limpo/
    │   ├── capa.jpg          # primeira imagem do DOM = imagem principal do anúncio
    │   ├── imagem_1.jpg
    │   ├── imagem_2.jpg
    │   ├── ...
    │   └── metadata.json     # título, URL, fonte, posição e métricas da tabela
    ├── 02 Outro Produto/
    └── ...                   # até 10
```

Uma raiz só, uma pasta por dia, em `AAAA-MM-DD` (ordem alfabética = ordem cronológica). O prefixo `01`–`10` mantém a ordem de extração e evita colisão de nome entre produtos de títulos parecidos.

O `metadata.json` guarda as métricas da linha da tabela (faturamento, vendas, preço, comissão…) e o campo `fonte`, que diz de qual lista o produto veio. É o insumo que a LLM usa depois para escolher o ângulo de venda.

Os rótulos vêm dos `<th>` da tabela. Dois detalhes que o `scraper.py` trata e que quebram silenciosamente se mexidos: a coluna da posição tem `<th>` **vazio** (descartá-lo desloca todos os rótulos — a comissão vira preço), e os `<th>` trazem **glifos de ícone** da Private Use Area colados no texto.

---

## 📁 Principais Arquivos de Configuração

- `.env`: Armazena credenciais da Kalodata e chaves de API externas.
- `extracted_products.txt`: O histórico de deduplicação, um título por linha. **Não apague** — é ele que impede o script de baixar duas vezes o mesmo produto. Linhas antigas no formato `tabela<TAB>titulo` continuam sendo lidas normalmente.
- `prompt_sistema.yaml`: O cérebro da direção de vídeo (tempo, proibições, formatação estrutural e estilos). Se o modelo do gerador de vídeos mudar de regras, é aqui que deve ser ajustado.
- `prompt_gen_image.yaml`: As regras do prompt da prancha vertical com os 6 painéis de storyboard.
- `prompt_gen_buy.yaml`: As regras do prompt da capa do produto (as duas famílias).
- `prompt_gen_check.yaml`: As seis auditorias da revisão.
- `.agents/skills/`: Contém as lógicas das skills `/start_gen_prompts`, `/start_gen_image`, `/start_gen_buy` e `/prompt_gen_check` para o Antigravity interpretar.
- `check_prompts.py`: `status` mostra o que falta em **todos** os dias (coluna `REV` = revisado); `check` valida os três prompts e a costura entre eles, e só fecha com `0 erros`. Prompts no formato antigo de 10s aparecem como `[LEGADO]` e não são validados.

## 🛠️ Preparando o ambiente

```bash
./start.sh setup     # cria venv, instala requirements e o Chromium do Playwright
./start.sh destroy   # remove o venv
```
