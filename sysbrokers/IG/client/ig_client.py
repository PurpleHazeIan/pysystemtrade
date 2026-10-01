from sysproduction.reporting.reporting_functions import pandas_display_for_reports

from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.IG.config.ig_instrument_config import (
    igInstrumentConfig,
    read_ig_instrument_config_from_file,
)

from sysbrokers.IG.client.ig_client_for_accounts import igClientForAccounts
from sysbrokers.IG.client.ig_client_for_markets import igClientForMarkets
from sysbrokers.IG.client.ig_client_for_orders import igClientForOrders
from sysbrokers.IG.client.ig_client_for_positions import igClientForPositions
from sysbrokers.IG.client.ig_client_for_prices import igClientForPrices

from syslogging.logger import *

pandas_display_for_reports()


class igClient(
    igClientForAccounts,
    igClientForMarkets,
    igClientForOrders,
    igClientForPositions,
    igClientForPrices,
):
    """
    igClientForAccounts -  for IG account info.
    igClientForMarkets -   for IG market info about an instrument or contract.
    igClientForOrders -    to submit or cancel an order at IG.
    igClientForPositions - for info about positions, activity, transactions, working orders
    igClientForPrices -    for IG price information about an instrument or contract

    """

    def __init__(self, igconnection: connectionIG, log=get_logger("igClient")):

        self._log = log
        self._ig_connection = igconnection
        self._ig_instrument_config = read_ig_instrument_config_from_file()

    def __repr__(self):
        return "IG client wrapping IG connection {self.igconnection}"

    @property
    def igconnection(self):
        return self._ig_connection

    @property
    def ig_instrument_config(self) -> igInstrumentConfig:
        return self._ig_instrument_config

    @property
    def log(self):
        return self._log
