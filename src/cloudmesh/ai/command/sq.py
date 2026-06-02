import click
import asyncio
import sys
import re
from typing import Optional
from tabulate import tabulate
from cloudmesh.ai.slurm_new.squeue import SQueue

async def _status(sq: SQueue):
    """Show cluster status and free nodes."""
    print("Fetching cluster status...")
    nodes = await sq.get_cluster_status()
    if not nodes:
        print("No node information available.")
        return

    print(f"{'Node':<15} {'State':<12} {'CPUs':<6} {'Mem (MB)':<10}")
    print("-" * 45)
    for n in nodes:
        print(f"{n.node_name:<15} {n.state:<12} {n.cpus:<6} {n.memory:<10}")

async def _jobs(sq: SQueue, user: Optional[str] = None):
    """List current Slurm jobs."""
    print(f"Fetching jobs{' for user ' + user if user else ' for current user'}...")
    jobs = await sq.get_jobs(user=user)
    if not jobs:
        print("No active jobs found.")
        return

    print(f"{'JobID':<12} {'Name':<20} {'State':<12} {'Partition':<12} {'Nodes':<15} {'GPUs':<8} {'GPU Type':<12} {'Start':<15} {'TTL':<10} {'Res':<10}")
    print("-" * 120)
    
    for j in jobs:
        # Fetch detailed info concurrently for each job
        gpu_count, gpu_type, res = await asyncio.gather(
            j.get_gpus(),
            j.get_gpu_type(),
            j.get_reservation()
        )
        
        gpu_info = f"{gpu_count}x" if gpu_count else "0x"
        res_val = res if res else "N/A"
        
        print(f"{j.job_id:<12} {j.name[:19]:<20} {j.state:<12} {j.partition:<12} {j.node_list[:14]:<15} {gpu_info:<8} {gpu_type:<12} {j.start_time[:14]:<15} {j.ttl:<10} {res_val:<10}")

async def _job_info(sq: SQueue, job_id: str):
    """Get detailed information for a specific job."""
    jobs = await sq.get_jobs()
    job = next((j for j in jobs if j.job_id == job_id), None)
    
    if not job:
        print(f"Job {job_id} not found.")
        return

    print(f"Job {job_id} Details:")
    print(f"  Name:      {job.name}")
    print(f"  State:     {job.state}")
    print(f"  User:      {job.user}")
    print(f"  Partition: {job.partition}")
    print(f"  Nodes:     {job.nodes}")
    print(f"  Start:     {job.start_time}")
    print(f"  TTL:       {job.ttl}")
    
    gpus = await job.get_gpus()
    print(f"  GPUs:      {gpus}")
    
    work_dir = await job.get_work_dir()
    print(f"  WorkDir:   {work_dir}")

    eff = await job.get_efficiency()
    if eff:
        print(f"  Efficiency: CPU {eff.get('cpu_efficiency', 0):.2f}%, Mem {eff.get('mem_efficiency', 0):.2f}%")
    else:
        print("  Efficiency: N/A")

async def _job_logs(sq: SQueue, job_id: str):
    """Print stdout logs for a job."""
    logs = await sq.get_out(job_id)
    if logs:
        print(f"--- Logs for Job {job_id} ---")
        print(logs)
    else:
        print(f"No logs found for job {job_id}.")

