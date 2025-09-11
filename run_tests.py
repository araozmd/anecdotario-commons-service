#!/usr/bin/env python3
"""
Test runner script for anecdotario-commons-service
Runs all tests and generates coverage reports following TDD best practices
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command, cwd=None):
    """Run a command and return the result"""
    print(f"Running: {command}")
    result = subprocess.run(
        command, shell=True, cwd=cwd, capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")
    return result.returncode == 0


def discover_test_files():
    """Discover all test files in the project"""
    test_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.startswith('test_') and file.endswith('.py'):
                test_files.append(os.path.join(root, file))
            elif file == 'test_app.py' and 'tests' in root:
                test_files.append(os.path.join(root, file))
    return test_files


def run_function_tests(function_name, coverage=False):
    """Run tests for a specific function"""
    test_dir = f"{function_name}/tests"
    if not os.path.exists(test_dir):
        print(f"No tests found for {function_name}")
        return False
    
    cmd = f"python -m pytest {test_dir} -v"
    if coverage:
        cmd += f" --cov={function_name} --cov-report=term-missing --cov-report=html:coverage_html/{function_name}"
    
    return run_command(cmd)


def run_all_tests(coverage=False, fail_under=80):
    """Run all tests in the project"""
    print("🧪 Running all tests for anecdotario-commons-service")
    print("=" * 60)
    
    # Discover all Lambda functions with tests
    functions_with_tests = []
    for item in os.listdir('.'):
        test_path = os.path.join(item, 'tests')
        if os.path.isdir(item) and os.path.exists(test_path):
            functions_with_tests.append(item)
    
    print(f"Found functions with tests: {functions_with_tests}")
    
    # Run simple verification test first
    print("\n🔧 Running infrastructure verification...")
    if not run_command("python -m pytest test_simple.py -v"):
        print("❌ Infrastructure test failed!")
        return False
    print("✅ Infrastructure test passed")
    
    # Run tests for each function
    all_passed = True
    results = {}
    
    for func in functions_with_tests:
        print(f"\n📁 Testing {func}...")
        try:
            success = run_function_tests(func, coverage)
            results[func] = "✅ PASSED" if success else "❌ FAILED"
            if not success:
                all_passed = False
        except Exception as e:
            print(f"Error testing {func}: {e}")
            results[func] = f"❌ ERROR: {e}"
            all_passed = False
    
    # Generate overall coverage report if requested
    if coverage:
        print("\n📊 Generating overall coverage report...")
        cmd = f"python -m pytest --cov=. --cov-report=html:coverage_html/overall --cov-report=term-missing --cov-fail-under={fail_under}"
        run_command(cmd)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    for func, result in results.items():
        print(f"{func:<20} {result}")
    
    if coverage:
        print(f"\n📊 Coverage reports generated in coverage_html/")
        print(f"   - Overall: coverage_html/overall/index.html")
        for func in functions_with_tests:
            if os.path.exists(f"coverage_html/{func}"):
                print(f"   - {func}: coverage_html/{func}/index.html")
    
    status = "🎉 ALL TESTS PASSED!" if all_passed else "💥 SOME TESTS FAILED!"
    print(f"\n{status}")
    
    return all_passed


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run tests for anecdotario-commons-service")
    parser.add_argument("--function", "-f", help="Run tests for specific function only")
    parser.add_argument("--coverage", "-c", action="store_true", help="Generate coverage reports")
    parser.add_argument("--fail-under", type=int, default=80, help="Coverage threshold (default: 80%)")
    parser.add_argument("--list", "-l", action="store_true", help="List all available test files")
    
    args = parser.parse_args()
    
    if args.list:
        print("📁 Available test files:")
        test_files = discover_test_files()
        for file in sorted(test_files):
            print(f"  {file}")
        return
    
    if args.function:
        success = run_function_tests(args.function, args.coverage)
        sys.exit(0 if success else 1)
    else:
        success = run_all_tests(args.coverage, args.fail_under)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()