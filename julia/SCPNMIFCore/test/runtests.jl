# SPDX-License-Identifier: AGPL-3.0-or-later
# SCPN-MIF-CORE — Julia tests.
using SCPNMIFCore
using Test

@testset "SCPNMIFCore bootstrap" begin
    @test SCPNMIFCore.VERSION == v"0.0.1"
end
