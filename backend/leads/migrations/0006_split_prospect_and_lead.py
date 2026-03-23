# Generated manually for Prospect/Lead split

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def migrate_leads_to_prospects(apps, schema_editor):
    """
    Migrate existing NEW Leads to Prospects.
    Keep CONTACTED/INTERESTED/REJECTED/SYNCED/ERROR Leads as Leads.
    """
    Lead = apps.get_model("leads", "Lead")
    Prospect = apps.get_model("leads", "Prospect")
    
    # Find all NEW leads and create Prospects from them
    new_leads = Lead.objects.filter(status="new")
    for lead in new_leads:
        prospect = Prospect.objects.create(
            source_name=lead.source_name,
            source_url=lead.source_url,
            source_ref=lead.source_ref,
            event_name=lead.event_name,
            company=lead.company,
            email=lead.email,
            phone_raw=lead.phone_raw,
            phone_e164=lead.phone_e164,
            website=lead.website,
            raw_payload=lead.raw_payload,
            raw_payload_hash=lead.raw_payload_hash,
            status="new",
            notes=lead.notes,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )
        # Link the Lead to the Prospect
        lead.prospect = prospect
        lead.status = "contacted"  # Convert NEW leads to CONTACTED status in Lead model
        lead.save(update_fields=["prospect", "status"])


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0005_rename_leads_lead_status_idx_leads_lead_status_e23abe_idx_and_more'),
    ]

    operations = [
        # 1. Create Prospect model
        migrations.CreateModel(
            name='Prospect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_name', models.CharField(blank=True, default='', max_length=100)),
                ('source_url', models.URLField(blank=True, default='')),
                ('source_ref', models.CharField(blank=True, default='', help_text='Optional source-specific identifier (listing id, etc.).', max_length=255)),
                ('event_name', models.CharField(blank=True, default='', help_text='Name of the event or meeting that was scraped.', max_length=255)),
                ('company', models.CharField(blank=True, default='', max_length=255)),
                ('email', models.EmailField(blank=True, null=True)),
                ('phone_raw', models.CharField(blank=True, default='', max_length=64)),
                ('phone_e164', models.CharField(blank=True, default='', help_text='Normalized E.164 number', max_length=32)),
                ('website', models.URLField(blank=True, default='', help_text='Website URL')),
                ('raw_payload', models.JSONField(blank=True, default=dict)),
                ('raw_payload_hash', models.CharField(blank=True, db_index=True, default='', help_text='SHA-256 of canonicalized raw_payload for dedupe/idempotency.', max_length=64)),
                ('status', models.CharField(choices=[('new', 'New'), ('contacted', 'Contacted'), ('converted', 'Converted'), ('rejected', 'Rejected')], default='new', max_length=20)),
                ('notes', models.TextField(blank=True, default='')),
                ('contacted_at', models.DateTimeField(blank=True, help_text='When the team first reached out.', null=True)),
                ('converted_at', models.DateTimeField(blank=True, help_text='When converted to Lead.', null=True)),
                ('rejected_at', models.DateTimeField(blank=True, help_text='When marked as not interested.', null=True)),
            ],
        ),
        # 2. Add indexes to Prospect
        migrations.AddIndex(
            model_name='prospect',
            index=models.Index(fields=['email'], name='leads_prospect_email_idx'),
        ),
        migrations.AddIndex(
            model_name='prospect',
            index=models.Index(fields=['phone_e164'], name='leads_prospect_phone_e164_idx'),
        ),
        migrations.AddIndex(
            model_name='prospect',
            index=models.Index(fields=['source_name', 'source_ref'], name='leads_prospect_source_idx'),
        ),
        migrations.AddIndex(
            model_name='prospect',
            index=models.Index(fields=['status'], name='leads_prospect_status_idx'),
        ),
        # 3. Add prospect ForeignKey to Lead
        migrations.AddField(
            model_name='lead',
            name='prospect',
            field=models.ForeignKey(
                blank=True,
                help_text='Source Prospect this Lead was converted from (if applicable).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='leads',
                to='leads.prospect',
            ),
        ),
        # 4. Update Lead status choices (remove NEW, keep others)
        migrations.AlterField(
            model_name='lead',
            name='status',
            field=models.CharField(
                choices=[
                    ('contacted', 'Contacted'),
                    ('interested', 'Interested'),
                    ('rejected', 'Rejected'),
                    ('synced', 'Synced'),
                    ('error', 'Error'),
                ],
                default='contacted',
                max_length=20,
            ),
        ),
        # 5. Add index on Lead.prospect
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['prospect'], name='leads_lead_prospect_idx'),
        ),
        # 6. Migrate data: NEW Leads → Prospects
        migrations.RunPython(migrate_leads_to_prospects, migrations.RunPython.noop),
    ]

