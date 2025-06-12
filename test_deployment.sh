#!/bin/bash

echo "🚀 Monitoraggio deployment Railway..."
echo "Testando endpoint: https://backend.fbaprepcenteritaly.com/prep_management/webhook/shipment-status/"
echo ""

counter=1
max_attempts=30  # 5 minuti massimo (30 * 10 secondi)

while [ $counter -le $max_attempts ]; do
    echo "[$counter/$max_attempts] Tentativo $(date '+%H:%M:%S')..."
    
    # Test dell'endpoint webhook
    response=$(curl -s -o /dev/null -w "%{http_code}" https://backend.fbaprepcenteritaly.com/prep_management/webhook/shipment-status/)
    
    if [ "$response" = "405" ] || [ "$response" = "200" ]; then
        echo "✅ SUCCESS! Endpoint attivo (HTTP $response)"
        echo "🎉 Deploy completato dopo $((counter * 10)) secondi"
        break
    elif [ "$response" = "404" ]; then
        echo "⏳ Deploy in corso... (HTTP 404)"
    else
        echo "⚠️  Risposta inaspettata: HTTP $response"
    fi
    
    if [ $counter -eq $max_attempts ]; then
        echo "❌ TIMEOUT: Deploy non completato dopo $((max_attempts * 10)) secondi"
        break
    fi
    
    echo "   Prossimo test tra 10 secondi..."
    sleep 10
    counter=$((counter + 1))
done

echo ""
echo "📊 Test finale dell'endpoint:"
curl -I https://backend.fbaprepcenteritaly.com/prep_management/webhook/shipment-status/ 