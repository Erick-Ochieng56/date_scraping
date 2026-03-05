import requests
import bs4

url = "https://www.eventbrite.com/d/united-states/tech/events/"
headers = {"User-Agent": "Mozilla/5.0"}
print("Fetching...")
r = requests.get(url, headers=headers, timeout=30)
soup = bs4.BeautifulSoup(r.text, 'lxml')
cards = soup.select('.event-card')
if cards:
    with open("card_dump.txt", "w", encoding="utf-8") as f:
        f.write("CARD 1:\n" + cards[0].prettify() + "\n")
        f.write("---\n")
        f.write("CARD 2:\n" + cards[1].prettify() + "\n")
        print("Wrote structure to card_dump.txt")
