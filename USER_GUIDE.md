# Protein Design Studio V3 — Getting Started Guide

## What is Protein Design Studio?

Protein Design Studio V3 is a web-based tool for designing protein binders using deep learning. It provides an interactive 3D viewer and submits design jobs to your compute cluster via SLURM.

**Available design tools:**
- **BindCraft** — de novo protein binder design
- **PepMLM** — peptide binder design via masked language modeling
- **RFAntibody** — nanobody/antibody design via RoseTTAFold
- **ProteinMPNN** — sequence optimization for binder complexes

---

## Setup

### Prerequisites

- **Python 3.8+** installed on your computer
- **SSH access** to the compute cluster
- An **SSH key** (if you don't have one, see [SSH Key Setup](#ssh-key-setup) below)

### Step 1 — Download the server

Download **`server.py`** from the GitHub repository (and optionally `start_server.bat` for Windows):

📁 **https://github.com/brassmonkey79/Protein-Studio-V3**

### Step 2 — Install dependencies

```
pip install flask paramiko scp
```

### Step 3 — Start the server

```
python server.py
```

### Step 4 — Open the app

Open **https://brassmonkey79.github.io/Protein-Studio-V3/** in your browser. The sidebar should show **● Connected**.

### Step 5 — Configure Server Settings

Click **Server Settings** in the sidebar and fill in each field (see [Server Settings Guide](#server-settings-guide) below). Click **💾 Save Settings**, then **🔌 Test Connection** to verify.

---

## Daily Use

1. Open a terminal and run `python server.py`
2. Open the website in your browser
3. When finished, press `Ctrl+C` to stop

> **Tip:** On Windows, double-click **`start_server.bat`** instead of typing commands.

---

## Server Settings Guide

When you first open Server Settings, all fields will be empty. Here's what to enter.

### SSH Connection

| Field | What to enter | How to find it |
|-------|---------------|----------------|
| **Server Host** | Hostname of your compute cluster | Same name you use for `ssh hostname` in your terminal |
| **Username** | Your login username on the cluster | |
| **SSH Private Key Path** | Full path to your SSH key on your local machine | Windows: `C:\Users\yourname\.ssh\id_rsa` — Mac: `/Users/yourname/.ssh/id_rsa` |
| **Remote Working Directory** | Folder on the cluster for design jobs | Example: `/home/yourname/binder_design` (created automatically) |

> **Important:** Use the full path for SSH keys. Do not use `~/.ssh/` — it won't work on Windows.

### SLURM Configuration

| Field | What to enter | How to find it |
|-------|---------------|----------------|
| **Partition** | SLURM partition name | SSH in and run: `sinfo -s` |
| **GPU Resource** | GPU resource string | SSH in and run: `sinfo -p gpu -o "%G"`. Common values: `gpu:1`, `gpu:a100:1` |

### Tool Paths

| Field | What to enter | How to find it |
|-------|---------------|----------------|
| **Conda Installation** | Base path of Miniforge/Conda on the cluster | SSH in and run: `which conda`. If it returns `/home/you/miniforge3/condabin/conda`, enter `/home/you/miniforge3` |
| **BindCraft Path** | Folder where BindCraft is installed | Example: `/home/yourname/BindCraft` |

**If Miniforge is not installed on the cluster:**
```bash
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh
```

**If BindCraft is not installed:** See https://github.com/martinpacesa/BindCraft

---

## Using the App

### Viewer controls

| Action | Mouse |
|--------|-------|
| Rotate | Left-click drag |
| Zoom | Scroll wheel |
| Pan | Right-click drag |
| Select residue | Click on structure |

### Viewer modes

| Button | Description |
|--------|-------------|
| **Ribbon** | Cartoon backbone |
| **Atom** | Ball-and-stick |
| **Surface** | Hydrophobicity surface (not clickable) |
| **Spheres** | Hydrophobicity spheres (clickable) |

**Colors:** 🟦 Teal = hydrophilic · ⬜ White = neutral · 🟧 Amber = hydrophobic

### Selecting hotspot residues

- **Click** a residue to select it (magenta highlight)
- **Click again** to deselect
- Selected residues auto-fill the **Hotspot Residues** field
- **Clear Selection** to reset

### Submitting a job

1. Upload your target PDB
2. Select hotspot residues
3. Configure parameters
4. Click **🚀 Submit Design Job**
5. Monitor in **Job Dashboard**

---

## SSH Key Setup

**Windows:**

1. Install OpenSSH (if `ssh-keygen` is not recognized). Open PowerShell **as Administrator**:
   ```
   Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
   ```
   Close and reopen PowerShell.

2. Generate your key:
   ```
   ssh-keygen
   ```

3. Copy to cluster:
   ```
   type $env:USERPROFILE\.ssh\id_rsa.pub | ssh your-username@your-hostname "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
   ```

**Mac/Linux:**
```
ssh-keygen
ssh-copy-id your-username@your-hostname
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Sidebar shows "Disconnected" | Make sure `python server.py` is running |
| "Connection error" | Check SSH key path and that `ssh your-hostname` works |
| "Missing required settings" | Fill in all fields in Server Settings |
| "invalid partition specified" | Enter correct partition (run `sinfo -s` on cluster) |
| Server won't start | Run `pip install flask paramiko scp` |
