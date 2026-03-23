# Data Availability Guide - Listing Pages vs Detail Pages

## Overview

When scraping event websites, it's crucial to understand **what data is available where**. Most sites have two types of pages:

1. **Listing Pages** - Show multiple events (limited data per event)
2. **Detail Pages** - Show one event (complete data)

Understanding this distinction prevents blank data issues and helps you design effective scraping strategies.

## Eventbrite Example

### Listing Page (Search Results)
**URL:** `https://www.eventbrite.com/d/united-states/tech/events/`

**Available Data:**
- ✅ Event Name/Title
- ✅ Event URL (link to detail page)
- ✅ Date/Time
- ✅ Venue/Location Name
- ✅ Price indicator (Free, Paid, Starting at $X)
- ✅ Thumbnail image
- ❌ Organizer contact info (email, phone)
- ❌ Full event description
- ❌ Organizer website
- ❌ Detailed address
- ❌ Registration/attendee info

**HTML Structure:**
```html
<div class="event-card">
  <a href="/e/event-name-tickets-123" aria-label="View Event Name">
    <img src="thumbnail.jpg" />
  </a>
  <h3>Event Name</h3>
  <p>Venue Name</p>
  <p>Friday • 6:00 PM</p>
</div>
```

**Recommended Selectors:**
```json
{
  "item_selector": ".event-card",
  "fields": {
    "event_name": "h3",
    "source_url": "a.event-card-link@href",
    "company": "a.event-card-link@aria-label"
  }
}
```

### Detail Page (Individual Event)
**URL:** `https://www.eventbrite.com/e/event-name-tickets-123456`

**Available Data:**
- ✅ Event Name/Title
- ✅ Full Description
- ✅ Date/Time (precise)
- ✅ Venue (full address)
- ✅ Organizer Name
- ✅ Organizer Profile Link
- ⚠️ Organizer Email (sometimes, if public)
- ⚠️ Organizer Phone (rarely, if public)
- ✅ Ticket prices
- ✅ Number of attendees (sometimes)
- ✅ Tags/Categories
- ✅ Social share links

**Note:** Contact information (email, phone) is usually NOT public on Eventbrite. You'd need to:
1. Visit organizer profile page
2. Look for "Contact" section
3. Even then, many organizers hide this info

## Meetup Example

### Listing Page
**URL:** `https://www.meetup.com/find/events/`

**Available Data:**
- ✅ Event Title
- ✅ Event URL
- ✅ Date/Time
- ✅ Group Name (organizer)
- ✅ Group Logo
- ✅ Attendee count
- ✅ Online/In-person indicator
- ❌ Full description
- ❌ Organizer contact
- ❌ Detailed location

### Detail Page
**URL:** `https://www.meetup.com/group-name/events/event-id/`

**Available Data:**
- ✅ Full description
- ✅ Group/Organizer info
- ✅ Group website (if provided)
- ✅ Detailed location/address
- ✅ RSVP list (if public)
- ⚠️ Organizer email (rarely public)
- ❌ Direct phone numbers

## Generic Event Sites

### Typical Listing Page Data
Most event listing pages provide:
- ✅ Event title
- ✅ Date/time
- ✅ Location name
- ✅ Link to details
- ✅ Category/tags
- ❌ Contact information
- ❌ Full descriptions

### Typical Detail Page Data
Most event detail pages provide:
- ✅ All listing data +
- ✅ Full description
- ✅ Organizer name
- ⚠️ Organizer website (50% of sites)
- ⚠️ Contact email (30% of sites)
- ⚠️ Phone number (10% of sites)

## Scraping Strategy Recommendations

### Strategy 1: Listing Page Only (Fast, Limited Data)

**Use when:**
- You need bulk discovery of events
- Contact info not critical
- Speed is important
- Low server load required

**Configuration:**
```json
{
  "name": "Quick Event Discovery",
  "start_url": "https://site.com/events",
  "config": {
    "item_selector": ".event-item",
    "fields": {
      "event_name": "h2, h3, .title",
      "source_url": "a@href"
    },
    "max_pages": 10
  }
}
```

