from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0002_configuration_soft_delete'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='cpu_cooler',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cfg_cpu_cooler', to='scraper.pcpart'),
        ),
    ]
