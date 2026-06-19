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
    @test_throws ArgumentError magnetic_flux(1e154, 1e154)
    @test_throws ArgumentError flux_rate(1e154, 0.0, 0.0, 1e154)
    @test_throws ArgumentError faraday_back_emf(1.0, 0.0, 0.0, 1e154, 1e154)
    @test_throws ArgumentError recovered_power(FaradayRecoverySpec(1.0, 1.0), 1e200)
    zero_coupling = FaradayRecoverySpec(1.0, 1.0; coupling_efficiency = 0.0)
    @test recovered_power(zero_coupling, 1e200) == 0.0
    zero_report = evaluate_faraday_recovery(
        zero_coupling,
        [0.0, 1.0],
        [1.0, 1.0],
        [0.0, 0.0],
        [0.0, 0.0],
        [1e200, 1e200],
    )
    @test all(zero_report.recovered_power_W .== 0.0)
    @test zero_report.recovered_energy_J == 0.0
    @test zero_report.peak_recovered_power_W == 0.0
    @test_throws ArgumentError evaluate_faraday_recovery(
        FaradayRecoverySpec(1.0, 1.0),
        [0.0, 1.0],
        [1e154, 1e154],
        [0.0, 0.0],
        [1e154, 1e154],
        [0.0, 0.0],
    )
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

    pair_spec = DopplerKuramotoSpec(
        [0.0, 0.0],
        [0.0 0.0; 0.0 0.0];
        doppler_strength_rad_s = 1.0,
        velocity_epsilon_m_s = 10.0,
    )
    pair_derivatives = doppler_derivatives(pair_spec, [0.0, 0.0], [0.0, 0.0], [120.0, -30.0])
    pair_expected = 150.0 / (0.5 * (120.0 + 30.0) + 10.0)
    @test pair_derivatives[1] ≈ pair_expected rtol = 1e-15
    @test pair_derivatives[2] ≈ -pair_expected rtol = 1e-15

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

    wrap_spec = MovingFrameUPDESpec([10.0], [0.0;;])
    wrap_engine = MovingFrameUPDE(wrap_spec, [pi - 0.01], [0.0], [0.0])
    wrap_state = step!(wrap_engine, 0.002)
    @test wrap_state.phases_rad[1] ≈ -pi + 0.01 atol = 1.0e-15
    @test wrap_state.positions_m[1] ≈ 0.0 atol = 1.0e-15
    @test wrap_state.local_error_estimate <= 1.0e-14
end

@testset "MIF-011 Kinematic safety certificate" begin
    spec = KinematicSafetySpec(; tolerance_m = 0.002, contraction = 0.75, disturbance_ratio = 0.2)
    cert = certify_sampled_kinematic_safety([0.0018, 0.0014, 0.00105, 0.0008], spec)
    @test cert.passed
    @test cert.samples == 4
    @test cert.budget_margin ≈ 0.05 atol = 1e-15
    @test cert.initial_margin_m > 0.0
    @test cert.minimum_step_slack_m >= 0.0
    @test cert.first_violation_index === nothing

    failed = certify_sampled_kinematic_safety(
        [0.001, 0.0015],
        KinematicSafetySpec(; contraction = 0.5, disturbance_ratio = 0.1, numerical_tolerance_m = 0.0),
    )
    @test !failed.passed
    @test failed.first_violation_index == 1
    @test failed.max_step_violation_m > 0.0

    initial_failed = certify_sampled_kinematic_safety(
        [0.0025, 0.001],
        KinematicSafetySpec(; contraction = 0.5, disturbance_ratio = 0.1, numerical_tolerance_m = 0.0),
    )
    @test !initial_failed.passed
    @test initial_failed.first_violation_index == 0

    @test_throws ArgumentError KinematicSafetySpec(; contraction = 0.9, disturbance_ratio = 0.2)
    @test_throws ArgumentError certify_sampled_kinematic_safety(Float64[])
    @test_throws ArgumentError certify_sampled_kinematic_safety([0.0, NaN])
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
    @test natural_peak_current_A(bank) ≈ v0 / sqrt(spec.inductance_H / spec.capacitance_F)
    state = nothing
    for _ in 1:100
        state = step!(bank, 1.0e-7)
    end
    v_anal, i_anal = free_response(spec, 1.0e-5, v0)
    @test state.voltage_V ≈ v_anal rtol = 1.0e-3
    @test state.current_A ≈ i_anal rtol = 1.0e-3
    expected_capacitor = 0.5 * spec.capacitance_F * state.voltage_V^2
    expected_inductor = 0.5 * spec.inductance_H * state.current_A^2
    @test state.capacitor_energy_J ≈ expected_capacitor rtol = 1e-15
    @test state.inductor_energy_J ≈ expected_inductor rtol = 1e-15
    @test state.energy_J ≈ expected_capacitor + expected_inductor rtol = 1e-15

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
    @test_throws ArgumentError CapacitorBankSpec(1.0e308, 1.0, 0.0, 1.0e154, 0.0)
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
    @test_throws ArgumentError DiagnosticChannelCalibration("wide_field_T", "T", -1.0e308, 1.0e308, "clip", "wide range calibration")
    @test_throws ArgumentError DiagnosticChannelCalibration("subnormal_probe_V", "V", 0.0, 5.0e-324, "clip", "subnormal span calibration")

    large_cal = DiagnosticChannelCalibration(
        "dense_plasma_m3",
        "m^-3",
        1.0e308,
        1.2e308,
        "clip",
        "large finite range calibration",
    )
    @test isfinite(SCPNMIFCore.offset(large_cal))
    @test SCPNMIFCore.offset(large_cal) == large_cal.physical_min + 0.5 * (large_cal.physical_max - large_cal.physical_min)
    normalised, clipped_flag = normalise_value(large_cal, 1.1e308)
    @test normalised ≈ 0.0 atol = 1.0e-12
    @test !clipped_flag
