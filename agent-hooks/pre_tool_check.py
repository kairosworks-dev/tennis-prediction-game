#!/usr/bin/env python3
"""Flag policy for the coding agent's `git commit` (called by claude-pre-tool.sh).

Reads the PreToolUse JSON on stdin. Exit 2 (reason on stderr) refuses; exit 0
allows. It inspects only the arguments of a `git commit` segment, never option
values, and never reads the index or file contents: content is the job of git's
own pre-commit hook (commit-gate.sh).

It is a guardrail against skipping git's hook by accident, not a security
boundary. Wrappers (`bash -c`, `eval`, `env`, ...), `$(...)`, inline git
configuration and aliases are followed; variable indirection, pipes into a
shell and the like are documented limits (agent-hooks/README.md).
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

ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GIT_ENV = re.compile(r"^(GIT_CONFIG_COUNT|GIT_CONFIG_KEY_\d+|GIT_CONFIG_VALUE_\d+|"
                     r"GIT_CONFIG_PARAMETERS|GIT_CONFIG_GLOBAL|GIT_CONFIG_SYSTEM|GIT_DIR)=")
# wrapper word -> its options that take a value
WRAPPERS = {
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "command": set(), "builtin": set(), "nohup": set(), "setsid": set(),
    "exec": {"-a"}, "nice": {"-n"}, "time": {"-f", "-o"},
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U", "-r", "-t"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "xargs": {"-I", "-n", "-L", "-P", "-d", "-E", "-s", "-a"},
}
KEYWORDS = {"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until"}
ASSIGN_BUILTINS = {"export", "declare", "typeset", "readonly", "local"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
MAX_DEPTH = 3
CONFIG_READ_ONLY = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "-l", "--list",
                    "--show-origin", "--show-scope", "--name-only"}


def refuse(msg):
    print("commit-gate: " + msg, file=sys.stderr)
    sys.exit(2)


class State:
    def __init__(self):
        self.found = False        # a commit (direct or via an alias) was seen
        self.findings = []        # overrides that matter only if a commit is found
        self.aliases = {}         # alias name -> expansion, defined within the command
        self.alias_cache = {}


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


def unwrap_substitutions(line):
    """Turn unquoted `...` and $(...) into command separators so their content
    is checked as commands. Quoted text is left alone."""
    out, quote, i = [], None, 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(line):
                i += 1
                out.append(line[i])
            elif ch == quote:
                quote = None
        elif ch == "\\" and i + 1 < len(line):
            out.append(ch + line[i + 1])
            i += 1
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        elif ch == "`":
            out.append(" ; ")
        elif ch == "$" and line[i + 1:i + 2] == "(":
            out.append(" ( ")
            i += 1
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def segments(line):
    lex = shlex.shlex(unwrap_substitutions(line), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    seg = []
    for t in lex:
        if t in SEPARATORS or set(t) <= set("()"):
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def check_config(value, shown, st):
    key, _, val = value.partition("=")
    if key.lower() == "core.hookspath":
        refuse(f"'{shown}' overrides core.hooksPath, which would bypass the commit gate.")
    if key.lower().startswith("alias."):
        st.aliases[key[6:]] = val


def git_verb(seg, st):
    """Return (index, verb) of the first non-option token after `git`."""
    i = 1
    while i < len(seg):
        t = seg[i]
        if not t.startswith("-"):
            return i, t
        name, eq, val = t.partition("=")
        if t == "-c" or name == "--config-env":
            if eq:
                check_config(val, t, st)
                i += 1
            else:
                if i + 1 < len(seg):
                    check_config(seg[i + 1], f"{t} {seg[i + 1]}", st)
                i += 2
        elif t.startswith("-c") and not t.startswith("--"):   # -ckey=value
            check_config(t[2:], t, st)
            i += 1
        elif name in GLOBAL_VALUE_OPTS and not eq:
            i += 2
        else:
            i += 1
    return None, None


def repo_alias(name, st):
    """The alias value from the git configuration of the checkout holding this hook."""
    if name not in st.alias_cache:
        here = os.path.dirname(os.path.realpath(__file__))
        r = subprocess.run(["git", "-C", here, "config", "--get", "alias." + name],
                           capture_output=True, text=True)
        st.alias_cache[name] = r.stdout.strip() if r.returncode == 0 else ""
    return st.alias_cache[name]


def resolve_alias(verb, rest, st):
    """Return the arguments of the commit that `git verb rest` expands to, or None."""
    for _ in range(5):
        if verb == "commit":
            return rest
        exp = st.aliases.get(verb) or repo_alias(verb, st)
        if not exp or exp.startswith("!"):
            return None
        words = shlex.split(exp)
        if not words:
            return None
        verb, rest = words[0], words[1:] + rest
    return None


def note_config_write(seg, vi, st):
    """`git config`: record alias definitions, flag writes to core.hooksPath."""
    args = seg[vi + 1:]
    if any(a in CONFIG_READ_ONLY for a in args):
        return
    pos = [a for a in args if not a.startswith("-")]
    if pos and pos[0] in ("set", "unset"):
        pos, writing = pos[1:], True
    else:
        writing = len(pos) > 1 or any(a.startswith(("--unset", "--replace", "--add")) for a in args)
    if not writing or not pos:
        return
    if pos[0].lower() == "core.hookspath":
        st.findings.append(f"'git config {pos[0]}' changes core.hooksPath, "
                           "which would bypass the commit gate.")
    elif pos[0].lower().startswith("alias.") and len(pos) > 1:
        st.aliases[pos[0][6:]] = pos[1]


def note_assignment(t, st):
    if GIT_ENV.match(t):
        name = t.split("=", 1)[0]
        st.findings.append(f"'{name}=' overrides git's configuration and could "
                           "bypass the commit gate.")


def check_segment(seg, st, depth):
    i = 0
    while i < len(seg):
        t = seg[i]
        base = os.path.basename(t)
        if ASSIGN.match(t):
            note_assignment(t, st)
            i += 1
        elif t in KEYWORDS:
            i += 1
        elif base in ASSIGN_BUILTINS:
            for a in seg[i + 1:]:
                note_assignment(a, st)
            return
        elif base in WRAPPERS:
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                i += 2 if seg[i] in WRAPPERS[base] else 1
            if base == "timeout" and i < len(seg):
                i += 1  # the DURATION positional
        else:
            break
    rest = seg[i:]
    if not rest:
        return
    base = os.path.basename(rest[0])
    if base in SHELLS:
        for j, t in enumerate(rest[1:], 1):
            if not t.startswith("-"):
                break
            if not t.startswith("--") and "c" in t and j + 1 < len(rest):
                check_command(rest[j + 1], st, depth + 1)
                break
    elif base == "eval":
        check_command(" ".join(rest[1:]), st, depth + 1)
    elif base == "git":
        vi, verb = git_verb(rest, st)
        if verb is None:
            return
        if verb == "config":
            note_config_write(rest, vi, st)
        args = resolve_alias(verb, rest[vi + 1:], st)
        if args is not None:
            st.found = True
            inspect_commit(args)


def check_command(cmd, st, depth):
    if depth > MAX_DEPTH:
        refuse(f"shell wrappers (bash -c, eval) nested deeper than {MAX_DEPTH} levels; refusing.")
    for line in split_lines(cmd):
        try:
            segs = list(segments(line))
        except ValueError as e:
            if re.search(r"\bgit\b", line):
                refuse(f"could not parse a command mentioning git ({e}); refusing.")
            continue
        for seg in segs:
            check_segment(seg, st, depth)


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
    st = State()
    check_command(cmd, st, 0)
    if st.found and st.findings:
        refuse(st.findings[0])
    if st.found and not hooks_enabled():
        refuse("git's pre-commit hook is not enabled in this clone, so the content "
               "gate would be off. Run `make hooks` first.")


main()
