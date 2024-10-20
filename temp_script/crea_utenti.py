from django.contrib.auth.models import User, Group

# Definisci gli utenti da creare e i loro gruppi
users = [
    {'username': 'adriano', 'password': 'AdrianoPassword123', 'email': 'info@wifiexpress.it', 'group': 'Admin'},
]

# Creare gli utenti e assegnarli ai gruppi
for user_data in users:
    # Crea l'utente se non esiste
    user, created = User.objects.get_or_create(username=user_data['username'], email=user_data['email'])
    
    if created:
        user.set_password(user_data['password'])
        user.save()
        print(f"User '{user_data['username']}' created.")
    else:
        print(f"User '{user_data['username']}' already exists.")
    
    # Assegna l'utente al gruppo
    group = Group.objects.get(name=user_data['group'])
    user.groups.add(group)
    print(f"User '{user_data['username']}' added to group '{user_data['group']}'.")
