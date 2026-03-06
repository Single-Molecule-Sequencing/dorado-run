# toSbatch.py
# Generate per-job Slurm sbatch scripts from a dorado cmd.txt

import random
import shlex
import sys
import yaml
from pathlib import Path

_DEFAULT_CMD_TXT = "./cmd.txt"
_DEFAULT_OUTDIR  = "./Sbatch"


def _load_config(config_path: str) -> dict:
	p = Path(config_path)
	if not p.exists():
		return {}
	with open(p, "r", encoding="utf-8") as fh:
		return yaml.safe_load(fh) or {}


def _read_commands(path: Path) -> list:
	"""Read non-empty lines from a commands file."""
	if not path.exists():
		sys.exit(f"[to-sbatch] Error: Commands file not found: {path}")
	return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _derive_job_name(cmd: str, job_prefix: str, fallback_idx: int) -> str:
	"""Derive a Slurm job name from the BAM path after '>' in the command."""
	try:
		tokens = shlex.split(cmd)
		idx = tokens.index(">")
		bam_path = tokens[idx + 1]
		base = Path(bam_path).stem
		if base and not base.startswith("-"):
			return f"{job_prefix}_{base}"
	except (ValueError, IndexError):
		pass
	return f"{job_prefix}_{fallback_idx:04d}"


def _build_header(partition, account, job_name, gres,
				  cpus, mem, walltime, email, logs_dir, module):
	"""Build the #SBATCH header block for one sbatch script."""
	lines = [
		"#!/bin/bash",
		f"#SBATCH --partition={partition}",
		f"#SBATCH --account={account}",
		f"#SBATCH --job-name={job_name}",
		f"#SBATCH --gres={gres}",
		"#SBATCH --nodes=1",
		"#SBATCH --ntasks=1",
		f"#SBATCH --cpus-per-task={cpus}",
		f"#SBATCH --mem={mem}",
		f"#SBATCH --time={walltime}",
	]
	if email:
		lines += [
			f"#SBATCH --mail-user={email}",
			"#SBATCH --mail-type=BEGIN,END,FAIL",
		]
	lines += [
		f"#SBATCH --output={logs_dir}/%x_%j.out",
		f"#SBATCH --error={logs_dir}/%x_%j.err",
		"",
		"set -euo pipefail",
		'echo "[$(date)] Node: $(hostname)"',
		'echo "[$(date)] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"',
	]
	if module:
		lines += ["", f"module load {module}"]
	lines += ["", "# run command"]
	return "\n".join(lines)


def run(args):
	"""Execute to-sbatch logic given parsed args namespace."""
	cfg = _load_config(args.config)

	# Resolve settings: CLI flag > config key > built-in default
	cmd_txt    = Path(args.input  or cfg.get("hpc_cmd_txt",  _DEFAULT_CMD_TXT))
	outdir     = Path(args.outdir or cfg.get("hpc_outdir",   _DEFAULT_OUTDIR))

	# Build list of (partition, gres) targets; each job is randomly assigned one.
	raw_targets = cfg.get("hpc_targets")
	if raw_targets and isinstance(raw_targets, list):
		targets = [
			(t["partition"], t["gres"])
			for t in raw_targets
			if isinstance(t, dict) and "partition" in t and "gres" in t
		]
		if not targets:
			sys.exit("[to-sbatch] Error: 'hpc_targets' contains no valid {partition, gres} entries.")
	else:
		# Fallback: legacy single-key values
		targets = [(
			cfg.get("hpc_partition", "gpu"),
			cfg.get("hpc_gres",      "gpu:1"),
		)]
	account    = cfg.get("hpc_account")    or None
	cpus       = int(cfg.get("hpc_cpus",   8))
	mem        = cfg.get("hpc_mem",        "32G")
	walltime   = cfg.get("hpc_time",       "12:00:00")
	email      = cfg.get("hpc_email")      or None
	job_prefix = cfg.get("hpc_job_prefix", "dorado")
	module     = cfg.get("hpc_module")     or None

	if not account:
		sys.exit(
			"[to-sbatch] Error: 'hpc_account' is not set in config.yml.\n"
			"Set it to your Slurm account/allocation name and re-run cfg-init."
		)

	cmds = _read_commands(cmd_txt)
	if not cmds:
		sys.exit(f"[to-sbatch] Error: No commands found in {cmd_txt}")

	logs_dir = (outdir / "Logs").resolve()

	if not args.dry_run:
		outdir.mkdir(parents=True, exist_ok=True)
		logs_dir.mkdir(parents=True, exist_ok=True)

	print(
		f"[to-sbatch] NOTE: Submit jobs from the directory where this command is run.\n"
		f"            Log paths in #SBATCH --output/--error are absolute and fixed at "
		f"generation time: {logs_dir}/"
	)

	written = 0
	for idx, cmd in enumerate(cmds, start=1):
		partition, gres = random.choice(targets)
		job_name = _derive_job_name(cmd, job_prefix, idx)
		header   = _build_header(
			partition = partition,
			account   = account,
			job_name  = job_name,
			gres      = gres,
			cpus      = cpus,
			mem       = mem,
			walltime  = walltime,
			email     = email,
			logs_dir  = logs_dir,
			module    = module,
		)

		# Format the command with backslash line-continuation for readability
		cmd_multiline = " \\\n  ".join(shlex.split(cmd))
		script = f"{header}\n{cmd_multiline}\n"

		if args.dry_run:
			print(f"\n# --- {job_name}.sbatch ---")
			print(script)
			continue

		outpath = outdir / f"{job_name}.sbatch"
		if outpath.exists():
			outpath = outdir / f"{job_name}_{idx:03d}.sbatch"
		outpath.write_text(script, encoding="utf-8")
		written += 1

	if not args.dry_run:
		print(f"[to-sbatch] Wrote {written} .sbatch file(s) to {outdir}/")
		print(f"[to-sbatch] Logs directory: {logs_dir}/")

