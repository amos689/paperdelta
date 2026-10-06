"""SARIF diagnostics with actual text positions and links to native report locations."""

from urllib.parse import quote

from paperdelta import __version__
from paperdelta.i18n import translated
from paperdelta.locations import location_label
from paperdelta.storage import fingerprint, sha256


def report_anchor(subject):
    return "subject-" + sha256(subject.encode("utf-8")).split(":")[1][:16]


def sarif_report(report, report_path="report.html"):
    results = []
    for diagnostic in report["diagnostics"]:
        location = diagnostic.get("location")
        native = bool(location and location.get("format") in {"docx", "pdf"})
        link = quote(report_path, safe="/") + "#" + report_anchor(diagnostic["subject"])
        message = str(translated(diagnostic["message"]))
        if native:
            message += "\n" + str(translated(location_label(location))) + "\n" + link
        result = {
            "ruleId": diagnostic["rule"],
            "level": {"error": "error", "warning": "warning", "unknown": "warning"}[
                diagnostic["severity"]
            ],
            "message": {"text": message},
            "partialFingerprints": {
                "paperdeltaIdentity/v1": fingerprint(
                    {"rule": diagnostic["rule"], "subject": diagnostic["subject"]}
                )
            },
            "properties": {
                "subject": diagnostic["subject"],
                "paperdeltaSeverity": diagnostic["severity"],
                "reportLocation": link,
            },
        }
        if location:
            physical = {"artifactLocation": {"uri": quote(location["file"], safe="/")}}
            if not native:
                text = location["text"]
                physical["region"] = {
                    "startLine": location["line"],
                    "startColumn": location["column"],
                    "endLine": location["line"] + text.count("\n"),
                    "endColumn": len(text.rsplit("\n", 1)[-1])
                    + (1 if "\n" in text else location["column"]),
                }
            else:
                result["properties"]["nativeLocation"] = location
            result["locations"] = [{"physicalLocation": physical}]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "PaperDelta",
                        "semanticVersion": __version__,
                        "informationUri": "https://github.com/amos689/paperdelta",
                        "rules": [{"id": rule} for rule in sorted({d["ruleId"] for d in results})],
                    }
                },
                "columnKind": "unicodeCodePoints",
                "results": results,
                "properties": {
                    "configPath": report["config_path"],
                    "inputHashes": report["input_hashes"],
                    "exitCode": report["exit_code"],
                },
            }
        ],
    }
