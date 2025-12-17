# Generated manually for EmailTemplate model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('a_family', '0007_make_email_optional_for_children'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, help_text="Internal identifier for this template (e.g., 'welcome_back', 'promo_summer')", max_length=100, unique=True)),
                ('subject', models.CharField(help_text='Email subject line', max_length=200)),
                ('body_html', models.TextField(help_text='HTML content for the email body. Use inline styles for email compatibility.')),
                ('is_active', models.BooleanField(default=True, help_text='Only active templates can be used to send emails')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'email template',
                'verbose_name_plural': 'email templates',
                'db_table': 'family_email_template',
                'ordering': ['-updated_at'],
            },
        ),
    ]
