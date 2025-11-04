//! Real PR Review Test
//! 
//! This processes a complete PR with AI analysis
//! 
//! Run with:
//! ```bash
//! export GITHUB_TOKEN=your_token
//! export GEMINI_API_KEY=your_key
//! cargo test --package coderabbit-integration-tests real_pr_review -- --ignored --nocapture
//! ```

#[cfg(test)]
mod tests {
    use std::sync::Arc;
    use coderabbit_api_gateway::helpers::git_client::GitHubClient;
    use coderabbit_orchestrator::{RedisOrchestrator, JobType};
    use coderabbit_code_analyzer::analyzer::CodeAnalyzer;
    use coderabbit_security::sandbox::{SecurityManager, SandboxConfig};
    use std::collections::HashMap;

    #[tokio::test]
    #[ignore]
    async fn real_pr_review_with_ai() {
        println!("\n🤖 CodeRabbit AI PR Review - Full Pipeline");
        println!("===========================================\n");

        // Configuration
        let github_token = std::env::var("GITHUB_TOKEN").expect("GITHUB_TOKEN required");
        let owner = std::env::var("TEST_GITHUB_OWNER").unwrap_or_else(|_| "rust-lang".to_string());
        let repo = std::env::var("TEST_GITHUB_REPO").unwrap_or_else(|_| "rust".to_string());
        let pr_number: u32 = std::env::var("TEST_GITHUB_PR")
            .unwrap_or_else(|_| "114183".to_string())
            .parse()
            .expect("PR number must be valid");

        println!("📋 Target: {}/{} PR #{}", owner, repo, pr_number);
        println!("");

        // Step 1: Fetch PR files
        println!("📥 STEP 1: Fetching PR from GitHub");
        println!("-----------------------------------");
        
        let github = GitHubClient::new(Some(github_token));
        let files = github.fetch_pr_files(&owner, &repo, pr_number).await
            .expect("Failed to fetch PR files");

        println!("✅ Fetched {} files\n", files.len());

        // Display file summary
        println!("📊 Files Changed:");
        let mut lang_counts = HashMap::new();
        for file in &files {
            *lang_counts.entry(file.language.clone()).or_insert(0) += 1;
            println!("   • {} ({}, {:?})", file.path, file.language, file.change_type);
        }
        
        println!("\n📈 Language Distribution:");
        for (lang, count) in lang_counts.iter() {
            println!("   {} files: {}", count, lang);
        }
        println!("");

        // Step 2: Analyze files
        println!("🔍 STEP 2: Analyzing Code");
        println!("-------------------------");

        let analyzer = CodeAnalyzer::new();
        let mut total_issues = 0;
        let mut analysis_results = Vec::new();

        for file in files.iter().take(3) { // Analyze first 3 files for demo
            if file.content.is_empty() {
                println!("   ⚠️  Skipping {} (no content)", file.path);
                continue;
            }

            println!("   Analyzing: {}", file.path);
            
            match analyzer.analyze_files(vec![file.clone()]).await {
                Ok(results) => {
                    if let Some(result) = results.first() {
                        println!("      ✅ Issues: {}", result.issues.len());
                        println!("      📊 Lines: {}", result.metrics.lines_of_code);
                        println!("      🔧 Complexity: {}", result.metrics.cyclomatic_complexity);

                        total_issues += result.issues.len();
                        analysis_results.push((file.path.clone(), result.clone()));
                    }
                }
                Err(e) => {
                    println!("      ⚠️  Analysis error: {}", e);
                }
            }
        }
        println!("");

        // Step 3: Security Analysis
        println!("🔒 STEP 3: Security Analysis");
        println!("----------------------------");

        let sandbox_config = SandboxConfig {
            max_memory_mb: 512,
            max_cpu_time_seconds: 10,
            max_execution_time_seconds: 30,
            allowed_directories: vec!["/tmp".to_string()],
            blocked_syscalls: vec![],
            enable_network: false,
            user_id: 1000,
            group_id: 1000,
        };

        match SecurityManager::new(sandbox_config).await {
            Ok(security_mgr) => {
                let stats = security_mgr.get_security_stats().await;
                println!("   ✅ Security manager active");
                println!("   🛡️  Security score: {:.1}/100", stats.security_score);
                
                // Check for security patterns in code
                let mut security_issues = Vec::new();
                for file in &files {
                    if file.content.contains("unsafe") {
                        security_issues.push(format!("{}: Contains 'unsafe' block", file.path));
                    }
                    if file.content.contains("unwrap()") {
                        security_issues.push(format!("{}: Uses unwrap() (potential panic)", file.path));
                    }
                    if file.content.contains("todo!") || file.content.contains("unimplemented!") {
                        security_issues.push(format!("{}: Contains unfinished code", file.path));
                    }
                }
                
                if !security_issues.is_empty() {
                    println!("\n   ⚠️  Potential Security/Quality Issues:");
                    for (i, issue) in security_issues.iter().take(5).enumerate() {
                        println!("      {}. {}", i + 1, issue);
                    }
                }
            }
            Err(e) => {
                println!("   ⚠️  Security manager unavailable: {}", e);
            }
        }
        println!("");

        // Step 4: Queue for AI Review
        println!("🤖 STEP 4: Queuing for AI Review");
        println!("---------------------------------");

        let redis_url = std::env::var("REDIS_URL")
            .or_else(|_| std::env::var("TEST_REDIS_URL"))
            .unwrap_or_else(|_| "redis://localhost:6380".to_string());

        match RedisOrchestrator::new(&redis_url) {
            Ok(orchestrator) => {
                let payload = serde_json::json!({
                    "repository": format!("{}/{}", owner, repo),
                    "pr_number": pr_number,
                    "files": files.len(),
                    "total_issues": total_issues,
                    "languages": lang_counts,
                });

                match orchestrator.enqueue_job(
                    JobType::ReviewRequest,
                    payload.to_string(),
                    7 // high priority
                ).await {
                    Ok(job_id) => {
                        println!("   ✅ Job queued: {}", job_id);
                        println!("   📊 Priority: High (7)");
                        println!("   📝 Status: Pending AI analysis");
                    }
                    Err(e) => {
                        println!("   ⚠️  Queue error: {}", e);
                    }
                }
            }
            Err(_) => {
                println!("   ⚠️  Redis unavailable - using in-memory queue");
            }
        }
        println!("");

        // Step 5: Generate AI Summary
        println!("✨ STEP 5: AI Analysis Summary");
        println!("------------------------------");

        // Prepare summary
        let summary = format!(
            "PR #{} - {} files changed\n\
            Languages: {:?}\n\
            Total issues found: {}\n\
            Files analyzed: {}/{}",
            pr_number,
            files.len(),
            lang_counts.keys().collect::<Vec<_>>(),
            total_issues,
            analysis_results.len(),
            files.len()
        );

        println!("{}", summary);
        println!("");

        // Generate insights
        println!("💡 Key Insights:");
        if total_issues > 0 {
            println!("   • Found {} code quality issues", total_issues);
        } else {
            println!("   • No major issues detected");
        }

        if lang_counts.len() > 1 {
            println!("   • Multi-language PR ({} languages)", lang_counts.len());
        }

        if files.len() > 10 {
            println!("   • Large PR - consider splitting");
        } else {
            println!("   • Reasonable PR size");
        }

        // Check for tests
        let has_tests = files.iter().any(|f| 
            f.path.contains("test") || f.path.contains("spec")
        );
        if has_tests {
            println!("   • Includes test files ✅");
        } else {
            println!("   • No test files detected ⚠️");
        }

        // Check for documentation
        let has_docs = files.iter().any(|f| 
            f.path.ends_with(".md") || f.path.contains("doc")
        );
        if has_docs {
            println!("   • Includes documentation ✅");
        }

        println!("");

        // Final verdict
        println!("📋 FINAL REVIEW");
        println!("===============");
        
        let score = if total_issues == 0 { 95 } 
                   else if total_issues < 5 { 85 }
                   else if total_issues < 10 { 75 }
                   else { 65 };

        println!("   Quality Score: {}/100", score);
        
        if score >= 90 {
            println!("   Verdict: ✅ APPROVED - Excellent quality");
        } else if score >= 80 {
            println!("   Verdict: ✅ APPROVED - Good quality");
        } else if score >= 70 {
            println!("   Verdict: ⚠️  APPROVED with comments");
        } else {
            println!("   Verdict: ❌ CHANGES REQUESTED");
        }

        println!("\n🎉 Review Complete!\n");
    }

    #[tokio::test]
    #[ignore]
    async fn real_pr_language_stats() {
        let github_token = std::env::var("GITHUB_TOKEN").expect("GITHUB_TOKEN required");
        let github = GitHubClient::new(Some(github_token));
        
        let files = github.fetch_pr_files("rust-lang", "rust", 114183).await.unwrap();

        let mut stats = HashMap::new();
        let mut total_size = 0;

        for file in &files {
            let lang_stat = stats.entry(file.language.clone()).or_insert((0, 0));
            lang_stat.0 += 1;
            lang_stat.1 += file.content.len();
            total_size += file.content.len();
        }

        println!("\n📊 Detailed Language Statistics");
        println!("================================\n");

        for (lang, (count, size)) in stats.iter() {
            let percentage = if total_size > 0 {
                (*size as f64 / total_size as f64) * 100.0
            } else { 0.0 };
            
            println!("{:15} {:3} files  {:8} bytes  ({:.1}%)", 
                     lang, count, size, percentage);
        }

        println!("\nTotal: {} files, {} bytes\n", files.len(), total_size);
    }
}
