"""PC-4: YAML template files must have no duplicate keys.

Source: YAML 1.2 Specification — Section 3.2.1.3 "Mapping Key Uniqueness".
"""
from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


class DuplicateKeyChecker(yaml.SafeLoader):
    pass


def _no_duplicate_keys(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.YAMLError(
                f"Duplicate key '{key}' at line {key_node.start_mark.line + 1}"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


if HAS_YAML:
    DuplicateKeyChecker.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
    )


def get_yaml_files():
    files = list(TEMPLATES_DIR.glob("**/*.yml")) + list(TEMPLATES_DIR.glob("**/*.yaml"))
    return sorted(files)


@pytest.mark.skipif(not HAS_YAML, reason="PyYAML not installed")
class TestYamlTemplates:

    @pytest.mark.parametrize("yaml_file", get_yaml_files(), ids=lambda f: f.name)
    def test_no_duplicate_keys(self, yaml_file):
        """YAML template must not contain duplicate mapping keys."""
        content = yaml_file.read_text(encoding="utf-8")
        try:
            yaml.load(content, Loader=DuplicateKeyChecker)
        except yaml.YAMLError as e:
            pytest.fail(f"{yaml_file.name}: {e}")
