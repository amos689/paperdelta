"""Localized argparse output without modifying argparse's process-global gettext."""

import argparse
import re
import sys
from contextvars import ContextVar

from paperdelta.i18n import msg, tr
from paperdelta.storage import json_text

json_errors: ContextVar[bool] = ContextVar("paperdelta_argument_json_errors", default=False)

_PATTERNS = [
    (r"argument (?P<argument>.+?): (?P<message>.*)", "argparse.argument"),
    (r"the following arguments are required: (?P<arguments>.*)", "argparse.required"),
    (r"unrecognized arguments: (?P<arguments>.*)", "argparse.unrecognized"),
    (r"invalid choice: (?P<value>.*) \(choose from (?P<choices>.*)\)", "argparse.choice"),
    (r"invalid (?P<type>.*?) value: (?P<value>.*)", "argparse.value"),
    (r"expected one argument", "argparse.one"),
    (r"expected at least one argument", "argparse.at_least_one"),
    (r"expected at most one argument", "argparse.at_most_one"),
    (r"expected (?P<count>\d+) arguments?", "argparse.count"),
    (r"not allowed with argument (?P<argument>.*)", "argparse.conflict"),
    (r"one of the arguments (?P<arguments>.*) is required", "argparse.one_required"),
    (r"ignored explicit argument (?P<argument>.*)", "argparse.ignored"),
    (r"ambiguous option: (?P<option>.*?) could match (?P<matches>.*)", "argparse.ambiguous"),
    (r"unknown parser (?P<parser>.*?) \(choices: (?P<choices>.*)\)", "argparse.parser"),
]


def argument_message(text):
    for pattern, key in _PATTERNS:
        match = re.fullmatch(pattern, text, re.DOTALL)
        if match:
            parameters = match.groupdict()
            if "message" in parameters:
                parameters["message"] = argument_message(parameters["message"])
            return msg(key, **parameters)
    return msg("argparse.other", message=text)


class HelpFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        # argparse uses an explicitly empty prefix when deriving a subcommand's prog.
        return super().add_usage(
            usage, actions, groups, tr("argparse.usage") if prefix is None else prefix
        )


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", HelpFormatter)
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = tr("argparse.positionals")
        self._optionals.title = tr("argparse.options")
        for action in self._actions:
            if isinstance(action, argparse._HelpAction):
                action.help = tr("argparse.help")

    def error(self, message):
        explanation = argument_message(message).render()
        if json_errors.get():
            print(
                json_text(
                    {"error": "ARGUMENTS", "message": message, "display_message": explanation}
                ),
                end="",
            )
        else:
            self.print_usage(sys.stderr)
            self._print_message(
                tr("argparse.error", prog=self.prog, message=explanation), sys.stderr
            )
        self.exit(2)
