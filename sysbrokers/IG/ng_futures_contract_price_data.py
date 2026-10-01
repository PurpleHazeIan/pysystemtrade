"""
Read prices data FOR individual futures contracts from Norgate

Requires 'norgatedata' module, see https://pypi.org/project/norgatedata/

"""

import datetime
import norgatedata
import numpy as np

from sysbrokers.broker_futures_contract_price_data import brokerFuturesContractPriceData

from syscore.exceptions import missingInstrument
from syscore.dateutils import month_from_contract_letter
from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysobjects.contracts import futuresContract, listOfFuturesContracts
from sysobjects.contract_dates_and_expiries import YEAR_SLICE

INCLUDE_OPEN_INTEREST = False


class ngFuturesContractPriceData(brokerFuturesContractPriceData):
    """
    Class to read futures price data from Norgate data (https://norgatedata.com/)

    """

    def _get_norgate_prices_for_contract(
        self, contract_object: futuresContract
    ) -> futuresContractPrices:

        instrument_code = contract_object.instrument_code
        timeseriesformat = "pandas-dataframe"
        ng_code = self.futures_instrument_data.get_ng_id(instrument_code)
        if ng_code is None:
            self.log.warning(
                "Can't find instrument %s from Norgate database!" % instrument_code
            )
            raise missingInstrument

        contract = (
            ng_code
            + "-"
            + contract_object.contract_date.date_str[YEAR_SLICE]
            + contract_object.contract_date.letter_month()
        )

        try:
            df = norgatedata.price_timeseries(
                symbol=contract, timeseriesformat=timeseriesformat
            )
        except:
            fcp = futuresContractPrices.create_empty()
            return fcp

        if len(df.index) == 0:
            fcp = futuresContractPrices.create_empty()
            return fcp

        df.rename(
            columns={
                "Open": "OPEN",
                "High": "HIGH",
                "Low": "LOW",
                "Close": "FINAL",
                "Volume": "VOLUME",
            },
            errors="raise",
            inplace=True,
        )
        if INCLUDE_OPEN_INTEREST:
            df.rename(
                columns={"Open Interest": "OPEN_INTEREST"}, errors="raise", inplace=True
            )
        else:
            df.drop(["Open Interest"], axis=1, errors="raise", inplace=True)

        # Invert pricing if needed
        invert_first = self.futures_instrument_data.get_invert_first(instrument_code)
        if invert_first:
            for col in ["OPEN", "HIGH", "LOW", "FINAL"]:
                df[col] = 1.0 / df[col]

        # Do unit conversion if needed
        mult = self.futures_instrument_data.get_unit_multiplier(instrument_code)
        if mult != 1:
            for col in ["OPEN", "HIGH", "LOW", "FINAL"]:
                df[col] = df[col] * mult

        # Append date with time used as end of day (23:00:00)
        p_datetime = df.index.values.copy()
        p_datetime = p_datetime + np.timedelta64(23, "h")
        df.index = p_datetime

        fcp = futuresContractPrices(df)

        return fcp

    def _get_norgate_contracts_with_merged_price_data_for_instrument_code(
        self, instrument_code: str, allow_expired=True
    ) -> listOfFuturesContracts:
        """
        Get all contracts that have price data for given instrument

        :param instrument_code: Instrument code
        :param allow_expired: bool Allow contracts that have passed expiry
            (approximated contract date)
        :return: listOfFuturesContracts
        """
        symbol = self.futures_instrument_data.get_ng_id(instrument_code)
        if symbol is None:
            return listOfFuturesContracts([])

        contract_list = norgatedata.futures_market_session_contracts(symbol)
        first_contract_to_use = self.futures_instrument_data.get_first_contract_to_use(
            instrument_code
        )
        revised_contract_list = []
        for contract in contract_list:
            if contract >= first_contract_to_use:
                revised_contract_list.append(contract)

        list_of_contracts = []

        for contract in revised_contract_list:
            symbol = contract.split("-")[0]
            timecode = contract.split("-")[1]
            year = int(timecode[0:-1])
            monthcode = timecode[-1]
            month = month_from_contract_letter(monthcode)
            contract_date = "%04d%02d%02d" % (year, month, 0)

            fc = futuresContract(instrument_code, contract_date)

            if allow_expired:
                list_of_contracts.append(fc)
            else:
                # we don't actually know if the contract is expired, but we
                # can try to guess this from the contract date
                e_date = fc.expiry_date  # derived automatically from contract date
                if e_date + datetime.timedelta(days=31) > datetime.datetime.now():
                    list_of_contracts.append(fc)

        return listOfFuturesContracts(list_of_contracts)
