# tests/test_cfgInit.py
"""Tests for cfgInit — placeholder resolution and config generation."""

import argparse
from pathlib import Path

import pytest
import yaml

from dorado_run import cfgInit


def _ns(**kwargs):
    defaults = dict(
        template="cfg/config_temp.yml",
        input_dir="./Input",
        output="./config.yml",
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ── placeholder resolution ───────────────────────────────────────────────────


class TestResolvePlaceholders:

    def test_simple_substitution(self):
        cfg = {"models_dir": "./Models", "simplex_model_dir": "{models_dir}/Simplex"}
        result = cfgInit._resolve_placeholders(cfg)
        assert result["simplex_model_dir"] == "./Models/Simplex"

    def test_chained_substitution(self):
        cfg = {
            "models_dir": "./M",
            "simplex_model_dir": "{models_dir}/S",
            "mods_model_dir": "{models_dir}/Mods",
        }
        result = cfgInit._resolve_placeholders(cfg)
        assert result["simplex_model_dir"] == "./M/S"
        assert result["mods_model_dir"] == "./M/Mods"

    def test_no_placeholder_passthrough(self):
        cfg = {"models_dir": "/absolute/path", "other_key": "value"}
        result = cfgInit._resolve_placeholders(cfg)
        assert result["models_dir"] == "/absolute/path"
        assert result["other_key"] == "value"

    def test_drd_exe_placeholder(self):
        cfg = {
            "drd_ver": "1.4.0",
            "drd_os": "linux",
            "drd_arch": "x64",
            "drd_exe": "./dorado-{drd_ver}-{drd_os}-{drd_arch}/bin/dorado",
        }
        result = cfgInit._resolve_placeholders(cfg)
        assert result["drd_exe"] == "./dorado-1.4.0-linux-x64/bin/dorado"

    def test_missing_placeholder_exits(self):
        cfg = {"models_dir": "{nonexistent_key}/Simplex"}
        with pytest.raises(SystemExit, match="undefined placeholder"):
            cfgInit._resolve_placeholders(cfg)

    def test_non_string_values_ignored(self):
        cfg = {"models_dir": 42, "simplex_model_dir": "{models_dir}/S"}
        # models_dir is not a string, so it can't be used as a placeholder
        with pytest.raises(SystemExit):
            cfgInit._resolve_placeholders(cfg)


# ── absolute path conversion ────────────────────────────────────────────────


class TestToAbs:

    def test_relative_becomes_absolute(self):
        cfg = {"models_dir": "./Models"}
        result = cfgInit._to_abs(cfg)
        assert Path(result["models_dir"]).is_absolute()

    def test_absolute_stays_absolute(self):
        cfg = {"models_dir": "/absolute/path"}
        result = cfgInit._to_abs(cfg)
        assert result["models_dir"] == "/absolute/path"

    def test_non_path_keys_untouched(self):
        cfg = {"other": "./relative", "models_dir": "./M"}
        result = cfgInit._to_abs(cfg)
        assert result["other"] == "./relative"  # not in _ABS_PATH_KEYS


# ── end-to-end run ──────────────────────────────────────────────────────────


class TestCfgInitRun:

    def test_writes_config_with_pod5_dirs(self, tmp_path):
        template = tmp_path / "template.yml"
        template.write_text(yaml.dump({
            "models_dir": "./Models",
            "simplex_model_dir": "{models_dir}/Simplex",
        }))
        input_dir = tmp_path / "Input"
        input_dir.mkdir()
        (input_dir / "sample1").mkdir()
        (input_dir / "sample2").mkdir()
        out = tmp_path / "config.yml"

        cfgInit.run(_ns(template=str(template), input_dir=str(input_dir),
                        output=str(out)))

        cfg = yaml.safe_load(out.read_text())
        assert len(cfg["pod5_dirs"]) == 2
        assert all(isinstance(d, str) for d in cfg["pod5_dirs"])

    def test_refuses_overwrite_template(self, tmp_path):
        f = tmp_path / "same.yml"
        f.write_text("key: val\n")
        with pytest.raises(SystemExit, match="must not be the same"):
            cfgInit.run(_ns(template=str(f), output=str(f),
                            input_dir=str(tmp_path)))

    def test_missing_template_exits(self, tmp_path):
        with pytest.raises(SystemExit, match="Template not found"):
            cfgInit.run(_ns(template=str(tmp_path / "no.yml"),
                            input_dir=str(tmp_path),
                            output=str(tmp_path / "out.yml")))

    def test_missing_input_dir_exits(self, tmp_path):
        template = tmp_path / "t.yml"
        template.write_text("key: val\n")
        with pytest.raises(SystemExit, match="does not exist"):
            cfgInit.run(_ns(template=str(template),
                            input_dir=str(tmp_path / "nope"),
                            output=str(tmp_path / "out.yml")))
