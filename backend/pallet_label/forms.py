from django import forms
from django.core.exceptions import ValidationError
import json


class PalletLabelForm(forms.Form):
    """
    Form per creare etichette pallet secondo i requisiti specifici.
    """
    nome_venditore = forms.CharField(
        max_length=200,
        label='Nome del venditore',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Es: Selley'
        })
    )
    
    nome_spedizione = forms.CharField(
        max_length=500,
        label='Nome spedizione',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Es: 904 - SINGER (USED RETURNS) Stiro Verticali (07/05/2025 07:52)-FC02'
        })
    )
    
    numero_spedizione = forms.CharField(
        max_length=100,
        label='Numero spedizione',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Es: FBA15KB85LXZ'
        })
    )
    
    indirizzo_spedizione = forms.CharField(
        max_length=500,
        label='Indirizzo di spedizione',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Es:\nAmazon.fr Logistique SAS\nParc d\'activites des Portes de Senlis\n1 avenue Alain Boucher\n60452 Senlis CEDEX\nFrancia'
        })
    )
    
    numero_pallet = forms.IntegerField(
        min_value=1,
        max_value=50,
        label='Numero di pallet',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Es: 3',
            'id': 'id_numero_pallet'
        })
    )
    
    # Campo nascosto per memorizzare i numeri di cartoni per ogni pallet
    cartoni_per_pallet = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'id_cartoni_per_pallet'}),
        required=False
    )
    
    def clean_numero_pallet(self):
        numero_pallet = self.cleaned_data['numero_pallet']
        if numero_pallet < 1:
            raise ValidationError('Il numero di pallet deve essere almeno 1.')
        if numero_pallet > 50:
            raise ValidationError('Il numero massimo di pallet è 50.')
        return numero_pallet
    
    def clean_cartoni_per_pallet(self):
        cartoni_data = self.cleaned_data.get('cartoni_per_pallet', '')
        numero_pallet = self.cleaned_data.get('numero_pallet', 0)
        
        if not cartoni_data:
            raise ValidationError('Devi specificare il numero di cartoni per ogni pallet.')
        
        try:
            cartoni_list = json.loads(cartoni_data)
        except (json.JSONDecodeError, TypeError):
            raise ValidationError('Dati cartoni non validi.')
        
        if not isinstance(cartoni_list, list):
            raise ValidationError('Dati cartoni non validi.')
        
        if len(cartoni_list) != numero_pallet:
            raise ValidationError(f'Devi specificare il numero di cartoni per tutti i {numero_pallet} pallet.')
        
        # Valida che ogni numero di cartoni sia valido
        for i, cartoni in enumerate(cartoni_list, 1):
            try:
                cartoni_int = int(cartoni)
                if cartoni_int < 1:
                    raise ValidationError(f'Il numero di cartoni per il pallet {i} deve essere almeno 1.')
                if cartoni_int > 1000:
                    raise ValidationError(f'Il numero massimo di cartoni per il pallet {i} è 1000.')
            except (ValueError, TypeError):
                raise ValidationError(f'Il numero di cartoni per il pallet {i} deve essere un numero valido.')
        
        return cartoni_list
    
    def get_cartoni_data(self):
        """
        Restituisce la lista dei numeri di cartoni per ogni pallet.
        """
        return self.cleaned_data.get('cartoni_per_pallet', []) 