import requests
import json

def fetch_and_dump(url, filename):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    print(f"Fetching {url}...")
    try:
        r = requests.get(url, headers=headers, timeout=30)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(r.text)
        print(f"Saved {len(r.text)} bytes to {filename}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    fetch_and_dump("https://www.eventbrite.com/d/united-states/tech/events/", "eventbrite_dump.html")
    fetch_and_dump("https://www.meetup.com/find/events/", "meetup_dump.html")
