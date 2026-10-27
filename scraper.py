import os
import re
import json
import time
import random
import argparse
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração ---------------------------------------------------------
META_DIARIA = 10                # produtos ineditos que queremos por dia
RAIZ_PRODUTOS = "produtos"      # tudo do dia cai em produtos/<AAAA-MM-DD>/
HISTORICO = "extracted_products.txt"
MAX_TITULO = 90                 # nome de pasta longo demais quebra o filesystem
TIMEOUT_IMAGEM_MS = 15000       # sem imagem nesse tempo = bloqueio por limite
TIMEOUT_TABELA_MS = 15000
TIMEOUT_DOWNLOAD_S = 20
TENTATIVAS_DOWNLOAD = 3
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

URL_PRODUTOS = "https://www.kalodata.com/product"

# A conta Prova so enxerga a pagina 1 (10 linhas) de cada busca: paginar exige plano
# pago ("Membership Required"). Para chegar aos 10 ineditos a gente varia a BUSCA em vez
# da pagina, cada faixa de comissao devolve outras 10 linhas. Ordem = preferencia:
# primeiro o top 10 absoluto, depois as comissoes mais gordas.
FONTES = [
    ("Top 10 geral", None),
    ("Comissao 15-20", "15% ~ 20%"),
    ("Comissao 20-30", "20% ~ 30%"),
    ("Comissao acima de 30", ">30%"),
    ("Comissao 10-15", "10% ~ 15%"),
    ("Comissao abaixo de 10", "<10%"),
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Referer": "https://www.kalodata.com/"})


class LimitReachedException(Exception):
    pass


class LoginFailedException(Exception):
    pass


def carregar_historico():
    """Titulos ja extraidos em qualquer dia e qualquer fonte. A deduplicacao e global
    de proposito: o mesmo produto aparece na lista geral e nas faixas de comissao, e o
    funil de video so quer ele uma vez."""
    titulos = set()
    if os.path.exists(HISTORICO):
        with open(HISTORICO, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                # formato antigo: "tabela<TAB>titulo"; hoje gravamos so o titulo
                titulo = linha.split("\t", 1)[1] if "\t" in linha else linha
                titulos.add(titulo)
                titulos.add(limpar_titulo(titulo))
    return titulos


def salvar_historico(titulo):
    with open(HISTORICO, "a", encoding="utf-8") as f:
        f.write(f"{titulo}\n")


def limpar_titulo(titulo):
    """Vira nome de pasta: sem caractere proibido, sem espaco duplo, sem estourar o
    limite do filesystem (titulos de marketplace passam de 250 caracteres)."""
    seguro = "".join(c for c in titulo if c.isalpha() or c.isdigit() or c in (" ", "-", "_"))
    seguro = re.sub(r"\s+", " ", seguro).strip()
    return seguro[:MAX_TITULO].strip()


def pasta_do_dia():
    return os.path.join(RAIZ_PRODUTOS, time.strftime("%Y-%m-%d"))


def remover_pasta_vazia(product_dir):
    """Pasta de produto sem nenhuma imagem nao serve para nada (ex: limite diario
    de visitas atingido). Remove apenas se estiver realmente vazia."""
    try:
        if product_dir and os.path.isdir(product_dir) and not os.listdir(product_dir):
            os.rmdir(product_dir)
            print(f"   [!] Pasta sem imagens removida: {os.path.basename(product_dir)}")
    except OSError as e:
        print(f"   [!] Nao foi possivel remover {product_dir}: {e}")


def baixar_imagem(url, destino):
    """Baixa com retry e confere que veio imagem de verdade (nao pagina de erro)."""
    for tentativa in range(1, TENTATIVAS_DOWNLOAD + 1):
        try:
            resposta = SESSION.get(url, timeout=TIMEOUT_DOWNLOAD_S)
            resposta.raise_for_status()
            conteudo = resposta.content
            if len(conteudo) < 1024:
                raise ValueError(f"conteudo muito pequeno ({len(conteudo)} bytes)")
            with open(destino, "wb") as f:
                f.write(conteudo)
            return True
        except Exception as e:
            if tentativa == TENTATIVAS_DOWNLOAD:
                print(f"   Erro ao baixar {os.path.basename(destino)}: {e}")
                return False
            time.sleep(1.5 * tentativa)
    return False


def fechar_modais(page, esperar_ms=0):
    """A Kalodata abre um modal ("Dicas de seguranca da conta") por cima da tabela que
    intercepta todos os cliques. Ele nao tem botao de fechar: so sai com Escape.
    esperar_ms > 0 aguarda o modal surgir, porque ele aparece alguns segundos
    depois da tabela e senao passaria batido bem na hora do clique."""
    if esperar_ms:
        try:
            page.wait_for_selector(".ant-modal-wrap", timeout=esperar_ms)
        except Exception:
            return True
    for _ in range(3):
        wrap = page.locator(".ant-modal-wrap")
        if wrap.count() == 0 or not wrap.first.is_visible():
            return True
        print("   Modal bloqueando a pagina. Fechando com Escape...")
        page.keyboard.press("Escape")
        page.wait_for_timeout(800)
    print("   [!] Modal continua aberto apos Escape.")
    return False


def ler_cabecalhos(page):
    """Rotulos das colunas da tabela, para dar nome as metricas do metadata.json.
    Nao descarta rotulo vazio: a coluna da posicao no ranking tem <th> em branco e
    remove-lo desloca todos os rotulos (a comissao viraria preco, e assim por diante)."""
    for seletor in ('th[data-slot="table-head"]', "thead th", "thead td"):
        try:
            # os <th> trazem glifos de icone (ajuda, setas de ordenacao) da Private
            # Use Area colados no texto; viram lixo invisivel na chave do metadata
            rotulos = [" ".join(re.sub(r"[-]", " ", t).split())
                       for t in page.locator(seletor).all_inner_texts()]
            if any(rotulos):
                return rotulos
        except Exception:
            continue
    return []


def extrair_metricas(row, cabecalhos):
    """Metricas da linha da tabela (faturamento, vendas, preco, comissao...).
    E o insumo que a LLM usa depois para escolher o angulo de venda."""
    try:
        celulas = [c.strip() for c in row.locator("td").all_inner_texts()]
    except Exception:
        return {}
    metricas = {}
    for idx, valor in enumerate(celulas):
        if not valor:
            continue
        rotulo = cabecalhos[idx] if idx < len(cabecalhos) else ""
        metricas[rotulo or f"coluna_{idx + 1}"] = " ".join(valor.split())
    return metricas


def coletar_urls_de_imagem(new_page):
    """Ordem do DOM preservada: a primeira imagem e a principal do anuncio (capa)."""
    urls = []
    vistas = set()

    for img in new_page.locator("img").all():
        src = img.get_attribute("src")
        if src and "tiktok.product.images" in src and src not in vistas:
            vistas.add(src)
            urls.append(src)

    if not urls:
        for bg in new_page.locator(".cursor-zoom-in").all():
            style = bg.get_attribute("style")
            if style and "tiktok.product.images" in style:
                match = re.search(r'url\("?([^"\)]+)"?\)', style)
                if match and match.group(1) not in vistas:
                    vistas.add(match.group(1))
                    urls.append(match.group(1))

    return urls


def abrir_lista(page, faixa_comissao):
    """Recarrega a lista de produtos e, se for o caso, aplica uma faixa de comissao.
    Recarrega sempre para nao acumular o filtro da fonte anterior. Cada Enviar gasta
    uma das buscas diarias da conta."""
    page.goto(URL_PRODUTOS)
    page.wait_for_selector('td[data-slot="table-cell"]:has-text("1")', timeout=TIMEOUT_TABELA_MS)
    fechar_modais(page, esperar_ms=10000)

    if faixa_comissao is None:
        return

    print(f"   Aplicando filtro de comissão {faixa_comissao}...")
    fechar_modais(page)
    page.locator(':text("Commission Rate"), :text("Taxa de comissão")').first.click(timeout=10000)
    time.sleep(1)
    page.locator(f'text="{faixa_comissao}"').first.click(timeout=10000)
    time.sleep(1)
    page.locator('button:has-text("Submit"), button:has-text("Enviar")').first.click(timeout=10000)
    time.sleep(10)  # espera segura para o SPA recarregar a tabela

    try:
        page.wait_for_selector('td[data-slot="table-cell"]:has-text("1")', timeout=TIMEOUT_TABELA_MS)
    except Exception:
        raise LimitReachedException("Limite de buscas diárias atingido (timeout na tabela).")
    fechar_modais(page)


def scrape_table(page, context, fonte, faltam, historico, ja_no_dia):
    """Varre as linhas da fonte atual e baixa ate `faltam` produtos ineditos.
    `ja_no_dia` conta os produtos que o dia ja tem, para numerar as pastas em sequencia."""
    if faltam <= 0:
        return 0

    print(f"\n--- Fonte: {fonte} (faltam {faltam} produtos) ---")
    base_dir = pasta_do_dia()
    cabecalhos = ler_cabecalhos(page)
    rows = page.locator('tr[data-slot="table-row"]:has(.line-clamp-2)').all()
    print(f"   {len(rows)} linhas disponíveis nesta lista.")

    extraidos, pulados = 0, 0

    for idx, row in enumerate(rows, start=1):
        if extraidos >= faltam:
            print(f"   Meta atingida na fonte {fonte}.")
            break

        product_dir = None
        new_page = None
        try:
            # a linha tem dois .line-clamp-2 (titulo e preco): o titulo e o primeiro
            title = row.locator(".line-clamp-2").first.inner_text().strip()
            safe_title = limpar_titulo(title)

            if safe_title in historico:
                print(f"{idx}. '{safe_title[:60]}' já extraído antes. Pulando...")
                pulados += 1
                continue

            metricas = extrair_metricas(row, cabecalhos)

            # so cria a pasta na hora de usar, senao sobra pasta vazia quando o dia
            # nao rende nenhum produto
            os.makedirs(base_dir, exist_ok=True)
            pastas_existentes = len([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))])
            numero = pastas_existentes + 1
            product_dir = os.path.join(base_dir, f"{numero:02d} {safe_title}")
            os.makedirs(product_dir, exist_ok=True)
            print(f"{idx}. Pasta criada: {os.path.basename(product_dir)}")

            print("   Abrindo página do produto...")
            # O modal pode reaparecer a qualquer momento e intercepta o clique da linha
            fechar_modais(page)
            try:
                with context.expect_page(timeout=10000) as new_page_info:
                    row.click(timeout=15000)
            except Exception:
                fechar_modais(page)
                with context.expect_page(timeout=10000) as new_page_info:
                    row.click(timeout=15000)

            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")

            try:
                # Esperamos pela imagem principal
                new_page.wait_for_selector(".cursor-zoom-in", timeout=TIMEOUT_IMAGEM_MS)
            except Exception:
                # Se não carregou a imagem, assumimos bloqueio por limite de visitas
                print("   [!] Imagem não carregada (provável bloqueio de limite).")
                remover_pasta_vazia(product_dir)
                raise LimitReachedException("Limite de visitas a produtos atingido (timeout na imagem).")

            url_produto = new_page.url

            print("   Abrindo modal da galeria para extração super rápida...")
            new_page.click(".cursor-zoom-in")
            new_page.wait_for_timeout(2000)

            urls = coletar_urls_de_imagem(new_page)
            print(f"   Encontradas {len(urls)} imagens no total!")

            if not urls:
                print("   [!] Nenhuma imagem encontrada para este produto.")
                remover_pasta_vazia(product_dir)
                continue

            # A primeira imagem do DOM e a principal do anuncio: vira a capa.
            arquivos = []
            if baixar_imagem(urls[0], os.path.join(product_dir, "capa.jpg")):
                arquivos.append("capa.jpg")
            for img_idx, img_url in enumerate(urls[1:], start=1):
                nome = f"imagem_{img_idx}.jpg"
                if baixar_imagem(img_url, os.path.join(product_dir, nome)):
                    arquivos.append(nome)

            if not arquivos:
                print("   [!] Nenhuma imagem pôde ser baixada.")
                remover_pasta_vazia(product_dir)
                continue

            metadata = {
                "titulo_bruto": title,
                "titulo_pasta": os.path.basename(product_dir),
                "fonte": fonte,
                "data": time.strftime("%Y-%m-%d"),
                "posicao_na_fonte": idx,
                "url_produto": url_produto,
                "metricas": metricas,
                "imagens": arquivos,
                "extraido_em": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(os.path.join(product_dir, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            print(f"   {len(arquivos)} imagens salvas + metadata.json")

            salvar_historico(safe_title)
            historico.add(safe_title)
            extraidos += 1

            time.sleep(random.uniform(0.5, 1.5))

        except LimitReachedException:
            raise
        except Exception as e:
            print(f"Erro ao processar linha {idx}: {e}")
            remover_pasta_vazia(product_dir)
        finally:
            if new_page:
                try:
                    new_page.close()
                except Exception:
                    pass

    print(f"   Fonte {fonte}: {extraidos} novos, {pulados} já existentes.")
    return extraidos


def fazer_login(page, login, password):
    print(f"Navegando direto para a página de login da Kalodata com {login}...")
    page.goto("https://www.kalodata.com/login")

    print("Aguardando o formulário de login carregar (com bypass)...")
    page.wait_for_selector("#register_email", timeout=15000)

    print("Preenchendo e-mail e senha de forma humanizada (com delay simulado)...")
    time.sleep(random.uniform(0.5, 1.5))
    page.type("#register_email", login, delay=random.randint(50, 150))
    time.sleep(random.uniform(0.5, 1.2))
    page.type("#register_password", password, delay=random.randint(50, 150))
    time.sleep(random.uniform(0.3, 1.0))

    print("Aceitando os termos de uso...")
    page.check("input.ant-checkbox-input", force=True)
    time.sleep(random.uniform(0.5, 1.5))

    print("Clicando no botão de submit...")
    page.click("button[type='submit'].submit-btn")
    page.wait_for_timeout(8000)

    # Se o formulario continua na tela, o login nao passou (senha errada,
    # captcha ou conta bloqueada). Melhor falhar aqui do que 3 telas adiante.
    if "login" in page.url and page.locator("#register_email").count() > 0:
        raise LoginFailedException(f"Login não completou para {login}.")

    print("Login efetuado com sucesso!")


def run_scraper(login, password, faltam, ja_no_dia):
    """Extrai ate `faltam` produtos nesta conta, percorrendo as FONTES em ordem.
    Nunca propaga erro: devolve quantos conseguiu, para o main somar o progresso
    das duas contas em vez de recomecar do zero."""
    extraidos = 0
    with stealth.Stealth().use_sync(sync_playwright()) as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--window-size=1920,1080",
            ]
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"
        )

        page = context.new_page()

        try:
            fazer_login(page, login, password)
            historico = carregar_historico()

            for fonte, faixa in FONTES:
                if extraidos >= faltam:
                    break
                abrir_lista(page, faixa)
                extraidos += scrape_table(
                    page, context, fonte,
                    faltam - extraidos, historico, ja_no_dia + extraidos,
                )

        except LimitReachedException as e:
            print(f"\n!!! Limite da conta {login}: {e}")
        except LoginFailedException as e:
            print(f"\n!!! {e}")
        except Exception as e:
            print(f"\n!!! Erro inesperado na conta {login}: {e}")

        finally:
            context.close()
            browser.close()

    print(f"\nConta {login}: {extraidos} produtos extraídos.")
    return extraidos


PLACEHOLDERS_INVALIDOS = {
    "email1@gmail.com",
    "email2@gmail.com",
    "seu_email_kalodata@gmail.com",
    "sua_senha_aqui",
    "sua_senha_kalodata_aqui",
}


def main():
    parser = argparse.ArgumentParser(
        description="Extrai produtos em alta da Kalodata usando o SEU login e senha."
    )
    parser.add_argument(
        "--login",
        help="Seu(s) e-mail(s) de login na Kalodata (separados por vírgula). Sobrescreve KALODATA_LOGINS do .env.",
    )
    parser.add_argument(
        "--senha",
        help="Sua senha da Kalodata. Sobrescreve KALODATA_PASSWORD do .env.",
    )
    args = parser.parse_args()

    logins_str = args.login or os.getenv("KALODATA_LOGINS") or os.getenv("KALODATA_LOGIN")
    password = args.senha or os.getenv("KALODATA_PASSWORD")

    if not logins_str or not password:
        print("Erro: Credenciais não encontradas.")
        print("Configure o SEU login e senha com './start.sh login', no arquivo .env,")
        print("ou passe direto no comando: python3 scraper.py --login seu@email.com --senha suasenha")
        return

    logins = [l.strip() for l in logins_str.split(",") if l.strip()]
    if not logins or password.strip() in PLACEHOLDERS_INVALIDOS or any(l in PLACEHOLDERS_INVALIDOS for l in logins):
        print("Erro: O arquivo .env ainda está com credenciais de exemplo (placeholders).")
        print("Configure o SEU próprio login e senha rodando './start.sh login'")
        print("ou execute: python3 scraper.py --login seu@email.com --senha suasenha")
        return

    # o dia pode ja ter produtos de uma rodada anterior: a meta e do dia, nao da rodada
    base_dir = pasta_do_dia()
    ja_no_dia = len([d for d in os.listdir(base_dir)
                     if os.path.isdir(os.path.join(base_dir, d))]) if os.path.isdir(base_dir) else 0
    if ja_no_dia:
        print(f"O dia já tem {ja_no_dia} produtos em {base_dir}.")

    for login in logins:
        base_dir = pasta_do_dia()
        total = len([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]) if os.path.isdir(base_dir) else 0
        if total >= META_DIARIA:
            break
        print("\n======================================")
        print(f"Conta: {login}  (faltam {META_DIARIA - total} de {META_DIARIA})")
        print("======================================")
        run_scraper(login, password, META_DIARIA - total, total)

    print("\n======================================")
    if total >= META_DIARIA:
        print(f"Meta diária atingida: {total} de {META_DIARIA} produtos em {base_dir}")
        print("\nPronto. Agora rode /start_gen_prompts no Antigravity.")
    else:
        print(f"[!] Fim das contas com {total} de {META_DIARIA} produtos em {base_dir}.")
        print("    As contas esgotaram a cota do dia ou todas as listas já estavam no histórico.")
        print("    Rode de novo amanhã (ou com outra conta) para completar a meta.")
    print("======================================")


if __name__ == "__main__":
    main()
