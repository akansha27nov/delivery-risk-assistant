"""
Phase 2, Step 1: Document loading.

Reads every file in data/ and normalizes it into one of two shapes, with a
"project" tag attached so results never get jumbled across projects later:
  - text/markdown -> {"source", "type": "text", "content", "project"}
  - CSV           -> {"source", "type": "csv", "rows", "project"}

Project assignment comes from project_manifest.json, NOT filename guessing
(e.g. "starts with nova_") -- every file in data/ must be explicitly listed
there. If a new file is added to data/ without being added to the
manifest, loading fails loudly instead of silently leaving it untagged and
letting it bleed into the wrong project's risk analysis.
"""

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
MANIFEST_PATH = Path(__file__).parent.parent / "project_manifest.json"

TEXT_EXTENSIONS = {".md", ".txt"}
CSV_EXTENSIONS = {".csv"}


def _load_manifest(manifest_path: Path = MANIFEST_PATH) -> dict:
    """Return {filename: project_id} flattened from project_manifest.json."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    file_to_project = {}
    for project_id, info in manifest.items():
        for filename in info["files"]:
            file_to_project[filename] = project_id
    return file_to_project


def load_documents(data_dir: Path = DATA_DIR, manifest_path: Path = MANIFEST_PATH) -> list[dict]:
    file_to_project = _load_manifest(manifest_path)

    documents = []
    for path in sorted(data_dir.iterdir()):
        if path.suffix not in TEXT_EXTENSIONS | CSV_EXTENSIONS:
            continue  # skip non-corpus files (.DS_Store, etc.)

        if path.name not in file_to_project:
            raise ValueError(
                f"'{path.name}' is in data/ but not listed in "
                f"project_manifest.json. Add it under the correct project's "
                f"\"files\" list before loading."
            )
        project = file_to_project[path.name]

        if path.suffix in TEXT_EXTENSIONS:
            documents.append({
                "source": path.name,
                "type": "text",
                "content": path.read_text(encoding="utf-8"),
                "project": project,
            })
        else:
            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            documents.append({
                "source": path.name,
                "type": "csv",
                "rows": rows,
                "project": project,
            })
    return documents


if __name__ == "__main__":
    docs = load_documents()
    print(f"Loaded {len(docs)} source documents:\n")
    for d in docs:
        tag = f"[{d['project']}]"
        if d["type"] == "text":
            print(f"  {tag:<8} {d['source']:<30} text   {len(d['content']):>5} chars")
        else:
            print(f"  {tag:<8} {d['source']:<30} csv    {len(d['rows']):>5} rows")
