# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — dynamic sibling compatibility matrix.
"""Dynamic compatibility report for MIF-owned cross-repository contracts."""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404  # controlled fixed-arg sibling inspection, never shell
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUS_READY = "ready"
STATUS_READY_WITH_BLOCKERS = "ready_with_external_blockers"
STATUS_READY_WITH_HARDWARE_GATE = "ready_with_hardware_gate"
STATUS_BLOCKED_RUNTIME = "blocked_runtime_dependency"
STATUS_BLOCKED_SURFACE = "blocked_surface"
STATUS_DEFERRED = "deferred_not_required_for_current_gate"
STATUS_MISSING_REPO = "missing_repo"


@dataclass(frozen=True)
class SurfaceSpec:
    """One source or import surface MIF expects from a sibling repository."""

    name: str
    detail: str
    module: str | None = None
    symbols: tuple[str, ...] = ()
    file_path: str | None = None
    tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class SiblingSpec:
    """A sibling repository contract consumed by MIF."""

    key: str
    package: str
    module: str
    repo_dir: str
    role: str
    lane: str
    current_gate: bool
    surfaces: tuple[SurfaceSpec, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SurfaceReport:
    """Availability report for one sibling surface."""

    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable representation."""
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class SiblingReport:
    """Dynamic compatibility row for one sibling repository."""

    key: str
    package: str
    module: str
    repo_path: str
    role: str
    lane: str
    current_gate: bool
    source_version: str | None
    import_version: str | None
    import_status: str
    import_detail: str
    status: str
    surfaces: tuple[SurfaceReport, ...]
    notes: tuple[str, ...]

    @property
    def failed_surfaces(self) -> tuple[SurfaceReport, ...]:
        """Return required surfaces that were not found."""
        return tuple(surface for surface in self.surfaces if surface.status != STATUS_READY)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "key": self.key,
            "package": self.package,
            "module": self.module,
            "repo_path": self.repo_path,
            "role": self.role,
            "lane": self.lane,
            "current_gate": self.current_gate,
            "source_version": self.source_version,
            "import_version": self.import_version,
            "import_status": self.import_status,
            "import_detail": self.import_detail,
            "status": self.status,
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class EcosystemReport:
    """Aggregate dynamic compatibility report for MIF ecosystem consumers."""

    generated_at_utc: str
    code_root: str
    siblings: tuple[SiblingReport, ...]

    def by_key(self) -> dict[str, SiblingReport]:
        """Return sibling rows keyed by repository identifier."""
        return {row.key: row for row in self.siblings}

    def require(self, key: str) -> SiblingReport:
        """Return a sibling row and raise when the report does not contain it."""
        try:
            return self.by_key()[key]
        except KeyError as exc:
            raise KeyError(f"dynamic compatibility report has no row for {key!r}") from exc

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "generated_at_utc": self.generated_at_utc,
            "code_root": self.code_root,
            "siblings": [row.to_dict() for row in self.siblings],
        }


SIBLINGS: tuple[SiblingSpec, ...] = (
    SiblingSpec(
        key="sc-neurocore-engine",
        package="sc-neurocore-engine",
        module="sc_neurocore",
        repo_dir="SC-NEUROCORE",
        role="SNN to SystemVerilog, Q8.8 ingress, AER HDL, UltraScale+ target contract",
        lane="NEU-C.5 / MIF-007 hardware ingress",
        current_gate=True,
        surfaces=(
            SurfaceSpec(
                name="ADC-to-spike quantiser documentation",
                detail="NEU-C.5 B-dot ADC to Q8.8 spike-rate contract",
                file_path="docs/hardware/adc_to_spike_quantiser.md",
                tokens=("ADC-to-spike", "Q8.8", "AER"),
            ),
            SurfaceSpec(
                name="UltraScale+ target contract",
                detail="Zynq UltraScale+ SystemVerilog target and timing gate",
                file_path="docs/hardware/ultrascale_plus.md",
                tokens=("UltraScale+", "SystemVerilog", "Vivado"),
            ),
        ),
        notes=("Vivado timing remains a hardware/tooling gate, not a MIF solver blocker.",),
    ),
    SiblingSpec(
        key="scpn-phase-orchestrator",
        package="scpn-phase-orchestrator",
        module="scpn_phase_orchestrator",
        repo_dir="SCPN-PHASE-ORCHESTRATOR",
        role="Kuramoto, Doppler, moving-frame UPDE, merge-window monitor",
        lane="PHA-C / MIF-001..MIF-003",
        current_gate=True,
        surfaces=(
            SurfaceSpec(
                name="Spatial coupling modulator",
                detail="Distance-aware coupling for MIF phase carriers",
                file_path="src/scpn_phase_orchestrator/coupling/spatial_modulator.py",
                tokens=("SpatialCouplingModulator",),
            ),
            SurfaceSpec(
                name="Moving-frame UPDE engine",
                detail="Doppler and moving-frame phase carrier",
                file_path="src/scpn_phase_orchestrator/upde/moving_frame.py",
                tokens=("DopplerEngine", "MovingFrameUPDEEngine"),
            ),
            SurfaceSpec(
                name="Merge-window monitor",
                detail="Axial merge tolerance monitor consumed by MIF lifecycle gates",
                file_path="src/scpn_phase_orchestrator/monitor/merge_window.py",
                tokens=("MergeWindowMonitor", "MergeWindowToleranceProfile"),
            ),
        ),
        notes=("Import may require PHASE runtime extras; source contract is still audited.",),
    ),
    SiblingSpec(
        key="scpn-control",
        package="scpn-control",
        module="scpn_control",
        repo_dir="SCPN-CONTROL",
        role="Pulsed-shot lifecycle, Petri-net runtime, capacitor bank, replay",
        lane="CON-C / MIF-004, MIF-005, MIF-012, MIF-018",
        current_gate=True,
        surfaces=(
            SurfaceSpec(
                name="Capacitor-bank compatibility module",
                detail="Public facade required by MIF capacitor-bank lifecycle bridge",
                module="scpn_control.control.capacitor_bank",
                symbols=(
                    "CapacitorBank",
                    "CapacitorBankSpec",
                    "CapacitorBankState",
                    "EnergyReport",
                    "PulseSpec",
                    "RLCRegime",
                    "free_response",
                ),
            ),
        ),
        notes=("SCPN-CONTROL claims the pulsed-control lane completed at its current source version.",),
    ),
    SiblingSpec(
        key="scpn-fusion-core",
        package="scpn-fusion-core",
        module="scpn_fusion",
        repo_dir="SCPN-FUSION-CORE",
        role="Canonical FRC physics solver laboratory consumed by MIF",
        lane="FUS-C / B-lane FRC solver ownership",
        current_gate=True,
        surfaces=(
            SurfaceSpec(
                name="FUSION FRC public contract",
                detail="FUS-C.1..FUS-C.7 symbols and explicit external-evidence blockers",
            ),
        ),
        notes=("FUSION owns the solver lane; MIF consumes accepted public surfaces.",),
    ),
    SiblingSpec(
        key="scpn-quantum-control",
        package="scpn-quantum-control",
        module="scpn_quantum_control",
        repo_dir="SCPN-QUANTUM-CONTROL",
        role="QAOA-MPC and future MIF-specific quantum-control bridge",
        lane="QUA-C deferred for current MIF gate",
        current_gate=False,
        surfaces=(
            SurfaceSpec(
                name="Generic QAOA-MPC",
                detail="Existing generic control surface",
                file_path="src/scpn_quantum_control/control/qaoa_mpc.py",
                tokens=("QAOA_MPC",),
            ),
            SurfaceSpec(
                name="MIF-specific quantum-control names",
                detail="Named MIF-lane surfaces (QRNG stream, PQC trigger signer, FRC QAOA cost, "
                "pulse-to-HLS), owned by and delivered in scpn-quantum-control",
                tokens=(
                    "QRNGStream",
                    "PqcTriggerSigner",
                    "FRCQAOAObjective",
                    "frc_pulsed_shot_cost",
                    "SubMicrosecondTracker",
                    "pulse_to_vivado_hls",
                ),
            ),
        ),
        notes=(
            "MIF-lane crypto, entropy, QAOA-cost and HLS surfaces are owned by and delivered in "
            "scpn-quantum-control; MIF consumes them as its release gate advances.",
        ),
    ),
)


def default_code_root() -> Path:
    """Return the sibling repository root used by the live compatibility scan."""
    env_root = os.environ.get("SCPN_MIF_ECOSYSTEM_ROOT") or os.environ.get("GOTM_CODE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def generate_ecosystem_report(
    code_root: Path | str | None = None,
    *,
    generated_at_utc: str | None = None,
) -> EcosystemReport:
    """Inspect sibling source trees and optional runtime imports."""
    root = Path(code_root).expanduser().resolve() if code_root is not None else default_code_root()
    siblings = tuple(_inspect_sibling(root, spec) for spec in SIBLINGS)
    return EcosystemReport(
        generated_at_utc=generated_at_utc or datetime.now(UTC).replace(microsecond=0).isoformat(),
        code_root=str(root),
        siblings=siblings,
    )


def render_compatibility_matrix(report: EcosystemReport) -> str:
    """Render the dynamic ecosystem report as Markdown."""
    year_range = "1996\u20132026"
    lines = [
        "<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->",
        "<!-- Commercial license available -->",
        f"<!-- © Concepts {year_range} Miroslav Šotek. All rights reserved. -->",
        f"<!-- © Code {year_range} Miroslav Šotek. All rights reserved. -->",
        "<!-- ORCID: 0009-0009-3560-0851 -->",
        "<!-- Contact: www.anulum.li | protoscience@anulum.li -->",
        "<!-- SCPN-MIF-CORE — generated dynamic compatibility matrix. -->",
        "",
        "# Dynamic Ecosystem Compatibility Matrix",
        "",
        "This file is generated from the live sibling repository check. It records",
        "source versions, optional runtime import status, and the contract surfaces",
        "that MIF consumes. Static equality pins are not the compatibility authority.",
        "",
        f"- Generated UTC: `{report.generated_at_utc}`",
        f"- Code root: `{report.code_root}`",
        "- Regenerate: `python tools/generate_compatibility_matrix.py`",
        "",
        "| Sibling | Source | Runtime | Status | Current gate | Lane |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in report.siblings:
        runtime = row.import_version or row.import_status
        lines.append(
            "| "
            f"`{row.package}` | "
            f"`{row.source_version or 'unknown'}` | "
            f"`{runtime}` | "
            f"`{row.status}` | "
            f"{'yes' if row.current_gate else 'deferred'} | "
            f"{row.lane} |"
        )

    lines.extend(["", "## Surface Details", ""])
    for row in report.siblings:
        lines.extend(
            [
                f"### `{row.package}`",
                "",
                f"- Role: {row.role}",
                f"- Repository: `{row.repo_path}`",
                f"- Import: `{row.import_status}` — {row.import_detail}",
                "",
                "| Surface | Status | Detail |",
                "|---|---|---|",
            ]
        )
        for surface in row.surfaces:
            lines.append(f"| {surface.name} | `{surface.status}` | {surface.detail} |")
        if row.notes:
            lines.append("")
            lines.append("Notes:")
            for note in row.notes:
                lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def compatibility_report_json(report: EcosystemReport) -> str:
    """Return deterministic JSON for generated compatibility artifacts."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def _inspect_sibling(root: Path, spec: SiblingSpec) -> SiblingReport:
    repo_path = root / spec.repo_dir
    if not repo_path.exists():
        return SiblingReport(
            key=spec.key,
            package=spec.package,
            module=spec.module,
            repo_path=str(repo_path),
            role=spec.role,
            lane=spec.lane,
            current_gate=spec.current_gate,
            source_version=None,
            import_version=None,
            import_status="missing",
            import_detail="sibling repository is absent",
            status=STATUS_MISSING_REPO,
            surfaces=(),
            notes=spec.notes,
        )

    source_version = _pyproject_version(repo_path)
    import_status, import_detail, import_version = _runtime_import(repo_path, spec.module)
    surfaces = _surface_reports(repo_path, spec)
    status = _sibling_status(spec, import_status, surfaces)
    notes = _notes(spec, import_status, import_detail, import_version, source_version)
    return SiblingReport(
        key=spec.key,
        package=spec.package,
        module=spec.module,
        repo_path=str(repo_path),
        role=spec.role,
        lane=spec.lane,
        current_gate=spec.current_gate,
        source_version=source_version,
        import_version=import_version,
        import_status=import_status,
        import_detail=import_detail,
        status=status,
        surfaces=surfaces,
        notes=notes,
    )


def _pyproject_version(repo_path: Path) -> str | None:
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        return None
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project")
    if isinstance(project, Mapping):
        version = project.get("version")
        if isinstance(version, str):
            return version
    tool = data.get("tool")
    if isinstance(tool, Mapping):
        poetry = tool.get("poetry")
        if isinstance(poetry, Mapping):
            version = poetry.get("version")
            if isinstance(version, str):
                return version
    return None


def _runtime_import(repo_path: Path, module_name: str) -> tuple[str, str, str | None]:
    script = (
        "import importlib,json\n"
        f"module=importlib.import_module({module_name!r})\n"
        "print(json.dumps({'version': getattr(module, '__version__', None), "
        "'file': getattr(module, '__file__', None)}))\n"
    )
    process = _run_python(repo_path, script)
    if process.returncode != 0:
        detail = _compact_error(process.stderr) or _compact_error(process.stdout) or "import failed"
        return "error", detail, None
    try:
        payload = json.loads(process.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return "error", "runtime import did not return JSON metadata", None
    version = payload.get("version")
    file_path = payload.get("file")
    detail = f"imported from {file_path}" if isinstance(file_path, str) else "imported"
    return "ok", detail, version if isinstance(version, str) else None


def _surface_reports(repo_path: Path, spec: SiblingSpec) -> tuple[SurfaceReport, ...]:
    if spec.key == "scpn-fusion-core":
        return (_fusion_frc_surface_report(repo_path),)
    if spec.key == "scpn-quantum-control":
        return _quantum_surface_reports(repo_path, spec.surfaces)
    return tuple(_generic_surface_report(repo_path, surface) for surface in spec.surfaces)


def _generic_surface_report(repo_path: Path, surface: SurfaceSpec) -> SurfaceReport:
    if surface.module:
        return _module_symbol_report(repo_path, surface)
    if surface.file_path:
        target = repo_path / surface.file_path
        if not target.exists():
            return SurfaceReport(surface.name, STATUS_BLOCKED_SURFACE, f"missing file {surface.file_path}")
        text = target.read_text(encoding="utf-8", errors="replace")
        missing = tuple(token for token in surface.tokens if token not in text)
        if missing:
            return SurfaceReport(surface.name, STATUS_BLOCKED_SURFACE, f"missing tokens: {', '.join(missing)}")
        return SurfaceReport(surface.name, STATUS_READY, surface.detail)
    return SurfaceReport(surface.name, STATUS_READY, surface.detail)


def _module_symbol_report(repo_path: Path, surface: SurfaceSpec) -> SurfaceReport:
    script = (
        "import importlib,json\n"
        f"module=importlib.import_module({surface.module!r})\n"
        f"symbols={list(surface.symbols)!r}\n"
        "print(json.dumps({'missing': [name for name in symbols if not hasattr(module, name)]}))\n"
    )
    process = _run_python(repo_path, script)
    if process.returncode != 0:
        detail = _compact_error(process.stderr) or _compact_error(process.stdout) or "surface import failed"
        return SurfaceReport(surface.name, STATUS_BLOCKED_RUNTIME, detail)
    try:
        payload = json.loads(process.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return SurfaceReport(surface.name, STATUS_BLOCKED_RUNTIME, "surface import did not return JSON metadata")
    missing = payload.get("missing")
    if isinstance(missing, list) and missing:
        return SurfaceReport(surface.name, STATUS_BLOCKED_SURFACE, f"missing symbols: {', '.join(map(str, missing))}")
    return SurfaceReport(surface.name, STATUS_READY, surface.detail)


def _fusion_frc_surface_report(repo_path: Path) -> SurfaceReport:
    mif_src = str(Path(__file__).resolve().parents[1])
    fusion_src = str(repo_path / "src")
    script = (
        "import json\n"
        "from scpn_mif_core.physics import inspect_fusion_frc_contract\n"
        "import scpn_fusion.core as fusion_core\n"
        "report = inspect_fusion_frc_contract(fusion_core)\n"
        "print(json.dumps({'ready': report.ready_for_mif_integration, "
        "'missing': report.missing_required_symbols, 'blocked': report.blocked_claim_boundaries}))\n"
    )
    process = _run_python(repo_path, script, extra_paths=(mif_src, fusion_src))
    if process.returncode != 0:
        detail = _compact_error(process.stderr) or _compact_error(process.stdout) or "FUSION FRC import failed"
        return SurfaceReport("FUSION FRC public contract", STATUS_BLOCKED_RUNTIME, detail)
    try:
        payload = json.loads(process.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return SurfaceReport("FUSION FRC public contract", STATUS_BLOCKED_RUNTIME, "FRC report did not return JSON")
    if payload.get("ready") is not True:
        missing = payload.get("missing", [])
        return SurfaceReport("FUSION FRC public contract", STATUS_BLOCKED_SURFACE, f"missing symbols: {missing}")
    blocked = payload.get("blocked", [])
    if blocked:
        return SurfaceReport(
            "FUSION FRC public contract",
            STATUS_READY_WITH_BLOCKERS,
            f"public symbols present; explicit evidence blockers remain: {', '.join(map(str, blocked))}",
        )
    return SurfaceReport("FUSION FRC public contract", STATUS_READY, "FUS-C.1..FUS-C.7 public symbols present")


def _quantum_surface_reports(repo_path: Path, surfaces: Sequence[SurfaceSpec]) -> tuple[SurfaceReport, ...]:
    reports: list[SurfaceReport] = []
    all_source = _repo_python_text(repo_path)
    for surface in surfaces:
        if surface.file_path:
            reports.append(_generic_surface_report(repo_path, surface))
            continue
        found = tuple(token for token in surface.tokens if token in all_source)
        missing = tuple(token for token in surface.tokens if token not in all_source)
        if missing:
            reports.append(
                SurfaceReport(
                    surface.name,
                    STATUS_DEFERRED,
                    f"present: {', '.join(found) if found else 'none'}; deferred missing names: {', '.join(missing)}",
                )
            )
        else:
            reports.append(SurfaceReport(surface.name, STATUS_READY, surface.detail))
    return tuple(reports)


def _repo_python_text(repo_path: Path) -> str:
    parts: list[str] = []
    for path in (repo_path / "src").rglob("*.py"):
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _sibling_status(spec: SiblingSpec, import_status: str, surfaces: Iterable[SurfaceReport]) -> str:
    if not spec.current_gate:
        return STATUS_DEFERRED
    surface_statuses = tuple(surface.status for surface in surfaces)
    if any(status == STATUS_BLOCKED_SURFACE for status in surface_statuses):
        return STATUS_BLOCKED_SURFACE
    if any(status == STATUS_READY_WITH_BLOCKERS for status in surface_statuses):
        return STATUS_READY_WITH_BLOCKERS
    if spec.key == "sc-neurocore-engine":
        return STATUS_READY_WITH_HARDWARE_GATE
    if import_status != "ok":
        return STATUS_BLOCKED_RUNTIME
    if any(status == STATUS_BLOCKED_RUNTIME for status in surface_statuses):
        return STATUS_BLOCKED_RUNTIME
    return STATUS_READY


def _notes(
    spec: SiblingSpec,
    import_status: str,
    import_detail: str,
    import_version: str | None,
    source_version: str | None,
) -> tuple[str, ...]:
    notes = list(spec.notes)
    if import_status != "ok":
        notes.append(f"Runtime import is non-authoritative for this row and currently reports: {import_detail}.")
    if import_version and source_version and import_version != source_version:
        notes.append(f"Runtime package metadata reports {import_version}; sibling source declares {source_version}.")
    return tuple(notes)


def _run_python(repo_path: Path, script: str, extra_paths: Sequence[str] = ()) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONWARNINGS", None)
    paths = [str(repo_path / "src"), *extra_paths]
    existing = env.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return subprocess.run(  # noqa: S603  # nosec B603  # fixed sys.executable + internal script, shell=False
        [sys.executable, "-c", script],
        cwd=repo_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30.0,
        check=False,
    )


def _compact_error(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    selected = lines[-3:]
    return " | ".join(selected)[:500]


__all__ = [
    "SIBLINGS",
    "EcosystemReport",
    "SiblingReport",
    "SiblingSpec",
    "SurfaceReport",
    "SurfaceSpec",
    "compatibility_report_json",
    "default_code_root",
    "generate_ecosystem_report",
    "render_compatibility_matrix",
]
