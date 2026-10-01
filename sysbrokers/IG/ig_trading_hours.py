import datetime
import pandas as pd
import yaml

from sysdata.config.private_config import (
    get_private_config_dir,
)
from sysobjects.production.trading_hours.trading_hours import (
    tradingHours,
    listOfTradingHours,
)
from syscore.fileutils import (
    does_resolved_filename_exist,
    resolve_path_and_filename_for_package,
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
IG_CONFIG_TRADING_HOURS_FILE = "sysbrokers.IG.ig_config_trading_hours.yaml"
PRIVATE_CONFIG_TRADING_HOURS_FILE = "private_config_trading_hours.yaml"

MARKET_HOURS_DAY_COUNT = 5


def get_saved_trading_hours():
    private_path = resolve_path_and_filename_for_package(
        get_private_config_dir(), PRIVATE_CONFIG_TRADING_HOURS_FILE
    )
    if does_resolved_filename_exist(private_path):
        return read_trading_hours(private_path)
    else:
        default_path = resolve_path_and_filename_for_package(
            IG_CONFIG_TRADING_HOURS_FILE
        )
        return read_trading_hours(default_path)


def read_trading_hours(filename: str):
    resolved_filename = resolve_path_and_filename_for_package(filename)

    try:
        with open(resolved_filename, "r") as file_to_parse:
            simple_dict = yaml.load(file_to_parse, Loader=yaml.Loader)
    except:
        print("File %s not found, no saved trading hours" % filename)
        simple_dict = {}

    return simple_dict


def parse_trading_hours(
    trading_hours: dict,
) -> listOfTradingHours:
    now = datetime.datetime.now()
    list_of_open_times = []

    date_range = pd.date_range(now, periods=MARKET_HOURS_DAY_COUNT, freq="B")
    for day in date_range:
        if trading_hours is None:
            list_of_open_times.append(build_hours_for_day(day, "00:00", "23:59"))
        else:
            for period in trading_hours["marketTimes"]:
                list_of_open_times.append(
                    build_hours_for_day(day, period["openTime"], period["closeTime"])
                )

    return listOfTradingHours(list_of_open_times)


def build_hours_for_day(dt: datetime, open: str, close: str):

    day = dt.strftime("%Y-%m-%d")

    dt_open = datetime.datetime.strptime(f"{day} {open}:00", DATE_FORMAT)
    dt_close = datetime.datetime.strptime(f"{day} {close}:00", DATE_FORMAT)

    if dt_close < dt_open:
        return tradingHours(dt_open - datetime.timedelta(days=1), dt_close)
    else:
        return tradingHours(dt_open, dt_close)
