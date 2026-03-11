"""
Protein Design Studio V3 — Flask Backend
SSH/SLURM integration for binder design workflows
"""
import os
import sys
import json
import uuid
import time
import threading
import webbrowser
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

import paramiko
from scp import SCPClient

# ─── PyInstaller Frozen Path Detection ────────────────────────
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle — _MEIPASS is where bundled data lives
    BASE_DIR = sys._MEIPASS
else:
    # Running as normal Python script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')

# ─── CORS Support ─────────────────────────────────────────────
# Allow cross-origin requests so the GitHub Pages frontend can
# call this local server for SSH/SLURM operations.
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ─── Configuration ────────────────────────────────────────────
SETTINGS_DIR = Path.home() / '.protein-studio-v3'
SETTINGS_FILE = SETTINGS_DIR / 'settings.json'
JOBS_FILE = SETTINGS_DIR / 'jobs.json'
UPLOAD_DIR = SETTINGS_DIR / 'uploads'

DEFAULT_SETTINGS = {
    'host': '',
    'username': '',
    'key_path': str(Path.home() / '.ssh' / 'id_rsa'),
    'remote_base': '',
    'partition': '',
    'gpu_type': '',
    'conda_path': '',
    'bindcraft_path': '',
    'pepmlm_path': '',
    'rfantibody_path': '',
    'mpnn_path': '',
}

# Ensure directories exist
SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─── SSH Helpers ──────────────────────────────────────────────

def get_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r') as f:
            saved = json.load(f)
        # Merge with defaults for any missing keys
        merged = {**DEFAULT_SETTINGS, **saved}
        return merged
    return dict(DEFAULT_SETTINGS)

def save_settings(data):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_ssh_client():
    """Create and return a connected SSH client."""
    settings = get_settings()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key_path = settings['key_path']
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"SSH key not found: {key_path}")

    client.connect(
        hostname=settings['host'],
        username=settings['username'],
        key_filename=key_path,
        timeout=15
    )
    return client

def ssh_exec(cmd):
    """Execute a command via SSH and return (stdout, stderr, exit_code)."""
    client = get_ssh_client()
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
        exit_code = stdout.channel.recv_exit_status()
        return stdout.read().decode('utf-8', errors='replace'), \
               stderr.read().decode('utf-8', errors='replace'), \
               exit_code
    finally:
        client.close()

def scp_upload(local_path, remote_path):
    """Upload a file via SCP."""
    client = get_ssh_client()
    try:
        with SCPClient(client.get_transport()) as scp:
            scp.put(local_path, remote_path)
    finally:
        client.close()

def scp_download(remote_path, local_path):
    """Download a file via SCP."""
    client = get_ssh_client()
    try:
        with SCPClient(client.get_transport()) as scp:
            scp.get(remote_path, local_path)
    finally:
        client.close()

# ─── Jobs Database ────────────────────────────────────────────

