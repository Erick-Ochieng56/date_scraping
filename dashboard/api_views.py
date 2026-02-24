from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from dashboard.models import Notification
from dashboard.utils import log_activity
from leads.models import Lead, LeadStatus, Prospect, ProspectStatus
from scraper.models import ScrapeRun, ScrapeRunStatus, ScrapeTarget
from scraper.tasks import scrape_target, enqueue_enabled_targets


@login_required
@require_POST
def api_trigger_scrape(request: HttpRequest) -> JsonResponse:
    """API endpoint to trigger a scrape for a specific target or all enabled targets."""
    try:
        body = {}
        if request.body:
            try:
                body = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        target_id = body.get("target_id")
        
        if target_id:
            # Trigger scrape for specific target
            try:
                target = ScrapeTarget.objects.get(id=target_id)
            except ScrapeTarget.DoesNotExist:
                return JsonResponse({"error": f"Target {target_id} not found"}, status=404)
            
            task = scrape_target.delay(target_id=int(target_id), trigger="manual")
            log_activity(
                action="scrape_triggered",
                object_type="target",
                object_id=int(target_id),
                description=f"Scrape triggered for {target.name}",
                user=request.user,
                metadata={"task_id": task.id},
            )
            return JsonResponse({
                "success": True,
                "message": f"Scrape triggered for {target.name}",
                "target_id": int(target_id),
                "task_id": task.id,
            })
        else:
            # Trigger scrape for all enabled targets
            task = enqueue_enabled_targets.delay()
            log_activity(
                action="scrape_triggered",
                object_type="target",
                object_id=0,
                description="Scrape triggered for all enabled targets",
                user=request.user,
                metadata={"task_id": task.id},
            )
            return JsonResponse({
                "success": True,
                "message": "Scrape triggered for all enabled targets",
                "task_id": task.id,
            })
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_retry_run(request: HttpRequest, run_id: int) -> JsonResponse:
    """API endpoint to retry a failed scrape run."""
    try:
        run = ScrapeRun.objects.get(id=run_id)
        
        if run.status != ScrapeRunStatus.FAILED:
            return JsonResponse({
                "error": f"Run {run_id} is not in failed status. Current status: {run.status}"
            }, status=400)
        
        # Trigger a new scrape for the same target
        task = scrape_target.delay(target_id=run.target.id, trigger="manual")
        log_activity(
            action="scrape_triggered",
            object_type="run",
            object_id=run.id,
            description=f"Retry triggered for run #{run.id} ({run.target.name})",
            user=request.user,
            metadata={"target_id": run.target.id, "task_id": task.id},
        )
        return JsonResponse({
            "success": True,
            "message": f"Retry triggered for target {run.target.name}",
            "target_id": run.target.id,
            "task_id": task.id,
        })
    
    except ScrapeRun.DoesNotExist:
        return JsonResponse({"error": f"Run {run_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def api_get_run_status(request: HttpRequest, run_id: int) -> JsonResponse:
    """API endpoint to get the current status of a scrape run."""
    try:
        run = ScrapeRun.objects.get(id=run_id)
        
        return JsonResponse({
            "success": True,
            "data": {
                "id": run.id,
                "status": run.status,
                "status_display": run.get_status_display(),
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "item_count": run.item_count,
                "created_leads": run.created_leads,
                "updated_leads": run.updated_leads,
                "error_text": run.error_text if run.status == ScrapeRunStatus.FAILED else None,
            }
        })
    
    except ScrapeRun.DoesNotExist:
        return JsonResponse({"success": False, "error": f"Run {run_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# Prospect API Endpoints

@login_required
@require_POST
def api_prospect_bulk_mark_contacted(request: HttpRequest) -> JsonResponse:
    """API endpoint to mark multiple prospects as contacted."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        prospect_ids = body.get("prospect_ids", [])
        
        if not prospect_ids:
            return JsonResponse({"error": "No prospect IDs provided"}, status=400)
        
        now = timezone.now()
        updated = Prospect.objects.filter(
            id__in=prospect_ids,
            status=ProspectStatus.NEW
        )
        count = updated.update(
            status=ProspectStatus.CONTACTED,
            contacted_at=now,
        )
        for pid in prospect_ids:
            log_activity(
                action="prospect_contacted",
                object_type="prospect",
                object_id=pid,
                description=f"Prospect #{pid} marked as contacted (bulk)",
                user=request.user,
            )
        return JsonResponse({
            "success": True,
            "message": f"Marked {count} prospect(s) as contacted",
            "count": count,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_prospect_bulk_convert(request: HttpRequest) -> JsonResponse:
    """API endpoint to convert multiple prospects to leads."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        prospect_ids = body.get("prospect_ids", [])
        
        if not prospect_ids:
            return JsonResponse({"error": "No prospect IDs provided"}, status=400)
        
        prospects = Prospect.objects.filter(
            id__in=prospect_ids,
            status__in=[ProspectStatus.NEW, ProspectStatus.CONTACTED]
        )
        
        count = 0
        errors = []
        for prospect in prospects:
            try:
                lead = prospect.convert_to_lead()
                count += 1
                log_activity(
                    action="prospect_converted",
                    object_type="prospect",
                    object_id=prospect.id,
                    description=f"Prospect #{prospect.id} converted to Lead #{lead.id}",
                    user=request.user,
                    metadata={"lead_id": lead.id},
                )
            except Exception as e:
                errors.append(f"Prospect {prospect.id}: {str(e)}")
        
        message = f"Converted {count} prospect(s) to leads"
        if errors:
            message += f". Errors: {len(errors)}"
        
        return JsonResponse({
            "success": True,
            "message": message,
            "count": count,
            "errors": errors if errors else None,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_prospect_bulk_reject(request: HttpRequest) -> JsonResponse:
    """API endpoint to reject multiple prospects."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        prospect_ids = body.get("prospect_ids", [])
        reason = body.get("reason", "")
        
        if not prospect_ids:
            return JsonResponse({"error": "No prospect IDs provided"}, status=400)
        
        now = timezone.now()
        count = Prospect.objects.filter(
            id__in=prospect_ids,
            status__in=[ProspectStatus.NEW, ProspectStatus.CONTACTED]
        ).update(
            status=ProspectStatus.REJECTED,
            rejected_at=now,
        )
        
        # Add reason to notes if provided
        if reason:
            for prospect in Prospect.objects.filter(id__in=prospect_ids):
                prospect.mark_rejected(reason=reason, save=True)
        for pid in prospect_ids:
            log_activity(
                action="prospect_rejected",
                object_type="prospect",
                object_id=pid,
                description=f"Prospect #{pid} rejected (bulk)",
                user=request.user,
            )
        return JsonResponse({
            "success": True,
            "message": f"Rejected {count} prospect(s)",
            "count": count,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_prospect_mark_contacted(request: HttpRequest, prospect_id: int) -> JsonResponse:
    """API endpoint to mark a single prospect as contacted."""
    try:
        prospect = Prospect.objects.get(id=prospect_id)
        prospect.mark_contacted()
        log_activity(
            action="prospect_contacted",
            object_type="prospect",
            object_id=prospect_id,
            description=f"Prospect #{prospect_id} marked as contacted",
            user=request.user,
        )
        return JsonResponse({
            "success": True,
            "message": f"Prospect {prospect_id} marked as contacted",
        })
    
    except Prospect.DoesNotExist:
        return JsonResponse({"error": f"Prospect {prospect_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_prospect_convert(request: HttpRequest, prospect_id: int) -> JsonResponse:
    """API endpoint to convert a single prospect to a lead."""
    try:
        prospect = Prospect.objects.get(id=prospect_id)
        lead = prospect.convert_to_lead()
        log_activity(
            action="prospect_converted",
            object_type="prospect",
            object_id=prospect_id,
            description=f"Prospect #{prospect_id} converted to Lead #{lead.id}",
            user=request.user,
            metadata={"lead_id": lead.id},
        )
        return JsonResponse({
            "success": True,
            "message": f"Prospect {prospect_id} converted to Lead {lead.id}",
            "lead_id": lead.id,
        })
    
    except Prospect.DoesNotExist:
        return JsonResponse({"error": f"Prospect {prospect_id} not found"}, status=404)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_prospect_reject(request: HttpRequest, prospect_id: int) -> JsonResponse:
    """API endpoint to reject a single prospect."""
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        reason = body.get("reason", "")
        
        prospect = Prospect.objects.get(id=prospect_id)
        prospect.mark_rejected(reason=reason)
        log_activity(
            action="prospect_rejected",
            object_type="prospect",
            object_id=prospect_id,
            description=f"Prospect #{prospect_id} rejected",
            user=request.user,
        )
        return JsonResponse({
            "success": True,
            "message": f"Prospect {prospect_id} rejected",
        })
    
    except Prospect.DoesNotExist:
        return JsonResponse({"error": f"Prospect {prospect_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Lead API Endpoints

@login_required
@require_POST
def api_lead_bulk_mark_interested(request: HttpRequest) -> JsonResponse:
    """API endpoint to mark multiple leads as interested."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        lead_ids = body.get("lead_ids", [])
        
        if not lead_ids:
            return JsonResponse({"error": "No lead IDs provided"}, status=400)
        
        updated_ids = list(
            Lead.objects.filter(
                id__in=lead_ids,
                status=LeadStatus.CONTACTED
            ).values_list("id", flat=True)
        )
        count = Lead.objects.filter(id__in=updated_ids).update(status=LeadStatus.INTERESTED)
        for lid in updated_ids:
            log_activity(
                action="lead_interested",
                object_type="lead",
                object_id=lid,
                description=f"Lead #{lid} marked as interested (bulk)",
                user=request.user,
            )
        return JsonResponse({
            "success": True,
            "message": f"Marked {count} lead(s) as interested",
            "count": count,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_lead_bulk_sync_crm(request: HttpRequest) -> JsonResponse:
    """API endpoint to sync multiple leads to CRM."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        lead_ids = body.get("lead_ids", [])
        
        if not lead_ids:
            return JsonResponse({"error": "No lead IDs provided"}, status=400)
        
        from crm_integration.models import PerfexLeadSync
        from crm_integration.tasks import sync_lead_to_perfex
        
        leads = Lead.objects.filter(
            id__in=lead_ids,
            status=LeadStatus.INTERESTED
        )
        
        count = 0
        for lead in leads:
            PerfexLeadSync.objects.get_or_create(lead=lead)
            sync_lead_to_perfex.delay(lead.id)
            count += 1
            log_activity(
                action="lead_synced",
                object_type="lead",
                object_id=lead.id,
                description=f"Lead #{lead.id} queued for CRM sync",
                user=request.user,
            )
        return JsonResponse({
            "success": True,
            "message": f"Queued {count} lead(s) for CRM sync",
            "count": count,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_lead_bulk_reject(request: HttpRequest) -> JsonResponse:
    """API endpoint to reject multiple leads."""
    try:
        body = json.loads(request.body.decode("utf-8"))
        lead_ids = body.get("lead_ids", [])
        
        if not lead_ids:
            return JsonResponse({"error": "No lead IDs provided"}, status=400)
        
        rejected_ids = list(
            Lead.objects.filter(
                id__in=lead_ids,
                status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED]
            ).values_list("id", flat=True)
        )
        count = Lead.objects.filter(id__in=rejected_ids).update(
            status=LeadStatus.REJECTED,
            rejected_at=timezone.now(),
        )
        for lid in rejected_ids:
            log_activity(
                action="lead_rejected",
                object_type="lead",
                object_id=lid,
                description=f"Lead #{lid} rejected (bulk)",
                user=request.user,
            )
        return JsonResponse({
            "success": True,
            "message": f"Rejected {count} lead(s)",
            "count": count,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_lead_mark_interested(request: HttpRequest, lead_id: int) -> JsonResponse:
    """API endpoint to mark a single lead as interested."""
    try:
        lead = Lead.objects.get(id=lead_id)
        
        if lead.status != LeadStatus.CONTACTED:
            return JsonResponse({
                "error": f"Lead {lead_id} must be in CONTACTED status. Current: {lead.status}"
            }, status=400)
        
        lead.status = LeadStatus.INTERESTED
        lead.save(update_fields=["status", "updated_at"])
        log_activity(
            action="lead_interested",
            object_type="lead",
            object_id=lead_id,
            description=f"Lead #{lead_id} marked as interested",
            user=request.user,
        )
        return JsonResponse({
            "success": True,
            "message": f"Lead {lead_id} marked as interested",
        })
    
    except Lead.DoesNotExist:
        return JsonResponse({"error": f"Lead {lead_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_lead_sync_crm(request: HttpRequest, lead_id: int) -> JsonResponse:
    """API endpoint to sync a single lead to CRM."""
    try:
        lead = Lead.objects.get(id=lead_id)
        
        if lead.status != LeadStatus.INTERESTED:
            return JsonResponse({
                "error": f"Lead {lead_id} must be in INTERESTED status. Current: {lead.status}"
            }, status=400)
        
        from crm_integration.models import PerfexLeadSync
        from crm_integration.tasks import sync_lead_to_perfex
        
        PerfexLeadSync.objects.get_or_create(lead=lead)
        task = sync_lead_to_perfex.delay(lead.id)
        log_activity(
            action="lead_synced",
            object_type="lead",
            object_id=lead_id,
            description=f"Lead #{lead_id} queued for CRM sync",
            user=request.user,
        )
        return JsonResponse({
            "success": True,
            "message": f"Lead {lead_id} queued for CRM sync",
            "task_id": task.id,
        })
    
    except Lead.DoesNotExist:
        return JsonResponse({"error": f"Lead {lead_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def api_lead_reject(request: HttpRequest, lead_id: int) -> JsonResponse:
    """API endpoint to reject a single lead."""
    try:
        lead = Lead.objects.get(id=lead_id)
        
        if lead.status in [LeadStatus.REJECTED, LeadStatus.SYNCED]:
            return JsonResponse({
                "error": f"Lead {lead_id} cannot be rejected. Current status: {lead.status}"
            }, status=400)
        
        lead.status = LeadStatus.REJECTED
        lead.rejected_at = timezone.now()
        lead.save(update_fields=["status", "rejected_at", "updated_at"])
        log_activity(
            action="lead_rejected",
            object_type="lead",
            object_id=lead_id,
            description=f"Lead #{lead_id} rejected",
            user=request.user,
        )
        return JsonResponse({
            "success": True,
            "message": f"Lead {lead_id} rejected",
        })
    
    except Lead.DoesNotExist:
        return JsonResponse({"error": f"Lead {lead_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Notifications API Endpoints

@login_required
@require_GET
def api_notifications(request: HttpRequest) -> JsonResponse:
    """API endpoint to get user notifications."""
    try:
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
        
        return JsonResponse({
            "success": True,
            "data": [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "message": n.message,
                    "read": n.read,
                    "link_url": n.link_url,
                    "created_at": n.created_at.isoformat(),
                }
                for n in notifications
            ]
        })
    
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_POST
def api_notification_read(request: HttpRequest, notif_id: int) -> JsonResponse:
    """API endpoint to mark a notification as read."""
    try:
        notification = Notification.objects.get(id=notif_id, user=request.user)
        notification.mark_read()
        
        return JsonResponse({
            "success": True,
            "message": "Notification marked as read",
        })
    
    except Notification.DoesNotExist:
        return JsonResponse({"error": f"Notification {notif_id} not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
