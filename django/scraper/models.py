from django.db import models
from django.utils import timezone

class PCPart(models.Model):
    """PC パーツモデル"""
    PART_CHOICES = [
        ('cpu', 'CPU'),
        ('cpu_cooler', 'CPU Cooler'),
        ('gpu', 'GPU'),
        ('motherboard', 'Motherboard'),
        ('memory', 'Memory'),
        ('storage', 'Storage'),
        ('psu', 'Power Supply'),
        ('case', 'Case'),
    ]
    
    part_type = models.CharField(max_length=20, choices=PART_CHOICES)
    name = models.CharField(max_length=200)
    price = models.IntegerField()
    specs = models.JSONField(default=dict)
    url = models.URLField()
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('part_type', 'name')
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.get_part_type_display()} - {self.name}"


class Configuration(models.Model):
    """PC 構成モデル"""
    USAGE_CHOICES = [
        ('gaming', 'Gaming'),
        ('video_editing', 'Video Editing'),
        ('general', 'General'),
    ]
    
    budget = models.IntegerField()
    usage = models.CharField(max_length=20, choices=USAGE_CHOICES)
    cpu = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_cpu')
    cpu_cooler = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_cpu_cooler')
    gpu = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_gpu')
    motherboard = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_mobo')
    memory = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_memory')
    storage = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_storage')
    psu = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_psu')
    case = models.ForeignKey(PCPart, on_delete=models.SET_NULL, null=True, related_name='cfg_case')
    total_price = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_usage_display()} - ¥{self.total_price}"

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])


class ScraperStatus(models.Model):
    """スクレイパー状態トラッキング"""
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    total_scraped = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    cache_enabled = models.BooleanField(default=True)
    cache_ttl_seconds = models.IntegerField(default=3600)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Scraper Status'
    
    def __str__(self):
        return f"Scraper Status (Last: {self.last_run})"
