//! Custom assertions for tests
//!
//! Provides domain-specific assertion helpers

/// Assert that a value is within a tolerance
pub fn assert_approx_eq(actual: f32, expected: f32, tolerance: f32) {
    let diff = (actual - expected).abs();
    assert!(
        diff <= tolerance,
        "Values not approximately equal: {} vs {} (diff: {}, tolerance: {})",
        actual,
        expected,
        diff,
        tolerance
    );
}

/// Assert that a similarity score is valid (0.0 to 1.0)
pub fn assert_valid_similarity(score: f32) {
    assert!(
        (0.0..=1.0).contains(&score),
        "Similarity score {} is not in valid range [0.0, 1.0]",
        score
    );
}

/// Assert that an embedding has the correct dimensions
pub fn assert_valid_embedding(embedding: &[f32], expected_dims: usize) {
    assert_eq!(
        embedding.len(),
        expected_dims,
        "Embedding has {} dimensions, expected {}",
        embedding.len(),
        expected_dims
    );

    // Check that it's not all zeros
    let sum: f32 = embedding.iter().sum();
    assert!(
        sum.abs() > 0.0001,
        "Embedding appears to be all zeros"
    );
}

/// Assert that a job status is one of the expected states
pub fn assert_job_status_in(actual: &str, expected_states: &[&str]) {
    assert!(
        expected_states.contains(&actual),
        "Job status '{}' is not in expected states: {:?}",
        actual,
        expected_states
    );
}

/// Assert that code analysis found expected number of issues
pub fn assert_issue_count(actual: usize, expected_min: usize, expected_max: usize) {
    assert!(
        actual >= expected_min && actual <= expected_max,
        "Found {} issues, expected between {} and {}",
        actual,
        expected_min,
        expected_max
    );
}

/// Assert that a duration is within acceptable bounds
pub fn assert_duration_within(actual: std::time::Duration, max: std::time::Duration) {
    assert!(
        actual <= max,
        "Duration {:?} exceeded maximum {:?}",
        actual,
        max
    );
}

/// Assert that a string contains a substring
pub fn assert_contains(haystack: &str, needle: &str) {
    assert!(
        haystack.contains(needle),
        "String does not contain expected substring.\nHaystack: {}\nNeedle: {}",
        haystack,
        needle
    );
}

/// Assert that a JSON value has a specific field
pub fn assert_json_field_exists(value: &serde_json::Value, field: &str) {
    assert!(
        value.get(field).is_some(),
        "JSON value does not contain field '{}'.\nJSON: {}",
        field,
        serde_json::to_string_pretty(value).unwrap_or_else(|_| "Invalid JSON".to_string())
    );
}

/// Assert that a result is an error
pub fn assert_is_error<T, E>(result: &Result<T, E>) {
    assert!(result.is_err(), "Expected error, got Ok");
}

/// Assert that a result is ok
pub fn assert_is_ok<T, E: std::fmt::Debug>(result: &Result<T, E>) {
    assert!(result.is_ok(), "Expected Ok, got Err: {:?}", result);
}
