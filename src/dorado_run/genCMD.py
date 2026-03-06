# genCMD.py
# Generate dorado basecaller command lines from config.yml

import sys
from pathlib import Path

import yaml


def _load_config(config_path: str) -> dict:
	p = Path(config_path)
	if not p.exists():
		sys.exit(f"[gen-cmd] Error: Config file not found: {p}")
	with open(p, "r", encoding="utf-8") as fh:
		return yaml.safe_load(fh) or {}


def _validate_config(cfg: dict):
	errors = []
	if not isinstance(cfg.get("pod5_dirs"), list) or not cfg["pod5_dirs"]:
		errors.append("'pod5_dirs' must be a non-empty list.")
	drd_exe = cfg.get("drd_exe", "")
	if not drd_exe or not Path(drd_exe).exists():
		errors.append(f"'drd_exe' not found: {drd_exe!r}")
	simplex_dir    = cfg.get("simplex_model_dir", "")
	simplex_ver    = cfg.get("simplex_model_ver", "")
	simplex_tier   = cfg.get("simplex_model_tier", "sup")
	model_prefix   = cfg.get("dna_model_prefix", "dna_r10.4.1_e8.2_400bps_")
	simplex_model  = f"{model_prefix}{simplex_tier}@v{simplex_ver}"
	simplex_path   = Path(simplex_dir) / simplex_model if simplex_dir else Path()
	if not simplex_dir or not simplex_path.exists():
		errors.append(f"simplex model not found: {str(simplex_path)!r}")
	trim = str(cfg.get("trim", "yes")).lower()
	if trim not in {"both", "yes", "no"}:
		errors.append(f"'trim' must be 'both', 'yes', or 'no' (got {trim!r}).")
	mods_flag = int(cfg.get("mods_flag", 0))
	if mods_flag != 0:
		mods_dir = cfg.get("mods_model_dir", "")
		if not mods_dir or not Path(mods_dir).exists():
			errors.append(f"'mods_model_dir' not found: {mods_dir!r} (required when mods_flag != 0).")
		elif not any(p.is_dir() for p in Path(mods_dir).iterdir()):
			errors.append(f"'mods_model_dir' contains no model subdirectories: {mods_dir}")
	if errors:
		for e in errors:
			print(f"[gen-cmd] Error: {e}", file=sys.stderr)
		sys.exit(1)


def _build_commands(cfg: dict) -> list:
	pod5_dirs    = cfg["pod5_dirs"]
	dorado_exe   = cfg["drd_exe"]
	simplex_dir  = cfg["simplex_model_dir"]
	simplex_ver  = cfg.get("simplex_model_ver", "")
	simplex_tier = cfg.get("simplex_model_tier", "sup")
	model_prefix = cfg.get("dna_model_prefix", "dna_r10.4.1_e8.2_400bps_")
	simplex_model_path = Path(simplex_dir) / f"{model_prefix}{simplex_tier}@v{simplex_ver}"
	output_dir   = cfg.get("output_directory", "./Output")
	trim_mode    = str(cfg.get("trim", "yes")).lower()
	gpu          = str(cfg.get("gpu", "auto"))
	mods_flag    = int(cfg.get("mods_flag", 0))
	mods_dir     = cfg.get("mods_model_dir", "")
	kit_name     = cfg.get("kit_name") or None

	# Enumerate modification model directories within mods_dir.
	mods_model_dirs = []
	if mods_flag != 0 and mods_dir:
		mods_model_dirs = sorted([
			str(p.resolve())
			for p in Path(mods_dir).iterdir()
			if p.is_dir()
		])

	# Trim permutations: (trimmed: bool, bam_suffix: str)
	if trim_mode == "both":
		trim_states = [(True, "_trim1"), (False, "_trim0")]
	elif trim_mode == "yes":
		trim_states = [(True, "_trim1")]
	else:
		trim_states = [(False, "_trim0")]

	commands = []
	for pod_dir in pod5_dirs:
		sample = Path(pod_dir).name or Path(pod_dir).stem
		for trimmed, trim_suffix in trim_states:
			# {sample}_{tier}_v{ver}{_trim1|_trim0}_{mods_flag}.bam
			bam_name   = f"{sample}_{simplex_tier}_v{simplex_ver}{trim_suffix}_{mods_flag}.bam"
			output_bam = str(Path(output_dir) / bam_name)

			parts = [
				str(Path(dorado_exe).resolve()),
				"basecaller",
				str(simplex_model_path.resolve()),
				str(Path(pod_dir).resolve()),
				"-x", gpu,
			]

			if not trimmed:
				parts.append("--no-trim")

			if kit_name:
				parts += ["--kit-name", kit_name]

			for mmod in mods_model_dirs:
				parts += ["--modified-bases-models", mmod]

			parts += [">", output_bam]
			commands.append(" ".join(parts))

	return commands


def run(args):
	"""Execute gen-cmd logic given parsed args namespace."""
	cfg = _load_config(args.config)
	_validate_config(cfg)
	commands = _build_commands(cfg)

	if args.dry_run:
		print(f"[gen-cmd] Dry-run — {len(commands)} command(s):")
		for cmd in commands:
			print(cmd)
		return

	# Create output dir only when actually writing (not during dry run)
	output_dir = cfg.get("output_directory", "./Output")
	Path(output_dir).mkdir(parents=True, exist_ok=True)

	out_path = Path(args.output)
	out_path.parent.mkdir(parents=True, exist_ok=True)
	with open(out_path, "w", encoding="utf-8") as fh:
		for cmd in commands:
			fh.write(cmd + "\n")

	pod5_count = len(cfg.get("pod5_dirs", []))
	print(f"[gen-cmd] Wrote {len(commands)} command(s) for {pod5_count} pod5 dir(s) → {out_path}")

