"""Explicit Notebook inspection and reviewed producer declarations."""

import argparse

from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr, translated
from paperdelta.notebooks import inspect_notebook
from paperdelta.provenance import (
    ProducerRequest,
    _safe_path,
    accept_producer,
    producer_record,
    propose_producer,
)
from paperdelta.records import validate_record
from paperdelta.storage import json_text, parse_json


def register_commands(commands):
    root = commands.add_parser("provenance", help=tr("provenance.help"))
    sub = root.add_subparsers(dest="provenance_command", required=True)
    notebook = sub.add_parser("notebook", help=tr("provenance.notebook_help"))
    notebook.add_argument("path", help=tr("provenance.source_help"))
    for action in ("preview", "run"):
        parser = sub.add_parser(action, help=tr("provenance." + action + "_help"))
        parser.add_argument("name", help=tr("provenance.name_help"))
        parser.add_argument(
            "--kind", choices=["notebook", "quarto"], required=True, help=tr("provenance.kind_help")
        )
        parser.add_argument("--source", required=True, help=tr("provenance.source_help"))
        parser.add_argument(
            "--input", action="append", default=[], help=tr("provenance.input_help")
        )
        parser.add_argument(
            "--output", action="append", required=True, help=tr("provenance.output_help")
        )
        parser.add_argument("--cell", action="append", default=[], help=tr("provenance.cell_help"))
        parser.add_argument("--rationale", required=True, help=tr("provenance.rationale"))
        parser.add_argument("--replace", action="store_true", help=tr("provenance.replace_help"))
        parser.add_argument("--out", required=True, help=tr("provenance.preview_out"))
        if action == "run":
            parser.add_argument(
                "--timeout", type=int, default=600, help=tr("provenance.timeout_help")
            )
            parser.add_argument(
                "--command",
                dest="command_args",
                required=True,
                nargs=argparse.REMAINDER,
                help=tr("provenance.command_help"),
            )
    accept = sub.add_parser("accept", help=tr("provenance.accept_help"))
    accept.add_argument("proposal", help=tr("provenance.proposal_help"))


def run_command(project, args):
    if args.provenance_command == "notebook":
        result = inspect_notebook(project, args.path)
    elif args.provenance_command == "accept":
        value = parse_json(project.read(args.proposal, 4 * 1024 * 1024).decode("utf-8"))
        result = accept_producer(project, value)
    else:
        output = _safe_path(project, args.out)
        dependencies = [args.source, *args.input, *args.output, args.config]
        if output in [_safe_path(project, path) for path in dependencies]:
            raise PaperDeltaError(
                "PROVENANCE_CONFIG_DEPENDENCY", msg("provenance.config_dependency")
            )
        if project.path(args.out).exists():
            raise PaperDeltaError(
                "ALREADY_EXISTS", msg("error.ALREADY_EXISTS.2", relative=args.out)
            )
        config, _ = load_config(project, args.config)
        if args.name in config.provenance and not args.replace:
            raise PaperDeltaError("PROVENANCE_EXISTS", msg("provenance.exists"))
        spec = {
            "kind": args.kind,
            "source": args.source,
            "inputs": args.input,
            "outputs": args.output,
            "cells": args.cell,
        }
        validate_record(
            ProducerRequest,
            {"name": args.name, "spec": spec, "rationale": args.rationale, "replace": args.replace},
            "PROVENANCE_SPEC",
        )
        if _safe_path(project, args.config) in [
            _safe_path(project, name) for name in [args.source, *args.input, *args.output]
        ]:
            raise PaperDeltaError(
                "PROVENANCE_CONFIG_DEPENDENCY", msg("provenance.config_dependency")
            )
        logs = None
        if args.provenance_command == "run":
            from paperdelta.producer_run import observe_producer_command

            command = args.command_args
            if command[:1] == ["--"]:
                command = command[1:]
            observed = observe_producer_command(
                project, spec, command, args.rationale, timeout=args.timeout
            )
            record, logs = observed["record"], observed["logs"]
        else:
            record = producer_record(project, spec, args.rationale)
        proposal = propose_producer(
            project, args.name, record, replace=args.replace, config_path=args.config
        )
        project.write(args.out, json_text(proposal).encode("utf-8"), exclusive=True)
        result = {
            "status": "preview",
            "path": args.out,
            "proposal": proposal,
            "logs": logs,
            "accepted": False,
        }
    print(json_text(translated(result)), end="")
    return 0
