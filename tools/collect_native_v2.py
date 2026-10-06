"""Select licensed native inputs using publisher metadata, never parser results."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v2"
EXCLUDED_CAPTIONS = re.compile(
    r"checklist|questionnaire|search strateg|quality assessment|primer|antibod|protocol",
    re.I,
)
STRATA = ("2024-01-01", "2024-07-01", "2025-01-01", "2025-07-01")


def fetch(url):
    with urlopen(
        Request(url, headers={"User-Agent": "PaperDelta licensed native-document evaluation"}),
        timeout=45,
    ) as response:
        data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise ValueError("Original exceeds declared 32 MiB limit")
        return data, response.geturl()


def save_new(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"Refusing to replace recorded metadata: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def plos_metadata(item):
    doi = item["id"]
    address = "https://journals.plos.org/plosone/article?id=" + doi
    raw, final = fetch(address)
    tree = html.fromstring(raw)
    links = tree.xpath("//a/@href")
    if not any("creativecommons.org/licenses/by/4.0" in url for url in links):
        return None
    meta = {}
    for element in tree.xpath('//meta[starts-with(@name,"citation_")]'):
        meta.setdefault(element.get("name"), []).append(element.get("content"))
    candidates = []
    for heading in tree.xpath('//h3[contains(@class,"siTitle")]'):
        caption = " ".join(heading.text_content().split())
        if "table" not in caption.lower() or EXCLUDED_CAPTIONS.search(caption):
            continue
        following = heading.getnext()
        formats = []
        for _ in range(4):
            if following is None or following.tag == "h3":
                break
            formats.append(" ".join(following.text_content().split()))
            following = following.getnext()
        hrefs = heading.xpath('.//a[contains(@href,"type=supplementary")]/@href')
        if hrefs and any("(DOCX)" in value for value in formats):
            candidates.append({"caption": caption, "url": urljoin(address, hrefs[0])})
    if not candidates or not meta.get("citation_pdf_url"):
        return None
    selected = candidates[0]
    return {
        "id": "plos-" + doi.rsplit(".", 1)[1],
        "doi": doi,
        "publisher": "PLOS ONE",
        "title": item["title"],
        "published": item["publication_date"],
        "article_url": final,
        "authors": meta.get("citation_author", []),
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "metadata_sha256": hashlib.sha256(raw).hexdigest(),
        "attachment_caption": selected["caption"],
        "urls": {
            "article.pdf": meta["citation_pdf_url"][0],
            "supplement.docx": selected["url"],
        },
    }


def select_plos(start):
    query = {
        "q": f"publication_date:[{start}T00:00:00Z TO *] AND doc_type:full "
        'AND article_type:"Research Article"',
        "fq": "journal_key:PLoSONE",
        "fl": "id,title,publication_date",
        "sort": "publication_date asc,id asc",
        "rows": "60",
    }
    raw, _ = fetch("https://api.plos.org/search?" + urlencode(query))
    inspected, selected = [], []
    for item in json.loads(raw)["response"]["docs"]:
        try:
            metadata = plos_metadata(item)
        except Exception as error:
            # Retain transport failures; selection never sees original document contents.
            inspected.append({"doi": item["id"], "retrieval_error": str(error)})
            continue
        inspected.append({"doi": item["id"], "eligible_original_docx_table": metadata is not None})
        if metadata is not None:
            metadata["stratum"] = start
            metadata["split"] = "development" if not selected else "held-out"
            selected.append(metadata)
            print(json.dumps({"selected": metadata["id"], "split": metadata["split"]}), flush=True)
        if len(selected) == 2:
            break
    if len(selected) != 2:
        raise ValueError(f"Insufficient eligible metadata in {start}: {inspected}")
    return {"stratum": start, "query": query, "inspected": inspected, "selected": selected}


def select_elife():
    raw, _ = fetch("https://api.elifesciences.org/articles?page=1&per-page=30&order=desc")
    selected = []
    for item in json.loads(raw)["items"]:
        if item.get("type") != "research-article" or item.get("status") != "vor":
            continue
        if item.get("copyright", {}).get("license") != "CC-BY-4.0" or not item.get("pdf"):
            continue
        # Detailed response is filtered to bibliographic fields; body/layout are not inspected.
        detail_raw, _ = fetch("https://api.elifesciences.org/articles/" + item["id"])
        detail = json.loads(detail_raw)
        selected.append(
            {
                "id": "elife-" + item["id"],
                "doi": item["doi"],
                "publisher": "eLife",
                "title": item["title"],
                "published": item["published"],
                "article_url": "https://elifesciences.org/articles/" + item["id"],
                "authors": [
                    author.get("name", author.get("preferredName", {}))
                    for author in detail["authors"]
                ],
                "license": "CC-BY-4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "copyright": item["copyright"],
                "metadata_sha256": hashlib.sha256(detail_raw).hexdigest(),
                "split": "development" if len(selected) % 2 == 0 else "held-out",
                "urls": {"article.pdf": item["pdf"]},
            }
        )
        if len(selected) == 4:
            return selected
    raise ValueError("Insufficient eLife research-article metadata")


def download(paper):
    files = {}
    for filename, url in paper["urls"].items():
        target = CORPUS / "papers" / paper["id"] / filename
        if target.exists():
            raw, final = target.read_bytes(), url
        else:
            raw, final = fetch(url)
            if not raw.startswith(b"%PDF-" if filename.endswith(".pdf") else b"PK"):
                raise ValueError(f"Wrong original format for {paper['id']}/{filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        files[filename] = {
            "url": url,
            "resolved_url": final.split("?", 1)[0],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    print(json.dumps({"downloaded": paper["id"], "files": len(files)}), flush=True)
    return {**paper, "files": files}


def main():
    selection_file = CORPUS / "selection.json"
    if selection_file.exists():
        selection = json.loads(selection_file.read_text("utf-8"))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            strata = list(pool.map(select_plos, STRATA))
        selection = {
            "selected_at": datetime.now(UTC).isoformat(),
            "plos_strata": strata,
            "elife": select_elife(),
            "selection_basis": (
                "First two eligible original DOCX table supplements by publication date/id "
                "from four fixed PLOS date strata; latest four eLife VOR research PDFs by "
                "publisher API order. Metadata only. PLOS first/second and alternating "
                "eLife entries define family-level split before original layout access."
            ),
        }
        save_new(selection_file, selection)
    papers = [p for s in selection["plos_strata"] for p in s["selected"]] + selection["elife"]
    assert len({p["doi"] for p in papers}) == 12
    assert sum(len(p["urls"]) for p in papers) == 20
    protocol = {
        "study": "native-layout-v2",
        "locked_at": selection["selected_at"],
        "baseline_version": "1.2.1",
        "baseline_commit": "eee7d663057cda78e1f461a0f95083204eb7cfaf",
        "selection_sha256": hashlib.sha256(selection_file.read_bytes()).hexdigest(),
        "papers": [
            {"id": p["id"], "doi": p["doi"], "split": p["split"], "files": list(p["urls"])}
            for p in papers
        ],
        "annotation": {
            "per_file_target": 16,
            "table": (
                "First twelve visible measured result number tokens after headers in the "
                "first result table, continuing subsequent result tables as necessary. "
                "Exclude IDs, dates, resource identifiers and method constants. Preserve "
                "complex layouts and multi-value cells."
            ),
            "prose": (
                "First four measured results in abstract/results or explanatory supplement "
                "prose. Use subsequent table results if absent; if no result table exists "
                "use first sixteen measured prose results. Record each fallback and any "
                "unfilled slots. Never replace a source after layout or parser inspection."
            ),
            "gold": (
                "Independently read original OOXML and PDFium geometry plus visual original"
                " renders before scoring. Keep exact original part/paragraph/character "
                "offsets or page/bounds. Developer is annotator; no independent-human "
                "claim."
            ),
            "held_out": (
                "No held-out original extraction/render/layout access until production "
                "implementation and evaluator are frozen. Lock held-out gold before first "
                "score. Preserve first score and subsequent regressions separately."
            ),
        },
        "outcomes": {
            "supported": (
                "Unique independently specified original position, accepted explicit "
                "binding, controlled-evidence pass and mismatch after +1 evidence change."
            ),
            "missed": "No unique original candidate and no location-specific conservative refusal.",
            "mislocated": (
                "Wrong original token/location or changed binding identity, including "
                "matching numbers elsewhere."
            ),
            "unknown": (
                "Explicit unsupported/ambiguous original location. Never counted as success."
            ),
        },
        "comparison": (
            "Run exact published 1.2.1, current reader and optional Docling on "
            "identical originals and locked gold. Conversion token extraction and "
            "usable identity-preserving PaperDelta bindings are distinct metrics."
        ),
        "scope": (
            "Two publishers, native text PDFs and publisher Word supplements; not OCR "
            "or all scientific publishing. Controlled synthetic evidence is not "
            "reproduction of experiments. Twenty documents and at least 200 targets are"
            " the planned scope; report any shortfall without silently shrinking the "
            "denominator."
        ),
    }
    save_new(CORPUS / "protocol-initial.json", protocol)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        downloaded = list(pool.map(download, papers))
    save_new(CORPUS / "sources.json", {"study": "native-layout-v2", "papers": downloaded})
    print(
        json.dumps(
            {
                "families": len(papers),
                "documents": 20,
                "selection": selection_file.relative_to(ROOT).as_posix(),
            }
        )
    )


if __name__ == "__main__":
    main()
