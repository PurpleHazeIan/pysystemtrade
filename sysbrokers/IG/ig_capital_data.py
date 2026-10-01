from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.IG.client.ig_client import igClient
from sysbrokers.broker_capital_data import brokerCapitalData
from sysdata.data_blob import dataBlob
from syscore.constants import arg_not_supplied

from sysobjects.spot_fx_prices import listOfCurrencyValues

from syslogging.logger import *


class igCapitalData(brokerCapitalData):
    def __init__(
        self,
        ig_conn: connectionIG,
        data: dataBlob,
        log=get_logger("igCapitalData"),
    ):
        super().__init__(log=log, data=data)
        self._ig_conn = ig_conn

    @property
    def ig_conn(self) -> connectionIG:
        return self._ig_conn

    @property
    def ig_client(self) -> igClient:
        client = getattr(self, "_ig_client", None)
        if client is None:
            client = self._ig_client = igClient(igconnection=self.ig_conn, log=self.log)
        return client

    def __repr__(self):
        return "IG capital data"

    def get_account_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        list_of_values_per_currency = (
            self.ig_client.broker_get_account_value_across_currency(
                account_id=account_id
            )
        )

        list_of_values_per_currency = listOfCurrencyValues(list_of_values_per_currency)
        return list_of_values_per_currency

    def get_excess_liquidity_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        list_of_values_per_currency = (
            self.ig_client.broker_get_excess_liquidity_value_across_currency(
                account_id=account_id
            )
        )

        list_of_values_per_currency = listOfCurrencyValues(list_of_values_per_currency)
        return list_of_values_per_currency

    """
    Can add other functions not in parent class to get IB specific stuff which could be required for
      strategy decomposition
    """
