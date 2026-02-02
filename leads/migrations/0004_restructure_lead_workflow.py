# Generated manually for workflow restructure

from django.db import migrations, models


def migrate_reviewed_to_contacted(apps, schema_editor):
    """Convert all existing REVIEWED leads to CONTACTED."""
    Lead = apps.get_model("leads", "Lead")
    Lead.objects.filter(status="reviewed").update(status="contacted")


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0002_lead_address_lead_city_lead_default_language_and_more'),
    ]

    operations = [
        # 1. RenameField - event_text → event_name
        migrations.RenameField(
            model_name='lead',
            old_name='event_text',
            new_name='event_name',
        ),
        # 2. AddField - contacted_at
        migrations.AddField(
            model_name='lead',
            name='contacted_at',
            field=models.DateTimeField(blank=True, help_text='When the team first reached out.', null=True),
        ),
        # 3. AddField - rejected_at
        migrations.AddField(
            model_name='lead',
            name='rejected_at',
            field=models.DateTimeField(blank=True, help_text='When the prospect was marked not interested.', null=True),
        ),
        # 4. AlterField - update status choices
        migrations.AlterField(
            model_name='lead',
            name='status',
            field=models.CharField(
                choices=[
                    ('new', 'New'),
                    ('contacted', 'Contacted'),
                    ('interested', 'Interested'),
                    ('rejected', 'Rejected'),
                    ('synced', 'Synced'),
                    ('error', 'Error'),
                ],
                default='new',
                max_length=20,
            ),
        ),
        # 5. RunPython - migrate reviewed to contacted
        migrations.RunPython(migrate_reviewed_to_contacted, migrations.RunPython.noop),
        # 6. AddIndex - on status
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['status'], name='leads_lead_status_idx'),
        ),
        # 7. AddIndex - on event_date
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['event_date'], name='leads_lead_event_date_idx'),
        ),
    ]

