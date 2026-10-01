import numpy as np
import time
import datetime as dt

from syscore.exceptions import missingData
from syscore.genutils import quickTimer
from sysobjects.contracts import futuresContract

from sysexecution.trade_qty import tradeQuantity
from sysexecution.tick_data import tickerObject, oneTick

from sysbrokers.IG.ig_positions import resolveBS_for_list, sign_from_BS


class igTickerObject(tickerObject):
    def __init__(self, ticker, direction: str, subkey):

        # qty can just be +1 or -1 size of trade doesn't matter to ticker
        qty = sign_from_BS(direction)
        super().__init__(ticker, qty=qty)

        self._subkey = subkey

    def wait_for_valid_bid_and_ask_and_return_current_tick(
        self, wait_time_seconds: int = 10
    ) -> oneTick:

        if self.ticker == []:
            raise missingData

        waiting = True
        timer = quickTimer(wait_time_seconds)
        while waiting:
            if timer.finished:
                raise missingData
            self.refresh()
            last_bid = self.bid()
            last_ask = self.ask()
            last_bid_is_valid = not np.isnan(last_bid)
            last_ask_is_valid = not np.isnan(last_ask)

            if last_bid_is_valid and last_ask_is_valid:
                break

        tick = oneTick(
            bid_price=last_bid,
            ask_price=last_ask,
            bid_size=self.bid_size(),
            ask_size=self.ask_size(),
        )
        self.add_tick(tick)

        return tick

    def refresh(self):
        # IG pushes updates to ticker, but pause briefly instead of pass
        time.sleep(0.01)

    def bid(self):
        return self.ticker.bid

    def ask(self):
        return self.ticker.offer

    def bid_size(self):
        # bid and ask sizes have no meaning so just return sufficient and balanced
        return 999

    def ask_size(self):
        # bid and ask sizes have no meaning so just return sufficient and balanced
        return 999


class igClientForPrices:
    """
    This class is for getting IG price information about an instrument or contract.
    Don't invoke directly, use only through inheritance as part of igClient.

    """

    def broker_get_ticker_object(
        self, contract_object: futuresContract, trade_qty: tradeQuantity = None
    ) -> igTickerObject:

        try:
            market = self.get_unique_market_for_contract(contract_object)
        except missingData:
            self.log.warning(
                f"Unable to create ticker object for contract {contract_object}"
            )
            empty_ticker = igTickerObject([], "BUY", None)
            return empty_ticker

        epic = market["epic"]
        try:
            ticker_object = self.get_ticker_object(epic, trade_qty)
        except missingData:
            empty_ticker = igTickerObject([], "BUY", None)
            return empty_ticker

        return ticker_object

    # Subscribe for tick streaming, leaves subscription open unless an error occurs
    def get_ticker_object(
        self, epic: str, trade_qty: tradeQuantity = None
    ) -> igTickerObject:

        self.log.debug(f"Starting ticker for {epic}")

        subkey = self.igconnection.streamer.start_tick_subscription(epic)
        try:
            ticker = self.igconnection.streamer.ticker(epic)
        except Exception as exc:
            self.log.error(f"Unable to start ticker for {epic}: {exc}")
            self.igconnection.streamer.stop_tick_subscription(epic)
            raise missingData

        if trade_qty is None:
            direction = "BUY"
        else:
            direction, _ = resolveBS_for_list(trade_qty)

        ticker_object = igTickerObject(ticker, direction, subkey)
        return ticker_object

    def broker_cancel_market_data(self, contract_object: futuresContract):

        try:
            market = self.get_unique_market_for_contract(contract_object)
        except missingData:
            # self.log.warning(
            #    "Unable to cancel ticker for contract %s" % contract_object
            # )
            return

        epic = market["epic"]
        # self.log.debug("Cancelling ticker for epic %s" % epic)
        self.cancel_market_data(epic)

    def cancel_market_data(self, epic: str):
        # if a second subscription to an epic is opened and closed within the
        # lifetime of a first subscription, the second subscription reuses the first,
        # and closing it would cause an error when the first tries to close it later.
        # I may do this when getting a price to autofill an order. It might be more
        # elegant, but would be harder, to manage a list of subscription counts.
        try:
            self.igconnection.streamer.stop_tick_subscription(epic)
        except:
            pass

    # Not called in production, only for a supporting report
    def broker_get_expiry_details(self, epic: str):
        expiry_key, last_dealing_date = self.get_expiry_details(epic)
        return expiry_key, last_dealing_date

    def get_expiry_details(self, epic: str):
        """
        Get the expiry key and actual expiry date (IG last dealing date) for a given epic
        :param epic:
        :return: str, str
        """

        if epic is not None:
            try:
                info = self.igconnection.rest_service.fetch_market_by_epic(epic)
                expiry_key = info["instrument"]["expiry"]
                last_dd = info["instrument"]["expiryDetails"]["lastDealingDate"]
                last_dd = dt.datetime.strptime(last_dd, "%Y-%m-%dT%H:%M")
                last_dd = last_dd.strftime("%Y-%m-%d %H:%M:%S")
                return expiry_key, last_dd
            except Exception as exc:
                self.log.error(f"Problem getting expiry date for '{epic}': {exc}")
                raise missingData
        else:
            raise missingData
