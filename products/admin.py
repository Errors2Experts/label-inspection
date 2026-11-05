from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'gtin', 'category', 'mrp', 'source')
    list_filter = ('source',)
    search_fields = ('name', 'brand', 'gtin', 'manufacturer')
    readonly_fields = ('gtin14', 'source_data', 'created_at', 'updated_at')
