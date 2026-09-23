import io
import os
import sys
import time
import random
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from playwright_stealth import stealth

load_dotenv()

# --- Configuração ---------------------------------------------------------
PERFIL_DIR = ".flow_profile"    # sessão do Google persiste aqui: loga uma vez só
URL_ABOUT = "https://flow.google.com/about"
URL_FLOW = "https://flow.google.com/"
PROJETO_NOME = "renda extra"     # projeto do Flow que guarda todos os produtos
COLECAO_SEM_TITULO = "Coleção sem título"  # nome que o Flow dá a uma coleção recém-criada
RAIZ_PRODUTOS = "produtos"       # mesma raiz do scraper.py: produtos/<AAAA-MM-DD>/<NN Titulo>/
MODELO_IMAGEM = "Nano Banana 2"
MODELO_VIDEO = "Omni 1.1 Flash"
TENTATIVAS_VIDEO = 10            # 10 x 2 min: o Omni leva ~3 min, mas a fila varia
TIMEOUT_UPLOAD_MS = 180000       # 9 fotos de ~100 KB, mas a fila do Flow é lenta
TIMEOUT_PADRAO_MS = 30000
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


class LoginFailedException(Exception):
    pass


class ChallengeException(Exception):
    """Google pediu verificação extra (2FA, celular, captcha). Só um humano resolve."""
    pass


def pausa_humana(minimo=0.5, maximo=1.5):
    time.sleep(random.uniform(minimo, maximo))


