# lnPod5.py
# Stage Pod5 directories using symlinks for Dorado basecalling

import os
import sys
from pathlib import Path


def _clean_symlinks(destdir: Path) -> int:
	"""Remove all symlinks in destdir. Returns count removed."""
	link_count = 0
	if not destdir.exists():
		return 0
	for item in sorted(destdir.iterdir()):
		if item.is_symlink():
			try:
				item.unlink()
				link_count += 1
			except Exception as e:
				print(f"[ln-pod5] Error removing {item.name}: {e}", file=sys.stderr)
		elif item.is_dir():
			print(f"[ln-pod5] Skipped physical directory: {item.name}")
	return link_count


def run(args):
	"""Execute ln-pod5 logic given parsed args namespace."""
	dest = Path(args.dest) if not isinstance(args.dest, Path) else args.dest

	# --- clean mode ---
	if args.clean:
		destdir = dest.resolve()
		if not destdir.exists():
			sys.exit(f"[ln-pod5] Error: Destination directory does not exist: {destdir}")
		print(f"[ln-pod5] Removing symlinks in {destdir}")
		removed = _clean_symlinks(destdir)
		print(f"[ln-pod5] Removed {removed} symlinks.")
		return

	# --- override mode: single pod5 dir with custom experiment name ---
	override_pod5 = getattr(args, 'override_pod5_dir', None)
	override_name = getattr(args, 'override_experiment_name', None)
	if override_pod5 and override_name:
		destdir = dest.resolve()
		destdir.mkdir(parents=True, exist_ok=True)
		removed = _clean_symlinks(destdir)
		if removed:
			print(f"[ln-pod5] Cleared {removed} existing symlink(s) from {destdir}")
		override_path = Path(override_pod5).resolve()
		if not override_path.exists():
			sys.exit(f"[ln-pod5] Error: Override pod5 directory does not exist: {override_path}")
		link_name = f"{override_name}_{override_path.name}"
		dest_link = destdir / link_name
		dest_link.symlink_to(override_path)
		print(f"[ln-pod5] Override: Linked {link_name} -> {override_path}")
		print(f"[ln-pod5] Linked 1 pod5 directory to {destdir}")
		return

	# --- link mode ---
	if not args.source:
		sys.exit("[ln-pod5] Error: --source is required unless using --clean or override")

	srcdir  = Path(args.source).resolve()
	destdir = dest.resolve()

	if not srcdir.exists():
		sys.exit(f"[ln-pod5] Error: Source directory does not exist: {srcdir}")
	destdir.mkdir(parents=True, exist_ok=True)

	# Pre-flight clean: remove any existing symlinks before creating new ones
	removed = _clean_symlinks(destdir)
	if removed:
		print(f"[ln-pod5] Cleared {removed} existing symlink(s) from {destdir}")

	print(f"[ln-pod5] Scanning {srcdir} -> Linking to {destdir}")

	link_count = 0
	for dirpath, dirnames, _ in os.walk(srcdir, followlinks=False):
		dirnames[:] = sorted(dirnames)   # walk in deterministic order
		current = Path(dirpath)
		if current.name != args.pod5_name:
			continue

		# Derive experiment name from the top-level directory under srcdir
		experiment_name = current.relative_to(srcdir).parts[0]

		# Pre-demux: no barcode subdirs; post-demux: barcode subdirs present
		subdirs = sorted([current / d for d in dirnames])

		if subdirs:
			# Post-demux: link each barcode directory individually
			for barcode_dir in subdirs:
				link_name = f"{experiment_name}_{barcode_dir.name}"
				dest_link = destdir / link_name
				dest_link.symlink_to(barcode_dir.resolve())
				print(f"  Linked: {link_name}")
				link_count += 1
		else:
			# Pre-demux: link the pod5 directory itself
			dest_link = destdir / experiment_name
			dest_link.symlink_to(current.resolve())
			print(f"  Linked: {experiment_name} (pre-demux)")
			link_count += 1

		# Do not descend further into a matched pod5 directory.
		dirnames.clear()

	print(f"[ln-pod5] Linked {link_count} pod5 directories to {destdir}")

