"""
Comando wrapper per eseguire altri comandi Django con timeout automatico.
Utile per comandic che potrebbero rimanere bloccati nell'attesa di input o log.
"""

import signal
import sys
import subprocess
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class TimeoutError(Exception):
    """Eccezione per timeout."""
    pass


def timeout_handler(signum, frame):
    """Handler per il timeout."""
    raise TimeoutError("Comando terminato dopo 30 secondi di timeout")


class Command(BaseCommand):
    help = 'Esegue un comando Django con timeout automatico di 30 secondi'

    def add_arguments(self, parser):
        parser.add_argument(
            'command', 
            type=str,
            help='Nome del comando da eseguire (es. test_messaging)'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout in secondi (default: 30)'
        )
        parser.add_argument(
            'args',
            nargs='*',
            help='Argomenti da passare al comando'
        )

    def handle(self, *args, **options):
        command = options['command']
        timeout = options['timeout']
        command_args = options['args']
        
        self.stdout.write(f'🕐 Eseguendo comando "{command}" con timeout di {timeout} secondi...')
        self.stdout.write(f'📝 Argomenti: {" ".join(command_args)}')
        
        # Imposta il gestore del segnale per il timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        try:
            # Costruisce il comando completo
            cmd_parts = ['python', 'manage.py', command] + command_args
            
            # Esegue il comando come subprocess
            process = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Legge l'output in tempo reale
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Stampa l'output del comando senza newline aggiuntive
                    self.stdout.write(output.strip())
            
            # Attende la fine del processo
            return_code = process.poll()
            
            # Legge eventuali errori
            stderr = process.stderr.read()
            if stderr:
                self.stderr.write(f'Errori: {stderr}')
            
            # Disabilita l'allarme se il comando termina naturalmente
            signal.alarm(0)
            
            if return_code == 0:
                self.stdout.write(self.style.SUCCESS(f'✅ Comando "{command}" completato con successo'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ Comando "{command}" terminato con errore (exit code: {return_code})'))
                
        except TimeoutError:
            # Termina il processo se ancora in esecuzione
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            
            self.stdout.write(self.style.WARNING(f'⏰ Comando "{command}" terminato automaticamente dopo {timeout} secondi'))
            self.stdout.write(self.style.SUCCESS('✅ Timeout applicato con successo - nessun blocco'))
            
        except KeyboardInterrupt:
            # Gestisce Ctrl+C
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            
            self.stdout.write(self.style.WARNING('⚠️ Comando interrotto dall\'utente'))
            
        except Exception as e:
            signal.alarm(0)  # Disabilita l'allarme
            self.stderr.write(self.style.ERROR(f'❌ Errore durante l\'esecuzione: {str(e)}'))
            raise CommandError(f'Errore nell\'esecuzione del comando: {str(e)}')
        
        finally:
            # Assicurati che l'allarme sia sempre disabilitato
            signal.alarm(0) 