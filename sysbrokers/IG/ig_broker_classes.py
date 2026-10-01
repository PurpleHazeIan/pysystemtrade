from sysbrokers.IG.ig_futures_contract_price_data import igFuturesContractPriceData
from sysbrokers.IG.ig_futures_contract_data import igFuturesContractData
from sysbrokers.IG.ig_contract_position_data import igContractPositionData
from sysbrokers.IG.ig_orders import igExecutionStackData
from sysbrokers.IG.ig_static_data import igStaticData
from sysbrokers.IG.ig_capital_data import igCapitalData
from sysbrokers.IG.ig_instruments_data import igFuturesInstrumentData


def get_ig_class_list():
    return [
        igFuturesContractPriceData,
        igFuturesContractData,
        igContractPositionData,
        igExecutionStackData,
        igStaticData,
        igCapitalData,
        igFuturesInstrumentData,
    ]
