from multiprocessing import Process, Queue, Event
from os import remove
from tempfile import TemporaryDirectory, NamedTemporaryFile

import pytest

import backtest.fetcher as sut


@pytest.mark.parametrize('input, expected', [
    ('AAAAA 10000 10 1234512345', ('AAAAA', 10000.0, 10.0, 1234512345)),
    ('AAAAA 10000 10 12345123\n', ('AAAAA', 10000.0, 10.0, 12345123)),
    ('AAAAA 10.1 1.1 1234512345', ('AAAAA', 10.1, 1.1, 1234512345)),
])
def test_parse(input, expected):
    tick = sut._parse(input)
    assert tick == expected


@pytest.mark.parametrize('input', [
    ('\n'),
    ('WRONG'),
    ('WRONG WRONG'),
    ('WRONG, 100, 10, 12345'),  # no comma
    ('WRONG 100 10 1234512345.0'),  # wrong timestamp format
    ('WRONG 100 10 1234512345 MORE'),
])
def test_parse_error(input):
    with pytest.raises(ValueError):
        sut._parse(input)


@pytest.fixture(scope='session')
def tick_file():
    # with TemporaryDirectory() as temp_dir:
    # with NamedTemporaryFile('wt', dir=temp_dir, delete=False) as file1:
    with NamedTemporaryFile('wt', delete=False) as file:
        file.write('AAAAA 1000 1 1000000001\n')
        file.write('AAAAA 1100 2 1000000002\n')
        file.write('AAAAA 1100 3 1000000003\n')
        file.write('BBBBB 3000 1 1000000004\n')

    yield file.name
    remove(file.name)


def test_get_tick_file(tick_file):
    gen = sut._read_tick(tick_file)
    tick = next(gen)
    assert tick.symbol == 'AAAAA'


def test_route_1():
    qs = [Queue()]
    route = sut._get_router(qs)

    assert route('AAAAA') == qs[0]
    assert route('BBBBB') == qs[0]
    assert route('AAAAA') == qs[0]
    assert route('CCCCC') == qs[0]
    assert route('BBBBB') == qs[0]
    assert route('AAAAA') == qs[0]


def test_route_3():
    qs = [Queue() for _ in range(3)]
    route = sut._get_router(qs)

    assert route('AAAAA') == qs[0]
    assert route('BBBBB') == qs[1]
    assert route('AAAAA') == qs[0]
    assert route('CCCCC') == qs[2]
    assert route('BBBBB') == qs[1]
    assert route('AAAAA') == qs[0]


def test_fetch(tick_file):
    queues = [Queue() for _ in range(2)]

    p = Process(target=sut.run, args=(tick_file, queues, Event()))
    p.start()
    p.join()

    assert queues[0].get().symbol == "AAAAA"
    assert queues[0].get().symbol == "AAAAA"
    assert queues[0].get().symbol == "AAAAA"
    assert queues[1].get().symbol == "BBBBB"
