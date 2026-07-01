#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — polyglot benchmark dashboard.
"""Aggregate the reviewed per-kernel benchmark results into one dashboard artefact.

The dashboard consolidates every promoted per-kernel comparison result under
``bench/results/*.json`` into a single citation-ready JSON document. It never
re-runs a benchmark and never authors a figure: every number is copied from a
committed, reviewed per-kernel result file, and every provenance field (host,
governor, isolation method, host load, command, and toolchain versions) travels
with the kernel it belongs to.

Two kinds of result files live under ``bench/results/``. Cross-backend
comparison results carry a ``tests`` list and a ``benchmark_context`` block;
those are the polyglot performance comparisons the dashboard aggregates.
Everything else (the decomposed sensor-to-trigger latency budget and the Belova
merge-window physics parity anchor) is not a performance comparison and is
recorded under ``excluded_artifacts`` with its own schema string as the reason.

Only ``rust`` and ``python`` are in-process dispatch backends, so the fastest
backend per group and the relative-speedup ratios are computed over those two
alone. The ``julia`` and ``go`` command-line paths and the ``systemverilog``
cosimulation fixture are process-startup or subprocess dominated; their rows are
kept for parity provenance and flagged ``runtime_comparable = false`` rather than
being promoted as runtime performance claims. This mirrors the honesty framing in
``bench/README.md`` and ADR 0007.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "bench" / "results"
DISPATCH_PATH = REPO_ROOT / "bench" / "dispatch.toml"
DASHBOARD_PATH = REPO_ROOT / "docs" / "_generated" / "benchmark_dashboard.json"
SCHEMA = "scpn-mif-core/benchmark-dashboard/1.0.0"

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

#: Documented role of each measured backend. ``rust`` and ``python`` are the
#: in-process dispatch backends; the rest are parity or cosimulation surfaces
#: whose timings are dominated by process/subprocess launch rather than the
#: kernel itself.
BACKEND_ROLE: Mapping[str, str] = {
    "rust": "runtime",
    "python": "runtime_reference",
    "julia": "parity_cli",
    "go": "parity_cli",
    "systemverilog": "cosimulation_fixture",
}
UNKNOWN_ROLE = "unclassified"
#: Backends whose numbers are genuine in-process runtime measurements and may
#: therefore be ranked against each other.
RUNTIME_COMPARABLE: frozenset[str] = frozenset({"rust", "python"})

#: Provenance fields lifted from a result's ``benchmark_context`` when present.
#: ``command`` and ``runtime_versions`` are required; the rest are optional and
#: emitted only when the source recorded them.
OPTIONAL_CONTEXT_FIELDS: tuple[str, ...] = (
    "cpu_isolated",
    "isolation_method",
    "affinity_or_reserved_cores",
    "cpu_governor",
    "host_load_before",
    "host_load_after",
    "hardware_summary",
)

INTEGRITY_STATEMENT = (
    "Every figure is copied from a committed, reviewed per-kernel result under "
    "bench/results/; no number is authored in prose. Local raw benchmark output "
    "stays under the gitignored bench/results/local/ scratch directory."
)
ISOLATION_DISCLAIMER = (
    "All comparison runs are non-isolated (taskset affinity on a shared "
    "workstation, no kernel isolcpus reservation). Absolute timings are noisy; "
    "only the fastest-first ranking, which holds across orders of magnitude, is "
    "promoted. Julia and Go command-line paths and the SystemVerilog "
    "cosimulation fixture are process-startup or subprocess dominated and are "
    "not runtime performance claims."
)


@dataclass(frozen=True)
class BackendRow:
    """One backend's measured timing within a benchmark group."""

    backend: str
    role: str
    runtime_comparable: bool
    mean_ns: float
    median_ns: float | None
    stddev_ns: float | None
    ops_per_s: float | None
    rounds: int | None
    relative_to_fastest: float | None

    def to_json(self) -> dict[str, JsonValue]:
        """Return this row as stable JSON data, omitting absent optional fields."""
        payload: dict[str, JsonValue] = {
            "backend": self.backend,
            "role": self.role,
            "runtime_comparable": self.runtime_comparable,
            "mean_ns": self.mean_ns,
        }
        if self.median_ns is not None:
            payload["median_ns"] = self.median_ns
        if self.stddev_ns is not None:
            payload["stddev_ns"] = self.stddev_ns
        if self.ops_per_s is not None:
            payload["ops_per_s"] = self.ops_per_s
        if self.rounds is not None:
            payload["rounds"] = self.rounds
        if self.relative_to_fastest is not None:
            payload["relative_to_fastest"] = self.relative_to_fastest
        return payload


