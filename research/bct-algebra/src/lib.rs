//! BCT algebra research core.
//!
//! Implements a bounded Artin braid-group action through the Artin action on
//! a free group. Integrity, provenance, and authority checks are admission
//! predicates surrounding a crossing, not interchangeable braid generators.

use std::collections::HashSet;
use thiserror::Error;

const MAX_STRANDS: usize = 32;
const MAX_DEPENDENCIES: usize = 64;
const MAX_CONTEXT_TEXT: usize = 128;
const MAX_TRACE_EVENTS: usize = 16_384;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TrustState { Untrusted, Proposed, Verified, Certified, Quarantined, Rejected }

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Strand {
    pub id: u32,
    pub payload_digest: [u8; 32],
    pub provenance_digest: [u8; 32],
    pub evidence_digest: [u8; 32],
    pub trust: TrustState,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CrossingContext {
    pub policy_id: String,
    pub schema_id: String,
    pub actor_id: String,
    pub request_id: String,
    pub dependencies: Vec<[u8; 32]>,
    /// Bounded dispatcher c_Gamma(i): one gate purpose per adjacent generator.
    pub purpose_by_generator: Vec<CrossingPurpose>,
    /// Fixed logical time. Wall-clock reads are excluded from the pure core.
    pub logical_time: u64,
}

impl CrossingContext {
    fn validate(&self) -> Result<(), BctError> {
        for (name, value) in [
            ("policy_id", &self.policy_id), ("schema_id", &self.schema_id),
            ("actor_id", &self.actor_id), ("request_id", &self.request_id),
        ] {
            if value.is_empty() || value.len() > MAX_CONTEXT_TEXT {
                return Err(BctError::InvalidContext(name));
            }
        }
        if self.dependencies.len() > MAX_DEPENDENCIES { return Err(BctError::DependencyLimit); }
        if self.purpose_by_generator.is_empty() || self.purpose_by_generator.len() > MAX_STRANDS - 1 {
            return Err(BctError::InvalidContext("purpose_by_generator"));
        }
        Ok(())
    }

    fn digest(&self) -> [u8; 32] {
        let mut bytes = Vec::new();
        for value in [&self.policy_id, &self.schema_id, &self.actor_id, &self.request_id] {
            bytes.extend_from_slice(&(value.len() as u32).to_be_bytes());
            bytes.extend_from_slice(value.as_bytes());
        }
        bytes.extend_from_slice(&self.logical_time.to_be_bytes());
        bytes.extend_from_slice(&(self.dependencies.len() as u32).to_be_bytes());
        for dependency in &self.dependencies { bytes.extend_from_slice(dependency); }
        for purpose in &self.purpose_by_generator {
            bytes.push(match purpose {
                CrossingPurpose::Integrity => 1, CrossingPurpose::Provenance => 2,
                CrossingPurpose::Authority => 3,
            });
        }
        *blake3::hash(&bytes).as_bytes()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CrossingPurpose { Integrity, Provenance, Authority }

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CrossingEvent {
    pub generator: usize,
    pub inverse: bool,
    pub purpose: CrossingPurpose,
    pub context_digest: [u8; 32],
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum BctError {
    #[error("strand count must be between 2 and 32")] StrandCount,
    #[error("duplicate strand identifier {0}")] DuplicateStrand(u32),
    #[error("generator index {index} is outside valid range for {strand_count} strands")]
    GeneratorOutOfRange { index: usize, strand_count: usize },
    #[error("invalid crossing context field: {0}")] InvalidContext(&'static str),
    #[error("crossing context dependency limit exceeded")] DependencyLimit,
    #[error("crossing trace limit exceeded")] TraceLimit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct FreeWord(Vec<i32>);

impl FreeWord {
    fn push_reduced(out: &mut Vec<i32>, letter: i32) {
        if out.last().copied() == Some(-letter) { out.pop(); } else { out.push(letter); }
    }

    fn substitute(&self, images: &[FreeWord]) -> Self {
        let mut out = Vec::new();
        for letter in &self.0 {
            let image = &images[letter.unsigned_abs() as usize - 1];
            if *letter > 0 {
                for item in &image.0 { Self::push_reduced(&mut out, *item); }
            } else {
                for item in image.0.iter().rev() { Self::push_reduced(&mut out, -*item); }
            }
        }
        Self(out)
    }
}

/// Endpoint strand order plus a faithful Artin representation. The latter
/// preserves pure-braid information that a simple swap/permutation loses.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BraidState {
    strands: Vec<Strand>,
    artin_images: Vec<FreeWord>,
    trace: Vec<CrossingEvent>,
}

impl BraidState {
    pub fn new(strands: Vec<Strand>) -> Result<Self, BctError> {
        if !(2..=MAX_STRANDS).contains(&strands.len()) { return Err(BctError::StrandCount); }
        let mut ids = HashSet::new();
        for strand in &strands {
            if !ids.insert(strand.id) { return Err(BctError::DuplicateStrand(strand.id)); }
        }
        let artin_images = (1..=strands.len())
            .map(|generator| FreeWord(vec![generator as i32])).collect();
        Ok(Self { strands, artin_images, trace: Vec::new() })
    }

    pub fn strands(&self) -> &[Strand] { &self.strands }
    pub fn trace(&self) -> &[CrossingEvent] { &self.trace }

    /// Apply sigma_i or sigma_i^-1. The index is zero-based.
    /// Positive: x_i -> x_i*x_(i+1)*x_i^-1; x_(i+1) -> x_i.
    /// Negative: x_i -> x_(i+1); x_(i+1) -> x_(i+1)^-1*x_i*x_(i+1).
    pub fn cross(
        &mut self, index: usize, inverse: bool, purpose: CrossingPurpose,
        context: &CrossingContext,
    ) -> Result<(), BctError> {
        context.validate()?;
        if index + 1 >= self.strands.len() {
            return Err(BctError::GeneratorOutOfRange { index, strand_count: self.strands.len() });
        }
        if index >= context.purpose_by_generator.len() {
            return Err(BctError::InvalidContext("purpose_by_generator"));
        }
        if self.trace.len() >= MAX_TRACE_EVENTS { return Err(BctError::TraceLimit); }
        let purpose = context.purpose_by_generator[index];

        let left = index as i32 + 1;
        let right = left + 1;
        let pair = if inverse {
            [FreeWord(vec![right]), FreeWord(vec![-right, left, right])]
        } else {
            [FreeWord(vec![left, right, -left]), FreeWord(vec![left])]
        };
        let substitution: Vec<FreeWord> = (1..=self.strands.len()).map(|g| {
            if g == index + 1 { pair[0].clone() }
            else if g == index + 2 { pair[1].clone() }
            else { FreeWord(vec![g as i32]) }
        }).collect();
        self.artin_images = self.artin_images.iter()
            .map(|word| word.substitute(&substitution)).collect();
        self.strands.swap(index, index + 1);
        self.trace.push(CrossingEvent {
            generator: index, inverse, purpose, context_digest: context.digest(),
        });
        Ok(())
    }

    /// Policy-bound semantic state and Artin image; excludes exact event history.
    pub fn tes_digest(&self, policy_id: &str) -> [u8; 32] {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&(policy_id.len() as u32).to_be_bytes());
        bytes.extend_from_slice(policy_id.as_bytes());
        for strand in &self.strands {
            bytes.extend_from_slice(&strand.id.to_be_bytes());
            bytes.extend_from_slice(&strand.payload_digest);
            bytes.extend_from_slice(&strand.provenance_digest);
            bytes.extend_from_slice(&strand.evidence_digest);
            bytes.push(trust_tag(strand.trust));
        }
        for image in &self.artin_images {
            bytes.extend_from_slice(&(image.0.len() as u32).to_be_bytes());
            for letter in &image.0 { bytes.extend_from_slice(&letter.to_be_bytes()); }
        }
        *blake3::hash(&bytes).as_bytes()
    }

    /// Exact ordered event-history digest.
    pub fn eth_digest(&self) -> [u8; 32] {
        let mut bytes = Vec::new();
        for event in &self.trace {
            bytes.extend_from_slice(&(event.generator as u64).to_be_bytes());
            bytes.push(u8::from(event.inverse));
            bytes.push(match event.purpose {
                CrossingPurpose::Integrity => 1, CrossingPurpose::Provenance => 2,
                CrossingPurpose::Authority => 3,
            });
            bytes.extend_from_slice(&event.context_digest);
        }
        *blake3::hash(&bytes).as_bytes()
    }

    pub fn topologically_equivalent(&self, other: &Self) -> bool {
        self.strands == other.strands && self.artin_images == other.artin_images
    }
}

fn trust_tag(trust: TrustState) -> u8 {
    match trust {
        TrustState::Untrusted => 0, TrustState::Proposed => 1, TrustState::Verified => 2,
        TrustState::Certified => 3, TrustState::Quarantined => 4, TrustState::Rejected => 5,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn context() -> CrossingContext {
        CrossingContext {
            policy_id: "policy-v1".into(), schema_id: "strand-v1".into(),
            actor_id: "test-actor".into(), request_id: "test-request".into(),
            dependencies: vec![], purpose_by_generator: vec![CrossingPurpose::Integrity; MAX_STRANDS - 1],
            logical_time: 42,
        }
    }
    fn state(n: usize) -> BraidState {
        BraidState::new((0..n).map(|id| Strand {
            id: id as u32, payload_digest: [id as u8; 32],
            provenance_digest: [1; 32], evidence_digest: [2; 32],
            trust: TrustState::Proposed,
        }).collect()).unwrap()
    }
    fn word(s: &mut BraidState, operations: &[(usize, bool)]) {
        for (i, inverse) in operations {
            s.cross(*i, *inverse, &context()).unwrap();
        }
    }

    #[test]
    fn yang_baxter_relation_holds_on_three_strands() {
        let (mut left, mut right) = (state(3), state(3));
        word(&mut left, &[(0,false),(1,false),(0,false)]);
        word(&mut right, &[(1,false),(0,false),(1,false)]);
        assert!(left.topologically_equivalent(&right));
        assert_eq!(left.tes_digest("policy-v1"), right.tes_digest("policy-v1"));
        assert_ne!(left.eth_digest(), right.eth_digest());
    }
    #[test]
    fn distant_generators_commute() {
        let (mut left, mut right) = (state(4), state(4));
        word(&mut left, &[(0,false),(2,false)]);
        word(&mut right, &[(2,false),(0,false)]);
        assert!(left.topologically_equivalent(&right));
        assert_ne!(left.eth_digest(), right.eth_digest());
    }
    #[test]
    fn generator_and_inverse_cancel() {
        let (mut s, original) = (state(3), state(3));
        word(&mut s, &[(1,false),(1,true)]);
        assert!(s.topologically_equivalent(&original));
    }
    #[test]
    fn pure_braid_is_not_collapsed_to_endpoint_permutation() {
        let mut s = state(3);
        word(&mut s, &[(0,false),(0,false)]);
        let identity = state(3);
        assert_eq!(s.strands(), identity.strands());
        assert_ne!(s.tes_digest("policy-v1"), identity.tes_digest("policy-v1"));
    }
    #[test]
    fn bounds_are_enforced() {
        let mut s = state(2);
        assert!(matches!(s.cross(1,false,CrossingPurpose::Integrity,&context()),
            Err(BctError::GeneratorOutOfRange { .. })));
        let mut ctx = context();
        ctx.dependencies = vec![[0;32]; MAX_DEPENDENCIES + 1];
        assert_eq!(s.cross(0,false,CrossingPurpose::Integrity,&ctx), Err(BctError::DependencyLimit));
    }
    #[test]
    fn duplicate_ids_are_rejected() {
        let mut strands = state(2).strands;
        strands[1].id = strands[0].id;
        assert_eq!(BraidState::new(strands), Err(BctError::DuplicateStrand(0)));
    }
    #[test]
    fn purpose_is_bound_into_exact_trace_not_topology() {
        let (mut a, mut b) = (state(2), state(2));
        a.cross(0,false,&context()).unwrap();
        let mut provenance_context = context();
        provenance_context.purpose_by_generator[0] = CrossingPurpose::Provenance;
        b.cross(0,false,&provenance_context).unwrap();
        assert_ne!(a.eth_digest(), b.eth_digest());
        assert_eq!(a.tes_digest("policy-v1"), b.tes_digest("policy-v1"));
    }
}
