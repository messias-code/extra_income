#!/bin/bash

# Nome do diretório do ambiente virtual
VENV_DIR="venv"

function setup() {
    echo "=== CRIANDO AMBIENTE ==="
    
    # Cria o arquivo .env se não existir
    if [ ! -f ".env" ]; then
        echo "Criando .env com placeholders..."
        echo "KALODATA_LOGINS=email1@gmail.com,email2@gmail.com" > .env
        echo "KALODATA_PASSWORD=sua_senha_aqui" >> .env
        echo "ATENÇÃO: Preencha suas credenciais no arquivo .env!"
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
    
    echo "Baixando navegadores do Playwright..."
    playwright install chromium

    echo "=== AMBIENTE PRONTO ==="
}

function destroy() {
    echo "=== DESTRUINDO AMBIENTE ==="
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
        echo "Diretório '$VENV_DIR' removido com sucesso."
    else
        echo "Nenhum ambiente virtual encontrado para destruir."
    fi
    echo "Ambiente limpo."
}

# Processa os argumentos
case "$1" in
    setup)
        setup
        ;;
    destroy)
        destroy
        ;;
    *)
        echo "Uso: $0 {setup|destroy}"
        exit 1
esac
