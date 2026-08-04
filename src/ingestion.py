"""
Phase 2, Step 1: Document loading.

Reads every file in data/ and normalizes it into one of two shapes:
  - text/markdown files -> {"source": filename, "type": "text", "content": str}
  - CSV files           -> {"source": filename, "type": "csv", "rows": [dict, ...]}

CSV rows are kept structured (not flattened into raw text) deliberately: a
naive character-split of a CSV would slice mid-row and produce garbage
chunks. Chunking a CSV should happen row-by-row instead, so a citation like
"ticket_export.csv — row ATL-142" stays exact.
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

TEXT_EXTENSIONS = {".md", ".txt"}
CSV_EXTENSIONS = {".csv"}


def load_documents(data_dir: Path = DATA_DIR) -> list[dict]:
    documents = []
    for path in sorted(data_dir.iterdir()):
        if path.suffix in TEXT_EXTENSIONS:
            documents.append({
                "source": path.name,
                "type": "text",
                "content": path.read_text(encoding="utf-8"),
            })
        elif path.suffix in CSV_EXTENSIONS:
            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            documents.append({
                "source": path.name,
                "type": "csv",
                "rows": rows,
            })
        else:
            continue  # skip non-corpus files (.DS_Store, etc.)
    return documents


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} source documents:\n")
    for d in docs:
        if d["type"] == "text":
            print(f"  {d['source']:<30} text   {len(d['content']):>5} chars")
        else:
            print(f"  {d['source']:<30} csv    {len(d['rows']):>5} rows")
