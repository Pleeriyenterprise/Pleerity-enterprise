"""Parse pytest junitxml into failure counts by test module (for triage)."""
from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("junit_path", default="pytest_junit.xml", nargs="?")
    args = p.parse_args()

    root = ET.parse(args.junit_path).getroot()
    by_class_prefix: dict[str, dict[str, int]] = defaultdict(lambda: {"failure": 0, "error": 0})

    for tc in root.iter("testcase"):
        classname = tc.get("classname") or ""
        kind = None
        for child in tc:
            if child.tag in ("failure", "error"):
                kind = child.tag
                break
        if not kind:
            continue
        # e.g. tests.test_reporting.TestFoo -> test_reporting
        if classname.startswith("tests."):
            rest = classname[6:]
        else:
            rest = classname
        prefix = rest.split(".")[0] if rest else "unknown"
        by_class_prefix[prefix][kind] += 1

    rows = sorted(
        by_class_prefix.items(),
        key=lambda x: -(x[1]["failure"] + x[1]["error"]),
    )
    print("failures+errors by tests.test_<module> prefix:\n")
    total_f = total_e = 0
    for name, c in rows:
        f, e = c["failure"], c["error"]
        if f + e == 0:
            continue
        total_f += f
        total_e += e
        print(f"  {name}: failure={f} error={e} total={f+e}")
    print(f"\nTOTAL failure={total_f} error={total_e} sum={total_f+total_e}")


if __name__ == "__main__":
    main()
