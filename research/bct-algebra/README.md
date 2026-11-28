# BCT Algebra Core v0.1 (research)

This crate is the first executable algebraic research component for AVA. It is separate from the Python provenance/reader infrastructure and the proposed Rust bct-memory storage crate.

## Contract

- A strand is (D, M, E, T): payload digest, provenance digest, evidence digest, and explicit trust state.
- A bounded context is Gamma = (policy, schema, actor, request, dependencies, logical_time).
- The algebraic generator is the Artin braid generator sigma_i, represented by its action on a free group. This preserves pure-braid information that a plain swap loses.
- CrossingPurpose::{Integrity, Provenance, Authority} labels the gate associated with an event. It does not pretend three different validators are one Yang-Baxter operator.
- Trust is data, not an automatic side effect. This crate never promotes a strand to VERIFIED or CERTIFIED.
- TES hashes policy-bound semantic state and the Artin representation. ETH hashes the exact ordered crossing trace.

## Mathematical boundary

The intended defining relations are far commutation, the adjacent Artin/Yang-Baxter relation, and generator/inverse cancellation. Tests exercise concrete bounded states. They are executable checks, not a formal proof of implementation correctness or detector soundness.

## Explicit non-claims

No cryptographic provenance verification, signature/key custody, authority policy evaluation, factual truth detection, cognitive reasoning, learning, OASIS lifecycle integration, or production memory admission is implemented. Hash agreement proves equality of the hashed representation, not factual truth. No superintelligence claim follows from algebraic consistency.

## Run

~~~sh
cargo test --manifest-path research/bct-algebra/Cargo.toml
~~~
