from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0004_configuration_os_and_pcpart_os_choice'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='storage2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cfg_storage2', to='scraper.pcpart'),
        ),
        migrations.AddField(
            model_name='configuration',
            name='storage3',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cfg_storage3', to='scraper.pcpart'),
        ),
    ]