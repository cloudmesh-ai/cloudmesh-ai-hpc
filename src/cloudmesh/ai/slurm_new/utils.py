import re

def parse_slurm_duration(duration_str):
    """Parse Slurm duration string [days-]HH:MM:SS into seconds."""
    if not duration_str or duration_str in ["N/A", "Unknown", "UNLIMITED"]:
        return 0
    try:
        days = 0
        if "-" in duration_str:
            days_str, duration_str = duration_str.split("-", 1)
            days = int(days_str)

        parts = list(map(int, duration_str.split(":")))
        if len(parts) == 3:  # HH:MM:SS
            return days * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:  # MM:SS
            return days * 86400 + parts[0] * 60 + parts[1]
        return days * 86400
    except Exception:
        return 0

def format_hhmm(seconds):
    """Format seconds into HH:MM."""
    if seconds <= 0:
        return "00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}"

def format_start_time(time_str):
    """Extract HH:MM from Slurm start time YYYY-MM-DDTHH:MM:SS."""
    if not time_str or time_str in ["N/A", "Unknown"]:
        return "Unknown"
    if "T" in time_str:
        try:
            time_part = time_str.split("T")[1]
            return ":".join(time_part.split(":")[:2])
        except Exception:
            pass
    return time_str