#!/bin/bash

# Script semplicissimo per monitorare il deployment Railway
# Controlla solo se il contenuto del file di versione cambia

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

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Funzione per ottenere il contenuto del file remoto
get_file_content() {
    curl -s "$VERSION_FILE_URL" 2>/dev/null || echo "error"
}

# Main function
main() {
    log_info "🚀 Monitoraggio deployment Railway (controllo cambio file)"
    
    # Leggi il contenuto iniziale
    local initial_content
    initial_content=$(get_file_content)
    log_info "Contenuto iniziale: '$initial_content'"
    
    # Se il contenuto iniziale è un errore, aspetta che diventi disponibile
    if [[ "$initial_content" == "error" || "$initial_content" == *"error"* || "$initial_content" == *"502"* || "$initial_content" == *"Not Found"* ]]; then
        log_info "File non ancora disponibile, aspetto che diventi accessibile..."
        
        # Aspetta che il file diventi disponibile
        local attempt=1
        while [[ $attempt -le $MAX_ATTEMPTS ]]; do
            log_info "Tentativo $attempt/$MAX_ATTEMPTS (aspetto disponibilità)..."
            
            local current_content
            current_content=$(get_file_content)
            
            # Se il contenuto non è più un errore, abbiamo il contenuto iniziale
            if [[ "$current_content" != "error" && "$current_content" != *"error"* && "$current_content" != *"502"* && "$current_content" != *"Not Found"* ]]; then
                initial_content="$current_content"
                log_info "File ora disponibile con contenuto: '$initial_content'"
                break
            fi
            
            if [[ $attempt -lt $MAX_ATTEMPTS ]]; then
                log_info "Attesa ${SLEEP_INTERVAL}s..."
                sleep $SLEEP_INTERVAL
            fi
            
            ((attempt++))
        done
        
        # Se ancora non disponibile, esci con errore
        if [[ "$initial_content" == "error" || "$initial_content" == *"error"* || "$initial_content" == *"502"* || "$initial_content" == *"Not Found"* ]]; then
            log_error "❌ File non è mai diventato disponibile"
            return 1
        fi
    fi
    
    # Ora monitora i cambiamenti
    log_info "Monitoraggio cambiamenti del file..."
    local attempt=1
    
    while [[ $attempt -le $MAX_ATTEMPTS ]]; do
        log_info "Controllo $attempt/$MAX_ATTEMPTS..."
        
        local current_content
        current_content=$(get_file_content)
        
        log_info "Contenuto attuale: '$current_content'"
        
        # Se il contenuto è cambiato, deployment completato
        if [[ "$current_content" != "$initial_content" ]]; then
            log_success "✅ Deployment completato! Contenuto cambiato da '$initial_content' a '$current_content'"
            return 0
        else
            log_info "Contenuto invariato, deployment in corso..."
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
    log_error "Il contenuto del file non è cambiato"
    return 1
}

# Esegui solo se chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 