# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — strict JSON object decoding for file inputs.
"""Decode one JSON object without accepting ambiguous documents.

The standard decoder keeps the last of two members with the same name and
accepts the non-standard ``NaN``, ``Infinity`` and ``-Infinity`` literals.
Either lets a document mean something other than what a reader sees, so
the file loaders refuse both, refuse a top-level value that is not an
object, and report nesting too deep to decode as an input error instead of
a crash. Every refusal is a :class:`ValueError`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


def _unique_members(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key!r}")
        result[key] = value
    return result


def _refuse_constant(name: str) -> Any:
    raise ValueError(f"non-standard JSON literal {name} is not accepted")


def loads_strict_object(text: str, *, what: str) -> dict[str, Any]:
    """Decode ``text`` as one JSON object under the strict rules.

    Parameters
    ----------
    text
        Document text.
    what
        Name of the document in error messages, such as ``"scenario"``.

    Returns
    -------
    dict[str, Any]
        The decoded top-level object.

    Raises
    ------
    ValueError
        If the text is not valid JSON, repeats a member name in any object,
        uses ``NaN`` or an infinity literal, nests deeper than the decoder
        can follow, or is not an object at the top level.
    """
    try:
        value = json.loads(text, object_pairs_hook=_unique_members, parse_constant=_refuse_constant)
    except RecursionError as error:
        raise ValueError(f"{what} JSON nests too deeply") from error
    except ValueError as error:
        raise ValueError(f"{what} JSON is invalid: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{what} JSON must be an object")
    return value


__all__ = ["loads_strict_object"]
