# tests/test_toSbatch.py
"""Tests for toSbatch — job name derivation and header building."""

from dorado_run.toSbatch import _derive_job_name, _build_header


class TestDeriveJobName:

    def test_extracts_bam_stem(self):
        cmd = '/path/to/dorado basecaller model pod5 -x auto > /out/sample_sup_v5_trim1_0.bam'
        assert _derive_job_name(cmd, "dorado", 1) == "dorado_sample_sup_v5_trim1_0"

    def test_fallback_on_no_redirect(self):
        cmd = "dorado basecaller model pod5"
        assert _derive_job_name(cmd, "drd", 7) == "drd_0007"

    def test_fallback_on_empty_after_redirect(self):
        # Edge case: '>' is last token
        cmd = "dorado basecaller >"
        assert _derive_job_name(cmd, "drd", 3) == "drd_0003"

    def test_prefix_applied(self):
        cmd = "dorado basecaller m p > /o/out.bam"
        name = _derive_job_name(cmd, "myprefix", 1)
        assert name.startswith("myprefix_")


class TestBuildHeader:

    def test_contains_required_directives(self):
        header = _build_header(
            partition="gpu", account="myaccount", job_name="test_job",
            gres="gpu:1", cpus=8, mem="32G", walltime="12:00:00",
            email=None, logs_dir="/logs", module=None,
        )
        assert "#SBATCH --partition=gpu" in header
        assert "#SBATCH --account=myaccount" in header
        assert "#SBATCH --job-name=test_job" in header
        assert "set -euo pipefail" in header

    def test_email_directives_when_set(self):
        header = _build_header(
            partition="gpu", account="a", job_name="j", gres="gpu:1",
            cpus=4, mem="16G", walltime="1:00:00",
            email="user@example.com", logs_dir="/l", module=None,
        )
        assert "#SBATCH --mail-user=user@example.com" in header
        assert "#SBATCH --mail-type=BEGIN,END,FAIL" in header

    def test_no_email_when_none(self):
        header = _build_header(
            partition="gpu", account="a", job_name="j", gres="gpu:1",
            cpus=4, mem="16G", walltime="1:00:00",
            email=None, logs_dir="/l", module=None,
        )
        assert "mail-user" not in header

    def test_module_load_when_set(self):
        header = _build_header(
            partition="gpu", account="a", job_name="j", gres="gpu:1",
            cpus=4, mem="16G", walltime="1:00:00",
            email=None, logs_dir="/l", module="cuda/12.0",
        )
        assert "module load cuda/12.0" in header
