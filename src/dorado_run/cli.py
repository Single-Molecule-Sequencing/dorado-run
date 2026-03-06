# cli.py
# Main CLI entry point for dorado-run.
# All argument parsing lives here; modules expose only run(args).

import argparse
import sys
from pathlib import Path

import yaml

from dorado_run import lnPod5, cfgInit, dlDorado, dlModels, genCMD, toSbatch


def _read_config_key(config_path: str, key: str):
	"""Read a single key from a YAML config file; return None on any failure."""
	try:
		with open(config_path, "r", encoding="utf-8") as fh:
			return (yaml.safe_load(fh) or {}).get(key)
	except Exception:
		return None


def _run_pipeline(args):
	"""Chain all pipeline steps: ln-pod5 → cfg-init → dl-dorado → dl-models → gen-cmd → to-sbatch."""
	dest   = Path(args.dest)
	config = args.config

	# Step 1: ln-pod5
	print("\n[run] Step 1/6 — ln-pod5")
	lnPod5.run(argparse.Namespace(
		source=Path(args.source),
		dest=dest,
		pod5_name=args.pod5_name,
		clean=False,
	))

	# Step 2: cfg-init
	print("\n[run] Step 2/6 — cfg-init")
	cfgInit.run(argparse.Namespace(
		template=args.template,
		input_dir=str(dest),
		output=config,
	))

	# Step 3: dl-dorado — derive extraction dest from drd_exe written by cfg-init
	print("\n[run] Step 3/6 — dl-dorado")
	drd_exe = _read_config_key(config, "drd_exe")
	dl_dest = str(Path(drd_exe).parent.parent.parent) if drd_exe else "."
	dlDorado.run(argparse.Namespace(
		config=config,
		version=None,
		target_os=None,
		arch=None,
		dest=dl_dest,
		verbose=False,
		dry_run=args.dry_run,
	))

	# Step 4: dl-models
	print("\n[run] Step 4/6 — dl-models")
	dlModels.run(argparse.Namespace(
		config=config,
		dry_run=args.dry_run,
	))

	# Step 5: gen-cmd
	print("\n[run] Step 5/6 — gen-cmd")
	genCMD.run(argparse.Namespace(
		config=config,
		output="./cmd.txt",
		dry_run=args.dry_run,
	))

	# Step 6: to-sbatch
	print("\n[run] Step 6/6 — to-sbatch")
	toSbatch.run(argparse.Namespace(
		config=config,
		input=None,
		outdir=None,
		dry_run=args.dry_run,
	))

	print("\n[run] Pipeline complete.")


