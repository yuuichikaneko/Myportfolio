from rest_framework import serializers
from .models import PCPart, Configuration, ScraperStatus


class PCPartSerializer(serializers.ModelSerializer):
    part_type_display = serializers.CharField(source='get_part_type_display', read_only=True)
    
    class Meta:
        model = PCPart
        fields = ['id', 'part_type', 'part_type_display', 'name', 'price', 'specs', 'url', 'scraped_at', 'updated_at']
        read_only_fields = ['id', 'scraped_at', 'updated_at']


class ConfigurationSerializer(serializers.ModelSerializer):
    usage_display = serializers.CharField(source='get_usage_display', read_only=True)
    cpu_data = PCPartSerializer(source='cpu', read_only=True)
    gpu_data = PCPartSerializer(source='gpu', read_only=True)
    motherboard_data = PCPartSerializer(source='motherboard', read_only=True)
    memory_data = PCPartSerializer(source='memory', read_only=True)
    storage_data = PCPartSerializer(source='storage', read_only=True)
    psu_data = PCPartSerializer(source='psu', read_only=True)
    case_data = PCPartSerializer(source='case', read_only=True)
    
    class Meta:
        model = Configuration
        fields = [
            'id', 'budget', 'usage', 'usage_display', 'total_price',
            'cpu', 'gpu', 'motherboard', 'memory', 'storage', 'psu', 'case',
            'cpu_data', 'gpu_data', 'motherboard_data', 'memory_data', 'storage_data', 'psu_data', 'case_data',
            'created_at'
        ]
        read_only_fields = ['id', 'total_price', 'created_at']


class ScraperStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScraperStatus
        fields = ['id', 'last_run', 'next_run', 'total_scraped', 'success_count', 'error_count', 'cache_enabled', 'cache_ttl_seconds', 'updated_at']
        read_only_fields = ['id', 'updated_at']
