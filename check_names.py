"""Catch calls to functions that do not exist in the module that calls them.

Written after `log(...)` was used in remote_proxy.py, where it does not exist —
it is nova_bridge.py's convention, copied across without noticing. The call sat
inside an `except` block, so nothing ran it until an escalation actually
failed, and then the ERROR HANDLER raised NameError and turned a degraded
answer into an HTTP 500. The feature had been deployed and smoke-tested; the
path that broke was the one that only runs when something else has already
gone wrong.

That is the shape of every bug worth a static check: silent at import, silent
in the happy path, and waiting in the handler you wrote to make things safer.

Python will not tell you at compile time and there is no linter on this box, so
this is a small one. It resolves every called name against the module's own
globals, its imports, its builtins and the local scope of the enclosing
function, and reports what is left.

    python3 check_names.py [file.py ...]

Exit code is the number of unresolved names.
"""
import ast
import builtins
import pathlib
import sys

DEFAULT = ["remote_proxy.py", "nova_bridge.py", "timeparse.py", "arith.py",
           "persona.py", "eval_models.py", "extract_persona.py"]


def module_names(tree):
    """Everything defined at module level: functions, classes, assignments."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.Global):
            names.update(node.names)
        # Comprehension and with/for targets bind names too.
        elif isinstance(node, ast.comprehension):
            for t in ast.walk(node.target):
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.withitem)):
            target = getattr(node, "target", None) or getattr(node, "optional_vars", None)
            for t in ast.walk(target) if target else []:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return names


def check(path):
    src = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    known = module_names(tree) | set(dir(builtins))

    missing = []
    for node in ast.walk(tree):
        # Only CALLS. An undefined bare name is usually a typo in a comment-like
        # context or a genuine error Python would raise on import; an undefined
        # CALL is the one that hides in a branch nobody runs.
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not isinstance(fn, ast.Name):
            continue          # obj.method() is resolved at runtime; not our job
        if fn.id not in known:
            missing.append((fn.lineno, fn.id))

    for line, name in sorted(set(missing)):
        print(f"  [FAIL] {path}:{line}  calls {name}() which is not defined here")
    return len(set(missing))


if __name__ == "__main__":
    targets = sys.argv[1:] or [f for f in DEFAULT if pathlib.Path(f).exists()]
    bad = sum(check(t) for t in targets)
    print(f"\n  {len(targets)} files checked, "
          + (f"{bad} undefined call(s)" if bad else "no undefined calls"))
    sys.exit(bad)
