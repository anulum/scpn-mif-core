# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — strict JSON object decoding tests.
"""Ambiguous or malformed documents are refused with ValueError only."""

from __future__ import annotations

import pytest

from scpn_mif_core._strict_json import loads_strict_object


def test_decodes_a_plain_object() -> None:
    """A plain object decodes unchanged."""
    assert loads_strict_object('{"a": 1, "b": {"c": [1.5, "x"]}}', what="doc") == {"a": 1, "b": {"c": [1.5, "x"]}}


@pytest.mark.parametrize(
    "text",
    ['{"a": 1, "a": 2}', '{"outer": {"a": 1, "a": 1}}', '[{"a": 1, "a": 2}]'],
)
def test_refuses_repeated_member_names_at_any_depth(text: str) -> None:
    """A repeated member at any depth is refused."""
    with pytest.raises(ValueError, match="duplicate JSON member: 'a'"):
        loads_strict_object(text, what="doc")


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_refuses_non_standard_literals(literal: str) -> None:
    """NaN and infinity literals are refused."""
    with pytest.raises(ValueError, match=f"non-standard JSON literal {literal} "):
        loads_strict_object(f'{{"a": {literal}}}', what="doc")


@pytest.mark.parametrize("text", ["[]", "1", '"x"', "null"])
def test_refuses_a_non_object_document(text: str) -> None:
    """A document that is not an object is refused."""
    with pytest.raises(ValueError, match=r"^doc JSON must be an object$"):
        loads_strict_object(text, what="doc")


def test_reports_invalid_json_with_the_document_name() -> None:
    """Invalid JSON is reported with the document's name."""
    with pytest.raises(ValueError, match=r"^scenario JSON is invalid: "):
        loads_strict_object("{ not json", what="scenario")


def test_reports_excessive_nesting_as_an_input_error() -> None:
    """Too deep nesting is reported as an input error."""
    with pytest.raises(ValueError, match=r"^doc JSON nests too deeply$"):
        loads_strict_object("[" * 200_000 + "]" * 200_000, what="doc")
