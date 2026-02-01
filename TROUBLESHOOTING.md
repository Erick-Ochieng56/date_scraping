# Troubleshooting Guide

## Common Issues and Solutions

### All Runs Failing

If all your scrape runs are showing "Failed" status, check the error messages in the ScrapeRun admin.

#### 1. Network/DNS Errors

**Error messages:**
- `Failed to resolve 'www.eventbrite.com'`
- `ERR_NAME_NOT_RESOLVED`
- `getaddrinfo failed`

**Solutions:**

1. **Check Internet Connection:**
   ```powershell
   ping www.google.com
   ```

2. **Test DNS Resolution:**
   ```powershell
   nslookup www.eventbrite.com
   ```

3. **Check Firewall/VPN:**
   - Temporarily disable firewall
   - If using VPN, try disabling it
   - Check if corporate proxy is blocking requests

4. **Fix DNS Settings:**
   - Try using Google DNS: `8.8.8.8` and `8.8.4.4`
   - Or Cloudflare DNS: `1.1.1.1` and `1.0.0.1`

5. **Temporarily Disable Targets:**
   - Go to ScrapeTarget admin
   - Uncheck "Enabled" for targets that keep failing
   - Re-enable once network is fixed

#### 2. Timeout Errors

**Error messages:**
- `Timeout 45000ms exceeded`
- `Request timed out`

**Solutions:**

1. **Increase Timeout:**
   - Edit target config in admin
   - Increase `timeout_seconds` (e.g., from 30 to 60)
   - For Playwright, also increase timeout in config

2. **Change Wait Strategy:**
   - For Playwright targets, change `wait_until` from `"networkidle"` to `"load"`
   - This is faster but may miss dynamic content

3. **Check Target Website:**
   - Visit the URL manually in browser
   - If it's slow or down, that's the issue

#### 3. CSS Selector Errors

**Error messages:**
- `Invalid character '@'`
- `SelectorSyntaxError`

**Solutions:**

1. **Fixed!** The `@href` syntax is now supported
2. **If still seeing errors:**
   - Check target config in admin
   - Make sure selectors are valid CSS
   - Test selectors manually in browser DevTools

#### 4. Configuration Errors

**Error messages:**
- `missing config.item_selector`
- `missing config.fields`

**Solutions:**

1. **Edit Target Config:**
   - Go to ScrapeTarget admin
   - Click on the target
   - Add missing required fields:
     ```json
     {
       "item_selector": ".event-card",
       "fields": {
         "full_name": ".title",
         "event_date": ".date"
       }
     }
     ```

2. **Use Auto-Create:**
   - Visit: `/admin/scraper/scrapetarget/auto-create/?url=YOUR_URL`
   - This generates a proper config automatically

## How to Diagnose Issues

### Step 1: Check Error Messages

1. Go to: `http://localhost:8000/admin/scraper/scraperun/`
2. Click on a failed run (ID number)
3. Expand "Error Information" section
4. Read the full error message

### Step 2: Check Error Type

The admin now shows error previews:
- 🌐 **Network/DNS** - Internet connectivity issue
- ⏱️ **Timeout** - Page took too long to load
- 🎯 **Selector** - CSS selector problem
- ⚙️ **Config** - Missing configuration

### Step 3: Test Target Manually

1. Go to ScrapeTarget admin
2. Click "Test Scrape" button next to target
3. Check the new ScrapeRun result
4. Review error message if it fails

### Step 4: Verify Network

```powershell
# Test basic connectivity
ping www.google.com

# Test specific target
ping www.eventbrite.com
ping www.meetup.com

# Test DNS
nslookup www.eventbrite.com
```

## Quick Fixes

### Disable Failing Targets Temporarily

1. Go to ScrapeTarget admin
2. Select failing targets
3. Choose "Disable selected targets" from Actions
4. Click "Go"
5. Re-enable once issues are fixed

### Retry Failed Runs

1. Go to ScrapeRun admin
2. Select failed runs
3. Choose "Retry selected failed runs" from Actions
4. Click "Go"

### Check System Status

```powershell
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Check if Celery worker is running
# Look for: "celery@HOSTNAME ready" in worker logs

# Check if Celery beat is running
# Look for: "beat: Starting..." in beat logs
```

## Prevention

### For Network Issues:

1. **Use Reliable Internet Connection**
2. **Add Retry Logic** (future enhancement)
3. **Monitor Target Websites** - Some may be down

### For Configuration Issues:

1. **Use Auto-Create** for initial setup
2. **Test Targets** before enabling
3. **Review Config** in admin before saving

### For Timeout Issues:

1. **Set Realistic Timeouts** based on target site speed
2. **Use HTML type** instead of Playwright for faster sites
3. **Reduce max_pages** if scraping is slow

## Getting Help

If issues persist:

1. **Check Error Messages** in ScrapeRun admin
2. **Check Worker Logs** for detailed stack traces
3. **Test Network** connectivity
4. **Verify Target URLs** work in browser
5. **Review Target Configs** for syntax errors

