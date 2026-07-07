<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — fire-time selection documentation. -->

# Fire-Time Selection

Retrospective selection of the fire instant over an evaluated
merge-window trace. `FIRST_LOCK` — the default and the streaming trigger's
latch instant — stays the reference policy; `MAX_WINDOW_MARGIN` is the
**opt-in** optimiser that picks the locked sample with the widest normalised
window margin `min((phi_tol - phi_err)/phi_tol, (x_tol - x_ref)/x_tol)`
(ties go to the earliest sample).

```python
from scpn_mif_core import (
    FireTimePolicy,
    certify_sampled_kinematic_safety,
    evaluate_merge_window_trace,
    select_fire_time,
)

trace = evaluate_merge_window_trace(window, time_s, phases_rad, positions_m)
certificate = certify_sampled_kinematic_safety([s.separation_m for s in trace.samples])
decision = select_fire_time(
    trace,
    window,
    certificate,
    bank_feasible=True,
    policy=FireTimePolicy.MAX_WINDOW_MARGIN,   # opt-in; FIRST_LOCK is the default
)
```

## Subordination guarantee

The optimiser never widens the verified fire envelope: it selects only among
samples the deterministic merge-window law already locked, and only when the
MIF-011 batch safety certificate passed, the bank is feasible, and the lane
is armed — the same gates the batch pipeline applies. A failed gate yields a
non-firing decision regardless of policy, so the policy can change *when* an
admissible shot fires, never *whether* an inadmissible one does. The seeded
sweep in `tests/unit/kinematic/test_fire_time.py` pins this property, and
the `FIRST_LOCK` instant is pinned against the actual streaming engine.

## No acceleration path

This is once-per-shot selection logic over an already-evaluated trace — a
handful of comparisons per sample after the dispatched kernels have done the
numeric work — so, like the merge-window feature boundary and the advisory
predictor, it has no multi-language acceleration path.

## API

::: scpn_mif_core.kinematic.fire_time
