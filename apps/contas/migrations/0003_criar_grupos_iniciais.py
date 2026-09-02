from django.db import migrations

GRUPOS_INICIAIS = ("Administrador", "Gestor/RH", "Candidato")


def criar_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nome in GRUPOS_INICIAIS:
        Group.objects.get_or_create(name=nome)


def remover_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GRUPOS_INICIAIS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0002_perfilcandidato"),
    ]

    operations = [
        migrations.RunPython(criar_grupos, remover_grupos),
    ]
