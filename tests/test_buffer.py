from cognita.buffer import Buffer


def test_buffer_init():
    data = b"hello"
    meta = {"type": "text"}
    buf = Buffer(data, meta)
    assert buf._data == data
    assert buf.meta == meta
    assert buf.remaining == 5


def test_buffer_read():
    data = b"0123456789"
    buf = Buffer(data)

    chunk1 = buf.read(4)
    assert chunk1 == b"0123"
    assert buf.remaining == 6

    chunk2 = buf.read(4)
    assert chunk2 == b"4567"
    assert buf.remaining == 2

    chunk3 = buf.read(10)  # Read more than remaining
    assert chunk3 == b"89"
    assert buf.remaining == 0

    chunk4 = buf.read(1)
    assert chunk4 == b""


def test_buffer_read_all():
    data = b"test"
    buf = Buffer(data)
    content = buf.read()  # read with None
    assert content == data
    assert buf.remaining == 0


def test_buffer_rewind():
    data = b"retry"
    buf = Buffer(data)
    buf.read(2)
    assert buf.remaining == 3

    buf.rewind()
    assert buf.remaining == 5
    assert buf.read() == data