end

@testset "MIF-017 Diagnostic stress injection" begin
    config = StressInjectionConfig(
        7,
        NoiseSpec(Dict(
            "temperature_eV" => 10.0,
            "bdot_V" => 0.5,
            "phase_lock_error_rad" => 1.0e-3,
        )),
        DropoutSpec(Dict("bdot_V" => 1.0)),
        JitterSpec(10, 50, 1.0),
    )
    frames = [
        DiagnosticFrame(
            1000,
            Dict(
                "temperature_eV" => 500.0,
                "bdot_V" => 0.0,
                "phase_lock_error_rad" => 0.0,
            ),
        ),
        DiagnosticFrame(
            1100,
            Dict(
                "temperature_eV" => 505.0,
                "bdot_V" => 0.1,
                "phase_lock_error_rad" => 0.0,
            ),
        ),
    ]
    stream = DegradedSensorStream(config)
    first = apply(stream, frames)
    first_log = copy(stream.audit_log)
    second = apply(DegradedSensorStream(config), frames)

    @test first[1].samples == second[1].samples
    @test 10 <= abs(first_log[1].jitter_ns) <= 50
    @test first_log[1].emitted_t_ns - first_log[1].source_t_ns == first_log[1].jitter_ns
    @test "bdot_V" in first_log[1].dropped_channels
    @test "temperature_eV" in first_log[1].noisy_channels
    @test !haskey(first[1].samples, "bdot_V")
    @test first[1].samples["temperature_eV"] != 500.0

    @test_throws ArgumentError NoiseSpec(Dict("temperature_eV" => -1.0))
    @test_throws ArgumentError DropoutSpec(Dict("bdot_V" => 1.2))
    @test_throws ArgumentError JitterSpec(50, 10, 1.0)

    overflow_config = StressInjectionConfig(
        3,
        NoiseSpec(Dict("temperature_eV" => 1.0e308)),
        DropoutSpec(Dict()),
        JitterSpec(0, 0, 0.0),
    )
    overflow_stream = DegradedSensorStream(overflow_config)
    overflow_error = try
        apply(overflow_stream, [DiagnosticFrame(1000, Dict("temperature_eV" => 1.0e308))])
        nothing
    catch err
        err
    end
    @test overflow_error isa ArgumentError
    @test occursin("stressed sample", sprint(showerror, overflow_error))
end

