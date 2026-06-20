<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
<!-- Commercial license available -->
<!-- © Concepts 1996–2026 Miroslav Šotek. All rights reserved. -->
<!-- © Code 2020–2026 Miroslav Šotek. All rights reserved. -->
<!-- ORCID: 0009-0009-3560-0851 -->
<!-- Contact: www.anulum.li | protoscience@anulum.li -->
<!-- SCPN-MIF-CORE — examples index. -->

# Examples

Runnable scripts that exercise the public API end to end. Each script exposes a
`main()` and is smoke-tested in `tests/integration/test_examples.py`.

| Script | Shows |
|---|---|
| [`frc_merge_trigger.py`](frc_merge_trigger.py) | The merge-trigger decision on a locked, safe approach (fires) and a diverging approach (preempted as unsafe). |
| [`pulsed_shot_lifecycle.py`](pulsed_shot_lifecycle.py) | The eight-state pulsed-shot lifecycle FSM traversing one complete shot under a telemetry script. |

Run any example from the repository root:

```bash
python examples/frc_merge_trigger.py
python examples/pulsed_shot_lifecycle.py
```
