#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
django.setup()

from django.contrib.auth.models import User

# スーパーユーザーを作成またはパスワードを設定
user, created = User.objects.get_or_create(username='admin')
user.email = 'admin@example.com'
user.set_password('admin')
user.is_staff = True
user.is_superuser = True
user.save()

print('✅ Superuser created/updated: admin')
print('   Email: admin@example.com')
print('   Password: admin')
