# In-memory job store for generation requests.
# Tracks status and result path so the frontend can poll and download.

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# --- Job status enum: used in API responses ---
class JobStatus(str, Enum):
    PENDING = "pending"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    BUILDING_PPT = "building_ppt"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Single job record: id, status, optional message, path to result file ---
@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.PENDING
    message: str = ""
    result_path: Optional[str] = None
    error: Optional[str] = None


# --- Global in-memory store: map job_id -> Job (replace with DB later) ---
_jobs: dict[str, Job] = {}


def create_job() -> Job:
    """Create a new job with a unique id and PENDING status."""
    job_id = str(uuid.uuid4())
    job = Job(id=job_id)
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    """Return the job for the given id, or None if not found."""
    return _jobs.get(job_id)


def update_job(job_id: str, status: JobStatus, message: str = "", result_path: Optional[str] = None, error: Optional[str] = None) -> None:
    """Update an existing job's status and optional result path or error."""
    job = _jobs.get(job_id)
    if not job:
        return
    job.status = status
    job.message = message
    if result_path is not None:
        job.result_path = result_path
    if error is not None:
        job.error = error
