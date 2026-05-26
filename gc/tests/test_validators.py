from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts"))

import validate_context_bundle as context_validator
import validate_verdict_report as verdict_validator


class ContextBundleValidatorTests(unittest.TestCase):
    def test_valid_context_bundle_accepts_only_name_path_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            subject = root / "requirements.md"
            subject.write_text("# Requirements\n", encoding="utf-8")
            bundle = root / "context.yaml"
            bundle.write_text(
                "items:\n"
                "  - name: Requirements\n"
                "    path: requirements.md\n"
                "    description: Product requirements.\n",
                encoding="utf-8",
            )

            result = context_validator.validate_bundle(bundle, allowed_roots=[root])

            self.assertEqual([item.name for item in result.items], ["Requirements"])
            self.assertEqual(result.items[0].resolved_path, subject.resolve())

    def test_context_bundle_rejects_unknown_item_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "requirements.md").write_text("# Requirements\n", encoding="utf-8")
            bundle = root / "context.yaml"
            bundle.write_text(
                "items:\n"
                "  - name: Requirements\n"
                "    path: requirements.md\n"
                "    description: Product requirements.\n"
                "    inline: no\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(context_validator.ValidationError, "unknown fields"):
                context_validator.validate_bundle(bundle, allowed_roots=[root])

    def test_context_bundle_rejects_missing_files_and_symlink_escapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            outside = pathlib.Path(tmp) / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            link = root / "link.md"
            link.symlink_to(outside)
            bundle = root / "context.yaml"
            bundle.write_text(
                "items:\n"
                "  - name: Link\n"
                "    path: link.md\n"
                "    description: Escaping symlink.\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(context_validator.ValidationError, "outside allowed roots"):
                context_validator.validate_bundle(bundle, allowed_roots=[root / "allowed"])

            bundle.write_text(
                "items:\n"
                "  - name: Missing\n"
                "    path: missing.md\n"
                "    description: Missing file.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(context_validator.ValidationError, "does not exist"):
                context_validator.validate_bundle(bundle, allowed_roots=[root])

    def test_context_bundle_rejects_binary_and_secret_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            binary = root / "blob.bin"
            binary.write_bytes(b"abc\x00def")
            bundle = root / "context.yaml"
            bundle.write_text(
                "items:\n"
                "  - name: Blob\n"
                "    path: blob.bin\n"
                "    description: Binary file.\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(context_validator.ValidationError, "binary"):
                context_validator.validate_bundle(bundle, allowed_roots=[root])

            secret = root / ".env"
            secret.write_text("TOKEN=secret\n", encoding="utf-8")
            bundle.write_text(
                "items:\n"
                "  - name: Secret\n"
                "    path: .env\n"
                "    description: Secret file.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(context_validator.ValidationError, "secret"):
                context_validator.validate_bundle(bundle, allowed_roots=[root])

            for filename in (".env.production", "private.pem", ".ssh/config", ".git/config", "cookies.txt"):
                secret = root / filename
                secret.parent.mkdir(parents=True, exist_ok=True)
                secret.write_text("secret\n", encoding="utf-8")
                bundle.write_text(
                    "items:\n"
                    "  - name: Secret\n"
                    f"    path: {filename}\n"
                    "    description: Secret file.\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(context_validator.ValidationError, "secret"):
                    context_validator.validate_bundle(bundle, allowed_roots=[root])


class VerdictReportValidatorTests(unittest.TestCase):
    def test_verdict_report_accepts_pass_and_fail_reports(self) -> None:
        pass_report = """---
schema: gc.verdict-report.v1
kind: review
verdict: pass
severity: none
findings: []
---

No issues found.
"""
        fail_report = """---
schema: gc.verdict-report.v1
kind: gap-analysis
verdict: fail
severity: major
findings:
  - id: gap-001
    severity: major
    title: Missing restart test
    evidence: No test covers restart.
    required_fix: Add restart coverage.
---

Failure details.
"""

        self.assertEqual(verdict_validator.validate_report_text(pass_report).verdict, "pass")
        self.assertEqual(verdict_validator.validate_report_text(fail_report).severity, "major")

    def test_verdict_report_rejects_bad_schema_and_unstructured_failures(self) -> None:
        bad_schema = """---
schema: other
kind: review
verdict: pass
severity: none
findings: []
---
"""
        no_findings = """---
schema: gc.verdict-report.v1
kind: review
verdict: fail
severity: major
findings: []
---
"""

        with self.assertRaisesRegex(verdict_validator.ValidationError, "schema"):
            verdict_validator.validate_report_text(bad_schema)
        with self.assertRaisesRegex(verdict_validator.ValidationError, "findings"):
            verdict_validator.validate_report_text(no_findings)

    def test_verdict_report_rejects_severity_that_is_not_max_finding_severity(self) -> None:
        report = """---
schema: gc.verdict-report.v1
kind: review
verdict: fail
severity: minor
findings:
  - id: rev-001
    severity: blocker
    title: Unsafe publish
    evidence: Publish can mutate protected branch.
    required_fix: Block protected branches.
---
"""

        with self.assertRaisesRegex(verdict_validator.ValidationError, "maximum"):
            verdict_validator.validate_report_text(report)


if __name__ == "__main__":
    unittest.main()