async def _free_nodes(sq: SQueue, gpu_type: Optional[str] = None):
    """List free nodes, optionally filtered by GPU type."""
    print(f"Searching for free nodes{' with GPU ' + gpu_type if gpu_type else ''}...")
    groups = await sq.find_free_nodes(gpu_type=gpu_type)
    if not groups:
        print("No free nodes found matching the criteria.")
        return

    # ANSI Color codes
    GREEN = "\033[38;5;22m"
    RED = "\033[91m"
    RESET = "\033[0m"

    # Scaling factors based on GPU relative performance: (display_string, sort_value)
    SCALING_FACTORS = {
        "rtx_2080": ("1x", 1),
        "v100": ("1.5x-2x", 1.75),
        "rtx_3090": ("2.5x-3x", 2.75),
        "a40": ("3x-4x", 3.5),
        "a6000": ("4x-5x", 4.5),
        "rtx_pro_6000": ("4x-5x", 4.5),
        "a100": ("8x-12x", 10),
        "h200": ("20x+", 20),
    }

    headers = ["", "GPU Type", "Memory", "Scale", "Free N", "Free G", "Used N", "Total N", "Used G", "Total G", "Free Nodes"]
    
    # Sort groups by scaling factor (fastest first)
    def get_sort_val(group):
        gpu_type = group['gpu_type'].lower()
        return SCALING_FACTORS.get(gpu_type, ( "N/A", -1 ))[1]

    groups.sort(key=get_sort_val, reverse=True)
    
    rows = []
    
    # Special row for udc-an26-1 at the top
    try:
        special_node = "udc-an26-1"
        # Get total capacity and state using scontrol for higher accuracy
        special_cmd = f"ssh {sq.host} 'scontrol show node {special_node}'"
        special_res = await sq._run_command_async(special_cmd)
        if special_res.returncode == 0 and special_res.stdout.strip():
            output = special_res.stdout
            # Extract State
            state_match = re.search(r"State=(\S+)", output)
            state = state_match.group(1) if state_match else "Unknown"
            
            # Extract Gres
            gres_match = re.search(r"Gres=(.*)", output)
            gres = gres_match.group(1).split()[0] if gres_match else "Unknown"
            
            # Extract Features
            feat_match = re.search(r"AvailableFeatures=(\S+)", output)
            features = feat_match.group(1) if feat_match else ""
            
            if gres != "Unknown":
                
                found_gpu_type = "Unknown"
                gpu_mem = "Unknown"
                gpu_count = 1
                if "gpu" in gres.lower():
                    match = re.search(r"gpu:([^:]+):(\d+)", gres.lower())
                    if match:
                        found_gpu_type = match.group(1).split(".")[0]
                        gpu_count = int(match.group(2))
                    
                    # Override total GPUs for udc-an26-1 as it is known to be 8
                    if special_node == "udc-an26-1":
                        gpu_count = 8

                    combined = f"{gres} {features}".lower()
                    if "a100_80gb" in combined or "a100-80" in combined: gpu_mem = "80GB"
                    elif "a100_40gb" in combined or "a100-40" in combined: gpu_mem = "40GB"
                    elif "v100_32gb" in combined: gpu_mem = "32GB"
                    elif "v100_16gb" in combined: gpu_mem = "16GB"
                    elif "h200" in combined: gpu_mem = "141GB"
                    elif "a40" in gres.lower() or "a6000" in gres.lower(): gpu_mem = "48GB"
                
                if found_gpu_type == "rtx3090": found_gpu_type = "rtx_3090"
                if found_gpu_type == "rtx2080": found_gpu_type = "rtx_2080"
                if found_gpu_type == "1g": found_gpu_type = "rtx_pro_6000"

                # Check actual usage via SQueue.get_jobs_on_node to handle reservations correctly
                allocated_gpus = 0
                jobs_on_node = await sq.get_jobs_on_node(special_node)
                for job in jobs_on_node:
                    job_gpu_count = await job.get_gpus()
                    if job_gpu_count:
                        allocated_gpus += job_gpu_count
                
                free_g = max(0, gpu_count - allocated_gpus)
                is_free = free_g > 0
                free_n = 1 if is_free else 0

                gpu_type_colored = f"{GREEN}{found_gpu_type}{RESET}" if is_free else f"{RED}{found_gpu_type}{RESET}"
                free_n_colored = f"{GREEN}1{RESET}" if is_free else f"{RED}0{RESET}"
                free_g_colored = f"{GREEN}{free_g}{RESET}" if is_free else f"{RED}0{RESET}"
                
                gpu_type_key = found_gpu_type.lower()
                scale = SCALING_FACTORS.get(gpu_type_key, ("N/A", -1))[0]
                status_indicator = f"{GREEN}●{RESET}" if is_free else f"{RED}✘{RESET}"

                rows.append([
                    status_indicator,
                    gpu_type_colored,
                    gpu_mem,
                    scale,
                    free_n_colored,
                    free_g_colored,
                    0 if is_free else 1,
                    1,
                    allocated_gpus,
                    gpu_count,
                    special_node
                ])
    except Exception:
        pass

    for g in groups:
        free_n = g['free_nodes']
        free_g = g['free_gpus']
        
        # GPU Type Color: Green font if free nodes > 0
        gpu_type_val = g['gpu_type']
        gpu_type_colored = f"{GREEN}{gpu_type_val}{RESET}" if free_n > 0 else f"{RED}{gpu_type_val}{RESET}"
        
        # Free N Color
        free_n_colored = f"{GREEN}{free_n}{RESET}" if free_n > 0 else f"{RED}{free_n}{RESET}"
        
        # Free G Color
        free_g_colored = f"{GREEN}{free_g}{RESET}" if free_g > 0 else f"{RED}{free_g}{RESET}"

        # Lookup scaling factor display string
        gpu_type_key = g['gpu_type'].lower()
        scale = SCALING_FACTORS.get(gpu_type_key, ("N/A", -1))[0]

        # Status indicator: Green circle if free GPUs > 0, Red X if 0
        status_indicator = f"{GREEN}●{RESET}" if free_g > 0 else f"{RED}✘{RESET}"

        rows.append([
            status_indicator,
            gpu_type_colored,
            g['gpu_mem'],
            scale,
            free_n_colored,
            free_g_colored,
            g['used_nodes'],
            g['total_nodes'],
            g['used_gpus'],
            g['total_gpus'],
            g['nodes']
        ])

    print("\n" + tabulate(rows, headers=headers, tablefmt="rounded_grid"))
    
    print("\nLegend:")
    print("  Used N / Free N / Total N:  Node counts")
    print("  Used G / Free G / Total G:  GPU counts")

