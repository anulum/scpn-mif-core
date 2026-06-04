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
//! overflowing feature vector.

#![forbid(unsafe_code)]
#![deny(missing_docs, rustdoc::broken_intra_doc_links)]

use std::{collections::HashSet, str::FromStr};

use thiserror::Error;

/// Crate version derived from the workspace.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

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
        0.5 * (self.physical_min + self.physical_max)
    }

    /// Multiplicative factor from physical units into `[-1, 1]`.
    pub fn scale(&self) -> f64 {
        2.0 / (self.physical_max - self.physical_min)
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
}
