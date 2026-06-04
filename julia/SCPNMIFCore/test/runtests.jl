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

@testset "MIF-001 Doppler-Kuramoto" begin
    spec = DopplerKuramotoSpec(
        [-4.0e6, 4.0e6],
        [0.0 25.0e6; 25.0e6 0.0];
        phase_lag_rad = 0.0,
        doppler_strength_rad_s = 2.0e6,
        velocity_epsilon_m_s = 1.0,
        distance_scale_m = 1.0,
    )
    derivatives = doppler_derivatives(
        spec,
        [0.0, 0.25],
        [-0.03, 0.03],
        [300_000.0, -300_000.0],
    )
    expected0 = -4.0e6 + (25.0e6 / 1.06) * sin(0.25) + 2.0e6 * (600_000.0 / 300_001.0)
    expected1 = 4.0e6 + (25.0e6 / 1.06) * sin(-0.25) + 2.0e6 * (-600_000.0 / 300_001.0)
    @test derivatives[1] ≈ expected0 rtol = 1e-12
    @test derivatives[2] ≈ expected1 rtol = 1e-12

    report = evaluate_doppler_kuramoto(
        spec,
        [0.0, 0.25],
        [-0.03, 0.03],
        [300_000.0, -300_000.0];
        dt_s = 1.0e-9,
        steps = 120,
    )
    centre_idx = argmin(vec(maximum(abs.(report.positions_m), dims = 2)))
    @test maximum(abs.(report.positions_m[centre_idx, :])) <= 2.0e-3
    @test report.phase_lock_error_rad[centre_idx] < 1.0e-2
    @test report.order_parameter[centre_idx] > 0.99999
end
