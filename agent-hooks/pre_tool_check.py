#!/usr/bin/env python3
"""Flag policy for the coding agent's `git commit` (called by claude-pre-tool.sh).

Reads the PreToolUse JSON on stdin. Exit 2 (reason on stderr) refuses; exit 0
allows. It inspects only the arguments of a `git commit` segment, never option
values, and never reads the index or file contents: content is the job of git's
own pre-commit hook (commit-gate.sh).
"""
import json
import os
import re
import shlex
import subprocess
import sys

SEPARATORS = {"&&", "||", ";", "|", "&", ";;", "|&"}

# git global options that take a value as the next token (unless written --opt=value)
GLOBAL_VALUE_OPTS = {"-C", "--git-dir", "--work-tree", "--namespace",
                     "--super-prefix", "--attr-source"}

# git commit long options: name -> takes a value
LONG_OPTS = {
    "all": 0, "patch": 0, "reuse-message": 1, "reedit-message": 1, "fixup": 1,
    "squash": 1, "reset-author": 0, "short": 0, "branch": 0, "porcelain": 0,
    "long": 0, "null": 0, "file": 1, "author": 1, "date": 1, "message": 1,
    "template": 1, "signoff": 0, "no-signoff": 0, "trailer": 1, "no-verify": 0,
    "verify": 0, "allow-empty": 0, "allow-empty-message": 0, "cleanup": 1,
    "edit": 0, "no-edit": 0, "amend": 0, "include": 0, "only": 0,
    "pathspec-from-file": 1, "pathspec-file-nul": 0, "untracked-files": 0,
    "verbose": 0, "quiet": 0, "dry-run": 0, "status": 0, "no-status": 0,
    "gpg-sign": 0, "no-gpg-sign": 0, "interactive": 0, "no-post-rewrite": 0,
    "post-rewrite": 0,
}
# short options that take a value (the rest of the group, else the next token)
SHORT_VALUE = set("mFCct")
# short options with an optional, attached-only value (rest of the group)
SHORT_OPTIONAL = set("Su")


def refuse(msg):
    print("commit-gate: " + msg, file=sys.stderr)
    sys.exit(2)


def split_lines(cmd):
    """Split on newlines outside quotes; drop unquoted heredoc bodies."""
    lines, cur, quote, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(cmd):
                i += 1
                cur.append(cmd[i])
            elif ch == quote:
                quote = None
        elif ch == "\\" and i + 1 < len(cmd):
            cur.append(ch)
            i += 1
            cur.append(cmd[i])
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch == "\n":
            lines.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    lines.append("".join(cur))
    out, delim = [], None
    for line in lines:
        if delim is not None:
            if line.strip() == delim:
                delim = None
            continue
        out.append(line)
        m = re.search(r"<<-?\s*(['\"]?)(\w+)\1", line)
        if m:
            delim = m.group(2)
    return out


def segments(line):
    lex = shlex.shlex(line, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    seg = []
    for t in lex:
        if t in SEPARATORS:
            if seg:
                yield seg
            seg = []
        elif set(t) <= set("()"):
            continue
        else:
            seg.append(t)
    if seg:
        yield seg


def check_config(value, shown):
    if value.split("=", 1)[0].lower() == "core.hookspath":
        refuse(f"'{shown}' overrides core.hooksPath, which would bypass the commit gate.")


def commit_args(seg):
    """Return the args after `git ... commit`, or None if this is not a commit."""
    if os.path.basename(seg[0]) != "git":
        return None
    i = 1
    while i < len(seg):
        t = seg[i]
        if not t.startswith("-"):
            return seg[i + 1:] if t == "commit" else None
        name, eq, val = t.partition("=")
        if t == "-c" or name == "--config-env":
            if eq:
                check_config(val, t)
                i += 1
            else:
                if i + 1 < len(seg):
                    check_config(seg[i + 1], f"{t} {seg[i + 1]}")
                i += 2
        elif t.startswith("-c") and not t.startswith("--"):   # -ckey=value
            check_config(t[2:], t)
            i += 1
        elif name in GLOBAL_VALUE_OPTS and not eq:
            i += 2
        else:
            i += 1
    return None


def resolve_long(opt):
    name = opt[2:]
    if name in LONG_OPTS:
        return name
    hits = [k for k in LONG_OPTS if k.startswith(name)] if name else []
    return hits[0] if len(hits) == 1 else None


def inspect_commit(args):
    i = 0
    while i < len(args):
        t = args[i]
        i += 1
        if t == "--":
            return
        if t.startswith("--"):
            opt, eq, _ = t.partition("=")
            name = resolve_long(opt)
            if name == "no-verify":
                refuse(f"'{t}' is not allowed: it skips the commit gate.")
            if name and LONG_OPTS[name] and not eq:
                i += 1
        elif t.startswith("-") and len(t) > 1:
            for j, ch in enumerate(t[1:], 1):
                if ch == "n":
                    refuse(f"'{t}' is not allowed: -n is --no-verify and skips the commit gate.")
                if ch in SHORT_VALUE:
                    if j == len(t) - 1:
                        i += 1
                    break
                if ch in SHORT_OPTIONAL:
                    break


def hooks_enabled():
    here = os.path.dirname(os.path.realpath(__file__))

    def git(*a):
        r = subprocess.run(["git", "-C", here, *a], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""

    path = git("config", "--type=path", "--get", "core.hooksPath")
    if not path:
        return False
    if not os.path.isabs(path):
        path = os.path.join(git("rev-parse", "--show-toplevel"), path)
    return os.path.realpath(path) == here


def main():
    try:
        cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "") or ""
    except Exception:
        return
    found = False
    for line in split_lines(cmd):
        if not (re.search(r"\bgit\b", line) and re.search(r"\bcommit\b", line)):
            continue
        try:
            segs = list(segments(line))
        except ValueError as e:
            refuse(f"could not parse a command mentioning git commit ({e}); refusing.")
        for seg in segs:
            args = commit_args(seg)
            if args is None:
                continue
            found = True
            inspect_commit(args)
    if found and not hooks_enabled():
        refuse("git's pre-commit hook is not enabled in this clone, so the content "
               "gate would be off. Run `make hooks` first.")


main()
