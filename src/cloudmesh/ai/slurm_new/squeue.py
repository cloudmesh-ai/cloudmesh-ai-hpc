import subprocess
import json
import asyncio
import re
from typing import List, Optional
from cloudmesh.ai.slurm_new.job import SlurmJob
from cloudmesh.ai.slurm_new.models import SlurmJobModel


class SQueue:
    """Wrapper for Slurm squeue to provide consistent JSON-like output."""

    def __init__(self, host="uva"):
        self.host = host

    async def _run_command_async(
        self, cmd: str, timeout: int = 30
    ) -> subprocess.CompletedProcess:
        """Helper to run a shell command asynchronously."""
        return await asyncio.to_thread(
            subprocess.run,
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    async def get_jobs(self, user: Optional[str] = None) -> List[SlurmJob]:
        """Retrieve running jobs for a user, returning a list of SlurmJob objects."""
        jobs_data = []
        try:
            text_jobs = await self._get_jobs_text(user=user)
            if text_jobs:
                jobs_data = text_jobs
        except Exception:
            pass

        if not jobs_data:
            try:
                user_flag = f"--user {user}" if user else "--me"
                cmd = f"ssh {self.host} 'squeue {user_flag} --json'"
                result = await self._run_command_async(cmd, timeout=10)
                if result and result.returncode == 0:
                    data = json.loads(result.stdout)
                    jobs_list = data.get("jobs", [])
                    for job in jobs_list:
                        resources = job.get("job_resources", {})
                        nodes_data = resources.get("nodes", {})
                        allocation = nodes_data.get("allocation", [])
                        job_copy = job.copy()
                        job_copy["nodes"] = allocation
                        jobs_data.append(job_copy)
            except Exception:
                pass

        return [SlurmJob(self, job) for job in jobs_data]

    async def get_jobs_on_node(self, node: str) -> List[SlurmJob]:
        """Retrieve all jobs running on a specific node."""
        jobs_data = []
        try:
            fmt = "%i|%P|%j|%u|%t|%M|%D|%R|%S|%l|%b|%C|%m"
            cmd = f"ssh {self.host} 'squeue --noheader -w {node} -o \"{fmt}\"'"
            result = await self._run_command_async(cmd)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) < 5:
                        continue

                    jobs_data.append(
                        {
                            "job_id": parts[0],
                            "partition": parts[1] if len(parts) > 1 else "Unknown",
                            "name": parts[2] if len(parts) > 2 else "Unknown",
                            "user": parts[3] if len(parts) > 3 else "Unknown",
                            "state": parts[4] if len(parts) > 4 else "Unknown",
                            "time_used": parts[5] if len(parts) > 5 else "Unknown",
                            "nodes": [
                                {"name": parts[7] if len(parts) > 7 else "Unknown"}
                            ],
                            "node_list": parts[7] if len(parts) > 7 else "Unknown",
                            "start_time": parts[8] if len(parts) > 8 else "Unknown",
                            "time_limit": parts[9] if len(parts) > 9 else "Unknown",
                            "gres": parts[10] if len(parts) > 10 else "Unknown",
                            "cpus": parts[11] if len(parts) > 11 else "Unknown",
                            "memory": parts[12] if len(parts) > 12 else "Unknown",
                        }
                    )
        except Exception:
            pass
        return [SlurmJob(self, job) for job in jobs_data]

    async def _get_jobs_text(self, user: Optional[str] = None) -> List[dict]:
        """Fastest method: Use the user-recommended squeue format for high performance."""
        try:
            fmt = "%i|%P|%j|%u|%t|%M|%D|%R|%S|%l|%b|%C|%m"
            user_flag = f"-u {user}" if user else "-u $USER"
            cmd = f"ssh {self.host} 'squeue --noheader {user_flag} -o \"{fmt}\"'"

            result = await self._run_command_async(cmd)
            if result.returncode != 0:
                return []

            jobs = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) < 5:
                    continue

                jobs.append(
                    {
                        "job_id": parts[0],
                        "partition": parts[1] if len(parts) > 1 else "Unknown",
                        "name": parts[2] if len(parts) > 2 else "Unknown",
                        "user": parts[3] if len(parts) > 3 else "Unknown",
                        "state": parts[4] if len(parts) > 4 else "Unknown",
                        "time_used": parts[5] if len(parts) > 5 else "Unknown",
                        "nodes": [{"name": parts[7] if len(parts) > 7 else "Unknown"}],
                        "node_list": parts[7] if len(parts) > 7 else "Unknown",
                        "start_time": parts[8] if len(parts) > 8 else "Unknown",
                        "time_limit": parts[9] if len(parts) > 9 else "Unknown",
                        "gres": parts[10] if len(parts) > 10 else "Unknown",
                        "cpus": parts[11] if len(parts) > 11 else "Unknown",
                        "memory": parts[12] if len(parts) > 12 else "Unknown",
                    }
                )
            return jobs
        except Exception:
            return []

    async def cancel(self, job_id: str) -> bool:
        """Cancel a Slurm job by its ID."""
        try:
            cmd = f"ssh {self.host} 'scancel {job_id}'"
            result = await self._run_command_async(cmd)
            return result.returncode == 0
        except Exception:
            return False

    async def requeue(self, job_id: str) -> bool:
        """Requeue a Slurm job."""
        try:
            cmd = f"ssh {self.host} 'scontrol requeue {job_id}'"
            result = await self._run_command_async(cmd)
            return result.returncode == 0
        except Exception:
            return False

    async def hold(self, job_id: str) -> bool:
        """Hold a Slurm job."""
        try:
            cmd = f"ssh {self.host} 'scontrol hold {job_id}'"
            result = await self._run_command_async(cmd)
            return result.returncode == 0
        except Exception:
            return False

    async def release(self, job_id: str) -> bool:
        """Release a held Slurm job."""
        try:
            cmd = f"ssh {self.host} 'scontrol release {job_id}'"
            result = await self._run_command_async(cmd)
            return result.returncode == 0
        except Exception:
            return False

    async def get_cluster_status(self) -> List[SlurmNodeModel]:
        """Retrieve status of all nodes in the cluster using sinfo."""
        try:
            # -N: Node-centric, -l: detailed
            cmd = f"ssh {self.host} 'sinfo -N -l'"
            result = await self._run_command_async(cmd)
            if result.returncode != 0:
                return []

            nodes = []
            lines = result.stdout.splitlines()
            if not lines:
                return []

            # Skip header
            for line in lines[1:]:
                parts = line.split()
                if len(parts) < 4:
                    continue

                # Standard sinfo -N -l columns:
                # NODELIST, PARTITION, STATE, NODES, CPU, MEM, ...
                nodes.append(
                    {
                        "nodename": parts[0],
                        "state": parts[2],
                        "cpus": int(parts[4]) if parts[4].isdigit() else 0,
                        "memory": int(parts[5]) if parts[5].isdigit() else 0,
                    }
                )

            from cloudmesh.ai.slurm_new.models import SlurmNodeModel

            return [SlurmNodeModel(**n) for n in nodes]
        except Exception:
            return []

    async def find_free_nodes(self, gpu_type: Optional[str] = None) -> List[dict]:
        """Search for idle nodes and group them by full GRES (including memory)."""
        # Mapping of GRES patterns to known memory capacities for this cluster
        # This avoids needing to run nvidia-smi on individual nodes
        # Mapping of GRES patterns to known memory capacities.
        # We use a list of tuples to allow for priority matching (most specific first).
        # Mapping of GRES patterns to known memory capacities.
        # If GRES strings are simple (e.g. 'gpu:a100:8'), we use these patterns.
        # To distinguish A100 40GB vs 80GB, they MUST have different GRES strings.
        GPU_MEMORY_PATTERNS = [
            ("h200", "141GB"),
            ("a100.*80gb", "80GB"),
            ("a100.*40gb", "40GB"),
            ("a100_80", "80GB"),
            ("a100_40", "40GB"),
            ("v100.*32gb", "32GB"),
            ("v100.*16gb", "16GB"),
            ("v100_32", "32GB"),
            ("v100_16", "16GB"),
            ("a40", "48GB"),
            ("a6000", "48GB"),
            ("rtx_2080", "16GB"),
            ("rtx_3090", "24GB"),
            ("rtx3090", "24GB"),
            ("rtxpro6000", "48GB"),
            # Fallbacks for simple GRES strings
            ("a100", "80GB"),
            ("v100", "16GB"),
        ]

        try:
            # 1. Get total counts for every single node's GRES and Features
            # We must group by both because different memory variants often share the same GRES
            total_cmd = f"ssh {self.host} 'sinfo -N -h -o \"%G|%f\"'"
            total_res = await self._run_command_async(total_cmd)
            total_counts = {}
            if total_res.returncode == 0:
                for line in total_res.stdout.splitlines():
                    parts = line.split("|")
                    if len(parts) < 2:
                        continue
                    gres, features = parts[0].strip(), parts[1].strip()
                    if gres and "gpu" in gres.lower():
                        key = (gres, features)
                        total_counts[key] = total_counts.get(key, 0) + 1

            # 2. Process ALL GPU groups found in the cluster
            # We first resolve the memory for every group to use it as a merging key
            resolved_groups = {}  # key: (gpu_type, gpu_mem, gpu_count), value: data

            # Get all idle nodes once for efficient lookup
            idle_cmd = f"ssh {self.host} 'sinfo -t idle -h -o \"%G|%f|%N\"'"
            idle_res = await self._run_command_async(idle_cmd)
            idle_map = {}
            if idle_res.returncode == 0:
                for line in idle_res.stdout.splitlines():
                    p = line.strip().split("|")
                    if len(p) >= 3:
                        idle_map[(p[0].strip(), p[1].strip())] = p[2]

            for group_key, total_nodes in total_counts.items():
                gres, features = group_key

                found_gpu_type = "Unknown"
                gpu_mem = "Unknown"
                gpu_count = 0

                if "gpu" in gres.lower():
                    mem_match = re.search(r"(\d+[gm]b)", gres.lower())
                    if mem_match:
                        gpu_mem = mem_match.group(1)

                    gres_stripped = gres.lower()
                    if mem_match:
                        gres_stripped = gres_stripped.replace(
                            mem_match.group(0), ""
                        ).replace("::", ":")

                    match_type_count = re.search(r"gpu:([^:]+):(\d+)", gres_stripped)
                    if match_type_count:
                        raw_type = match_type_count.group(1)
                        # Only split on dot (usually separates type from memory in GRES)
                        # Do NOT split on underscore as it's part of the model name (e.g. rtx_3090)
                        type_parts = raw_type.split(".")
                        found_gpu_type = type_parts[0]
                        gpu_count = int(match_type_count.group(2))
                    else:
                        match_count = re.search(r"gpu:(\d+)", gres_stripped)
                        if match_count:
                            gpu_count = int(match_count.group(1))
                        else:
                            p_split = gres_stripped.split(":")
                            if len(p_split) >= 3:
                                raw_type = p_split[1]
                                type_parts = raw_type.split(".")
                                found_gpu_type = type_parts[0]
                                try:
                                    gpu_count = int(p_split[-1])
                                except ValueError:
                                    gpu_count = 0
                    
                    # Normalize type
                    if found_gpu_type == "rtx3090": found_gpu_type = "rtx_3090"
                    if found_gpu_type == "rtx2080": found_gpu_type = "rtx_2080"
                    if found_gpu_type == "1g": found_gpu_type = "rtx_pro_6000"
                    # Ensure we don't end up with just "rtx"
                    if found_gpu_type == "rtx":
                        # Try to find a number in the GRES to distinguish RTX models
                        num_match = re.search(r"(\d{4})", gres)
                        if num_match:
                            found_gpu_type = f"rtx_{num_match.group(1)}"
                        else:
                            found_gpu_type = "rtx_unknown"

                    # Force correct memory for known types if resolution failed
                    if found_gpu_type == "rtx_pro_6000" and gpu_mem not in ["48GB", "48gb"]:
                        gpu_mem = "48GB"

                if gpu_mem == "Unknown":
                    combined_info = f"{gres} {features}".lower()
                    
                    # 1. High-priority explicit feature tags
                    # We check for these first as they are the most definitive
                    if "a100_40gb" in combined_info or "a100-40" in combined_info:
                        gpu_mem = "40GB"
                    elif "a100_80gb" in combined_info or "a100-80" in combined_info:
                        gpu_mem = "80GB"
                    elif "v100_16gb" in combined_info or "v100-16" in combined_info:
                        gpu_mem = "16GB"
                    elif "v100_32gb" in combined_info or "v100-32" in combined_info:
                        gpu_mem = "32GB"
                    elif "h200" in combined_info:
                        gpu_mem = "141GB"
                    else:
                        # 2. Standard pattern matching
                        for pattern, mem in GPU_MEMORY_PATTERNS:
                            if re.search(pattern, combined_info):
                                gpu_mem = mem
                                break

                if found_gpu_type == "Unknown" and gpu_count == 0:
                    continue
                if gpu_type and (
                    found_gpu_type == "Unknown"
                    or found_gpu_type.lower() != gpu_type.lower()
                ):
                    continue

                # Resolve memory for ambiguous types via scontrol on controller
                if found_gpu_type.lower() in ["a100", "v100"] and gpu_mem == "Unknown":
                    rep_cmd = (
                        f"ssh {self.host} 'sinfo -h -N -o \"%N\" -C {features}' | head -n 1"
                        if features
                        else f"ssh {self.host} 'sinfo -h -N -o \"%N\"' | head -n 1"
                    )
                    rep_res = await self._run_command_async(rep_cmd)
                    if rep_res.returncode == 0 and rep_res.stdout.strip():
                        rep_node = rep_res.stdout.strip().splitlines()[0]
                        scontrol_res = await self._run_command_async(
                            f"ssh {self.host} 'scontrol show node {rep_node}'"
                        )
                        if scontrol_res.returncode == 0:
                            m_match = re.search(
                                r"gpu:[^:]*:(40gb|80gb|16gb|32gb)",
                                scontrol_res.stdout.lower(),
                            )
                            if m_match:
                                gpu_mem = m_match.group(1).upper()

                # Use (Type, Mem, Count) as the key to merge different feature sets of the same hardware
                # To prevent A100 40GB and 80GB from merging when memory is "Unknown", 
                # we use features as a differentiator.
                if gpu_mem == "Unknown":
                    # Further split A100s if they have different feature tags
                    merge_key = (found_gpu_type, "Unknown", gpu_count, features)
                else:
                    merge_key = (found_gpu_type, gpu_mem, gpu_count)

                # Determine free nodes for this specific group
                node_list = idle_map.get(group_key, "")
                free_nodes = 0
                if node_list:
                    expand_res = await self._run_command_async(
                        f"ssh {self.host} 'scontrol show hostnames {node_list}'"
                    )
                    free_nodes = (
                        len(expand_res.stdout.splitlines())
                        if expand_res.returncode == 0
                        else 0
                    )

                if merge_key not in resolved_groups:
                    resolved_groups[merge_key] = {
                        "gpu_type": found_gpu_type,
                        "gpu_mem": gpu_mem,
                        "used_nodes": 0,
                        "free_nodes": 0,
                        "total_nodes": 0,
                        "used_gpus": 0,
                        "free_gpus": 0,
                        "total_gpus": 0,
                        "nodes": [],
                    }

                g = resolved_groups[merge_key]
                g["total_nodes"] += total_nodes
                g["free_nodes"] += free_nodes
                g["used_nodes"] += total_nodes - free_nodes
                if node_list:
                    g["nodes"].append(node_list)
                elif total_nodes > 0:
                    # If there are no free nodes, we still want to indicate that in the data
                    # though the final string will be empty, we keep the record.
                    pass

            groups = []
            for key, g in resolved_groups.items():
                # Handle both 3-tuple and 4-tuple keys
                gpu_count = key[2]
                g["total_gpus"] = g["total_nodes"] * gpu_count
                g["free_gpus"] = g["free_nodes"] * gpu_count
                g["used_gpus"] = g["used_nodes"] * gpu_count
                # Join the compressed node lists with commas
                g["nodes"] = ",".join(g["nodes"])
                groups.append(g)

            return groups
        except Exception:
            return []

    async def submit_job(
        self,
        script_content: str,
        job_name: str = "cloudmesh-job",
        partition: str = "gpu",
        gpus: int = 1,
        cpus: int = 1,
        memory: str = "16G",
        time_limit: str = "01:00:00",
    ) -> Optional[str]:
        """Submit a job to Slurm."""
        try:
            # Create the sbatch header
            header = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition={partition}
