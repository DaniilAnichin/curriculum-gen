import os

MAX_WORKERS = max(int(os.getenv('SOLVER_MAX_WORKERS', os.cpu_count() - 1)), 1)
