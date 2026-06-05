// SPDX-License-Identifier: AGPL-3.0-or-later
// Commercial license available
// © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
// © Code 2020–2026 Miroslav Šotek. All rights reserved.
// ORCID: 0009-0009-3560-0851
// Contact: www.anulum.li | protoscience@anulum.li
// SCPN-MIF-CORE — MIF-016 diagnostic normalisation kernel.
//! Diagnostic signal normalisation for MIF-016.
//!
//! Maps calibrated physical diagnostic channels into the closed interval
//! `[-1, 1]` before AER encoding. The deterministic clip/reject policy is part
//! of each channel calibration so the downstream front-end never receives an
//! overflowing feature vector. Calibration validation also rejects finite
//! endpoint pairs that would produce non-finite affine coefficients.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

use std::{collections::HashSet, str::FromStr};

use thiserror::Error;

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
const MASK64: u64 = u64::MAX;
const GOLDEN_GAMMA: u64 = 0x9E37_79B9_7F4A_7C15;
const FRAME_MIX: u64 = 0xD1B5_4A32_D192_ED03;

/// Out-of-range behavior for one diagnostic channel.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ClipPolicy {
    /// Saturate deterministically at the nearest calibrated endpoint.
    Clip,
    /// Reject the sample with an error when it leaves the calibrated interval.
    Reject,
}

impl ClipPolicy {
    /// Return the canonical manifest identifier.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Clip => "clip",
            Self::Reject => "reject",
        }
    }
}

impl FromStr for ClipPolicy {
    type Err = DiagnosticError;

    /// Parse a canonical clip-policy identifier.
    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "clip" => Ok(Self::Clip),
            "reject" => Ok(Self::Reject),
            _ => Err(DiagnosticError::UnknownClipPolicy),
        }
    }
}

/// Calibration record for one diagnostic channel.
#[derive(Debug, Clone, PartialEq)]
pub struct DiagnosticChannelCalibration {
    /// Stable channel name.
    pub name: String,
    /// Physical unit label.
    pub unit: String,
    /// Lower physical calibration bound.
    pub physical_min: f64,
    /// Upper physical calibration bound.
    pub physical_max: f64,
    /// Out-of-range policy.
    pub clip_policy: ClipPolicy,
    /// Calibration provenance string.
    pub provenance: String,
    /// Optional AER output address for the channel.
    pub aer_address: Option<usize>,
}

impl DiagnosticChannelCalibration {
    /// Construct a validated channel calibration.
    pub fn new(
        name: impl Into<String>,
        unit: impl Into<String>,
        physical_min: f64,
        physical_max: f64,
        clip_policy: ClipPolicy,
        provenance: impl Into<String>,
        aer_address: Option<usize>,
    ) -> Result<Self, DiagnosticError> {
        let calibration = Self {
            name: name.into(),
            unit: unit.into(),
            physical_min,
            physical_max,
            clip_policy,
            provenance: provenance.into(),
            aer_address,
        };
        calibration.validate()?;
        Ok(calibration)
    }

    /// Physical midpoint subtracted before applying [`Self::scale`].
    pub fn offset(&self) -> f64 {
        self.physical_min + 0.5 * self.affine_span()
    }

    /// Multiplicative factor from physical units into `[-1, 1]`.
    pub fn scale(&self) -> f64 {
        2.0 / self.affine_span()
    }

    /// Return `(normalised_value, clipped)` for one sample.
    pub fn normalise_value(&self, value: f64) -> Result<(f64, bool), DiagnosticError> {
        require_finite("sample", value)?;
        let mut sample = value;
        let mut clipped = false;
        if sample < self.physical_min {
            if self.clip_policy == ClipPolicy::Reject {
                return Err(DiagnosticError::BelowRange {
                    channel: self.name.clone(),
                });
            }
            sample = self.physical_min;
            clipped = true;
        } else if sample > self.physical_max {
            if self.clip_policy == ClipPolicy::Reject {
                return Err(DiagnosticError::AboveRange {
                    channel: self.name.clone(),
                });
            }
            sample = self.physical_max;
            clipped = true;
        }
        Ok((clamp_unit((sample - self.offset()) * self.scale()), clipped))
    }

