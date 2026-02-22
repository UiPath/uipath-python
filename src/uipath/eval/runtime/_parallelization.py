import asyncio
from typing import Awaitable, Iterable, TypeVar

T = TypeVar("T")


async def execute_parallel(
    evaluation_result_iterable: Iterable[Awaitable[T]],
    workers: int,
) -> list[T]:
    # Create a queue with max concurrency
    queue: asyncio.Queue[tuple[int, Awaitable[T]] | None] = asyncio.Queue(
        maxsize=workers
    )

    # Dictionary to store results with their original indices
    results_dict: dict[int, T] = {}

    # Producer task to fill the queue
    async def producer() -> None:
        for index, eval_item in enumerate(evaluation_result_iterable):
            await queue.put((index, eval_item))
        # Signal completion by putting None markers
        for _ in range(workers):
            await queue.put(None)

    # Worker function to process items from the queue
    async def worker(worker_id: int) -> None:
        while True:
            item = await queue.get()

            # Check for termination signal
            if item is None:
                queue.task_done()
                break

            index, eval_item = item

            try:
                # Execute the evaluation
                result = await eval_item

                # Store result with its index to maintain order
                results_dict[index] = result
            finally:
                # Mark the task as done
                queue.task_done()

    # Start producer
    producer_task = asyncio.create_task(producer())

    # Create worker tasks based on workers
    worker_tasks = [asyncio.create_task(worker(i)) for i in range(workers)]

    # Wait for producer and all workers to complete
    await producer_task
    await asyncio.gather(*worker_tasks)

    # Return results in the original order
    return [results_dict[i] for i in range(len(results_dict))]
