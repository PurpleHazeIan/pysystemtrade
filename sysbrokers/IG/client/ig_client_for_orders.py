import datetime as dt

from syscore.exceptions import missingData
from sysexecution.orders.named_order_objects import missing_order
from sysexecution.orders.broker_orders import limit_order_type, market_order_type

from sysbrokers.IG.ig_translate_broker_order_objects import (
    igOrderWithControls,
    create_control_object_in_place_of_trade_result,
)


class igClientForOrders:
    """
    This class will submit, amend or cancel an order at IG.
    Don't invoke directly, use only through inheritance as part of igClient.

    """

    def broker_submit_order(self, broker_order) -> igOrderWithControls:
        """
        Caller (igExecutionStackData.send_broker_order_to_ig) can handle either
        missing_order or an Exception as a failure condition, and the order will
        be cancelled - i.e. treated straightaway as if it was never raised. (NB
        this method doesn't raise or handle any Exceptions itself.)

        Otherwise it will receive a real trade_result from IG if order placed,
        or a realistic trade_result if autofilled.

        If the trade_result records that it was ACCEPTED, the broker_order is filled
        and in the controlling algo this will result in it being considered complete,
        with held positions updated accordingly in mongo.

        If the trade_result records that it was REJECTED, the broker_order is left
        unfilled. The controlling algo will see that it has not completed synchronously
        and test if it has completed asynchronously or cancelled. If cancelled then
        no position updates occur.

        Market orders raised here never wait at the broker - unlike real futures
        markets, there is no concept of available volume - so they always return
        synchronously with an acceptance or a rejection. Limit orders may be rejected
        synchronously, or wait for execution to be completed or rejected asynchronously.

        """

        self.log.debug("Preparing to submit order to IG: %s" % broker_order)

        order_type = broker_order.order_type
        contract_object = broker_order.futures_contract
        trade = broker_order.trade

        # Can't place an order with non-simple trade quantity, so return missing_order;
        # not sure this can ever arise this late in the process, but no harm in checking.
        size_with_sign = trade.as_single_trade_qty_or_error()
        if size_with_sign is missing_order:
            self.log.warning("IG order has invalid trade quantity '%s'" % trade)
            return missing_order

        try:
            matching_market_info = self.get_unique_market_for_contract(contract_object)
        except missingData:
            # Can't find an unambiguous market to use for this instrument; not sure that
            # we should be able to get this far if this were so. Return missing_order.
            self.log.warning("IG order has invalid market '%s'" % contract_object)
            return missing_order

        epic = matching_market_info["epic"]
        expiry = matching_market_info["expiry"]

        # If the market is not currently tradeable, then we can't place a trade.
        # We could manage this and execute the order later when open, but simply
        # return missing_order. Next run of order generator will regenerate if needed.
        market_status = matching_market_info["marketStatus"]
        if market_status != "TRADEABLE":
            self.log.warning(
                "IG order for %s not placed as status is '%s'" % (epic, market_status)
            )
            return missing_order

        size = abs(size_with_sign)
        sign = trade.buy_or_sell()
        if sign == 1:
            direction = "BUY"
        else:
            direction = "SELL"

        # If autofilling orders just make it look like order has been placed and filled
        if not self.igconnection.place_trades:
            self.log.debug("IG autofilled order for %s %s" % (epic, expiry))

            fill_qty = trade
            filled_price = broker_order.side_price

            trade_result = create_control_object_in_place_of_trade_result(
                epic=epic,
                expiry=expiry,
                size=size,
                direction=direction,
                filled_price=filled_price,
            )
            self.log.debug("IG autofilled order response %s" % trade_result)

            # Comment out this next line to test order not being filled
            # NB if never filled then fill_qty is [0] and filled_price is None
            broker_order.fill_order(fill_qty=fill_qty, filled_price=filled_price)

            order_with_controls = igOrderWithControls(
                control_object=trade_result, broker_order=broker_order
            )
            return order_with_controls

        self.log.debug("IG submitted order for %s %s" % (epic, expiry))

        # If placing trades then ... place market trade and fill order from response
        if order_type == market_order_type:
            trade_result = self.submit_market_order(
                epic=epic,
                expiry=expiry,
                size=size,
                direction=direction,
            )
            fill_qty = [trade_result["size"] * sign]
            filled_price = trade_result["level"]
            broker_order.fill_order(fill_qty=fill_qty, filled_price=filled_price)

        # Or place limit trade ... no filling afterwards as we wait on execution
        if order_type == limit_order_type:
            trade_result = self.submit_limit_order(
                epic=epic,
                expiry=expiry,
                size=size,
                direction=direction,
                limit=broker_order.limit_price,
            )

        # XXX There's a logical execution gap here. If the order was a limit order
        # there's a small hole in trading_ig. After the working order is submitted
        # the rest code searches for the deal_reference in the list of working orders.
        # But if the working_order executed instantly then it won't find it - the window
        # for this is tiny, but I've seen it once in not that many orders - and the
        # rest code returns the exception "error.confirms.deal-not-found" to our caller
        # ig_orders._send_broker_order_to_IG(). Unfortunately we are not returned the
        # deal_id or the deal_reference with which to search in the activity history.

        self.log.debug("IG submitted order response %s" % trade_result)

        # A simple missing_order is used here if order was not accepted on submission.
        # Alternatively we could leave on the stack, returning a trade_result
        # with no fill information, to be tidied up in stack_handler shutdown.
        # In practice we return missing_order from other situations in which orders would
        # not be accepted, and if we changed this here we'd have to change the earlier
        # behaviour too, as well as checking elsewhere that we didn't misread the rejected
        # activity as a successful execution (i.e. not missing_order). Also in principle
        # flagging it now rather than leaving it to stack_handler shutdown allows the
        # possibility of doing something about it.
        if trade_result["dealStatus"] != "ACCEPTED":
            reason = trade_result["reason"]
            self.log.warning("IG submitted order rejected reason %s" % reason)
            # order_with_controls = igOrderWithControls(
            #    control_object=trade_result, broker_order=broker_order
            # )
            # return order_with_controls
            return missing_order

        order_with_controls = igOrderWithControls(
            control_object=trade_result, broker_order=broker_order
        )
        return order_with_controls

    def submit_market_order(self, epic: str, expiry: str, size, direction: str) -> dict:

        trade_result = self.igconnection.rest_service.create_open_position(
            epic=epic,
            direction=direction,
            currency_code="GBP",
            order_type="MARKET",
            expiry=expiry,
            force_open=False,
            guaranteed_stop=False,
            size=size,
            level=None,
            limit_level=None,
            limit_distance=None,
            quote_id=None,
            stop_distance=None,
            stop_level=None,
            trailing_stop=False,
            trailing_stop_increment=None,
            session=None,
        )

        # self.log.debug(f"result of submit_market_order(): {trade_result}")

        return trade_result

    def submit_limit_order(
        self, epic: str, expiry: str, size, direction: str, limit: float
    ) -> dict:

        # Limit order expires after 15 minutes although algo should time it out in 600s
        good_till_date = get_good_till_date()

        trade_result = self.igconnection.rest_service.create_working_order(
            epic=epic,
            direction=direction,
            currency_code="GBP",
            order_type="LIMIT",
            expiry=expiry,
            force_open=False,
            guaranteed_stop=False,
            size=size,
            level=limit,
            limit_level=None,
            limit_distance=None,
            stop_distance=None,
            stop_level=None,
            session=None,
            time_in_force="GOOD_TILL_DATE",
            good_till_date=good_till_date,
        )

        if (
            trade_result["dealStatus"] == "REJECTED"
            and trade_result["reason"] == "ATTACHED_ORDER_LEVEL_ERROR"
        ):
            # Limit order was rejected because level was wrong i.e. price moved so that
            # the market price is more favourable than the requested limit price. Algos
            # that manage limit orders assume that one is in place for them to manage,
            # otherwise they flounder. Pre-empt this by using a market order instead,
            # which will be seen by algos as a limit order that executed immediately.
            # What about algoLimit which wants an unmanaged limit order? Rationalise
            # the same response, as the limit order rejection means that the market
            # is already at a better price than the requested limit price (when the
            # market price is worse, the limit order is accepted, to wait for better).
            self.log.warning(
                "Limit order rejected, market more favourable, switching to market order"
            )
            trade_result = self.submit_market_order(epic, expiry, size, direction)

        # self.log.debug(f"result of submit_limit_order(): {trade_result}")

        return trade_result

    def broker_amend_limit_order(self, broker_order, new_limit_price: float) -> dict:

        deal_id = broker_order.broker_permid

        trade_result = self.amend_limit_order(
            deal_id=deal_id,
            limit=new_limit_price,
        )

        return trade_result

    def amend_limit_order(self, deal_id: str, limit: float) -> dict:

        # Limit order expires after 15 minutes although algo should time it out in 600s
        good_till_date = get_good_till_date()

        amend_result = self.igconnection.rest_service.update_working_order(
            deal_id=deal_id,
            level=limit,
            order_type="LIMIT",
            limit_distance=None,
            limit_level=None,
            stop_distance=None,
            stop_level=None,
            guaranteed_stop=False,
            time_in_force="GOOD_TILL_DATE",
            good_till_date=good_till_date,
        )

        # self.log.debug(f"result of amend_limit_order(): {amend_result}")

        return amend_result

    def broker_cancel_order(self, broker_order) -> dict:
        # If we can't cancel (as if a working_order) with deal_id, return missing_order
        deal_id = broker_order.broker_permid
        try:
            cancel_result = self.cancel_order(deal_id)
            return cancel_result
        except:
            return missing_order

    def cancel_order(self, deal_id: str) -> dict:
        cancel_result = self.igconnection.rest_service.delete_working_order(deal_id)
        # self.log.debug(f"result of cancel_order(): {cancel_result}")
        return cancel_result


def get_good_till_date():
    good_till_date = dt.datetime.now() + dt.timedelta(minutes=15)
    good_till_date_str = good_till_date.strftime("%Y/%m/%d %H:%M:%S")
    return good_till_date_str
