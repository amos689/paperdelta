"""Convert the identical locked native-v2 sources with optional Docling.

Run in a separate environment; Docling is not a PaperDelta dependency. Keep its
original structured output for independent position/table scoring. No OCR.
"""

import argparse
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=["development", "held-out"])
    parser.add_argument("--backend", choices=["default", "pdfium"], default="default")
    args = parser.parse_args()
    if args.split == "held-out":
        assert (CORPUS / "implementation-lock.json").exists()
        assert (CORPUS / "held-out-gold-lock.json").exists()
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    backend = {}
    if args.backend == "pdfium":
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

        backend["backend"] = PyPdfiumDocumentBackend
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=options,
                **backend,
            )
        }
    )
    output = ROOT / "build/native-v2/docling" / (args.split + "-" + args.backend)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for paper in json.loads((CORPUS / "sources.json").read_text("utf-8"))["papers"]:
        if paper["split"] != args.split:
            continue
        for filename, metadata in paper["files"].items():
            source = CORPUS / "papers" / paper["id"] / filename
            assert hashlib.sha256(source.read_bytes()).hexdigest() == metadata["sha256"]
            dest = output / f"{paper['id']}-{Path(filename).suffix[1:]}"
            if dest.with_suffix(".record.json").exists():
                records.append(json.loads(dest.with_suffix(".record.json").read_text("utf-8")))
                continue
            start = time.perf_counter()
            record = {
                "case": paper["id"],
                "file": filename,
                "source_sha256": metadata["sha256"],
                "docling": importlib.metadata.version("docling"),
            }
            record["backend"] = args.backend
            try:
                result = converter.convert(
                    source, max_num_pages=200, max_file_size=32 * 1024 * 1024
                )
                result.document.save_as_json(dest.with_suffix(".json"))
                record.update(
                    status=str(result.status),
                    tables=len(result.document.tables),
                    text_items=len(result.document.texts),
                )
            except Exception as error:
                record.update(status="failed", error=f"{type(error).__name__}: {error}")
            record["seconds"] = round(time.perf_counter() - start, 3)
            dest.with_suffix(".record.json").write_text(json.dumps(record, indent=2), "utf-8")
            records.append(record)
            print(json.dumps(record), flush=True)
    (output / "runs.json").write_text(json.dumps(records, indent=2), "utf-8")


if __name__ == "__main__":
    main()
