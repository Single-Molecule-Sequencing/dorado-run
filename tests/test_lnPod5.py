# tests/test_lnPod5.py
"""Tests for lnPod5 — pod5 directory symlink derivation and linking."""

import argparse
import os
from pathlib import Path

import pytest

from dorado_run import lnPod5


# ── helpers ──────────────────────────────────────────────────────────────────


def _ns(**kwargs):
    """Build an argparse.Namespace with sensible defaults for lnPod5.run()."""
    defaults = dict(
        source=None,
        dest=Path("."),
        pod5_name="pod5_pass",
        clean=False,
        override_pod5_dir=None,
        override_experiment_name=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _make_experiment(root: Path, experiment: str, pod5_name: str,
                     barcodes=None):
    """Create a fake experiment directory tree under *root*.

    Pre-demux (barcodes=None):
        root/experiment/.../pod5_name/  (leaf dir, no sub-dirs)

    Post-demux (barcodes=['barcode01', ...]):
        root/experiment/.../pod5_name/barcode01/
        root/experiment/.../pod5_name/barcode02/
    """
    pod5_dir = root / experiment / pod5_name
    pod5_dir.mkdir(parents=True, exist_ok=True)
    if barcodes:
        for bc in barcodes:
            (pod5_dir / bc).mkdir(parents=True, exist_ok=True)
    return pod5_dir


# ── _clean_symlinks ─────────────────────────────────────────────────────────


class TestCleanSymlinks:

    def test_removes_symlinks(self, tmp_path):
        target = tmp_path / "real"
        target.mkdir()
        for i in range(3):
            (tmp_path / f"link{i}").symlink_to(target)
        removed = lnPod5._clean_symlinks(tmp_path)
        assert removed == 3
        remaining = list(tmp_path.iterdir())
        assert remaining == [target]

    def test_skips_physical_dirs(self, tmp_path):
        (tmp_path / "real_dir").mkdir()
        removed = lnPod5._clean_symlinks(tmp_path)
        assert removed == 0
        assert (tmp_path / "real_dir").exists()

    def test_nonexistent_dir_returns_zero(self, tmp_path):
        removed = lnPod5._clean_symlinks(tmp_path / "nonexistent")
        assert removed == 0

    def test_mixed_symlinks_and_dirs(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        (tmp_path / "link").symlink_to(target)
        (tmp_path / "physical").mkdir()
        removed = lnPod5._clean_symlinks(tmp_path)
        assert removed == 1
        assert (tmp_path / "physical").exists()
        assert not (tmp_path / "link").exists()


# ── link mode — experiment name derivation ───────────────────────────────────


class TestLinkModeDerivation:
    """Core behavior: derive experiment name from top-level dir under srcdir."""

    def test_predemux_single_experiment(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _make_experiment(src, "exp1", "pod5_pass")

        lnPod5.run(_ns(source=src, dest=dest))

        links = sorted(dest.iterdir())
        assert len(links) == 1
        assert links[0].name == "exp1"
        assert links[0].is_symlink()
        assert links[0].resolve() == (src / "exp1" / "pod5_pass").resolve()

    def test_postdemux_single_experiment(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _make_experiment(src, "exp1", "pod5_pass",
                         barcodes=["barcode01", "barcode02"])

        lnPod5.run(_ns(source=src, dest=dest))

        links = sorted(dest.iterdir())
        assert len(links) == 2
        assert links[0].name == "exp1_barcode01"
        assert links[1].name == "exp1_barcode02"
        # Each link points to the barcode subdir
        assert links[0].resolve() == (src / "exp1" / "pod5_pass" / "barcode01").resolve()

    def test_multiple_experiments(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _make_experiment(src, "alpha", "pod5_pass")
        _make_experiment(src, "beta", "pod5_pass",
                         barcodes=["barcode01"])

        lnPod5.run(_ns(source=src, dest=dest))

        names = sorted(p.name for p in dest.iterdir())
        assert names == ["alpha", "beta_barcode01"]

    def test_custom_pod5_name(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _make_experiment(src, "exp1", "pod5_fail")

        lnPod5.run(_ns(source=src, dest=dest, pod5_name="pod5_fail"))

        links = list(dest.iterdir())
        assert len(links) == 1
        assert links[0].name == "exp1"

    def test_nested_pod5_dir(self, tmp_path):
        """pod5_pass is several levels deep; experiment name is still the
        top-level directory under srcdir."""
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        pod5 = src / "run1" / "level1" / "level2" / "pod5_pass"
        pod5.mkdir(parents=True)

        lnPod5.run(_ns(source=src, dest=dest))

        links = list(dest.iterdir())
        assert len(links) == 1
        assert links[0].name == "run1"

    def test_no_matching_pod5_dirs(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        (src / "exp1" / "other_dir").mkdir(parents=True)

        lnPod5.run(_ns(source=src, dest=dest))

        assert dest.exists()
        assert list(dest.iterdir()) == []


# ── link mode — deterministic ordering ───────────────────────────────────────


class TestDeterministicOrdering:

    def test_barcode_links_sorted(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        _make_experiment(src, "exp", "pod5_pass",
                         barcodes=["barcode03", "barcode01", "barcode02"])

        lnPod5.run(_ns(source=src, dest=dest))

        names = [p.name for p in sorted(dest.iterdir())]
        assert names == ["exp_barcode01", "exp_barcode02", "exp_barcode03"]

    def test_experiments_processed_in_sorted_order(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        for name in ["zebra", "apple", "mango"]:
            _make_experiment(src, name, "pod5_pass")

        lnPod5.run(_ns(source=src, dest=dest))

        names = sorted(p.name for p in dest.iterdir())
        assert names == ["apple", "mango", "zebra"]


# ── link mode — pre-flight cleanup ──────────────────────────────────────────


class TestPreflightCleanup:

    def test_existing_symlinks_removed_before_new(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        dest.mkdir()
        # Create a stale symlink
        stale_target = tmp_path / "stale"
        stale_target.mkdir()
        (dest / "old_link").symlink_to(stale_target)

        _make_experiment(src, "exp1", "pod5_pass")
        lnPod5.run(_ns(source=src, dest=dest))

        names = sorted(p.name for p in dest.iterdir())
        assert "old_link" not in names
        assert "exp1" in names


# ── link mode — error handling ───────────────────────────────────────────────


class TestLinkModeErrors:

    def test_missing_source_exits(self, tmp_path):
        with pytest.raises(SystemExit, match="does not exist"):
            lnPod5.run(_ns(source=tmp_path / "nonexistent",
                           dest=tmp_path / "dest"))

    def test_no_source_no_override_exits(self, tmp_path):
        with pytest.raises(SystemExit, match="--source is required"):
            lnPod5.run(_ns(source=None, dest=tmp_path / "dest"))

    def test_dest_created_if_absent(self, tmp_path):
        src = tmp_path / "src"
        dest = tmp_path / "new" / "nested" / "dest"
        _make_experiment(src, "exp1", "pod5_pass")

        lnPod5.run(_ns(source=src, dest=dest))

        assert dest.is_dir()
        assert len(list(dest.iterdir())) == 1


# ── clean mode ───────────────────────────────────────────────────────────────


class TestCleanMode:

    def test_clean_removes_symlinks(self, tmp_path):
        dest = tmp_path / "dest"
        dest.mkdir()
        target = tmp_path / "real"
        target.mkdir()
        (dest / "link1").symlink_to(target)
        (dest / "link2").symlink_to(target)

        lnPod5.run(_ns(dest=dest, clean=True))

        assert list(dest.iterdir()) == []

    def test_clean_nonexistent_dest_exits(self, tmp_path):
        with pytest.raises(SystemExit, match="does not exist"):
            lnPod5.run(_ns(dest=tmp_path / "missing", clean=True))


# ── override mode ────────────────────────────────────────────────────────────


class TestOverrideMode:

    def test_override_link_naming(self, tmp_path):
        pod5 = tmp_path / "my_pod5_data"
        pod5.mkdir()
        dest = tmp_path / "dest"

        lnPod5.run(_ns(
            dest=dest,
            override_pod5_dir=str(pod5),
            override_experiment_name="custom_exp",
        ))

        links = list(dest.iterdir())
        assert len(links) == 1
        assert links[0].name == "custom_exp_my_pod5_data"
        assert links[0].is_symlink()
        assert links[0].resolve() == pod5.resolve()

    def test_override_cleans_existing_symlinks(self, tmp_path):
        pod5 = tmp_path / "pod5_data"
        pod5.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        stale = tmp_path / "stale"
        stale.mkdir()
        (dest / "old").symlink_to(stale)

        lnPod5.run(_ns(
            dest=dest,
            override_pod5_dir=str(pod5),
            override_experiment_name="exp",
        ))

        names = [p.name for p in dest.iterdir()]
        assert "old" not in names
        assert "exp_pod5_data" in names

    def test_override_missing_pod5_exits(self, tmp_path):
        with pytest.raises(SystemExit, match="does not exist"):
            lnPod5.run(_ns(
                dest=tmp_path / "dest",
                override_pod5_dir=str(tmp_path / "nonexistent"),
                override_experiment_name="exp",
            ))

    def test_override_creates_dest_dir(self, tmp_path):
        pod5 = tmp_path / "pod5"
        pod5.mkdir()
        dest = tmp_path / "new" / "dest"

        lnPod5.run(_ns(
            dest=dest,
            override_pod5_dir=str(pod5),
            override_experiment_name="exp",
        ))

        assert dest.is_dir()
        assert len(list(dest.iterdir())) == 1


# ── link mode — pod5 dir not descended after match ───────────────────────────


class TestNoDescentAfterMatch:

    def test_nested_pod5_pass_ignored(self, tmp_path):
        """If pod5_pass contains a sub-dir also called pod5_pass, only the
        outer one should match (dirnames is cleared after the match)."""
        src = tmp_path / "src"
        nested = src / "exp1" / "pod5_pass" / "pod5_pass"
        nested.mkdir(parents=True)

        dest = tmp_path / "dest"
        lnPod5.run(_ns(source=src, dest=dest))

        links = list(dest.iterdir())
        # The outer pod5_pass has subdirs → post-demux naming
        assert len(links) == 1
        assert links[0].name == "exp1_pod5_pass"
