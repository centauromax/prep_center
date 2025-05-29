"""
Servizio per la generazione di PDF delle etichette pallet per Amazon.
"""

import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.conf import settings
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)


class PalletLabelPDFGenerator:
    """
    Generatore di PDF per etichette pallet Amazon.
    """
    
    def __init__(self):
        self.page_width, self.page_height = A4
        self.margin = 20 * mm
        self.content_width = self.page_width - 2 * self.margin
        
    def generate_pdf(self, pallet_label):
        """
        Genera il PDF per un'etichetta pallet.
        
        Args:
            pallet_label: Istanza del modello PalletLabel
            
        Returns:
            BytesIO: Buffer contenente il PDF generato
        """
        buffer = BytesIO()
        
        # Crea il documento PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin
        )
        
        # Costruisci il contenuto
        story = []
        
        # Header con titolo
        story.extend(self._build_header())
        story.append(Spacer(1, 15 * mm))
        
        # Informazioni principali del pallet
        story.extend(self._build_pallet_info(pallet_label))
        story.append(Spacer(1, 10 * mm))
        
        # Informazioni mittente e destinatario
        story.extend(self._build_addresses(pallet_label))
        story.append(Spacer(1, 10 * mm))
        
        # Dettagli spedizione
        story.extend(self._build_shipment_details(pallet_label))
        story.append(Spacer(1, 10 * mm))
        
        # Dettagli pallet
        story.extend(self._build_pallet_details(pallet_label))
        story.append(Spacer(1, 10 * mm))
        
        # Istruzioni speciali se presenti
        if pallet_label.special_instructions:
            story.extend(self._build_special_instructions(pallet_label))
            story.append(Spacer(1, 10 * mm))
        
        # Footer
        story.extend(self._build_footer())
        
        # Genera il PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    def _build_header(self):
        """Costruisce l'header del documento."""
        styles = getSampleStyleSheet()
        
        # Titolo principale
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=5 * mm,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1f4e79')
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#666666')
        )
        
        elements = [
            Paragraph("ETICHETTA PALLET AMAZON", title_style),
            Paragraph("Shipping Label for Amazon Warehouse", subtitle_style)
        ]
        
        return elements
    
    def _build_pallet_info(self, pallet_label):
        """Costruisce le informazioni principali del pallet."""
        styles = getSampleStyleSheet()
        
        # Stile per le informazioni principali
        info_style = ParagraphStyle(
            'PalletInfo',
            parent=styles['Normal'],
            fontSize=16,
            spaceAfter=3 * mm,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1f4e79'),
            fontName='Helvetica-Bold'
        )
        
        elements = [
            Paragraph(f"<b>PALLET ID: {pallet_label.pallet_id}</b>", info_style),
            Paragraph(f"<b>{pallet_label.pallet_description}</b>", info_style),
            Paragraph(f"<b>WAREHOUSE: {pallet_label.amazon_warehouse_code}</b>", info_style)
        ]
        
        return elements
    
    def _build_addresses(self, pallet_label):
        """Costruisce la sezione con indirizzi mittente e destinatario."""
        styles = getSampleStyleSheet()
        
        # Stili per gli indirizzi
        header_style = ParagraphStyle(
            'AddressHeader',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=3 * mm,
            textColor=colors.HexColor('#1f4e79'),
            fontName='Helvetica-Bold'
        )
        
        address_style = ParagraphStyle(
            'Address',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=1 * mm
        )
        
        # Costruisci gli indirizzi
        sender_address = [
            Paragraph("DA / FROM:", header_style),
            Paragraph(f"<b>{pallet_label.sender_name}</b>", address_style),
            Paragraph(pallet_label.sender_address_line1, address_style)
        ]
        
        if pallet_label.sender_address_line2:
            sender_address.append(Paragraph(pallet_label.sender_address_line2, address_style))
        
        sender_address.extend([
            Paragraph(f"{pallet_label.sender_postal_code} {pallet_label.sender_city}", address_style),
            Paragraph(pallet_label.sender_country, address_style)
        ])
        
        recipient_address = [
            Paragraph("A / TO:", header_style),
            Paragraph(f"<b>{pallet_label.amazon_warehouse_name}</b>", address_style),
            Paragraph(f"<b>Warehouse Code: {pallet_label.amazon_warehouse_code}</b>", address_style),
            Paragraph(pallet_label.amazon_address_line1, address_style)
        ]
        
        if pallet_label.amazon_address_line2:
            recipient_address.append(Paragraph(pallet_label.amazon_address_line2, address_style))
        
        recipient_address.extend([
            Paragraph(f"{pallet_label.amazon_postal_code} {pallet_label.amazon_city}", address_style),
            Paragraph(pallet_label.amazon_country, address_style)
        ])
        
        # Crea tabella con gli indirizzi
        address_table = Table(
            [[sender_address, recipient_address]],
            colWidths=[self.content_width / 2, self.content_width / 2]
        )
        
        address_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10 * mm),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc'))
        ]))
        
        return [address_table]
    
    def _build_shipment_details(self, pallet_label):
        """Costruisce i dettagli della spedizione."""
        styles = getSampleStyleSheet()
        
        header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=5 * mm,
            textColor=colors.HexColor('#1f4e79'),
            fontName='Helvetica-Bold'
        )
        
        # Dati della spedizione
        shipment_data = [
            ['Shipment ID:', pallet_label.shipment_id],
            ['Data creazione:', pallet_label.created_at.strftime('%d/%m/%Y %H:%M')],
        ]
        
        if pallet_label.po_number:
            shipment_data.append(['PO Number:', pallet_label.po_number])
        
        if pallet_label.carrier:
            shipment_data.append(['Corriere:', pallet_label.carrier])
        
        if pallet_label.tracking_number:
            shipment_data.append(['Tracking:', pallet_label.tracking_number])
        
        shipment_table = Table(shipment_data, colWidths=[40 * mm, 80 * mm])
        shipment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ]))
        
        return [
            Paragraph("DETTAGLI SPEDIZIONE / SHIPMENT DETAILS", header_style),
            shipment_table
        ]
    
    def _build_pallet_details(self, pallet_label):
        """Costruisce i dettagli del pallet."""
        styles = getSampleStyleSheet()
        
        header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=5 * mm,
            textColor=colors.HexColor('#1f4e79'),
            fontName='Helvetica-Bold'
        )
        
        # Dati del pallet
        pallet_data = [
            ['Numero scatole:', str(pallet_label.total_boxes)],
            ['Peso:', f"{pallet_label.pallet_weight} kg"],
            ['Dimensioni (L×W×H):', f"{pallet_label.pallet_dimensions_length}×{pallet_label.pallet_dimensions_width}×{pallet_label.pallet_dimensions_height} cm"],
        ]
        
        if pallet_label.total_volume_cbm > 0:
            pallet_data.append(['Volume:', f"{pallet_label.total_volume_cbm:.3f} m³"])
        
        pallet_table = Table(pallet_data, colWidths=[40 * mm, 80 * mm])
        pallet_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ]))
        
        return [
            Paragraph("DETTAGLI PALLET / PALLET DETAILS", header_style),
            pallet_table
        ]
    
    def _build_special_instructions(self, pallet_label):
        """Costruisce la sezione istruzioni speciali."""
        styles = getSampleStyleSheet()
        
        header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading3'],
            fontSize=12,
            spaceAfter=5 * mm,
            textColor=colors.HexColor('#1f4e79'),
            fontName='Helvetica-Bold'
        )
        
        instruction_style = ParagraphStyle(
            'Instructions',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=3 * mm
        )
        
        return [
            Paragraph("ISTRUZIONI SPECIALI / SPECIAL INSTRUCTIONS", header_style),
            Paragraph(pallet_label.special_instructions, instruction_style)
        ]
    
    def _build_footer(self):
        """Costruisce il footer del documento."""
        styles = getSampleStyleSheet()
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#666666')
        )
        
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        return [
            Spacer(1, 10 * mm),
            Paragraph(f"Generato il {timestamp} - Prep Center Italy", footer_style)
        ]


def generate_pallet_label_pdf(pallet_label):
    """
    Funzione di utilità per generare il PDF di un'etichetta pallet.
    
    Args:
        pallet_label: Istanza del modello PalletLabel
        
    Returns:
        ContentFile: File PDF pronto per essere salvato
    """
    try:
        generator = PalletLabelPDFGenerator()
        pdf_buffer = generator.generate_pdf(pallet_label)
        
        # Crea il nome del file
        filename = f"pallet_label_{pallet_label.pallet_id}_{pallet_label.pallet_number}.pdf"
        
        # Crea il ContentFile
        pdf_file = ContentFile(pdf_buffer.getvalue(), name=filename)
        
        return pdf_file
        
    except Exception as e:
        logger.error(f"Errore nella generazione del PDF per pallet {pallet_label.pallet_id}: {str(e)}")
        raise 