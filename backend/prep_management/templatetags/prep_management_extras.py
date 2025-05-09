from django import template
import json

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Filtro template per accedere a un elemento di un dizionario usando una chiave.
    Uso in template: {{ my_dict|get_item:my_key }}
    """
    return dictionary.get(key, None)

@register.filter(name='add_to_list')
def add_to_list(value, arg):
    """
    Aggiunge un elemento a una lista.
    Uso in template: {% with new_list=my_list|add_to_list:new_item %}
    """
    return value + [arg]

@register.filter(name='pprint')
def pprint_json(value):
    """
    Formatta un oggetto JSON per visualizzarlo in modo leggibile.
    Uso in template: {{ my_json|pprint }}
    """
    if value is None:
        return "null"
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)

@register.filter
def get_range(value):
    """
    Filter - returns a list containing range made from given value
    Usage (in template):
    <ul>{% for i in 3|get_range %}
      <li>{{ i }}. Do something</li>
    {% endfor %}</ul>
    """
    return range(1, int(value) + 1) 