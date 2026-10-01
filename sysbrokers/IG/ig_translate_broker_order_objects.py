"""

Note:
a broker_order is the internal representation of an order to be sent to the broker.
a control_object, also a trade_result, is the broker response to submitting that
broker_order. This response is issued synchronously and contains execution data
for a market order, or the equivalent data for a working limit order, allowing it
to be tracked to completion. It can be autofilled if that was specified for the trade.
an order_with_controls is the combination of a broker_order with a control_object
and an optional ticker_object (not defined in this module, see ig_client_for_prices).
a broker_activity is the response to a call to get_activities which has a slightly
different format from the trade_result.

"""

import datetime

from sysexecution.orders.broker_orders import brokerOrder
from sysexecution.order_stacks.broker_order_stack import orderWithControls
from sysexecution.tick_data import tickerObject


# XXX WIP
# The object returned from this is still a brokerOrder, so has no extra methods/properties
# only added attributes
class igBrokerOrder(brokerOrder):

    def __init__(self):
        pass

    @classmethod
    def from_broker_order(cls, broker_order):
        broker_order._extra_field = "XXX"
        return broker_order


class igOrderWithControls(orderWithControls):
    def __init__(
        self,
        control_object,
        broker_order: brokerOrder,
        ticker_object: tickerObject = None,
    ):

        super().__init__(
            broker_order=broker_order,
            control_object=control_object,
            ticker_object=ticker_object,
        )

    def __repr__(self):
        return f"Order: {str(self.order)}, with control: {str(self.control_object)}"

    def update_order(self):
        pass

    def broker_limit_price(self):
        return self.order.limit_price


def create_control_object_in_place_of_trade_result(
    epic=None,
    expiry=None,
    size=None,
    direction=None,
    filled_price=None,
) -> dict:

    created_control_object = {
        "date": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "CLOSED",
        "reason": "SUCCESS",
        "dealStatus": "ACCEPTED",
        "epic": epic,
        "expiry": expiry,
        "dealReference": epic,  # unique per run of stack_handler
        "dealId": epic,  # likewise
        "affectedDeals": [],
        "level": filled_price,
        "size": size,
        "direction": direction,
        "stopLevel": None,
        "limitLevel": None,
        "stopDistance": None,
        "limitDistance": None,
        "guaranteedStop": False,
        "trailingStop": False,
        "profit": 0.0,
        "profitCurrency": "GBP",
    }

    return created_control_object


def create_control_object_from_broker_activity(broker_activity: dict) -> dict:
    """
    A sample individual activity from ig_client.broker_get_actvities()
    {
    'epic': 'IX.D.SPTRD.MONTH2.IP',
    'dealId': 'DIAAAAN8YUNL7AR',
    'activityHistoryId': '3870450725',
    'date': '14/03/25',
    'time': '13:13',
    'activity': 'Order',
    'marketName': 'US 500',
    'period': 'MAR-25',
    'result': 'Position opened: 8YUNL7AR',
    'channel': 'Web',
    'currency': '£',
    'size': '-1',
    'level': '5579.13',
    'stop': '-',
    'stopType': '-',
    'limit': '-',
    'actionStatus': 'ACCEPT'
    }

    """

    if float(broker_activity["size"]) >= 0:
        direction = "BUY"
    else:
        direction = "SELL"
    if broker_activity["actionStatus"] == "ACCEPT":
        dealStatus = "ACCEPTED"
    else:
        dealStatus = "REJECTED"

    activity_date = broker_activity["date"]
    activity_time = broker_activity["time"]
    activity_datetime = activity_date + " " + activity_time
    fill_datetime = datetime.datetime.strptime(activity_datetime, "%d/%m/%y %H:%M")

    created_control_object = {
        "date": fill_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": dealStatus,
        "reason": broker_activity["activity"],
        "dealStatus": dealStatus,
        "epic": broker_activity["epic"],
        "expiry": broker_activity["period"],
        "dealReference": "Not in feed",
        "dealId": broker_activity["dealId"],
        "affectedDeals": broker_activity["result"],
        "level": float(broker_activity["level"]),
        "size": abs(float(broker_activity["size"])),
        "direction": direction,
        "stopLevel": None,
        "limitLevel": None,
        "stopDistance": None,
        "limitDistance": None,
        "guaranteedStop": False,
        "trailingStop": False,
        "profit": 0.0,
        "profitCurrency": "GBP",
    }

    return created_control_object


def create_broker_order_from_broker_activity(
    broker_activity: dict,
    instrument_code: str,
) -> brokerOrder:
    """
    A sample individual activity from ig_client.broker_get_actvities() as before

    """

    strategy = broker_activity["epic"]  # Isn't strategy but fills field!

    period = broker_activity["period"]
    if period == "DFB":
        contract_id = "20991200"
    else:
        contract_id = (
            datetime.datetime.strptime(period, "%b-%y").strftime("%Y%m") + "00"
        )

    fill = [int(float(broker_activity["size"]))]  # because it's a string
    trade = fill
    filled_price = float(broker_activity["level"])

    activity_date = broker_activity["date"]
    activity_time = broker_activity["time"]
    activity_datetime = activity_date + " " + activity_time
    fill_datetime = datetime.datetime.strptime(activity_datetime, "%d/%m/%y %H:%M")

    broker_permid = broker_activity["dealId"]

    created_broker_order = brokerOrder(
        strategy,
        instrument_code,
        contract_id,
        trade,
        fill=fill,
        fill_datetime=fill_datetime,
        filled_price=filled_price,
        broker_permid=broker_permid,
    )

    return created_broker_order
