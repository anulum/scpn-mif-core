# SPDX-License-Identifier: AGPL-3.0-or-later
# SCPN-MIF-CORE — Julia tests.
using SCPNMIFCore
using Test

@testset "SCPNMIFCore bootstrap" begin
    @test SCPNMIFCore.VERSION == v"0.0.1"
end

@testset "MIF-009 Faraday recovery" begin
    spec = FaradayRecoverySpec(20.0, 5.0; coupling_efficiency=0.8)
    emf_radius = faraday_back_emf(0.2, 800.0, 5.0, 0.0, 12.0)
    @test emf_radius ≈ -12.0 * (2.0 * pi * 0.2 * 800.0 * 5.0) rtol = 1e-15

    emf_field = faraday_back_emf(0.17, 0.0, 3.0, 25_000.0, 48.0)
    @test emf_field ≈ -48.0 * (pi * 0.17^2 * 25_000.0) rtol = 1e-15
    @test faraday_back_emf(0.4, 0.0, 8.0, 0.0, 32.0) ≈ 0.0 atol = 1e-15

    time_s = [0.0, 0.5, 1.0, 1.5]
    radius_m = fill(0.1, length(time_s))
    radial_velocity_m_s = zeros(length(time_s))
    magnetic_field_T = 3.0 .+ 2.0 .* time_s
    magnetic_field_rate_T_s = fill(2.0, length(time_s))
    report = evaluate_faraday_recovery(
        spec,
        time_s,
        radius_m,
        radial_velocity_m_s,
        magnetic_field_T,
        magnetic_field_rate_T_s,
    )
    expected_emf = -spec.turns * pi * 0.1^2 * 2.0
    expected_power = spec.coupling_efficiency * expected_emf^2 / spec.load_resistance_ohm
    @test all(isapprox.(report.back_emf_V, expected_emf; rtol = 0.0, atol = 1e-15))
    @test report.recovered_energy_J ≈ expected_power * 1.5 rtol = 1e-15

    @test_throws ArgumentError FaradayRecoverySpec(0.0, 1.0)
    @test_throws ArgumentError faraday_back_emf(-0.1, 0.0, 5.0, 0.0, 10.0)
end
