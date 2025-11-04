/// Integration test for the .coderabbit.yaml configuration loader
use coderabbit_api_gateway::services::ConfigLoader;
use coderabbit_shared::RepoConfig;

#[tokio::test]
async fn test_config_loader_creation() {
    let loader = ConfigLoader::new(Some("test_token".to_string()));

    // Check cache stats
    let (size, keys) = loader.cache_stats().await;
    assert_eq!(size, 0);
    assert_eq!(keys.len(), 0);
}

#[tokio::test]
async fn test_cache_operations() {
    let loader = ConfigLoader::new(Some("test_token".to_string()));

    // Clear cache should not panic
    loader.clear_cache().await;

    // Invalidate should not panic
    loader.invalidate_repo("owner", "repo").await;

    let (size, _) = loader.cache_stats().await;
    assert_eq!(size, 0);
}

#[tokio::test]
#[ignore] // Requires GitHub token
async fn test_load_config_from_real_repo() {
    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let loader = ConfigLoader::new(Some(github_token));

    // Try to load config from a public repo
    // This will return default config if .coderabbit.yaml doesn't exist
    let owner = "rust-lang";
    let repo = "rust";
    let ref_name = "master";

    println!("📋 Loading config from {}/{} (ref: {})", owner, repo, ref_name);

    let config = loader.load_config(owner, repo, ref_name).await;

    match config {
        Ok(cfg) => {
            println!("✅ Config loaded successfully");
            println!("   Auto review: {}", cfg.reviews.auto_review);
            println!("   Min severity: {}", cfg.reviews.min_severity);
            println!("   Max comments: {}", cfg.reviews.max_comments);
            println!("   Inherit: {}", cfg.inherit);

            // Should have default values
            assert!(cfg.reviews.auto_review);
            assert_eq!(cfg.reviews.min_severity, "warning");
        }
        Err(e) => {
            panic!("Failed to load config: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_config_cache_hit() {
    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let loader = ConfigLoader::new(Some(github_token));

    let owner = "rust-lang";
    let repo = "rust";
    let ref_name = "master";

    println!("📋 First load (cache miss)...");
    let start = std::time::Instant::now();
    let config1 = loader.load_config(owner, repo, ref_name).await.unwrap();
    let first_duration = start.elapsed();
    println!("   First load took: {:?}", first_duration);

    println!("📋 Second load (cache hit)...");
    let start = std::time::Instant::now();
    let config2 = loader.load_config(owner, repo, ref_name).await.unwrap();
    let second_duration = start.elapsed();
    println!("   Second load took: {:?}", second_duration);

    // Second load should be much faster (cache hit)
    assert!(second_duration < first_duration / 2);

    // Configs should be identical
    assert_eq!(config1.reviews.auto_review, config2.reviews.auto_review);
    assert_eq!(config1.reviews.min_severity, config2.reviews.min_severity);

    // Check cache stats
    let (cache_size, cache_keys) = loader.cache_stats().await;
    println!("   Cache size: {}", cache_size);
    println!("   Cache keys: {:?}", cache_keys);
    assert_eq!(cache_size, 1);
}

#[tokio::test]
#[ignore]
async fn test_parse_example_config() {
    // Load the example config file (try multiple paths)
    let paths = vec![
        "config/coderabbit.example.yaml",
        "../config/coderabbit.example.yaml",
        "../../config/coderabbit.example.yaml",
    ];

    let mut yaml = None;
    for path in paths {
        if let Ok(content) = std::fs::read_to_string(path) {
            println!("Found config at: {}", path);
            yaml = Some(content);
            break;
        }
    }

    let yaml = yaml.expect("Failed to read example config file from any path");

    println!("📋 Parsing example .coderabbit.yaml...");

    let config = RepoConfig::from_yaml(&yaml);

    match config {
        Ok(cfg) => {
            println!("✅ Example config parsed successfully");
            println!("   Auto review: {}", cfg.reviews.auto_review);
            println!("   Min severity: {}", cfg.reviews.min_severity);
            println!("   Max comments: {}", cfg.reviews.max_comments);
            println!("   Comment style: {:?}", cfg.reviews.comment_style);
            println!("   Ignored directories: {:?}", cfg.ignore.directories);
            println!("   Enabled rules: {:?}", cfg.rules.enabled);
            println!("   Disabled rules: {:?}", cfg.rules.disabled);
            println!("   Languages: {:?}", cfg.languages.keys().collect::<Vec<_>>());

            // Verify specific values from example
            assert!(cfg.reviews.auto_review);
            assert_eq!(cfg.reviews.min_severity, "warning");
            assert_eq!(cfg.reviews.max_comments, 50);

            // Check ignore patterns
            assert!(cfg.ignore.directories.contains(&"node_modules".to_string()));
            assert!(cfg.ignore.directories.contains(&"dist".to_string()));

            // Check language configs
            assert!(cfg.languages.contains_key("rust"));
            assert!(cfg.languages.contains_key("python"));
            assert!(cfg.languages.contains_key("javascript"));

            // Check rules
            assert!(cfg.rules.enabled.contains(&"security".to_string()));
            assert!(cfg.rules.disabled.contains(&"style".to_string()));

            // Test ignore patterns
            assert!(cfg.should_ignore_file("node_modules/package/index.js", Some("javascript")));
            assert!(cfg.should_ignore_file("dist/bundle.min.js", Some("javascript")));
            assert!(!cfg.should_ignore_file("src/main.rs", Some("rust")));
        }
        Err(e) => {
            panic!("Failed to parse example config: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_config_invalidation() {
    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let loader = ConfigLoader::new(Some(github_token));

    let owner = "rust-lang";
    let repo = "rust";
    let ref_name = "master";

    // Load config (cache miss)
    loader.load_config(owner, repo, ref_name).await.unwrap();

    let (cache_size, _) = loader.cache_stats().await;
    assert_eq!(cache_size, 1);

    // Invalidate the specific repo
    loader.invalidate_repo(owner, repo).await;

    let (cache_size, _) = loader.cache_stats().await;
    assert_eq!(cache_size, 0);
}

#[tokio::test]
async fn test_default_config_values() {
    let config = RepoConfig::default();

    // Verify defaults
    assert!(config.reviews.auto_review);
    assert_eq!(config.reviews.min_severity, "warning");
    assert_eq!(config.reviews.max_comments, 50);
    assert!(config.reviews.request_changes_on_error);
    assert!(!config.reviews.auto_approve_no_issues);
    assert!(config.reviews.post_summary);
    assert!(config.reviews.review_tests);

    assert!(config.chat.enabled);
    assert!(config.chat.include_examples);
    assert_eq!(config.chat.tone, "professional");

    assert!(config.inherit);
}