def ja_esta_logado(page):
    """Perfil persistente guarda o cookie: se flow.google.com abre sem cair no
    accounts.google.com, a sessão anterior ainda vale e o login inteiro é pulado."""
    page.goto(URL_FLOW, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    return "accounts.google.com" not in page.url and "/about" not in page.url


def abrir_tela_de_login(page):
    print("Abrindo a landing do Flow...")
    page.goto(URL_ABOUT, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    print("Clicando em 'Crie com o Google Flow'...")
    botao = page.locator("button[aria-label='Crie com o Google Flow']").first
    if botao.count() == 0:
        botao = page.get_by_role("button", name="Crie com o Google Flow").first
    botao.click()

    # O clique dispara o redirect para accounts.google.com; a URL exata varia
    # (dsh/continue aleatórios), então esperamos o domínio, não o caminho.
    page.wait_for_url("**accounts.google.com/**", timeout=TIMEOUT_PADRAO_MS)
    page.wait_for_timeout(3000)


def preencher_email(page, login):
    print(f"Preenchendo o e-mail ({login})...")
    page.wait_for_selector("#identifierId", timeout=TIMEOUT_PADRAO_MS)
    pausa_humana()
    page.type("#identifierId", login, delay=random.randint(60, 160))
    pausa_humana()

    print("Avançar (e-mail)...")
    page.click("#identifierNext")
    page.wait_for_timeout(6000)


def preencher_senha(page, password):
    print("Aguardando o campo de senha...")
    try:
        page.wait_for_selector("input[name='Passwd']", state="visible",
                               timeout=TIMEOUT_PADRAO_MS)
    except PWTimeout:
        raise LoginFailedException(
            "Campo de senha não apareceu. Google provavelmente barrou o navegador "
            "ou pediu verificação antes da senha (veja debug_flow_erro_sem_campo_senha.png)."
        )

    print("Preenchendo a senha...")
    pausa_humana()
    page.type("input[name='Passwd']", password, delay=random.randint(60, 160))
    pausa_humana()

    print("Avançar (senha)...")
    page.click("#passwordNext")
    page.wait_for_timeout(8000)


def confirmar_login(page):
    """Depois da senha o Google pode: liberar, pedir 2FA, ou recusar o navegador.
    Separar os três casos aqui evita erro genérico 5 telas adiante."""
    try:
        page.wait_for_url("**flow.google.com/**", timeout=60000)
    except PWTimeout:
        if "challenge" in page.url or "signin/v2" in page.url:
            raise ChallengeException(
                f"Google pediu verificação extra em {page.url}. "
                "Resolva uma vez num navegador com o mesmo perfil e a sessão fica salva."
            )
        raise LoginFailedException(f"Não chegou no Flow. Parou em {page.url}")

    page.wait_for_timeout(5000)
    print(f"Login efetuado com sucesso! URL: {page.url}")


def fazer_login(page, login, password):
    if ja_esta_logado(page):
        print(f"Sessão do perfil '{PERFIL_DIR}' ainda válida — login não é necessário.")
        return

    abrir_tela_de_login(page)
    preencher_email(page, login)
    preencher_senha(page, password)
    confirmar_login(page)


def abrir_projeto(page, nome):
    """Entra no projeto pelo nome. O clique tem que cair na miniatura: o rótulo do
    card fica sob o botão flutuante 'Novo projeto' e o clique é interceptado."""
    print(f"Abrindo o projeto '{nome}'...")
    page.goto(URL_FLOW, wait_until="domcontentloaded")
    page.wait_for_timeout(8000)

    # o banner promocional empurra a grade para baixo e desalinha os cards
    dispensar = page.locator("button[aria-label='Dispensar banner']")
    if dispensar.count():
        dispensar.first.click()
        page.wait_for_timeout(2000)

    card = page.locator(".project-card").filter(has_text=nome).first
    if card.count() == 0:
        raise LoginFailedException(f"Projeto '{nome}' não encontrado na home.")
    card.locator("img, video").first.click()

    page.wait_for_url("**/project/**", timeout=TIMEOUT_PADRAO_MS)
    page.wait_for_timeout(6000)
    print(f"Dentro do projeto: {page.url}")


def abrir_colecao(page, titulo):
    """Abre a coleção pelo título. O clique vai no tile inteiro porque o div
    '.preview' cobre o texto e intercepta qualquer clique no rótulo.

    O filtro é por texto exato: ':has-text()' casa substring e faria 'produto 1'
    abrir a coleção 'produto 12'."""
    tile = page.locator("flow-collection-tile").filter(
        has=page.get_by_text(titulo, exact=True)
    ).first
    if tile.count() == 0:
        return False
    tile.click()
    page.wait_for_url("**/collection/**", timeout=TIMEOUT_PADRAO_MS)
    page.wait_for_timeout(5000)
    return True


def renomear_colecao(page, nome):
    print(f"Renomeando a coleção para '{nome}'...")
    campo = page.locator("input.editable-text-input").first
    campo.click()
    page.keyboard.press("ControlOrMeta+a")
    pausa_humana(0.2, 0.5)
    page.type("input.editable-text-input", nome, delay=random.randint(50, 120))
    page.keyboard.press("Enter")
    page.wait_for_timeout(4000)

    atual = campo.input_value()
    if atual.strip() != nome:
        raise LoginFailedException(f"Rename não pegou: campo ficou como {atual!r}")
    print(f"Coleção '{nome}' pronta: {page.url}")


def criar_colecao(page, nome):
    """Garante a coleção do produto: entra se já existe, senão cria e renomeia.
    Se uma execução anterior morreu entre
    o criar e o renomear, sobra uma 'Coleção sem título' — reaproveita em vez de
    empilhar coleções órfãs a cada produto."""
    if abrir_colecao(page, nome):
        print(f"Coleção '{nome}' já existe — entrando nela.")
        return
    if abrir_colecao(page, COLECAO_SEM_TITULO):
        print(f"Reaproveitando uma '{COLECAO_SEM_TITULO}' de execução anterior.")
    else:
        print("Criando nova coleção...")
        page.locator("button[aria-label='Menu para adicionar arquivos']").click()
        page.wait_for_timeout(2000)
        page.locator("[role='menuitem']:has-text('Nova coleção')").click()
        page.wait_for_timeout(6000)
        if not abrir_colecao(page, COLECAO_SEM_TITULO):
            raise LoginFailedException("Coleção nova não apareceu na grade.")

    renomear_colecao(page, nome)


def listar_produtos():
    """A coleção 'produto N' do Flow é o N-ésimo produto da fila, contando todos os
    dias em ordem cronológica — não o produto NN de um dia específico."""
    return sorted(
        os.path.join(RAIZ_PRODUTOS, dia, prod)
        for dia in os.listdir(RAIZ_PRODUTOS)
        if os.path.isdir(os.path.join(RAIZ_PRODUTOS, dia))
        for prod in os.listdir(os.path.join(RAIZ_PRODUTOS, dia))
        if os.path.isdir(os.path.join(RAIZ_PRODUTOS, dia, prod))
    )


def dia_do_produto(pasta):
    return os.path.basename(os.path.dirname(pasta))


def faixa_do_ultimo_dia():
    """Padrão do dia a dia: rodar só a pasta de data mais recente, sem reabrir os
    dias já entregues. A numeração das coleções continua global ('produto 21'),
    então a faixa é a posição desses produtos na fila inteira — não 1..N do dia."""
    pastas = listar_produtos()
    dia = dia_do_produto(pastas[-1])
    primeiro = next(i for i, p in enumerate(pastas, 1) if dia_do_produto(p) == dia)
    return dia, primeiro, len(pastas)


def produto_por_ordem(n):
    pastas = listar_produtos()
    if not 1 <= n <= len(pastas):
        raise IndexError(f"produto {n} não existe (a fila tem {len(pastas)})")
    return pastas[n - 1]


def ler_prompt(pasta, nome):
    caminho = os.path.join(pasta, "prompt_video", nome)
    with io.open(caminho, encoding="utf-8") as f:
        return f.read().strip()


def imagens_do_produto(pasta):
    """capa.jpg + imagem_N.jpg. A ordem alfabética já põe a capa na frente."""
    return sorted(
        os.path.join(pasta, f) for f in os.listdir(pasta) if f.endswith(".jpg")
    )


def contar_imagens(page):
    return page.locator("flow-image-tile img[data-media-id]").count()


def esperar_grade(page, esperado):
    """A coleção abre com a grade vazia e vai preenchendo. Contar antes disso faz o
    guarda de idempotência ler 0 e reenviar fotos que já estão lá — foi assim que a
    primeira rodada duplicou as 9 imagens. Sai no que vier primeiro: as fotos
    carregadas ou o cartaz de coleção vazia."""
    try:
        page.wait_for_function(
            "n => document.querySelectorAll('flow-image-tile img[data-media-id]').length >= n"
            " || document.body.innerText.includes('Comece a criar ou adicione')",
            arg=esperado,
            timeout=60000,
        )
    except PWTimeout:
        print("    [aviso] grade não estabilizou em 60s, seguindo com o que tem")


def enviar_imagens(page, arquivos):
    # sem isso, reprocessar um produto duplica as fotos dentro da colecao
    esperar_grade(page, len(arquivos))
    ja = contar_imagens(page)
    if ja >= len(arquivos):
        print(f"Coleção já tem {ja} imagens — upload pulado.")
        return

    print(f"Enviando {len(arquivos)} imagens...")
    page.locator("button[aria-label='Menu para adicionar arquivos']").click()
    page.wait_for_timeout(2000)

    with page.expect_file_chooser() as fc:
        page.locator("[role='menuitem']:has-text('Enviar')").click()
    fc.value.set_files(arquivos)

    # o tile aparece vazio assim que o upload comeca e so ganha o <img> quando a
    # foto termina de subir. Contar tile em vez do <img> entra na geracao com
    # metade das fotos ainda no ar.
    page.wait_for_function(
        "n => document.querySelectorAll('flow-image-tile img[data-media-id]').length >= n",
        arg=len(arquivos),
        timeout=TIMEOUT_UPLOAD_MS,
    )
    page.wait_for_timeout(5000)
    print("Imagens enviadas.")


def selecionar_imagens(page, ignorar=0, limite=None):
    """Ctrl+clique em cada foto. É a seleção que vira 'ingrediente' do prompt —
    sem ela o Nano Banana gera sem ver o produto.

    A grade vem do mais novo para o mais antigo, então o que acabou de ser gerado
    fica na frente: `ignorar=1` deixa o storyboard de fora e manda para a capa só
    as fotos originais do produto; `ignorar=1, limite=1` faz o contrário e pega
    só a prancha, que é o único ingrediente do vídeo.

    O reload é de propósito: ctrl+clique num tile já selecionado DESmarca, e depois
    de uma geração a grade pode voltar com seleção. Recarregar zera o estado."""
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(12000)

    tiles = page.locator("flow-image-tile")
    total = tiles.count()
    fim = total if limite is None else min(ignorar + limite, total)
    alvo = fim - ignorar
    print(f"Selecionando {alvo} de {total} imagens (ignorando as {ignorar} mais novas)...")
    for i in range(ignorar, fim):
        tiles.nth(i).click(modifiers=["Control"])
        page.wait_for_timeout(300)

    conferir_ingredientes(page, alvo)
    return alvo


def conferir_ingredientes(page, esperado):
    """Trocar Imagem->Vídeo re-renderiza a barra do comando. Se a seleção cair no
    caminho, o modelo gera sem ver a prancha e a geração vai pro lixo — conferir
    antes de clicar em gerar sai mais barato."""
    page.wait_for_function(
        "n => document.querySelectorAll('flow-ingredient-chip').length >= n",
        arg=esperado,
        timeout=60000,
    )
    chips = page.locator("flow-ingredient-chip").count()
    if chips != esperado:
        raise LoginFailedException(f"Esperava {esperado} ingredientes, veio {chips}.")
    print(f"{chips} ingredientes no comando.")


def esperar_geracao(page, total_esperado):
    print(f"Aguardando a geração terminar ({total_esperado} imagens na grade)...")
    page.wait_for_function(
        "n => document.querySelectorAll('flow-image-tile img[data-media-id]').length >= n",
        arg=total_esperado,
        timeout=600000,
    )
    page.wait_for_timeout(6000)
    print(f"Pronto: {contar_imagens(page)} imagens na coleção.")


def esperar_video(page, total_esperado):
    """Vídeo não vira <img data-media-id>: a grade ganha um <flow-video-tile>.

    A espera é pela miniatura, não pelo tile: o tile aparece assim que a geração
    entra na fila, exibindo o percentual, e seguir nele largaria o produto com um
    vídeo em 3% e ainda marcaria 'vídeo já existe' numa retomada.

    Vale qualquer um dos dois estados do tile pronto: parado ele mostra o <img> da
    miniatura, sob o cursor ele troca pelo <video> do preview. Esperar só por um
    deles trava para sempre com o vídeo já entregue."""
    print(f"Aguardando o vídeo ficar pronto ({total_esperado} na coleção)...")
    for tentativa in range(TENTATIVAS_VIDEO):
        try:
            page.wait_for_function(
                "n => document.querySelectorAll("
                "'flow-video-tile img.thumbnail, flow-video-tile video[src]').length >= n",
                arg=total_esperado,
                timeout=120000,
            )
            break
        except PWTimeout:
            print(f"    ainda não: recarregando ({tentativa + 1}/{TENTATIVAS_VIDEO})")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(12000)
    else:
        raise LoginFailedException("Vídeo não ficou pronto no tempo limite.")
    page.wait_for_timeout(6000)
    print("Vídeo gerado.")


def _toggle(page, texto):
    """Os grupos mat-button-toggle-group-N são renumerados a cada render, então o
    alvo tem que ser o rótulo, nunca o id do grupo."""
    botao = page.locator(
        f"button.mat-button-toggle-button:has(.toggle-text:text-is('{texto}'))"
    ).first
    if botao.get_attribute("aria-checked") == "true":
        return
    botao.click()
    page.wait_for_timeout(1200)


def escolher_modelo(page, nome):
    """O modelo é um dropdown, não um toggle. Só abre o menu se o atual for outro."""
    trigger = page.locator(".model-select-trigger-content").first
    if nome in trigger.inner_text():
        return
    trigger.click()
    page.wait_for_timeout(2000)
    page.locator(f"[role='menuitem']:has-text('{nome}')").first.click()
    page.wait_for_timeout(2000)


def configurar_geracao(page, *opcoes, modelo=None):
    """O painel tem que estar aberto para os toggles existirem no DOM, e o modo
    (Imagem/Vídeo) precisa vir primeiro: duração e resolução só aparecem em vídeo."""
    print("Configurando: " + " / ".join(opcoes) + (f" / {modelo}" if modelo else ""))
    page.locator(".settings-summary").first.click()
    page.wait_for_timeout(2500)
    for opcao in opcoes:
        _toggle(page, opcao)
    if modelo:
        escolher_modelo(page, modelo)
    page.keyboard.press("Escape")
    page.wait_for_timeout(1500)


def escrever_prompt(page, texto):
    print(f"Colando o prompt ({len(texto)} caracteres)...")
    page.locator(".ProseMirror").first.click()
    page.wait_for_timeout(800)
    page.keyboard.insert_text(texto)
    page.wait_for_timeout(1500)


def gerar(page):
    botao = page.locator("button[aria-label='Iniciar geração']").first
    if botao.is_disabled():
        raise LoginFailedException("Botão de gerar continua desabilitado.")
    print("Iniciando a geração...")
    botao.click()
    page.wait_for_timeout(5000)


def gerar_imagem(page, pasta, arquivo, ignorar, total_final):
    alvo = selecionar_imagens(page, ignorar=ignorar)
    escrever_prompt(page, ler_prompt(pasta, arquivo))
    configurar_geracao(page, "Imagem", "9:16", "x1", modelo=MODELO_IMAGEM)
    conferir_ingredientes(page, alvo)
    gerar(page)
    esperar_geracao(page, total_final)


def gerar_video(page, pasta):
    """Ingrediente único: a prancha. Ela é o tile 1 porque a capa, gerada logo
    antes, entra na frente dela na grade."""
    alvo = selecionar_imagens(page, ignorar=1, limite=1)
    escrever_prompt(page, ler_prompt(pasta, "prompt_cena.md"))
    configurar_geracao(page, "Vídeo", "Elementos", "9:16", "720p", "10s", "x1",
                       modelo=MODELO_VIDEO)
    conferir_ingredientes(page, alvo)
    gerar(page)
    esperar_video(page, 1)


def processar_produto(page, n, projeto_url):
    """Coleção -> fotos -> storyboard -> capa -> vídeo. Cada etapa confere o que já
    existe antes de rodar: um lote de 17 produtos que morre no meio precisa poder
    ser retomado sem regerar (e repagar) o que já ficou pronto."""
    pasta = produto_por_ordem(n)
    print(f"\n===== produto {n} = {pasta} =====")
    criar_colecao(page, f"produto {n}")

    arquivos = imagens_do_produto(pasta)
    enviar_imagens(page, arquivos)
    base = len(arquivos)

    if contar_imagens(page) >= base + 1:
        print("Storyboard já está na coleção — pulando.")
    else:
        gerar_imagem(page, pasta, "prompt_storyboard.md", 0, base + 1)

    if contar_imagens(page) >= base + 2:
        print("Capa já está na coleção — pulando.")
    else:
        gerar_imagem(page, pasta, "prompt_capa.md", 1, base + 2)

    # o tile conta mesmo sem o <video>: se uma execucao anterior morreu no meio da
    # renderizacao, gerar de novo aqui daria dois videos no mesmo produto
    if page.locator("flow-video-tile").count():
        print("Vídeo já está na coleção (ou ainda renderizando) — só aguardando.")
        esperar_video(page, 1)
    else:
        gerar_video(page, pasta)

    print(f"===== produto {n} concluído =====")
    voltar_ao_projeto(page, projeto_url)


def voltar_ao_projeto(page, url):
    """Sai da coleção pela URL do projeto em vez do botão de voltar: a seta do
    cabeçalho às vezes cai no editor de mídia aberto, não na grade."""
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(8000)


def abrir_navegador(playwright):
    """Contexto persistente: o cookie do Google sobrevive entre execuções.
    channel='chromium' usa o browser completo (headless novo) em vez do
    headless-shell, que o login do Google rejeita com mais frequência."""
    return playwright.chromium.launch_persistent_context(
        user_data_dir=os.path.abspath(PERFIL_DIR),
        channel="chromium",
        headless=True,
        user_agent=USER_AGENT,
        viewport={"width": 1920, "height": 1080},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
        ],
    )


def main():
    # 'python flow_video.py' faz so o dia mais recente; 'python flow_video.py 7'
    # faz so o produto 7; 'python flow_video.py 7 9' faz a faixa (usado no atraso
    # dos dias 18 e 19)
    if len(sys.argv) > 1:
        primeiro = int(sys.argv[1])
        ultimo = int(sys.argv[2]) if len(sys.argv) > 2 else primeiro
        print(f"Faixa manual: produto {primeiro} ao {ultimo}")
    else:
        dia, primeiro, ultimo = faixa_do_ultimo_dia()
        print(f"Dia mais recente: {dia} -> produto {primeiro} ao {ultimo}")

    login = os.getenv("GOOGLE_LOGIN")
    password = os.getenv("GOOGLE_PASSWORD")
    if not login or not password:
        print("[!] Defina GOOGLE_LOGIN e GOOGLE_PASSWORD no .env")
        return

    with stealth.Stealth().use_sync(sync_playwright()) as playwright:
        context = abrir_navegador(playwright)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            fazer_login(page, login, password)
            abrir_projeto(page, PROJETO_NOME)
            projeto_url = page.url

            falhas = []
            for n in range(primeiro, ultimo + 1):
                try:
                    processar_produto(page, n, projeto_url)
                except Exception as e:
                    print(f"\n!!! produto {n} falhou: {e}")
                    falhas.append(n)
                    voltar_ao_projeto(page, projeto_url)

            print(f"\nLote encerrado: {primeiro}..{ultimo}")
            print("Falhas: " + (", ".join(map(str, falhas)) if falhas else "nenhuma"))
        except (LoginFailedException, ChallengeException) as e:
            print(f"\n!!! {e}")
        except Exception as e:
            print(f"\n!!! Erro inesperado: {e}")
        finally:
            context.close()


if __name__ == "__main__":
    main()
