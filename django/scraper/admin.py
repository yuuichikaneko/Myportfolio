from django.contrib import admin
from .models import PCPart, Configuration, ScraperStatus


@admin.register(PCPart)
class PCPartAdmin(admin.ModelAdmin):
    list_display = ['name', 'part_type', 'price', 'updated_at']
    list_filter = ['part_type', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['scraped_at', 'updated_at']


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ['id', 'usage', 'budget', 'total_price', 'created_at']
    list_filter = ['usage', 'created_at']
    readonly_fields = ['created_at']


@admin.register(ScraperStatus)
class ScraperStatusAdmin(admin.ModelAdmin):
    list_display = ['last_run', 'total_scraped', 'success_count', 'error_count', 'cache_enabled']
    readonly_fields = ['updated_at']