@dataclass(frozen=True)
class BenchmarkGroup:
    """A single benchmark group with its ranked backend rows."""

    group: str
    fastest_backend: str | None
    fastest_mean_ns: float | None
    backends: tuple[BackendRow, ...]

    def to_json(self) -> dict[str, JsonValue]:
        """Return this group as stable JSON data."""
        return {
            "group": self.group,
            "fastest_backend": self.fastest_backend,
            "fastest_mean_ns": self.fastest_mean_ns,
            "backends": [row.to_json() for row in self.backends],
        }


@dataclass(frozen=True)
class KernelEntry:
    """One aggregated kernel with its provenance and ranked groups."""

    kernel: str
    source: str
    dispatch_key: str | None
    datetime: str | None
    notes: tuple[str, ...]
    provenance: Mapping[str, JsonValue]
    groups: tuple[BenchmarkGroup, ...]
    backends: tuple[str, ...] = field(default=())
    runtime_versions: Mapping[str, JsonValue] = field(default_factory=dict)

    def to_json(self) -> dict[str, JsonValue]:
        """Return this kernel as stable JSON data."""
        return {
            "kernel": self.kernel,
            "source": self.source,
            "dispatch_key": self.dispatch_key,
            "datetime": self.datetime,
            "backends": list(self.backends),
            "provenance": dict(self.provenance),
            "notes": list(self.notes),
            "groups": [group.to_json() for group in self.groups],
        }


def _json_str_list(values: Iterable[str]) -> list[JsonValue]:
    """Return the strings widened to a JSON value list, preserving order."""
    return list(values)


def _load_json(path: Path) -> JsonValue:
    return cast(JsonValue, json.loads(path.read_text(encoding="utf-8")))


def _display_path(path: Path) -> str:
    if path.is_relative_to(REPO_ROOT):
        return str(path.relative_to(REPO_ROOT))
    return str(path)


def _object_mapping(value: object, path: Path) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(Mapping[str, object], value)


def _float_field(mapping: Mapping[str, object], name: str, path: Path) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{path} field {name!r} must be numeric")
    return float(value)


def _optional_float(mapping: Mapping[str, object], name: str) -> float | None:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _optional_int(mapping: Mapping[str, object], name: str) -> int | None:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def is_comparison_result(document: object) -> bool:
    """Return whether a result document is a cross-backend comparison benchmark."""
    if not isinstance(document, dict):
        return False
    tests = document.get("tests")
    context = document.get("benchmark_context")
    return isinstance(tests, list) and bool(tests) and isinstance(context, dict)


def backend_of(test_name: str) -> str:
    """Return the backend token encoded in a ``test_bench_<backend>_...`` name."""
    segment = test_name.split("test_bench_", 1)[-1]
    for candidate in BACKEND_ROLE:
        if segment == candidate or segment.startswith(f"{candidate}_"):
            return candidate
    return segment.split("_", 1)[0]


def role_of(backend: str) -> str:
    """Return the documented role label for a backend token."""
    return BACKEND_ROLE.get(backend, UNKNOWN_ROLE)


def _dispatch_keys() -> tuple[str, ...]:
    if not DISPATCH_PATH.is_file():
        return ()
    keys: list[str] = []
    in_kernels = False
    for raw in DISPATCH_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_kernels = line == "[kernels]"
            continue
        if in_kernels and line.startswith('"') and "=" in line:
            keys.append(line.split("=", 1)[0].strip().strip('"'))
    return tuple(keys)


def dispatch_key_for(kernel: str, keys: Sequence[str]) -> str | None:
    """Return the dispatch-table key for a kernel, or ``None`` when none matches."""
    for key in keys:
        if key.replace(".", "_") == kernel or key.rsplit(".", 1)[-1] == kernel:
            return key
    return None


