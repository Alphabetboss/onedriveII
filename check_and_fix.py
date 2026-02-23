#!/usr/bin/env python3
r"""
check_and_fix.py

Usage:
  # just run checks (no file changes)
  python check_and_fix.py --check

  # run checks and then attempt autofixes (ruff --fix + black)
  python check_and_fix.py --fix

This script:
 - compiles every .py file to detect syntax errors (py_compile)
 - searches file text for problematic escape patterns like "\U", "\u", "\x" in source
 - optionally runs ruff --fix and black . to apply common fixes
 - creates a timestamped backup of all .py files before applying fixes
"""
import argparse, os, sys, py_compile, compileall, subprocess, shutil, re, time
from pathlib import Path

ROOT = Path(".").resolve()
EXCLUDE_DIRS = {".venv", "venv", ".git", "__pycache__"}

def list_py_files():
    for p in ROOT.rglob("*.py"):
        # skip files in excluded directories
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        yield p

def compile_check():
    print("=== Syntax check (py_compile) ===")
    errors = []
    for p in list_py_files():
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as e:
            errors.append((p, e))
            print(f"[SYNTAX ERROR] {p}: {e.__class__.__name__}: {e}")
    if not errors:
        print("No syntax errors found.")
    return errors

def find_unicode_escape_patterns():
    print("\n=== Searching for suspicious backslash escape patterns in source ===")
    pattern = re.compile(r"\\[Uux]", re.IGNORECASE)  # matches \U, \u, \x
    found = []
    for p in list_py_files():
        text = p.read_text(encoding="utf8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                snippet = line.strip()
                print(f"[POTENTIAL ESCAPE] {p}:{i}: {snippet}")
                found.append((p, i, snippet))
    if not found:
        print("No suspicious backslash-escape patterns found.")
    return found

def run_tool(cmd, cwd=ROOT):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"

def run_lint_and_format(check_only=False):
    results = {}
    # ruff: fast linter + fixer
    rc, out, err = run_tool(["ruff", "--version"])
    if rc == 127:
        print("\n[INFO] ruff not installed. To install: pip install ruff")
        results['ruff'] = None
    else:
        print("\n=== Running ruff (lint) ===")
        if check_only:
            rc, out, err = run_tool(["ruff", "check", str(ROOT)])
            print(out or "(no ruff output)")
        else:
            print("Running ruff --fix ...")
            rc, out, err = run_tool(["ruff", "check", str(ROOT)])
            # try autofix if available
            rc2, out2, err2 = run_tool(["ruff", "format", str(ROOT)])
            # note: some ruff versions use 'ruff format' or 'ruff --fix' depending on version
            if rc2 == 127:
                rc2, out2, err2 = run_tool(["ruff", "--fix", str(ROOT)])
            print(out2 or "(no ruff fix output)")
        results['ruff'] = (rc, out, err)
    # black formatter
    rc, out, err = run_tool(["black", "--version"])
    if rc == 127:
        print("\n[INFO] black not installed. To install: pip install black")
        results['black'] = None
    else:
        print("\n=== Running black ===")
        if check_only:
            rc, out, err = run_tool(["black", "--check", str(ROOT)])
            print(out or "(black check output empty)")
        else:
            rc, out, err = run_tool(["black", str(ROOT)])
            print(out or "(black output empty)")
        results['black'] = (rc, out, err)
    return results

def make_backup(backup_dir):
    backup_dir.mkdir(parents=True, exist_ok=True)
    for p in list_py_files():
        dest = backup_dir / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    print(f"Backed up python files to {backup_dir}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Run checks only (no fixes)")
    ap.add_argument("--fix", action="store_true", help="Attempt auto-fixes (ruff --fix + black .) - will backup files first")
    args = ap.parse_args()

    print(f"Project root: {ROOT}")
    compile_errors = compile_check()
    escape_findings = find_unicode_escape_patterns()

    if args.fix:
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup_dir = ROOT / f"py_backups_{ts}"
        print("\nBacking up all .py files before applying fixes...")
        make_backup(backup_dir)
        print("\nAttempting auto-fixes using ruff and black (if installed).")
        results = run_lint_and_format(check_only=False)
        # re-run compile check to surface remaining syntax errors
        print("\nRe-running syntax check after fixes:")
        compile_errors_after = compile_check()
        print("\nDone. Inspect the backup directory if you want to revert.")
    else:
        # just run lint/format as check (no changes)
        results = run_lint_and_format(check_only=True)
        print("\nDone. Use --fix to attempt automatic fixes (will create backups).")

if __name__ == "__main__":
    main()
