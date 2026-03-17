import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'myportfolio_django.settings'
django.setup()
from scraper.models import PCPart
count = PCPart.objects.count()
print(f'Database: {count} parts saved')
