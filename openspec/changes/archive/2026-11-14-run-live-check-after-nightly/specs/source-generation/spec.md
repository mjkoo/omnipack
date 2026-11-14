# Spec Delta

## REMOVED Requirements

### Requirement: The daily source catalog workflow checks that pack projects answer

**Reason**: The live check now runs after each nightly publishing run in a workflow of its own and shares nothing with source generation.

**Migration**: Replaced by the requirements "A live check runs after each nightly publish", "The live check job holds only read access", "The live check reports its outcome in the run", "The live check's verdict follows reachability, not health" and "The live check raises findings through its own alert job" in nightly-publishing.
