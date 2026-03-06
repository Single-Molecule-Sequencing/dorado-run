# dorado-run

A Python CLI tool for orchestrating [Oxford Nanopore Dorado](https://github.com/nanoporetech/dorado) basecalling on HPC and local systems. It handles pod5 staging, config resolution, binary and model downloads, command generation, and Slurm job submission — each as an independently runnable subcommand or chained together with a single `run` call.

> **System requirement:** `curl` must be on `$PATH` (used by `dl-dorado` to fetch releases from GitHub).

---

## Installation

### 1. Create and activate the conda environment

```bash
conda env create -f env/env.yml
conda activate dorado-run
```

### 2. Install the package

Expose the `dorado-run` command.

```bash
pip install -e .
```

---

## Manifest

All modules are in `src/dorado_run/`.

| Module        | Subcommand  | Description                                                   |
| ------------- | ----------- | ------------------------------------------------------------- |
| `lnPod5.py`   | `ln-pod5`   | Symlink pod5 dirs from a raw experiment tree into `Input/`    |
| `cfgInit.py`  | `cfg-init`  | Resolve `config_temp.yml` placeholders and write `config.yml` |
| `dlDorado.py` | `dl-dorado` | Download and extract a Dorado release binary from GitHub      |
| `dlModels.py` | `dl-models` | Download Dorado simplex and modification models               |
| `genCMD.py`   | `gen-cmd`   | Generate dorado basecaller shell commands into `cmd.txt`      |
| `toSbatch.py` | `to-sbatch` | Generate per-job Slurm `.sbatch` scripts from `cmd.txt`       |
| `cli.py`      | *(entry)*   | Central argparse entry point; also exposes the `run` pipeline |

---

## Usage

### Push-button run

Edit `cfg/config_temp.yml`, then run the full pipeline with a single command:

```bash
dorado-run run -s /path/to/raw/experiments/with/pod5/dirs
```

This chains all steps in order: `ln-pod5` → `cfg-init` → `dl-dorado` → `dl-models` → `gen-cmd`.

| Flag              | Default                 | Description                                              |
| ----------------- | ----------------------- | -------------------------------------------------------- |
| `-s, --source`    | *(required)*            | Raw experiment root dir; passed to `ln-pod5`             |
| `-d, --dest`      | `./Input`               | Symlink destination; also used as `cfg-init --input-dir` |
| `-t, --template`  | `./cfg/config_temp.yml` | Config template; passed to `cfg-init`                    |
| `-c, --config`    | `./config.yml`          | Output config path; passed to all downstream steps       |
| `-p, --pod5-name` | `pod5_pass`             | Pod5 subdirectory name to search for recursively         |
| `--dry-run`       | `False`                 | Preview all steps without network or disk operations     |

### Individual subcommands

Each step can be run independently at any time:

```bash
dorado-run ln-pod5    -s <raw_dir> [-d <dest>] [-p <pod5_name>]
dorado-run cfg-init   [-t <template>] [-i <input_dir>] [-o <output>]
dorado-run dl-dorado  [-v <version>] [-O <os>] [-a <arch>] [-d <dest>]
dorado-run dl-models  [-c <config>] [--dry-run]
dorado-run gen-cmd    [-c <config>] [-o <cmd_txt>] [--dry-run]
dorado-run to-sbatch  [-c <config>] [-i <cmd_txt>] [-o <outdir>] [--dry-run]
```

---

#### `ln-pod5`

Recursively finds pod5 directories under `--source` and symlinks them into `--dest`. Handles both pre-demux (no barcode subdirs) and post-demux (barcode subdirs present) layouts.

| Flag              | Default      | Description                                   |
| ----------------- | ------------ | --------------------------------------------- |
| `-s, --source`    | *(required)* | Root path containing raw experiment folders   |
| `-d, --dest`      | `./Input`    | Destination path where symlinks are created   |
| `-p, --pod5-name` | `pod5_pass`  | Pod5 directory name to search for recursively |
| `--clean`         | `False`      | Remove all symlinks in `--dest` and exit      |

```bash
dorado-run ln-pod5 -s /data/runs/2026-03-01 -d ./Input
```

---

#### `cfg-init`

Reads `config_temp.yml`, resolves `{placeholder}` references between keys, converts all path keys to absolute paths, scans `--input-dir` for pod5 symlinks/subdirs, and writes the fully resolved `config.yml`.

> **CWD note:** All `dorado-run` subcommands must be run from the project root. Path resolution in `cfg-init` (and all subsequent steps) is relative to the working directory when the command is invoked.

| Flag              | Default                 | Description                         |
| ----------------- | ----------------------- | ----------------------------------- |
| `-t, --template`  | `./cfg/config_temp.yml` | Path to the config template         |
| `-i, --input-dir` | `./Input`               | Directory to scan for pod5 symlinks |
| `-o, --output`    | `./config.yml`          | Output path for the resolved config |

```bash
dorado-run cfg-init -t cfg/config_temp.yml -i ./Input -o config.yml
```

---

#### `dl-dorado`

Downloads the specified Dorado release tarball from the ONT CDN and extracts it. Version, OS, and architecture are read from `config.yml` by default; CLI flags override.

| Flag              | Default               | Description                                         |
| ----------------- | --------------------- | --------------------------------------------------- |
| `-c, --config`    | `./config.yml`        | Config file to read `drd_ver`/`drd_os`/`drd_arch`   |
| `-v, --version`   | *(config or `l`)*     | Dorado version: `l` for latest, or `X.Y.Z`          |
| `-O, --target-os` | *(config or `linux`)* | Target OS: `linux` or `macos`                       |
| `-a, --arch`      | *(config or `x64`)*   | Architecture: `x64` or `arm64`                      |
| `-d, --dest`      | `.`                   | Directory to extract Dorado into                    |
| `-V, --verbose`   | `False`               | Enable verbose output                               |

```bash
dorado-run dl-dorado -v 0.9.1 -O linux -a x64 -d .
```

---

#### `dl-models`

Downloads the simplex basecalling model and any modification models specified by `mods_flag` in `config.yml`. Uses `dorado download --list-yaml` to discover available model versions. Skips models that are already present on disk.

| Flag           | Default        | Description                                    |
| -------------- | -------------- | ---------------------------------------------- |
| `-c, --config` | `./config.yml` | Config file to read model settings from        |
| `--dry-run`    | `False`        | Print what would be downloaded without running |

```bash
dorado-run dl-models --dry-run
dorado-run dl-models
```

---

#### `gen-cmd`

Reads `config.yml` and generates a `dorado basecaller` shell command for each pod5 directory. When `trim: both`, two commands are written per sample — one with adapter trimming (`_trim1` suffix) and one without (`_trim0` suffix). When `trim: yes`, the output is suffixed `_trim1`. When `trim: no`, the output is suffixed `_trim0`.

| Flag           | Default        | Description                              |
| -------------- | -------------- | ---------------------------------------- |
| `-c, --config` | `./config.yml` | Resolved config file                     |
| `-o, --output` | `./cmd.txt`    | Path for the output commands file        |
| `--dry-run`    | `False`        | Print commands to stdout without writing |

```bash
dorado-run gen-cmd --dry-run
dorado-run gen-cmd -o cmd.txt
```

---

#### `to-sbatch`

Reads `cmd.txt` and generates one `.sbatch` script per line, using HPC settings from `config.yml`. Log files are written to `{outdir}/Logs/` via `%x_%j.out/err`.

`hpc_account` **must** be set in `config.yml` before running this subcommand.

| Flag           | Default        | Description                                               |
| -------------- | -------------- | --------------------------------------------------------- |
| `-c, --config` | `./config.yml` | Config file to read HPC settings from                     |
| `-i, --input`  | `./cmd.txt`    | Path to commands file (or `hpc_cmd_txt` in config)        |
| `-o, --outdir` | `./Sbatch`     | Directory for `.sbatch` files (or `hpc_outdir` in config) |
| `--dry-run`    | `False`        | Print scripts to stdout without writing files             |

```bash
dorado-run to-sbatch --dry-run
dorado-run to-sbatch -o Sbatch/
```

---

## `cfg/config_temp.yml`

Copy and edit before running. `cfg-init` reads this file and writes the resolved `config.yml`.

### Basecalling settings

| Key                  | Default                                               | Description                                  |
| -------------------- | ----------------------------------------------------- | -------------------------------------------- |
| `drd_ver`            | `"1.4.0"`                                             | Dorado release version                       |
| `drd_os`             | `"linux"`                                             | Target OS for the binary (`linux` / `macos`) |
| `drd_arch`           | `"x64"`                                               | CPU architecture (`x64` / `arm64`)           |
| `drd_exe`            | `"./dorado-{drd_ver}-{drd_os}-{drd_arch}/bin/dorado"` | Resolved path to Dorado binary               |
| `simplex_model_ver`  | `"5.0.0"`                                             | Simplex model version                        |
| `simplex_model_tier` | `"sup"`                                               | Model tier: `sup`, `hac`, or `fast`          |
| `dna_model_prefix`   | `"dna_r10.4.1_e8.2_400bps_"`                          | Model name prefix                            |
| `mods_flag`          | `0`                                                   | Modifications bit-flag (see table below)     |
| `mods_ver`           | `null`                                                | Per-mod-type version pin (`null` = latest)   |
| `trim`               | `"yes"`                                               | Trim adapter: `yes`, `no`, or `both`         |
| `gpu`                | `"auto"`                                              | GPU selector passed to `-x`                  |
| `models_dir`         | `"./Models"`                                          | Root directory for downloaded models         |
| `simplex_model_dir`  | `"{models_dir}/Simplex"`                              | Destination for simplex model                |
| `mods_model_dir`     | `"{models_dir}/Mods"`                                 | Destination for modification models          |
| `output_directory`   | `"./Output"`                                          | Directory for output BAM files               |

### `mods_flag` values

| Flag | Modification(s)      |
| ---- | -------------------- |
| `0`  | none (simplex only)  |
| `1`  | `5mCG_5hmCG`         |
| `2`  | `5mC_5hmC`           |
| `3`  | `4mC_5mC`            |
| `4`  | `5mC`                |
| `8`  | `6mA`                |
| `9`  | `6mA` + `5mCG_5hmCG` |
| `10` | `6mA` + `5mC_5hmC`   |
| `11` | `6mA` + `4mC_5mC`    |
| `12` | `6mA` + `5mC`        |

### HPC / Slurm settings

| Key              | Default      | Description                                                         |
| ---------------- | ------------ | ------------------------------------------------------------------- |
| `hpc_account`    | `null`       | **Required** — Slurm account / allocation name                      |
| `hpc_partition`  | `"gpu"`      | Slurm partition                                                     |
| `hpc_gres`       | `"gpu:1"`    | Full Slurm GRES string (e.g. `gpu:nvidia_a100_80gb_pcie_3g.40gb:1`) |
| `hpc_cpus`       | `8`          | CPUs per task                                                       |
| `hpc_mem`        | `"32G"`      | Memory per task                                                     |
| `hpc_time`       | `"12:00:00"` | Walltime (HH:MM:SS)                                                 |
| `hpc_email`      | `null`       | Email for BEGIN/END/FAIL notifications (`null` to disable)          |
| `hpc_job_prefix` | `"dorado"`   | Prefix prepended to Slurm job names                                 |
| `hpc_module`     | `null`       | `module load <value>` line inserted in each script                  |
| `hpc_outdir`     | `"./Sbatch"` | Directory where `.sbatch` scripts are written                       |

---

## Workflow

```txt
Input:
  Raw experiment tree   e.g. /data/runs/2026-03-01/
  Config template       cfg/config_temp.yml
        │
        ▼
┌─────────────────────────┐
│  1. ln-pod5             │  Symlinks pod5 dirs → Input/
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│  2. cfg-init            │  Resolves paths, scans Input/ → config.yml
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│  3. dl-dorado           │  Downloads & extracts Dorado binary
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│  4. dl-models           │  Downloads simplex [+ mods] models
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│  5. gen-cmd             │  Writes dorado basecaller commands → cmd.txt
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│  6. to-sbatch           │  (optional) Generates Slurm .sbatch scripts
└─────────────────────────┘
        │
        ▼
  Output/<sample>.bam
```