    fn validate(&self) -> Result<(), DiagnosticError> {
        require_non_empty("name", &self.name)?;
        require_non_empty("unit", &self.unit)?;
        require_non_empty("provenance", &self.provenance)?;
        require_finite("physical_min", self.physical_min)?;
        require_finite("physical_max", self.physical_max)?;
        if self.physical_max <= self.physical_min {
            return Err(DiagnosticError::InvalidRange);
        }
        self.validate_affine_coefficients()?;
        Ok(())
    }

    fn affine_span(&self) -> f64 {
        self.physical_max - self.physical_min
    }

    fn validate_affine_coefficients(&self) -> Result<(), DiagnosticError> {
        let span = self.affine_span();
        require_finite("affine span", span)?;
        if span <= 0.0 {
            return Err(DiagnosticError::InvalidRange);
        }
        require_finite("affine offset", self.physical_min + 0.5 * span)?;
        let scale = 2.0 / span;
        require_finite("affine scale", scale)?;
        if scale <= 0.0 {
            return Err(DiagnosticError::NonPositive {
                field: "affine scale",
            });
        }
        Ok(())
    }
}

/// Normalised vector plus clipping metadata.
#[derive(Debug, Clone, PartialEq)]
pub struct NormalisedDiagnosticSample {
    /// Ordered channel names matching the feature vector.
    pub channel_names: Vec<String>,
    /// Bounded feature vector.
    pub features: Vec<f64>,
    /// Per-channel clip mask.
    pub clip_mask: Vec<bool>,
    /// Channel names that clipped during normalisation.
    pub out_of_range_channels: Vec<String>,
    /// Optional nominal sample period.
    pub sample_period_ns: Option<u64>,
}

/// Ordered diagnostic normalisation state.
#[derive(Debug, Clone, PartialEq)]
pub struct DiagnosticNormalisationState {
    calibrations: Vec<DiagnosticChannelCalibration>,
    sample_period_ns: Option<u64>,
}

impl DiagnosticNormalisationState {
    /// Construct a validated normalisation state.
    pub fn new(
        calibrations: Vec<DiagnosticChannelCalibration>,
        sample_period_ns: Option<u64>,
    ) -> Result<Self, DiagnosticError> {
        if calibrations.is_empty() {
            return Err(DiagnosticError::EmptyCalibrations);
        }
        if sample_period_ns == Some(0) {
            return Err(DiagnosticError::NonPositive {
                field: "sample_period_ns",
            });
        }
        let mut names = HashSet::with_capacity(calibrations.len());
        for calibration in &calibrations {
            calibration.validate()?;
            if !names.insert(calibration.name.clone()) {
                return Err(DiagnosticError::DuplicateChannel {
                    channel: calibration.name.clone(),
                });
            }
        }
        Ok(Self {
            calibrations,
            sample_period_ns,
        })
    }

    /// Return ordered immutable calibrations.
    pub fn calibrations(&self) -> &[DiagnosticChannelCalibration] {
        &self.calibrations
    }

    /// Return ordered channel names.
    pub fn channel_names(&self) -> Vec<String> {
        self.calibrations
            .iter()
            .map(|calibration| calibration.name.clone())
            .collect()
    }

    /// Return the optional nominal sample period in nanoseconds.
    pub fn sample_period_ns(&self) -> Option<u64> {
        self.sample_period_ns
    }

