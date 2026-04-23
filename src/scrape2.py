import requests
from bs4 import BeautifulSoup
import json

EPFIGMS_URL = "https://epfigms.gov.in"

def scrape_epfigms(url=EPFIGMS_URL):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    grievances = []
    gid = 0

    # Example: grievance categories often appear in <table> or <ul>/<li>
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2:
                category = cols[0].get_text(" ", strip=True)
                details = cols[1].get_text(" ", strip=True)

                if category and details:
                    grievances.append({
                        "doc_id": f"GRIEV_{gid}",
                        "title": category,
                        "content": details,
                        "source_url": url,
                        "effective_date": None,
                        "supersedes": None,
                        "domain": "grievance",
                        "section_id": "EPFIGMS",
                        "span_start": 0,
                        "span_end": len(details),
                        "conditions": [],
                        "required_slots": [],
                        "forms": [],
                        "chunk_id": f"GRIEV_{gid}_chunk_0",
                        "chunk_index": 0,
                        "total_chunks": 1,
                        "language": "en",
                        "query_type": ["grievance"]
                    })
                    gid += 1

    # Also scrape lists (<ul>/<li>) if present
    lists = soup.find_all("ul")
    for ul in lists:
        items = ul.find_all("li")
        for item in items:
            text = item.get_text(" ", strip=True)
            if text:
                grievances.append({
                    "doc_id": f"GRIEV_{gid}",
                    "title": "Grievance Point",
                    "content": text,
                    "source_url": url,
                    "effective_date": None,
                    "supersedes": None,
                    "domain": "grievance",
                    "section_id": "EPFIGMS",
                    "span_start": 0,
                    "span_end": len(text),
                    "conditions": [],
                    "required_slots": [],
                    "forms": [],
                    "chunk_id": f"GRIEV_{gid}_chunk_0",
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "language": "en",
                    "query_type": ["grievance"]
                })
                gid += 1

    return grievances

grievances = scrape_epfigms()
with open("epfigms.json", "w", encoding="utf-8") as f:
    json.dump(grievances, f, indent=2)

print(f"Scraped {len(grievances)} grievance entries")
