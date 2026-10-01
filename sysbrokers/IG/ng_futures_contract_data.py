"""
Read data ABOUT individual futures contracts (not the prices data itself) from Norgate

Requires 'norgatedata' module, see https://pypi.org/project/norgatedata/

"""

import norgatedata

from sysbrokers.broker_futures_contract_data import brokerFuturesContractData

from syscore.exceptions import missingInstrument
from sysobjects.contract_dates_and_expiries import (
    expiryDate,
    EXPIRY_DATE_FORMAT,
    NO_EXPIRY_DATE_PASSED,
    YEAR_SLICE,
)
from sysobjects.contracts import futuresContract


class ngFuturesContractData(brokerFuturesContractData):
    """
    Class to read data about contracts from Norgate data (https://norgatedata.com/)

    """

    def _get_actual_expiry_date_for_single_contract_from_norgate(
        self, contract_object: futuresContract
    ) -> expiryDate:

        ng_code = self.futures_instrument_data.get_ng_id(
            contract_object.instrument_code
        )
        if ng_code is None:
            self.log.warning(
                "Can't find instrument %s from Norgate database!"
                % contract_object.instrument_code
            )
            raise missingInstrument

        contract = (
            ng_code
            + "-"
            + contract_object.contract_date.date_str[YEAR_SLICE]
            + contract_object.contract_date.letter_month()
        )

        try:
            expiry_date = norgatedata.last_quoted_date(
                symbol=contract, datetimeformat="datetime"
            )
            datestring = expiry_date.strftime(EXPIRY_DATE_FORMAT)
            expiry_date = expiryDate.from_str(datestring)
            return expiry_date

        except:
            self.log.warning(
                f"Can't get expiry for {contract_object}, returning NO_EXPIRY_DATE_PASSED"
            )
            return NO_EXPIRY_DATE_PASSED
