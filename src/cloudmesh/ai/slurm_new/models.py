from pydantic import BaseModel, Field
from typing import Optional, List

class SlurmNodeModel(BaseModel):
    """Model for Slurm node information."""
    node_name: str = Field(..., alias="nodename")
    state: str
    cpus: int = 0
    memory: int = 0  # in MB
    gres: Optional[str] = None
    gpu_type: Optional[str] = None
    gpu_count: int = 0

    class Config:
        populate_by_name = True

class SlurmJobModel(BaseModel):
    """Model for Slurm job metadata."""
    job_id: str
    name: str
    user: str
    state: str
    partition: str
    nodes: Optional[List] = None
    node_list: str = "Unknown"
    start_time: str = "Unknown"
    time_limit: str = "Unknown"
    time_used: str = "Unknown"
    gres: Optional[str] = None
    gpu_count: int = 0
    gpu_type: Optional[str] = None
    reservation: Optional[str] = None
    cpus: Optional[str] = "Unknown"
    memory: Optional[str] = "Unknown"
    work_dir: Optional[str] = None

    class Config:
        populate_by_name = True