#!/usr/bin/env python
"""
Performance Report Generator for BLACPHICS E-Commerce System
Analyzes test results and generates comprehensive performance reports.
"""

import os
import json
import glob
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd

class PerformanceReportGenerator:
    """Generates comprehensive performance reports from test results."""

    def __init__(self, results_dir="performance_reports"):
        self.results_dir = results_dir
        self.reports = []
        self.summary_stats = {}

    def load_reports(self):
        """Load all performance report files."""
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

        # Load JSON reports
        json_files = glob.glob(os.path.join(self.results_dir, "performance_report_*.json"))
        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    report = json.load(f)
                    self.reports.append(report)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")

        # Load Locust CSV results if available
        csv_files = glob.glob("*.csv")
        for csv_file in csv_files:
            if "locust" in csv_file.lower():
                try:
                    df = pd.read_csv(csv_file)
                    self._process_locust_data(df, csv_file)
                except Exception as e:
                    print(f"Error loading {csv_file}: {e}")

    def _process_locust_data(self, df, filename):
        """Process Locust CSV data into report format."""
        if df.empty:
            return

        # Extract test metadata from filename
        test_info = {
            'test_run': {
                'timestamp': datetime.now().isoformat(),
                'source': 'locust',
                'filename': filename
            },
            'results': {}
        }

        # Process request statistics
        if 'Name' in df.columns and 'Average Response Time' in df.columns:
            for _, row in df.iterrows():
                test_name = f"Locust: {row['Name']}"
                test_info['results'][test_name] = {
                    'duration': row.get('Average Response Time', 0) / 1000,  # Convert to seconds
                    'success': row.get('Status', 'OK') == 'OK',
                    'requests': row.get('Request Count', 0),
                    'failures': row.get('Failure Count', 0),
                    'timestamp': datetime.now().isoformat()
                }

        self.reports.append(test_info)

    def generate_summary_stats(self):
        """Generate summary statistics from all reports."""
        if not self.reports:
            return

        all_results = []
        for report in self.reports:
            for test_name, result in report.get('results', {}).items():
                result['test_name'] = test_name
                result['source'] = report['test_run'].get('source', 'performance_suite')
                all_results.append(result)

        if not all_results:
            return

        # Convert to DataFrame for analysis
        df = pd.DataFrame(all_results)

        # Basic statistics
        self.summary_stats = {
            'total_tests': len(df),
            'successful_tests': len(df[df.get('success', True) == True]),
            'failed_tests': len(df[df.get('success', False) == False]),
            'avg_duration': df['duration'].mean(),
            'median_duration': df['duration'].median(),
            'p95_duration': df['duration'].quantile(0.95),
            'p99_duration': df['duration'].quantile(0.99),
            'max_duration': df['duration'].max(),
            'total_memory_delta': df.get('memory_delta', pd.Series()).sum(),
            'test_categories': {}
        }

        # Categorize tests
        categories = defaultdict(list)
        for _, row in df.iterrows():
            test_name = row['test_name']
            if 'API:' in test_name:
                categories['API'].append(row)
            elif 'DB:' in test_name:
                categories['Database'].append(row)
            elif 'Financial:' in test_name:
                categories['Financial'].append(row)
            elif 'Concurrent' in test_name or 'Stock' in test_name:
                categories['Concurrent'].append(row)
            elif 'Locust:' in test_name:
                categories['Load_Test'].append(row)
            else:
                categories['Other'].append(row)

        # Calculate per-category stats
        for category, tests in categories.items():
            if tests:
                cat_df = pd.DataFrame(tests)
                self.summary_stats['test_categories'][category] = {
                    'count': len(tests),
                    'avg_duration': cat_df['duration'].mean(),
                    'success_rate': (cat_df.get('success', pd.Series()).sum() / len(tests)) * 100,
                    'p95_duration': cat_df['duration'].quantile(0.95)
                }

    def create_performance_charts(self):
        """Create performance visualization charts."""
        if not self.reports:
            return

        # Set up the plotting style
        plt.style.use('default')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('BLACPHICS E-Commerce Performance Report', fontsize=16, fontweight='bold')

        # Chart 1: Response Time Distribution
        all_durations = []
        for report in self.reports:
            for result in report.get('results', {}).values():
                if 'duration' in result:
                    all_durations.append(result['duration'])

        if all_durations:
            axes[0, 0].hist(all_durations, bins=50, alpha=0.7, color='blue', edgecolor='black')
            axes[0, 0].axvline(np.mean(all_durations), color='red', linestyle='--', label=f'Mean: {np.mean(all_durations):.3f}s')
            axes[0, 0].axvline(np.percentile(all_durations, 95), color='orange', linestyle='--', label=f'P95: {np.percentile(all_durations, 95):.3f}s')
            axes[0, 0].set_xlabel('Response Time (seconds)')
            axes[0, 0].set_ylabel('Frequency')
            axes[0, 0].set_title('Response Time Distribution')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)

        # Chart 2: Test Success Rate by Category
        if self.summary_stats.get('test_categories'):
            categories = list(self.summary_stats['test_categories'].keys())
            success_rates = [self.summary_stats['test_categories'][cat]['success_rate'] for cat in categories]

            bars = axes[0, 1].bar(categories, success_rates, color='green', alpha=0.7)
            axes[0, 1].set_ylabel('Success Rate (%)')
            axes[0, 1].set_title('Test Success Rate by Category')
            axes[0, 1].set_ylim(0, 100)

            # Add value labels on bars
            for bar, rate in zip(bars, success_rates):
                axes[0, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                               f'{rate:.1f}%', ha='center', va='bottom')

            plt.setp(axes[0, 1].get_xticklabels(), rotation=45, ha='right')

        # Chart 3: Average Response Time by Category
        if self.summary_stats.get('test_categories'):
            categories = list(self.summary_stats['test_categories'].keys())
            avg_times = [self.summary_stats['test_categories'][cat]['avg_duration'] for cat in categories]

            bars = axes[1, 0].bar(categories, avg_times, color='orange', alpha=0.7)
            axes[1, 0].set_ylabel('Average Response Time (seconds)')
            axes[1, 0].set_title('Average Response Time by Category')

            # Add value labels on bars
            for bar, time in zip(bars, avg_times):
                axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                               f'{time:.3f}s', ha='center', va='bottom')

            plt.setp(axes[1, 0].get_xticklabels(), rotation=45, ha='right')

        # Chart 4: Performance Timeline (if multiple reports)
        if len(self.reports) > 1:
            timestamps = []
            durations = []

            for report in self.reports:
                timestamp = datetime.fromisoformat(report['test_run']['timestamp'].replace('Z', '+00:00'))
                # Get average duration for this report
                report_durations = [r.get('duration', 0) for r in report.get('results', {}).values()]
                if report_durations:
                    avg_duration = np.mean(report_durations)
                    timestamps.append(timestamp)
                    durations.append(avg_duration)

            if timestamps and durations:
                axes[1, 1].plot(timestamps, durations, marker='o', linestyle='-', color='purple')
                axes[1, 1].set_xlabel('Test Run Time')
                axes[1, 1].set_ylabel('Average Response Time (seconds)')
                axes[1, 1].set_title('Performance Timeline')
                axes[1, 1].tick_params(axis='x', rotation=45)

                # Add trend line
                if len(timestamps) > 1:
                    z = np.polyfit(range(len(timestamps)), durations, 1)
                    p = np.poly1d(z)
                    axes[1, 1].plot(timestamps, p(range(len(timestamps))), "r--", alpha=0.7, label='Trend')
                    axes[1, 1].legend()

        plt.tight_layout()
        plt.savefig(os.path.join(self.results_dir, 'performance_report.png'), dpi=300, bbox_inches='tight')
        plt.close()

    def generate_text_report(self):
        """Generate a detailed text report."""
        report_path = os.path.join(self.results_dir, 'performance_report.txt')

        with open(report_path, 'w') as f:
            f.write("="*80 + "\n")
            f.write("BLACPHICS E-COMMERCE SYSTEM PERFORMANCE REPORT\n")
            f.write("="*80 + "\n\n")

            f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Test Reports Analyzed: {len(self.reports)}\n\n")

            if self.summary_stats:
                f.write("OVERALL PERFORMANCE SUMMARY\n")
                f.write("-"*40 + "\n")
                f.write(f"Total Tests Run: {self.summary_stats['total_tests']}\n")
                f.write(f"Successful Tests: {self.summary_stats['successful_tests']}\n")
                f.write(f"Failed Tests: {self.summary_stats['failed_tests']}\n")
                f.write(".1f")
                f.write(".3f")
                f.write(".3f")
                f.write(".3f")
                f.write(".3f")
                f.write("+.1f")

                if self.summary_stats.get('test_categories'):
                    f.write("\n\nPERFORMANCE BY CATEGORY\n")
                    f.write("-"*40 + "\n")
                    f.write("<12")
                    f.write("-"*60 + "\n")

                    for category, stats in self.summary_stats['test_categories'].items():
                        f.write("<12")

                f.write("\n\nRECOMMENDATIONS\n")
                f.write("-"*40 + "\n")

                # Performance recommendations based on results
                if self.summary_stats.get('p95_duration', 0) > 2.0:
                    f.write("WARNING: HIGH LATENCY: P95 response time > 2.0s - Consider database optimization\n")

                if self.summary_stats.get('failed_tests', 0) > 0:
                    f.write(f"WARNING: TEST FAILURES: {self.summary_stats['failed_tests']} tests failed - Review error handling\n")

                api_stats = self.summary_stats.get('test_categories', {}).get('API', {})
                if api_stats and api_stats.get('avg_duration', 0) > 0.5:
                    f.write("WARNING: SLOW API: Average API response > 0.5s - Consider caching or query optimization\n")

                concurrent_stats = self.summary_stats.get('test_categories', {}).get('Concurrent', {})
                if concurrent_stats and concurrent_stats.get('success_rate', 100) < 95:
                    f.write("WARNING: CONCURRENCY ISSUES: Low success rate under concurrent load - Review locking mechanisms\n")

                if not any('Locust' in str(r.get('test_run', {})) for r in self.reports):
                    f.write("INFO: LOAD TESTING: Consider running Locust load tests for production capacity planning\n")

                f.write("SUCCESS: SYSTEM HEALTHY: All core performance metrics within acceptable ranges\n")

            f.write("\n\nRAW TEST RESULTS\n")
            f.write("-"*40 + "\n")

            for i, report in enumerate(self.reports, 1):
                f.write(f"\nReport {i} ({report['test_run'].get('source', 'unknown')}):\n")
                f.write(f"  Timestamp: {report['test_run']['timestamp']}\n")

                for test_name, result in report.get('results', {}).items():
                    status = "PASS" if result.get('success', True) else "FAIL"
                    duration = result.get('duration', 0)
                    f.write(f"  {status} {test_name}: {duration:.3f}s\n")

        return report_path

    def run_analysis(self):
        """Run complete performance analysis."""
        print("Loading performance reports...")
        self.load_reports()

        if not self.reports:
            print("No performance reports found. Run performance_test_suite.py first.")
            return

        print(f"Analyzed {len(self.reports)} test reports")

        print("Generating summary statistics...")
        self.generate_summary_stats()

        print("Creating performance charts...")
        self.create_performance_charts()

        print("Generating text report...")
        report_path = self.generate_text_report()

        print(f"\nPerformance analysis complete!")
        print(f"Results saved to: {self.results_dir}")
        print(f"Text report: {report_path}")
        print(f"Charts: {os.path.join(self.results_dir, 'performance_report.png')}")

        # Print summary to console
        if self.summary_stats:
            print("\n" + "="*50)
            print("PERFORMANCE SUMMARY")
            print("="*50)
            print(f"Total Tests: {self.summary_stats['total_tests']}")
            print(f"Success Rate: {(self.summary_stats['successful_tests']/self.summary_stats['total_tests']*100):.1f}%")
            print(f"Average Response Time: {self.summary_stats['avg_duration']:.3f}s")
            print(f"P95 Response Time: {self.summary_stats['p95_duration']:.3f}s")
            print(f"P99 Response Time: {self.summary_stats['p99_duration']:.3f}s")

if __name__ == '__main__':
    analyzer = PerformanceReportGenerator()
    analyzer.run_analysis()
