use coderabbit_api_gateway::handlers::issue_filtering::apply_repo_config_to_filter;
/// Integration test for issue ranking and filtering system
use coderabbit_shared::{IssueCategory, IssueFilter, IssueSeverity, RankedIssue, RepoConfig};

#[test]
fn test_issue_severity_ordering() {
    let mut issues = vec![
        create_issue("1", IssueSeverity::Info, IssueCategory::Documentation),
        create_issue("2", IssueSeverity::Critical, IssueCategory::Security),
        create_issue("3", IssueSeverity::Warning, IssueCategory::Style),
        create_issue("4", IssueSeverity::Error, IssueCategory::BugRisk),
    ];

    issues.sort();

    // Should be ordered by priority: Critical > Error > Warning > Info
    assert_eq!(issues[0].id, "2"); // Critical security
    assert_eq!(issues[1].id, "4"); // Error bug-risk
    assert_eq!(issues[2].id, "3"); // Warning style
    assert_eq!(issues[3].id, "1"); // Info documentation

    println!("✅ Issues correctly sorted by priority:");
    for (i, issue) in issues.iter().enumerate() {
        println!(
            "   {}. {} {} - {} (priority: {})",
            i + 1,
            issue.severity.emoji(),
            issue.severity,
            issue.title,
            issue.priority_score
        );
    }
}

#[test]
fn test_filter_by_minimum_severity() {
    let issues = vec![
        create_issue("1", IssueSeverity::Debug, IssueCategory::Style),
        create_issue("2", IssueSeverity::Info, IssueCategory::Documentation),
        create_issue("3", IssueSeverity::Warning, IssueCategory::Performance),
        create_issue("4", IssueSeverity::Error, IssueCategory::Security),
        create_issue("5", IssueSeverity::Critical, IssueCategory::Security),
    ];

    println!("\n📊 Testing minimum severity filter");
    println!("   Total issues: {}", issues.len());

    // Filter for warning and above
    let filter = IssueFilter::with_min_severity(IssueSeverity::Warning);
    let filtered = filter.apply(issues.clone());

    println!("   After filtering (min: warning): {}", filtered.len());
    assert_eq!(filtered.len(), 3); // Warning, Error, Critical

    // Should only have warning, error, and critical
    for issue in &filtered {
        assert!(issue.severity >= IssueSeverity::Warning);
        println!("   - {} {}", issue.severity.emoji(), issue.severity);
    }

    // Filter for error and above
    let filter = IssueFilter::with_min_severity(IssueSeverity::Error);
    let filtered = filter.apply(issues);

    println!("   After filtering (min: error): {}", filtered.len());
    assert_eq!(filtered.len(), 2); // Error, Critical
}

#[test]
fn test_filter_by_category() {
    let issues = vec![
        create_issue("1", IssueSeverity::Error, IssueCategory::Security),
        create_issue("2", IssueSeverity::Warning, IssueCategory::Performance),
        create_issue("3", IssueSeverity::Warning, IssueCategory::Style),
        create_issue("4", IssueSeverity::Error, IssueCategory::BugRisk),
    ];

    println!("\n🏷️  Testing category filtering");

    // Block style issues
    let mut filter = IssueFilter::default();
    filter.blocked_categories = vec![IssueCategory::Style];

    let filtered = filter.apply(issues.clone());

    println!("   Blocked 'style' category");
    println!("   Remaining: {}", filtered.len());
    assert_eq!(filtered.len(), 3);
    assert!(!filtered
        .iter()
        .any(|i| matches!(i.category, IssueCategory::Style)));

    // Allow only security and bug-risk
    let mut filter = IssueFilter::default();
    filter.allowed_categories = vec![IssueCategory::Security, IssueCategory::BugRisk];

    let filtered = filter.apply(issues);

    println!("   Allowed only 'security' and 'bug-risk'");
    println!("   Remaining: {}", filtered.len());
    assert_eq!(filtered.len(), 2);
}

#[test]
fn test_filter_max_issues() {
    let mut issues = vec![];
    for i in 1..=20 {
        issues.push(create_issue(
            &i.to_string(),
            IssueSeverity::Warning,
            IssueCategory::BestPractices,
        ));
    }

    println!("\n🔢 Testing max issues limit");
    println!("   Total issues: {}", issues.len());

    let mut filter = IssueFilter::default();
    filter.max_issues = Some(10);

    let filtered = filter.apply(issues);

    println!("   After limiting to 10: {}", filtered.len());
    assert_eq!(filtered.len(), 10);
}

#[test]
fn test_filter_confidence_threshold() {
    let mut issues = vec![
        create_issue_with_confidence("1", IssueSeverity::Error, IssueCategory::Security, 0.95),
        create_issue_with_confidence("2", IssueSeverity::Error, IssueCategory::Security, 0.75),
        create_issue_with_confidence("3", IssueSeverity::Error, IssueCategory::Security, 0.50),
        create_issue_with_confidence("4", IssueSeverity::Error, IssueCategory::Security, 0.30),
    ];

    println!("\n🎯 Testing confidence threshold");

    let mut filter = IssueFilter::default();
    filter.min_confidence = Some(0.70);

    let filtered = filter.apply(issues);

    println!("   Min confidence: 0.70");
    println!("   Filtered count: {}", filtered.len());
    assert_eq!(filtered.len(), 2); // 0.95 and 0.75

    for issue in &filtered {
        println!("   - Confidence: {:.2}", issue.confidence);
        assert!(issue.confidence >= 0.70);
    }
}

