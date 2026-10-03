"""Persistent Edge Storage for Pico W Gateway.

Stores observations as newline-delimited JSON (JSONL) on the local filesystem.
Maintains a bounded in-memory cache of the most recent observations while
persisting all valid observations to flash. Tolerates corrupted lines gracefully.
"""

import json

STORAGE_FILE = "observations.jsonl"
DEFAULT_MAX_CACHE = 50
MAX_FILE_BYTES = 256 * 1024

# In-memory bounded cache and total counter
_cache = []
_max_cache = DEFAULT_MAX_CACHE
_total_count = 0
_filename = STORAGE_FILE



def initialize(filename=STORAGE_FILE, max_cache=DEFAULT_MAX_CACHE):
    """Initialize storage, count existing records, and populate bounded cache.

    Tolerates missing files and corrupted lines without crashing.
    """
    global _cache, _max_cache, _total_count, _filename

    _filename = filename
    _max_cache = max_cache
    _cache = []
    _total_count = 0

    try:
        with open(_filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    _total_count += 1
                    _cache.append(record)
                    if len(_cache) > _max_cache:
                        _cache.pop(0)
                except Exception as e:
                    # AC-10: Skip corrupted/malformed line gracefully
                    print("Storage warning: skipping corrupted line:", line[:50])
    except OSError:
        # File does not exist yet; create an empty file
        try:
            with open(_filename, "w") as f:
                pass
        except Exception as e:
            print("Storage init warning:", e)

    return _total_count


def _rotate_file_if_needed():
    """If file exceeds MAX_FILE_BYTES, retain the most recent records to prevent ENOSPC."""
    global _filename
    try:
        import os
        size = 0
        try:
            stat_res = os.stat(_filename)
            size = stat_res[6]
        except Exception:
            return

        if size > MAX_FILE_BYTES:
            print("Storage: rotating", _filename, "(" + str(size) + " bytes)")
            with open(_filename + ".tmp", "w") as f:
                for item in _cache:
                    f.write(json.dumps(item) + "\n")
            try:
                os.remove(_filename)
            except Exception:
                pass
            os.rename(_filename + ".tmp", _filename)
            print("Storage: rotation complete, file size reset.")
    except Exception as e:
        print("Storage rotation warning:", e)


def save_observation(observation):
    """Append a single observation to the JSONL file and update the RAM cache.

    Flushes immediately to ensure durability across power loss.
    """
    global _total_count

    try:
        _rotate_file_if_needed()
        serialized = json.dumps(observation)
        with open(_filename, "a") as f:
            f.write(serialized + "\n")
            f.flush()

        _total_count += 1
        _cache.append(observation)
        if len(_cache) > _max_cache:
            _cache.pop(0)

        return True, None
    except Exception as e:
        return False, str(e)



def get_observations():
    """Return the bounded in-memory cache of recent observations."""
    return list(_cache)


def count_observations():
    """Return the total number of observations recorded on flash."""
    return _total_count


def get_stats():
    """Return storage diagnostic information."""
    return {
        "filename": _filename,
        "total_records": _total_count,
        "cached_records": len(_cache),
        "max_cache": _max_cache
    }


def clear_storage():
    """Reset storage file and RAM cache (used primarily for testing)."""
    global _cache, _total_count
    _cache = []
    _total_count = 0
    with open(_filename, "w") as f:
        pass
