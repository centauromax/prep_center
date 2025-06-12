#!/bin/bash

echo "🔧 TEST: Endpoint debug WebhookEventProcessor"
echo "Monitoraggio deploy e test endpoint..."
echo ""

counter=1
max_attempts=20  # 3-4 minuti massimo

while [ $counter -le $max_attempts ]; do
    echo "[$counter/$max_attempts] Test $(date '+%H:%M:%S')..."
    
    # Test dell'endpoint debug
    response=$(curl -s -o /dev/null -w "%{http_code}" https://backend.fbaprepcenteritaly.com/prep_management/debug/webhook-processor/)
    
    if [ "$response" = "200" ]; then
        echo "✅ SUCCESS! Endpoint debug attivo (HTTP $response)"
        echo "🎉 Deploy completato dopo $((counter * 10)) secondi"
        echo ""
        echo "📊 STATO WEBHOOK PROCESSOR:"
        
        # Ottieni i dati di debug
        debug_data=$(curl -s https://backend.fbaprepcenteritaly.com/prep_management/debug/webhook-processor/)
        
        # Estrai informazioni chiave
        client_available=$(echo "$debug_data" | jq -r '.client_status.client_available // "unknown"')
        client_type=$(echo "$debug_data" | jq -r '.client_status.client_type // "none"')
        test_successful=$(echo "$debug_data" | jq -r '.client_test.test_successful // "unknown"')
        merchants_count=$(echo "$debug_data" | jq -r '.client_test.merchants_count // "unknown"')
        unprocessed_events=$(echo "$debug_data" | jq -r '.debug_info.unprocessed_events // "unknown"')
        outbound_closed_count=$(echo "$debug_data" | jq -r '.debug_info.outbound_closed_count // "unknown"')
        
        echo "🔧 Client disponibile: $client_available"
        echo "🔧 Tipo client: $client_type"
        echo "🧪 Test client riuscito: $test_successful"
        echo "👥 Merchants recuperati: $merchants_count"
        echo "⏳ Eventi non processati: $unprocessed_events"
        echo "📦 Eventi outbound.closed totali: $outbound_closed_count"
        
        echo ""
        echo "📋 ULTIMI EVENTI OUTBOUND.CLOSED:"
        echo "$debug_data" | jq -r '.recent_outbound_closed_events[] | "ID: \(.id) | Shipment: \(.shipment_id) | Processato: \(.processed) | Successo: \(.process_success) | Messaggio: \(.process_message // "nessuno")"'
        
        if [ "$client_available" = "true" ] && [ "$test_successful" = "true" ]; then
            echo ""
            echo "🎉 CLIENT FUNZIONA! La logica residuale dovrebbe essere attiva."
        else
            echo ""
            echo "❌ PROBLEMA CLIENT: La logica residuale NON funziona."
            echo "🔍 Dettagli errore:"
            echo "$debug_data" | jq '.client_test.error // "nessun errore specifico"'
        fi
        
        break
        
    elif [ "$response" = "404" ]; then
        echo "❌ DEPLOY NON ANCORA PRONTO (HTTP $response)"
    else
        echo "⚠️  Risposta inaspettata: HTTP $response"
    fi
    
    if [ $counter -eq $max_attempts ]; then
        echo "💥 TIMEOUT! Deploy non completato in tempo"
        exit 1
    fi
    
    sleep 10
    counter=$((counter + 1))
done 