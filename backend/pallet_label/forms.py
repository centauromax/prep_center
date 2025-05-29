from django import forms
from .models import PalletLabel


class PalletLabelForm(forms.ModelForm):
    """
    Form per la creazione di etichette pallet per Amazon.
    """
    
    class Meta:
        model = PalletLabel
        exclude = ['created_by', 'created_at', 'updated_at', 'pdf_generated', 'pdf_file']
        
        widgets = {
            'pallet_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Es: PLT-001'
            }),
            'sender_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome della tua azienda'
            }),
            'sender_address_line1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Via/Piazza e numero civico'
            }),
            'sender_address_line2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Interno, scala, ecc. (opzionale)'
            }),
            'sender_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Città'
            }),
            'sender_postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'CAP'
            }),
            'sender_country': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'amazon_warehouse_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Es: MXP5, LIN1, FCO1'
            }),
            'amazon_warehouse_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome del warehouse Amazon'
            }),
            'amazon_address_line1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Indirizzo del warehouse Amazon'
            }),
            'amazon_address_line2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Informazioni aggiuntive indirizzo (opzionale)'
            }),
            'amazon_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Città del warehouse'
            }),
            'amazon_postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'CAP del warehouse'
            }),
            'amazon_country': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'shipment_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID della spedizione Amazon'
            }),
            'po_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numero Purchase Order (opzionale)'
            }),
            'pallet_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'pallet_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'total_boxes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'pallet_weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'pallet_dimensions_length': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'pallet_dimensions_width': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'pallet_dimensions_height': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'carrier': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome del corriere (opzionale)'
            }),
            'tracking_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numero di tracking (opzionale)'
            }),
            'special_instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Istruzioni speciali per la consegna (opzionale)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Aggiungi validazione JavaScript per il numero pallet
        self.fields['pallet_number'].widget.attrs.update({
            'onchange': 'validatePalletNumber()'
        })
        self.fields['pallet_count'].widget.attrs.update({
            'onchange': 'validatePalletNumber()'
        })
    
    def clean(self):
        cleaned_data = super().clean()
        pallet_number = cleaned_data.get('pallet_number')
        pallet_count = cleaned_data.get('pallet_count')
        
        if pallet_number and pallet_count:
            if pallet_number > pallet_count:
                raise forms.ValidationError(
                    "Il numero del pallet corrente non può essere maggiore del numero totale di pallet."
                )
        
        return cleaned_data


class QuickPalletForm(forms.Form):
    """
    Form semplificata per la creazione rapida di etichette con dati precompilati.
    """
    
    # Dati essenziali del pallet
    pallet_id = forms.CharField(
        max_length=100,
        label="ID Pallet",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Es: PLT-001'
        })
    )
    
    amazon_warehouse_code = forms.CharField(
        max_length=10,
        label="Codice Warehouse Amazon",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Es: MXP5, LIN1'
        })
    )
    
    shipment_id = forms.CharField(
        max_length=100,
        label="ID Spedizione",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Shipment ID Amazon'
        })
    )
    
    total_boxes = forms.IntegerField(
        label="Numero Scatole",
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        })
    )
    
    pallet_weight = forms.DecimalField(
        label="Peso (kg)",
        max_digits=8,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    # Opzioni per pallet multipli
    pallet_count = forms.IntegerField(
        label="Numero totale pallet",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        })
    )
    
    generate_all = forms.BooleanField(
        label="Genera etichette per tutti i pallet",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    ) 