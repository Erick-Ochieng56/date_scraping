import requests
from bs4 import BeautifulSoup


def analyze_eventbrite():
    url = "https://www.eventbrite.com/d/united-states/tech/events/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print("Fetching Eventbrite page...")
    r = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(r.text, "lxml")

    cards = soup.select(".event-card")
    print(f"\n=== FOUND {len(cards)} EVENT CARDS ===\n")

    for i, card in enumerate(cards[:3]):
        print(f"Card {i + 1}:")

        # Try to find title
        h3 = card.select_one("h3")
        title = h3.get_text(strip=True) if h3 else "NOT FOUND"
        print(f"  Title (h3): {title}")

        # Try to find link
        link = card.select_one("a.event-card-link")
        href = link.get("href", "") if link else "NOT FOUND"
        print(f"  Link: {href}")

        # Try to find aria-label
        aria_label = link.get("aria-label", "") if link else "NOT FOUND"
        print(f"  Aria-label: {aria_label}")

        # Try to find date/time info
        paragraphs = card.select("p")
        print(f"  Paragraphs found: {len(paragraphs)}")
        for j, p in enumerate(paragraphs[:3]):
            print(f"    P{j + 1}: {p.get_text(strip=True)}")

        # Try to find location
        location_text = ""
        for p in paragraphs:
            text = p.get_text(strip=True)
            if any(
                keyword in text.lower()
                for keyword in [
                    "convention",
                    "center",
                    "hotel",
                    "venue",
                    "street",
                    "online",
                ]
            ):
                location_text = text
                break
        print(f"  Location: {location_text or 'NOT FOUND'}")

        print()


if __name__ == "__main__":
    analyze_eventbrite()
