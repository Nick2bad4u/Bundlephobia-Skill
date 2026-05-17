#!/usr/bin/env python3
"""Bundlephobia and local JavaScript package size helper."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


BUNDLEPHOBIA_BASE = "https://bundlephobia.com"
DEFAULT_SKIP_PATTERNS = [
    r"dotenv",
    r"gulp",
    r"cli",
    r"webpack",
    r"react-native",
    r"babel",
    r"rollup",
    r"autoprefixer",
    r"css-nano",
    r"node-sass",
    r"next",
    r"create-react-app",
    r"react-scripts",
    r"-loader",
    r"extract-plugin",
    r"jest",
    r"enzyme",
    r"mocha",
    r"ava",
    r"nightwatch",
    r"koa",
    r"express",
    r"pm2",
    r"nodemon",
    r"supervisor",
    r"prop-types",
    r"devtools",
]
DEFAULT_ARTIFACT_EXTENSIONS = {
    ".js",
    ".mjs",
    ".cjs",
    ".css",
    ".wasm",
    ".json",
    ".map",
}


class SizeCheckError(RuntimeError):
    """Raised for expected command or API failures."""


def request_json(url: str, *, timeout: int, attempts: int = 2) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "bundle-size-analysis-skill/1.0",
        "X-Bundlephobia-User": "bundle-size-analysis skill",
    }
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"error": {"code": str(error.code), "message": body or error.reason}}
            if error.code >= 500 and attempt < attempts:
                last_error = error
                retry_after = 0
                try:
                    retry_after = int(error.headers.get("Retry-After", "0"))
                except ValueError:
                    retry_after = 0
                time.sleep(max(retry_after, 1.5 * attempt))
                continue
            raise SizeCheckError(json.dumps(payload, ensure_ascii=False)) from error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(1.5 * attempt)
                continue
    raise SizeCheckError(f"request failed for {url}: {last_error}") from last_error


def bundlephobia_url(endpoint: str, package: str, extra: dict[str, Any] | None = None) -> str:
    package_query = f"package={urllib.parse.quote(package, safe='@/')}"
    if extra:
        extra_query = urllib.parse.urlencode(extra)
        return f"{BUNDLEPHOBIA_BASE}/api/{endpoint}?{package_query}&{extra_query}"
    return f"{BUNDLEPHOBIA_BASE}/api/{endpoint}?{package_query}"


def query_bundlephobia_package(
    package: str,
    *,
    timeout: int,
    include_exports: bool,
    include_dependencies: bool,
    include_history: int,
    include_similar: bool,
    record_search: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "package": package,
        "bundlephobiaUrl": f"{BUNDLEPHOBIA_BASE}/package/{package}",
    }
    try:
        extra = {"record": "true"} if record_search else None
        result["size"] = request_json(
            bundlephobia_url("size", package, extra),
            timeout=timeout,
        )
    except SizeCheckError as error:
        result["error"] = parse_api_error(str(error))
        return result

    optional_endpoints = [
        ("exports", include_exports, "exports", None),
        ("exportsSizes", include_exports, "exports-sizes", None),
        ("dependencies", include_dependencies, "dependencies", None),
        ("history", include_history > 0, "package-history", {"limit": include_history}),
        ("similar", include_similar, "similar-packages", None),
    ]
    for key, enabled, endpoint, extra in optional_endpoints:
        if not enabled:
            continue
        try:
            result[key] = request_json(bundlephobia_url(endpoint, package, extra), timeout=timeout)
        except SizeCheckError as error:
            result[f"{key}Error"] = parse_api_error(str(error))
    return result


def parse_api_error(message: str) -> dict[str, Any]:
    try:
        parsed = json.loads(message)
        if isinstance(parsed, dict):
            return parsed.get("error", parsed)
    except json.JSONDecodeError:
        pass
    return {"code": "RequestError", "message": message}


def read_package_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SizeCheckError(f"package.json not found: {path}") from error
    except json.JSONDecodeError as error:
        raise SizeCheckError(f"invalid package.json at {path}: {error}") from error


def packages_from_package_json(
    path: Path,
    *,
    include_dev: bool,
    include_optional: bool,
    skip_patterns: list[str],
) -> list[str]:
    data = read_package_json(path)
    sections = ["dependencies"]
    if include_optional:
        sections.append("optionalDependencies")
    if include_dev:
        sections.append("devDependencies")

    compiled = [re.compile(pattern) for pattern in skip_patterns]
    packages: list[str] = []
    seen: set[str] = set()
    for section in sections:
        deps = data.get(section, {})
        if not isinstance(deps, dict):
            continue
        for name, range_text in sorted(deps.items()):
            if any(pattern.search(name) for pattern in compiled):
                continue
            if not isinstance(range_text, str) or is_non_registry_spec(range_text):
                continue
            spec = name if range_text in {"*", "latest"} else f"{name}@{range_text}"
            if spec not in seen:
                packages.append(spec)
                seen.add(spec)
    return packages


def is_non_registry_spec(spec: str) -> bool:
    return bool(
        spec.startswith(("file:", "link:", "workspace:", "git+", "github:", "http:", "https:"))
    )


def query_many_packages(packages: list[str], args: argparse.Namespace) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = {
            executor.submit(
                query_bundlephobia_package,
                package,
                timeout=args.timeout,
                include_exports=args.exports,
                include_dependencies=args.dependencies,
                include_history=args.history,
                include_similar=args.similar,
                record_search=args.record_search,
            ): package
            for package in packages
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["package"].lower())
    return summarize_package_results(results)


def summarize_package_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [item for item in results if "size" in item]
    failed = [item for item in results if "error" in item]
    total_size = sum(int(item["size"].get("size") or 0) for item in ok)
    total_gzip = sum(int(item["size"].get("gzip") or 0) for item in ok)
    return {
        "kind": "bundlephobia",
        "summary": {
            "packageCount": len(results),
            "successful": len(ok),
            "failed": len(failed),
            "totalMinifiedBytes": total_size,
            "totalGzipBytes": total_gzip,
        },
        "packages": results,
    }


def run_npm_pack(repo: Path) -> dict[str, Any]:
    command = ["npm", "pack", "--json", "--dry-run"]
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError as error:
        raise SizeCheckError("npm was not found on PATH") from error
    if completed.returncode != 0:
        raise SizeCheckError(completed.stderr.strip() or completed.stdout.strip() or "npm pack failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SizeCheckError(f"npm pack returned invalid JSON: {completed.stdout}") from error
    if not isinstance(payload, list) or not payload:
        raise SizeCheckError("npm pack returned no package metadata")
    pack = payload[0]
    files = pack.get("files") if isinstance(pack, dict) else None
    if not isinstance(files, list):
        files = []
    largest_files = sorted(
        [
            {"path": item.get("path"), "size": item.get("size", 0)}
            for item in files
            if isinstance(item, dict)
        ],
        key=lambda item: int(item.get("size") or 0),
        reverse=True,
    )[:20]
    return {
        "kind": "npmPack",
        "repo": str(repo),
        "name": pack.get("name"),
        "version": pack.get("version"),
        "filename": pack.get("filename"),
        "packedBytes": pack.get("size"),
        "unpackedBytes": pack.get("unpackedSize"),
        "fileCount": len(files),
        "largestFiles": largest_files,
    }


def measure_artifacts(paths: list[Path], extensions: set[str]) -> dict[str, Any]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())
    measured = []
    for file_path in files:
        if extensions and file_path.suffix.lower() not in extensions:
            continue
        try:
            data = file_path.read_bytes()
        except OSError:
            continue
        measured.append(
            {
                "path": str(file_path),
                "bytes": len(data),
                "gzipBytes": len(gzip.compress(data, compresslevel=9)),
            }
        )
    measured.sort(key=lambda item: int(item["gzipBytes"]), reverse=True)
    return {
        "kind": "artifacts",
        "summary": {
            "fileCount": len(measured),
            "totalBytes": sum(item["bytes"] for item in measured),
            "totalGzipBytes": sum(item["gzipBytes"] for item in measured),
        },
        "files": measured[:50],
    }


def default_artifact_paths(repo: Path) -> list[Path]:
    candidates = ["dist", "build", "lib", "esm", "es", "cjs"]
    return [repo / candidate for candidate in candidates if (repo / candidate).exists()]


def format_bytes(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "n/a"
    units = ["B", "kB", "MB", "GB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    if index == 0:
        return f"{int(size)} {units[index]}"
    return f"{size:.1f} {units[index]}"


def print_text(payload: dict[str, Any]) -> None:
    kind = payload.get("kind")
    if kind == "bundlephobia":
        summary = payload["summary"]
        print(
            "Bundlephobia: "
            f"{summary['successful']}/{summary['packageCount']} successful, "
            f"total min {format_bytes(summary['totalMinifiedBytes'])}, "
            f"total gzip {format_bytes(summary['totalGzipBytes'])}"
        )
        for item in sorted(
            payload["packages"],
            key=lambda row: int(row.get("size", {}).get("gzip") or -1),
            reverse=True,
        ):
            if "error" in item:
                error = item["error"]
                code = error.get("code") or error.get("status") or error.get("error_code") or "unknown"
                message = (
                    error.get("message")
                    or error.get("detail")
                    or error.get("title")
                    or json.dumps(error, ensure_ascii=False)
                )
                print(f"- {item['package']}: ERROR {code} - {message}")
                continue
            size = item["size"]
            print(
                f"- {item['package']}: min {format_bytes(size.get('size'))}, "
                f"gzip {format_bytes(size.get('gzip'))}, "
                f"deps {size.get('dependencyCount', 'n/a')}, "
                f"version {size.get('version', 'n/a')}"
            )
        return
    if kind == "npmPack":
        print(
            f"npm pack: {payload.get('name')}@{payload.get('version')} "
            f"packed {format_bytes(payload.get('packedBytes'))}, "
            f"unpacked {format_bytes(payload.get('unpackedBytes'))}, "
            f"{payload.get('fileCount')} files"
        )
        for item in payload.get("largestFiles", [])[:10]:
            print(f"- {item.get('path')}: {format_bytes(item.get('size'))}")
        return
    if kind == "artifacts":
        summary = payload["summary"]
        print(
            "Artifacts: "
            f"{summary['fileCount']} files, "
            f"total {format_bytes(summary['totalBytes'])}, "
            f"gzip {format_bytes(summary['totalGzipBytes'])}"
        )
        for item in payload.get("files", [])[:15]:
            print(f"- {item['path']}: {format_bytes(item['bytes'])}, gzip {format_bytes(item['gzipBytes'])}")
        return
    if kind == "audit":
        for section in payload["sections"]:
            print_text(section)
        return
    print(json.dumps(payload, indent=2))


def apply_thresholds(payload: dict[str, Any], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    max_gzip = getattr(args, "max_gzip_kb", None)
    max_size = getattr(args, "max_size_kb", None)
    max_packed = getattr(args, "max_packed_kb", None)
    max_unpacked = getattr(args, "max_unpacked_kb", None)
    max_artifact_gzip = getattr(args, "max_artifact_gzip_kb", None)

    def kb(value: Any) -> float:
        try:
            return float(value) / 1024
        except (TypeError, ValueError):
            return 0.0

    if payload.get("kind") == "bundlephobia":
        for item in payload.get("packages", []):
            size = item.get("size") or {}
            if max_gzip is not None and kb(size.get("gzip")) > max_gzip:
                failures.append(f"{item['package']} gzip {kb(size.get('gzip')):.1f} kB > {max_gzip:.1f} kB")
            if max_size is not None and kb(size.get("size")) > max_size:
                failures.append(f"{item['package']} min {kb(size.get('size')):.1f} kB > {max_size:.1f} kB")
    elif payload.get("kind") == "npmPack":
        if max_packed is not None and kb(payload.get("packedBytes")) > max_packed:
            failures.append(f"packed size {kb(payload.get('packedBytes')):.1f} kB > {max_packed:.1f} kB")
        if max_unpacked is not None and kb(payload.get("unpackedBytes")) > max_unpacked:
            failures.append(f"unpacked size {kb(payload.get('unpackedBytes')):.1f} kB > {max_unpacked:.1f} kB")
    elif payload.get("kind") == "artifacts":
        total_gzip = payload.get("summary", {}).get("totalGzipBytes")
        if max_artifact_gzip is not None and kb(total_gzip) > max_artifact_gzip:
            failures.append(f"artifact gzip total {kb(total_gzip):.1f} kB > {max_artifact_gzip:.1f} kB")
    elif payload.get("kind") == "audit":
        for section in payload.get("sections", []):
            failures.extend(apply_thresholds(section, args))
    return failures


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a text summary.")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds.")
    parser.add_argument("--max-gzip-kb", type=float, help="Fail if any Bundlephobia gzip size exceeds this kB.")
    parser.add_argument("--max-size-kb", type=float, help="Fail if any Bundlephobia minified size exceeds this kB.")
    parser.add_argument("--max-packed-kb", type=float, help="Fail if npm packed tarball exceeds this kB.")
    parser.add_argument("--max-unpacked-kb", type=float, help="Fail if npm unpacked size exceeds this kB.")
    parser.add_argument("--max-artifact-gzip-kb", type=float, help="Fail if artifact gzip total exceeds this kB.")
    parser.add_argument("--allow-failures", action="store_true", help="Exit zero even if package queries fail.")


def add_bundlephobia_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exports", action="store_true", help="Fetch export names and export-size endpoint data.")
    parser.add_argument("--dependencies", action="store_true", help="Fetch Bundlephobia dependency data.")
    parser.add_argument("--history", type=int, default=0, help="Fetch package-history data with the given limit.")
    parser.add_argument("--similar", action="store_true", help="Fetch similar package suggestions.")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent Bundlephobia package requests.")
    parser.add_argument("--record-search", action="store_true", help="Pass record=true to mimic a Bundlephobia site search.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    package_parser = subparsers.add_parser("package", help="Query Bundlephobia for one or more packages.")
    package_parser.add_argument("packages", nargs="+", help="Package specs such as react or react@18.2.0.")
    add_common_args(package_parser)
    add_bundlephobia_args(package_parser)

    scan_parser = subparsers.add_parser("scan", help="Scan package.json dependencies with Bundlephobia.")
    scan_parser.add_argument("--package-json", type=Path, default=Path("package.json"))
    scan_parser.add_argument("--include-dev", action="store_true", help="Include devDependencies.")
    scan_parser.add_argument("--include-optional", action="store_true", help="Include optionalDependencies.")
    scan_parser.add_argument("--no-default-skips", action="store_true", help="Do not skip common backend/dev-tool packages.")
    scan_parser.add_argument("--exclude-regex", action="append", default=[], help="Additional package-name regex to skip.")
    add_common_args(scan_parser)
    add_bundlephobia_args(scan_parser)

    pack_parser = subparsers.add_parser("pack", help="Measure npm publish package footprint.")
    pack_parser.add_argument("--repo", type=Path, default=Path("."))
    add_common_args(pack_parser)

    artifacts_parser = subparsers.add_parser("artifacts", help="Measure local build artifacts and gzip sizes.")
    artifacts_parser.add_argument("paths", nargs="+", type=Path)
    artifacts_parser.add_argument("--extensions", default=",".join(sorted(DEFAULT_ARTIFACT_EXTENSIONS)))
    add_common_args(artifacts_parser)

    audit_parser = subparsers.add_parser("audit", help="Run package.json scan, npm pack, and artifact checks.")
    audit_parser.add_argument("--repo", type=Path, default=Path("."))
    audit_parser.add_argument("--include-dev", action="store_true")
    audit_parser.add_argument("--include-optional", action="store_true")
    audit_parser.add_argument("--no-default-skips", action="store_true")
    audit_parser.add_argument("--exclude-regex", action="append", default=[])
    add_common_args(audit_parser)
    add_bundlephobia_args(audit_parser)

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    payload: dict[str, Any]

    try:
        if args.command == "package":
            payload = query_many_packages(args.packages, args)
        elif args.command == "scan":
            patterns = ([] if args.no_default_skips else DEFAULT_SKIP_PATTERNS) + args.exclude_regex
            packages = packages_from_package_json(
                args.package_json,
                include_dev=args.include_dev,
                include_optional=args.include_optional,
                skip_patterns=patterns,
            )
            payload = query_many_packages(packages, args)
            payload["sourcePackageJson"] = str(args.package_json)
        elif args.command == "pack":
            payload = run_npm_pack(args.repo.resolve())
        elif args.command == "artifacts":
            extensions = {extension.strip().lower() for extension in args.extensions.split(",") if extension.strip()}
            payload = measure_artifacts(args.paths, extensions)
        elif args.command == "audit":
            repo = args.repo.resolve()
            sections = []
            package_json = repo / "package.json"
            if package_json.exists():
                patterns = ([] if args.no_default_skips else DEFAULT_SKIP_PATTERNS) + args.exclude_regex
                packages = packages_from_package_json(
                    package_json,
                    include_dev=args.include_dev,
                    include_optional=args.include_optional,
                    skip_patterns=patterns,
                )
                scan_payload = query_many_packages(packages, args)
                scan_payload["sourcePackageJson"] = str(package_json)
                sections.append(scan_payload)
            try:
                sections.append(run_npm_pack(repo))
            except SizeCheckError as error:
                sections.append({"kind": "npmPack", "error": str(error), "repo": str(repo)})
            artifact_paths = default_artifact_paths(repo)
            if artifact_paths:
                sections.append(measure_artifacts(artifact_paths, DEFAULT_ARTIFACT_EXTENSIONS))
            payload = {"kind": "audit", "repo": str(repo), "sections": sections}
        else:
            raise SizeCheckError(f"unknown command: {args.command}")
    except SizeCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_text(payload)

    failures = apply_thresholds(payload, args)
    if failures:
        print("\nThreshold failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 2
    if not args.allow_failures and payload_has_query_failures(payload):
        return 1
    return 0


def payload_has_query_failures(payload: dict[str, Any]) -> bool:
    if payload.get("kind") == "bundlephobia":
        return any("error" in item for item in payload.get("packages", []))
    if payload.get("kind") == "audit":
        return any(payload_has_query_failures(section) for section in payload.get("sections", []))
    return False


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
