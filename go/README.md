<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Go services

Network-facing daemons and tooling for SCPN-MIF-CORE: AER router glue,
telemetry fan-out, replay-streaming WebSocket server, and the optional
campaign daemon.

## Layout

```
go/
├── go.mod                    (root: github.com/anulum/scpn-mif-core/go)
├── services/                 long-running daemons
│   ├── telemetry_daemon/
│   ├── aer_router_glue/
│   └── campaign_daemon/      (optional, build-tagged)
└── pkg/                      shared Go libraries
```

## Build

```bash
cd go
go build ./...
go test ./...
```

Implementation lands in P4 (CON-C.6 multi-shot campaign) and P5 (telemetry).
