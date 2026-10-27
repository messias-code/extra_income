#!/bin/bash

# Nome do diretório do ambiente virtual e perfil do navegador
VENV_DIR="venv"
FLOW_PROFILE_DIR=".flow_profile"

function criar_env_padrao() {
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        cat <<EOF > .env
KALODATA_LOGINS=seu_email_kalodata@gmail.com
KALODATA_PASSWORD=sua_senha_kalodata_aqui
GOOGLE_LOGIN=seu_email_google@gmail.com
GOOGLE_PASSWORD=sua_senha_google_aqui
EOF
    fi
}

function setup() {
    echo "=== CRIANDO AMBIENTE ==="
    
    # Cria o arquivo .env se não existir
    if [ ! -f ".env" ]; then
        echo "Criando arquivo .env a partir do modelo..."
        criar_env_padrao
        echo "ATENÇÃO: Configure SEU login e senha rodando './start.sh login' ou editando o arquivo .env!"
    fi

    # Cria o ambiente virtual
    if [ ! -d "$VENV_DIR" ]; then
        echo "Criando ambiente virtual ($VENV_DIR)..."
        python3 -m venv "$VENV_DIR"
    else
        echo "Ambiente virtual já existe."
    fi

    # Ativa e instala dependências
    source "$VENV_DIR/bin/activate"
    echo "Atualizando pip..."
    pip install --upgrade pip > /dev/null
    
    echo "Instalando dependências do requirements.txt..."
    pip install -r requirements.txt
    
    echo "Baixando navegador Chromium do Playwright..."
    playwright install chromium

    echo ""
    echo "=== AMBIENTE PRONTO ==="
    echo "Próximos passos:"
    echo "  1. Configure suas próprias credenciais: ./start.sh login"
    echo "  2. Ative o ambiente virtual no terminal: source venv/bin/activate"
}

function configurar_login() {
    echo "=== CONFIGURAR SEU LOGIN E SENHA ==="
    echo "Isso substituirá as credenciais do arquivo .env pelos SEUS dados"
    echo "e limpará qualquer sessão antiga salva no navegador (.flow_profile)."
    echo ""

    read -r -p "E-mail(s) da Kalodata (se tiver mais de um, separe por vírgula): " kalodata_logins
    read -r -s -p "Senha da Kalodata: " kalodata_password
    echo ""
    read -r -p "E-mail da sua conta Google (Google Flow): " google_login
    read -r -s -p "Senha da sua conta Google: " google_password
    echo ""

    if [ -z "$kalodata_logins" ] || [ -z "$kalodata_password" ]; then
        echo "[!] E-mail e senha da Kalodata são obrigatórios. Operação cancelada."
        exit 1
    fi

    cat <<EOF > .env
# Credenciais configuradas via ./start.sh login
KALODATA_LOGINS=$kalodata_logins
KALODATA_PASSWORD=$kalodata_password
GOOGLE_LOGIN=$google_login
GOOGLE_PASSWORD=$google_password
EOF

    chmod 600 .env

    if [ -d "$FLOW_PROFILE_DIR" ]; then
        rm -rf "$FLOW_PROFILE_DIR"
        echo "Sessão antiga do Google Flow ($FLOW_PROFILE_DIR) removida para usar a sua conta."
    fi

    echo ""
    echo "=== CREDENCIAIS ATUALIZADAS COM SUCESSO ==="
    echo "Suas credenciais foram salvas em .env (protegido apenas para o seu usuário)."
}

function destroy() {
    echo "=== DESTRUINDO AMBIENTE ==="
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
        echo "Diretório '$VENV_DIR' removido com sucesso."
    else
        echo "Nenhum ambiente virtual encontrado para destruir."
    fi
    echo "Ambiente limpo. (Para trocar as credenciais e limpar o login salvo, use: ./start.sh login)"
}

# Processa os argumentos
case "$1" in
    setup)
        setup
        ;;
    login|credenciais)
        configurar_login
        ;;
    destroy)
        destroy
        ;;
    *)
        echo "Uso: $0 {setup|login|destroy}"
        echo "  setup   - Cria o ambiente virtual (venv), instala dependências e o navegador Chromium"
        echo "  login   - Configura SEU próprio login e senha (Kalodata e Google) e limpa sessão anterior"
        echo "  destroy - Remove o ambiente virtual (venv)"
        exit 1
        ;;
esac
