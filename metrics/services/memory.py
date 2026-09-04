import resource
from pathlib import Path

_CGROUP_CURRENT_PATHS = (
    Path("/sys/fs/cgroup/memory.current"),
    Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"),
)
_CGROUP_PEAK_PATHS = (
    Path("/sys/fs/cgroup/memory.peak"),
    Path("/sys/fs/cgroup/memory/memory.max_usage_in_bytes"),
)
_MIB = 1024 * 1024


def snapshot():
    return {
        "rss_mib": _current_rss_mib(),
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "cgroup_current_mib": _read_cgroup_mib(_CGROUP_CURRENT_PATHS),
        "cgroup_peak_mib": _read_cgroup_mib(_CGROUP_PEAK_PATHS),
    }


def format_snapshot(values=None):
    values = values or snapshot()
    parts = [
        f"RSS {values['rss_mib']:.1f} MiB",
        f"peak RSS {values['peak_rss_mib']:.1f} MiB",
    ]
    if values["cgroup_current_mib"] is not None:
        parts.append(f"cgroup current {values['cgroup_current_mib']:.1f} MiB")
    if values["cgroup_peak_mib"] is not None:
        parts.append(f"cgroup peak {values['cgroup_peak_mib']:.1f} MiB")
    return "; ".join(parts)


def _current_rss_mib():
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _read_cgroup_mib(paths):
    for path in paths:
        try:
            value = path.read_text().strip()
            if value != "max":
                return int(value) / _MIB
        except (OSError, ValueError):
            continue
    return None
