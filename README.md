# Cloudmesh AI HPC

**Authors**: \* **Gregor von Laszewski** ([laszewski\@gmail.com](mailto:laszewski@gmail.com))

Cloudmesh AI HPC is a powerful CLI tool designed to simplify access and management of resources on High Performance Computing (HPC) clusters, with primary support for the University of Virginia (UVA) Rivanna cluster. It abstracts the complexity of Slurm job submission, Apptainer image management, and remote cluster interaction into a streamlined set of commands.

## Getting Started

### 1. Installation

**Recommended: Using pipx** For the best experience with CLI tools, use `pipx` to install `cloudmesh-ai-hpc` in an isolated environment.

``` bash
pipx install cloudmesh-ai-hpc
# Or from a local directory:
pipx install .
```

**Using pip**

``` bash
pip install cloudmesh-ai-hpc
# Or from a local directory:
pip install .
```

### 2. First Steps

Start by checking your current configuration and available HPC partitions:

``` bash
cmc hpc info
```

Set your default host and partition to avoid specifying them in every command:

``` bash
cmc hpc set-default --host uva --partition a100
```

------------------------------------------------------------------------

## Usage Guide

### Connectivity & Remote Access

#### VPN Management

Many HPC resources require a VPN. Cloudmesh AI HPC integrates VPN control directly:

``` bash
cmc hpc vpn on       # Connect to the HPC VPN
cmc hpc vpn status   # Check if VPN is active
cmc hpc vpn off      # Disconnect
```

#### Interactive Login

You can SSH into an interactive node. Use the `--ui` flag to open a sophisticated visual selector:

``` bash
# Interactive selection via Textual UI
cmc hpc login --ui
```

**The Interactive UI features**: \* **Real-time Monitoring**: The table automatically updates "Idle Nodes" and "GPU Usage" every 30 seconds. \* **Dynamic GRES Adjustment**: Use `+` and `-` keys to increase or decrease the requested GPU count directly in the table. \* **Resource Verification**: Before final login, the tool verifies actual resource availability and displays a confirmation banner with the exact command to be executed.

**Direct login to a specific partition**:

``` bash
cmc hpc login a100
```

#### Remote Execution & Editing

Run a command without entering a full shell, or edit a remote file using your preferred editor:

``` bash
# Run a one-off command
cmc hpc run "df -h /scratch/$USER"

# Edit a remote file (defaults to emacs)
cmc hpc edit my_script.py --editor vim
```

### Slurm Job Management

#### Job Submission Workflow

1.  **Generate a template**:

    ``` bash
    cmc hpc slurm template a100 > my_job.sh
    ```

2.  **Edit your script** and add your logic.

3.  **Submit the job**:

    ``` bash
    cmc hpc slurm submit my_job.sh
    ```

#### Advanced Submission

You can override or add Slurm parameters at submission time using the `key:val` format:

``` bash
cmc hpc slurm submit my_job.sh --sbatch "time:01:00:00,mem:16G"
```

#### Monitoring & Maintenance

``` bash
cmc hpc slurm list            # List all your active jobs
cmc hpc slurm status 123456   # Quick status of a specific job
cmc hpc slurm job-info 123456 # Detailed scontrol output
cmc hpc slurm wait 123456     # Block until job completes
cmc hpc slurm logs 123456     # Read output logs
cmc hpc slurm logs 123456 --tail # Tail output logs in real-time
cmc hpc slurm cancel 123456   # Cancel a job
```

#### Advanced Cluster Monitoring (`sq`)

The `sq` command provides a high-performance, color-coded view of cluster resources and job states:

``` bash
cmc hpc sq free-nodes             # Find available GPUs with performance scaling
cmc hpc sq free-nodes a100        # Find free A100 GPUs specifically
cmc hpc sq jobs                   # List current jobs with GPU types and TTL
cmc hpc sq jobs myuser            # List jobs for a specific user
cmc hpc sq job-info 123456        # Deep dive into job resources and efficiency
cmc hpc sq job-logs 123456        # Quickly retrieve job stdout
cmc hpc sq status                 # Overview of all cluster nodes
```

**`sq free-nodes` Features**: \* **Resource Grouping**: Automatically groups nodes by GPU type and memory (e.g., A100 40GB vs 80GB). \* **Performance Scaling**: Displays a relative scaling factor (e.g., H200 as 20x+, A100 as 8x-12x) to help choose the best hardware. \* **Real-time Status**: Uses ANSI colors (Green/Red) to instantly show which GPU groups have available capacity. \* **Priority Node Tracking**: Special high-accuracy tracking for critical nodes (e.g., `udc-an26-1`) to ignore reservations and show actual running usage.

#### Cluster Monitoring & Reporting

Get high-level insights into cluster health and usage:

``` bash
# Node information and cluster summary
cmc hpc sinfo --output summary

# Get the current job queue
cmc hpc squeue --search "node[01-10]"

# Detailed usage reports for users, accounts, or partitions
cmc hpc sreport --stat

# Check GPU usage for a specific node or reservation
cmc hpc slurm gpu-usage a100-node-01
```

### Image & Storage Management

#### Apptainer Images

Build container images directly on the HPC to ensure environment consistency:

``` bash
cmc hpc image build my_env.def
```

#### Storage Checks

Quickly check your disk usage or quota:

``` bash
cmc hpc storage info /home/user/data
cmc hpc slurm quota
```

### Jupyter Notebooks

Launch a Jupyter server on the cluster:

``` bash
cmc hpc jupyter --port 8888
```

*Note: This requires an active VPN connection and an SSH tunnel (the command output will provide the exact tunnel string).*

### System Info & Support

``` bash
cmc hpc config     # View hardware and queue specifications
cmc hpc tutorial   # Open HPC tutorials in browser
cmc hpc ticket     # Open support request form
```

