from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):
    """Audit trail for important actions in the dashboard."""
    
    ACTION_CHOICES = [
        ('prospect_created', 'Prospect Created'),
        ('prospect_contacted', 'Prospect Marked Contacted'),
        ('prospect_converted', 'Prospect Converted to Lead'),
        ('prospect_rejected', 'Prospect Rejected'),
        ('lead_created', 'Lead Created'),
        ('lead_interested', 'Lead Marked Interested'),
        ('lead_synced', 'Lead Synced to CRM'),
        ('lead_rejected', 'Lead Rejected'),
        ('target_created', 'Target Created'),
        ('target_updated', 'Target Updated'),
        ('target_enabled', 'Target Enabled'),
        ('target_disabled', 'Target Disabled'),
        ('scrape_triggered', 'Scrape Triggered'),
        ('scrape_completed', 'Scrape Completed'),
        ('scrape_failed', 'Scrape Failed'),
    ]
    
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=50)  # 'prospect', 'lead', 'target', 'run'
    object_id = models.PositiveIntegerField()
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['action', 'object_type']),
        ]
    
    def __str__(self) -> str:
        return f"{self.get_action_display()} - {self.object_type} #{self.object_id} at {self.created_at}"


class Notification(models.Model):
    """User notifications for important events."""
    
    NOTIFICATION_TYPES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]
    
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    title = models.CharField(max_length=200)
    message = models.TextField()
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'read']),
        ]
    
    def __str__(self) -> str:
        return f"{self.title} ({self.user.username})"
    
    def mark_read(self):
        """Mark notification as read."""
        from django.utils import timezone
        self.read = True
        self.read_at = timezone.now()
        self.save(update_fields=['read', 'read_at'])
