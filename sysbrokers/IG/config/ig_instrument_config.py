import pandas as pd

from syscore.exceptions import missingFile
from syscore.fileutils import resolve_path_and_filename_for_package

from syslogging.logger import *


class igInstrumentConfig(pd.DataFrame):
    pass


IG_INSTRUMENT_CONFIG_FILE = resolve_path_and_filename_for_package(
    "sysbrokers.IG.config.ig_instrument_config.csv"
)


def read_ig_instrument_config_from_file(
    log=get_logger("IG instrument config"),
) -> igInstrumentConfig:
    try:
        df = pd.read_csv(IG_INSTRUMENT_CONFIG_FILE)
    except Exception as e:
        log.warning("Can't read file %s" % IG_INSTRUMENT_CONFIG_FILE)
        raise missingFile from e

    return igInstrumentConfig(df)