------------------------------------------------------------------------

## Configuration & Customization

Cloudmesh AI HPC uses a two-tier configuration system: 1. **Base Config**: Packaged `partitions.yaml` containing standard cluster definitions. 2. **Local Overrides**: Located at `~/.cloudmesh/hpc.yaml`.

### Local Configuration Example

You can define your own default host, partition, and **aliases** for complex sbatch parameters.

Create `~/.cloudmesh/hpc.yaml`:

``` yaml
cloudmesh:
  ai:
    default:
      host: uva
      partition: a100
    # Aliases allow you to use a short name for a set of parameters
    aliases:
      heavy_gpu: "gres:gpu:a100:1,mem:80G,time:24:00:00"
      light_gpu: "gres:gpu:v100:1,mem:16G,time:02:00:00"
    # You can also add custom partitions or override existing ones
    partition:
      uva:
        my-custom-partition:
          partition: gpu
          account: my_account
          gres: gpu:a100:1
```

**Using an alias in a command**:

``` bash
cmc hpc slurm submit my_job.sh --sbatch "heavy_gpu"
```

------------------------------------------------------------------------

## Command Reference

| Command | Description | Key Options |
|:-----------------------|:-----------------------|:-----------------------|
| `info` | Show config, available hosts, and partitions | `[key]` |
| `config` | Show hardware and queue specifications |  |
| `login` | SSH into an interactive node | `--ui`, `--host`, `--sbatch` |
| `run` | Execute a one-off remote command | `"command"` |
| `slurm template` | Generate a `.sbatch` boilerplate | `[key]` |
| `slurm submit` | Upload and submit a Slurm job | `--key`, `--sbatch` |
| `slurm job-info` | Detailed job metadata | `<job_id>` |
| `slurm status` | Current job state (R, PD, etc.) | `<job_id>` |
| `slurm list` | List all active jobs for current user |  |
| `slurm wait` | Block until job finishes | `<job_id>`, `--interval` |
| `slurm logs` | Read or tail job output logs | `<job_id>`, `--tail` |
| `slurm quota` | Check disk quota |  |
| `slurm nodes` | Check node availability in partition | `--partition` |
| `sinfo` | Get node information and cluster summary | `--output summary`, `--search` |
| `squeue` | Get Slurm queue information | `--search`, `--output` |
| `sreport` | Get Slurm usage reports | `--start`, `--end`, `--stat` |
| `slurm gpu-usage` | Check GPU usage for node/reservation | `<target>` |
| `slurm search-jobs` | Find jobs by node regex | `<node_regex>` |
| `sq free-nodes` | High-perf GPU availability table | `[gpu_type]` |
| `sq jobs` | GPU-aware job listing | `[user]` |
| `sq job-info` | Detailed job efficiency & metadata | `<job_id>` |
| `sq job-logs` | Quick access to job stdout | `<job_id>` |
| `sq status` | Cluster-wide node status |  |
| `slurm cancel` | Terminate a Slurm job | `<job_id>` |
| `set-default` | Set default host/partition in config | `--host`, `--partition` |
| `image build` | Build Apptainer image from `.def` file | `<file>` |
| `storage info` | Get directory size on HPC | `<dir>` |
| `edit` | Edit remote file via SSH | `<file>`, `--editor` |
| `vpn on/off` | Toggle VPN connection |  |
| `vpn status` | Check VPN connectivity |  |
| `jupyter` | Setup Jupyter notebook on cluster | `--port` |
| `tutorial` | Open HPC tutorials in browser | `[keyword]` |
| `ticket` | Open support request form |  |

------------------------------------------------------------------------

## Debugging & Troubleshooting

### Using Debug Mode

Almost every command supports the `--debug` flag. When enabled, the tool prints the exact SSH/Shell commands it intends to execute without actually running them. This is invaluable for verifying the generated Slurm directives.

``` bash
cmc hpc slurm submit my_job.sh --debug
```

### Common Issues

- **Permission Denied (publickey)**: Ensure your SSH keys are added to the HPC cluster and your local `ssh-agent` is running.
- **VPN Connection Failed**: Check your network and ensure you have the necessary credentials for the VPN service.
- **Job Pending (PD)**: Use `cmc hpc slurm job-info <id>` to see why a job is pending (e.g., waiting for resources or priority).
- **Interactive UI not loading**: Ensure your terminal supports TUI applications (Textual).

------------------------------------------------------------------------

## Appendix: UVA Partition Table

| Key         | Partition | Account           | GRES / Constraint / Reservation     |
|:-----------------|:-----------------|:-----------------|:-----------------|
| `parallel`  | parallel  | bii_dsc_community | nodes: 2, ntask-per-node: 4         |
| `v100`      | bii-gpu   | bii_dsc_community | gpu:v100:1                          |
| `a100`      | gpu       | bii_dsc_community | gpu:a100:1                          |
| `a100-80gb` | gpu       | bii_dsc_community | gpu:a100:1, constraint: a100_80gb   |
| `a100-dgx`  | bii-gpu   | bii_dsc_community | gpu:a100:1, reservation: bi_fox_dgx |
| `k80`       | gpu       | bii_dsc_community | gpu:k80:1                           |
| `p100`      | gpu       | bii_dsc_community | gpu:p100:1                          |
| `a6000`     | gpu       | bii_dsc_community | gpu:a6000:1                         |
| `a100-pod`  | gpu       | bii_dsc_community | gpu:a100:1, constraint: gpupod      |
| `rtx2080`   | gpu       | bii_dsc_community | gpu:rtx2080:1                       |
| `rtx3090`   | gpu       | bii_dsc_community | gpu:rtx3090:1                       |