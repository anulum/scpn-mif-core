<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->
# Go services

Network-facing daemons and tooling for SCPN-MIF-CORE: AER router glue,
telemetry fan-out, replay-streaming WebSocket server, and the optional
campaign daemon.
MIF-018 adds the DAQ mock scaffold used to validate UDP-style replay frame
encoding before a long-running daemon is introduced.

## Layout

```
go.mod                        module: github.com/anulum/scpn-mif-core/go
go/
├── services/                 long-running daemons
│   ├── telemetry_daemon/
│   ├── aer_router_glue/
│   └── campaign_daemon/      (optional, build-tagged)
├── cmd/
│   └── daqmock_probe/        MIF-018 benchmark probe
└── daqmock/                  MIF-018 frame codec
```

## Build

```bash
cd go
go build ./...
go test ./...
```

## API documentation

From the repository root, enforce package and exported-declaration comments and
render every package through the native Go documentation tool:

```bash
go run ./go/cmd/doccheck ./go/...
for package in $(go list ./go/...); do go doc -all "$package" >/dev/null; done
```

The advisory polyglot workflow and the local preflight run both checks. The
generated output is intentionally ephemeral; the documented Go source remains
the canonical API contract.

Implementation lands in P4 (CON-C.6 multi-shot campaign) and P5 (telemetry).
