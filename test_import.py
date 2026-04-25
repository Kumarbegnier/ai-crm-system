import sys
sys.path.insert(0, 'backend')
try:
    from app.agent import _classify_intent
    print("SUCCESS: _classify_intent imported")
except ImportError as e:
    print(f"FAIL: {e}")
except Exception as e:
    print(f"ERROR: {e}")

