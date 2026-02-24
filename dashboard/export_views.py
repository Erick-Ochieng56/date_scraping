from __future__ import annotations

import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from leads.models import Lead, Prospect


@login_required
@require_GET
def export_prospects_csv(request: HttpRequest) -> HttpResponse:
    """Export prospects to CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="prospects_export.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'ID', 'Status', 'Event Name', 'Company', 'Email', 'Phone', 'Website',
        'Source Name', 'Source URL', 'Created At', 'Contacted At', 'Converted At', 'Rejected At'
    ])
    
    # Get filter parameters
    status_filter = request.GET.get('status')
    source_filter = request.GET.get('source')
    search = request.GET.get('search')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Build queryset with same filters as list view
    queryset = Prospect.objects.all()
    
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if source_filter:
        queryset = queryset.filter(source_name__icontains=source_filter)
    if search and search.strip():
        from django.db.models import Q
        queryset = queryset.filter(
            Q(event_name__icontains=search) |
            Q(company__icontains=search) |
            Q(email__icontains=search) |
            Q(phone_e164__icontains=search) |
            Q(source_name__icontains=search)
        )
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    
    # Write data rows
    for prospect in queryset.order_by('-created_at'):
        writer.writerow([
            prospect.id,
            prospect.get_status_display(),
            prospect.event_name or '',
            prospect.company or '',
            prospect.email or '',
            prospect.phone_e164 or prospect.phone_raw or '',
            prospect.website or '',
            prospect.source_name or '',
            prospect.source_url or '',
            prospect.created_at.strftime('%Y-%m-%d %H:%M:%S') if prospect.created_at else '',
            prospect.contacted_at.strftime('%Y-%m-%d %H:%M:%S') if prospect.contacted_at else '',
            prospect.converted_at.strftime('%Y-%m-%d %H:%M:%S') if prospect.converted_at else '',
            prospect.rejected_at.strftime('%Y-%m-%d %H:%M:%S') if prospect.rejected_at else '',
        ])
    
    return response


@login_required
@require_GET
def export_leads_csv(request: HttpRequest) -> HttpResponse:
    """Export leads to CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads_export.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'ID', 'Status', 'Full Name', 'First Name', 'Last Name', 'Position', 'Company', 'Email', 'Phone',
        'Website', 'Event Name', 'Address', 'City', 'State', 'Country', 'Zip Code',
        'Default Language', 'Lead Value', 'Source Name', 'Source URL', 'Created At', 'Contacted At', 'Rejected At'
    ])
    
    # Get filter parameters
    status_filter = request.GET.get('status')
    source_filter = request.GET.get('source')
    search = request.GET.get('search')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Build queryset with same filters as list view
    queryset = Lead.objects.select_related('prospect').all()
    
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if source_filter:
        queryset = queryset.filter(source_name__icontains=source_filter)
    if search and search.strip():
        from django.db.models import Q
        queryset = queryset.filter(
            Q(full_name__icontains=search) |
            Q(company__icontains=search) |
            Q(email__icontains=search) |
            Q(phone_e164__icontains=search) |
            Q(event_name__icontains=search) |
            Q(source_name__icontains=search)
        )
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    
    # Write data rows
    for lead in queryset.order_by('-created_at'):
        writer.writerow([
            lead.id,
            lead.get_status_display(),
            lead.full_name or '',
            lead.first_name or '',
            lead.last_name or '',
            lead.position or '',
            lead.company or '',
            lead.email or '',
            lead.phone_e164 or lead.phone_raw or '',
            lead.website or '',
            lead.event_name or '',
            lead.address or '',
            lead.city or '',
            lead.state or '',
            lead.country_code or '',
            lead.zip_code or '',
            lead.default_language or '',
            str(lead.lead_value) if lead.lead_value else '',
            lead.source_name or '',
            lead.source_url or '',
            lead.created_at.strftime('%Y-%m-%d %H:%M:%S') if lead.created_at else '',
            lead.contacted_at.strftime('%Y-%m-%d %H:%M:%S') if lead.contacted_at else '',
            lead.rejected_at.strftime('%Y-%m-%d %H:%M:%S') if lead.rejected_at else '',
        ])
    
    return response

