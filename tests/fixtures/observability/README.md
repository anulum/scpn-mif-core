# MIF merge-compression observation fixture

The canonical fixture is produced through the public `merge_compression_observation_to_bytes` API from real `MovingFrameUPDEState` and `StreamingMergeTrigger` carriers.

- schema: `scpn-mif-core.merge-compression-observation.v1`
- producer revision: `f60dbae4b2ea3344ac0cb086a3b7d248d65cf92f`
- exact length: 2,475 bytes
- SHA-256: `c780706abd5a0b185a95e85767e623248388664da61126d196fcb3d528b0c0ca`
- evidence class: numerical simulation
- authority: review-only, non-actionable

Update custody: change the fixture only with a versioned producer-schema change, regenerate it from the public API, pin the new exact length/digest/revision, and update all downstream immutable receipts. It is not captured facility data, physical-phase evidence, hardware-in-the-loop evidence, or proof that a compression command actuated hardware.
