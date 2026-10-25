"""Charge le workflow global par défaut (docs/03-workflow.md)."""
from django.db import migrations

from apps.projects.default_workflow import load_default_workflow


def forwards(apps, schema_editor):
    load_default_workflow(apps.get_model("projects", "WorkflowStatus"))


def backwards(apps, schema_editor):
    apps.get_model("projects", "WorkflowStatus").objects.filter(project__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("projects", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
