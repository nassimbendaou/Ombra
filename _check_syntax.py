import py_compile
import sys

files = [
    "agent_loop.py",
    "server.py",
    "autonomy_daemon.py",
    "telegram_router.py",
    "creative_exploration.py",
]

ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"[OK] {f}")
    except py_compile.PyCompileError as e:
        print(f"[FAIL] {f}: {e}")
        ok = False

if ok:
    print("\nAll files compile OK!")
else:
    print("\nSome files have errors!")
    sys.exit(1)
