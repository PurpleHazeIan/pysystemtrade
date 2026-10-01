import datetime

from syscore.constants import arg_not_supplied
from sysobjects.spot_fx_prices import currencyValue, listOfCurrencyValues


class igClientForAccounts:
    """
    This class is for getting IG account info.
    Don't invoke directly, use only through inheritance as part of igClient.

    """

    def broker_get_time_local_tz(self):
        return datetime.datetime.now()

    def broker_get_account_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        list_of_values_per_currency = list(
            [
                currencyValue(currency, self.get_capital(account_id))
                for currency in ["GBP"]
            ]
        )
        list_of_values_per_currency = listOfCurrencyValues(list_of_values_per_currency)
        return list_of_values_per_currency

    def broker_get_excess_liquidity_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        list_of_values_per_currency = list(
            [
                currencyValue(currency, self.get_margin(account_id))
                for currency in ["GBP"]
            ]
        )
        list_of_values_per_currency = listOfCurrencyValues(list_of_values_per_currency)
        return list_of_values_per_currency

    def broker_fx_balances(self, account_id: str = arg_not_supplied) -> dict:
        return dict()

    def get_capital(self, account: str = arg_not_supplied):

        model_capital = self.igconnection.model_capital
        if model_capital > 0:
            return model_capital

        data = self.igconnection.rest_service.fetch_accounts()

        if account is arg_not_supplied:
            account = self.igconnection.account_number
        self.log.debug(f"\n{data.T}")
        data = data.loc[data["accountId"] == account]

        balance = data.iloc[0]["balance"]
        profit_loss = data.iloc[0]["profitLoss"]
        capital = balance + profit_loss

        boost_capital = self.igconnection.boost_capital
        self.log.debug(f"Adding to capital boost_capital of: {boost_capital}")

        return capital + boost_capital

    def get_margin(self, account: str = arg_not_supplied):

        model_capital = self.igconnection.model_capital
        if model_capital > 0:
            return model_capital * 0.5

        data = self.igconnection.rest_service.fetch_accounts()

        if account is arg_not_supplied:
            account = self.igconnection.account_number
        data = data.loc[data["accountId"] == account]

        free_margin = data.iloc[0]["available"]

        boost_capital = self.igconnection.boost_capital
        self.log.debug(f"Adding to margin boost_capital of: {boost_capital}")

        return free_margin + boost_capital
