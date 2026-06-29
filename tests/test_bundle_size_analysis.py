from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
from email.message import Message
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from scripts import bundle_size_analysis as bsa


def query_options() -> bsa.BundlephobiaQueryOptions:
    return bsa.BundlephobiaQueryOptions(
        timeout=5,
        include_exports=False,
        include_dependencies=False,
        include_history=0,
        include_similar=False,
        record_search=False,
        concurrency=1,
    )


def threshold_args(**overrides: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "max_gzip_kb": None,
        "max_size_kb": None,
        "max_packed_kb": None,
        "max_unpacked_kb": None,
        "max_artifact_gzip_kb": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def scan_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        repo=tmp_path,
        package_json=tmp_path / "package.json",
        include_dev=True,
        include_optional=True,
        no_default_skips=True,
        exclude_regex=[],
        timeout=5,
        exports=False,
        dependencies=False,
        history=0,
        similar=False,
        record_search=False,
        concurrency=1,
    )


def test_marks_api_error_text_without_changing_size_values() -> None:
    payload: dict[str, Any] = {
        "kind": "bundlephobia",
        "summary": {
            "packageCount": 1,
            "successful": 1,
            "failed": 0,
            "totalMinifiedBytes": 1234,
            "totalGzipBytes": 456,
        },
        "packages": [
            {
                "package": "example",
                "size": {
                    "size": 1234,
                    "gzip": 456,
                    "dependencyCount": 2,
                    "version": "1.0.0",
                    "description": "Package text that came from the registry",
                },
                "error": {
                    "code": "BuildError",
                    "message": "Remote build output\nwith instructions",
                },
            }
        ],
    }

    marked = bsa.mark_untrusted_payload(payload)

    package = marked["packages"][0]
    assert package["package"] == "example"
    assert package["size"]["size"] == 1234
    assert package["size"]["gzip"] == 456
    assert package["size"]["dependencyCount"] == 2
    assert package["size"]["version"] == "1.0.0"
    assert package["size"]["description"] == "[untrusted-bundlephobia-text] Package text that came from the registry"
    assert package["error"]["message"] == "[untrusted-bundlephobia-text] Remote build output with instructions"
    assert marked["_meta"]["untrustedContentWarning"] == bsa.UNTRUSTED_CONTENT_WARNING