def main():
	"""Primary entry point for the dorado-run CLI."""
	parser = argparse.ArgumentParser(
		prog="dorado-run",
		description="ONT Dorado Basecaller Runner",
	)
	subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

	# --- ln-pod5 ---
	parser_ln = subparsers.add_parser(
		"ln-pod5",
		help="Symlink pod5 dirs from a raw experiment tree into Input/",
	)
	parser_ln.add_argument("-s", "--source", required=True, type=Path,
		help="Root path containing raw experiment folders")
	parser_ln.add_argument("-d", "--dest", type=Path, default=Path("./Input"),
		help="Destination path where symlinks are created [%(default)s]")
	parser_ln.add_argument("-p", "--pod5-name", default="pod5_pass",
		help="Pod5 directory name to search for recursively [%(default)s]")
	parser_ln.add_argument("--clean", action="store_true",
		help="Remove all symlinks in --dest and exit")

	# --- cfg-init ---
	parser_cfg = subparsers.add_parser(
		"cfg-init",
		help="Resolve config template and write a project config.yml",
	)
	parser_cfg.add_argument("-t", "--template", default="./cfg/config_temp.yml",
		help="Path to config template YAML [%(default)s]")
	parser_cfg.add_argument("-i", "--input-dir", default="./Input",
		help="Directory to scan for pod5 symlinks [%(default)s]")
	parser_cfg.add_argument("-o", "--output", default="./config.yml",
		help="Output path for resolved config [%(default)s]")

	# --- dl-dorado ---
	parser_drd = subparsers.add_parser(
		"dl-dorado",
		help="Download and extract a Dorado release binary",
	)
	parser_drd.add_argument("-c", "--config", default="./config.yml",
		help="Config file to read version/os/arch defaults from [%(default)s]")
	parser_drd.add_argument("-v", "--version", type=str, default=None,
		help="Dorado version: 'l' for latest, or X.Y.Z [config or 'l']")
	parser_drd.add_argument("-O", "--target-os", type=str, default=None,
		help="Target OS: linux, macos [config or 'linux']")
	parser_drd.add_argument("-a", "--arch", type=str, default=None,
		help="Architecture: x64, arm64 [config or 'x64']")
	parser_drd.add_argument("-d", "--dest", type=str, default=".",
		help="Directory to extract Dorado into [%(default)s]")
	parser_drd.add_argument("-V", "--verbose", action="store_true",
		help="Enable verbose output")

	# --- dl-models ---
	parser_dlm = subparsers.add_parser(
		"dl-models",
		help="Download Dorado simplex and modification models from config.yml",
	)
	parser_dlm.add_argument("-c", "--config", default="./config.yml",
		help="Config file to read model settings from [%(default)s]")
	parser_dlm.add_argument("--dry-run", action="store_true",
		help="Print what would be downloaded without running Dorado")

	# --- gen-cmd ---
	parser_gen = subparsers.add_parser(
		"gen-cmd",
		help="Generate dorado basecaller command lines from config.yml",
	)
	parser_gen.add_argument("-c", "--config", default="./config.yml",
		help="Path to resolved config file [%(default)s]")
	parser_gen.add_argument("-o", "--output", default="./cmd.txt",
		help="Output path for generated commands [%(default)s]")
	parser_gen.add_argument("--dry-run", action="store_true",
		help="Print commands to stdout without writing a file")

	# --- to-sbatch ---
	parser_sb = subparsers.add_parser(
		"to-sbatch",
		help="Generate per-job Slurm sbatch scripts from cmd.txt",
	)
	parser_sb.add_argument("-c", "--config", default="./config.yml",
		help="Config file to read HPC settings from [%(default)s]")
	parser_sb.add_argument("-i", "--input", default=None,
		help="Path to commands file [config hpc_cmd_txt or './cmd.txt']")
	parser_sb.add_argument("-o", "--outdir", default=None,
		help="Directory to write .sbatch files into [config hpc_outdir or './Sbatch']")
	parser_sb.add_argument("--dry-run", action="store_true",
		help="Print scripts to stdout without writing files")

	# --- run (full pipeline) ---
	parser_run = subparsers.add_parser(
		"run",
		help="Full pipeline: ln-pod5 → cfg-init → dl-dorado → dl-models → gen-cmd → to-sbatch",
	)
	parser_run.add_argument("-s", "--source", required=True, type=Path,
		help="Raw experiment root dir; passed to ln-pod5")
	parser_run.add_argument("-d", "--dest", type=Path, default=Path("./Input"),
		help="Symlink destination; also used as cfg-init --input-dir [%(default)s]")
	parser_run.add_argument("-t", "--template", default="./cfg/config_temp.yml",
		help="Config template; passed to cfg-init [%(default)s]")
	parser_run.add_argument("-c", "--config", default="./config.yml",
		help="Output config path; passed to all downstream steps [%(default)s]")
	parser_run.add_argument("-p", "--pod5-name", default="pod5_pass",
		help="Pod5 subdirectory name to search for recursively [%(default)s]")
	parser_run.add_argument("--dry-run", action="store_true",
		help="Preview all pipeline steps without network or disk operations")

	args = parser.parse_args()

	if args.command is None:
		parser.print_help()
		sys.exit(0)

	try:
		if args.command == "run":
			_run_pipeline(args)
		elif args.command == "ln-pod5":
			lnPod5.run(args)
		elif args.command == "cfg-init":
			cfgInit.run(args)
		elif args.command == "dl-dorado":
			dlDorado.run(args)
		elif args.command == "dl-models":
			dlModels.run(args)
		elif args.command == "gen-cmd":
			genCMD.run(args)
		elif args.command == "to-sbatch":
			toSbatch.run(args)
		else:
			parser.print_help()
			sys.exit(1)
	except SystemExit:
		raise
	except Exception as e:
		print(f"\n[{args.command}] Error: {e}", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()
