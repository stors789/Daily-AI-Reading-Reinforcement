#!/usr/bin/env python3
"""Run the Android production-edge JVM tests without an Android SDK.

The standalone Gradle project compiles the actual production bridge,
dispatcher, and repository source files.  It intentionally does not apply the
Android Gradle plugin.  The first run may resolve pinned Kotlin/JUnit/JSON
artifacts from public repositories; no untracked local cache is assumed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping, Sequence


ANDROID_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ANDROID_ROOT / "jvm-tests"
RESULTS_DIR = PROJECT_DIR / "build" / "test-results" / "test"
EXPECTED_TESTS = 7
SUPPORTED_GRADLE = frozenset({(8, 10, 2), (9, 6, 1)})


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", value.strip())
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def java_major(version_output: str) -> int | None:
    match = re.search(r'(?:java|openjdk) version "?(\d+)(?:[._])', version_output, re.IGNORECASE)
    return int(match.group(1)) if match else None


def gradle_version(version_output: str) -> tuple[int, int, int] | None:
    match = re.search(r"(?m)^Gradle\s+([^\s]+)", version_output)
    return _version_tuple(match.group(1)) if match else None


def java17_candidates(explicit: str | None, environ: Mapping[str, str]) -> list[Path]:
    candidates: list[Path] = []
    for value in (
        explicit,
        environ.get("JAVA_HOME"),
        "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home",
        "/usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home",
        "/usr/lib/jvm/java-17-openjdk-amd64",
        "/usr/lib/jvm/java-17-openjdk-arm64",
    ):
        if value:
            path = Path(value).expanduser()
            if path not in candidates:
                candidates.append(path)
    return candidates


def discover_java17(
    explicit: str | None,
    environ: Mapping[str, str],
    *,
    candidates: Sequence[Path] | None = None,
) -> tuple[Path, str] | None:
    for home in candidates or java17_candidates(explicit, environ):
        executable = home / "bin" / ("java.exe" if os.name == "nt" else "java")
        if not executable.is_file():
            continue
        try:
            result = subprocess.run(
                [str(executable), "-version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode == 0 and java_major(output) == 17:
            return home, output.strip()
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gradle",
        default="gradle",
        help="Gradle executable supplied by the developer or CI (default: gradle on PATH).",
    )
    parser.add_argument(
        "--java-home",
        help="Optional JDK 17 home. JAVA_HOME and common Homebrew/OpenJDK paths are also checked.",
    )
    return parser.parse_args()


def count_results(results_dir: Path = RESULTS_DIR) -> tuple[int, int, int]:
    reports = sorted(results_dir.glob("TEST-*.xml"))
    if not reports:
        raise RuntimeError(f"no JUnit XML reports found under {results_dir}")
    tests = failures = errors = 0
    for report in reports:
        suite = ET.parse(report).getroot()
        tests += int(suite.attrib.get("tests", "0"))
        failures += int(suite.attrib.get("failures", "0"))
        errors += int(suite.attrib.get("errors", "0"))
    return tests, failures, errors


def main() -> int:
    args = parse_args()
    gradle = shutil.which(args.gradle)
    if gradle is None:
        print(
            "Android SDK-free JVM tests require Gradle 8.10.2 on PATH. "
            "CI installs that exact version with gradle/actions/setup-gradle.",
            file=sys.stderr,
        )
        return 2
    java = discover_java17(args.java_home, os.environ)
    if java is None:
        print(
            "Android SDK-free JVM tests require JDK 17. Set JAVA_HOME (or "
            "--java-home) to a JDK 17 installation; on Apple Silicon Homebrew "
            "this is usually /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home.",
            file=sys.stderr,
        )
        return 2
    java_home, java_output = java
    environment = {
        **os.environ,
        "JAVA_HOME": str(java_home),
        "GRADLE_USER_HOME": os.environ.get(
            "GRADLE_USER_HOME",
            str(PROJECT_DIR / ".gradle-user-home"),
        ),
    }
    version_result = subprocess.run(
        [gradle, "--version"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    detected_gradle = gradle_version(f"{version_result.stdout}\n{version_result.stderr}")
    if (
        version_result.returncode != 0
        or detected_gradle is None
        or detected_gradle not in SUPPORTED_GRADLE
    ):
        rendered = ".".join(str(part) for part in detected_gradle) if detected_gradle else "unknown"
        print(
            f"Android SDK-free JVM tests support Gradle 8.10.2 or 9.6.1; found {rendered}. "
            "Install one of those versions; CI uses the canonical Gradle 8.10.2 toolchain.",
            file=sys.stderr,
        )
        return 2
    java_label = java_output.splitlines()[0] if java_output else "JDK 17"
    print(
        f"Android SDK-free toolchain: Gradle {'.'.join(map(str, detected_gradle))}; "
        f"JAVA_HOME={java_home} ({java_label}).",
        flush=True,
    )
    result = subprocess.run(
        [gradle, "--no-daemon", "--project-dir", str(PROJECT_DIR), "cleanTest", "test"],
        cwd=ANDROID_ROOT.parent.parent,
        env=environment,
        check=False,
    )
    if result.returncode != 0:
        return int(result.returncode)
    tests, failures, errors = count_results()
    if tests != EXPECTED_TESTS or failures or errors:
        print(
            f"Expected exactly {EXPECTED_TESTS} passing Android JVM tests; "
            f"found tests={tests}, failures={failures}, errors={errors}.",
            file=sys.stderr,
        )
        return 1
    print(f"Android SDK-free JVM tests passed: {tests}/{EXPECTED_TESTS}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
