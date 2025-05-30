from django.db import migrations

def mark_existing_users_verified(apps, schema_editor):
    User = apps.get_model('access', 'User')
    User.objects.all().update(email_verified=True)

class Migration(migrations.Migration):
    dependencies = [
        ('access', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(mark_existing_users_verified),
    ]
