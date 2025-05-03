from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Filtro template per accedere a un elemento di un dizionario usando una chiave.
    Uso in template: {{ my_dict|get_item:my_key }}
    """
    return dictionary.get(key, None) 