    /// Normalise a positional vector in calibration order.
    pub fn normalise_features(
        &self,
        values: &[f64],
    ) -> Result<NormalisedDiagnosticSample, DiagnosticError> {
        if values.len() != self.calibrations.len() {
            return Err(DiagnosticError::VectorLengthMismatch {
                expected: self.calibrations.len(),
                actual: values.len(),
            });
        }
        let mut features = Vec::with_capacity(values.len());
        let mut clip_mask = Vec::with_capacity(values.len());
        let mut out_of_range_channels = Vec::new();
        for (calibration, value) in self.calibrations.iter().zip(values.iter()) {
            let (feature, clipped) = calibration.normalise_value(*value)?;
            features.push(feature);
            clip_mask.push(clipped);
            if clipped {
                out_of_range_channels.push(calibration.name.clone());
            }
        }
        Ok(NormalisedDiagnosticSample {
            channel_names: self.channel_names(),
            features,
            clip_mask,
            out_of_range_channels,
            sample_period_ns: self.sample_period_ns,
        })
    }
}

/// Per-channel degradation settings for MIF-017 stress injection.
#[derive(Debug, Clone, PartialEq)]
pub struct StressChannelConfig {
    /// Stable channel name.
    pub name: String,
    /// Additive Gaussian sigma in physical units.
    pub noise_sigma: f64,
    /// Bernoulli dropout probability.
    pub dropout_probability: f64,
}

impl StressChannelConfig {
    /// Construct a validated stress channel config.
    pub fn new(
        name: impl Into<String>,
        noise_sigma: f64,
        dropout_probability: f64,
    ) -> Result<Self, DiagnosticError> {
        let config = Self {
            name: name.into(),
            noise_sigma,
            dropout_probability,
        };
        config.validate()?;
        Ok(config)
    }

    fn validate(&self) -> Result<(), DiagnosticError> {
        require_non_empty("name", &self.name)?;
        require_finite("noise_sigma", self.noise_sigma)?;
        require_finite("dropout_probability", self.dropout_probability)?;
        if self.noise_sigma < 0.0 {
            return Err(DiagnosticError::Negative {
                field: "noise_sigma",
            });
        }
        if !(0.0..=1.0).contains(&self.dropout_probability) {
            return Err(DiagnosticError::ProbabilityOutOfRange {
                field: "dropout_probability",
            });
        }
        Ok(())
    }
}

/// Deterministic MIF-017 stress-injection configuration.
#[derive(Debug, Clone, PartialEq)]
pub struct StressInjectionConfig {
    /// Base seed.
    pub seed: u64,
    /// Per-channel settings.
    pub channels: Vec<StressChannelConfig>,
    /// Minimum absolute timestamp jitter in nanoseconds.
    pub jitter_min_ns: u64,
    /// Maximum absolute timestamp jitter in nanoseconds.
    pub jitter_max_ns: u64,
    /// Bernoulli probability that jitter is applied to a frame.
    pub jitter_probability: f64,
    /// Whether sampled jitter may be early or late rather than positive-only.
    pub jitter_signed: bool,
}

impl StressInjectionConfig {
    /// Construct a validated stress-injection config.
    pub fn new(
        seed: u64,
        channels: Vec<StressChannelConfig>,
        jitter_min_ns: u64,
        jitter_max_ns: u64,
        jitter_probability: f64,
        jitter_signed: bool,
    ) -> Result<Self, DiagnosticError> {
        let config = Self {
            seed,
            channels,
            jitter_min_ns,
            jitter_max_ns,
            jitter_probability,
            jitter_signed,
        };
        config.validate()?;
        Ok(config)
    }

