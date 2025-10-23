import os
import django
from django.core import management

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartparking.settings')
django.setup()

# Xuất dữ liệu ra file với encoding UTF-8 an toàn
with open('data_backup.json', 'w', encoding='utf-8') as f:
    management.call_command('dumpdata',
        '--exclude', 'contenttypes',
        '--exclude', 'auth.permission',
        indent=2,
        stdout=f
    )

print("✅ Export hoàn tất -> file: data_backup.json (UTF-8 safe)")
