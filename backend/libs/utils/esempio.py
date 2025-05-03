"""
Funzioni di esempio per dimostrare l'uso della libreria condivisa.
"""

def formatta_ean(ean):
    """
    Formatta un codice EAN per visualizzazione o elaborazione.
    
    Args:
        ean (str): Il codice EAN da formattare
        
    Returns:
        str: EAN formattato
    """
    if len(ean) == 13 and ean.isdigit():
        return f"{ean[0]}-{ean[1:7]}-{ean[7:13]}"
    elif len(ean) == 12 and ean.isdigit():
        return f"{ean[0:6]}-{ean[6:12]}"
    elif len(ean) == 10 and ean.isalnum():
        # Formato FNSKU (Amazon)
        return ean.upper()
    else:
        return ean 