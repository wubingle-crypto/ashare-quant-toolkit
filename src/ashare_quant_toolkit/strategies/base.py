"""
策略基类 — 所有策略共用的接口定义
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """策略基类：所有策略必须实现 generate_signals 方法"""

    @abstractmethod
    def generate_signals(self, prices_df, positions, account, config):
        """
        生成买卖信号

        Parameters
        ----------
        prices_df : pd.DataFrame
            包含行情数据的 DataFrame，列至少包括 code, name, close, volume
        positions : list
            当前持仓列表
        account : dict
            账户信息（含 cash, total_assets 等）
        config : dict
            策略配置参数

        Returns
        -------
        dict
            {'buy': [(code, name, price, shares, reason), ...],
             'sell': [(code, name, price, shares, reason), ...]}
        """
        pass

    @property
    def strategy_id(self):
        """策略ID"""
        return "base"

    @property
    def display_name(self):
        """策略展示名称"""
        return "基础策略"
