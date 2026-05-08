"""
dorado_run — ONT Dorado Basecaller Runner.

Provides CLI entry point `dorado-run` with subcommands:
  ln-pod5   — Symlink pod5 dirs from source tree into Input/
  cfg-init  — Resolve config template and write project config.yml
  dl-dorado — Download the latest Dorado release from GitHub and extract it
  dl-models — Download Dorado simplex and modification models
  gen-cmd   — Generate dorado basecaller command lines from config.yml
  to-sbatch — Generate per-job Slurm sbatch scripts from cmd.txt
  run       — Full pipeline: ln-pod5 → cfg-init → dl-dorado → dl-models → gen-cmd → to-sbatch
"""

__version__ = "0.3.0"
