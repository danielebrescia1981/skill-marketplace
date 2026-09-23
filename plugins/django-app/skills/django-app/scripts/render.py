#!/usr/bin/env python3
"""Render the django-app skeleton (or one file): resolve feature blocks, substitute placeholders.

    render.py assets/skeleton ~/code/acme --on tenant,help \
        --set myapp=acme MyApp=Acme __DB_PORT__=5437 __DEV_PORT__=8012 __SERVER__=devmo2

Block markers sit alone on a line, in any comment syntax (#, //, <!-- -->, {# #}):
    [tenant] ... [/tenant]     kept only when `tenant` is in --on
    [!tenant] ... [/!tenant]   kept only when `tenant` is NOT in --on
Marker lines are always dropped; blocks may nest. A file that renders to only
whitespace *because a disabled block removed its content* is not written, so wrapping a whole file in [tenant] makes it tenant-only.
Path segments starting with `dot-` become dotfiles (dot-gitignore → .gitignore).
--set pairs apply longest-key first (so `myapp.com` wins over `myapp`), to file
contents and to paths. Refuses to write into a non-empty DEST unless --force.
Exits non-zero if a block is unbalanced or a `__PLACEHOLDER__` survives.
"""

import argparse
from pathlib import Path
import re
import sys

# The comment prefix is mandatory, so TOML/INI table headers like `[project]` pass through.
MARKER = re.compile(r"^\s*(?:#|//|<!--|\{#)\s*\[(/?)(!?)([a-z]+)\]\s*(?:-->|#\})?\s*$")
PLACEHOLDER = re.compile(r"__[A-Z][A-Z_]*__")


def render(text: str, on: set[str], subs: dict[str, str]) -> str:
    return render_ex(text, on, subs)[0]


def render_ex(text: str, on: set[str], subs: dict[str, str]) -> tuple[str, bool]:
    """Rendered text, and whether any content was dropped by a disabled block."""
    out, stack, dropped = [], [], False  # stack of (feature, negated, keep)
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        m = MARKER.match(line)
        if m:
            closing, neg, feat = m.group(1) == "/", m.group(2) == "!", m.group(3)
            if closing:
                if not stack or stack[-1][:2] != (feat, neg):
                    raise ValueError(f"line {n}: unbalanced [/{'!' if neg else ''}{feat}]")
                stack.pop()
            else:
                keep = (feat in on) != neg
                dropped |= not keep  # a disabled block counts even when empty (marker-only __init__.py)
                stack.append((feat, neg, keep))
            continue
        if all(keep for *_, keep in stack):
            out.append(line)
        else:
            dropped = True
    if stack:
        raise ValueError(f"unclosed block [{stack[-1][0]}]")
    text = substitute("".join(out), subs)
    # Removed blocks can leave trailing blank lines; formatters want exactly one final newline.
    return (text.rstrip("\n") + "\n" if text.strip() else ""), dropped


def substitute(text: str, subs: dict[str, str]) -> str:
    for key in sorted(subs, key=len, reverse=True):
        text = text.replace(key, subs[key])
    return text


def dest_path(rel: Path, subs: dict[str, str]) -> Path:
    parts = ["." + p[4:] if p.startswith("dot-") else p for p in rel.parts]
    return Path(substitute(str(Path(*parts)), subs))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("src", type=Path)
    p.add_argument("dest", type=Path)
    p.add_argument("--on", default="", help="comma-separated features to enable")
    p.add_argument("--set", nargs="*", default=[], metavar="KEY=VALUE")
    p.add_argument("--force", action="store_true", help="write into a non-empty DEST")
    a = p.parse_args()
    on = {f for f in a.on.split(",") if f}
    subs = dict(pair.split("=", 1) for pair in a.set)

    if a.src.is_dir():
        if a.dest.exists() and any(a.dest.iterdir()) and not a.force:
            print(f"{a.dest} is not empty; pass --force to write into it", file=sys.stderr)
            return 1
        jobs = [(f, a.dest / dest_path(f.relative_to(a.src), subs)) for f in sorted(a.src.rglob("*")) if f.is_file()]
    else:
        jobs = [(a.src, a.dest)]

    leftovers = []
    for src, dest in jobs:
        try:
            result, dropped = render_ex(src.read_text(), on, subs)
        except ValueError as e:
            print(f"{src}: {e}", file=sys.stderr)
            return 1
        if dropped and not result.strip():
            continue  # everything was inside a disabled block
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(result)
        if src.stat().st_mode & 0o111:
            dest.chmod(0o755)
        leftovers += [f"{dest}: {ph}" for ph in sorted(set(PLACEHOLDER.findall(result)))]
    if leftovers:
        print("unfilled placeholders:\n  " + "\n  ".join(leftovers), file=sys.stderr)
        return 2
    return 0


def _selftest() -> None:
    src = "a\n# [x]\nb\n  # [!y]\nc\n  # [/!y]\n# [/x]\n<!-- [!x] -->\nd myapp.com myapp\n<!-- [/!x] -->\n{# [y] #}\ne\n{# [/y] #}\n"
    assert render(src, {"x"}, {}) == "a\nb\nc\n"
    assert render(src, {"x", "y"}, {}) == "a\nb\ne\n"
    assert render(src, set(), {"myapp": "acme", "myapp.com": "acme.io"}) == "a\nd acme.io acme\n"
    assert render_ex("# [x]\n# [/x]\n", {"x"}, {}) == ("", False)  # marker-only __init__.py, feature on: keep
    assert render_ex("# [x]\n# [/x]\n", set(), {}) == ("", True)  # ...feature off: skip
    assert render_ex("# [x]\nz\n# [/x]\n", set(), {}) == ("", True)
    assert render("a\n# [x]\nz\n# [/x]\n\n", set(), {}) == "a\n"  # trailing blanks trimmed
    assert render("[project]\n# [x]\n[tool]\n# [/x]\n", set(), {}) == "[project]\n"
    assert dest_path(Path("dot-github/workflows/ci.yml"), {}) == Path(".github/workflows/ci.yml")
    assert dest_path(Path("src/myapp/x.py"), {"myapp": "acme"}) == Path("src/acme/x.py")
    for bad in ("# [x]\n", "# [/x]\n", "# [x]\n# [/!x]\n"):
        try:
            render(bad, set(), {})
        except ValueError:
            continue
        raise AssertionError(f"accepted unbalanced input: {bad!r}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        _selftest()
        print("ok")
        sys.exit(0)
    sys.exit(main())
