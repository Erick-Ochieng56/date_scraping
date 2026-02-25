# Scraping FAQ - Adaptive CSS Selectors & Multi-Platform Support

## Table of Contents
- [General Questions](#general-questions)
- [CSS Selector Adaptation](#css-selector-adaptation)
- [Platform-Specific Questions](#platform-specific-questions)
- [Automation Questions](#automation-questions)
- [Troubleshooting](#troubleshooting)

---

## General Questions

### Q: Will the CSS selector fix work for Meetup and other event sites?

**Short answer:** No, not automatically. Each platform needs its own selectors.

**Why:**
- Eventbrite uses `<h3>` for event titles
- Meetup uses different class names and structure
- LinkedIn has completely different HTML
- Twitter uses `data-testid` attributes

**The fix we applied was specific to Eventbrite:**
```json
{
  "item_selector": ".event-card",
  "fields": {
    "event_name": "h3",
    "source_url": "a.event-card-link@href"
  }
}
```

**Meetup requires different selectors:**
```json
{
  "item_selector": "[data-event-id], .eventCard",
  "fields": {
    "event_name": "h3[id*='event-title']",
    "source_url": "a[href*='/events/']@href"
  }
}
```

**Current status in targets.json:**
- ✅ Eventbrite: Fixed and working (100% fields filled)
- ⚠️ Meetup: Needs testing and potentially updating
- ❌ LinkedIn/Twitter: Not configured yet

### Q: How do I make CSS selectors automatically adapt to different websites?

**Answer:** There are 3 approaches:

#### Approach 1: Manual Configuration (Current - Recommended)
- Inspect each website's HTML structure
- Write platform-specific selectors
- Test with `python test_config.py`
- Update `targets.json` when sites change

**Pros:** Most reliable, accurate extraction
**Cons:** Requires manual work for each platform

#### Approach 2: Smart Discovery (Implemented in this project)
- Use `scraper/services/auto_discover.py` for platform detection
- Platform-specific selector templates
- Fallback to generic selectors

**How to use:**
```bash
# Via API
curl -X POST http://localhost:8000/ops/auto-create-target \
  -H "X-OPS-TOKEN: your-token" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.eventbrite.com/d/us/events/", "name": "Auto Eventbrite"}'

# Via Django shell
python manage.py shell --command "
from scraper.services.auto_discover import auto_create_target;
config = auto_create_target('https://www.eventbrite.com/d/us/events/', 'Auto Target');
print(config);
"
```

**Pros:** Quick setup for known platforms
**Cons:** Templates may be outdated, needs testing

#### Approach 3: AI-Powered Discovery (Future Enhancement)
- Use GPT-4 Vision to analyze page screenshots
- AI generates optimal selectors
- Automatic validation and refinement

**Status:** Not implemented yet, but possible with OpenAI API

**Recommended approach:** Start with Approach 2 (auto-discover), then refine manually using Approach 1.

### Q: Can the scraper automatically detect when a website changes its structure?

**Answer:** Not automatically, but you can monitor for it.

**Detection methods:**

1. **Monitor extraction success rate:**
```python
# In tasks.py, add after scraping:
if run.item_count > 0 and run.created_leads == 0:
    # Items found but all fields blank = selectors broken
    send_alert("Selectors may be broken for target: " + target.name)
```

2. **Run periodic validation:**
```bash
# Create a cron job to test selectors weekly
0 0 * * 0 cd /app && python test_config.py >> selector_test.log
```

3. **Track field fill rates:**
```python
from leads.models import Prospect
recent = Prospect.objects.filter(created_at__gte=last_week)
empty_count = recent.filter(event_name="", company="").count()
if empty_count > threshold:
    # Selectors may be broken
```

**Best practice:** Run `python test_config.py` weekly to catch changes early.

---

## CSS Selector Adaptation

### Q: How do I create selectors for a new platform (e.g., LinkedIn, Twitter)?

**Step-by-step guide:**

#### Step 1: Inspect the HTML
```bash
# Fetch the page
python -c "
import requests
from bs4 import BeautifulSoup
url = 'https://target-site.com/listings'
html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
soup = BeautifulSoup(html, 'lxml')
# Look at the structure
print(soup.prettify()[:3000])
"
```

#### Step 2: Find repeating items
- Look for elements that appear multiple times (events, posts, profiles)
- Common patterns: `.card`, `.item`, `article`, `[data-testid='...']`
- Count occurrences: `len(soup.select('.potential-selector'))`

#### Step 3: Identify field locations within items
```python
# Test selector on first item
item = soup.select('.event-card')[0]
print("Title:", item.select_one('h3').get_text(strip=True))
print("Link:", item.select_one('a')['href'])
```

#### Step 4: Write configuration
```json
{
  "item_selector": ".event-card",
  "fields": {
    "event_name": "h3",
    "source_url": "a@href"
  }
}
```

#### Step 5: Test before deploying
```bash
python test_config.py
```

**Example configurations:**

**LinkedIn (requires authentication):**
```json
{
  "item_selector": ".feed-shared-update-v2, article",
  "fields": {
    "full_name": ".update-components-actor__name",
    "company": ".update-components-actor__description", 
    "post_text": ".feed-shared-update-v2__description",
    "source_url": "a[href*='/in/']@href"
  },
  "target_type": "playwright",
  "timeout_seconds": 60
}
```

**Twitter/X:**
```json
{
  "item_selector": "article[data-testid='tweet']",
  "fields": {
    "full_name": "[data-testid='User-Name'] span",
    "post_text": "[data-testid='tweetText']",
    "source_url": "a[href*='/status/']@href"
  },
  "target_type": "playwright",
  "timeout_seconds": 45
}
```

### Q: What if the website uses JavaScript to load content?

**Answer:** Use `target_type: "playwright"` instead of `"html"`

**When to use Playwright:**
- Content loads via AJAX/fetch
- Infinite scroll
- "Load More" buttons
- React/Vue/Angular apps
- Social media sites (LinkedIn, Twitter, Facebook)

**Configuration:**
```json
{
  "target_type": "playwright",
  "config": {
    "timeout_seconds": 60,
    "wait_until": "networkidle"
  }
}
```

**Trade-offs:**
- ✅ Can scrape JS-heavy sites
- ✅ More reliable for dynamic content
- ❌ 5-10x slower than HTML scraping
- ❌ Higher memory usage
- ❌ Higher risk of detection

**Installation:**
```bash
# Install Playwright
pip install playwright

# Install browsers
playwright install chromium
```

### Q: How do I extract attributes (href, src, data-*) instead of text?

**Answer:** Use the `@attribute` syntax

**Examples:**
```json
{
  "fields": {
    "url": "a@href",                           // Extract href attribute
    "image": "img@src",                        // Extract src attribute
    "event_id": "[data-event-id]@data-event-id", // Extract data-* attribute
    "aria_label": "button@aria-label"          // Extract aria-label
  }
}
```

**Multiple fallbacks:**
```json
{
  "url": "a.primary-link@href, a.event-link@href, a@href"
}
```

The scraper will try each selector in order and use the first match.

### Q: Can I use complex CSS selectors?

**Answer:** Yes! The scraper supports full CSS3 selectors.

**Examples:**
```json
{
  "fields": {
    // Descendant selectors
    "title": ".card .header h3",
    
    // Child selectors
    "subtitle": ".card > .content > p",
    
    // Attribute selectors
    "external_link": "a[target='_blank']@href",
    "email_link": "a[href^='mailto:']@href",
    
    // Pseudo-classes
    "first_paragraph": "p:first-child",
    "last_item": ".item:last-of-type",
    
    // Multiple classes
    "featured": ".event.featured.highlighted",
    
    // Contains text (Note: Not supported in CSS, use regex after extraction)
    "location": ".location, .venue, .address"
  }
}
```

---

## Platform-Specific Questions

### Q: Can this scrape LinkedIn profiles?

**Answer:** Technically yes, but legally and practically difficult.

**Technical requirements:**
- Must use `target_type: "playwright"`
- Requires authentication (login cookies)
- Heavy bot detection
- Need to handle CAPTCHAs

**Legal/ethical concerns:**
- LinkedIn Terms of Service prohibit scraping
- Risk of account suspension
- GDPR/privacy concerns

**Better alternatives:**
1. **LinkedIn API** (official, paid)
2. **LinkedIn Sales Navigator** (official tool)
3. **Third-party enrichment services:**
   - Apollo.io
   - Hunter.io
   - RocketReach
   - Clearbit

**If you must scrape LinkedIn:**
- Use very long delays (10+ seconds)
- Rotate accounts/IPs
- Use residential proxies
- Be prepared for account bans
- Consult with legal counsel

### Q: Can this scrape Twitter/X?

**Answer:** Yes, but with significant limitations.

**Challenges:**
- Requires authentication (login)
- Rate limiting is strict
- API is better option
- Frequent HTML structure changes

**Configuration example:**
```json
{
  "name": "Twitter User Feed",
  "start_url": "https://twitter.com/username",
  "target_type": "playwright",
  "config": {
    "item_selector": "article[data-testid='tweet']",
    "fields": {
      "username": "[data-testid='User-Name'] [dir='ltr']",
      "tweet_text": "[data-testid='tweetText']",
      "timestamp": "time@datetime",
      "source_url": "a[href*='/status/']@href"
    },
    "timeout_seconds": 60,
    "wait_until": "networkidle"
  }
}
```

**Better alternative:**
- Twitter API v2 (official, free tier available)
- Twitter Academic Research access (if eligible)

### Q: What about Facebook Events?

**Answer:** Very difficult, not recommended.

**Why it's hard:**
- Requires login
- Aggressive bot detection
- Frequent HTML changes
- Legal/ToS concerns

**Alternatives:**
- Facebook Events API (requires app approval)
- Use official Facebook Pages/Events integrations
- Manual data entry

### Q: Which platforms work best with this scraper?

**Easy (HTML scraping):**
- ✅ Eventbrite (now working perfectly)
- ✅ Generic event listing sites
- ✅ Public RSS feeds
- ✅ Static HTML sites

**Medium (Playwright required):**
- ⚠️ Meetup (JS-heavy, but possible)
- ⚠️ Ticketmaster
- ⚠️ Eventful
- ⚠️ Brown Paper Tickets

**Difficult (authentication + anti-bot):**
- ❌ LinkedIn (use API instead)
- ❌ Facebook (use API instead)
- ❌ Twitter/X (use API instead)
- ❌ Instagram (use API instead)

---

## Automation Questions

### Q: How do I automate scraping for multiple platforms?

**Answer:** Use the two-stage scraping system now implemented.

**Stage 1: Listing pages (automatic):**
```bash
# Configure in .env
SCRAPE_ALL_INTERVAL_SECONDS=300  # Every 5 minutes

# Celery Beat automatically runs:
# - Eventbrite scraping every 2 hours
# - Meetup scraping every 3 hours
# - Other targets based on run_every_minutes
```

**Stage 2: Detail pages (optional, automatic):**
```bash
# Configure in .env
ENRICHMENT_ENABLED=1
ENRICHMENT_INTERVAL_SECONDS=1800  # Every 30 minutes
ENRICHMENT_BATCH_SIZE=25

# Celery Beat automatically:
# - Finds prospects without contact info
# - Visits detail pages
# - Extracts additional fields
# - Updates prospects
```

**Configuration per platform:**
```json
[
  {
    "name": "Eventbrite - Tech Events",
    "start_url": "https://www.eventbrite.com/d/us/tech/events/",
    "enabled": true,
    "run_every_minutes": 120
  },
  {
    "name": "Meetup - Local Events",
    "start_url": "https://www.meetup.com/find/events/",
    "enabled": true,
    "run_every_minutes": 180,
    "target_type": "playwright"
  }
]
```

### Q: How do I prevent getting blocked by websites?

**Best practices:**

1. **Use appropriate delays:**
```python
# In config
"timeout_seconds": 30,

# For enrichment
python manage.py enrich_prospects --delay 2.0
```

2. **Respect robots.txt:**
```bash
# Check if scraping is allowed
curl https://www.eventbrite.com/robots.txt
```

3. **Use realistic User-Agent:**
```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

4. **Implement rate limiting:**
```python
# Limit requests per minute
max_requests_per_minute = 30
delay = 60 / max_requests_per_minute  # 2 seconds
```

5. **Rotate User-Agents (if needed):**
```python
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
    "Mozilla/5.0 (X11; Linux x86_64)..."
]
```

6. **Use proxies (advanced):**
```python
# Residential proxies for sensitive targets
proxies = {
    "http": "http://proxy-server:8080",
    "https": "http://proxy-server:8080"
}
```

### Q: Can I schedule different scraping times for different targets?

**Answer:** Yes! Use `run_every_minutes` in each target config.

**Example:**
```json
[
  {
    "name": "High Priority - Hourly",
    "run_every_minutes": 60
  },
  {
    "name": "Medium Priority - Daily",
    "run_every_minutes": 1440
  },
  {
    "name": "Low Priority - Weekly",
    "run_every_minutes": 10080
  }
]
```

**Or use cron schedule (advanced):**
```python
# In settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "scrape-eventbrite-morning": {
        "task": "scraper.tasks.scrape_target",
        "schedule": crontab(hour=9, minute=0),  # 9 AM daily
        "args": (1,)  # target_id
    }
}
```

---

## Troubleshooting

### Q: The scraper finds items but all fields are blank. What's wrong?

**Answer:** CSS selectors don't match the actual HTML structure.

**Diagnosis:**
```bash
# Test selectors
python test_config.py

# Check recent prospects
python manage.py shell --command "
from leads.models import Prospect;
p = Prospect.objects.order_by('-created_at').first();
print('Raw payload:', p.raw_payload);
"
```

**Solution:**
1. Inspect the actual HTML (see earlier question)
2. Update selectors in `targets.json`
3. Sync to database: `python manage.py sync_targets --update`
4. Test again: `python test_config.py`

See `BLANK_DATA_FIX.md` for detailed guide.

### Q: Enrichment (Stage 2) isn't finding any contact information. Why?

**Answer:** Contact info is usually not publicly available.

**Reality check - What's typically available:**

| Platform | Listing Page | Detail Page |
|----------|--------------|-------------|
| **Eventbrite** | Event name, date | Organizer name, sometimes website |
| **Meetup** | Group name, event | Group website (if provided) |
| **LinkedIn** | Name, headline | Full profile (requires auth) |
| **Generic sites** | Event title | Sometimes email/phone |

**Email/phone are rarely public.** You'll need to:
1. Use enrichment for organizer names and websites
2. Visit organizer websites manually
3. Use platform messaging
4. Use paid enrichment services (Hunter.io, Apollo.io)

See `DATA_AVAILABILITY_GUIDE.md` for complete breakdown.

### Q: How do I test selectors without scraping live data?

**Answer:** Use the test scripts provided.

**Option 1: Test full configuration**
```bash
python test_config.py
```

**Option 2: Test specific URL**
```bash
python manage.py shell
```
```python
from scraper.services.fetch import fetch_html
from scraper.services.extract import extract_items

url = "https://www.eventbrite.com/d/us/events/"
html = fetch_html(url, headers={"User-Agent": "Mozilla/5.0"})

config = {
    "item_selector": ".event-card",
    "fields": {
        "event_name": "h3",
        "source_url": "a@href"
    }
}

items = extract_items(html, **config)
print(f"Found {len(items)} items")
print(f"First item: {items[0]}")
```

**Option 3: Use saved HTML (offline testing)**
```python
# Save HTML for offline testing
with open("test_page.html", "w", encoding="utf-8") as f:
    f.write(html)

# Test later without hitting the website
with open("test_page.html", "r", encoding="utf-8") as f:
    html = f.read()
    items = extract_items(html, **config)
```

### Q: The scraper worked before but stopped working. What happened?

**Common causes:**

1. **Website structure changed**
   - Solution: Update selectors, test with `test_config.py`

2. **Getting blocked/rate limited**
   - Check for 429, 403 errors in logs
   - Solution: Increase delays, reduce frequency

3. **Website down or URL changed**
   - Test URL manually in browser
   - Update start_url if changed

4. **Network/DNS issues**
   - Check internet connection
   - Try: `ping www.eventbrite.com`

5. **Playwright browser not installed**
   - Run: `playwright install chromium`

**Diagnosis steps:**
```bash
# 1. Check recent scrape runs
# Django Admin → Scraper → Scrape Runs → View errors

# 2. Test target manually
python manage.py shell --command "
from scraper.models import ScrapeTarget;
from scraper.services.runner import run_target;
target = ScrapeTarget.objects.get(id=1);
try:
    items = run_target(target);
    print(f'Success: {len(items)} items');
except Exception as e:
    print(f'Error: {e}');
"

# 3. Test network
curl -I https://www.eventbrite.com
```

---

## Summary

**Key takeaways:**

1. **CSS selectors are platform-specific** - Each site needs its own configuration
2. **Test before deploying** - Always use `python test_config.py`
3. **Monitor for changes** - Websites update their HTML regularly
4. **Two-stage scraping** - Fast discovery + selective enrichment
5. **Contact info is rare** - Don't expect email/phone from scraping alone
6. **Respect limits** - Use delays, follow robots.txt, respect ToS

**Recommended workflow:**
1. Use auto-discovery to generate initial config
2. Test and refine selectors manually
3. Deploy to targets.json
4. Monitor scrape runs for blank data
5. Update selectors when sites change
6. Use enrichment selectively for high-value prospects

**Need help?**
- Check `BLANK_DATA_FIX.md` for selector issues
- Check `DATA_AVAILABILITY_GUIDE.md` for platform capabilities  
- Check `TWO_STAGE_SCRAPING.md` for enrichment setup
- Check `TROUBLESHOOTING.md` for common errors