def _build_group(name: str, tests: Sequence[Mapping[str, object]], path: Path) -> BenchmarkGroup:
    parsed: list[tuple[str, float, Mapping[str, object]]] = []
    for test in tests:
        backend = backend_of(_str(test, "name", path))
        parsed.append((backend, _float_field(test, "mean_ns", path), test))

    runtime_rows = [(backend, mean) for backend, mean, _ in parsed if backend in RUNTIME_COMPARABLE]
    ranking = runtime_rows or [(backend, mean) for backend, mean, _ in parsed]
    fastest_backend, fastest_mean = min(ranking, key=lambda item: item[1])

    rows = tuple(
        BackendRow(
            backend=backend,
            role=role_of(backend),
            runtime_comparable=backend in RUNTIME_COMPARABLE,
            mean_ns=mean,
            median_ns=_optional_float(test, "median_ns"),
            stddev_ns=_optional_float(test, "stddev_ns"),
            ops_per_s=_optional_float(test, "ops_per_s"),
            rounds=_optional_int(test, "rounds"),
            relative_to_fastest=round(mean / fastest_mean, 6) if fastest_mean > 0 else None,
        )
        for backend, mean, test in parsed
    )
    ordered = tuple(sorted(rows, key=lambda row: row.mean_ns))
    return BenchmarkGroup(
        group=name,
        fastest_backend=fastest_backend,
        fastest_mean_ns=fastest_mean,
        backends=ordered,
    )


def _str(mapping: Mapping[str, object], name: str, path: Path) -> str:
    value = mapping.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{path} field {name!r} must be a string")
    return value


def _provenance(
    document: Mapping[str, object],
    context: Mapping[str, object],
    runtime_versions: Mapping[str, JsonValue],
    path: Path,
) -> dict[str, JsonValue]:
    host = document.get("host")
    python_version = document.get("python_version")
    provenance: dict[str, JsonValue] = {
        "host": host if isinstance(host, str) else None,
        "python_version": python_version if isinstance(python_version, str) else None,
        "command": _str(context, "command", path),
        "runtime_versions": dict(runtime_versions),
    }
    for name in OPTIONAL_CONTEXT_FIELDS:
        if name in context:
            provenance[name] = cast(JsonScalar, context[name])
    return provenance


def _runtime_versions(context: Mapping[str, object], path: Path) -> dict[str, JsonValue]:
    versions = context.get("runtime_versions")
    if not isinstance(versions, dict):
        raise ValueError(f"{path} benchmark_context.runtime_versions must be a JSON object")
    return {str(tool): cast(JsonScalar, value) for tool, value in versions.items()}


def _kernel_entry(path: Path, document: Mapping[str, object], keys: Sequence[str]) -> KernelEntry:
    kernel = _str(document, "kernel", path)
    context = cast(Mapping[str, object], document["benchmark_context"])
    tests = cast(Sequence[Mapping[str, object]], document["tests"])

    grouped: dict[str, list[Mapping[str, object]]] = {}
    backends: list[str] = []
    for test in tests:
        entry = _object_mapping(test, path)
        grouped.setdefault(_str(entry, "group", path), []).append(entry)
        backend = backend_of(_str(entry, "name", path))
        if backend not in backends:
            backends.append(backend)

    groups = tuple(_build_group(name, grouped[name], path) for name in sorted(grouped))
    notes_value = document.get("notes", [])
    notes = tuple(str(note) for note in notes_value if isinstance(note, str)) if isinstance(notes_value, list) else ()
    datetime_value = document.get("datetime")
    runtime_versions = _runtime_versions(context, path)
    return KernelEntry(
        kernel=kernel,
        source=_display_path(path),
        dispatch_key=dispatch_key_for(kernel, keys),
        datetime=datetime_value if isinstance(datetime_value, str) else None,
        notes=notes,
        provenance=_provenance(document, context, runtime_versions, path),
        groups=groups,
        backends=tuple(sorted(backends)),
        runtime_versions=runtime_versions,
    )


