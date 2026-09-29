"""Keep OMX realignment safe with the locked Sharrow/PyTables loader.

Sharrow 2.15's shared-memory loader explicitly uses Dask's threaded scheduler.
Concurrent reads through a PyTables handle can segfault when OMX and land-use
orders differ. One Dask worker serializes those reads without changing the
ActivitySim worker count or compiled expression execution.
"""

import dask

_DASK_SKIM_CONFIG = dask.config.set(num_workers=1)
