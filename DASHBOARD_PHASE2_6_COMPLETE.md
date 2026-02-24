# Dashboard Phase 2.6 - AJAX Functionality ✅

## Completed Tasks

### 1. API Endpoints ✅
Created `dashboard/api_views.py` with:
- **`api_trigger_scrape`** - Trigger scrape for specific target or all enabled targets
- **`api_retry_run`** - Retry a failed scrape run
- **`api_get_run_status`** - Get current status of a scrape run (for future polling)

All endpoints:
- Require authentication (`@login_required`)
- Return JSON responses
- Include proper error handling
- Use Django authentication (not OPS_TOKEN)

### 2. Toast Notification System ✅
Added to `templates/base.html`:
- Toast container in top-right corner
- `showToast(message, type)` JavaScript function
- Supports: success, error, warning, info
- Auto-dismiss after 5 seconds
- Bootstrap 5 toast styling

### 3. AJAX Helper Functions ✅
Added to `templates/base.html`:
- **`getCsrfToken()`** - Extracts CSRF token from cookies
- **`makeAjaxRequest(url, options)`** - Generic AJAX helper with:
  - Automatic CSRF token inclusion
  - JSON request/response handling
  - Error handling
  - Returns `{success: boolean, data/error}`

### 4. Dashboard Home - Trigger Scrape ✅
Updated `templates/dashboard/index.html`:
- "Trigger Scrape (All)" button now uses AJAX
- Loading state with spinner
- Success/error toast notifications
- Auto-refresh page after 2 seconds on success

### 5. Target Detail - Test Scrape ✅
Updated `templates/dashboard/target_detail.html`:
- "Test Scrape" button now uses AJAX
- Loading state with spinner
- Success/error toast notifications
- Auto-refresh page after 2 seconds on success
- Sends target_id in request body

### 6. Run Detail - Retry Failed Run ✅
Updated `templates/dashboard/run_detail.html`:
- "Retry Run" button now uses AJAX
- Loading state with spinner
- Success/error toast notifications
- Redirects to target detail page after success
- Validates run is in failed status

### 7. Loading States & Error Handling ✅
All AJAX buttons include:
- Disabled state during request
- Spinner animation
- Original text restoration on error
- User-friendly error messages
- Confirmation dialogs before actions

## API Endpoints

### POST `/dashboard/api/trigger-scrape/`
**Request Body:**
```json
{
  "target_id": 1  // Optional: if omitted, triggers all enabled targets
}
```

**Response:**
```json
{
  "success": true,
  "message": "Scrape triggered for Target Name",
  "target_id": 1,
  "task_id": "celery-task-id"
}
```

### POST `/dashboard/api/runs/<run_id>/retry/`
**Response:**
```json
{
  "success": true,
  "message": "Retry triggered for target Target Name",
  "target_id": 1,
  "task_id": "celery-task-id"
}
```

### GET `/dashboard/api/runs/<run_id>/status/`
**Response:**
```json
{
  "id": 1,
  "status": "success",
  "status_display": "Success",
  "started_at": "2026-01-29T12:00:00Z",
  "finished_at": "2026-01-29T12:05:00Z",
  "item_count": 10,
  "created_leads": 5,
  "updated_leads": 2,
  "error_text": null
}
```

## JavaScript Functions

### `showToast(message, type)`
Display a toast notification.

**Parameters:**
- `message` (string) - The message to display
- `type` (string) - One of: 'success', 'error', 'warning', 'info'

**Example:**
```javascript
showToast('Scrape triggered successfully!', 'success');
showToast('Failed to trigger scrape', 'error');
```

### `makeAjaxRequest(url, options)`
Make an AJAX request with automatic CSRF handling.

**Parameters:**
- `url` (string) - The URL to request
- `options` (object) - Fetch options:
  - `method` (string) - HTTP method (default: 'GET')
  - `body` (object) - Request body (will be JSON stringified)

**Returns:**
```javascript
{
  success: true,
  data: {...}  // Response data
}
// or
{
  success: false,
  error: "Error message"
}
```

**Example:**
```javascript
const result = await makeAjaxRequest('/dashboard/api/trigger-scrape/', {
  method: 'POST',
  body: { target_id: 1 }
});

if (result.success) {
  showToast(result.data.message, 'success');
} else {
  showToast(result.error, 'error');
}
```

## User Experience Improvements

1. **No Page Reloads** - Actions happen via AJAX (except auto-refresh on success)
2. **Visual Feedback** - Loading spinners and disabled buttons
3. **Notifications** - Toast messages for all actions
4. **Error Handling** - User-friendly error messages
5. **Confirmation** - Dialogs before destructive actions

## Security

- All API endpoints require authentication (`@login_required`)
- CSRF protection via automatic token inclusion
- Input validation and error handling
- No sensitive data exposed in responses

## Testing

To test the AJAX functionality:

1. **Trigger Scrape (All):**
   - Go to `/dashboard/`
   - Click "Trigger Scrape (All)" button
   - Confirm action
   - Watch for toast notification
   - Page should refresh after 2 seconds

2. **Test Scrape (Single Target):**
   - Go to `/dashboard/targets/<id>/`
   - Click "Test Scrape" button
   - Confirm action
   - Watch for toast notification
   - Page should refresh after 2 seconds

3. **Retry Failed Run:**
   - Go to `/dashboard/runs/<id>/` (for a failed run)
   - Click "Retry Run" button
   - Confirm action
   - Watch for toast notification
   - Should redirect to target detail page

## Next Steps

Future enhancements could include:
- Real-time status polling for running scrapes
- WebSocket integration for live updates
- Progress bars for long-running operations
- Batch operations (retry multiple failed runs)
- Scheduled scrape management

## Notes

- Toast notifications use Bootstrap 5's toast component
- All AJAX requests include CSRF tokens automatically
- Error messages are user-friendly and actionable
- Loading states prevent duplicate requests
- Auto-refresh helps users see results immediately

