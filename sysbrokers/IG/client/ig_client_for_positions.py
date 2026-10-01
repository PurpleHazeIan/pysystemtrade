from syscore.constants import arg_not_supplied
from sysexecution.orders.named_order_objects import missing_order


class listOfTradesWithContracts(list):
    pass


class igClientForPositions:
    """
    This class is for information about positions, activity, transactions, working orders
    Don't invoke directly, use only through inheritance as part of igClient.

    """

    def broker_get_activities(
        self,
        account_id: str = arg_not_supplied,
        milliseconds: int = 4 * 24 * 60 * 60 * 1000,  # 4 days in milliseconds
    ) -> listOfTradesWithContracts:
        """
        Get activity including trades and orders
        (also trailing stop loss movements, orders to open, etc.
        which are filtered out later)

        """
        account_activity = self._get_activity_history(milliseconds=milliseconds)
        trade_list = listOfTradesWithContracts(account_activity)
        return trade_list

    # Returns a list of dicts containing 8/17 fields from dataframe from rest_service
    # Fields were epic, date, time, marketName, size, level, actionStatus, period
    # Now include all 17 fields; extra fields are dealId, activityHistoryId, activity,
    # result, channel, currency, stop, stopType, limit
    def _get_activity_history(self, milliseconds):
        activities = self.igconnection.rest_service.fetch_account_activity_by_period(
            milliseconds
        )
        list_of_dicts_of_activities = activities.to_dict(orient="records")
        return list_of_dicts_of_activities

    def broker_get_transactions(self):
        pass

    # Not used. Transaction_history shows completed deals (opened and closed), not the
    # individual activities (open and close, orders to open, stop and limit changes, etc.)
    # that led up to them.
    # Might be useful if I wanted to use actual profit/loss on individual trades.
    def _get_transaction_history(self, start, end):
        history = self.rest_service.fetch_transaction_history(
            from_date=start, to_date=end
        )
        list_of_dicts_of_transactions = history.to_dict(orient="records")
        return list_of_dicts_of_transactions

    def broker_get_working_orders(
        self, account_id: str = arg_not_supplied
    ) -> listOfTradesWithContracts:
        """
        Get working_orders

        """
        list_of_working_orders = self._get_working_orders()
        order_list = listOfTradesWithContracts(list_of_working_orders)
        return order_list

    # Returns a list of dicts containing 31 fields from dataframe from rest_service
    # Fields are instrumentName, exchangeId, streamingPricesAvailable, offer, low, bid,
    # updateTime, expiry, high, marketStatus, delayTime, lotSize, percentageChange, epic,
    # netChange, instrumentType, scalingFactor, createdDate, currencyCode, dealId,
    # direction, dma, goodTillDate, goodTillDateISO, guaranteedStop, limitDistance,
    # orderLevel, orderSize, orderType, stopDistance, timeInForce
    def _get_working_orders(self):
        working_orders = self.igconnection.rest_service.fetch_working_orders()
        list_of_dicts_of_working_orders = working_orders.to_dict(orient="records")
        return list_of_dicts_of_working_orders

    def broker_query_position(self, broker_order):
        # If we can't query (as a position) with deal_id, return missing_order
        deal_id = broker_order.broker_permid
        try:
            query_result = self._query_position(deal_id)
            return query_result
        except:
            return missing_order

    def _query_position(self, deal_id: str):
        query_result = self.igconnection.rest_service.fetch_open_position_by_deal_id(
            deal_id
        )
        self.log.debug(f"result of query_position(): {query_result}")
        return query_result

    def broker_get_positions(self):
        list_of_positions = self._get_positions()
        return list_of_positions

    # Returned a list of dicts containing 11/29 fields from dataframe from rest_service
    # Fields were account, instrumentName->name, size, direction->dir, level, expiry,
    # epic, currency, createdDateUTC->createDate, dealId, dealReference, instrumentType
    # Now include all 29 fields; extra fields are contractSize, createdDate, limitLevel,
    # currency, controlledRisk, stopLevel, trailingStep, trailingStopDistance,
    # limitedRiskPremium, lotSize, bid, offer, updateTime, updateTimeUTC, delayTime,
    # streamingPricesAvailable, marketStatus, scalingFactor
    def _get_positions(self):

        positions = self.igconnection.rest_service.fetch_open_positions()
        # Add account
        positions["account"] = self.igconnection.account_number
        # Rename some columns for use downstream
        # dir was used in ig_positions.resolve_ig_fsb_position(), now uses direction
        # dir was used in igContractPositionData._get_contract_position_for_raw_entry()
        # for the others no usage has been found yet
        # positions.rename({"direction":"dir",
        #                  "instrumentName":"name",
        #                  "createdDateUTC":"createDate"
        #                  },
        #                 axis='columns', inplace=True)

        list_of_dicts_of_positions = positions.to_dict(orient="records")

        return list_of_dicts_of_positions