**Pros:**
- Fast (1-2 seconds per page)
- Efficient (10-50 events per page)
- Low risk of blocking
- Good for initial discovery

**Cons:**
- No contact information
- Limited event details
- Can't pre-qualify leads

### Strategy 2: Two-Stage Scraping (Slow, Complete Data)

**Use when:**
- You need contact information
- Lead quality over quantity
- You have time for detailed scraping
- You're okay with higher server load

**Implementation:**

**Stage 1 - Listing Page:**
```json
{
  "name": "Stage 1: Collect URLs",
  "config": {
    "item_selector": ".event-card",
    "fields": {
      "event_name": "h3",
      "source_url": "a@href"
    }
  }
}
```

**Stage 2 - Detail Pages:**
```python
# Custom scraper or follow-up task
for prospect in Prospect.objects.filter(company=''):
    detail_html = fetch_html(prospect.source_url)
    # Extract organizer, email, phone, etc.
    prospect.company = extract_organizer(detail_html)
    prospect.email = extract_email(detail_html)
    prospect.save()
```

**Pros:**
- Complete data collection
- Better lead quality
- Can extract contact info (if available)

**Cons:**
- Much slower (1-2 seconds per event)
- Higher server load
- Higher risk of IP blocking
- Requires more complex logic

### Strategy 3: Hybrid Approach (Recommended)

**Use when:**
- You want balance between speed and data quality
- You can do follow-up research manually
- You're building a prospect pipeline

**Implementation:**
1. Scrape listing pages for bulk discovery (automated)
2. Store event URLs in Prospects
3. Sync to Google Sheets
4. Team manually visits promising event pages
5. Team fills in contact info for qualified leads
6. Convert to Leads when ready

**Configuration:**
```json
{
  "name": "Hybrid Discovery",
  "config": {
    "item_selector": ".event-card",
    "fields": {
      "event_name": "h3",
      "source_url": "a@href"
    },
    "max_pages": 5
  }
}
```

**Workflow:**
```
1. Automated scraping → Prospects with basic info
2. Auto-sync to Google Sheets
3. Team reviews and researches manually
4. Team adds contact info to promising prospects
5. Mark as "Contacted" in Sheets
6. Convert to Leads for CRM workflow
```

**Pros:**
- Fast automated discovery
- Human intelligence for qualification
- Lower risk of blocking
- Flexible data collection

**Cons:**
- Requires manual work
- Not fully automated
- Contact info not immediate

## Contact Information Availability by Platform

### Eventbrite
- **Email:** ❌ Almost never public on listing or detail pages
- **Phone:** ❌ Never public
- **Website:** ⚠️ Sometimes on organizer profile (requires extra click)
- **Best Approach:** Focus on event discovery, manual follow-up via event registration

### Meetup
- **Email:** ❌ Rarely public
- **Phone:** ❌ Never public
- **Website:** ✅ Often in group profile
- **Best Approach:** Scrape group websites, use Meetup messaging for contact

### Facebook Events
- **Email:** ❌ Never public
- **Phone:** ❌ Never public
- **Website:** ⚠️ Sometimes in page info
- **Best Approach:** Use Facebook Messenger, visit linked pages

### Independent Event Sites
- **Email:** ⚠️ 30-50% of sites
- **Phone:** ⚠️ 10-30% of sites
- **Website:** ✅ 70-90% of sites
- **Best Approach:** Check detail pages, look for "Contact Organizer" sections

## Why Contact Info Is Usually Hidden

Event platforms intentionally hide contact information to:

1. **Prevent spam:** Protect organizers from unsolicited messages
2. **Keep users on platform:** Force communication through platform
3. **Privacy compliance:** GDPR, CCPA require consent for contact info
4. **Anti-scraping:** Detect and block automated data collection
5. **Monetization:** Charge for sponsored/promoted contact

## Alternative Data Sources for Contact Info

If listing/detail pages don't have contact info, try:

