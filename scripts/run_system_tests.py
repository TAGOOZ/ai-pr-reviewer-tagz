#!/usr/bin/env python3
"""Main entry point for running system integration tests."""

import argparse
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.system.config import TestConfig
from tests.system.orchestrator import run_tests
from tests.system.report_generator import ReportGenerator


async def main():
    parser = argparse.ArgumentParser(description="Run CodeRabbit system integration tests")
    parser.add_argument("--load-tests", action="store_true", help="Include load tests")
    parser.add_argument("--output-dir", default="test-results", help="Output directory for reports")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--api-gateway", default=None, help="API Gateway URL")
    parser.add_argument("--ai-pipeline", default=None, help="AI Pipeline URL")
    args = parser.parse_args()
    
    # Configure
    config = TestConfig()
    config.run_load_tests = args.load_tests
    config.verbose = args.verbose
    
    if args.api_gateway:
        config.api_gateway_url = args.api_gateway
    if args.ai_pipeline:
        config.ai_pipeline_url = args.ai_pipeline
    
    print("\n🚀 CodeRabbit System Integration Tests")
    print("=" * 50)
    print(f"API Gateway: {config.api_gateway_url}")
    print(f"AI Pipeline: {config.ai_pipeline_url}")
    print(f"Database: {config.database_url[:40]}...")
    print(f"Redis: {config.redis_url}")
    print(f"Load Tests: {'Enabled' if config.run_load_tests else 'Disabled'}")
    print("=" * 50)
    
    # Run tests
    report = await run_tests(config)
    
    # Save reports
    os.makedirs(args.output_dir, exist_ok=True)
    
    json_path = os.path.join(args.output_dir, f"report_{report.run_id}.json")
    md_path = os.path.join(args.output_dir, f"report_{report.run_id}.md")
    
    with open(json_path, "w") as f:
        f.write(report.to_json())
    
    with open(md_path, "w") as f:
        f.write(report.to_markdown())
    
    print(f"\n📄 Reports saved:")
    print(f"   JSON: {json_path}")
    print(f"   Markdown: {md_path}")
    
    # Exit with appropriate code
    if report.failed > 0:
        print(f"\n❌ {report.failed} tests failed")
        sys.exit(1)
    else:
        print(f"\n✅ All {report.passed} tests passed")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
