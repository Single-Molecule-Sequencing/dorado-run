# tests/test_genCMD.py
"""Tests for genCMD — command line building from config."""

from pathlib import Path

from dorado_run.genCMD import _build_commands


def _cfg(tmp_path, *, pod5_dirs=None, trim="yes", mods_flag=0, kit_name=None,
         mods_model_dirs=None):
    """Build a minimal config dict for _build_commands, creating real paths."""
    exe = tmp_path / "bin" / "dorado"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.touch()
    exe.chmod(0o755)

    simplex = tmp_path / "models" / "simplex" / "dna_r10.4.1_e8.2_400bps_sup@v5.0.0"
    simplex.mkdir(parents=True, exist_ok=True)

    output = tmp_path / "Output"
    output.mkdir(exist_ok=True)

    mods_dir = tmp_path / "models" / "mods"
    if mods_model_dirs:
        for d in mods_model_dirs:
            (mods_dir / d).mkdir(parents=True, exist_ok=True)

    if pod5_dirs is None:
        sample = tmp_path / "input" / "sample1"
        sample.mkdir(parents=True, exist_ok=True)
        pod5_dirs = [str(sample)]

    return {
        "pod5_dirs": pod5_dirs,
        "drd_exe": str(exe),
        "simplex_model_dir": str(simplex.parent),
        "simplex_model_ver": "5.0.0",
        "simplex_model_tier": "sup",
        "dna_model_prefix": "dna_r10.4.1_e8.2_400bps_",
        "output_directory": str(output),
        "trim": trim,
        "gpu": "auto",
        "mods_flag": mods_flag,
        "mods_model_dir": str(mods_dir),
        "kit_name": kit_name,
    }


class TestBuildCommands:

    def test_single_sample_trim_yes(self, tmp_path):
        cfg = _cfg(tmp_path)
        cmds = _build_commands(cfg)
        assert len(cmds) == 1
        assert "sample1" in cmds[0]
        assert "_trim1_" in cmds[0]
        assert "--no-trim" not in cmds[0]

    def test_single_sample_trim_no(self, tmp_path):
        cfg = _cfg(tmp_path, trim="no")
        cmds = _build_commands(cfg)
        assert len(cmds) == 1
        assert "_trim0_" in cmds[0]
        assert "--no-trim" in cmds[0]

    def test_trim_both_generates_two_commands(self, tmp_path):
        cfg = _cfg(tmp_path, trim="both")
        cmds = _build_commands(cfg)
        assert len(cmds) == 2
        assert any("_trim1_" in c for c in cmds)
        assert any("_trim0_" in c for c in cmds)

    def test_sample_name_from_pod5_dir(self, tmp_path):
        """Sample name is the basename of the pod5 dir path."""
        sample = tmp_path / "input" / "exp1_barcode05"
        sample.mkdir(parents=True)
        cfg = _cfg(tmp_path, pod5_dirs=[str(sample)])
        cmds = _build_commands(cfg)
        assert "exp1_barcode05_sup_v5.0.0_trim1_0.bam" in cmds[0]

    def test_multiple_pod5_dirs(self, tmp_path):
        s1 = tmp_path / "input" / "s1"
        s2 = tmp_path / "input" / "s2"
        s1.mkdir(parents=True)
        s2.mkdir(parents=True)
        cfg = _cfg(tmp_path, pod5_dirs=[str(s1), str(s2)])
        cmds = _build_commands(cfg)
        assert len(cmds) == 2

    def test_kit_name_included(self, tmp_path):
        cfg = _cfg(tmp_path, kit_name="SQK-NBD114-96")
        cmds = _build_commands(cfg)
        assert "--kit-name" in cmds[0]
        assert "SQK-NBD114-96" in cmds[0]

    def test_mods_models_appended(self, tmp_path):
        cfg = _cfg(tmp_path, mods_flag=1, mods_model_dirs=["mod_a", "mod_b"])
        cmds = _build_commands(cfg)
        assert cmds[0].count("--modified-bases-models") == 2

    def test_bam_output_uses_redirect(self, tmp_path):
        cfg = _cfg(tmp_path)
        cmds = _build_commands(cfg)
        assert "> " in cmds[0]
        assert cmds[0].endswith(".bam")
