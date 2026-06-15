import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import pytest
if __name__ == '__main__':
    raise SystemExit(pytest.main(['tests/test_patrol_planner.py','-q']))
