#!/usr/bin/env python3
"""
Fetch and analyze a REAL GitHub PR using the full CodeRabbit AI system.
"""

import sys
import os
import json
import requests

# Add python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

# Set API keys and AST-Grep rules path
os.environ['ANTHROPIC_API_KEY'] = "API_KEY"
os.environ['ASTGREP_RULES_PATH'] = "/tmp/ast-grep-rules"

from coderabbit_ai.models import (
    ReviewRequest,
    Repository,
    PullRequest,
    FileChange,
    User,
    ChangeType,
    Platform,
    AISettings,
    ReviewRules,
    OrganizationConfig
)
from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline

print("=" * 80)
print("🌐 GITHUB PR ANALYZER - Full System Test")
print("=" * 80)
print()

# Configuration
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Example PR to analyze (you can change this)
# Using CodeRabbit's own PR review system
REPO_OWNER = "coderabbitai"
REPO_NAME = "coderabbit-pr-review"
PR_NUMBER = 63

def fetch_github_pr(owner, repo, pr_number):
    """Fetch PR details from GitHub API."""
    print(f"📡 Fetching PR #{pr_number} from {owner}/{repo}...")

    # Get PR details
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(pr_url, headers=HEADERS)

    if response.status_code == 404:
        # PR not found, get latest PR instead
        print(f"   PR #{pr_number} not found, fetching latest PR...")
        prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=1"
        response = requests.get(prs_url, headers=HEADERS)
        if response.status_code == 200 and response.json():
            latest_pr = response.json()[0]
            pr_number = latest_pr['number']
            pr_url = latest_pr['url']
            response = requests.get(pr_url, headers=HEADERS)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch PR: {response.status_code} - {response.text}")

    pr_data = response.json()

    # Get PR files
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    files_response = requests.get(files_url, headers=HEADERS)

    if files_response.status_code != 200:
        raise Exception(f"Failed to fetch PR files: {files_response.status_code}")

    files_data = files_response.json()

    print(f"✅ Fetched PR #{pr_data['number']}: {pr_data['title']}")
    print(f"   Files changed: {len(files_data)}")
    print(f"   Additions: +{pr_data.get('additions', 0)}")
    print(f"   Deletions: -{pr_data.get('deletions', 0)}")
    print()

    return pr_data, files_data

def convert_github_pr_to_model(pr_data, files_data):
    """Convert GitHub PR data to CodeRabbit models."""

    # Convert files
    file_changes = []
    for file_data in files_data[:10]:  # Limit to first 10 files for testing
        # Determine change type
        status = file_data.get('status', 'modified')
        change_type_map = {
            'added': ChangeType.ADDED,
            'removed': ChangeType.DELETED,
            'modified': ChangeType.MODIFIED,
            'renamed': ChangeType.MODIFIED
        }
        change_type = change_type_map.get(status, ChangeType.MODIFIED)

        # Get file extension for language
        filename = file_data.get('filename', '')
        ext = filename.split('.')[-1] if '.' in filename else 'unknown'
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'go': 'go',
            'java': 'java',
            'rb': 'ruby',
            'php': 'php',
            'rs': 'rust',
            'cpp': 'cpp',
            'c': 'c'
        }
        language = language_map.get(ext, ext)

        file_change = FileChange(
            path=filename,
            change_type=change_type,
            content=file_data.get('patch', '')[:5000],  # Limit content size
            diff=file_data.get('patch', '')[:5000],
            language=language
        )
        file_changes.append(file_change)

    # Create user
    author_data = pr_data.get('user', {})
    user = User(
        id=str(author_data.get('id', 'unknown')),
        username=author_data.get('login', 'unknown'),
        email=None
    )

    # Create pull request
    pull_request = PullRequest(
        id=str(pr_data['id']),
        number=pr_data['number'],
        title=pr_data['title'],
        description=pr_data.get('body', '') or 'No description provided',
        author=user,
        base_branch=pr_data['base']['ref'],
        head_branch=pr_data['head']['ref'],
        files_changed=file_changes
    )

    # Create repository
    repo_data = pr_data['base']['repo']
    repository = Repository(
        id=str(repo_data['id']),
        name=repo_data['name'],
        owner=repo_data['owner']['login'],
        platform=Platform.GITHUB,
        clone_url=repo_data['clone_url'],
        default_branch=repo_data['default_branch']
    )

    return repository, pull_request

