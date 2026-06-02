import pytest
from cloudmesh.ai.slurm_new.models import SlurmJobModel, SlurmNodeModel

def test_slurm_job_model():
    job_data = {
        "job_id": "12345",
        "name": "test_job",
        "user": "user1",
        "state": "RUNNING",
        "partition": "gpu",
        "nodes": 1,
        "node_list": "node01",
        "start_time": "2023-10-27T10:00:00",
        "time_limit": "01:00:00",
        "time_used": "00:05:00",
        "gres": "gpu:1",
        "cpus": "1",
        "memory": "1000M",
        "work_dir": "/tmp"
    }
    job = SlurmJobModel(**job_data)
    assert job.job_id == "12345"
    assert job.name == "test_job"
    assert job.state == "RUNNING"

def test_slurm_node_model():
    node_data = {
        "nodename": "node01",
        "state": "idle",
        "cpus": 40,
        "memory": 128000,
        "gres": "gpu:a100:4",
        "gpu_type": "a100",
        "gpu_count": 4
    }
    node = SlurmNodeModel(**node_data)
    assert node.node_name == "node01"
    assert node.state == "idle"
    assert node.cpus == 40
    assert node.gpu_count == 4
