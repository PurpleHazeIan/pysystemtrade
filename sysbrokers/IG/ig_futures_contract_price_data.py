"""
Read historical data from Norgate for individual futures contracts.
Read recent tick data from IG for individual futures contracts.

Requires 'norgatedata' module as well as a connection to IG

"""

from syscore.dateutils import Frequency, DAILY_PRICE_FREQ
from syscore.exceptions import missingData

from sysdata.data_blob import dataBlob

from sysbrokers.IG.ig_instruments_data import igFuturesInstrumentData
from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.IG.client.ig_client import igClient
from sysbrokers.IG.ng_futures_contract_price_data import ngFuturesContractPriceData

from sysexecution.tick_data import (
    tickerObject,
    dataFrameOfRecentTicks,
    TICK_REQUIRED_COLUMNS,
)
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.broker_orders import brokerOrder
from sysexecution.trade_qty import tradeQuantity

from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysobjects.contracts import futuresContract, listOfFuturesContracts

from syslogging.logger import *


class igFuturesContractPriceData(ngFuturesContractPriceData):
    """
    Class to read futures price data from Norgate data (https://norgatedata.com/) and
    access recent bid-ask tick data from IG supporting trading with IG as the broker

    """

    def __init__(
        self,
        ig_conn: connectionIG,
        data: dataBlob,
        log=get_logger("igFuturesContractPriceData"),
    ):
        super().__init__(log=log, data=data)
        self._ig_conn = ig_conn

    def __repr__(self):
        return "IG w/Norgate futures contract price data"

    @property
    def ig_conn(self) -> connectionIG:
        return self._ig_conn

    @property
    def ig_client(self) -> igClient:
        client = getattr(self, "_ig_client", None)
        if client is None:
            client = self._ig_client = igClient(igconnection=self.ig_conn, log=self.log)
        return client

    @property
    def futures_instrument_data(self) -> igFuturesInstrumentData:
        return self.data.broker_futures_instrument

    # Could inherit but this is a quicker and simpler way of getting this list
    def get_list_of_instrument_codes_with_merged_price_data(self) -> list:
        # return list of instruments for which pricing is configured
        list_of_instruments = self.futures_instrument_data.get_list_of_instruments()
        return list_of_instruments

    # Override inherited version which gets a list of all available contracts and
    # checks whether the desired one is present, a very time-consuming approach
    def has_merged_price_data_for_contract(
        self, futures_contract: futuresContract
    ) -> bool:
        fcp = self._get_prices_for_contract_object_no_checking(futures_contract)
        return len(fcp.index) != 0

    def contracts_with_merged_price_data_for_instrument_code(
        self, instrument_code: str, allow_expired=True
    ) -> listOfFuturesContracts:

        list_of_contracts = (
            self._get_norgate_contracts_with_merged_price_data_for_instrument_code(
                instrument_code=instrument_code,
                allow_expired=allow_expired,
            )
        )

        return list_of_contracts

    def get_contracts_with_merged_price_data(self) -> listOfFuturesContracts:
        """
        :return: list of contracts
        """
        list_of_contracts = listOfFuturesContracts()
        instruments = self.get_list_of_instrument_codes_with_merged_price_data()
        for instr in instruments:
            contracts = self.contracts_with_merged_price_data_for_instrument_code(instr)
            list_of_contracts += contracts

        return list_of_contracts

    # Override inherited version which gets a list of all available contracts and
    # checks whether the desired one is present, a very time-consuming approach
    def get_prices_at_frequency_for_contract_object(
        self,
        contract_object: futuresContract,
        frequency: Frequency = DAILY_PRICE_FREQ,
        return_empty: bool = True,
    ) -> futuresContractPrices:
        if frequency is not DAILY_PRICE_FREQ:
            self.log.warning(
                "Requesting non-existent data at frequency %s for %s"
                % (frequency, contract_object)
            )
            if return_empty:
                self.log.debug("Returning empty futuresContractPrices as requested")
                return futuresContractPrices.create_empty()
            else:
                raise NotImplementedError
        price_data = self._get_prices_at_frequency_for_contract_object_no_checking(
            contract_object=contract_object, frequency=frequency
        )
        return price_data

    def _get_prices_at_frequency_for_contract_object_no_checking(
        self, contract_object: futuresContract, frequency: Frequency
    ) -> futuresContractPrices:
        price_data = self._get_prices_at_frequency_for_contract_object_no_checking_with_expiry_flag(
            futures_contract_object=contract_object,
            frequency=frequency,
            allow_expired=False,
        )
        return price_data

    def get_prices_at_frequency_for_potentially_expired_contract_object(
        self,
        contract: futuresContract,
        freq: Frequency = DAILY_PRICE_FREQ,
        return_empty: bool = True,
    ) -> futuresContractPrices:
        if freq is not DAILY_PRICE_FREQ:
            self.log.warning(
                "Requesting non-existent data at frequency %s for %s" % (freq, contract)
            )
            if return_empty:
                self.log.debug("Returning empty futuresContractPrices as requested")
                return futuresContractPrices.create_empty()
            else:
                raise NotImplementedError
        price_data = self._get_prices_at_frequency_for_contract_object_no_checking_with_expiry_flag(
            futures_contract_object=contract,
            frequency=freq,
            allow_expired=True,
        )
        return price_data

    def _get_prices_at_frequency_for_contract_object_no_checking_with_expiry_flag(
        self,
        futures_contract_object: futuresContract,
        frequency: Frequency,
        allow_expired: bool = False,
    ) -> futuresContractPrices:
        """
        Get historical prices at a particular frequency

        We override this method, rather than _get_prices_at_frequency_for_contract_object_no_checking
        Because the list of dates returned by contracts_with_price_data is likely to not match (expiries)

        :param futures_contract_object:  futuresContract
        :return: data
        """

        price_data = self._get_norgate_prices_for_contract(futures_contract_object)
        return price_data

    def get_ticker_object_for_order(self, order: contractOrder) -> tickerObject:
        # self.log.debug("Call to create ticker_object for order")
        futures_contract = order.futures_contract
        trade_list = order.trade

        ticker = self.get_ticker_object_for_contract_and_trade_qty(
            futures_contract=futures_contract,
            trade_qty=trade_list,
        )

        return ticker

    def get_ticker_object_for_contract(
        self, futures_contract: futuresContract
    ) -> tickerObject:
        # self.log.debug("Call to create ticker_object for contract")
        return self.get_ticker_object_for_contract_and_trade_qty(
            futures_contract=futures_contract
        )

    def get_ticker_object_for_contract_and_trade_qty(
        self,
        futures_contract: futuresContract,
        trade_qty: tradeQuantity = None,
    ) -> tickerObject:

        ticker_object = self.ig_client.broker_get_ticker_object(
            futures_contract,
            trade_qty=trade_qty,
        )

        return ticker_object

    def cancel_market_data_for_contract(self, contract: futuresContract):
        self.ig_client.broker_cancel_market_data(contract_object=contract)
        return

    def cancel_market_data_for_order(self, order: brokerOrder):
        contract = order.futures_contract
        self.ig_client.broker_cancel_market_data(contract_object=contract)
        return
