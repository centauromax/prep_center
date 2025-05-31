"""
Generatore PDF per etichette pallet secondo il formato richiesto.
Genera un unico PDF con tutte le etichette della spedizione, una per pagina.
"""

from io import BytesIO
from django.core.files.base import ContentFile

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm, cm
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Paragraph
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_shipment_labels_pdf(pallet_labels_queryset):
    """
    Genera un unico PDF con tutte le etichette di una spedizione.
    Ogni etichetta occupa una pagina intera in formato A4 landscape.
    
    Args:
        pallet_labels_queryset: QuerySet di PalletLabel della stessa spedizione
    
    Returns:
        ContentFile: File PDF pronto per il download
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("ReportLab non è disponibile")
    
    if not pallet_labels_queryset.exists():
        raise ValueError("Nessuna etichetta da generare")
    
    # Ordina i pallet per numero
    pallet_labels = list(pallet_labels_queryset.order_by('pallet_numero'))
    first_label = pallet_labels[0]
    
    # Crea buffer per il PDF
    buffer = BytesIO()
    
    # Configurazione pagina A4 landscape
    page_width, page_height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    # Margini
    margin_left = 2 * cm
    margin_right = 2 * cm
    margin_top = 2 * cm
    margin_bottom = 1.5 * cm  # Ridotto perché non c'è footer
    
    content_width = page_width - margin_left - margin_right
    content_height = page_height - margin_top - margin_bottom
    
    # Genera una pagina per ogni etichetta pallet
    for i, pallet_label in enumerate(pallet_labels):
        if i > 0:  # Aggiungi nuova pagina dal secondo pallet in poi
            c.showPage()
        
        # Posizione Y iniziale (dall'alto verso il basso)
        y_position = page_height - margin_top
        
        # Titolo principale - Venditore
        c.setFont("Helvetica-Bold", 34)
        vendor_text = f"Venditore: {pallet_label.nome_venditore}"
        c.drawString(margin_left, y_position, vendor_text)
        y_position -= 50
        
        # Linea separatrice principale
        c.setStrokeColor(colors.black)
        c.setLineWidth(2)
        c.line(margin_left, y_position, page_width - margin_right, y_position)
        y_position -= 40
        
        # PARTE SUPERIORE - Dati della spedizione (uguale per tutti i pallet)
        
        # Nome spedizione
        c.setFont("Helvetica-Bold", 18)
        c.drawString(margin_left, y_position, "Nome spedizione:")
        y_position -= 25
        
        c.setFont("Helvetica", 15)
        nome_spedizione = pallet_label.nome_spedizione
        # Gestione testo lungo su più righe
        if len(nome_spedizione) > 100:  # Adattato per landscape
            lines = []
            words = nome_spedizione.split()
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= 100:
                    current_line += " " + word if current_line else word
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            for line in lines:
                c.drawString(margin_left, y_position, line)
                y_position -= 20
        else:
            c.drawString(margin_left, y_position, nome_spedizione)
            y_position -= 30
        
        # Numero spedizione
        c.setFont("Helvetica-Bold", 18)
        c.drawString(margin_left, y_position, "Numero spedizione:")
        y_position -= 25
        c.setFont("Helvetica", 15)
        c.drawString(margin_left, y_position, pallet_label.numero_spedizione)
        y_position -= 35
        
        # Origine spedizione
        c.setFont("Helvetica-Bold", 18)
        c.drawString(margin_left, y_position, "Origine spedizione:")
        y_position -= 25
        c.setFont("Helvetica", 15)
        origine_lines = pallet_label.origine_spedizione.split('\n')
        for line in origine_lines:
            if line.strip():
                c.drawString(margin_left, y_position, line.strip())
                y_position -= 20
        y_position -= 15
        
        # Indirizzo di spedizione
        c.setFont("Helvetica-Bold", 18)  # Aumentato del 10% da 16 a 18
        c.drawString(margin_left, y_position, "Indirizzo di spedizione:")
        y_position -= 25
        c.setFont("Helvetica", 15)  # Aumentato del 10% da 14 a 15
        
        # Tratta l'indirizzo come riga unica (già convertito dal JavaScript)
        indirizzo_text = pallet_label.indirizzo_spedizione.strip()
        if indirizzo_text:
            # Gestione testo lungo su più righe se necessario
            if len(indirizzo_text) > 120:  # Limite caratteri per landscape
                words = indirizzo_text.split()
                lines = []
                current_line = ""
                for word in words:
                    if len(current_line + " " + word) <= 120:
                        current_line += " " + word if current_line else word
                    else:
                        lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)
                
                for line in lines:
                    c.drawString(margin_left, y_position, line)
                    y_position -= 20
            else:
                c.drawString(margin_left, y_position, indirizzo_text)
                y_position -= 20
        
        y_position -= 25
        
        # Linea separatrice centrale
        c.setStrokeColor(colors.gray)
        c.setLineWidth(3)
        c.line(margin_left, y_position, page_width - margin_right, y_position)
        y_position -= 50
        
        # PARTE INFERIORE - Dati specifici del pallet (varia per ogni pallet)
        
        # Numero di cartoni - MOLTO GRANDE e prominente
        c.setFont("Helvetica-Bold", 40)
        cartoni_text = f"Numero di cartoni: {pallet_label.numero_cartoni}"
        c.drawString(margin_left, y_position, cartoni_text)
        y_position -= 80
        
        # Pallet n. X di Y - MOLTO GRANDE e prominente
        c.setFont("Helvetica-Bold", 40)
        pallet_text = f"Pallet n. {pallet_label.pallet_numero} di {pallet_label.pallet_totale}"
        c.drawString(margin_left, y_position, pallet_text)
        
        # Nessun footer come richiesto
    
    # Finalizza il PDF
    c.save()
    
    # Ritorna il file
    buffer.seek(0)
    
    # Nome file basato sulla spedizione
    filename = f"etichette_spedizione_{first_label.numero_spedizione}.pdf"
    pdf_file = ContentFile(buffer.read(), name=filename)
    buffer.close()
    
    return pdf_file


def generate_pallet_label_pdf(pallet_label):
    """
    Wrapper per compatibilità: genera PDF per singolo pallet.
    In realtà genera PDF per tutta la spedizione.
    """
    from .models import PalletLabel
    
    # Trova tutte le etichette della stessa spedizione
    shipment_labels = PalletLabel.objects.filter(
        numero_spedizione=pallet_label.numero_spedizione
    )
    
    return generate_shipment_labels_pdf(shipment_labels) 