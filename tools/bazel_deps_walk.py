#!/usr/bin/env python3
"""Textual Bazel dependency walker.

Walks transitive in-repo deps of a Bazel target (default
//backend/schema/updater:schema_updater) by regex-parsing BUILD files and
reports every dependency path that reaches a //third_party/spanner_pg label.

Usage:
  bazel_deps_walk.py [--root REPO] [--start LABEL] [--forbidden PREFIX]
                     [--all-edges]
"""
import argparse
import os
import re
import sys
from collections import deque

# Matches a rule invocation body (balanced parentheses handled roughly).
RULE_RE = re.compile(r"^(\w+)\(\s*$", re.M)
NAME_RE = re.compile(r'\bname\s*=\s*"([^"]+)"')
LABEL_RE = re.compile(r'"((?://|:|@)[^"]*)"')
DEP_ATTRS = ("deps", "exports", "implementation_deps", "runtime_deps")


def split_rules(text):
    """Yield (kind, body) for each top-level rule call in a BUILD file."""
    i = 0
    n = len(text)
    while i < n:
        m = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(").search(text, i)
        if not m:
            return
        kind = m.group(1)
        depth = 0
        j = m.end() - 1
        start = j
        in_str = None
        while j < n:
            c = text[j]
            if in_str:
                if c == "\\":
                    j += 1
                elif c == in_str:
                    in_str = None
            elif c in "\"'":
                in_str = c
            elif c == "#":
                while j < n and text[j] != "\n":
                    j += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        body = text[start:j + 1]
        yield kind, body
        i = j + 1


def attr_block(body, attr):
    """Return raw text of `attr = <expr>` (up to matching bracket/paren)."""
    m = re.search(r"\b%s\s*=\s*" % attr, body)
    if not m:
        return None
    j = m.end()
    depth = 0
    start = j
    in_str = None
    while j < len(body):
        c = body[j]
        if in_str:
            if c == "\\":
                j += 1
            elif c == in_str:
                in_str = None
        elif c in "\"'":
            in_str = c
        elif c in "[({":
            depth += 1
        elif c in "])}":
            depth -= 1
            if depth <= 0:
                j += 1
                break
        elif c == "," and depth == 0:
            break
        j += 1
    return body[start:j]


def normalize(label, pkg):
    if label.startswith("@"):
        return None
    if label.startswith(":"):
        return "//%s%s" % (pkg, label)
    if label.startswith("//"):
        if ":" not in label:
            label = label + ":" + label.rsplit("/", 1)[-1]
        return label
    return None


def load_package(root, pkg, cache):
    if pkg in cache:
        return cache[pkg]
    rules = {}
    for fn in ("BUILD", "BUILD.bazel"):
        p = os.path.join(root, pkg, fn)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
            for kind, body in split_rules(text):
                nm = NAME_RE.search(body)
                if not nm:
                    continue
                deps = []
                for attr in DEP_ATTRS:
                    blk = attr_block(body, attr)
                    if blk:
                        deps.extend(LABEL_RE.findall(blk))
                # proto_library "deps" and cc_proto_library "deps" are covered.
                rules[nm.group(1)] = (kind, [normalize(d, pkg) for d in deps])
            break
    cache[pkg] = rules
    return rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--start", default="//backend/schema/updater:schema_updater")
    ap.add_argument("--forbidden", default="//third_party/spanner_pg")
    ap.add_argument("--all-edges", action="store_true",
                    help="print every visited edge")
    args = ap.parse_args()

    cache = {}
    parent = {args.start: None}
    q = deque([args.start])
    visited_targets = []
    forbidden_hits = []
    missing = []
    while q:
        label = q.popleft()
        visited_targets.append(label)
        if label.startswith(args.forbidden):
            forbidden_hits.append(label)
            continue  # do not descend into third_party/spanner_pg
        pkg, _, name = label[2:].partition(":")
        rules = load_package(args.root, pkg, cache)
        if name not in rules:
            missing.append(label)
            continue
        kind, deps = rules[name]
        for d in deps:
            if d is None:
                continue
            if args.all_edges:
                print("%s -> %s" % (label, d))
            if d not in parent:
                parent[d] = label
                q.append(d)

    print("start: %s" % args.start)
    print("visited in-repo targets: %d" % len(visited_targets))
    if missing:
        print("unresolved labels (no rule found, %d):" % len(missing))
        for m in missing:
            print("  %s  (via %s)" % (m, parent[m]))
    print("forbidden (%s) labels reached: %d" % (args.forbidden, len(forbidden_hits)))
    for hit in forbidden_hits:
        chain = []
        cur = hit
        while cur is not None:
            chain.append(cur)
            cur = parent[cur]
        print("  " + " <- ".join(chain))
    # Also list which first-party targets directly depend on forbidden labels
    # (all edges, not just the BFS discovery edge).
    direct = {}
    for label in visited_targets:
        if label.startswith(args.forbidden):
            continue
        pkg, _, name = label[2:].partition(":")
        rules = load_package(args.root, pkg, cache)
        if name not in rules:
            continue
        for d in rules[name][1]:
            if d and d.startswith(args.forbidden):
                direct.setdefault(label, []).append(d)
    if direct:
        print("first-party targets with direct forbidden deps:")
        for t in sorted(direct):
            print("  %s" % t)
            for h in direct[t]:
                print("      %s" % h)
    return 1 if forbidden_hits else 0


if __name__ == "__main__":
    sys.exit(main())
