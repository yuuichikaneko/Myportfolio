from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0003_configuration_cpu_cooler'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pcpart',
            name='part_type',
            field=models.CharField(choices=[('cpu', 'CPU'), ('cpu_cooler', 'CPU Cooler'), ('gpu', 'GPU'), ('motherboard', 'Motherboard'), ('memory', 'Memory'), ('storage', 'Storage'), ('os', 'OS'), ('psu', 'Power Supply'), ('case', 'Case')], max_length=20),
        ),
        migrations.AddField(
            model_name='configuration',
            name='os',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cfg_os', to='scraper.pcpart'),
        ),
    ]