def test_main_thresholds_use_raw_payload_not_marked_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload: dict[str, Any] = {
        "kind": "bundlephobia",
        "summary": {
            "packageCount": 1,
            "successful": 1,
            "failed": 0,
            "totalMinifiedBytes": 1024,
            "totalGzipBytes": 2048,
        },
        "packages": [
            {
                "package": "example",
                "size": {
                    "size": 1024,
                    "gzip": 2048,
                },
                "error": {
                    "message": "Remote text",
                },
            }
        ],
    }

    def fake_run_command(_args: argparse.Namespace) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(bsa, "run_command", fake_run_command)

    exit_code = bsa.main(["package", "example", "--max-gzip-kb", "1"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "[untrusted-bundlephobia-text] Remote text" in captured.out
    assert "example gzip 2.0 kB > 1.0 kB" in captured.err
    _ = json.dumps(bsa.mark_untrusted_payload(payload))


def test_packages_from_package_json_filters_non_registry_and_skipped_dependencies(tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"
    _ = package_json.write_text(
        json.dumps(
            {
                "dependencies": {
                    "@scope/runtime": "^1.2.3",
                    "local": "file:../local",
                    "react": "latest",
                    "webpack": "^5.0.0",
                },
                "optionalDependencies": {
                    "optional-lib": "2.0.0",
                },
                "devDependencies": {
                    "pytest": "workspace:*",
                    "tiny-dev": "1.0.0",
                },
            }
        ),
        encoding="utf-8",
    )

    packages = bsa.packages_from_package_json(
        package_json,
        include_dev=True,
        include_optional=True,
        skip_patterns=[r"webpack"],
    )

    assert packages == ["@scope/runtime@^1.2.3", "react", "optional-lib@2.0.0", "tiny-dev@1.0.0"]


def test_query_many_packages_sorts_and_summarizes(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_query_bundlephobia_package(package: str, *, options: bsa.BundlephobiaQueryOptions) -> dict[str, Any]:
        assert options.timeout == 5
        if package == "bad":
            return {"package": package, "error": {"message": "Nope"}}
        return {
            "package": package,
            "size": {
                "size": len(package) * 100,
                "gzip": len(package) * 10,
            },
        }

    monkeypatch.setattr(bsa, "query_bundlephobia_package", fake_query_bundlephobia_package)

    payload = bsa.query_many_packages(["zeta", "bad", "alpha"], query_options())

    assert payload["summary"] == {
        "packageCount": 3,
        "successful": 2,
        "failed": 1,
        "totalMinifiedBytes": 900,
        "totalGzipBytes": 90,
    }
    assert [item["package"] for item in payload["packages"]] == ["alpha", "bad", "zeta"]


def test_measure_artifacts_filters_extensions_and_sorts_by_gzip(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    large = dist / "large.js"
    small = dist / "small.css"
    ignored = dist / "ignored.txt"
    _ = large.write_text("const value = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';\n", encoding="utf-8")
    _ = small.write_text("body{color:red}", encoding="utf-8")
    _ = ignored.write_text("not measured", encoding="utf-8")

    payload = bsa.measure_artifacts([dist], {".js", ".css"})

    assert payload["summary"]["fileCount"] == 2
    assert payload["summary"]["totalBytes"] == large.stat().st_size + small.stat().st_size
    assert [Path(item["path"]).name for item in payload["files"]] == ["large.js", "small.css"]


def test_bundlephobia_request_rejects_non_api_urls() -> None:
    with pytest.raises(bsa.SizeCheckError, match="refusing non-Bundlephobia API URL"):
        _ = bsa.bundlephobia_request("file:///etc/passwd", {})


def test_mark_untrusted_text_truncates_and_removes_control_characters() -> None:
    marked = bsa.mark_untrusted_text("hello\x00\n" + ("x" * 600))

    assert marked.startswith("[untrusted-bundlephobia-text] hello x")
    assert marked.endswith("... [truncated]")
    assert "\x00" not in marked


def test_bundlephobia_url_encodes_package_and_extra_params() -> None:
    url = bsa.bundlephobia_url("package-history", "@scope/pkg@1.0.0", {"limit": 3, "record": True})

    assert url == "https://bundlephobia.com/api/package-history?package=@scope/pkg@1.0.0&limit=3&record=True"


def test_parse_http_error_payload_handles_json_and_text() -> None:
    json_error = urllib.error.HTTPError(
        "https://bundlephobia.com/api/size",
        502,
        "Bad gateway",
        Message(),
        BytesIO(b'{"error":{"code":"BuildError","message":"failed"}}'),
    )
    text_error = urllib.error.HTTPError(
        "https://bundlephobia.com/api/size",
        404,
        "Not found",
        Message(),
        BytesIO(b"missing"),
    )

    try:
        assert bsa.parse_http_error_payload(json_error) == {"error": {"code": "BuildError", "message": "failed"}}
        assert bsa.parse_http_error_payload(text_error) == {"error": {"code": "404", "message": "missing"}}
    finally:
        json_error.close()
        text_error.close()


def test_http_retry_delay_uses_retry_after_and_fallback() -> None:
    headers = Message()
    headers["Retry-After"] = "7"
    retry_error = urllib.error.HTTPError("https://bundlephobia.com/api/size", 503, "Busy", headers, None)
    bad_header = Message()
    bad_header["Retry-After"] = "later"
    fallback_error = urllib.error.HTTPError("https://bundlephobia.com/api/size", 503, "Busy", bad_header, None)

    try:
        assert bsa.should_retry_http_error(retry_error, attempt=1, attempts=2)
        assert not bsa.should_retry_http_error(retry_error, attempt=2, attempts=2)
        assert bsa.http_retry_delay(retry_error, 1) == 7
        assert bsa.http_retry_delay(fallback_error, 2) == 3.0
    finally:
        retry_error.close()
        fallback_error.close()


def test_parse_api_error_normalizes_json_and_plain_messages() -> None:
    assert bsa.parse_api_error('{"error":{"code":"Bad","message":"No"}}') == {"code": "Bad", "message": "No"}
    assert bsa.parse_api_error('{"error":"No"}') == {"message": "No"}
    assert bsa.parse_api_error("network down") == {"code": "RequestError", "message": "network down"}


def test_read_package_json_rejects_missing_invalid_and_non_object_files(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    array_payload = tmp_path / "array.json"
    _ = invalid.write_text("{", encoding="utf-8")
    _ = array_payload.write_text("[]", encoding="utf-8")

    with pytest.raises(bsa.SizeCheckError, match=re.escape("package.json not found")):
        _ = bsa.read_package_json(tmp_path / "missing.json")
    with pytest.raises(bsa.SizeCheckError, match=re.escape("invalid package.json")):
        _ = bsa.read_package_json(invalid)
    with pytest.raises(bsa.SizeCheckError, match="must contain a JSON object"):
        _ = bsa.read_package_json(array_payload)


def test_dependency_helpers_dedupe_and_skip_non_registry_specs() -> None:
    data: dict[str, Any] = {
        "dependencies": {"a": "^1.0.0", "b": "github:user/repo", "skip-me": "1.0.0"},
        "optionalDependencies": {"a": "^1.0.0", "c": "*"},
        "devDependencies": {"d": "latest", "e": 5},
    }
    sections = bsa.dependency_sections(include_dev=True, include_optional=True)

    specs = bsa.iter_registry_dependency_specs(data, sections, [re.compile("skip")])

    assert specs == ["a@^1.0.0", "a@^1.0.0", "c", "d"]
    assert bsa.is_non_registry_spec("https://example.test/pkg.tgz")
    assert bsa.dependency_spec("typed", "latest", []) == "typed"
    assert bsa.dependency_spec("typed", "file:../typed", []) is None


def test_query_bundlephobia_package_fetches_optional_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []

    def fake_request_json(url: str, *, timeout: int, attempts: int = 2) -> dict[str, object]:
        assert timeout == 5
        assert attempts == 2
        urls.append(url)
        if "dependencies" in url:
            raise bsa.SizeCheckError('{"error":{"code":"Deps","message":"No deps"}}')
        return {"url": url, "size": 100, "gzip": 50}

    options = bsa.BundlephobiaQueryOptions(
        timeout=5,
        include_exports=True,
        include_dependencies=True,
        include_history=2,
        include_similar=True,
        record_search=True,
        concurrency=1,
    )
    monkeypatch.setattr(bsa, "request_json", fake_request_json)

    payload = bsa.query_bundlephobia_package("@scope/pkg", options=options)

    assert payload["size"] == {"url": urls[0], "size": 100, "gzip": 50}
    assert payload["dependenciesError"] == {"code": "Deps", "message": "No deps"}
    assert {"exports", "exportsSizes", "history", "similar"}.issubset(payload)
    assert any("record=true" in url for url in urls)
    assert any("limit=2" in url for url in urls)


def test_query_bundlephobia_package_returns_size_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request_json(_url: str, *, timeout: int, attempts: int = 2) -> dict[str, object]:
        raise bsa.SizeCheckError("network down")

    monkeypatch.setattr(bsa, "request_json", fake_request_json)

    payload = bsa.query_bundlephobia_package("broken", options=query_options())

    assert payload["error"] == {"code": "RequestError", "message": "network down"}


def test_run_npm_pack_parses_largest_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pack_stdout = json.dumps(
        [
            {
                "name": "pkg",
                "version": "1.0.0",
                "filename": "pkg-1.0.0.tgz",
                "size": 4096,
                "unpackedSize": 8192,
                "files": [
                    {"path": "small.js", "size": 10},
                    {"path": "large.js", "size": "20"},
                    {"path": 7, "size": "bad"},
                    "ignored",
                ],
            }
        ]
    )

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
        encoding: str,
    ) -> subprocess.CompletedProcess[str]:
        assert command == ["npm", "pack", "--json", "--dry-run"]
        assert cwd == tmp_path
        assert not check
        assert capture_output
        assert text
        assert encoding == "utf-8"
        return subprocess.CompletedProcess("npm", 0, stdout=pack_stdout, stderr="")

    monkeypatch.setattr(bsa, "npm_executable", lambda: "npm")
    monkeypatch.setattr("scripts.bundle_size_analysis.subprocess.run", fake_run)

    payload = bsa.run_npm_pack(tmp_path)

    assert payload["packedBytes"] == 4096
    assert payload["fileCount"] == 4
    assert payload["largestFiles"] == [
        {"path": "large.js", "size": 20},
        {"path": "small.js", "size": 10},
        {"path": "", "size": 0},
    ]


@pytest.mark.parametrize(
    ("stdout", "stderr", "message"),
    [
        ("[]", "", "npm pack returned no package metadata"),
        ("not json", "", "npm pack returned invalid JSON"),
        ('["bad"]', "", "npm pack returned invalid package metadata"),
        ("", "boom", "boom"),
    ],
)
def test_run_npm_pack_raises_for_invalid_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stdout: str,
    stderr: str,
    message: str,
) -> None:
    return_code = 1 if stderr else 0

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
        encoding: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess("npm", return_code, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(bsa, "npm_executable", lambda: "npm")
    monkeypatch.setattr("scripts.bundle_size_analysis.subprocess.run", fake_run)

    with pytest.raises(bsa.SizeCheckError, match=message):
        _ = bsa.run_npm_pack(tmp_path)


def test_run_npm_pack_reports_missing_executable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
        encoding: str,
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr(bsa, "npm_executable", lambda: "npm")
    monkeypatch.setattr("scripts.bundle_size_analysis.subprocess.run", fake_run)

    with pytest.raises(bsa.SizeCheckError, match="npm was not found"):
        _ = bsa.run_npm_pack(tmp_path)


def test_npm_executable_prefers_found_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(candidate: str) -> str | None:
        return f"/bin/{candidate}" if candidate == "npm" else None

    monkeypatch.setattr("scripts.bundle_size_analysis.os.name", "posix")
    monkeypatch.setattr("scripts.bundle_size_analysis.shutil.which", fake_which)

    assert bsa.npm_executable() == "/bin/npm"


def test_npm_executable_raises_when_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_which(_candidate: str) -> None:
        return None

    monkeypatch.setattr("scripts.bundle_size_analysis.shutil.which", missing_which)

    with pytest.raises(bsa.SizeCheckError, match="npm was not found"):
        _ = bsa.npm_executable()


def test_format_and_threshold_helpers() -> None:
    bundle_payload: dict[str, Any] = {
        "kind": "bundlephobia",
        "packages": [{"package": "big", "size": {"gzip": 4096, "size": 8192}}, {"package": "unknown"}],
    }
    pack_payload = {"kind": "npmPack", "packedBytes": 4096, "unpackedBytes": 8192}
    artifact_payload = {"kind": "artifacts", "summary": {"totalGzipBytes": 4096}}
    audit_payload = {"kind": "audit", "sections": [bundle_payload, pack_payload, artifact_payload]}

    assert bsa.format_bytes(None) == "n/a"
    assert bsa.format_bytes(512) == "512 B"
    assert bsa.format_bytes(1536) == "1.5 kB"
    assert bsa.bytes_to_kb("bad") == 0.0
    assert bsa.apply_thresholds(bundle_payload, threshold_args(max_gzip_kb=1.0, max_size_kb=1.0)) == [
        "big gzip 4.0 kB > 1.0 kB",
        "big min 8.0 kB > 1.0 kB",
    ]
    assert bsa.apply_thresholds(pack_payload, threshold_args(max_packed_kb=1.0, max_unpacked_kb=1.0)) == [
        "packed size 4.0 kB > 1.0 kB",
        "unpacked size 8.0 kB > 1.0 kB",
    ]
    assert bsa.apply_thresholds(artifact_payload, threshold_args(max_artifact_gzip_kb=1.0)) == [
        "artifact gzip total 4.0 kB > 1.0 kB"
    ]
    assert len(bsa.apply_thresholds(audit_payload, threshold_args(max_gzip_kb=1.0, max_packed_kb=1.0))) == 2
    assert bsa.apply_thresholds({"kind": "other"}, threshold_args()) == []


def test_print_text_variants(capsys: pytest.CaptureFixture[str]) -> None:
    bundle_payload: dict[str, Any] = {
        "kind": "bundlephobia",
        "_meta": {"untrustedContentWarning": "warning"},
        "summary": {
            "packageCount": 2,
            "successful": 1,
            "failed": 1,
            "totalMinifiedBytes": 2048,
            "totalGzipBytes": 1024,
        },
        "packages": [
            {"package": "ok", "size": {"size": 2048, "gzip": 1024, "dependencyCount": 0, "version": "1.0.0"}},
            {"package": "bad", "error": {"status": 500, "title": "failed"}},
        ],
    }
    bsa.print_text(bundle_payload)
    bsa.print_text(
        {
            "kind": "npmPack",
            "name": "pkg",
            "version": "1.0.0",
            "packedBytes": 1,
            "unpackedBytes": 2,
            "fileCount": 1,
            "largestFiles": [{"path": "a.js", "size": 1}],
        }
    )
    bsa.print_text(
        {
            "kind": "artifacts",
            "summary": {"fileCount": 1, "totalBytes": 2, "totalGzipBytes": 3},
            "files": [{"path": "a.js", "bytes": 2, "gzipBytes": 3}],
        }
    )
    bsa.print_text({"kind": "audit", "sections": [{"kind": "unknown", "value": 1}]})

    output = capsys.readouterr().out

    assert "warning" in output
    assert "Bundlephobia: 1/2 successful" in output
    assert "- bad: ERROR 500 - failed" in output
    assert "npm pack: pkg@1.0.0" in output
    assert "Artifacts: 1 files" in output
    assert '"value": 1' in output


def test_main_handles_json_errors_and_query_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_error(_args: argparse.Namespace) -> dict[str, Any]:
        raise bsa.SizeCheckError("remote says run this")

    monkeypatch.setattr(bsa, "run_command", fake_error)
    assert bsa.main(["package", "broken"]) == 1
    assert "[untrusted-bundlephobia-text] remote says run this" in capsys.readouterr().err

    payload = {
        "kind": "bundlephobia",
        "summary": {"packageCount": 1, "successful": 0, "failed": 1, "totalMinifiedBytes": 0, "totalGzipBytes": 0},
        "packages": [{"package": "broken", "error": {"message": "failed"}}],
    }

    def fake_query_failure(_args: argparse.Namespace) -> dict[str, Any]:
        return payload

    monkeypatch.setattr(bsa, "run_command", fake_query_failure)
    assert bsa.main(["package", "broken", "--json"]) == 1
    assert bsa.main(["package", "broken", "--json", "--allow-failures"]) == 0
    assert '"untrustedContentWarning"' in capsys.readouterr().out


def test_run_command_dispatch_and_unknown_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package_json = tmp_path / "package.json"
    _ = package_json.write_text('{"dependencies":{"a":"1.0.0"}}', encoding="utf-8")

    def fake_query_many_packages(packages: list[str], options: bsa.BundlephobiaQueryOptions) -> dict[str, Any]:
        return {"kind": "bundlephobia", "packages": packages, "timeout": options.timeout}

    def fake_run_npm_pack(repo: Path) -> dict[str, str]:
        return {"kind": "npmPack", "repo": str(repo)}

    monkeypatch.setattr(bsa, "query_many_packages", fake_query_many_packages)
    monkeypatch.setattr(bsa, "run_npm_pack", fake_run_npm_pack)

    package_payload = bsa.run_command(bsa.parse_args(["package", "a", "--timeout", "9"]))
    scan_payload = bsa.run_command(
        bsa.parse_args(["scan", "--package-json", str(package_json), "--include-dev", "--exclude-regex", "skip"])
    )
    pack_payload = bsa.run_command(bsa.parse_args(["pack", "--repo", str(tmp_path)]))
    artifact_payload = bsa.run_command(bsa.parse_args(["artifacts", str(package_json), "--extensions", ".json"]))

    assert package_payload["packages"] == ["a"]
    assert package_payload["timeout"] == 9
    assert scan_payload["sourcePackageJson"] == str(package_json)
    assert pack_payload["repo"] == str(tmp_path.resolve())
    assert artifact_payload["summary"]["fileCount"] == 1
    with pytest.raises(bsa.SizeCheckError, match="unknown command"):
        _ = bsa.run_command(argparse.Namespace(command="nope"))


def test_audit_sections_include_scan_pack_and_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = (tmp_path / "package.json").write_text('{"dependencies":{"a":"1.0.0"}}', encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    _ = (dist / "bundle.js").write_text("console.log(1)", encoding="utf-8")
    args = scan_args(tmp_path)

    def fake_query_many_packages(packages: list[str], _options: bsa.BundlephobiaQueryOptions) -> dict[str, Any]:
        return {"kind": "bundlephobia", "packages": packages}

    def fake_run_npm_pack(_repo: Path) -> dict[str, int | str]:
        return {"kind": "npmPack", "packedBytes": 1}

    monkeypatch.setattr(bsa, "query_many_packages", fake_query_many_packages)
    monkeypatch.setattr(bsa, "run_npm_pack", fake_run_npm_pack)

    payload = bsa.command_audit(args)

    assert payload["kind"] == "audit"
    assert [section["kind"] for section in payload["sections"]] == ["bundlephobia", "npmPack", "artifacts"]
    assert bsa.payload_has_query_failures(
        {"kind": "audit", "sections": [{"kind": "bundlephobia", "packages": [{"error": "x"}]}]}
    )


def test_pack_repo_for_audit_converts_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run_npm_pack(_repo: Path) -> dict[str, Any]:
        raise bsa.SizeCheckError("no npm")

    monkeypatch.setattr(bsa, "run_npm_pack", fake_run_npm_pack)

    assert bsa.pack_repo_for_audit(tmp_path) == {"kind": "npmPack", "error": "no npm", "repo": str(tmp_path)}
    assert bsa.measure_default_artifacts(tmp_path) == []
