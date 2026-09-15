import json
import os
import signal
from pathlib import Path


class MigrationInterrupted(RuntimeError):
    pass


class StopController:
    def __init__(self):
        self.requested = False
        self.previous_handlers = {}

    def install(self):
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            self.previous_handlers[signal_number] = signal.getsignal(signal_number)
            signal.signal(signal_number, self._request_stop)

    def restore(self):
        for signal_number, handler in self.previous_handlers.items():
            signal.signal(signal_number, handler)
        self.previous_handlers = {}

    def _request_stop(self, _signal_number, _frame):
        self.requested = True

    def raise_if_requested(self):
        if self.requested:
            raise MigrationInterrupted(
                "Migration interruption requested; the current batch was completed."
            )


def write_json_atomic(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(".%s.%d.tmp" % (destination.name, os.getpid()))
    try:
        with open(temporary, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_report_destination(path, protected_paths):
    if not path:
        return

    destination = Path(path).resolve()
    protected = {Path(value).resolve() for value in protected_paths}
    if destination in protected:
        raise ValueError("Report path would overwrite a migration input file.")
