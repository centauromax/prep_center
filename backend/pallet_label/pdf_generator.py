"""
Generatore PDF per etichette pallet secondo il formato richiesto.
Basato sull'immagine fornita dall'utente.
"""

from io import BytesIO
from django.core.files.base import ContentFile

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_pallet_label_pdf(pallet_label):
    """
    Genera il PDF per l'etichetta pallet secondo il formato richiesto.
    
    Il PDF è formato da:
    - Parte superiore: uguale per tutti i pallet
      - Venditore: nome_venditore
      - Nome spedizione: nome_spedizione  
      - Numero spedizione: numero_spedizione
      - Origine spedizione: origine_spedizione (fisso)
      - Indirizzo di spedizione: indirizzo_spedizione
    - Parte inferiore: specifica per ogni pallet
      - Numero di cartoni: numero_cartoni
      - Pallet n. X di Y
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("ReportLab non è disponibile")
    
    # Crea buffer per il PDF
    buffer = BytesIO()
    
    # Configurazione pagina A4
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    
    # Margini
    margin_left = 2 * cm
    margin_right = 2 * cm
    margin_top = 2 * cm
    margin_bottom = 2 * cm
    
    content_width = width - margin_left - margin_right
    content_height = height - margin_top - margin_bottom
    
    # Posizioni Y (dall'alto verso il basso)
    y_position = height - margin_top
    
    # Titolo - Venditore
    c.setFont("Helvetica-Bold", 24)
    vendor_text = f"Venditore: {pallet_label.nome_venditore}"
    c.drawString(margin_left, y_position, vendor_text)
    y_position -= 40
    
    # Linea separatrice
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(margin_left, y_position, width - margin_right, y_position)
    y_position -= 30
    
    # PARTE SUPERIORE - Dati della spedizione (uguale per tutti i pallet)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_left, y_position, "Nome spedizione:")
    y_position -= 20
    
    # Nome spedizione (può essere lungo, dividi su più righe se necessario)
    c.setFont("Helvetica", 12)
    nome_spedizione = pallet_label.nome_spedizione
    if len(nome_spedizione) > 80:  # Se troppo lungo, spezza
        lines = []
        words = nome_spedizione.split()
        current_line = ""
        for word in words:
            if len(current_line + " " + word) <= 80:
                current_line += " " + word if current_line else word
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        for line in lines:
            c.drawString(margin_left, y_position, line)
            y_position -= 18
    else:
        c.drawString(margin_left, y_position, nome_spedizione)
        y_position -= 25
    
    # Numero spedizione
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_left, y_position, "Numero spedizione:")
    y_position -= 20
    c.setFont("Helvetica", 12)
    c.drawString(margin_left, y_position, pallet_label.numero_spedizione)
    y_position -= 30
    
    # Origine spedizione
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_left, y_position, "Origine spedizione:")
    y_position -= 20
    c.setFont("Helvetica", 12)
    c.drawString(margin_left, y_position, pallet_label.origine_spedizione)
    y_position -= 30
    
    # Indirizzo di spedizione
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_left, y_position, "Indirizzo di spedizione:")
    y_position -= 20
    c.setFont("Helvetica", 12)
    
    # Indirizzo può essere su più righe
    indirizzo_lines = pallet_label.indirizzo_spedizione.split('\n')
    for line in indirizzo_lines:
        c.drawString(margin_left, y_position, line.strip())
        y_position -= 18
    
    y_position -= 20
    
    # Linea separatrice centrale
    c.setStrokeColor(colors.gray)
    c.setLineWidth(2)
    c.line(margin_left, y_position, width - margin_right, y_position)
    y_position -= 40
    
    # PARTE INFERIORE - Dati specifici del pallet (varia per ogni pallet)
    
    # Numero di cartoni - GRANDE e prominente
    c.setFont("Helvetica-Bold", 32)
    cartoni_text = f"Numero di cartoni: {pallet_label.numero_cartoni}"
    c.drawString(margin_left, y_position, cartoni_text)
    y_position -= 60
    
    # Pallet n. X di Y - GRANDE e prominente
    c.setFont("Helvetica-Bold", 32)
    pallet_text = f"Pallet n. {pallet_label.pallet_numero} di {pallet_label.pallet_totale}"
    c.drawString(margin_left, y_position, pallet_text)
    
    # Footer con informazioni tecniche (piccolo)
    footer_y = margin_bottom + 10
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.gray)
    timestamp = pallet_label.created_at.strftime("%d/%m/%Y %H:%M")
    footer_text = f"Generato il {timestamp} - ID: {pallet_label.pk}"
    c.drawString(margin_left, footer_y, footer_text)
    
    # Finalizza il PDF
    c.save()
    
    # Ritorna il file
    buffer.seek(0)
    pdf_file = ContentFile(buffer.read(), name=pallet_label.pdf_filename)
    buffer.close()
    
    return pdf_file 