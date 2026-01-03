"""Test orchestrator for running system integration tests."""

import asyncio
import uuid
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from .config import TestConfig, get_config
from .issue_collector import IssueCollector, Severity, Category, get_collector
from .report_generator import TestReport, ReportGenerator, ComponentResult


class TestOrchestrator:
    """Coordinates all system integration tests."""
    
    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or get_config()
        self.collector = get_collector()
        self.report_generator = ReportGenerator()
        self.current_report: Optional[TestReport] = None
        
    async def run_all_tests(self) -> TestReport:
        """Execute all test phases in order."""
        run_id = str(uuid.uuid4())[:8]
        self.current_report = self.report_generator.create_report(run_id)
        self.current_report.environment = {
            "api_gateway_url": self.config.api_gateway_url,
            "ai_pipeline_url": self.config.ai_pipeline_url,
            "database_url": self.config.database_url[:50] + "...",
            "redis_url": self.config.redis_url,
        }
        
        print(f"\n{'='*60}")
        print(f"  System Integration Test Run: {run_id}")
        print(f"  Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"{'='*60}\n")
        
        # Phase 1: Health checks (blocking)
        print("📋 Phase 1: Health Checks")
        health_passed = await self._run_phase("health", self._run_health_tests)
        
        if not health_passed and self.collector.has_critical_issues():
            print("\n❌ Critical health check failures. Stopping tests.")
            self._finalize_report()
            return self.current_report
        
        # Phase 2: Component tests
        print("\n📋 Phase 2: Component Tests")
        await self._run_phase("bridge", self._run_bridge_tests)
        await self._run_phase("analysis", self._run_analysis_tests)
        await self._run_phase("vector", self._run_vector_tests)
        await self._run_phase("cache", self._run_cache_tests)
        
        # Phase 3: Integration tests
        print("\n📋 Phase 3: Integration Tests")
        await self._run_phase("integration", self._run_integration_tests)
        
        # Phase 4: E2E tests
        print("\n📋 Phase 4: End-to-End Tests")
        await self._run_phase("e2e", self._run_e2e_tests)
        
        # Phase 5: Load tests (optional)
        if self.config.run_load_tests:
            print("\n📋 Phase 5: Load Tests")
            await self._run_phase("load", self._run_load_tests)
        
        self._finalize_report()
        return self.current_report
    
    async def _run_phase(
        self, 
        phase_name: str, 
        test_func: Callable
    ) -> bool:
        """Run a test phase and track results."""
        start_time = datetime.utcnow()
        component_result = ComponentResult(name=phase_name)
        
        try:
            passed, failed, skipped = await test_func()
            component_result.tests_passed = passed
            component_result.tests_failed = failed
            component_result.tests_skipped = skipped
            component_result.tests_run = passed + failed + skipped
        except Exception as e:
            self.collector.record_failure(
                test_name=f"{phase_name}_phase",
                component=phase_name,
                error=e,
                severity=Severity.CRITICAL,
                category=Category.UNKNOWN
            )
            component_result.tests_failed = 1
            component_result.tests_run = 1
        
        component_result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        self.current_report.component_results[phase_name] = component_result
        
        # Update totals
        self.current_report.total_tests += component_result.tests_run
        self.current_report.passed += component_result.tests_passed
        self.current_report.failed += component_result.tests_failed
        self.current_report.skipped += component_result.tests_skipped
        
        status = "✅" if component_result.tests_failed == 0 else "❌"
        print(f"  {status} {phase_name}: {component_result.tests_passed}/{component_result.tests_run} passed")
        
        return component_result.tests_failed == 0
    
    async def _run_health_tests(self) -> Tuple[int, int, int]:
        """Run health check tests."""
        from .health import test_health
        return await test_health.run_all(self.config, self.collector)
    
    async def _run_bridge_tests(self) -> Tuple[int, int, int]:
        """Run bridge communication tests."""
        from .bridge import test_bridge
        return await test_bridge.run_all(self.config, self.collector)
    
    async def _run_analysis_tests(self) -> Tuple[int, int, int]:
        """Run code analysis tests."""
        from .analysis import test_analysis
        return await test_analysis.run_all(self.config, self.collector)
    
    async def _run_vector_tests(self) -> Tuple[int, int, int]:
        """Run vector engine tests."""
        from .vector import test_vector
        return await test_vector.run_all(self.config, self.collector)
    
    async def _run_cache_tests(self) -> Tuple[int, int, int]:
        """Run cache layer tests."""
        from .cache import test_cache
        return await test_cache.run_all(self.config, self.collector)
    
    async def _run_integration_tests(self) -> Tuple[int, int, int]:
        """Run integration tests."""
        from .integration import test_integration
        return await test_integration.run_all(self.config, self.collector)
    
    async def _run_e2e_tests(self) -> Tuple[int, int, int]:
        """Run end-to-end tests."""
        from .e2e import test_e2e
        return await test_e2e.run_all(self.config, self.collector)
    
    async def _run_load_tests(self) -> Tuple[int, int, int]:
        """Run load tests."""
        from .load import test_load
        return await test_load.run_all(self.config, self.collector)
    
    def _finalize_report(self) -> None:
        """Finalize the test report."""
        self.current_report.finalize(self.collector)
        
        print(f"\n{'='*60}")
        print("  Test Run Complete")
        print(f"{'='*60}")
        print(f"  Total: {self.current_report.total_tests}")
        print(f"  Passed: {self.current_report.passed} ✅")
        print(f"  Failed: {self.current_report.failed} ❌")
        print(f"  Skipped: {self.current_report.skipped} ⏭️")
        print(f"  Duration: {self.current_report.duration_seconds:.1f}s")
        print(f"\n  Issues Found:")
        for severity, count in self.current_report.issue_summary.items():
            if count > 0:
                print(f"    {severity}: {count}")
        print(f"{'='*60}\n")


async def run_tests(config: Optional[TestConfig] = None) -> TestReport:
    """Main entry point for running all tests."""
    orchestrator = TestOrchestrator(config)
    return await orchestrator.run_all_tests()
