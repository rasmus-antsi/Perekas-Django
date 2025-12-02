"""
Custom test runner that displays test results in a nice format.
Shows each test name with OK/FAIL status.
"""
from django.test.runner import DiscoverRunner
from io import StringIO
import sys


class NiceTestRunner(DiscoverRunner):
    """Test runner that shows test names with status"""
    
    def run_suite(self, suite):
        """Run the test suite with nice output"""
        from unittest import TextTestRunner
        from django.test.runner import get_runner
        
        # Create a custom stream that captures output
        stream = StringIO()
        
        # Use Django's test runner but with custom result class
        runner_class = get_runner(self.settings, self.test_runner_class)
        runner = runner_class(
            verbosity=self.verbosity,
            interactive=False,
            failfast=self.failfast,
            keepdb=self.keepdb,
            reverse=self.reverse,
            debug_mode=self.debug_mode,
            debug_sql=self.debug_sql,
            parallel=self.parallel,
            tags=self.tags,
            exclude_tags=self.exclude_tags,
            test_name_patterns=self.test_name_patterns,
            pdb=self.pdb,
            buffer=True,
        )
        
        return runner.run(suite)

