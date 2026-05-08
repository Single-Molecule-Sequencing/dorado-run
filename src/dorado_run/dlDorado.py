# dlDorado.py
# Download Dorado release from GitHub and extract it

import json
import os
import re
import sys
import subprocess
from pathlib import Path

try:
	import yaml
	_YAML_AVAILABLE = True
except ImportError:
	_YAML_AVAILABLE = False


DRD_DL_URL_PREFIX = "https://cdn.oxfordnanoportal.com/software/analysis/"
DRD_GH_API = "https://api.github.com/repos/nanoporetech/dorado/releases/latest"


def _load_config_defaults(config_path: str) -> dict:
	"""Read drd_ver, drd_os, drd_arch from config.yml if it exists."""
	if not _YAML_AVAILABLE:
		return {}
	p = Path(config_path)
	if not p.exists():
		return {}
	try:
		with open(p, "r", encoding="utf-8") as fh:
			cfg = yaml.safe_load(fh) or {}
		return {k: cfg[k] for k in ("drd_ver", "drd_os", "drd_arch") if k in cfg}
	except Exception:
		return {}


def run(args):
	"""Execute dl-dorado logic given parsed args namespace."""
	def vprint(*a, **kw):
		if args.verbose:
			print(*a, **kw)

	# Read config defaults, then apply CLI overrides
	cfg_defaults = _load_config_defaults(args.config)
	version  = args.version     or cfg_defaults.get("drd_ver",  "l")
	drd_os   = (args.target_os  or cfg_defaults.get("drd_os",   "linux")).lower()
	drd_arch = (args.arch       or cfg_defaults.get("drd_arch", "x64")).lower()
	dest     = args.dest

	# Validate inputs
	if drd_os not in ("linux", "macos"):
		sys.exit(f"[dl-dorado] Error: Invalid OS '{drd_os}'. Choose 'linux' or 'macos'.")
	if drd_arch not in ("x64", "arm64"):
		sys.exit(f"[dl-dorado] Error: Invalid architecture '{drd_arch}'. Choose 'x64' or 'arm64'.")
	if drd_os == "macos" and drd_arch == "x64":
		sys.exit("[dl-dorado] Error: macOS x64 builds are not available. Use 'arm64'.")
	if version != "l" and not re.match(r"^\d+\.\d+\.\d+$", version):
		sys.exit(f"[dl-dorado] Error: Invalid version format '{version}'. "
		         "Use 'l' for latest or a version like '1.4.0'.")

	os.makedirs(dest, exist_ok=True)

	# Idempotency check: skip download if the expected binary already exists and is executable.
	# Only applies when version is concrete; deferred to post-resolution when version == 'l'.
	if version != "l":
		expected_exe = os.path.join(
			dest, f"dorado-{version}-{drd_os}-{drd_arch}", "bin", "dorado"
		)
		if os.path.isfile(expected_exe) and os.access(expected_exe, os.X_OK):
			print(f"[dl-dorado] Dorado {version} already present at {os.path.abspath(expected_exe)} — skipping download.")
			return

	# Resolve version
	if version == "l":
		vprint("[dl-dorado] Fetching latest Dorado version from GitHub...")
		try:
			result = subprocess.run(
				["curl", "-sf", "--fail", DRD_GH_API],
				check=True, capture_output=True, text=True,
			)
			version = json.loads(result.stdout)["tag_name"].lstrip("v")
			vprint(f"[dl-dorado] Latest version resolved: {version}")
		except subprocess.CalledProcessError as e:
			sys.exit(f"[dl-dorado] Error: Failed to reach GitHub API: {e}")
		except (KeyError, json.JSONDecodeError) as e:
			sys.exit(f"[dl-dorado] Error: Could not parse GitHub API response: {e}")

	tar_name = f"dorado-{version}-{drd_os}-{drd_arch}.tar.gz"
	url = f"{DRD_DL_URL_PREFIX}{tar_name}"

	if getattr(args, 'dry_run', False):
		print(f"[dl-dorado] [DRY-RUN] Would download Dorado {version} ({drd_os}/{drd_arch})")
		print(f"[dl-dorado] [DRY-RUN] URL: {url}")
		print(f"[dl-dorado] [DRY-RUN] Extract to: {os.path.abspath(dest)}")
		return

	tar_path = os.path.join(dest, tar_name)

	print(f"[dl-dorado] Downloading Dorado {version} ({drd_os}/{drd_arch}) → {os.path.abspath(dest)}")
	vprint(f"[dl-dorado] URL: {url}")

	try:
		try:
			subprocess.run(["curl", "-L", "--fail", url, "-o", tar_path], check=True)
			vprint("[dl-dorado] Download completed.")
		except subprocess.CalledProcessError as e:
			sys.exit(f"[dl-dorado] Error: Download failed: {e}")

		if not os.path.exists(tar_path) or os.path.getsize(tar_path) == 0:
			sys.exit("[dl-dorado] Error: Downloaded file is missing or empty.")

		try:
			subprocess.run(["tar", "-tzf", tar_path], check=True, capture_output=True)
			vprint("[dl-dorado] Archive integrity verified.")
		except subprocess.CalledProcessError:
			sys.exit("[dl-dorado] Error: Downloaded archive is corrupt or invalid.")

		vprint("[dl-dorado] Extracting Dorado...")
		try:
			subprocess.run(["tar", "-xzf", tar_path, "-C", dest], check=True)
			vprint("[dl-dorado] Extraction completed.")
		except subprocess.CalledProcessError as e:
			sys.exit(f"[dl-dorado] Error extracting Dorado: {e}")

	finally:
		if os.path.exists(tar_path):
			os.remove(tar_path)
			vprint("[dl-dorado] Cleaned up archive.")

	drd_exe = os.path.join(dest, f"dorado-{version}-{drd_os}-{drd_arch}", "bin", "dorado")
	if not os.path.isfile(drd_exe):
		sys.exit(f"[dl-dorado] Error: Expected executable not found at {drd_exe}")

	print(f"[dl-dorado] Dorado is ready at {os.path.abspath(drd_exe)}")
