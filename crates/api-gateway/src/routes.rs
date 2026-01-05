use crate::handlers::{
    comment_handler, database, github, health, indexing, issue_filtering, jobs, pr_features,
    review, webhook,
};
use axum::{
    routing::{get, post},
    Router,
};

pub fn create_routes() -> Router<database::DatabaseState> {
    Router::new()
        .route("/health", get(health::health_check))
        // GitHub integration routes
        .route("/webhook/github", post(webhook::github_webhook))
        .route(
            "/webhook/github/comment",
            post(comment_handler::handle_comment_webhook),
        )
        .route(
            "/github/repos/:owner/:repo/prs/:pr_number",
            get(github::get_github_pr),
        )
        // PR Features routes (Summarization, Suggestions, Issue Validation)
        .route(
            "/repos/:owner/:repo/pulls/:pr_number/summary",
            get(pr_features::generate_pr_summary),
        )
        .route(
            "/repos/:owner/:repo/pulls/:pr_number/suggestions",
            get(pr_features::get_pr_suggestions),
        )
        .route(
            "/repos/:owner/:repo/pulls/:pr_number/validate-issues",
            get(pr_features::validate_pr_issues),
        )
        .route("/suggestions/apply", post(pr_features::apply_suggestion))
        // Issue filtering and ranking routes
        .route(
            "/repos/:owner/:repo/pulls/:pr_number/issues",
            get(issue_filtering::get_filtered_issues),
        )
        // Job orchestration routes
        .route("/jobs", post(jobs::create_job))
        .route("/jobs/:job_id", get(jobs::get_job_status))
        .route("/jobs/:job_id/cancel", post(jobs::cancel_job))
        .route(
            "/jobs/repository/:repository_id",
            get(jobs::get_repository_jobs),
        )
        .route("/jobs/metrics", get(jobs::get_orchestration_metrics))
        // Database routes
        .route(
            "/repositories/:organization_id",
            get(database::list_repositories),
        )
        .route(
            "/repositories/:repository_id/show",
            get(database::get_repository),
        )
        .route("/repositories", post(database::create_repository))
        .route(
            "/repositories/:repository_id/jobs",
            get(database::list_jobs),
        )
        .route("/jobs/:job_id/status", post(database::update_job_status))
        .route("/jobs/:job_id/results", get(database::get_analysis_results))
        .route(
            "/organizations/:organization_id/stats",
            get(database::get_organization_stats),
        )
        // Legacy webhook routes (for future GitLab/Azure integration)
        .route("/webhook/gitlab", post(webhook::gitlab_webhook))
        .route("/webhook/azure", post(webhook::azure_webhook))
        // Review management routes
        .route("/review", post(review::create_review))
        .route("/review/enqueue", post(review::enqueue_review))
        .route("/review/:id", get(review::get_review_status))
        .route("/review/:id/cancel", post(review::cancel_review))
        // RAG indexing routes
        .route("/index", post(indexing::index_repository))
}
