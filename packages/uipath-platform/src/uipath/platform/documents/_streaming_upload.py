"""Multipart bodies for documents that are uploaded while they are read.

httpx builds a multipart body from a file object, but it needs `fileno()` or
`seek()` to find the length. A network stream has neither, so httpx falls back to
chunked transfer encoding, and on a retry it cannot rewind the stream. Here the
body is built by hand: the length is known before the first byte is sent, and
each attempt reads the source again from the start.

The part has the same bytes httpx would write for
`files={"File": (name, content, content_type)}`, so the service sees no change.
"""

import os
from collections.abc import AsyncGenerator, AsyncIterator, Iterable, Iterator
from dataclasses import dataclass

from .documents import FileChunks, StreamingFile

# Same escaping httpx applies to form parameters (HTML5 multipart rules).
_PARAM_REPLACEMENTS = {'"': "%22", "\\": "\\\\", "\r": "%0D", "\n": "%0A"}


def _quote_param(value: str) -> str:
    return "".join(_PARAM_REPLACEMENTS.get(char, char) for char in value)


@dataclass(frozen=True)
class MultipartLayout:
    """The fixed parts of a one-file multipart body."""

    content_type: str
    head: bytes
    tail: bytes
    content_length: int


def multipart_layout(source: StreamingFile, field_name: str) -> MultipartLayout:
    """Build the boundary, part headers and total length for `source`."""
    boundary = os.urandom(16).hex()
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{_quote_param(field_name)}"; '
        f'filename="{_quote_param(source.name)}"\r\n'
        f"Content-Type: {source.content_type}\r\n"
        "\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return MultipartLayout(
        content_type=f"multipart/form-data; boundary={boundary}",
        head=head,
        tail=tail,
        content_length=len(head) + source.size + len(tail),
    )


def _size_error(source: StreamingFile, sent: int) -> ValueError:
    return ValueError(
        f"StreamingFile '{source.name}' declared {source.size} bytes, "
        f"but its source yielded {'more than ' if sent > source.size else ''}{sent}."
    )


def iter_body(layout: MultipartLayout, source: StreamingFile) -> Iterator[bytes]:
    """Yield one attempt's body. Opens the source, and closes it when done."""
    chunks = source.open()
    if not isinstance(chunks, Iterable):
        raise TypeError(
            "The synchronous methods need a StreamingFile whose `open` returns "
            "an Iterable[bytes]. Use the asynchronous method for an async source."
        )
    iterator = iter(chunks)
    try:
        yield layout.head
        sent = 0
        for chunk in iterator:
            sent += len(chunk)
            if sent > source.size:
                raise _size_error(source, sent)
            if chunk:
                yield bytes(chunk)
        if sent != source.size:
            raise _size_error(source, sent)
        yield layout.tail
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            close()


async def aiter_body(
    layout: MultipartLayout, source: StreamingFile
) -> AsyncIterator[bytes]:
    """Asynchronous version of `iter_body`. Accepts a sync or an async source."""
    chunks: FileChunks = source.open()
    reader = _aiter_chunks(chunks)
    try:
        yield layout.head
        sent = 0
        async for chunk in reader:
            sent += len(chunk)
            if sent > source.size:
                raise _size_error(source, sent)
            if chunk:
                yield bytes(chunk)
        if sent != source.size:
            raise _size_error(source, sent)
        yield layout.tail
    finally:
        await reader.aclose()
        aclose = getattr(chunks, "aclose", None)
        close = getattr(chunks, "close", None)
        if aclose is not None:
            await aclose()
        elif close is not None:
            close()


async def _aiter_chunks(chunks: FileChunks) -> AsyncGenerator[bytes, None]:
    if isinstance(chunks, Iterable):
        iterator = iter(chunks)
        try:
            for chunk in iterator:
                yield chunk
        finally:
            if iterator is not chunks:
                close = getattr(iterator, "close", None)
                if close is not None:
                    close()
    else:
        async_iterator = aiter(chunks)
        try:
            async for chunk in async_iterator:
                yield chunk
        finally:
            if async_iterator is not chunks:
                aclose = getattr(async_iterator, "aclose", None)
                if aclose is not None:
                    await aclose()
