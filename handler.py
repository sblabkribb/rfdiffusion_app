# handler.py
import base64
import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
import runpod


RFD_REPO_DIR = Path("/app/RFdiffusion")
PYTHON_BIN = os.environ.get("RF_PYTHON_BIN", "python")
DEFAULT_MODEL_SUBDIR = os.environ.get("RF_MODEL_SUBDIR", "rfdiffusion_models")


def run(job):
    job_input = job["input"]

    # 1. 입력 데이터 파싱
    pdb_b64 = job_input["pdb_file"]
    pdb_bytes = base64.b64decode(pdb_b64)
    commands = job_input.get("commands", [])

    try:
        model_dir = _prepare_model_directory(job_input.get("model_directory_path"))
    except Exception as prep_err:
        return {
            "error": f"Failed to prepare model directory: {prep_err}"
        }

    # 2. 임시 작업 디렉토리
    with tempfile.TemporaryDirectory() as tmpdir:
        input_pdb = os.path.join(tmpdir, "input.pdb")
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(output_dir, exist_ok=True)

        with open(input_pdb, "wb") as f:
            f.write(pdb_bytes)

        # 3. 명령어 구성
        cmd = [
            PYTHON_BIN,
            str(RFD_REPO_DIR / "scripts/run_inference.py"),
            f"inference.input_pdb={input_pdb}",
            f"inference.output_prefix={output_dir}/design",
            f"inference.model_directory_path={model_dir}",
        ] + commands

        print("Running command:", " ".join(cmd))

        # 4. 실행
        try:
            result = subprocess.run(
                cmd,
                cwd=str(RFD_REPO_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
        except subprocess.CalledProcessError as e:
            return {
                "error": str(e),
                "stderr": e.stderr,
                "stdout": e.stdout,
            }

        # 5. 결과 ZIP + base64
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(output_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, output_dir)
                    zf.write(full_path, arcname)

        zip_buffer.seek(0)
        return {
            "result_zip_b64": base64.b64encode(zip_buffer.getvalue()).decode("utf-8"),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }


def _prepare_model_directory(requested_path):
    resolved_path = _resolve_model_directory(requested_path)
    _ensure_models(resolved_path)
    return str(resolved_path)


def _resolve_model_directory(requested_path):
    if requested_path:
        return Path(requested_path).expanduser()

    env_override = os.environ.get("RF_MODEL_DIR")
    if env_override:
        return Path(env_override).expanduser()

    mount_candidates = []
    for env_var in ("RUNPOD_MOUNT_PATH", "RUNPOD_NETWORK_MOUNT", "RUNPOD_PERSISTENT_MOUNT"):
        mount_path = os.environ.get(env_var)
        if mount_path:
            mount_candidates.append(Path(mount_path))

    mount_candidates.extend([
        Path("/workspace/network_storage"),
        Path("/workspace"),
    ])

    for base in mount_candidates:
        candidate = base / DEFAULT_MODEL_SUBDIR
        if _models_exist(candidate):
            return candidate

    base = mount_candidates[0] if mount_candidates else Path("/workspace")
    return base / DEFAULT_MODEL_SUBDIR


def _models_exist(path: Path) -> bool:
    if not path.exists():
        return False

    for pattern in ("**/*.pt", "**/*.ckpt", "**/*.pkl"):
        if any(path.glob(pattern)):
            return True
    return False


def _ensure_models(target_path: Path):
    target_path = target_path.expanduser()
    if _models_exist(target_path):
        return

    target_path.mkdir(parents=True, exist_ok=True)
    print(f"Model files not found in {target_path}, downloading via RFdiffusion script...")

    src_models_dir = RFD_REPO_DIR / "models"
    if not _models_exist(src_models_dir):
        # RFdiffusion repo uses a bash script for model download (download_models.sh)
        # Older references may point to a Python script; prefer the bash script when present.
        sh_script = RFD_REPO_DIR / "scripts" / "download_models.sh"
        py_script = RFD_REPO_DIR / "scripts" / "download_models.py"
        try:
            if sh_script.exists():
                download_cmd = ["bash", str(sh_script), "models"]
            elif py_script.exists():
                download_cmd = [PYTHON_BIN, str(py_script)]
            else:
                raise RuntimeError(
                    "Neither download_models.sh nor download_models.py found in RFdiffusion/scripts."
                )

            subprocess.run(
                download_cmd,
                cwd=str(RFD_REPO_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as download_err:
            raise RuntimeError(
                f"Model download script failed: {download_err.stderr or download_err.stdout}"
            ) from download_err

    if not src_models_dir.exists():
        raise RuntimeError("Model download script completed but /app/RFdiffusion/models does not exist.")

    for item in src_models_dir.iterdir():
        dest = target_path / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    if not _models_exist(target_path):
        raise RuntimeError("Model download finished but no weight files found in target directory.")


if __name__ == "__main__":
    # Start RunPod serverless worker using the `run` function as handler
    runpod.serverless.start({"handler": run})
