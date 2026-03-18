import sys
import py_compile

try:
    py_compile.compile('django/scraper/views.py', doraise=True)
    print("✓ Syntax check passed: django/scraper/views.py")
    sys.exit(0)
except py_compile.PyCompileError as e:
    print(f"✗ Syntax error: {e}")
    sys.exit(1)
