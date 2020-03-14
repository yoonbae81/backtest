import json
from datetime import datetime
from multiprocessing import Value
from os.path import join
from pathlib import Path

from . import logger
from .data import Order, Filled
from .market import kosdaq, kospi


def run(config, cash, holding_dict, order_queue, log_queue):
    logger.config(log_queue)

    ledger = _get_ledger(config['ledger_dir'])
    print(json.dumps({'cash': cash.value}), file=ledger)

    logger.info('Loading symbols list from ' + config['symbols_json'])
    with open(config['symbols_json'], 'rt') as f:
        market_dict = json.load(f)

    count = 0
    while order := order_queue.get():
        market = _get_market(market_dict, order.symbol)
        filled = _get_filled(config, market, order)

        _update_holding(holding_dict, filled)
        _update_cash(cash, filled)

        print(json.dumps(filled), file=ledger)
        logger.debug('Ledger: ' + json.dumps(filled))

        count += 1

    ledger.close()
    logger.info(f'Processed {count} orders and wrote to {ledger.name}')


def _get_ledger(dir):
    Path(dir).mkdir(parents=True, exist_ok=True)
    name = f'{datetime.now():%Y%m%d%H%M%S}.jsonl'

    return open(join(dir, name), 'wt')


def _get_market(market_dict, symbol):
    return kospi if market_dict.get(symbol, None) == 'KOSPI' else kosdaq


def _get_filled(config, market, order) -> Filled:
    price = market.simulate_market_price(order, config['slippage_stdev'])
    commission = market.calc_commission(order)
    tax = market.calc_tax(order)

    filled = Filled(
        order.timestamp,
        order.symbol,
        order.quantity,
        price,
        commission,
        tax,
        order.price - price,
    )

    return filled


def _update_holding(holding_dict, filled: Filled):
    holding_dict.setdefault(filled.symbol, 0)
    holding_dict[filled.symbol] += filled.quantity

    assert holding_dict[filled.symbol] >= 0


def _update_cash(cash: Value, filled: Filled):
    cash.value -= filled.quantity * filled.price \
                  + filled.commission \
                  + filled.tax

    assert cash.value >= 0
