from django.contrib import admin
from .models import PictureCheck, Cliente

@admin.register(PictureCheck)
class PictureCheckAdmin(admin.ModelAdmin):
    list_display = ('ean', 'cliente', 'data')
    list_filter = ('cliente', 'data')
    search_fields = ('ean', 'cliente')
    date_hierarchy = 'data'

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'attivo')
    list_filter = ('attivo',)
    search_fields = ('nome',) 