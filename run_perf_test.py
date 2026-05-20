#!/usr/bin/env python
"""
Simple performance test runner
"""

import os
import json
from performance_test_suite import PerformanceTestSuite
import datetime

def main():
    suite = PerformanceTestSuite()
    suite.log('Starting simplified performance test...')

    if suite.ensure_test_data():
        suite.log('Test data ready')
        suite.test_api_endpoints()
        suite.test_database_queries()

        # Convert results to serializable format
        serializable_results = {}
        for key, result in suite.results.items():
            serializable_results[key] = {
                'duration': result['duration'],
                'memory_delta': result['memory_delta'],
                'success': result['success'],
                'result': str(result.get('result', '')),
                'timestamp': result['timestamp']
            }

        # Save results
        os.makedirs('performance_reports', exist_ok=True)
        report_file = 'performance_reports/performance_report_manual.json'
        with open(report_file, 'w') as f:
            json.dump({
                'test_run': {'timestamp': datetime.datetime.now().isoformat(), 'source': 'manual'},
                'results': serializable_results
            }, f, indent=2)

        suite.log(f'Results saved to {report_file}')
        print('Performance test results:')
        for test, result in serializable_results.items():
            status = 'PASS' if result['success'] else 'FAIL'
            print(f'  {status}: {test} - {result["duration"]:.3f}s')

        suite.cleanup_test_data()
    else:
        print('Failed to setup test data')

if __name__ == '__main__':
    main()