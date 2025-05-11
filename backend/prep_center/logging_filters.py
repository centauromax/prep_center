import logging

class TruncatingLogFilter(logging.Filter):
    def __init__(self, max_length=1000, placeholder='*****[PORZIONE DI LOG CANCELLATO]*****'):
        super().__init__()
        self.max_length = max_length
        self.placeholder = placeholder
        self.placeholder_len = len(placeholder)
        self.cut_len = (max_length - self.placeholder_len) // 2

    def filter(self, record):
        if hasattr(record, 'getMessage') and callable(record.getMessage):
            msg = record.getMessage()
            if len(msg) > self.max_length:
                if self.cut_len > 0:
                    record.msg = f"{msg[:self.cut_len]}{self.placeholder}{msg[-self.cut_len:]}"
                else:
                    # Se il placeholder è troppo lungo, tronca semplicemente
                    record.msg = msg[:self.max_length]
            # Se record.args è presente e il messaggio è stato modificato,
            # potrebbe essere necessario pulire args per evitare che logging provi a riformattare
            # Questo dipende da come è strutturato il logging, per ora lo lasciamo
            # se record.msg è stato cambiato, gli args originali non saranno usati per la formattazione di record.msg
        return True 