    /// Stress one positional diagnostic frame.
    pub fn stress_inject_frame(
        &self,
        channel_names: &[String],
        values: &[f64],
        source_t_ns: u64,
        frame_index: usize,
    ) -> Result<StressedFrame, DiagnosticError> {
        if channel_names.len() != values.len() {
            return Err(DiagnosticError::VectorLengthMismatch {
                expected: channel_names.len(),
                actual: values.len(),
            });
        }
        let mut rng = SplitMix64::new(
            self.seed ^ (((frame_index as u64) + 1).wrapping_mul(FRAME_MIX) & MASK64),
        );
        let mut stressed_values = Vec::with_capacity(values.len());
        let mut noisy_channels = Vec::new();
        let mut dropped_channels = Vec::new();
        for (channel, value) in channel_names.iter().zip(values.iter()) {
            require_finite("diagnostic value", *value)?;
            let channel_config = self.channel_config(channel);
            if channel_config.dropout_probability > 0.0
                && rng.uniform() < channel_config.dropout_probability
            {
                dropped_channels.push(channel.clone());
                stressed_values.push(None);
                continue;
            }
            let mut stressed = *value;
            if channel_config.noise_sigma > 0.0 {
                stressed += rng.normal() * channel_config.noise_sigma;
                require_finite("stressed sample", stressed)?;
                noisy_channels.push(channel.clone());
            }
            stressed_values.push(Some(stressed));
        }
        let jitter_ns = self.jitter_ns(&mut rng);
        let emitted_t_ns = if jitter_ns >= 0 {
            source_t_ns
                .checked_add(jitter_ns as u64)
                .ok_or(DiagnosticError::TimestampOverflow)?
        } else {
            source_t_ns
                .checked_sub(jitter_ns.unsigned_abs())
                .ok_or(DiagnosticError::NegativeEmittedTimestamp)?
        };
        Ok(StressedFrame {
            source_t_ns,
            emitted_t_ns,
            jitter_ns,
            values: stressed_values,
            noisy_channels,
            dropped_channels,
        })
    }

    fn validate(&self) -> Result<(), DiagnosticError> {
        if self.channels.is_empty() {
            return Err(DiagnosticError::EmptyStressChannels);
        }
        if self.jitter_max_ns < self.jitter_min_ns {
            return Err(DiagnosticError::InvalidJitterRange);
        }
        if self.jitter_max_ns > i64::MAX as u64 {
            return Err(DiagnosticError::InvalidJitterRange);
        }
        require_finite("jitter_probability", self.jitter_probability)?;
        if !(0.0..=1.0).contains(&self.jitter_probability) {
            return Err(DiagnosticError::ProbabilityOutOfRange {
                field: "jitter_probability",
            });
        }
        let mut names = HashSet::with_capacity(self.channels.len());
        for channel in &self.channels {
            channel.validate()?;
            if !names.insert(channel.name.clone()) {
                return Err(DiagnosticError::DuplicateChannel {
                    channel: channel.name.clone(),
                });
            }
        }
        Ok(())
    }

    fn channel_config(&self, channel: &str) -> StressChannelConfig {
        self.channels
            .iter()
            .find(|config| config.name == channel)
            .cloned()
            .unwrap_or_else(|| StressChannelConfig {
                name: channel.to_string(),
                noise_sigma: 0.0,
                dropout_probability: 0.0,
            })
    }

    fn jitter_ns(&self, rng: &mut SplitMix64) -> i64 {
        if self.jitter_probability <= 0.0 || rng.uniform() >= self.jitter_probability {
            return 0;
        }
        let span = self.jitter_max_ns - self.jitter_min_ns + 1;
        let magnitude = self.jitter_min_ns + (rng.uniform() * span as f64).floor() as u64;
        let signed_magnitude = magnitude as i64;
        if self.jitter_signed && rng.uniform() < 0.5 {
            -signed_magnitude
        } else {
            signed_magnitude
        }
    }
}

/// Result of stressing one diagnostic frame.
#[derive(Debug, Clone, PartialEq)]
pub struct StressedFrame {
    /// Original source timestamp.
    pub source_t_ns: u64,
    /// Timestamp after jitter.
    pub emitted_t_ns: u64,
    /// Applied jitter in nanoseconds.
    pub jitter_ns: i64,
    /// Stressed channel values; `None` means the channel dropped out.
    pub values: Vec<Option<f64>>,
    /// Channels with additive noise applied.
    pub noisy_channels: Vec<String>,
    /// Channels removed by dropout.
    pub dropped_channels: Vec<String>,
}

#[derive(Debug, Clone)]
struct SplitMix64 {
    state: u64,
}

