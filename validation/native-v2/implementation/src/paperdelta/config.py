"""Safe YAML loading; no duplicate keys, executable tags or implicit dates."""

from __future__ import annotations

import copy
import re
from decimal import Decimal

import yaml

from paperdelta.errors import PaperDeltaError, error_message
from paperdelta.i18n import msg
from paperdelta.models import Config
from paperdelta.storage import Project, decimal_value, sha256


class ConfigLoader(yaml.SafeLoader):
    yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)


for initial, rules in list(ConfigLoader.yaml_implicit_resolvers.items()):
    ConfigLoader.yaml_implicit_resolvers[initial] = [
        rule
        for rule in rules
        if rule[0] not in ("tag:yaml.org,2002:timestamp", "tag:yaml.org,2002:bool")
    ]
ConfigLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.IGNORECASE), list("tTfF")
)


def _mapping(loader: ConfigLoader, node: yaml.MappingNode) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, (str, int)) or isinstance(key, bool):
            raise PaperDeltaError("CONFIG_KEY", msg("error.CONFIG_KEY"))
        if key in result:
            raise PaperDeltaError("DUPLICATE_KEY", msg("error.DUPLICATE_KEY", key=key))
        result[key] = loader.construct_object(value_node, deep=True)
    return result


ConfigLoader.add_constructor("tag:yaml.org,2002:map", _mapping)
ConfigLoader.add_constructor(
    "tag:yaml.org,2002:float", lambda loader, node: decimal_value(loader.construct_scalar(node))
)


class ConfigDumper(yaml.SafeDumper):
    pass


ConfigDumper.add_representer(
    Decimal, lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:float", str(value))
)


def config_text(config: Config) -> str:
    value = config.model_dump(exclude_none=True)
    if config.schema_version == 1:
        value.pop("review_scope", None)
        value.pop("coverage_exclusions", None)
    return yaml.dump(
        value,
        Dumper=ConfigDumper,
        allow_unicode=True,
        sort_keys=False,
    )


def load_config(project: Project, path: str = "paperdelta.yaml") -> tuple[Config, str]:
    text, raw = project.text(path, limit=1024 * 1024)
    try:
        data = yaml.load(text, Loader=ConfigLoader)
        return Config.model_validate(data), sha256(raw)
    except (yaml.YAMLError, ValueError, RecursionError) as exc:
        raise PaperDeltaError("INVALID_CONFIG", error_message(exc)) from exc
