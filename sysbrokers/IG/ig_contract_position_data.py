import datetime

from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.IG.client.ig_client import igClient
from sysbrokers.IG.ig_positions import resolve_ig_positions
from sysbrokers.IG.ig_instruments_data import igFuturesInstrumentData
from sysbrokers.IG.ig_futures_contract_data import igFuturesContractData

from sysbrokers.broker_contract_position_data import brokerContractPositionData
from syscore.exceptions import missingContract
from syscore.constants import arg_not_supplied
from sysobjects.production.positions import contractPosition, listOfContractPositions
from sysobjects.contract_dates_and_expiries import EXPIRY_DATE_FORMAT
from sysobjects.contracts import futuresContract
from sysdata.data_blob import dataBlob

from syslogging.logger import *


class igContractPositionData(brokerContractPositionData):
    def __init__(
        self,
        ig_conn: connectionIG,
        data: dataBlob,
        log=get_logger("igContractPositionData"),
    ):
        super().__init__(log=log, data=data)
        self._ig_conn = ig_conn

    def __repr__(self):
        return "IG per contract position data"

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
    def futures_contract_data(self) -> igFuturesContractData:
        return self.data.broker_futures_contract

    @property
    def futures_instrument_data(self) -> igFuturesInstrumentData:
        return self.data.broker_futures_instrument

    def get_all_current_positions_as_list_with_contract_objects(
        self, account_id=arg_not_supplied
    ) -> listOfContractPositions:
        all_positions = self._get_all_futures_positions_as_raw_list(
            account_id=account_id
        )
        current_positions = []
        for position_entry in all_positions:
            try:
                contract_position_object = self._get_contract_position_for_raw_entry(
                    position_entry
                )
            except missingContract:
                continue
            else:
                current_positions.append(contract_position_object)

        list_of_contract_positions = listOfContractPositions(current_positions)

        list_of_contract_positions_no_duplicates = (
            list_of_contract_positions.sum_for_contract()
        )

        return list_of_contract_positions_no_duplicates

    def _get_contract_position_for_raw_entry(self, position_entry) -> contractPosition:
        position = position_entry["size"]
        if position_entry["direction"] == "SELL":
            position = position * -1
        if position == 0:
            raise missingContract

        expiry_key = position_entry["expiry"]
        if expiry_key == "DFB":
            raise missingContract

        epic = position_entry["symbol"]
        instrument_code = (
            self.futures_instrument_data.get_instrument_code_from_broker_code(epic)
        )
        if instrument_code is None:
            raise missingContract

        expiry_as_dt = datetime.datetime.strptime(f"01-{expiry_key}", "%d-%b-%y")
        expiry_as_str = f"{expiry_as_dt.strftime('%Y%m')}00"
        temp_contract = futuresContract(instrument_code, expiry_as_str)
        expiry = self.futures_contract_data.get_actual_expiry_date_for_single_contract(
            temp_contract
        )
        expiry_as_str = expiry.strftime(EXPIRY_DATE_FORMAT)

        contract = futuresContract(instrument_code, expiry_as_str)
        contract_position_object = contractPosition(position, contract)

        return contract_position_object

    def _get_all_futures_positions_as_raw_list(
        self, account_id: str = arg_not_supplied
    ) -> list:
        raw_positions = self.ig_client.broker_get_positions()
        positions = resolve_ig_positions(raw_positions)

        return positions

    def get_position_as_df_for_contract_object(self, *args, **kwargs):
        raise Exception("Only current position data available from IG")

    def update_position_for_contract_object(self, *args, **kwargs):
        raise Exception("IG position data is read only")

    def delete_last_position_for_contract_object(self, *args, **kwargs):
        raise Exception("IG position data is read only")

    def _get_series_for_args_dict(self, *args, **kwargs):
        raise Exception("Only current position data available from IG")

    def _update_entry_for_args_dict(self, *args, **kwargs):
        raise Exception("IG position data is read only")

    def _delete_last_entry_for_args_dict(self, *args, **kwargs):
        raise Exception("IG position data is read only")

    def _get_list_of_args_dict(self) -> list:
        raise Exception("Args dict not used for IG")

    def get_list_of_instruments_with_any_position(self):
        raise Exception("Not implemented for IG")
