#!/bin/bash

# Script intelligente per monitorare il deployment Railway
# Invece di aspettare un tempo fisso, monitora attivamente lo stato

set -e

BACKEND_URL="https://backend.fbaprepcenteritaly.com"
MAX_ATTEMPTS=30
SLEEP_INTERVAL=10
EXPECTED_COMMIT_HASH=""

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

# Funzione per ottenere l'ultimo commit hash locale
get_local_commit_hash() {
    git rev-parse HEAD
}

# Funzione per verificare se il backend risponde
check_backend_health() {
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL" || echo "000")
    
    if [[ "$http_code" =~ ^[23][0-9][0-9]$ ]]; then
        return 0  # Success
    else
        return 1  # Failure
    fi
}

# Funzione per ottenere lo status del deployment da Railway
get_deployment_status() {
    # Prova prima con railway status, poi fallback su test HTTP
    local railway_hash
    railway_hash=$(railway status --json 2>/dev/null | jq -r '.services.edges[0].node.serviceInstances.edges[0].node.latestDeployment.meta.commitHash' 2>/dev/null || echo "unknown")
    
    if [[ "$railway_hash" != "unknown" && "$railway_hash" != "null" ]]; then
        echo "$railway_hash"
    else
        # Fallback: prova a ottenere info dal backend stesso
        local backend_info
        backend_info=$(curl -s "$BACKEND_URL/prep_management/api-debug/" 2>/dev/null | grep -o '"commit_hash":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
        echo "$backend_info"
    fi
}

# Funzione per verificare se il deployment è completo
check_deployment_complete() {
    local current_commit_hash
    current_commit_hash=$(get_deployment_status)
    
    # Se non riusciamo a ottenere l'hash, consideriamo il deployment non completo
    if [[ "$current_commit_hash" == "unknown" || "$current_commit_hash" == "null" || -z "$current_commit_hash" ]]; then
        return 1
    fi
    
    # Confronta gli hash (primi 8 caratteri per compatibilità)
    local expected_short="${EXPECTED_COMMIT_HASH:0:8}"
    local current_short="${current_commit_hash:0:8}"
    
    if [[ "$current_short" == "$expected_short" ]]; then
        return 0  # Deployment complete
    else
        return 1  # Still deploying
    fi
}

# Funzione per test più robusto del backend
check_backend_health_robust() {
    local health_checks=0
    local max_health_checks=3
    
    # Test multipli per essere sicuri
    for i in $(seq 1 $max_health_checks); do
        if check_backend_health; then
            ((health_checks++))
        fi
        sleep 2
    done
    
    # Richiede almeno 2 su 3 test positivi
    if [[ $health_checks -ge 2 ]]; then
        return 0
    else
        return 1
    fi
}

# Funzione per testare un endpoint specifico (opzionale)
test_specific_endpoint() {
    local endpoint="$1"
    local expected_status="${2:-200}"
    
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL$endpoint" || echo "000")
    
    if [[ "$http_code" == "$expected_status" ]]; then
        return 0
    else
        return 1
    fi
}

# Main function
main() {
    log_info "🚀 Monitoraggio deployment Railway intelligente"
    
    # Ottieni l'hash del commit locale
    EXPECTED_COMMIT_HASH=$(get_local_commit_hash)
    log_info "Commit hash atteso: $EXPECTED_COMMIT_HASH"
    
    # Verifica iniziale
    log_info "Verifica stato iniziale..."
    if check_backend_health_robust; then
        log_info "✅ Backend risponde"
    else
        log_warning "⚠️  Backend non risponde ancora"
    fi
    
    # Loop di monitoraggio
    local attempt=1
    local deployment_ready=false
    local backend_healthy=false
    
    while [[ $attempt -le $MAX_ATTEMPTS ]]; do
        log_info "Tentativo $attempt/$MAX_ATTEMPTS..."
        
        # Controlla se il deployment è completo
        if check_deployment_complete; then
            if [[ "$deployment_ready" == false ]]; then
                log_success "✅ Deployment completato (commit hash corretto)"
                deployment_ready=true
            fi
        else
            current_hash=$(get_deployment_status)
            log_info "Deployment in corso... (hash attuale: $current_hash)"
        fi
        
        # Controlla se il backend è healthy
        if check_backend_health_robust; then
            if [[ "$backend_healthy" == false ]]; then
                log_success "✅ Backend risponde correttamente"
                backend_healthy=true
            fi
        else
            log_warning "⚠️  Backend non risponde ancora"
            backend_healthy=false
        fi
        
        # Se entrambi sono pronti, esci
        if [[ "$deployment_ready" == true && "$backend_healthy" == true ]]; then
            log_success "🎉 Deployment completato e backend operativo!"
            
            # Test opzionali di endpoint specifici
            log_info "Test endpoint specifici..."
            
            if test_specific_endpoint "/prep_management/api-debug/" "200"; then
                log_success "✅ API Debug endpoint funzionante"
            else
                log_warning "⚠️  API Debug endpoint non risponde come atteso"
            fi
            
            if test_specific_endpoint "/prep_management/merchants/" "200"; then
                log_success "✅ Merchants endpoint funzionante"
            else
                log_warning "⚠️  Merchants endpoint non risponde come atteso"
            fi
            
            return 0
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
    log_error "Deployment potrebbe non essere completato o backend non risponde"
    return 1
}

# Esegui solo se chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 