import requests
from bs4 import BeautifulSoup
import json

FAQ_URL = "https://www.epfindia.gov.in/site_en/FAQ.php"

def scrape_epfo_faq(url=FAQ_URL):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    faqs = []
    tables = soup.find_all("table")  # FAQs are inside tables

    faq_id = 0
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:  # usually Q in first col, A in second
                question = cols[0].get_text(" ", strip=True)
                answer = cols[1].get_text(" ", strip=True)

                if question and answer:
                    faqs.append({
                        "doc_id": f"FAQ_{faq_id}",
                        "title": question,
                        "content": answer,
                        "source_url": url,
                        "effective_date": None,
                        "supersedes": None,
                        "domain": "faq",
                        "section_id": "GENERAL",
                        "span_start": 0,
                        "span_end": len(answer),
                        "conditions": [],
                        "required_slots": [],
                        "forms": [],
                        "chunk_id": f"FAQ_{faq_id}_chunk_0",
                        "chunk_index": 0,
                        "total_chunks": 1,
                        "language": "en",
                        "query_type": ["faq"]
                    })
                    faq_id += 1

    return faqs

faqs = scrape_epfo_faq()
with open("faq.json", "w", encoding="utf-8") as f:
    json.dump(faqs, f, indent=2)

print(f"Scraped {len(faqs)} FAQs")