#SBATCH --gres=gpu:{gpus}
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={memory}
#SBATCH --time={time_limit}
"""
            full_script = header + script_content

            # We use a heredoc to write the script to a temporary file and then run sbatch
            # This avoids needing to scp the file separately
            escaped_script = full_script.replace("'", "'\\''")
            cmd = f"ssh {self.host} \"cat << 'EOF' > /tmp/cm_job.sh\n{full_script}\nEOF\nsbatch /tmp/cm_job.sh\""

            result = await self._run_command_async(cmd)
            if result.returncode == 0:
                # sbatch output typically is: Submitted batch job 123456
                match = re.search(r"Submitted batch job (\d+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    async def get_job_logs(self, job_id: str) -> Optional[dict]:
        """Retrieve the stdout and stderr log paths for a Slurm job."""
        try:
            cmd = f"ssh {self.host} 'scontrol show job {job_id}'"
            result = await self._run_command_async(cmd, timeout=10)
            if result.returncode != 0:
                return None

            output = result.stdout
            logs = {"stdout": None, "stderr": None}

            for line in output.splitlines():
                if "StdOut=" in line:
                    logs["stdout"] = line.split("StdOut=")[1].split()[0]
                if "StdErr=" in line:
                    logs["stderr"] = line.split("StdErr=")[1].split()[0]

            return logs
        except Exception:
            return None

    async def get_out(self, job_id: str) -> Optional[str]:
        """Retrieve the content of the stdout log for a Slurm job."""
        logs = await self.get_job_logs(job_id)
        if not logs or not logs.get("stdout"):
            return None
        try:
            path = logs["stdout"]
            cmd = f"ssh {self.host} 'cat {path}'"
            result = await self._run_command_async(cmd, timeout=30)
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    async def get_err(self, job_id: str) -> Optional[str]:
        """Retrieve the content of the stderr log for a Slurm job."""
        logs = await self.get_job_logs(job_id)
        if not logs or not logs.get("stderr"):
            return None
        try:
            path = logs["stderr"]
            cmd = f"ssh {self.host} 'cat {path}'"
            result = await self._run_command_async(cmd, timeout=30)
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None
