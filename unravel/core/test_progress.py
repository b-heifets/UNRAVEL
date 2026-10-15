#!/usr/bin/env python3

import time

from unravel.core.utils import initialize_progress_bar


def main():
    total = 200

    progress, task_id = initialize_progress_bar(
        total,
        task_message="Processing...",
    )

    with progress:
        for _ in range(total):
            time.sleep(0.05)
            progress.advance(task_id)


if __name__ == "__main__":
    main()