@testset "MIF-003 merge-window monitor" begin
    spec = MergeWindowSpec(
        phase_tolerance_rad = 0.01,
        spatial_tolerance_m = 0.002,
        consecutive_samples = 3,
        reference_point_m = 0.0,
    )

    rows = 256
    time_s = collect(0:rows-1) .* 1.0e-9
    phases = repeat([0.0 0.003 -0.002], rows)
    positions = repeat([-0.001 0.0005 0.0015], rows)
    # Row 1 fails the phase tolerance; row 2 fails the spatial tolerance; locking
    # then begins on row 3 and reaches the consecutive threshold on row 5.
    phases[1, 2] = 0.04
    positions[2, :] = [-0.004, 0.0, 0.004]

    trace = evaluate_merge_window_trace(spec, time_s, phases, positions)
    @test trace.lock_achieved
    @test trace.first_lock_time_s ≈ 4.0e-9 rtol = 1e-15
    @test trace.samples[end].streak == rows - 2
    @test trace.samples[1].candidate_lock == false
    @test trace.samples[2].candidate_lock == false
    @test trace.samples[5].lock_achieved

    # A clean three-oscillator window is an immediate lock candidate.
    single = evaluate_merge_window_trace(spec, [0.0], reshape([0.0, 0.003, -0.002], 1, 3), reshape([-0.001, 0.0005, 0.0015], 1, 3))
    @test single.samples[1].candidate_lock
    @test single.samples[1].separation_m ≈ 0.0025 rtol = 1e-15

    nonincreasing = try
        evaluate_merge_window_trace(spec, [0.0, 0.0], repeat([0.0 0.003 -0.002], 2), repeat([-0.001 0.0005 0.0015], 2))
        nothing
    catch err
        err
    end
    @test nonincreasing isa ArgumentError
    @test occursin("strictly increasing", sprint(showerror, nonincreasing))

    shape_mismatch = try
        evaluate_merge_window_trace(spec, [0.0], reshape([0.0, 0.003], 1, 2), reshape([-0.001, 0.0005, 0.0015], 1, 3))
        nothing
    catch err
        err
    end
    @test shape_mismatch isa ArgumentError
end

@testset "MIF-006 AER spike buffer and decode" begin
    events = [AERSpikeEvent(idx % 16, idx * 10, idx % 5 == 0 ? -1 : 1) for idx in 0:255]
    buffer = AERSpikeBuffer(512)
    for event in events
        push_spike!(buffer, event)
    end
    @test length(buffer) == 256

    spec = AERDecodeSpec(16, 4096, :rate, 0)
    features = decode_spike_features(buffer, spec)
    @test length(features) == 16
    # 204 events carry +1 and 52 carry -1; all fall inside the 4096 ns window,
    # so the summed rate is 152 / 4096.
    @test sum(features) ≈ 152 / 4096 rtol = 1e-15

    observation = decode_spike_observation(buffer, spec)
    @test observation.spike_count == 256
    @test observation.window_start_ns == 0
    @test observation.window_stop_ns == 4096

    # Temporal strategy encodes first-spike latency as 1 - (t - start) / window.
    temporal = AERSpikeBuffer(8)
    push_spike!(temporal, AERSpikeEvent(0, 0, 1))
    push_spike!(temporal, AERSpikeEvent(1, 1024, 1))
    temporal_features = decode_spike_features(temporal, AERDecodeSpec(2, 4096, :temporal, 0))
    @test temporal_features[1] ≈ 1.0 rtol = 1e-15
    @test temporal_features[2] ≈ 0.75 rtol = 1e-15

    # Inter-spike-interval strategy is the reciprocal mean interval in 1/ns.
    isi = AERSpikeBuffer(8)
    push_spike!(isi, AERSpikeEvent(0, 0, 1))
    push_spike!(isi, AERSpikeEvent(0, 100, 1))
    push_spike!(isi, AERSpikeEvent(0, 300, 1))
    isi_features = decode_spike_features(isi, AERDecodeSpec(1, 4096, :isi, 0))
    @test isi_features[1] ≈ 2 / 300 rtol = 1e-15

    # The ring evicts the oldest event past capacity.
    ring = AERSpikeBuffer(2)
    push_spike!(ring, AERSpikeEvent(0, 0, 1))
    push_spike!(ring, AERSpikeEvent(1, 10, 1))
    push_spike!(ring, AERSpikeEvent(2, 20, 1))
    @test length(ring) == 2
    @test ring.events[1].address == 1

    monotone = try
        bad = AERSpikeBuffer(4)
        push_spike!(bad, AERSpikeEvent(0, 100, 1))
        push_spike!(bad, AERSpikeEvent(0, 50, 1))
        nothing
    catch err
        err
    end
    @test monotone isa ArgumentError
    @test occursin("monotone", sprint(showerror, monotone))

    out_of_range = try
        small = AERSpikeBuffer(4)
        push_spike!(small, AERSpikeEvent(5, 0, 1))
        decode_spike_features(small, AERDecodeSpec(2, 4096, :rate, 0))
        nothing
    catch err
        err
    end
    @test out_of_range isa ArgumentError
    @test occursin("outside n_channels", sprint(showerror, out_of_range))

    @test_throws ArgumentError AERSpikeEvent(0, 0, 2)
    @test_throws ArgumentError AERDecodeSpec(0, 4096, :rate)
    @test_throws ArgumentError AERDecodeSpec(16, 4096, :unknown)
end
