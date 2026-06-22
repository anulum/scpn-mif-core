# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — one-command demo image.
#
# Builds the pure-Python floor (the multi-backend dispatch falls back to Python
# when the Rust extension is absent, so the demo runs with no Rust toolchain) plus
# the `demo` extra for the campaign figures. Build and run the full demo:
#
#   docker build -t scpn-mif-core .
#   docker run --rm scpn-mif-core
#
# It prints the lifecycle + merge-trigger results and writes the campaign JSON +
# PNG artifacts into campaigns/results/ inside the container.

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[demo]"

CMD ["make", "demo"]
