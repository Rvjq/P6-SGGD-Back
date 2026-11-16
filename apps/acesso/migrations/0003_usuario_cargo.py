from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("acesso", "0002_papeis_e_permissoes")]
    operations = [migrations.AddField(model_name="usuario", name="cargo", field=models.CharField(blank=True, max_length=120, verbose_name="cargo / função"))]