### 1. Organizer Profile Pages
```
Event Page → "Hosted by XYZ" → XYZ Profile → Contact/About
```

### 2. Linked Websites
```
Event Page → Organizer Website → Contact Us page
```

### 3. Social Media
```
Event Page → Facebook/Twitter/LinkedIn links → Bio/About
```

### 4. Domain WHOIS
```python
import whois
domain_info = whois.whois('organizerwebsite.com')
email = domain_info.emails  # Sometimes available
```

### 5. Company Databases
- LinkedIn Sales Navigator
- Hunter.io (email finder)
- RocketReach
- Apollo.io
- Clearbit

### 6. Google Search
```
site:organizerwebsite.com contact
site:organizerwebsite.com email
"organizer name" email
```

## Recommended Workflow for This Tool

Based on the current architecture, here's the recommended approach:

### Phase 1: Automated Discovery (Current)
```
Scrape listing pages → Create Prospects → Sync to Google Sheets
```

**Collect:**
- Event name
- Event URL
- Date/time (if available)
- Location (if available)

### Phase 2: Manual Qualification (Manual)
```
Team reviews Google Sheets → Researches promising events → Adds contact info
```

**Research methods:**
- Visit event detail pages
- Check organizer profiles
- Google search for organization
- Use LinkedIn/Hunter.io
- Check social media

### Phase 3: Lead Conversion (Semi-automated)
```
Mark as "Contacted" in Sheets → Convert to Lead in Django → Sync to CRM
```

## Setting Realistic Expectations

### What Automated Scraping CAN Do:
- ✅ Discover events at scale (100s-1000s)
- ✅ Extract basic information (name, date, location)
- ✅ Collect event URLs for follow-up
- ✅ Monitor for new events continuously
- ✅ Aggregate across multiple platforms

### What Automated Scraping CANNOT Do:
- ❌ Extract hidden contact information
- ❌ Bypass privacy protections
- ❌ Qualify lead quality automatically
- ❌ Replace human research and outreach
- ❌ Guarantee email/phone for every event

### The Bottom Line:
**Automated scraping is for DISCOVERY, not QUALIFICATION.**

Use it to build a pipeline of potential leads, then use human intelligence (or paid APIs) to qualify and enrich the data.

## Updating Your Scraping Configs

When creating new targets, ask yourself:

1. **What page am I scraping?**
   - Listing page → basic info only
   - Detail page → might have contact info

2. **What data is actually visible?**
   - Inspect HTML first
   - Don't assume email/phone will be there

3. **Is multi-stage scraping worth it?**
   - Listing + Details = 10-50x slower
   - Only do it if contact info is reliably available

4. **Should I automate or manual?**
   - Automate: High-volume discovery
   - Manual: Qualification and enrichment

## Examples of Working Configs

### Listing Page Scraper (Recommended)
```json
{
  "name": "Event Discovery - Fast",
  "start_url": "https://eventbrite.com/d/us/tech/events/",
  "target_type": "html",
  "run_every_minutes": 120,
  "config": {
    "item_selector": ".event-card",
    "fields": {
      "event_name": "h3",
      "source_url": "a.event-card-link@href"
    },
    "max_pages": 5
  }
}
```

### Detail Page Scraper (When Needed)
```json
{
  "name": "Event Details - Slow",
  "start_url": "https://eventbrite.com/e/specific-event-123",
  "target_type": "html",
  "config": {
    "item_selector": "main, article, .event-details",
    "fields": {
      "event_name": "h1",
      "description": ".description, .event-description",
      "company": ".organizer-name, .hosted-by",
      "website": "a.organizer-website@href"
    }
  }
}
```

## Summary

- **Listing pages** = discovery (fast, limited data)
- **Detail pages** = enrichment (slow, more data, maybe contact info)
- **Contact info** = usually NOT available without extra work
- **Best strategy** = automated discovery + manual qualification
- **Set expectations** = scraping finds leads, humans qualify them

This tool is designed for **Phase 1 (Discovery)**. Use it to build your pipeline, then do manual research or use paid APIs for contact enrichment.