try:
    # Fetch PR from GitHub
    pr_data, files_data = fetch_github_pr(REPO_OWNER, REPO_NAME, PR_NUMBER)

    # Convert to models
    print("🔄 Converting GitHub PR to CodeRabbit models...")
    repository, pull_request = convert_github_pr_to_model(pr_data, files_data)
    print(f"✅ Converted {len(pull_request.files_changed)} files")
    print()

    # Create organization config
    ai_settings = AISettings(
        primary_model="claude-3-sonnet-20240229",
        fallback_models=["gpt-3.5-turbo"],
        temperature=0.7,
        max_tokens=4096
    )

    review_rules = ReviewRules(
        enabled_checks=["security", "performance", "style", "logic"],
        severity_thresholds={
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low"
        },
        custom_rules=[]
    )

    org_config = OrganizationConfig(
        id="org123",
        name="Test Organization",
        review_rules=review_rules,
        ai_settings=ai_settings,
        integrations=[]
    )

    # Create review request
    review_request = ReviewRequest(
        repository=repository,
        pull_request=pull_request,
        config=org_config
    )

    # Configure DSPy with Anthropic Claude
    print("🔧 Configuring DSPy with Anthropic Claude...")
    import dspy

    anthropic_lm = dspy.LM(
        model="anthropic/claude-3-haiku-20240307",
        api_key=os.environ.get('ANTHROPIC_API_KEY'),
        max_tokens=4096,
        temperature=0.7
    )
    dspy.settings.configure(lm=anthropic_lm)
    print("✅ DSPy configured with Claude 3 Haiku")
    print()

    # Initialize pipeline
    print("🔧 Initializing CodeRabbit AI Pipeline...")
    pipeline_config = {
        "verification_specializations": ["security", "performance", "style"],
        "anthropic_api_key": os.environ.get('ANTHROPIC_API_KEY'),
        "security": {
            "block_on_critical": True,
            "max_high_severity": 3,
            "confidence_threshold": 0.7
        },
        "use_codeact": False
    }

    pipeline = CodeRabbitMultiAgentPipeline(pipeline_config)
    print("✅ Pipeline initialized")
    print()

    # Process the review
    print("=" * 80)
    print("🤖 RUNNING AI-POWERED CODE REVIEW")
    print("=" * 80)
    print()

    print("⏳ Processing PR through pipeline...")
    print("   📊 Phase 1: Static analysis & security scanning...")
    print("   🧠 Phase 2: AI analysis with Claude Haiku...")
    print("   🔒 Phase 3: Security aggregation & recommendations...")
    print()

    response = pipeline.forward(review_request)

    print("=" * 80)
    print("✅ REVIEW COMPLETE")
    print("=" * 80)
    print()

    # Display results
    print(f"📊 Review ID: {response.review_id}")
    print(f"📊 Status: {response.status}")
    print()

    # Metrics
    print("📈 METRICS:")
    print(f"   ⏱️  Analysis time: {response.metrics.analysis_time_ms}ms ({response.metrics.analysis_time_ms/1000:.1f}s)")
    print(f"   📁 Files analyzed: {response.metrics.files_analyzed}")
    print(f"   🔍 Issues found: {response.metrics.issues_found}")
    print(f"   💰 AI cost: ${response.metrics.ai_cost:.4f}")
    print()

    # Security Summary
    if response.security_summary:
        print("🔒 SECURITY SUMMARY:")
        print(f"   Total findings: {response.security_summary.total_findings}")
        if response.security_summary.by_severity:
            print(f"   By severity:")
            for severity, count in response.security_summary.by_severity.items():
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(severity, "⚫")
                print(f"     {icon} {severity.upper()}: {count}")

        if response.security_summary.critical_files:
            print(f"   Critical files: {', '.join(response.security_summary.critical_files[:5])}")
        if response.security_summary.tools_used:
            print(f"   Tools used: {', '.join(response.security_summary.tools_used)}")
        print()

    # Security Recommendation
    if response.security_recommendation:
        rec = response.security_recommendation
        print("⚠️  SECURITY RECOMMENDATION:")
        print(f"   Action: {rec['action'].upper()}")
        print(f"   Severity: {rec['severity_level']}")
        print(f"   {rec['message']}")
        print()

    # Comments
    if response.comments:
        print(f"💬 REVIEW COMMENTS ({len(response.comments)}):")
        print()

        # Show first 10 comments
        for i, comment in enumerate(response.comments[:10], 1):
            severity_icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "⚪",
                "info": "ℹ️"
            }.get(comment.severity, "⚫")

            print(f"{i}. {severity_icon} {comment.file_path}:{comment.line_number} [{comment.severity.upper()}]")
            print(f"   {comment.message[:150]}")
            if hasattr(comment, 'suggested_fix') and comment.suggested_fix:
                print(f"   💡 Fix: {comment.suggested_fix[:100]}")
            print()

        if len(response.comments) > 10:
            print(f"   ... and {len(response.comments) - 10} more issues")
        print()
    else:
        print("💬 No review comments generated")
        print()

    # Save results
    output_file = f"github_pr_{pull_request.number}_review.json"
    with open(output_file, "w") as f:
        result_dict = response.model_dump() if hasattr(response, 'model_dump') else response.dict()
        json.dump(result_dict, f, indent=2, default=str)

    print("=" * 80)
    print(f"✅ Results saved to: {output_file}")
    print("=" * 80)
    print()

    # Summary
    print("📋 FINAL RECOMMENDATION:")
    if response.security_recommendation:
        action = response.security_recommendation['action']
        if action == "block":
            print("   ❌ BLOCK MERGE - Critical security issues detected!")
        elif action == "caution":
            print("   ⚠️  PROCEED WITH CAUTION - Review security issues carefully")
        elif action == "warning":
            print("   ⚡ WARNING - Minor security issues detected")
        else:
            print("   ✅ APPROVE - No security issues detected")
    else:
        print("   ℹ️  Review complete (no security analysis)")

    print()
    print("🎉 Full GitHub PR analysis COMPLETE!")
    print()
    print(f"📎 View PR on GitHub: {pr_data['html_url']}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
