#!/usr/bin/env python
"""
Nice test runner - shows each test with status.
Just use: python manage.py test --verbosity=2
This script is a convenience wrapper.
"""
import sys
import os
import subprocess
from pathlib import Path

if __name__ == '__main__':
    # Change to project root directory (parent of scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    test_args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    print("\n" + "=" * 70)
    print("🧪 RUNNING TESTS")
    print("=" * 70 + "\n")
    
    # Run with verbosity=2 which shows test names
    cmd = ['python', 'manage.py', 'test', '--verbosity=2'] + test_args
    sys.exit(subprocess.run(cmd).returncode)
