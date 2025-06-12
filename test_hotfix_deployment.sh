#!/bin/bash

echo "🚨 HOTFIX - Monitoraggio deploy per ripristino notifiche Telegram..."
echo "Testando endpoint: https://backend.fbaprepcenteritaly.com/prep_management/webhook/"
echo ""

counter=1
max_attempts=20  # 3-4 minuti massimo

while [ $counter -le $max_attempts ]; do
    echo "[$counter/$max_attempts] Tentativo $(date '+%H:%M:%S')..."
    
    # Test dell'endpoint webhook
    response=$(curl -s -o /dev/null -w "%{http_code}" https://backend.fbaprepcenteritaly.com/prep_management/webhook/)
    
    if [ "$response" = "405" ] || [ "$response" = "200" ]; then
        echo "✅ SUCCESS! Endpoint attivo (HTTP $response)"
        echo "🎉 Deploy completato dopo $((counter * 10)) secondi"
        
        # Test immediato con webhook che dovrebbe inviare notifica Telegram
        echo ""
        echo "🧪 TEST NOTIFICA TELEGRAM..."
        echo "Invio webhook per merchant 7812 (dovrebbe usare fallback email)..."
        
        test_response=$(curl -s -X POST https://backend.fbaprepcenteritaly.com/prep_management/webhook/ \
          -H "Content-Type: application/json" \
          -d '{
            "id": 999777,
            "name": "HOTFIX-TEST-TELEGRAM",
            "status": "closed",
            "shipped_at": "2025-06-12T15:00:00.000000Z",
            "team_id": 7812,
            "warehouse_id": 310,
            "notes": "Test hotfix - dovrebbe inviare notifica Telegram"
          }')
        
        echo "Risposta webhook: $test_response"
        echo ""
        echo "🔔 Controlla Telegram per la notifica di test!"
        echo "📧 Dovrebbe usare email fallback: prep@easyavant.com"
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