"""
Simplest possible execution method, one market order

Designed for market order spread bets at IG. These complete on submission, either filled
or rejected, hence 'synchronous', unlike at IB where there may be a wait for completion.
So this code finds the order already completed, and manage_live_trade is very simple.

Also remove size limit, as some spread bet 'contracts' are small, and checks for timeout
and cancellation, which can't occur.
"""

from sysexecution.orders.named_order_objects import missing_order

from sysexecution.algos.algo import Algo
from sysexecution.algos.common_functions import (
    post_trade_processing,
)
from sysexecution.order_stacks.broker_order_stack import orderWithControls
from sysexecution.orders.broker_orders import market_order_type, brokerOrderType


class algoMarketSync(Algo):
    """
    Simplest possible execution algo
    Submits a single market order for the entire quantity

    """

    def submit_trade(self) -> orderWithControls:
        broker_order_with_controls = self.prepare_and_submit_trade()
        if broker_order_with_controls is missing_order:
            # something went wrong
            return missing_order

        return broker_order_with_controls

    def manage_trade(
        self, broker_order_with_controls: orderWithControls
    ) -> orderWithControls:
        broker_order_with_controls = self.manage_live_trade(broker_order_with_controls)
        broker_order_with_controls = post_trade_processing(
            self.data, broker_order_with_controls
        )

        return broker_order_with_controls

    def prepare_and_submit_trade(self):
        contract_order = self.contract_order

        order_type = self.order_type_to_use
        broker_order_with_controls = (
            self.get_and_submit_broker_order_for_contract_order(
                contract_order, order_type=order_type
            )
        )

        return broker_order_with_controls

    @property
    def order_type_to_use(self) -> brokerOrderType:
        return market_order_type

    def manage_live_trade(
        self, broker_order_with_controls: orderWithControls
    ) -> orderWithControls:
        log_attrs = {
            **broker_order_with_controls.order.log_attributes(),
            "method": "temp",
        }
        self.data.log.debug(
            "Completed trade %s with market order"
            % str(broker_order_with_controls.order),
            **log_attrs,
        )

        # Test for completion just to ensure any behind-the-scenes processing is done
        _ = broker_order_with_controls.completed()

        return broker_order_with_controls
