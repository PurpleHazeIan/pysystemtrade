from sysbrokers.IG.ng_instruments_data import ngFuturesInstrumentData
from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.IG.client.ig_client import igClient
from sysbrokers.IG.config.ig_instrument_config import igInstrumentConfig

from sysdata.data_blob import dataBlob

from syslogging.logger import *


class igFuturesInstrumentData(ngFuturesInstrumentData):
    """
    IG Futures as Spread Bets instrument data

    """

    def __init__(
        self,
        ig_conn: connectionIG,
        data: dataBlob,
        log=get_logger("igFuturesInstrumentData"),
    ):
        super().__init__(log=log, data=data)
        self._ig_conn = ig_conn

    def __repr__(self):
        return "IG Futures as Spread Bets instrument data"

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
    def config(self) -> igInstrumentConfig:
        return self.ig_client.ig_instrument_config

    def get_broker_code_from_instrument_code(self, instrument_code: str) -> str:
        msg = "Instrument_code to broker_code is one:many so can't be handled"
        self.log.critical(msg)
        raise NotImplementedError

    def get_instrument_code_from_broker_code(self, broker_code: str) -> str:
        dot_pos = find_char_instances(broker_code, ".")
        code_base = broker_code[: dot_pos[2]]

        config_row = self.config[self.config.IGEpic == code_base]
        if len(config_row) == 0:
            msg = f"Broker symbol {broker_code} not found in configuration file!"
            self.log.warning(msg)
            return None

        if len(config_row) > 1:
            msg = f"Broker symbol {broker_code} duplicated in configuration file!"
            self.log.critical(msg)
            return None

        return config_row.iloc[0].Instrument

    def get_list_of_instruments(self) -> list:
        """
        Instruments that we can handle with this broker

        :return: list of str
        """
        instrument_list = list(self.config.Instrument)
        return instrument_list


def find_char_instances(search_str, ch):
    return [i for i, ltr in enumerate(search_str) if ltr == ch]
