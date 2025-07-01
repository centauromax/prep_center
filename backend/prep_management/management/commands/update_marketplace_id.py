from django.core.management.base import BaseCommand
from prep_management.models import AmazonSPAPIConfig


class Command(BaseCommand):
    help = 'Aggiorna marketplace_id per configurazione Amazon SP-API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config-id',
            type=int,
            default=1,
            help='ID della configurazione da aggiornare (default: 1)'
        )
        parser.add_argument(
            '--marketplace-id',
            type=str,
            default='APJ6JRA9NG5V4',
            help='Marketplace ID da impostare (default: APJ6JRA9NG5V4 per Amazon.it)'
        )

    def handle(self, *args, **options):
        config_id = options['config_id']
        marketplace_id = options['marketplace_id']
        
        try:
            config = AmazonSPAPIConfig.objects.get(id=config_id)
            old_marketplace_id = config.marketplace_id
            
            config.marketplace_id = marketplace_id
            config.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Configurazione {config.name} aggiornata:\n'
                    f'   Marketplace: {config.marketplace}\n'
                    f'   Marketplace ID: {old_marketplace_id} → {marketplace_id}\n'
                    f'   Status: Attivo={config.is_active}'
                )
            )
            
        except AmazonSPAPIConfig.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Configurazione con ID {config_id} non trovata')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Errore durante l\'aggiornamento: {str(e)}')
            ) 