#[test]
fn test_repo_config_integration() {
    let mut config = RepoConfig::default();
    config.reviews.min_severity = "error".to_string();
    config.reviews.max_comments = 15;
    config.rules.disabled = vec!["style".to_string(), "documentation".to_string()];
    config.rules.enabled = vec![
        "security".to_string(),
        "bug-risk".to_string(),
        "performance".to_string(),
    ];

    println!("\n⚙️  Testing repository config integration");
    println!("   Config min severity: {}", config.reviews.min_severity);
    println!("   Config max comments: {}", config.reviews.max_comments);
    println!("   Disabled categories: {:?}", config.rules.disabled);
    println!("   Enabled categories: {:?}", config.rules.enabled);

    let mut filter = IssueFilter::default();
    apply_repo_config_to_filter(&mut filter, &config, None);

    println!("\n   Applied filter:");
    println!("   - Min severity: {:?}", filter.min_severity);
    println!("   - Max issues: {:?}", filter.max_issues);
    println!(
        "   - Blocked categories: {} items",
        filter.blocked_categories.len()
    );
    println!(
        "   - Allowed categories: {} items",
        filter.allowed_categories.len()
    );

    // Check that config was applied correctly
    assert_eq!(filter.min_severity, Some(IssueSeverity::Error));
    assert_eq!(filter.max_issues, Some(15));
    assert!(filter.blocked_categories.contains(&IssueCategory::Style));
    assert!(filter.allowed_categories.contains(&IssueCategory::Security));
}

#[test]
fn test_priority_calculation() {
    println!("\n📈 Testing priority calculation");

    // Critical security should have highest priority
    let critical_security = create_issue("1", IssueSeverity::Critical, IssueCategory::Security);
    println!("   Critical Security: {}", critical_security.priority_score);
    assert_eq!(critical_security.priority_score, 500); // (4*100) + 100

    // Error bug-risk should be high but less than critical security
    let error_bug = create_issue("2", IssueSeverity::Error, IssueCategory::BugRisk);
    println!("   Error Bug-Risk: {}", error_bug.priority_score);
    assert_eq!(error_bug.priority_score, 390); // (3*100) + 90

    // Info style should have low priority
    let info_style = create_issue("3", IssueSeverity::Info, IssueCategory::Style);
    println!("   Info Style: {}", info_style.priority_score);
    assert_eq!(info_style.priority_score, 110); // (1*100) + 10

    // Test with confidence multiplier
    let low_confidence =
        create_issue_with_confidence("4", IssueSeverity::Critical, IssueCategory::Security, 0.5);
    println!(
        "   Critical Security (50% confidence): {}",
        low_confidence.priority_score
    );
    assert_eq!(low_confidence.priority_score, 250); // 500 * 0.5
}

#[test]
fn test_complete_filtering_workflow() {
    println!("\n🔄 Testing complete filtering workflow");

    // Create a realistic set of issues
    let issues = vec![
        create_issue("1", IssueSeverity::Critical, IssueCategory::Security),
        create_issue("2", IssueSeverity::Critical, IssueCategory::Security),
        create_issue("3", IssueSeverity::Error, IssueCategory::BugRisk),
        create_issue("4", IssueSeverity::Error, IssueCategory::Performance),
        create_issue("5", IssueSeverity::Warning, IssueCategory::BestPractices),
        create_issue("6", IssueSeverity::Warning, IssueCategory::Maintainability),
        create_issue("7", IssueSeverity::Info, IssueCategory::Documentation),
        create_issue("8", IssueSeverity::Info, IssueCategory::Style),
        create_issue(
            "9",
            IssueSeverity::Debug,
            IssueCategory::Other("test".to_string()),
        ),
    ];

    println!("   Initial issues: {}", issues.len());

    // Apply typical production filter
    let mut filter = IssueFilter::with_min_severity(IssueSeverity::Warning);
    filter.max_issues = Some(5);
    filter.blocked_categories = vec![IssueCategory::Style];

    let filtered = filter.apply(issues);

    println!("   After filtering:");
    println!("   - Total: {}", filtered.len());
    assert!(filtered.len() <= 5);

    println!("   - Top issues:");
    for (i, issue) in filtered.iter().enumerate() {
        println!(
            "     {}. {} {:?} - Priority: {}",
            i + 1,
            issue.severity.emoji(),
            issue.category,
            issue.priority_score
        );

        // All should be warning or above
        assert!(issue.severity >= IssueSeverity::Warning);

        // No style issues
        assert!(issue.category != IssueCategory::Style);
    }

    // First issue should be highest priority (Critical Security)
    assert_eq!(filtered[0].severity, IssueSeverity::Critical);
    assert!(matches!(filtered[0].category, IssueCategory::Security));
}

// Helper functions

fn create_issue(id: &str, severity: IssueSeverity, category: IssueCategory) -> RankedIssue {
    RankedIssue::new(
        id.to_string(),
        severity,
        category,
        format!("Test issue {}", id),
        "Test description".to_string(),
        "test.rs".to_string(),
    )
}

fn create_issue_with_confidence(
    id: &str,
    severity: IssueSeverity,
    category: IssueCategory,
    confidence: f32,
) -> RankedIssue {
    let mut issue = create_issue(id, severity, category);
    issue.confidence = confidence;
    issue.recalculate_priority();
    issue
}