def load_jobs():
    if JOBS_FILE.exists():
        with open(JOBS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_jobs(jobs):
    with open(JOBS_FILE, 'w') as f:
        json.dump(jobs, f, indent=2)

def add_job(job):
    jobs = load_jobs()
    jobs.insert(0, job)
    save_jobs(jobs)
    return job

def update_job(job_id, updates):
    jobs = load_jobs()
    for j in jobs:
        if j['id'] == job_id:
            j.update(updates)
            break
    save_jobs(jobs)

# ─── SLURM Helpers ────────────────────────────────────────────

def check_slurm_status(slurm_job_id):
    """Check SLURM job status via squeue, fallback to sacct."""
    try:
        stdout, stderr, code = ssh_exec(
            f"squeue -j {slurm_job_id} -h -o '%T' 2>/dev/null"
        )
        status = stdout.strip()
        if status:
            return status  # RUNNING, PENDING, COMPLETING, etc.

        # Job not in queue — check accounting
        stdout, stderr, code = ssh_exec(
            f"sacct -j {slurm_job_id} -o State -n -X 2>/dev/null"
        )
        status = stdout.strip().split('\n')[0].strip() if stdout.strip() else 'UNKNOWN'
        return status  # COMPLETED, FAILED, TIMEOUT, etc.
    except Exception:
        return 'UNKNOWN'

def get_slurm_log(slurm_job_id, remote_dir, offset=0):
    """Get SLURM output log content."""
    try:
        log_path = f"{remote_dir}/slurm_{slurm_job_id}.out"
        stdout, stderr, code = ssh_exec(f"tail -c +{offset + 1} {log_path} 2>/dev/null")
        return stdout
    except Exception:
        return ''

# ─── API Routes ───────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/api/ping', methods=['GET'])
def api_ping():
    """Health check for frontend auto-detection."""
    return jsonify({'status': 'ok', 'server': 'Protein Design Studio V3'})

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    settings = get_settings()
    # Don't send key content, just path
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.get_json()
    save_settings(data)
    return jsonify({'status': 'ok'})

@app.route('/api/connect', methods=['POST'])
def api_connect():
    """Test SSH connection to remote server."""
    try:
        stdout, stderr, code = ssh_exec('hostname && whoami && echo "OK"')
        return jsonify({
            'status': 'ok',
            'hostname': stdout.strip().split('\n')[0],
            'user': stdout.strip().split('\n')[1] if len(stdout.strip().split('\n')) > 1 else '',
            'message': 'Connected successfully'
        })
    except FileNotFoundError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/jobs', methods=['GET'])
def api_list_jobs():
    jobs = load_jobs()
    return jsonify(jobs)

@app.route('/api/jobs/<job_id>/status', methods=['GET'])
def api_job_status(job_id):
    jobs = load_jobs()
    job = next((j for j in jobs if j['id'] == job_id), None)
    if not job:
        return jsonify({'status': 'error', 'message': 'Job not found'}), 404

    if job.get('slurm_id') and job.get('status') not in ('COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED'):
        slurm_status = check_slurm_status(job['slurm_id'])
        job['status'] = slurm_status
        update_job(job_id, {'status': slurm_status})

    return jsonify(job)

@app.route('/api/jobs/<job_id>/logs', methods=['GET'])
def api_job_logs(job_id):
    jobs = load_jobs()
    job = next((j for j in jobs if j['id'] == job_id), None)
    if not job:
        return jsonify({'logs': ''}), 404

    offset = request.args.get('offset', 0, type=int)
    logs = get_slurm_log(job.get('slurm_id', ''), job.get('remote_dir', ''), offset)
    return jsonify({'logs': logs, 'offset': offset + len(logs)})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Upload a PDB file to the server."""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400

    f = request.files['file']
    filename = f.filename
    local_path = str(UPLOAD_DIR / filename)
    f.save(local_path)

    settings = get_settings()
    remote_path = f"{settings['remote_base']}/uploads/{filename}"

    try:
        ssh_exec(f"mkdir -p {settings['remote_base']}/uploads")
        scp_upload(local_path, remote_path)
        return jsonify({'status': 'ok', 'remote_path': remote_path, 'filename': filename})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ─── BindCraft Submit ─────────────────────────────────────────

@app.route('/api/submit/bindcraft', methods=['POST'])
def api_submit_bindcraft():
    data = request.get_json()
    settings = get_settings()

    job_id = str(uuid.uuid4())[:8]
    job_name = data.get('job_name', f'bindcraft_{job_id}')
    target_pdb = data.get('target_pdb', '')
    target_chain = data.get('target_chain', 'A')
    hotspots = data.get('hotspots', '')
    intensity = data.get('intensity', 'Standard')
    helicity = data.get('helicity', '-3')
    beta_sheet = data.get('beta_sheet', False)
    omit_aas = data.get('omit_aas', 'C')
    num_designs = data.get('num_designs', 10)

    # Intensity presets
    intensities = {
        'Draft': {'soft_iters': 40, 'temp_iters': 20},
        'Standard': {'soft_iters': 75, 'temp_iters': 45},
        'High-Res': {'soft_iters': 150, 'temp_iters': 100},
    }
    preset = intensities.get(intensity, intensities['Standard'])

    remote_dir = f"{settings['remote_base']}/jobs/{job_name}"
    bindcraft_path = settings['bindcraft_path']

    # Generate settings.json for BindCraft
    bc_settings = {
        'design_path': f'{remote_dir}/',
        'starting_pdb': f'{remote_dir}/target.pdb',
        'chains': target_chain,
        'hotspots': hotspots,
        'soft_iters': preset['soft_iters'],
        'temp_iters': preset['temp_iters'],
        'helicity_value': float(helicity),
        'beta_sheet_bias': beta_sheet,
        'omit_AAs': omit_aas,
        'num_designs': int(num_designs),
    }

    # Generate SLURM script
    slurm_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition={settings['partition']}
#SBATCH --gres={settings['gpu_type']}
#SBATCH --output={remote_dir}/slurm_%j.out
#SBATCH --error={remote_dir}/slurm_%j.err
#SBATCH --time=48:00:00
#SBATCH --mem=32G

# JAX environment fixes
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export JAX_COMPILATION_CACHE_DIR=/tmp/jax_cache_$SLURM_JOB_ID
mkdir -p $JAX_COMPILATION_CACHE_DIR

# Activate environment
source {settings['conda_path']}/etc/profile.d/conda.sh
conda activate {bindcraft_path}/bindcraft_env 2>/dev/null || conda activate bindcraft

cd {bindcraft_path}
python bindcraft.py \\
    --settings {remote_dir}/settings.json \\
    --filters {bindcraft_path}/default_filter_settings.json \\
    --advanced {bindcraft_path}/default_advanced_settings.json
"""

    try:
        # Create remote directory
        ssh_exec(f"mkdir -p {remote_dir}")

        # Write settings.json locally, then upload
        local_settings = str(UPLOAD_DIR / f'{job_name}_settings.json')
        with open(local_settings, 'w') as f:
            json.dump(bc_settings, f, indent=2)
        scp_upload(local_settings, f'{remote_dir}/settings.json')

        # Upload target PDB if it's a remote path reference
        if target_pdb and os.path.exists(str(UPLOAD_DIR / os.path.basename(target_pdb))):
            scp_upload(str(UPLOAD_DIR / os.path.basename(target_pdb)), f'{remote_dir}/target.pdb')
        elif target_pdb:
            # It's already a remote path — copy on server
            ssh_exec(f"cp {target_pdb} {remote_dir}/target.pdb")

        # Write and upload SLURM script
        local_slurm = str(UPLOAD_DIR / f'{job_name}.slurm')
        with open(local_slurm, 'wb') as f:
            f.write(slurm_script.encode('utf-8').replace(b'\r\n', b'\n'))
        scp_upload(local_slurm, f'{remote_dir}/run.slurm')

        # Submit job
        stdout, stderr, code = ssh_exec(f"cd {remote_dir} && sbatch run.slurm")
        slurm_id = ''
        if 'Submitted batch job' in stdout:
            slurm_id = stdout.strip().split()[-1]

        job = add_job({
            'id': job_id,
            'name': job_name,
            'tool': 'BindCraft',
            'status': 'PENDING' if slurm_id else 'SUBMIT_ERROR',
            'slurm_id': slurm_id,
            'remote_dir': remote_dir,
            'submitted_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'params': {
                'chain': target_chain,
                'hotspots': hotspots,
                'intensity': intensity,
                'num_designs': num_designs,
            }
        })

        return jsonify({
            'status': 'ok',
            'job': job,
            'message': f'Submitted SLURM job {slurm_id}' if slurm_id else 'Submit error: ' + stderr
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ─── Placeholder submit endpoints for future tools ────────────

@app.route('/api/submit/pepmlm', methods=['POST'])
def api_submit_pepmlm():
    return jsonify({'status': 'error', 'message': 'PepMLM integration coming soon. Program must be installed on the cluster first.'}), 501

@app.route('/api/submit/rfantibody', methods=['POST'])
def api_submit_rfantibody():
    return jsonify({'status': 'error', 'message': 'RFAntibody integration coming soon. Program must be installed on the cluster first.'}), 501

@app.route('/api/submit/proteinmpnn', methods=['POST'])
def api_submit_proteinmpnn():
    return jsonify({'status': 'error', 'message': 'ProteinMPNN integration coming soon. Program must be installed on the cluster first.'}), 501

# ─── First-Run Setup ──────────────────────────────────────────

def first_run_setup():
    """Interactive setup for new users. Runs once when no settings exist."""
    settings = get_settings()

    # Check if required fields are configured
    if settings.get('host') and settings.get('username'):
        return  # Already configured

    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │         First-Time Setup                    │")
    print("  │  Configure your cluster connection below.   │")
    print("  │  Press Enter to accept defaults in [brackets]. │")
    print("  └─────────────────────────────────────────────┘")
    print()

    host = input(f"  Cluster hostname []: ").strip()
    username = input(f"  SSH username []: ").strip()

    default_key = str(Path.home() / '.ssh' / 'id_ed25519')
    key_path = input(f"  SSH key path [{default_key}]: ").strip() or default_key

    default_remote = f'/home/{username}/binder_design' if username else ''
    remote_base = input(f"  Remote working directory [{default_remote}]: ").strip() or default_remote

    # Save settings
    settings.update({
        'host': host,
        'username': username,
        'key_path': key_path,
        'remote_base': remote_base,
    })
    save_settings(settings)

    print()
    print(f"  ✓ Settings saved to {SETTINGS_FILE}")
    print("  You can change these anytime in Server Settings.")
    print()


# ─── Main ─────────────────────────────────────────────────────

if __name__ == '__main__':
    is_frozen = getattr(sys, 'frozen', False)
    port = 5000

    print("=" * 60)
    print("  Protein Design Studio V3 — Binder Design Edition")
    print(f"  Open http://localhost:{port} in your browser")
    print("=" * 60)

    # First-run setup for new users
    first_run_setup()

    # Auto-open browser when running as packaged app
    if is_frozen:
        threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{port}')).start()

    app.run(host='0.0.0.0', port=port, debug=not is_frozen)
