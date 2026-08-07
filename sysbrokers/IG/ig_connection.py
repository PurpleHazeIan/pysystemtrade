"""
A connection to IG as a broker is supported by entries in private_config.yaml and
ig_connection_config.py, both in the private directory

Add the following to private_config.yaml for each computer+user in use ...
COMPUTER_NAME\\user_name:
   live_account: True|False # True: use configLive, False: use ConfigDemo
   place_trades: True|False # True: place trades, False: autofill then trade manually
   model_capital: -1 # if positive, use value in place of broker capital for testing
   boost_capital: 14000 # add this amount of unused margin parked elsewhere
[I use this to support production and test instances]

NB 'autofill' means that the trade is not placed but is filled as if successful

Add the following to ig_connection_config.py for configLive and likewise for configDemo ...
def configLive():
    config = {
        "ig_username": "xxx",
        "ig_password": "xxx",
        "ig_api_key": "xxx",
        "ig_acc_type": "LIVE",  # LIVE / DEMO
        "ig_acc_number": "xxx",
    }
    return config
[These are fixed details for Live and Demo accounts, chosen for each computer+user
setup by private_config.yaml. Done this way to avoid seeing account details in the
saved configs of production runs.]

Requires tenacity and trading_ig to be installed

"""

import os

from tenacity import Retrying, wait_exponential, retry_if_exception_type
from trading_ig.rest import IGService, ApiExceededException, TokenInvalidException
from trading_ig.stream import IGStreamService
from trading_ig.streamer.manager import StreamingManager

from syscore.constants import arg_not_supplied
from sysdata.config.production_config import get_production_config

from private.ig_connection_config import configDemo, configLive

from syslogging.logger import *

RETRYABLE = (ApiExceededException, TokenInvalidException)


class connectionIG(object):

    def __init__(
        self,
        log=get_logger("IG connection"),
        force_demo: bool = False,
    ):

        self._log = log

        self._host_based_config = get_host_based_config()

        if self.is_configured_as_live and not force_demo:
            ig_config = configLive()
        else:
            ig_config = configDemo()

        try:
            self._init_connection(ig_config)
        except Exception as e:
            # Log all exceptions generated during connection as critical error.
            # Error is reraised as we can't really continue without user intervention.
            self.log.critical(f"Failed with exception - {e}")
            raise

        self.log.info(
            f"Configured as '{self.account_type}' using account '{self.account_number}'"
        )
        self.log.info(f"Original config {self.host_based_config}")

    @property
    def log(self):
        return self._log

    def __repr__(self):
        return "IG broker connection" + str(self.host_based_config)

    @property
    def host_based_config(self):
        return self._host_based_config

    def _init_connection(self, ig_config):
        retryer = Retrying(
            wait=wait_exponential(), retry=retry_if_exception_type(RETRYABLE)
        )
        rest_service = IGService(
            ig_config["ig_username"],
            ig_config["ig_password"],
            ig_config["ig_api_key"],
            acc_type=ig_config["ig_acc_type"],
            acc_number=ig_config["ig_acc_number"],
            retryer=retryer,
        )

        rest_service.create_session(version="2")
        self._rest_service = rest_service

        stream_service = IGStreamService(self.rest_service)
        stream_service.create_session(version="2")
        self._stream_service = stream_service

        self._streamer = StreamingManager(self.stream_service)

        self._account_number = ig_config["ig_acc_number"]
        self._account_type = ig_config["ig_acc_type"]

    @property
    def rest_service(self):
        return self._rest_service

    @property
    def stream_service(self):
        return self._stream_service

    @property
    def streamer(self):
        return self._streamer

    def close_connection(self):

        self.log.debug("Stopping all IG streamers")
        self.streamer.stop_subscriptions()

        self.log.debug("Logging out of IG Stream service")
        self.stream_service.disconnect()

        self.log.debug("Logging out of IG REST service")
        self.rest_service.logout()

    @property
    def is_configured_as_live(self):
        return self.host_based_config.get("live_account", False)

    @property
    def place_trades(self):
        return self.host_based_config.get("place_trades", False)

    @property
    def model_capital(self):
        return self.host_based_config.get("model_capital", -1)

    @property
    def boost_capital(self):
        return self.host_based_config.get("boost_capital", 0)

    @property
    def account_number(self):
        return self._account_number

    @property
    def account_type(self):
        return self._account_type

    def client_id(self):
        pass


def get_host_based_config():
    try:
        config = get_production_config()
        host = "\\".join([os.getenv("COMPUTERNAME"), os.getenv("USERNAME")])
        host_based_config = config.get_element_or_arg_not_supplied(host)
    except:
        host_based_config = arg_not_supplied

    if host_based_config is arg_not_supplied:
        host_based_config = dict()

    return host_based_config