def run_command(cmd_name: str, args: list, host: str = "uva"):
    """Synchronous wrapper to run async Slurm commands."""
    sq = SQueue(host=host)
    
    try:
        if cmd_name == "status":
            asyncio.run(_status(sq))
        elif cmd_name == "jobs":
            user = args[0] if args else None
            asyncio.run(_jobs(sq, user=user))
        elif cmd_name == "job-info":
            if not args:
                print("Error: Job ID required.")
                return
            asyncio.run(_job_info(sq, args[0]))
        elif cmd_name == "job-logs":
            if not args:
                print("Error: Job ID required.")
                return
            asyncio.run(_job_logs(sq, args[0]))
        elif cmd_name == "free-nodes":
            gpu_type = args[0] if args else None
            asyncio.run(_free_nodes(sq, gpu_type=gpu_type))
        else:
            print(f"Unknown command: {cmd_name}")
    except Exception as e:
        print(f"Command failed: {e}")

def main():
    """Main entry point for the cmc-slurm command."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cloudmesh AI Slurm CLI")
    parser.add_argument("--host", default="uva", help="Slurm host (default: uva)")
    
    subparsers = parser.add_subparsers(dest="command", help="Slurm commands")
    
    # status
    subparsers.add_parser("status", help="Show cluster status")
    
    # jobs
    jobs_parser = subparsers.add_parser("jobs", help="List current jobs")
    jobs_parser.add_argument("user", nargs="?", help="Filter by user")
    
    # job-info
    info_parser = subparsers.add_parser("job-info", help="Get detailed job info")
    info_parser.add_argument("job_id", help="Slurm Job ID")
    
    # job-logs
    logs_parser = subparsers.add_parser("job-logs", help="Print job logs")
    logs_parser.add_argument("job_id", help="Slurm Job ID")
    
    # free-nodes
    free_parser = subparsers.add_parser("free-nodes", help="List free nodes")
    free_parser.add_argument("gpu_type", nargs="?", help="Filter by GPU type (e.g. a100)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    # Map argparse command to run_command names
    cmd_map = {
        "status": "status",
        "jobs": "jobs",
        "job-info": "job-info",
        "job-logs": "job-logs",
        "free-nodes": "free-nodes"
    }
    
    cmd_name = cmd_map.get(args.command)
    # Extract positional args for the command
    cmd_args = []
    if args.command == "jobs":
        cmd_args.append(args.user)
    elif args.command in ["job-info", "job-logs"]:
        cmd_args.append(args.job_id)
    elif args.command == "free-nodes":
        cmd_args.append(args.gpu_type)
        
    run_command(cmd_name, cmd_args, host=args.host)



@click.group()
def sq_group():
    """Slurm cluster and job management"""
    pass

@sq_group.command(name="status")
def status():
    """Show cluster status and free nodes."""
    run_command("status", [])

@sq_group.command(name="jobs")
@click.argument("user", required=False)
def jobs(user):
    """List current Slurm jobs."""
    run_command("jobs", [user] if user else [])

@sq_group.command(name="job-info")
@click.argument("job_id")
def job_info(job_id):
    """Get detailed information for a specific job."""
    run_command("job-info", [job_id])

@sq_group.command(name="job-logs")
@click.argument("job_id")
def job_logs(job_id):
    """Print stdout logs for a job."""
    run_command("job-logs", [job_id])

@sq_group.command(name="free-nodes")
@click.argument("gpu_type", required=False)
def free_nodes(gpu_type):
    """List free nodes, optionally filtered by GPU type."""
    run_command("free-nodes", [gpu_type] if gpu_type else [])

def register(cli):
    """Register slurm commands with the CMC CLI framework."""
    cli.add_command(sq_group, name="sq")
