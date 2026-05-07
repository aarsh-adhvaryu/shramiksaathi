import os
import json
import PyPDF2
from sentence_transformers import SentenceTransformer
import faiss

ROOT = os.path.join(os.path.dirname(__file__), "..")
KB_PATH = os.path.join(ROOT, "data", "kb.jsonl")
INDEX_PATH = os.path.join(ROOT, "index", "faiss_index_finetuned.bin")
STORE_PATH = os.path.join(ROOT, "index", "chunk_store.json")
MODEL_PATH = os.path.join(ROOT, "out", "retriever_finetuned")

def extract_pdf_text(pdf_path):
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception as e:
        print(f"Could not read PDF: {e}")
    return text

def extract_readme_text(readme_path):
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Could not read README: {e}")
        return ""

def chunk_text(text, chunk_size=300, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def ingest():
    print("Extracting text from project files...")
    pdf_path = os.path.join(ROOT, "ShramikSaathi.pdf")
    readme_path = os.path.join(ROOT, "README.md")
    
    pdf_text = extract_pdf_text(pdf_path)
    readme_text = extract_readme_text(readme_path)
    
    pdf_chunks = chunk_text(pdf_text)
    readme_chunks = chunk_text(readme_text)
    
    new_docs = []
    for i, c in enumerate(pdf_chunks):
        new_docs.append({
            "doc_id": f"PROJECT_PDF_CH_{i}",
            "domain": "general",
            "content": f"From ShramikSaathi.pdf Report: {c}"
        })
    for i, c in enumerate(readme_chunks):
        new_docs.append({
            "doc_id": f"PROJECT_README_CH_{i}",
            "domain": "general",
            "content": f"From README.md documentation: {c}"
        })
        
    print(f"Generated {len(new_docs)} new chunks.")
    if not new_docs:
        print("Nothing to ingest.")
        return
        
    print("Loading retriever model...")
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Fine-tuned retriever not found at {MODEL_PATH}")
        return
    model = SentenceTransformer(MODEL_PATH)
    
    print("Encoding new chunks...")
    texts = [d["content"] for d in new_docs]
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    
    print("Updating KB files...")
    # Append to kb.jsonl
    with open(KB_PATH, "a", encoding="utf-8") as f:
        for doc in new_docs:
            f.write(json.dumps(doc) + "\n")
            
    # Load and append to FAISS
    index = faiss.read_index(INDEX_PATH)
    index.add(embeddings)
    faiss.write_index(index, INDEX_PATH)
    
    # Append to chunk_store
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        store = json.load(f)
    for doc in new_docs:
        store[doc["doc_id"]] = doc
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
        
    print("Ingestion complete! FAISS index updated.")

if __name__ == "__main__":
    ingest()
