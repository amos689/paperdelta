"""Prepare independent development material without importing the product parser."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from prepare_native_v2 import extract_pdf, extract_word

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v3"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=["development", "held-out"])
    args = parser.parse_args()
    assert (CORPUS / "pre-development-lock.json").is_file()
    if args.split == "held-out":
        assert (CORPUS / "implementation-lock.json").is_file(), "Freeze implementation first"
    output = ROOT / "build/native-v3" / args.split
    assert not output.exists(), "Preserve previous independent annotation material"
    sources = json.loads((CORPUS / "sources.json").read_text("utf-8"))
    records = []
    for paper in sources["papers"]:
        if paper["split"] != args.split:
            continue
        dest = output / paper["id"]
        dest.mkdir(parents=True)
        for filename, metadata in paper["files"].items():
            path = CORPUS / "papers" / paper["id"] / filename
            assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
            if filename.endswith(".pdf"):
                independent = extract_pdf(path)
                (dest / "independent-pdf.json").write_text(
                    json.dumps(independent, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                (dest / "pdf-text.txt").write_text(
                    "\n\n".join(f"PAGE {page['page']}\n{page['text']}" for page in independent),
                    encoding="utf-8",
                )
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        "1",
                        "-l",
                        "1",
                        "-scale-to",
                        "1500",
                        "-png",
                        "-singlefile",
                        str(path),
                        str(dest / "original-page-1"),
                    ],
                    check=True,
                )
                records.append({"family": paper["id"], "file": filename, "pages": len(independent)})
            else:
                independent = extract_word(path)
                (dest / "independent-docx.json").write_text(
                    json.dumps(independent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                records.append(
                    {"family": paper["id"], "file": filename, "tables": len(independent["tables"])}
                )
            assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
    (output / "preparation.json").write_text(
        json.dumps({"split": args.split, "records": records}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
