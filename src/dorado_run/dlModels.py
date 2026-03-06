# dlModels.py
# Download Dorado simplex and modification models from config.yml

import subprocess
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# mods_flag bit-flag decode
# ---------------------------------------------------------------------------
# Bit layout: bit 3 (value 8) = 6mA; bits 0-2 = cytosine mod (0=none, 1-4)
_CYTO_MAP = {
	1: "5mCG_5hmCG",
	2: "5mC_5hmC",
	3: "4mC_5mC",
	4: "5mC",
}


def decode_mods_flag(flag: int) -> list:
	"""Return list of mod type strings implied by mods_flag integer."""
	mods = []
	cyto    = flag & 0x07
	adenine = bool(flag & 0x08)
	if cyto:
		mod = _CYTO_MAP.get(cyto)
		if mod is None:
			sys.exit(f"[dl-models] Error: mods_flag cytosine bits value {cyto} is not valid (1-4).")
		mods.append(mod)
	if adenine:
		mods.append("6mA")
	return mods


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config(config_path: str) -> dict:
	p = Path(config_path)
	if not p.exists():
		sys.exit(f"[dl-models] Error: Config file not found: {p}")
	with open(p, "r", encoding="utf-8") as fh:
		return yaml.safe_load(fh) or {}


def _get_list_yaml(dorado_exe: str) -> list:
	"""Run 'dorado download --list-yaml' and return the modification models list.

	Dorado emits a YAML dict keyed by model category; values are plain lists of
	model name strings.  Returns the list under 'modification models'.
	"""
	try:
		result = subprocess.run(
			[dorado_exe, "download", "--list-yaml"],
			check=True, capture_output=True, text=True,
		)
	except subprocess.CalledProcessError as e:
		sys.exit(f"[dl-models] Error: 'dorado download --list-yaml' failed: {e}")
	try:
		data = yaml.safe_load(result.stdout)
	except yaml.YAMLError as e:
		sys.exit(f"[dl-models] Error: Could not parse dorado list-yaml output: {e}")
	if not isinstance(data, dict):
		sys.exit("[dl-models] Error: Unexpected format from 'dorado download --list-yaml'.")
	return data.get("modification models", [])


def _candidates_for_mod(list_data: list, simplex_ver: str, mod_type: str) -> list:
	"""
	Return mod model name strings from list_data that match simplex_ver and mod_type.

	Matching uses exact token boundaries: '@v{simplex_ver}_' for the simplex version
	and '_{mod_type}@v' for the mod type.  Version strings follow X.Y.Z format.
	"""
	candidates = []
	for name in list_data:
		if not isinstance(name, str):
			continue
		if not name.startswith("dna"):
			continue
		if "polish_bacterial_methylation" in name:
			continue
		# mod type token boundary: _<mod_type>@v
		if f"_{mod_type}@v" not in name:
			continue
		# simplex version token boundary: @v<ver>_
		if simplex_ver and f"@v{simplex_ver}_" not in name:
			continue
		candidates.append(name)
	return candidates


def _latest_of(model_names: list):
	"""Pick the model name with the highest mod version from the last @v<ver> segment."""
	if not model_names:
		return None
	def ver_key(name):
		parts = name.split("@v")
		if len(parts) < 2:
			return (0,)
		tag = parts[-1]  # last @v<ver> segment
		result = []
		for part in tag.split("."):
			try:
				result.append(int(part))
			except ValueError:
				result.append(0)
		return tuple(result)
	return max(model_names, key=ver_key)


def _download_model(dorado_exe: str, model_name: str, models_dir: str, dry_run: bool) -> bool:
	"""Download a single model. Returns True if downloaded, False if skipped."""
	target = Path(models_dir) / model_name
	if target.exists():
		print(f"  Skipped (exists): {model_name}")
		return False
	cmd = [dorado_exe, "download", "--model", model_name, "--models-directory", models_dir]
	if dry_run:
		print(f"  [DRY-RUN] Would run: {' '.join(cmd)}")
		return True
	Path(models_dir).mkdir(parents=True, exist_ok=True)
	print(f"  Downloading: {model_name}")
	try:
		subprocess.run(cmd, check=True)
	except subprocess.CalledProcessError as e:
		sys.exit(f"[dl-models] Error: Download failed for {model_name}: {e}")
	return True


# ---------------------------------------------------------------------------
# Module interface
# ---------------------------------------------------------------------------


def run(args):
	"""Execute dl-models logic given parsed args namespace."""
	cfg = _load_config(args.config)

	dorado_exe        = cfg.get("drd_exe", "dorado")
	simplex_ver       = cfg.get("simplex_model_ver", "")
	simplex_tier      = cfg.get("simplex_model_tier", "sup")
	model_prefix      = cfg.get("dna_model_prefix", "dna_r10.4.1_e8.2_400bps_")
	simplex_dir       = cfg.get("simplex_model_dir", "./Models/Simplex")
	mods_flag         = int(cfg.get("mods_flag", 0))
	mods_ver_override = cfg.get("mods_ver") or {}
	mods_dir          = cfg.get("mods_model_dir", "./Models/Mods")

	if not dorado_exe:
		sys.exit("[dl-models] Error: 'drd_exe' not set in config.")

	downloaded = 0
	skipped    = 0

	# --- Simplex model ---
	simplex_name = f"{model_prefix}{simplex_tier}@v{simplex_ver}"
	print(f"[dl-models] Simplex model: {simplex_name}")
	if _download_model(dorado_exe, simplex_name, simplex_dir, args.dry_run):
		downloaded += 1
	else:
		skipped += 1

	# --- Modification models ---
	if mods_flag == 0:
		print("[dl-models] mods_flag = 0 → skipping modification models.")
	else:
		mod_types = decode_mods_flag(mods_flag)
		print(f"[dl-models] mods_flag = {mods_flag} → mod types: {', '.join(mod_types)}")
		list_data = _get_list_yaml(dorado_exe)

		for mod_type in mod_types:
			print(f"[dl-models] Resolving mod model for: {mod_type}")
			candidates = _candidates_for_mod(list_data, simplex_ver, mod_type)
			if not candidates:
				print(f"  [WARNING] No candidates found for {mod_type} "
				      f"(simplex ver {simplex_ver}). Skipping.", file=sys.stderr)
				continue

			pinned = mods_ver_override.get(mod_type) if isinstance(mods_ver_override, dict) else None
			if pinned:
				matching = [c for c in candidates if f"@v{pinned}" in c]
				if not matching:
					sys.exit(f"[dl-models] Error: No model found for {mod_type} with pinned "
					         f"version '{pinned}'. Available: {candidates}")
				model_name = matching[-1]
				print(f"  Pinned version {pinned}: {model_name}")
			else:
				model_name = _latest_of(candidates)
				print(f"  Latest: {model_name}")

			if _download_model(dorado_exe, model_name, mods_dir, args.dry_run):
				downloaded += 1
			else:
				skipped += 1

	tag = "[DRY-RUN] " if args.dry_run else ""
	print(f"[dl-models] {tag}Done. Downloaded: {downloaded}, Skipped: {skipped}")

