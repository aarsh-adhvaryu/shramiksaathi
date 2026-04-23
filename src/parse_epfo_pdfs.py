"""
EPFO Knowledge Base Document Parser (Windows Ready)
"""

import os
import re
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime

import fitz
import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------- YOUR PATH (UPDATED) ---------------- #

INPUT_DIR = r"C:\Users\sniks\OneDrive\Desktop\dl\claude data"
OUTPUT_FILE = "kb.jsonl"
BUILD_INDEX = False     # set True if you want FAISS
USE_LLM = False         # set True if using Ollama

# ---------------- CONFIG ---------------- #

CHUNK_SIZE = 512
WORDS_PER_TOKEN = 0.75
MAX_CHUNK_WORDS = int(CHUNK_SIZE * WORDS_PER_TOKEN)
CHUNK_OVERLAP = 64

# ---------------- DATA CLASSES ---------------- #

@dataclass
class Condition:
    slot: str
    operator: str
    value: object
    outcome: str
    type: str
    raw_text: str = ""


@dataclass
class KBDocument:
    doc_id: str
    title: str
    content: str
    source_url: str
    effective_date: str
    supersedes: Optional[str]
    domain: str
    section_id: str
    span_start: int
    span_end: int
    conditions: list
    required_slots: list
    forms: list
    chunk_id: str
    chunk_index: int
    total_chunks: int
    language: str = "en"
    query_type: list = field(default_factory=list)
    source_file: str = ""
    page_numbers: list = field(default_factory=list)

# ---------------- PDF EXTRACTION ---------------- #

def extract_text(pdf_path):
    pages = []
    pos = 0

    doc = fitz.open(pdf_path)

    # open pdfplumber once (important)
    try:
        plumber_pdf = pdfplumber.open(pdf_path)
    except:
        plumber_pdf = None

    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")

        # fallback safely
        if len(text.strip()) < 50 and plumber_pdf:
            try:
                if i - 1 < len(plumber_pdf.pages):
                    text = plumber_pdf.pages[i - 1].extract_text() or ""
            except:
                text = ""

        pages.append({
            "page": i,
            "text": text,
            "start": pos,
            "end": pos + len(text)
        })
        pos += len(text)

    if plumber_pdf:
        plumber_pdf.close()

    return pages

# ---------------- CLEANING ---------------- #

def clean_text(text):
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"Page \d+", "", text)
    return text.strip()

# ---------------- CHUNKING ---------------- #

def chunk_text(text, pages):
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current = []
    word_count = 0
    start = 0

    for sent in sentences:
        words = sent.split()

        if word_count + len(words) > MAX_CHUNK_WORDS:
            chunk_str = " ".join(current)
            chunks.append({
                "text": chunk_str,
                "span_start": start,
                "span_end": start + len(chunk_str),
                "pages": [p["page"] for p in pages]
            })

            current = current[-CHUNK_OVERLAP:] + words
            word_count = len(current)
            start += len(chunk_str)

        else:
            current.extend(words)
            word_count += len(words)

    if current:
        chunk_str = " ".join(current)
        chunks.append({
            "text": chunk_str,
            "span_start": start,
            "span_end": start + len(chunk_str),
            "pages": [p["page"] for p in pages]
        })

    return chunks

# ---------------- CONDITIONS ---------------- #

def extract_conditions_rulebased(text):
    conditions = []
    t = text.lower()

    if "less than 5 years" in t:
        conditions.append(Condition("service_years", "lt", 5, "TDS_APPLICABLE", "WARNING"))

    if "more than 50000" in t or "above 50000" in t:
        conditions.append(Condition("withdrawal_amount", "gt", 50000, "TDS_APPLICABLE", "WARNING"))

    if "kyc" in t and "complete" in t:
        conditions.append(Condition("kyc_status", "eq", "complete", "ELIGIBLE", "MANDATORY"))

    return conditions


def extract_conditions_llm(text, doc_id):
    import subprocess

    prompt = f"Extract EPFO conditions as JSON:\n{text[:1500]}"

    try:
        result = subprocess.run(
            ["ollama", "run", "llama3"],
            input=prompt.encode(),
            stdout=subprocess.PIPE,
            timeout=30
        )

        output = result.stdout.decode()
        items = json.loads(output)

        return [Condition(**i) for i in items]

    except:
        log.warning("LLM failed → fallback")
        return extract_conditions_rulebased(text)

# ---------------- HELPERS ---------------- #

def extract_forms(text):
    return re.findall(r'Form\s?\d+[A-Z]*', text)

def infer_domain(text):
    t = text.lower()
    if "withdrawal" in t: return "withdrawal"
    if "kyc" in t: return "kyc"
    if "pension" in t: return "pension"
    if "tds" in t: return "tax"
    return "general"

# ---------------- MAIN ---------------- #

def process_pdf(path):
    pages = extract_text(path)
    full_text = clean_text(" ".join(p["text"] for p in pages))

    title = Path(path).stem
    domain = infer_domain(full_text)
    date = datetime.now().strftime("%Y-%m-%d")
    doc_id = f"{domain}_{date[:4]}_{title}"

    chunks = chunk_text(full_text, pages)
    docs = []

    for i, chunk in enumerate(chunks):
        text = chunk["text"]

        if USE_LLM:
            conditions = extract_conditions_llm(text, doc_id)
        else:
            conditions = extract_conditions_rulebased(text)

        doc = KBDocument(
            doc_id=doc_id,
            title=title,
            content=text,
            source_url=path,
            effective_date=date,
            supersedes=None,
            domain=domain,
            section_id=f"{doc_id}_S{i}",
            span_start=chunk["span_start"],
            span_end=chunk["span_end"],
            conditions=[asdict(c) for c in conditions],
            required_slots=[c.slot for c in conditions],
            forms=extract_forms(text),
            chunk_id=f"{doc_id}_chunk_{i}",
            chunk_index=i,
            total_chunks=len(chunks),
            source_file=path,
            page_numbers=chunk["pages"]
        )

        docs.append(doc)

    return docs


def process_all():
    files = list(Path(INPUT_DIR).glob("*.pdf"))

    with open(OUTPUT_FILE, "w") as f:
        for file in files:
            log.info(f"Processing {file}")
            docs = process_pdf(str(file))

            for d in docs:
                f.write(json.dumps(asdict(d)) + "\n")

    print(f"\n✅ DONE → Output saved at {OUTPUT_FILE}")


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    process_all()