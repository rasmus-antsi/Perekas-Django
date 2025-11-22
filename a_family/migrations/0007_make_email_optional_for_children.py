# Generated migration for making email optional for children

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('a_family', '0006_add_notification_preferences'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='email address'),
        ),
    ]

