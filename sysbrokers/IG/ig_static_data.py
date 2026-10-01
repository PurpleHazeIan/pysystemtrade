from sysbrokers.IG.ig_connection import connectionIG
from sysbrokers.broker_static_data import brokerStaticData
from sysdata.data_blob import dataBlob

from syslogging.logger import *


class igStaticData(brokerStaticData):
    def __init__(
        self,
        ig_conn: connectionIG,
        data: dataBlob,
        log=get_logger("igStaticData"),
    ):
        super().__init__(log=log, data=data)
        self._ig_conn = ig_conn

    def __repr__(self):
        return "IG static data"

    @property
    def ig_conn(self) -> connectionIG:
        return self._ig_conn

    def get_broker_account(self) -> str:
        return self.ig_conn.account_number

    def get_broker_name(self) -> str:
        return "IG"

    def get_broker_clientid(self) -> int:
        pass
