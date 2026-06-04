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

    affine_spec = DopplerKuramotoSpec(
        [1_200.0],
        [0.0;;];
        omega_rate_rad_s2 = [-20_000.0],
    )
    affine_engine = DopplerKuramoto(affine_spec, [0.0], [0.0], [0.0])
    affine_state = nothing
    affine_dt_s = 1.0e-6
    affine_steps = 1_000
    for _ in 1:affine_steps
        affine_state = step!(affine_engine, affine_dt_s)
    end
    affine_t_s = affine_steps * affine_dt_s
    affine_expected = 1_200.0 * affine_t_s + 0.5 * -20_000.0 * affine_t_s^2
    @test affine_state.t_s ≈ affine_t_s atol = 1e-15
    @test affine_state.phases_rad[1] ≈ affine_expected rtol = 1.0e-6 atol = 1.0e-9
    @test doppler_derivatives(affine_spec, [0.0], [0.0], [0.0]; t_s = affine_t_s)[1] ≈
        1_200.0 - 20_000.0 * affine_t_s rtol = 1e-15

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

@testset "MIF-002 Moving-frame UPDE" begin
    spec = MovingFrameUPDESpec(
        [-4.0e6, 4.0e6],
        [0.0 25.0e6; 25.0e6 0.0];
        phase_lag_rad = 0.0,
        doppler_strength_rad_s = 2.0e6,
        velocity_epsilon_m_s = 1.0,
        distance_scale_m = 1.0,
        reference_point_m = 0.0,
    )
    derivatives = moving_frame_derivatives(
        spec,
        [0.0, 0.25],
        [-0.03, 0.03],
        [300_000.0, -300_000.0],
    )
    @test length(derivatives) == 4
    @test derivatives[3] == 300_000.0
    @test derivatives[4] == -300_000.0

    engine = MovingFrameUPDE(spec, [0.0, 0.25], [-0.03, 0.03], [300_000.0, -300_000.0])
    @test time_to_reference_s(engine) ≈ [1.0e-7, 1.0e-7] rtol = 1e-15
    state = nothing
    for _ in 1:100
        state = step!(engine, 1.0e-9)
    end
    @test state.reference_error_m <= 2.0e-3
    @test state.separation_m <= 4.0e-3
    @test collision_imminent(engine; eps_m = 2.0e-3)
end

@testset "MIF-005 Capacitor bank" begin
    spec = CapacitorBankSpec(100e-6, 100e-6, 0.5, 10_000.0, 10.0)
    critical_spec = CapacitorBankSpec(100e-6, 100e-6, 2.0, 10_000.0, 10.0)
    overdamped_spec = CapacitorBankSpec(100e-6, 100e-6, 10.0, 10_000.0, 10.0)
    @test regime(spec) == UNDERDAMPED
    @test regime(critical_spec) == CRITICALLY_DAMPED
    @test regime(overdamped_spec) == OVERDAMPED

    t = 1.0e-5
    v0 = 5000.0
    alpha = spec.series_resistance_ohm / (2.0 * spec.inductance_H)
    omega0 = 1.0 / sqrt(spec.inductance_H * spec.capacitance_F)
    omega_d = sqrt(omega0^2 - alpha^2)
    expected_v = exp(-alpha * t) * v0 * (cos(omega_d * t) + (alpha / omega_d) * sin(omega_d * t))
    expected_i = (v0 / (spec.inductance_H * omega_d)) * exp(-alpha * t) * sin(omega_d * t)

    v, i = free_response(spec, t, v0)
    @test v ≈ expected_v rtol = 1e-12
    @test i ≈ expected_i rtol = 1e-12
    @test free_response(critical_spec, 0.0, v0) == (v0, 0.0)
    v_over, i_over = free_response(overdamped_spec, t, v0)
    @test isfinite(v_over)
    @test isfinite(i_over)

    bank = CapacitorBank(spec, v0)
    state = nothing
    for _ in 1:100
        state = step!(bank, 1.0e-7)
    end
    v_anal, i_anal = free_response(spec, 1.0e-5, v0)
    @test state.voltage_V ≈ v_anal rtol = 1.0e-3
    @test state.current_A ≈ i_anal rtol = 1.0e-3
    @test state.energy_J ≈ 0.5 * spec.capacitance_F * state.voltage_V^2 rtol = 1e-15

    loaded = CapacitorBank(spec, v0)
    natural = CapacitorBank(spec, v0)
    for _ in 1:50
        step!(loaded, 1.0e-7, 50.0)
        step!(natural, 1.0e-7)
    end
    @test loaded.state.energy_J < natural.state.energy_J

    reset!(bank, 3000.0)
    @test bank.state.t == 0.0
    @test bank.state.voltage_V == 3000.0
    @test bank.state.current_A == 0.0

    @test_throws ArgumentError CapacitorBankSpec(-1.0, 100e-6, 0.5, 10_000.0, 10.0)
    @test_throws ArgumentError CapacitorBank(spec, spec.voltage_max_V + 1.0)
    @test_throws ArgumentError reset!(bank, -1.0)
    @test_throws ArgumentError free_response(spec, -1.0e-9, v0)
end

@testset "MIF-016 Diagnostic normalisation" begin
    calibrations = [
        DiagnosticChannelCalibration(
            "temperature_eV",
            "eV",
            0.0,
            1000.0,
            "clip",
            "thermal calibration",
            0,
        ),
        DiagnosticChannelCalibration(
            "bdot_V",
            "V",
            -10.0,
            10.0,
            "clip",
            "B-dot calibration",
            1,
        ),
    ]
    state = DiagnosticNormalisationState(calibrations, 50)
    sample = normalise_sample(
        state,
        Dict("temperature_eV" => 500.0, "bdot_V" => -5.0),
    )
    @test sample.features ≈ [0.0, -0.5] rtol = 0.0 atol = 0.0
    @test sample.clip_mask == (false, false)
    @test sample.out_of_range_channels == ()

    clipped = normalise_sample(
        state,
        Dict("temperature_eV" => 1200.0, "bdot_V" => -20.0),
    )
    @test clipped.features == [1.0, -1.0]
    @test clipped.clip_mask == (true, true)
    @test clipped.out_of_range_channels == ("temperature_eV", "bdot_V")
    @test all(-1.0 .<= clipped.features .<= 1.0)

    manifest = calibration_manifest(state)
    @test manifest.kernel == "diagnostics.normalisation"
    @test manifest.channels[1].physical_unit_range == [0.0, 1000.0]
    @test manifest.channels[1].offset == 500.0
    @test manifest.channels[1].scale == 0.002

    reject_cal = DiagnosticChannelCalibration(
        "bdot_dv_dt",
        "V/s",
        -1.0e9,
        1.0e9,
        "reject",
        "B-dot derivative calibration",
    )
    reject_state = DiagnosticNormalisationState([reject_cal])
    @test_throws ArgumentError normalise_sample(reject_state, Dict("bdot_dv_dt" => 2.0e9))
    @test_throws ArgumentError DiagnosticChannelCalibration("flat", "V", 1.0, 1.0, "clip", "flat")
end
