from sysbrokers.IG.ig_futures_contract_data import igFuturesContractData
from sysbrokers.IG.ig_instruments_data import igFuturesInstrumentData
from sysbrokers.IG.ig_translate_broker_order_objects import (
    igOrderWithControls,
    create_broker_order_from_broker_activity,
    create_control_object_from_broker_activity,
)

from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.IG.client.ig_client import igClient

from sysbrokers.broker_execution_stack import brokerExecutionStackData
from sysdata.data_blob import dataBlob
from syscore.constants import arg_not_supplied
from syscore.exceptions import orderCannotBeModified

from sysexecution.orders.named_order_objects import missing_order
from sysexecution.orders.list_of_orders import listOfOrders
from sysexecution.orders.broker_orders import brokerOrder

from syslogging.logger import *


class igExecutionStackData(brokerExecutionStackData):
    def __init__(
        self,
        ig_conn: connectionIG,
        data: dataBlob,
        log=get_logger("igExecutionStackData"),
    ):
        super().__init__(log=log, data=data)
        self._ig_conn = ig_conn

    def __repr__(self):
        return "IG execution stack"

    @property
    def ig_conn(self) -> connectionIG:
        return self._ig_conn

    @property
    def futures_contract_data(self) -> igFuturesContractData:
        return self.data.broker_futures_contract

    @property
    def futures_instrument_data(self) -> igFuturesInstrumentData:
        return self.data.broker_futures_instrument

    @property
    def ig_client(self) -> igClient:
        client = getattr(self, "_ig_client", None)
        if client is None:
            client = self._ig_client = igClient(igconnection=self.ig_conn, log=self.log)
        return client

    @property
    def traded_object_store(self) -> dict:
        store = getattr(self, "_traded_object_store", None)
        if store is None:
            store = self._traded_object_store = {}

        return store

    def _add_order_with_controls_to_store(
        self, order_with_controls: igOrderWithControls
    ):
        storage_key = order_with_controls.order.broker_permid
        self.traded_object_store[storage_key] = order_with_controls

    def get_list_of_broker_orders_with_account_id(
        self, account_id: str = arg_not_supplied
    ) -> listOfOrders:
        """
        Get list of broker orders from IG, and return as broker_order objects

        :return: list of brokerOrder objects
        """
        list_of_control_objects = self.get_list_of_broker_control_orders(
            account_id=account_id
        )
        order_list = [
            order_with_control.order for order_with_control in list_of_control_objects
        ]

        order_list = listOfOrders(order_list)

        return order_list

    def _get_dict_of_broker_control_orders(
        self, account_id: str = arg_not_supplied
    ) -> dict:
        control_order_list = self.get_list_of_broker_control_orders(
            account_id=account_id
        )
        dict_of_control_orders = dict(
            [
                (control_order.order.broker_permid, control_order)
                for control_order in control_order_list
            ]
        )
        return dict_of_control_orders

    def get_list_of_broker_control_orders(
        self, account_id: str = arg_not_supplied
    ) -> list:
        """
        Get list of broker orders from IG, as activities in the activity history,
        and return a list of orders with controls

        :return: list of brokerOrderWithControl objects
        """

        list_of_broker_activities = self.ig_client.broker_get_activities(
            account_id=account_id
        )

        broker_order_with_controls_list = [
            self._create_broker_control_order_object(single_broker_activity)
            for single_broker_activity in list_of_broker_activities
        ]

        broker_order_with_controls_list = [
            broker_order_with_controls
            for broker_order_with_controls in broker_order_with_controls_list
            if broker_order_with_controls is not missing_order
        ]

        return broker_order_with_controls_list

    def _create_broker_control_order_object(
        self, single_broker_activity
    ) -> igOrderWithControls:
        """
        Map from the data IG gives us in the activity history to a broker order
        and a control object and then create an order with controls

        """

        # don't want to see stop loss or limit changes
        if single_broker_activity["activity"] == "S&L":
            return missing_order
        # also don't want to see creating or deleting limit orders (Orders To Open)
        # only the real order if it actually executed
        if single_broker_activity["activity"] == "OTO":
            return missing_order
        # nor do we want to see rejects e.g. trying to deal when market not available
        if single_broker_activity["actionStatus"] == "REJECT":
            return missing_order

        epic = single_broker_activity["epic"]
        instrument_code = (
            self.futures_instrument_data.get_instrument_code_from_broker_code(epic)
        )
        # nor do we want to see activity on instruments we don't recognise
        if instrument_code is None:
            return missing_order

        created_control_object = create_control_object_from_broker_activity(
            single_broker_activity,
        )

        created_broker_order = create_broker_order_from_broker_activity(
            single_broker_activity,
            instrument_code,
        )

        order_with_controls = igOrderWithControls(
            control_object=created_control_object, broker_order=created_broker_order
        )

        return order_with_controls

    def get_list_of_orders_from_storage(self) -> listOfOrders:
        dict_of_stored_orders = self._get_dict_of_orders_from_storage()
        list_of_orders = listOfOrders(dict_of_stored_orders.values())

        return list_of_orders

    def _get_dict_of_orders_from_storage(self) -> dict:
        # Get dict from storage, update, return just the orders
        dict_of_orders_with_control = self._get_dict_of_control_orders_from_storage()
        order_dict = dict(
            [
                (key, order_with_control.order)
                for key, order_with_control in dict_of_orders_with_control.items()
            ]
        )

        return order_dict

    def _get_dict_of_control_orders_from_storage(self) -> dict:
        dict_of_orders_with_control = self.traded_object_store
        __ = [
            order_with_control.update_order()
            for order_with_control in dict_of_orders_with_control.values()
        ]

        return dict_of_orders_with_control

    def put_order_on_stack(self, broker_order: brokerOrder) -> igOrderWithControls:
        """

        :param broker_order: key properties are instrument_code, contract_id, quantity
        :return: igOrderWithControls or missing_order
        """
        placed_broker_order_with_controls = self._send_broker_order_to_IG(broker_order)
        if placed_broker_order_with_controls is missing_order:
            return missing_order

        order_time = self.ig_client.broker_get_time_local_tz()
        placed_broker_order_with_controls.order.submit_datetime = order_time

        # Set permid (and tempid, although it's not used in this implementation)
        placed_broker_order_with_controls.order.broker_permid = (
            placed_broker_order_with_controls.control_object["dealId"]
        )
        placed_broker_order_with_controls.order.broker_tempid = (
            placed_broker_order_with_controls.control_object["dealReference"]
        )

        self._add_order_with_controls_to_store(placed_broker_order_with_controls)

        return placed_broker_order_with_controls

    def _send_broker_order_to_IG(
        self, broker_order: brokerOrder
    ) -> igOrderWithControls:
        """

        :param broker_order: key properties are instrument_code, contract_id, quantity
        :return: trade_result or missing_order

        """

        log_attrs = {**broker_order.log_attributes(), "method": "temp"}
        self.log.debug(
            "Going to submit order %s to IG" % str(broker_order),
            **log_attrs,
        )

        try:
            order_with_controls = self.ig_client.broker_submit_order(broker_order)
        except Exception as exc:
            self.log.warning(f"Problem submitting broker order: {exc}", **log_attrs)
            order_with_controls = missing_order

        if order_with_controls is missing_order:
            self.log.warning("Couldn't submit order", **log_attrs)
            return missing_order

        self.log.debug("Order submitted to IG", **log_attrs)

        return order_with_controls

    def match_db_broker_order_to_order_from_brokers(
        self, broker_order_to_match: brokerOrder
    ) -> brokerOrder:
        matched_control_order = (
            self.match_db_broker_order_to_control_order_from_brokers(
                broker_order_to_match
            )
        )
        if matched_control_order is missing_order:
            return missing_order

        broker_order = matched_control_order.order

        return broker_order

    def match_db_broker_order_to_control_order_from_brokers(
        self, broker_order_to_match: brokerOrder
    ) -> igOrderWithControls:
        """

        :return: brokerOrder coming from broker
        """

        # check stored orders first
        dict_of_stored_control_orders = self._get_dict_of_control_orders_from_storage()
        matched_control_order = match_control_order_from_dict(
            dict_of_stored_control_orders, broker_order_to_match
        )
        if matched_control_order is not missing_order:
            return matched_control_order

        # Match on permid
        dict_of_broker_control_orders = self._get_dict_of_broker_control_orders()
        matched_control_order = match_control_order_from_dict(
            dict_of_broker_control_orders, broker_order_to_match
        )

        return matched_control_order

    def cancel_order_on_stack(self, broker_order: brokerOrder):
        # Before cancelling we check whether the order has executed already. If it has,
        # capture the fill, if not, issue the cancel.
        #
        # XXX Corner case - what if we try to cancel an order which executes at the same
        # time? Do this the other way around and pause in-between?

        log_attrs = {**broker_order.log_attributes(), "method": "temp"}

        dict_of_broker_control_orders = self._get_dict_of_broker_control_orders()
        matched_control_order = match_control_order_from_dict(
            dict_of_broker_control_orders, broker_order
        )

        if matched_control_order is not missing_order:
            # Order found in list of broker activities, so has executed, so need to fill
            # broker_order so that fills and completion can happen

            control_object = matched_control_order.control_object
            fill_qty = control_object["size"]
            if control_object["direction"] == "SELL":
                fill_qty = -fill_qty
            fill_qty = [fill_qty]
            filled_price = control_object["level"]

            broker_order.fill_order(fill_qty=fill_qty, filled_price=filled_price)

            self.log.debug(
                "Executed so no need to cancel %s" % str(broker_order), **log_attrs
            )

            # Response is not consumed by caller stack_handler.cancel_and_modify().
            # Instead caller goes on to query whether cancellation succeeded or not
            return missing_order

        self.ig_client.broker_cancel_order(broker_order)
        self.log.debug("Sent cancellation for %s" % str(broker_order), **log_attrs)

    def cancel_order_given_control_object(
        self, broker_order_with_controls: igOrderWithControls
    ):
        broker_order = broker_order_with_controls.order
        cancel_result = self.ig_client.broker_cancel_order(broker_order)
        return cancel_result

    def check_order_is_cancelled(self, broker_order: brokerOrder) -> bool:
        matched_control_order = (
            self.match_db_broker_order_to_control_order_from_brokers(broker_order)
        )
        if matched_control_order is missing_order:
            # Not found in store or at broker - hence cancelled or not cancellable
            return True
        cancellation_status = self.check_order_is_cancelled_given_control_object(
            matched_control_order
        )

        return cancellation_status

    def check_order_is_cancelled_given_control_object(
        self, broker_order_with_controls: igOrderWithControls
    ) -> bool:

        # If the order is still in the list of working_orders, it is not cancelled
        in_working_orders = self.check_order_can_be_modified_given_control_object(
            broker_order_with_controls
        )
        if in_working_orders:
            return False

        # Possibilities are:
        # Market order which executed synchronously
        # Limit order which has executed or been cancelled
        # So: nothing to cancel but nothing to execute, so effectively cancelled
        return True

    def check_order_can_be_modified_given_control_object(
        self, broker_order_with_controls: igOrderWithControls
    ) -> bool:

        # Check whether the order is in the list of working_orders
        deal_id = broker_order_with_controls.order.broker_permid

        working_orders = self.ig_client.broker_get_working_orders()
        working_deals = [
            working_order.get("dealId") for working_order in working_orders
        ]
        in_working_orders = deal_id in working_deals

        return in_working_orders

    def get_status_for_control_object(
        self, broker_order_with_controls: igOrderWithControls
    ):

        # Generally called to check whether an order has been cancelled successfully
        # just after it has been cancelled hopefully. Returns missing_order which
        # signals successful, or position detail which also implies success in that
        # there is nothing left to cancel

        # Possibilities are:
        # Market or limit order that has been executed ...
        # - cancel should always 'succeed' as there is nothing left to cancel
        # - querying position by dealId returns position detail
        # - for the executed limit order it has the actual price and quantity
        # Limit order that is working ...
        # - cancel should always succeed and a real cancellation should have occurred
        # - querying non-existent position by dealId returns missing_order

        order_object = broker_order_with_controls.order
        query_result = self.ig_client.broker_query_position(order_object)

        return query_result

    def modify_limit_price_given_control_object(
        self, broker_order_with_controls: igOrderWithControls, new_limit_price: float
    ) -> igOrderWithControls:
        """
        NOTE this does not update the internal state of orders,
        which will retain the original order

        :param broker_order_with_controls:
        :param new_limit_price:
        :return:
        """

        in_working_orders = self.check_order_can_be_modified_given_control_object(
            broker_order_with_controls
        )

        # If the deal is no longer a working order, return an exception for the algo
        if not in_working_orders:
            raise orderCannotBeModified(
                "Order can't be modified as not a working order"
            )

        broker_order = broker_order_with_controls.order
        new_control_object = self.ig_client.broker_amend_limit_order(
            broker_order,
            new_limit_price,
        )

        new_deal_id = new_control_object.get("dealId")
        original_id = broker_order.broker_permid

        # If the id is the same then the amend was accepted; if they differ then the
        # amend was rejected (with a new deal_id) whilst the original order remains in
        # place (with the original deal_id)
        if new_deal_id != original_id:
            raise orderCannotBeModified(
                "New limit price %f rejected by broker" % new_limit_price
            )

        # update order and replace control object in order_with_controls and in store
        broker_order_with_controls.order.limit_price = new_limit_price
        broker_order_with_controls.replace_control_object(new_control_object)
        broker_order_with_controls.update_order()

        self._add_order_with_controls_to_store(broker_order_with_controls)

        return broker_order_with_controls


def match_control_order_from_dict(
    dict_of_broker_control_orders: dict, broker_order_to_match: brokerOrder
):
    matched_control_order_from_dict = dict_of_broker_control_orders.get(
        broker_order_to_match.broker_permid, missing_order
    )

    return matched_control_order_from_dict
