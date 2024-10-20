from django.contrib.auth.models import Group, Permission

# Definisci i gruppi e i relativi permessi (modifica come necessario)
group_names = ['Admin', 'PrepCenter', 'Client']

# Creare i gruppi se non esistono
for group_name in group_names:
    group, created = Group.objects.get_or_create(name=group_name)
    if created:
        print(f"Group '{group_name}' created.")
    else:
        print(f"Group '{group_name}' already exists.")


