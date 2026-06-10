from enum import Enum
class RunnerMixin:

    class Status(Enum):
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    def run(self):
        self.status = self.Status.RUNNING
        try:
            self._compute_run()
            self.status = self.Status.COMPLETED
        except Exception as e:
            self.status = self.Status.FAILED
            raise e