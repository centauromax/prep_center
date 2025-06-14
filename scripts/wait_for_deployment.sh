#!/bin/bash

# Script semplificato per monitorare il deployment Railway
# Monitora il file di versione scritto dall'applicazione all'avvio

set -e

VERSION_FILE_URL="https://backend.fbaprepcenteritaly.com/prep_management/version-file/"
MAX_ATTEMPTS=30
SLEEP_INTERVAL=10

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Funzione per ottenere la versione attesa dal codice locale
get_expected_version() {
    grep "VERSION = " backend/prep_center/settings.py | cut -d'"' -f2 2>/dev/null || echo "unknown"
}

# Funzione per ottenere la versione corrente dal file remoto
get_current_version() {
    curl -s "$VERSION_FILE_URL" 2>/dev/null || echo "unknown"
}

# Main function
main() {
    log_info "🚀 Monitoraggio deployment Railway (versione semplificata)"
    
    # Ottieni la versione attesa
    local expected_version
    expected_version=$(get_expected_version)
    log_info "Versione attesa: $expected_version"
    
    if [[ "$expected_version" == "unknown" ]]; then
        log_error "❌ Impossibile leggere la versione dal file settings.py"
        return 1
    fi
    
    # Loop di monitoraggio
    local attempt=1
    
    while [[ $attempt -le $MAX_ATTEMPTS ]]; do
        log_info "Tentativo $attempt/$MAX_ATTEMPTS..."
        
        # Ottieni la versione corrente
        local current_version
        current_version=$(get_current_version)
        
        log_info "Versione corrente: $current_version"
        
        # Controlla se le versioni coincidono
        if [[ "$current_version" == "$expected_version" ]]; then
            log_success "✅ Deployment completato! Versione $current_version attiva"
            return 0
        else
            log_info "Deployment in corso... (attesa: $expected_version, corrente: $current_version)"
        fi
        
        # Aspetta prima del prossimo tentativo
        if [[ $attempt -lt $MAX_ATTEMPTS ]]; then
            log_info "Attesa ${SLEEP_INTERVAL}s prima del prossimo controllo..."
            sleep $SLEEP_INTERVAL
        fi
        
        ((attempt++))
    done
    
    # Timeout raggiunto
    log_error "❌ Timeout raggiunto dopo $((MAX_ATTEMPTS * SLEEP_INTERVAL)) secondi"
    log_error "Deployment potrebbe non essere completato"
    return 1
}

# Esegui solo se chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 