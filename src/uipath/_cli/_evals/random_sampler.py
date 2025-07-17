import random
from typing import Any, Generator, Sequence


class RandomChainSampler:
    """Sampler that randomly chains multiple iterables together.

    This class takes a sequence of generators and yields items from them
    in random order, removing generators as they become exhausted.
    """

    def __init__(self, iterables: Sequence[Generator[Any, None, None]]):
        """Initialize the sampler with a sequence of iterables.

        Args:
            iterables: Sequence of generators to sample from
        """
        self.iterables = list(iterables)

    def __iter__(self):
        """Return the iterator object."""
        return self

    def __next__(self):
        """Get the next item from a randomly selected iterable.

        Returns:
            The next item from one of the iterables

        Raises:
            StopIteration: When all iterables are exhausted
        """
        while len(self.iterables) > 0:
            current_iterable = random.choice(self.iterables)
            try:
                return next(current_iterable)
            except StopIteration:
                self.iterables.remove(current_iterable)
        raise StopIteration
