import pandas as pd

from syscore.constants import arg_not_supplied
from syscore.exceptions import missingData, missingInstrument
from sysobjects.contracts import futuresContract


class igClientForMarkets:
    """
    This class is for getting IG market info about an instrument or contract.
    Don't invoke directly, use only through inheritance as part of igClient.

    """

    @property
    def cached_market_info(self) -> dict:
        store = getattr(self, "_cached_market_info", None)
        if store is None:
            store = self._cached_market_info = {}
        return store

    def _get_cached_market_info(self, search_string):
        found_markets = self.cached_market_info[search_string]
        return found_markets

    def _set_cached_market_info(self, search_string, found_markets):
        self._cached_market_info[search_string] = found_markets

    def get_unique_market_for_contract(
        self,
        contract_object: futuresContract,
        require_exact_match=True,  # Was False for convenience, now forced True
        display_exact_match=False,  # Often called when exact match must logically exist
    ):

        instrument_code = contract_object.instrument_code

        try:
            epics_for_instrument = self.get_markets_for_instrument(instrument_code)
        except missingInstrument:
            self.log.error(
                "No match when searching for available epic for %s" % contract_object
            )
            raise missingData

        try:
            epic_for_contract = self.get_market_for_contract(
                contract_object, epics_for_instrument
            )
            if display_exact_match:
                self.log.debug("Exact match found for %s" % contract_object)
        except missingData:
            # If epics_for_instrument is OK, but epic_for_contract failed, then it means
            # that one or more contract(s) is available, but not the one we looked for
            if require_exact_match:
                self.log.warning(
                    "No exact match when exact match required for %s" % contract_object
                )
                raise missingData
            # Accept contract with different expiry if it is the only one
            if len(epics_for_instrument) == 1:
                self.log.warning(
                    "No exact match, returning only available epic for %s"
                    % contract_object
                )
                epic_for_contract = epics_for_instrument
            # Otherwise choose the first contract after the one asked for, or the last
            # one available. Assume markets have been returned in ascending order of expiry
            else:
                contract_date = contract_object.date_str
                df = epics_for_instrument[epics_for_instrument.contract > contract_date]
                if len(df) == 0:
                    self.log.warning(
                        "No exact match, returning previous epic for %s"
                        % contract_object
                    )
                    df = epics_for_instrument.tail(1)
                else:
                    self.log.warning(
                        "No exact match, returning next available epic for %s"
                        % contract_object
                    )
                epic_for_contract = df

        # Return dict for market which either matches or is the best match
        ans = epic_for_contract.iloc[0].to_dict()
        return ans

    def get_market_for_contract(
        self, contract_object: futuresContract, markets_for_instrument=arg_not_supplied
    ):

        instrument_code = contract_object.instrument_code

        if markets_for_instrument is arg_not_supplied:
            try:
                markets = self.get_markets_for_instrument(instrument_code)
            except missingInstrument:
                raise missingData
        else:
            markets = markets_for_instrument

        contract_date = contract_object.contract_date
        matches = markets[markets.contract == contract_date.date_str]

        if len(matches) != 1:
            raise missingData
        return matches

    def get_markets_for_instrument(self, instrument_code):

        try:
            markets = self._search_markets_for_instrument(instrument_code)
        except missingInstrument:
            raise missingInstrument

        markets["instrument"] = instrument_code
        markets["contract"] = (
            pd.to_datetime(markets.expiry, format="%b-%y").dt.strftime("%Y%m") + "00"
        )
        return markets

    def _search_markets_for_instrument(self, instrument_code):

        try:
            search_parameters = self._get_search_parameters(instrument_code)
        except missingInstrument:
            raise missingInstrument

        ig_name, ig_type, ig_epic, ig_periods = search_parameters
        try:
            matching = self._get_markets_matching_search_string(
                search_string=ig_name,
                epic_string=ig_epic,
                periods_string=ig_periods,
            )
        except missingInstrument:
            self.log.warning(
                "Can't get market details for %s, error in get_markets"
                % instrument_code
            )
            raise missingInstrument

        filtered = matching[matching.instrumentName == ig_name]
        filtered = filtered[filtered.instrumentType == ig_type]
        filtered = filtered[filtered.expiry != "DFB"]
        if len(filtered) == 0:
            self.log.warning(
                "Can't get market details for %s, no match to search parameters"
                % instrument_code
            )
            raise missingInstrument

        return filtered

    def _get_search_parameters(self, instrument_code):

        config_data = self.ig_instrument_config
        matching_config_data = config_data[config_data.Instrument == instrument_code]

        if len(matching_config_data) == 0:
            self.log.warning(
                "Can't get IG config for %s missing from config" % instrument_code
            )
            raise missingInstrument

        elif len(matching_config_data) > 1:
            self.log.warning(
                "Can't get IG config for %s not unique in config" % instrument_code
            )
            raise missingInstrument

        ig_name = matching_config_data.IGName.values[0]
        ig_type = matching_config_data.IGType.values[0]
        ig_epic = matching_config_data.IGEpic.values[0]
        ig_periods = matching_config_data.IGPeriods.values[0]

        if ig_name != ig_name or ig_type != ig_type:
            self.log.warning(
                "Can't get IG config for %s values not set in config" % instrument_code
            )
            raise missingInstrument

        return ig_name, ig_type, ig_epic, ig_periods

    def _get_markets_matching_search_string(
        self,
        search_string: str,
        epic_string: str = arg_not_supplied,
        periods_string: str = arg_not_supplied,
    ):

        try:
            found_markets = self._get_cached_market_info(search_string)
            # self.log.debug(f"Success reusing market info for {search_string}")
            return found_markets

        except:
            pass

        try:
            found_markets = self.igconnection.rest_service.search_markets(search_string)
            found_markets = found_markets[found_markets.instrumentName == search_string]

            self._set_cached_market_info(search_string, found_markets)
            self.log.debug(
                f"Success getting market info for {search_string}\n"
                + str(
                    found_markets.drop(
                        columns=[
                            "percentageChange",
                            "netChange",
                            "delayTime",
                            "scalingFactor",
                            "streamingPricesAvailable",
                        ]
                    )
                )
            )
            return found_markets

        except Exception as exc:
            if epic_string is arg_not_supplied or periods_string is arg_not_supplied:
                self.log.warning(
                    f"Problem '{exc}' getting market info for '{search_string}', and ..."
                )
                self.log.error(
                    f"Cannot use fallback with epic={epic_string}/periods={periods_string}"
                )
                raise missingInstrument
            else:
                pass

        periods = periods_string.split("|")
        all_markets = []
        for period in periods:
            search_for_epic = epic_string + "." + period + ".IP"
            market = self.igconnection.rest_service.fetch_market_by_epic(
                search_for_epic
            )
            flattened = dict()
            for key in market.keys():  # instrument, dealingRules, snapshot
                for inner_key in market[key]:
                    flattened[inner_key] = market[key][inner_key]
            all_markets.append(flattened)

        found_markets = pd.DataFrame(all_markets)
        found_markets["instrumentName"] = found_markets["name"]
        found_markets["instrumentType"] = found_markets["type"]

        if len(found_markets) != 0:
            self._set_cached_market_info(search_string, found_markets)
            self.log.debug(
                f"Success getting market info by fallback route for {search_string}"
            )
            self.log.debug(str(found_markets))
            return found_markets
        else:
            self.log.error(
                f"Failed using fallback with epic={epic_string}/periods={periods_string}"
            )
            raise missingInstrument

    def is_exact_match_available_for_contract(
        self, contract_object: futuresContract
    ) -> bool:
        try:
            self.get_unique_market_for_contract(
                contract_object=contract_object,
                require_exact_match=True,
            )
            return True
        except missingData:
            return False
