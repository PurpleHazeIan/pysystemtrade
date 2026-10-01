"""
Norgate instrument database. This contains mapping of Norgate instrument ID ->
instrument code, as well as other metadata of each instrument.

"""

from numpy import NaN
import pandas as pd

from sysdata.csv.csv_futures_contract_prices import ConfigCsvFuturesPrices
from sysbrokers.broker_instrument_data import brokerFuturesInstrumentData

NG_ID_COLUMN = "NorgateInstrument"
ID_COLUMN = "Instrument"
EXCH_COL = "Exchange"
CURRENCY_COL = "Currency"
DESC_COL = "Name"
POINTVALUE_COL = "PointValue"
UNIT_MULTIPLIER_COL = "UnitMultiplier"
INVERT_FIRST_COL = "InvertFirst"
FIRST_CONTRACT_COL = "FirstContract"


def csv_config_factory():
    """
    CSV config factory for parametric CSV database. This can be used with
    csvFuturesContractPriceData to load prices from CSV files saved by
    Norgate Date Updater (via its Export Task Manager) as an alternative to
    pulling data directly from the norgate database with norgatedata module

    """

    db = ngFuturesInstrumentData()

    csv_config = ConfigCsvFuturesPrices()
    csv_config.input_filename_format = "%{BS}-%{YEAR}%{LETTER}.csv"
    csv_config.input_date_format = "%Y%m%d"
    input_column_mapping = dict(
        OPEN="Open", HIGH="High", LOW="Low", FINAL="Close", VOLUME="Volume"
    )
    csv_config.input_date_index_name = "Date"
    csv_config.input_column_mapping = input_column_mapping
    csv_config.broker_symbols = db.get_id_map()
    csv_config.instrument_price_multiplier = db.get_unit_multipliers()
    return csv_config


class ngFuturesInstrumentData(brokerFuturesInstrumentData):

    def get_ng_id(self, instrument: str):
        """
        Gets Norgate instrument symbol
        :param instrument: str instrument code
        :return: Norgate instrument symbol or None

        """

        res = self.config[self.config[ID_COLUMN] == instrument]
        if len(res) == 0:
            return None
        return res.iloc[-1].at[NG_ID_COLUMN]

    def get_ng_instrument_metadata(self, instrument: str) -> pd.Series:
        """
        Gets metadata for Norgate instrument (Pandas series)
        :param instrument: str instrument code
        :return: metadata as Pandas series or None
        """
        ng_id = self.get_ng_id(instrument)
        if ng_id is None:
            return None

        res = self.config[self.config[NG_ID_COLUMN] == ng_id]
        if len(res) == 0:
            return None
        return res.iloc[-1]

    def get_instrument(self, ng_id: str):
        """
        Gets instrument code by Norgate instrument symbol
        :param ng_id: str Norgate instrument symbol
        :return: instrument code or None
        """
        res = self.config[self.config[NG_ID_COLUMN] == ng_id]
        if len(res) == 0:
            return None
        if res.iloc[-1].at[ID_COLUMN] is NaN:
            return None
        return res.iloc[-1].at[ID_COLUMN]

    def get_list_of_instruments(self) -> list:
        """
        Get instruments that should have price data
        Pulls these in from a config file

        :return: list of str
        """
        res = self.config[ID_COLUMN]
        # remove NaN rows
        res = res[res == res]
        instrument_list = list(res)
        return instrument_list

    def get_unit_multiplier(self, instrument: str):
        """
        Gets multiplier that is used to process price data from Norgate
        to match the price level that prices from Interactive Brokers have
        :param instrument: str instrument code
        :return: unit multiplier or 1.0 if not found
        """
        res = self.config[self.config[ID_COLUMN] == instrument]
        if len(res) == 0:
            return 1.0
        return res.iloc[-1].at[UNIT_MULTIPLIER_COL]

    def get_unit_multipliers(self):
        """
        Gets dict of unit multipliers, one for each instrument code. Multipliers are used to process
        price data from Norgate to match the price level that prices from Interactive Brokers have
        :return: dict of unit multipliers
        """
        m = dict()
        ids = self.config[self.config[NG_ID_COLUMN] == self.config[NG_ID_COLUMN]]
        ids = ids[ids[ID_COLUMN] == ids[ID_COLUMN]]
        for index, row in ids.iterrows():
            multiplier = row[UNIT_MULTIPLIER_COL]
            id = row[ID_COLUMN]
            m[id] = multiplier
        return m

    def get_invert_first(self, instrument: str):
        """
        Gets flag whether price should be inverted between Norgate and IG
        :param instrument: str instrument code
        :return: True/False default False
        """
        res = self.config[self.config[ID_COLUMN] == instrument]
        if len(res) == 0:
            return False
        return res.iloc[-1].at[INVERT_FIRST_COL]

    def get_first_contract_to_use(self, instrument: str):
        """
        Gets first_contract_to_use, default 1901F, as occasionally we have problems
        creating the roll calendar when there are gaps early on
        :param instrument: str instrument code
        :return: first contract to use as string
        """
        res = self.config[self.config[ID_COLUMN] == instrument]
        if len(res) == 0:
            return None
        ng_id = res.iloc[-1].at[NG_ID_COLUMN]
        if res.iloc[-1].at[FIRST_CONTRACT_COL] is NaN:
            return ng_id + "-1901F"
        return res.iloc[-1].at[FIRST_CONTRACT_COL]

    def get_id_map(self) -> dict:
        """
        Get all id / instrument code pairs as dict
        """
        m = dict()
        ids = self.config[self.config[NG_ID_COLUMN] == self.config[NG_ID_COLUMN]]
        ids = ids[ids[ID_COLUMN] == ids[ID_COLUMN]]
        for index, row in ids.iterrows():
            csi_id = row[NG_ID_COLUMN]
            id = row[ID_COLUMN]
            m[id] = csi_id
        return m