def _environments(kernels: Sequence[KernelEntry]) -> dict[str, JsonValue]:
    hosts: set[str] = set()
    governors: set[str] = set()
    pythons: set[str] = set()
    toolchains: dict[str, set[str]] = {}
    for kernel in kernels:
        provenance = kernel.provenance
        host = provenance.get("host")
        if isinstance(host, str):
            hosts.add(host)
        governor = provenance.get("cpu_governor")
        if isinstance(governor, str):
            governors.add(governor)
        python = provenance.get("python_version")
        if isinstance(python, str):
            pythons.add(python)
        for tool, value in kernel.runtime_versions.items():
            if tool != "python" and isinstance(value, str):
                toolchains.setdefault(tool, set()).add(value)
    return {
        "distinct_hosts": _json_str_list(sorted(hosts)),
        "distinct_cpu_governors": _json_str_list(sorted(governors)),
        "python_versions": _json_str_list(sorted(pythons)),
        "toolchains": {tool: _json_str_list(sorted(values)) for tool, values in sorted(toolchains.items())},
    }


def _backend_coverage(kernels: Sequence[KernelEntry]) -> dict[str, JsonValue]:
    counts: dict[str, int] = {}
    for kernel in kernels:
        for backend in kernel.backends:
            counts[backend] = counts.get(backend, 0) + 1
    return {backend: counts[backend] for backend in sorted(counts)}


def build_dashboard(*, results_dir: Path | None = None) -> dict[str, JsonValue]:
    """Build the polyglot benchmark dashboard from committed per-kernel results."""
    directory = RESULTS_DIR if results_dir is None else results_dir
    keys = _dispatch_keys()

    kernels: list[KernelEntry] = []
    excluded: list[dict[str, JsonValue]] = []
    for path in sorted(directory.glob("*.json")):
        document = _load_json(path)
        if is_comparison_result(document):
            kernels.append(_kernel_entry(path, cast(Mapping[str, object], document), keys))
            continue
        excluded.append(
            {
                "file": _display_path(path),
                "reason": _exclusion_reason(document),
            }
        )

    group_count = sum(len(kernel.groups) for kernel in kernels)
    return {
        "SPDX-License-Identifier": "AGPL-3.0-or-later",
        "schema": SCHEMA,
        "generated_from": "bench/results/*.json (reviewed, promoted per-kernel comparison results)",
        "integrity": {
            "adr": "docs/adr/0007-validation-and-benchmark-integrity.md",
            "statement": INTEGRITY_STATEMENT,
            "isolation_disclaimer": ISOLATION_DISCLAIMER,
        },
        "backend_roles": dict(BACKEND_ROLE),
        "runtime_comparable_backends": _json_str_list(sorted(RUNTIME_COMPARABLE)),
        "kernel_count": len(kernels),
        "group_count": group_count,
        "backend_coverage": _backend_coverage(kernels),
        "environments": _environments(kernels),
        "kernels": [kernel.to_json() for kernel in kernels],
        "excluded_artifacts": list(excluded),
    }


def _exclusion_reason(document: object) -> str:
    if isinstance(document, dict) and isinstance(document.get("schema"), str):
        return f"not a cross-backend performance comparison (schema: {document['schema']})"
    return "not a cross-backend performance comparison (unrecognised benchmark schema)"


def render(dashboard: Mapping[str, JsonValue]) -> str:
    """Render a dashboard as stable, pretty-printed JSON."""
    return json.dumps(dashboard, indent=2, sort_keys=False) + "\n"


def write_dashboard(*, dashboard_path: Path | None = None, results_dir: Path | None = None) -> Path:
    """Write the dashboard artefact and return its path."""
    target = DASHBOARD_PATH if dashboard_path is None else dashboard_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(build_dashboard(results_dir=results_dir)), encoding="utf-8")
    return target


def check_dashboard(*, dashboard_path: Path | None = None, results_dir: Path | None = None) -> tuple[str, ...]:
    """Return drift errors between the committed dashboard and a fresh build."""
    target = DASHBOARD_PATH if dashboard_path is None else dashboard_path
    if not target.is_file():
        return (f"missing benchmark dashboard: {target}",)
    committed = target.read_text(encoding="utf-8")
    expected = render(build_dashboard(results_dir=results_dir))
    if committed != expected:
        return (f"stale benchmark dashboard: {target} does not match a fresh build",)
    return ()


def main(argv: list[str] | None = None) -> int:
    """Generate the benchmark dashboard, or check it for drift."""
    parser = argparse.ArgumentParser(description="Generate or check the polyglot benchmark dashboard.")
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(argv)

    if args.check:
        errors = check_dashboard()
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0

    path = write_dashboard()
    display = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"Wrote {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
