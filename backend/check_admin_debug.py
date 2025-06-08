#!/usr/bin/env python3

"""
Script per verificare la configurazione admin nel database
"""

print("🔍 Debug Admin Chat System")
print("=" * 40)

print("\n📧 ADMIN_EMAIL dalla configurazione:")
print("   'info@fbaprepcenteritaly.com'")

print("\n🔎 Per risolvere l'errore, verifica su Railway:")
print("   1. Vai al Dashboard di Railway")
print("   2. Apri il Database/PostgreSQL")
print("   3. Esegui questa query:")

query = """
SELECT 
    email, 
    chat_id, 
    is_active, 
    username,
    first_name,
    created_at
FROM prep_management_telegramnotification 
WHERE email = 'info@fbaprepcenteritaly.com'
ORDER BY created_at DESC;
"""

print(f"\n💾 Query SQL:\n{query}")

print("\n🎯 Problemi possibili:")
print("   ❌ Admin non registrato con email 'info@fbaprepcenteritaly.com'")
print("   ❌ Admin registrato ma chat_id sbagliato (999999998 non esiste)")
print("   ❌ Admin registrato ma is_active = False")

print("\n🔧 Soluzioni:")
print("   1. L'admin deve scrivere /start al bot")
print("   2. L'admin deve registrarsi con 'info@fbaprepcenteritaly.com'")
print("   3. Verificare che il chat_id sia corretto")

print("\n📱 Verifica anche:")
print("   - L'admin ha mai scritto al bot Telegram?")
print("   - Il bot può inviare messaggi all'admin?")
print("   - L'email admin è esattamente 'info@fbaprepcenteritaly.com'?")

print("\n🚀 Alternativa temporanea:")
print("   - Commenta il codice che invia all'admin")
print("   - Testa prima solo la comunicazione cliente-cliente")
print("   - Poi aggiungi l'admin una volta registrato correttamente") 