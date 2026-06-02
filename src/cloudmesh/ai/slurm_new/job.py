import re
import asyncio
from typing import Optional, List, AsyncGenerator
from cloudmesh.ai.slurm_new.utils import parse_slurm_duration, format_hhmm, format_start_time
from cloudmesh.ai.slurm_new.models import SlurmJobModel

class SlurmJob:
    """Represents a Slurm job and provides access to its metadata and logs."""

    def __init__(self, squeue, job_data):
        self.squeue = squeue
        # Validate data using Pydantic model
        self.model = SlurmJobModel(**job_data)
        self.data = job_data
        
        self.job_id = self.model.job_id
        self.name = self.model.name
        self.state = self.model.state
        self.nodes = self.model.nodes
        self.partition = self.model.partition
        self.user = self.model.user
        self.node_list = self.model.node_list
        self.cpus = self.model.cpus
        self.memory = self.model.memory

    async def get_output(self):
        """Retrieve the content of the stdout log."""
        return await self.squeue.get_out(self.job_id)

    async def get_error(self):
        """Retrieve the content of the stderr log."""
        return await self.squeue.get_err(self.job_id)

    @property
    def start_time(self):
        """Return the formatted start time."""
        return format_start_time(self.data.get("start_time"))

    @property
    def ttl(self):
        """Calculate and return the remaining time (TTL) in HH:MM format."""
        limit_raw = self.data.get("time_limit", "0")
        used_raw = self.data.get("time_used", "0")
        
        limit_sec = parse_slurm_duration(limit_raw)
        used_sec = parse_slurm_duration(used_raw)
        
        ttl_sec = max(0, limit_sec - used_sec)
        return format_hhmm(ttl_sec)

    async def get_gpus(self) -> int:
        """Retrieve the number of GPUs allocated to the job."""
        # 1. Check GRES field from squeue data first
        gres_raw = self.data.get("gres", "")
        if gres_raw and "gpu" in gres_raw.lower():
            match = re.search(r'gpu[:\w]*:(\d+)', gres_raw.lower())
            if match:
                return int(match.group(1))
        
        # 2. Fallback to scontrol via async SQueue
        try:
            cmd = f"ssh {self.squeue.host} 'scontrol show job {self.job_id} -o'"
            res = await self.squeue._run_command_async(cmd, timeout=5)
            if res.returncode == 0:
                output = res.stdout.lower()
                match = re.search(r'gpu[=\:](\d+)', output)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
            
        return 0

    async def get_gpu_type(self) -> str:
        """Retrieve the type of GPUs allocated to the job."""
        gres_raw = self.data.get("gres", "")
        if gres_raw and "gpu" in gres_raw.lower():
            match = re.search(r'gpu:([^:]+):', gres_raw.lower())
            if match:
                return match.group(1)
        
        try:
            cmd = f"ssh {self.squeue.host} 'scontrol show job {self.job_id} -o'"
            res = await self.squeue._run_command_async(cmd, timeout=5)
            if res.returncode == 0:
                output = res.stdout.lower()
                match = re.search(r'gres=gpu:([^:]+)', output)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return "N/A"

    async def get_reservation(self) -> str:
        """Retrieve the reservation the job is running under."""
        res_raw = self.data.get("reservation")
        if res_raw:
            return res_raw
            
        try:
            cmd = f"ssh {self.squeue.host} 'scontrol show job {self.job_id} -o'"
            res = await self.squeue._run_command_async(cmd, timeout=5)
            if res.returncode == 0:
                output = res.stdout.lower()
                match = re.search(r'reservation=([^\s]+)', output)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return "N/A"

    async def get_work_dir(self) -> str:
        """Retrieve the working directory of the job."""
        try:
            cmd = f"ssh {self.squeue.host} 'scontrol show job {self.job_id} -o'"
            res = await self.squeue._run_command_async(cmd, timeout=5)
            if res.returncode == 0:
                match = re.search(r'WorkDir=([^\s]+)', res.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return "Unknown"

    async def get_efficiency(self) -> Optional[dict]:
        """Retrieve CPU and Memory efficiency using seff."""
        try:
            cmd = f"ssh {self.squeue.host} 'seff {self.job_id}'"
            result = await self.squeue._run_command_async(cmd)
            if result.returncode == 0:
                metrics = {}
                cpu_match = re.search(r'CPU Efficiency: ([\d.]+)%', result.stdout)
                mem_match = re.search(r'Memory Efficiency: ([\d.]+)%', result.stdout)
                if cpu_match: metrics["cpu_efficiency"] = float(cpu_match.group(1))
                if mem_match: metrics["mem_efficiency"] = float(mem_match.group(1))
                return metrics if metrics else None
        except Exception:
            pass
        return None

    async def tail_logs(self, stream: str = "stdout") -> AsyncGenerator[str, None]:
        """Async generator that tails the Slurm log file in real-time."""
        logs = await self.squeue.get_job_logs(self.job_id)
        if not logs or not logs.get(stream):
            return

        path = logs[stream]
        cmd = f"ssh {self.squeue.host} 'tail -f {path}'"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode().strip()
        finally:
            process.terminate()
            await process.wait()

    def __repr__(self):
        # Note: gpus and ttl are now async or property, 
        # so we only show static info in repr for simplicity
        return f"SlurmJob(id={self.job_id}, name={self.name}, state={self.state}, partition={self.partition})"

    def to_dict(self):
        """Return job data as a dictionary for backward compatibility."""
        return self.data