impl SplitMix64 {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    fn next_u64(&mut self) -> u64 {
        self.state = self.state.wrapping_add(GOLDEN_GAMMA);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    fn uniform(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / ((1_u64 << 53) as f64))
    }

    fn normal(&mut self) -> f64 {
        let u1 = self.uniform().max(1.0e-300);
        let u2 = self.uniform();
        (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
    }
}

/// Fit min/max calibrations from an observation matrix.
pub fn fit_diagnostic_calibrations(
    names: &[String],
    units: &[String],
    observations: &[Vec<f64>],
    clip_policy: ClipPolicy,
    provenance: impl Into<String>,
    aer_addresses: &[Option<usize>],
) -> Result<Vec<DiagnosticChannelCalibration>, DiagnosticError> {
    if names.is_empty() {
        return Err(DiagnosticError::EmptyCalibrations);
    }
    if names.len() != units.len() || names.len() != aer_addresses.len() {
        return Err(DiagnosticError::VectorLengthMismatch {
            expected: names.len(),
            actual: units.len().max(aer_addresses.len()),
        });
    }
    if observations.is_empty() {
        return Err(DiagnosticError::EmptyObservations);
    }
    for row in observations {
        if row.len() != names.len() {
            return Err(DiagnosticError::VectorLengthMismatch {
                expected: names.len(),
                actual: row.len(),
            });
        }
    }
    let provenance = provenance.into();
    require_non_empty("provenance", &provenance)?;
    let mut calibrations = Vec::with_capacity(names.len());
    for index in 0..names.len() {
        let mut min_value = f64::INFINITY;
        let mut max_value = f64::NEG_INFINITY;
        for row in observations {
            let value = row[index];
            require_finite("observation", value)?;
            min_value = min_value.min(value);
            max_value = max_value.max(value);
        }
        if min_value == max_value {
            return Err(DiagnosticError::ZeroCalibrationSpan {
                channel: names[index].clone(),
            });
        }
        calibrations.push(DiagnosticChannelCalibration::new(
            names[index].clone(),
            units[index].clone(),
            min_value,
            max_value,
            clip_policy,
            provenance.clone(),
            aer_addresses[index],
        )?);
    }
    Ok(calibrations)
}

/// Errors raised by the diagnostic normalisation crate.
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum DiagnosticError {
    /// A string field was empty.
    #[error("{field} must be non-empty")]
    EmptyField {
        /// Field name.
        field: &'static str,
    },
    /// A floating field was not finite.
    #[error("{field} must be finite")]
    NonFinite {
        /// Field name.
        field: &'static str,
    },
    /// The configured physical interval is invalid.
    #[error("physical_max must be greater than physical_min")]
    InvalidRange,
    /// Clip policy identifier is unknown.
    #[error("clip_policy must be one of: clip, reject")]
    UnknownClipPolicy,
    /// At least one calibration is required.
    #[error("at least one calibration is required")]
    EmptyCalibrations,
    /// At least one observation is required for fitting.
    #[error("at least one observation is required")]
    EmptyObservations,
    /// A positive integer field was zero.
    #[error("{field} must be positive")]
    NonPositive {
        /// Field name.
        field: &'static str,
    },
    /// A floating field was negative where only non-negative values are valid.
    #[error("{field} must be non-negative")]
    Negative {
        /// Field name.
        field: &'static str,
    },
    /// A probability field was outside `[0, 1]`.
    #[error("{field} must lie in [0, 1]")]
    ProbabilityOutOfRange {
        /// Field name.
        field: &'static str,
    },
    /// At least one stress channel is required.
    #[error("at least one stress channel is required")]
    EmptyStressChannels,
    /// The configured jitter interval is invalid.
    #[error("jitter max_ns must be greater than or equal to min_ns")]
    InvalidJitterRange,
    /// Timestamp arithmetic overflowed while applying jitter.
    #[error("emitted timestamp overflowed while applying jitter")]
    TimestampOverflow,
    /// Signed jitter moved an emitted timestamp below zero.
    #[error("emitted timestamp must be non-negative")]
    NegativeEmittedTimestamp,
    /// Calibration channel names must be unique.
    #[error("duplicate calibration channel: {channel}")]
    DuplicateChannel {
        /// Duplicated channel name.
        channel: String,
    },
    /// The supplied vector length does not match the calibration count.
    #[error("value vector length must match calibration count: expected {expected}, got {actual}")]
    VectorLengthMismatch {
        /// Expected item count.
        expected: usize,
        /// Actual item count.
        actual: usize,
    },
    /// A reject-policy sample fell below the calibrated interval.
    #[error("{channel} sample below calibrated range")]
    BelowRange {
        /// Channel name.
        channel: String,
    },
    /// A reject-policy sample exceeded the calibrated interval.
    #[error("{channel} sample above calibrated range")]
    AboveRange {
        /// Channel name.
        channel: String,
    },
    /// A fitted channel has no physical span.
    #[error("{channel} has zero calibration span")]
    ZeroCalibrationSpan {
        /// Channel name.
        channel: String,
    },
}

fn require_non_empty(field: &'static str, value: &str) -> Result<(), DiagnosticError> {
    if value.trim().is_empty() {
        Err(DiagnosticError::EmptyField { field })
    } else {
        Ok(())
    }
}

fn require_finite(field: &'static str, value: f64) -> Result<(), DiagnosticError> {
    if value.is_finite() {
        Ok(())
    } else {
        Err(DiagnosticError::NonFinite { field })
    }
}

fn clamp_unit(value: f64) -> f64 {
    value.clamp(-1.0, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_state() -> DiagnosticNormalisationState {
        DiagnosticNormalisationState::new(
            vec![
                DiagnosticChannelCalibration::new(
                    "temperature_eV",
                    "eV",
                    0.0,
                    1000.0,
                    ClipPolicy::Clip,
                    "thermal calibration",
                    Some(0),
                )
                .expect("valid calibration"),
                DiagnosticChannelCalibration::new(
                    "bdot_V",
                    "V",
                    -10.0,
                    10.0,
                    ClipPolicy::Clip,
                    "B-dot calibration",
                    Some(1),
                )
                .expect("valid calibration"),
            ],
            Some(50),
        )
        .expect("valid state")
    }

    #[test]
    fn affine_mapping_matches_fixture() {
        let report = fixture_state()
            .normalise_features(&[500.0, -5.0])
            .expect("normalised vector");
        assert_eq!(report.features, vec![0.0, -0.5]);
        assert_eq!(report.clip_mask, vec![false, false]);
        assert_eq!(report.out_of_range_channels, Vec::<String>::new());
    }

    #[test]
    fn clipping_is_bounded_and_reported() {
        let report = fixture_state()
            .normalise_features(&[1200.0, -20.0])
            .expect("normalised vector");
        assert_eq!(report.features, vec![1.0, -1.0]);
        assert_eq!(report.clip_mask, vec![true, true]);
        assert_eq!(
            report.out_of_range_channels,
            vec!["temperature_eV".to_string(), "bdot_V".to_string()]
        );
    }

    #[test]
    fn reject_policy_raises() {
        let calibration = DiagnosticChannelCalibration::new(
            "temperature_eV",
            "eV",
            0.0,
            1000.0,
            ClipPolicy::Reject,
            "thermal calibration",
            None,
        )
        .expect("valid calibration");
        let state =
            DiagnosticNormalisationState::new(vec![calibration], None).expect("valid state");
        assert!(matches!(
            state.normalise_features(&[1200.0]),
            Err(DiagnosticError::AboveRange { .. })
        ));
    }

    #[test]
    fn rejects_non_finite_affine_span() {
        assert!(matches!(
            DiagnosticChannelCalibration::new(
                "wide_field_T",
                "T",
                -1.0e308,
                1.0e308,
                ClipPolicy::Clip,
                "wide range calibration",
                None,
            ),
            Err(DiagnosticError::NonFinite {
                field: "affine span"
            })
        ));
    }

    #[test]
    fn large_same_sign_range_uses_stable_midpoint() {
        let calibration = DiagnosticChannelCalibration::new(
            "dense_plasma_m3",
            "m^-3",
            1.0e308,
            1.2e308,
            ClipPolicy::Clip,
            "large finite range calibration",
            None,
        )
        .expect("valid calibration");

        assert!(calibration.offset().is_finite());
        assert_eq!(
            calibration.offset(),
            calibration.physical_min + 0.5 * (calibration.physical_max - calibration.physical_min)
        );
        let (normalised, clipped) = calibration
            .normalise_value(1.1e308)
            .expect("normalised value");
        assert!(normalised.abs() <= 1.0e-12);
        assert!(!clipped);
    }

    #[test]
    fn fit_calibrations_preserves_order() {
        let calibrations = fit_diagnostic_calibrations(
            &["temperature_eV".to_string(), "density_m3".to_string()],
            &["eV".to_string(), "m^-3".to_string()],
            &[vec![100.0, 1.0e20], vec![900.0, 5.0e21]],
            ClipPolicy::Clip,
            "shot sweep",
            &[Some(0), Some(1)],
        )
        .expect("fit");
        assert_eq!(calibrations[0].name, "temperature_eV");
        assert_eq!(calibrations[0].physical_min, 100.0);
        assert_eq!(calibrations[0].physical_max, 900.0);
    }

    #[test]
    fn stress_injection_is_deterministic_and_logged() {
        let config = StressInjectionConfig::new(
            7,
            vec![
                StressChannelConfig::new("temperature_eV", 10.0, 0.0).expect("valid channel"),
                StressChannelConfig::new("bdot_V", 0.5, 1.0).expect("valid channel"),
            ],
            10,
            50,
            1.0,
            true,
        )
        .expect("valid config");
        let names = vec!["temperature_eV".to_string(), "bdot_V".to_string()];
        let first = config
            .stress_inject_frame(&names, &[500.0, 0.0], 1_000, 0)
            .expect("stress frame");
        let second = config
            .stress_inject_frame(&names, &[500.0, 0.0], 1_000, 0)
            .expect("stress frame");
        assert_eq!(first, second);
        assert!((10..=50).contains(&first.jitter_ns.abs()));
        assert_eq!(
            first.emitted_t_ns as i64 - first.source_t_ns as i64,
            first.jitter_ns
        );
        assert_eq!(first.dropped_channels, vec!["bdot_V".to_string()]);
        assert_eq!(first.noisy_channels, vec!["temperature_eV".to_string()]);
        assert!(first.values[0].is_some());
        assert_eq!(first.values[1], None);
    }

    #[test]
    fn stress_injection_rejects_non_finite_stressed_values() {
        let config = StressInjectionConfig::new(
            3,
            vec![StressChannelConfig::new("temperature_eV", 1.0e308, 0.0).expect("valid channel")],
            0,
            0,
            0.0,
            false,
        )
        .expect("valid config");
        assert!(matches!(
            config.stress_inject_frame(&["temperature_eV".to_string()], &[1.0e308], 1_000, 0),
            Err(DiagnosticError::NonFinite {
                field: "stressed sample"
            })
        ));
    }

    #[test]
    fn stress_injection_rejects_bad_envelopes() {
        assert!(matches!(
            StressChannelConfig::new("temperature_eV", -1.0, 0.0),
            Err(DiagnosticError::Negative { .. })
        ));
        assert!(matches!(
            StressChannelConfig::new("temperature_eV", 1.0, 1.2),
            Err(DiagnosticError::ProbabilityOutOfRange { .. })
        ));
        assert!(matches!(
            StressInjectionConfig::new(
                1,
                vec![StressChannelConfig::new("temperature_eV", 1.0, 0.0).expect("valid channel")],
                50,
                10,
                1.0,
                true,
            ),
            Err(DiagnosticError::InvalidJitterRange)
        ));
    }
}
