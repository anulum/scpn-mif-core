# Analytical current-driven LIF reference

`campaigns/lif_oracles/analytic_decimal.py` is an independent numerical oracle
for the normalised, piecewise-constant equation

\[
\tau\dot V=-(V-V_{rest})+RI.
\]

The integrating factor yields
\(V(t)=V_\infty+(V(0)-V_\infty)e^{-t/\tau}\), where
\(V_\infty=V_{rest}+RI\). For \(V_\infty>V_{threshold}\), solving the
threshold equation yields the next crossing. Crossing at an interval endpoint
emits a spike; immediate hard reset precedes further evolution within the same
interval. The reference retains initial, threshold, reset and tick-end states.

The oracle uses Python Decimal arithmetic and imports no MIF, CONTROL or
SC-NeuroCore solver. Contributions are summed in a context wide enough for
exact decimal cancellation before evolution. Input strings represent exact
decimal values; binary64 inputs must first be encoded using
`str(Decimal.from_float(value))`. The default profile has a 20 ms time
constant, rest/reset -65, threshold -50 and normalised resistance 1.

The existing full-chain CI lane executes 384 deterministic regression
trajectories through real AER ingress, the MIF bridge, CONTROL and SC-NeuroCore.
Six forcing families cover telegraph currents, simultaneous contributions,
burst/quiet intervals, staircases, rheobase and sustained drive. Each family
sweeps 64 exactly representable pulse widths from 1 to 1.984375 ms. Expected
forcing is constructed independently from the requested input, rather than
copied from the resulting projection. The oracle runs at 80 and 120 digits;
their state/event differences must be below 1e-60. Binary64 state/time
comparisons use a tolerance of max(2e-12, 64 ULP), with exact event counts and
ordered state phases. These thresholds are regression criteria, not a
measured error certificate.

Dedicated unit tests exercise limiting solutions, endpoint crossing, repeated
spikes and remainder, continuation, cancellation order, precision agreement
and refusal of invalid or unresolved trajectories. An event budget raises an
error instead of returning a truncated successful trace. Numerically unresolved
subthreshold states at the threshold also raise.

This surface is analytical regression evidence for normalised simulation.
Decimal precision agreement is not interval arithmetic or a formal proof.
It does not establish held-out performance, NEST/Brian2 conformance, biological
or facility calibration, fixed-point/RTL parity, hardware timing or actuation
authority. Only an actual CI result establishes whether a revision passes.
