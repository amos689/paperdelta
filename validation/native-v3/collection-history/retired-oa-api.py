"""Select new licensed native families using metadata before layout inspection."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v3"
LIMIT = 32 * 1024 * 1024
LICENSE = re.compile(r"https?://creativecommons\.org/licenses/by/4\.0/?$", re.I)
EXCLUDED = re.compile(
    r"checklist|questionnaire|search strateg|quality assessment|primer|antibod|protocol", re.I
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fetch(url):
    request = Request(url, headers={"User-Agent": "PaperDelta licensed native-document study"})
    with urlopen(request, timeout=45) as response:
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("Download exceeds the 32 MiB study limit")
        return raw, response.geturl()


def save_new(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"Refusing to replace {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def plos_candidates(stratum):
    query = {
        "q": f"publication_date:[{stratum['from']}T00:00:00Z TO "
        f'{stratum["to"]}T23:59:59Z] AND doc_type:full AND article_type:"Research Article"',
        "fq": "journal_key:" + stratum["journal_key"],
        "fl": "id,title,publication_date",
        "sort": "publication_date asc,id asc",
        "rows": str(stratum["metadata_limit"]),
    }
    url = "https://api.plos.org/search?" + urlencode(query)
    raw, _ = fetch(url)
    return url, digest(raw), json.loads(raw)["response"]["docs"]


def plos_metadata(item, stratum):
    address = "https://journals.plos.org/" + stratum["route"] + "/article?id=" + item["id"]
    raw, final = fetch(address)
    tree = html.fromstring(raw)
    if not any(LICENSE.fullmatch(url) for url in tree.xpath("//a/@href")):
        return None
    metadata = {}
    for element in tree.xpath('//meta[starts-with(@name,"citation_")]'):
        metadata.setdefault(element.get("name"), []).append(element.get("content"))
    attachments = []
    for heading in tree.xpath('//h3[contains(@class,"siTitle")]'):
        caption = " ".join(heading.text_content().split())
        if "table" not in caption.lower() or EXCLUDED.search(caption):
            continue
        following, formats = heading.getnext(), []
        for _ in range(4):
            if following is None or following.tag == "h3":
                break
            formats.append(" ".join(following.text_content().split()))
            following = following.getnext()
        links = heading.xpath('.//a[contains(@href,"type=supplementary")]/@href')
        if links and any("(DOCX)" in value for value in formats):
            attachments.append((caption, urljoin(address, links[0])))
    if not attachments or not metadata.get("citation_pdf_url"):
        return None
    return {
        "id": stratum["route"] + "-" + item["id"].rsplit(".", 1)[1],
        "doi": item["id"],
        "title": item["title"],
        "published": item["publication_date"],
        "authors": metadata.get("citation_author", []),
        "article_url": final,
        "metadata_sha256": digest(raw),
        "attachment_caption": attachments[0][0],
        "urls": {
            "article.pdf": metadata["citation_pdf_url"][0],
            "supplement.docx": attachments[0][1],
        },
    }


def epmc_candidates(stratum):
    query = {
        "query": f"ISSN:{stratum['issn']} FIRST_PDATE:[{stratum['from']} TO "
        f"{stratum['to']}] OPEN_ACCESS:Y HAS_PDF:Y",
        "format": "json",
        "resultType": "lite",
        "pageSize": str(stratum["metadata_limit"]),
    }
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode(query)
    raw, _ = fetch(url)
    values = json.loads(raw)["resultList"]["result"]
    values.sort(key=lambda value: (value.get("firstPublicationDate", ""), value.get("doi", "")))
    return url, digest(raw), values


def xml(raw):
    return etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True))


def epmc_metadata(item, stratum):
    if not item.get("pmcid") or not item.get("doi"):
        return None
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/" + item["pmcid"] + "/fullTextXML"
    raw, _ = fetch(url)
    tree = xml(raw)
    if tree.get("article-type") != "research-article":
        return None
    front = tree.find("front/article-meta")
    if front is None:
        return None
    licenses = front.xpath('.//permissions/license//@*[local-name()="href"]')
    if not any(LICENSE.fullmatch(value) for value in licenses):
        return None
    links = front.xpath(
        './/self-uri[@content-type="pdf" or @content-type="pmc-pdf"]/@*[local-name()="href"]'
    )
    if not links:
        return None
    package_api = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=" + item["pmcid"]
    package_raw, _ = fetch(package_api)
    packages = xml(package_raw).xpath('//link[@format="tgz"]/@href')
    if not packages:
        return None
    package = packages[0].replace("ftp://ftp.ncbi.nlm.nih.gov/", "https://ftp.ncbi.nlm.nih.gov/")
    if not package.startswith("https://ftp.ncbi.nlm.nih.gov/pub/pmc/"):
        raise ValueError("Unexpected original package host/path")
    return {
        "id": stratum["id"].rsplit("-", 1)[0] + "-" + item["pmcid"].lower(),
        "doi": item["doi"],
        "title": item["title"],
        "published": item["firstPublicationDate"],
        "authors": [
            " ".join(name.itertext()).strip()
            for name in front.xpath('.//contrib[@contrib-type="author"]/name')
        ],
        "article_url": "https://doi.org/" + item["doi"],
        "metadata_url": url,
        "metadata_sha256": digest(raw),
        "package_lookup_url": package_api,
        "package_lookup_sha256": digest(package_raw),
        "package_url": package,
        "original_pdf_name": links[0].rsplit("/", 1)[-1],
        "urls": {"article.pdf": package},
    }


def previous_dois():
    result = set()
    for name in ("native-v1", "native-v2"):
        source = json.loads((ROOT / "validation" / name / "sources.json").read_text("utf-8"))
        result.update(paper["doi"] for paper in source["papers"])
    return result


def select(stratum, excluded, directory):
    is_plos = "journal_key" in stratum
    url, identity, candidates = (plos_candidates if is_plos else epmc_candidates)(stratum)
    inspected, chosen = [], []
    for item in candidates:
        doi = item.get("doi", item.get("id"))
        if doi in excluded:
            inspected.append({"doi": doi, "eligible": False, "reason": "previous family"})
            continue
        try:
            paper = (plos_metadata if is_plos else epmc_metadata)(item, stratum)
        except Exception as error:
            inspected.append({"doi": doi, "retrieval_error": str(error)})
            continue
        inspected.append({"doi": doi, "eligible": paper is not None})
        if paper:
            paper.update(
                publisher=stratum["publisher"],
                stratum=stratum["id"],
                split="development" if not chosen else "held-out",
                license="CC-BY-4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
            )
            chosen.append(paper)
            print(json.dumps({"selected": paper["id"], "split": paper["split"]}), flush=True)
        if len(chosen) == 2:
            break
    result = {
        "stratum": stratum["id"],
        "query_url": url,
        "response_sha256": identity,
        "inspected": inspected,
        "selected": chosen,
        "status": "selected" if len(chosen) == 2 else "insufficient_eligible_metadata",
    }
    save_new(directory / (stratum["id"] + ".json"), result)
    return result


def download(paper):
    files = {}
    for filename, url in paper["urls"].items():
        raw, final = fetch(url)
        transport = {"url": url, "resolved_url": final.split("?", 1)[0], "sha256": digest(raw)}
        if "package_url" in paper:
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                matches = [
                    item
                    for item in archive.getmembers()
                    if item.isfile() and item.name.rsplit("/", 1)[-1] == paper["original_pdf_name"]
                ]
                if len(matches) != 1 or matches[0].size > LIMIT:
                    raise ValueError("No unique bounded publisher PDF in original package")
                with archive.extractfile(matches[0]) as stream:
                    raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT or not raw.startswith(b"%PDF-" if filename.endswith("pdf") else b"PK"):
            raise ValueError("Unexpected original document format/size")
        target = CORPUS / "papers" / paper["id"] / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError("Refusing to replace an original")
        target.write_bytes(raw)
        files[filename] = {"sha256": digest(raw), "bytes": len(raw), "transport": transport}
    return {**paper, "files": files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--selection-round", choices=["initial", "issn-correction"], default="initial"
    )
    args = parser.parse_args()
    suffix = "" if args.selection_round == "initial" else "-" + args.selection_round
    directory = CORPUS / ("selection" + suffix)
    if suffix:
        assert (CORPUS / ("amendment" + suffix + ".json")).is_file()
    protocol = CORPUS / "protocol-plan.json"
    plan = json.loads(protocol.read_text("utf-8"))
    for name, identity in plan["initial_parser_sha256"].items():
        assert digest((ROOT / "src/paperdelta" / name).read_bytes()) == identity
    selections = []
    excluded = previous_dois()
    for stratum in plan["strata"]:
        saved = directory / (stratum["id"] + ".json")
        result = (
            json.loads(saved.read_text("utf-8"))
            if saved.exists()
            else select(stratum, excluded, directory)
        )
        selections.append(result)
    papers = [paper for item in selections for paper in item["selected"]]
    lock = CORPUS / ("selection-lock" + suffix + ".json")
    if not lock.exists():
        save_new(
            lock,
            {
                "locked_at": datetime.now(UTC).isoformat(),
                "protocol_sha256": digest(protocol.read_bytes()),
                "families": [{"id": p["id"], "doi": p["doi"], "split": p["split"]} for p in papers],
                "selection_sha256": {
                    p.name: digest(p.read_bytes()) for p in sorted(directory.glob("*.json"))
                },
                "planned_families": 8,
                "selected_families": len(papers),
                "before_original_layout_access_and_parser_changes": True,
            },
        )
    assert len({p["doi"] for p in papers}) == len(papers)
    assert all(p["doi"] not in excluded for p in papers)
    if len(papers) != 8:
        raise ValueError("Selection shortage retained; amend the protocol before proceeding")
    acquired = []
    for paper in papers:
        record = CORPUS / "acquisition" / (paper["id"] + ".json")
        if record.exists():
            acquired.append(json.loads(record.read_text("utf-8")))
            continue
        try:
            result = download(paper)
            result["status"] = "downloaded"
        except Exception as error:
            result = {**paper, "status": "unavailable", "retrieval_error": str(error)}
        save_new(record, result)
        acquired.append(result)
        print(json.dumps({"family": paper["id"], "status": result["status"]}), flush=True)
    save_new(CORPUS / "sources.json", {"study": plan["study"], "papers": acquired})


if __name__ == "__main__":
    main()
