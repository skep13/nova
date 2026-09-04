"""Catch names used in a module that the module never defines.

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
           "filters.py",
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
    # The module dunders Python provides to every file.
    known = module_names(tree) | set(dir(builtins)) | {
        "__file__", "__name__", "__doc__", "__package__", "__spec__",
        "__loader__", "__builtins__", "__debug__"}

    missing = []
    for node in ast.walk(tree):
        # Every name READ but never bound, not just called ones.
        #
        # This checked calls only at first, on the reasoning that an undefined
        # bare name is an error Python raises at import anyway. It is not: a
        # module-level regex used inside a function is read at CALL time, so
        # moving strip_closing_offer into filters.py while leaving
        # _CLOSING_OFFER behind produced a module that imported cleanly, passed
        # its own 27-case suite, and failed five tests an hour later with the
        # whole stack up. _CLOSING_OFFER.sub() is an attribute call, so the
        # call-only version could not see it either.
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in known:
                missing.append((node.lineno, node.id))

    for line, name in sorted(set(missing)):
        print(f"  [FAIL] {path}:{line}  uses {name}, which is not defined here")
    return len(set(missing))


if __name__ == "__main__":
    targets = sys.argv[1:] or [f for f in DEFAULT if pathlib.Path(f).exists()]
    bad = sum(check(t) for t in targets)
    print(f"\n  {len(targets)} files checked, "
          + (f"{bad} undefined name(s)" if bad else "no undefined names"))
    sys.exit(bad)
