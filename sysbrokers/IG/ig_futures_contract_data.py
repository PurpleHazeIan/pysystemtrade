"""
Read data ABOUT individual futures contracts (not the prices data itself)

Requires 'norgatedata' module as well as a connection to IG

"""

from sysbrokers.IG.ig_instruments_data import igFuturesInstrumentData
from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.IG.ng_futures_contract_data import ngFuturesContractData
from sysbrokers.IG.ig_trading_hours import get_saved_trading_hours, parse_trading_hours

from syscore.exceptions import missingContract
from sysdata.data_blob import dataBlob
from sysobjects.contract_dates_and_expiries import expiryDate
from sysobjects.contracts import futuresContract
from sysobjects.production.trading_hours.trading_hours import listOfTradingHours

from syslogging.logger import *


class igFuturesContractData(ngFuturesContractData):
    def __init__(
        self,
        ig_conn: connectionIG,
        data: dataBlob,
        log=get_logger("igFuturesContractData"),
    ):
        super().__init__(log=log, data=data)
        self._ig_conn = ig_conn

    def __repr__(self):
        return "IG w/Norgate futures contract data"

    @property
    def ig_conn(self) -> connectionIG:
        return self._ig_conn

    @property
    def futures_instrument_data(self) -> igFuturesInstrumentData:
        return self.data.broker_futures_instrument

    def get_actual_expiry_date_for_single_contract(
        self, futures_contract: futuresContract
    ) -> expiryDate:
        """
        Get the actual expiry date of a contract
        From Norgate not IG as they have the more complete set of contracts,
        and historic data is available, not just the subset currently trading on IG

        :param futures_contract: type futuresContract
        :return: expiryDate i.e. datetime.datetime, or NO_EXPIRY_DATE_PASSED i.e. ""
        """
        if futures_contract.is_spread_contract():
            self.log.warning(
                "Can't find expiry for multiple leg contract here",
                **futures_contract.log_attributes(),
                method="temp",
            )
            raise missingContract
        expiry_date = self._get_actual_expiry_date_for_single_contract_from_norgate(
            contract_object=futures_contract
        )
        return expiry_date

    def get_min_tick_size_for_contract(self, contract_object: futuresContract) -> float:
        return 0.01

    # Re checking of trading hours. IG market orders are only accepted when the market is
    # open, so it's just as easy to try and see the response. Likewise, limit orders can
    # only be placed when they can be placed, else they are rejected. We learn what we
    # need from placing the order and handling the response. This is partly driven
    # by just running stack_handler once per day; orders that are turned back would be
    # generated again on the morrow, if still required.
    # I also note that preprocessing in create_broker_orders_from_contract_orders() in
    # stack_handler returns missing_order if contract is not OK to trade, which is handled
    # much the same as an order rejected on submission, for an equivalent outcome.

    def get_trading_hours_for_contract(
        self, futures_contract: futuresContract
    ) -> listOfTradingHours:

        # NB brokerFuturesContractData can handle a missingContract exception from here

        # We could return something instrument-specific (either from a config or from
        # market info retrieved from IG), but we learn what we need from placing the
        # order and handling the response.

        # get_saved_trading_hours() reads a config. To set up the config file, see
        # sysbrokers.IG.ig_trading_hours.py and sysbrokers.IG.ig_config_trading_hours.yaml
        saved_trading_hours = get_saved_trading_hours()

        trading_hours_broker_default = {
            "marketTimes": [{"openTime": "23:00", "closeTime": "22:00"}]
        }
        trading_hours_saved_default = saved_trading_hours.get(
            "default", trading_hours_broker_default
        )
        instrument_code = futures_contract.instrument_code
        trading_hours_for_instrument = saved_trading_hours.get(
            instrument_code, trading_hours_saved_default
        )

        # It would be useful to query this data from IG, but market info just includes
        # { ..., "openingHours": null, ...}.
        # The settings below reflect that IG opens at 23:00 and closes for the day at
        # 22:00, for the most-favoured instruments. This is also the format returned by
        # get_saved_trading_hours(), and there can be multiple openTime/closeTime pairs.
        # trading_hours_broker_default = {
        #     "marketTimes": [{"openTime": "23:00", "closeTime": "22:00"}]
        # }
        trading_hours = parse_trading_hours(trading_hours_for_instrument)
        return trading_hours
