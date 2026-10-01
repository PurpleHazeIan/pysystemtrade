from syscore.genutils import highest_common_factor_for_list, sign

from sysexecution.trade_qty import tradeQuantity


def resolve_ig_positions(raw_positions) -> dict:
    """
    :param raw_positions: list of positions
    :return: list of positions resolved as fsb positions

    """
    resolved_positions_list = [
        resolve_ig_position(position) for position in raw_positions
    ]

    return resolved_positions_list


def resolve_ig_position(position):

    return dict(
        account=position["account"],
        symbol=position["epic"],
        expiry=position["expiry"],
        currency=position["currency"],
        size=position["size"],
        direction=position["direction"],
    )


def resolveBS_for_list(trade_list: tradeQuantity):
    if len(trade_list) == 1:
        return resolveBS(trade_list[0])
    else:
        return resolveBS_for_calendar_spread(trade_list)


def resolveBS_for_calendar_spread(trade_list: tradeQuantity):
    trade = highest_common_factor_for_list(trade_list)
    trade = sign(trade_list[0]) * trade
    return resolveBS(trade)


def resolveBS(trade: int):
    if trade < 0:
        return "SELL", int(abs(trade))
    return "BUY", int(abs(trade))


def sign_from_BS(buy_or_sell):
    if buy_or_sell == "SELL":
        return -1
    return 1
