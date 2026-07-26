from dataclasses import replace

from nds_bot.backtest.account import AccountPolicy, OverlapPolicy
from nds_bot.backtest.contracts import (
    ContractSpecification,
    calculate_position_size,
)
from nds_bot.backtest.costs import (
    TradingCostPolicy,
    apply_trading_costs,
)
from nds_bot.backtest.execution import (
    ExecutedTrade,
    ExitFillType,
    ExitReason,
)
from nds_bot.backtest.margin import (
    InsufficientMarginPolicy,
    MarginPolicy,
    calculate_margin,
)
from nds_bot.broker.models import (
    PaperClosedTrade,
    PaperEquityPoint,
    PaperOrder,
    PaperOrderReason,
    PaperOrderRequest,
    PaperOrderStatus,
    PaperPosition,
)


class PaperBroker:
    """
    Deterministic in-memory broker adapter for offline paper trading.

    The adapter never connects to a live broker and never submits a real
    order. Balance changes only when a simulated position is closed.
    """

    def __init__(
        self,
        *,
        account_policy: AccountPolicy | None = None,
        cost_policy: TradingCostPolicy | None = None,
        contract_specification: ContractSpecification | None = None,
        margin_policy: MarginPolicy | None = None,
    ) -> None:
        self.account_policy = account_policy or AccountPolicy()
        self.cost_policy = cost_policy or TradingCostPolicy()
        self.contract_specification = contract_specification
        self.margin_policy = margin_policy

        self._balance = self.account_policy.initial_balance
        self._peak_balance = self._balance

        self._orders: dict[str, PaperOrder] = {}
        self._positions: dict[str, PaperPosition] = {}
        self._closed_trades: list[PaperClosedTrade] = []
        self._equity_curve: list[PaperEquityPoint] = [
            PaperEquityPoint(
                event_number=0,
                time=None,
                balance=self._balance,
                peak_balance=self._peak_balance,
                drawdown_amount=0.0,
                drawdown_fraction=0.0,
            )
        ]

        self._order_counter = 0
        self._position_counter = 0
        self._trade_counter = 0

    @property
    def initial_balance(self) -> float:
        return self.account_policy.initial_balance

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def orders(self) -> tuple[PaperOrder, ...]:
        return tuple(self._orders.values())

    @property
    def open_positions(self) -> tuple[PaperPosition, ...]:
        return tuple(self._positions.values())

    @property
    def closed_trades(self) -> tuple[PaperClosedTrade, ...]:
        return tuple(self._closed_trades)

    @property
    def equity_curve(self) -> tuple[PaperEquityPoint, ...]:
        return tuple(self._equity_curve)

    def submit_order(
        self,
        request: PaperOrderRequest,
    ) -> PaperOrder:
        self._order_counter += 1
        order_id = f"ORD-{self._order_counter:06d}"

        order = PaperOrder(
            order_id=order_id,
            request=request,
            status=PaperOrderStatus.PENDING,
            created_index=request.signal.generated_at_index,
            created_time=request.signal.generated_at_time,
        )

        self._orders[order_id] = order
        return order

    def open_position(
        self,
        *,
        order_id: str,
        raw_trade: ExecutedTrade,
    ) -> PaperPosition | None:
        order = self._get_order(order_id)

        if order.status is not PaperOrderStatus.PENDING:
            raise ValueError("Only a pending paper order can be filled.")

        if raw_trade.entry_index != order.scheduled_entry_index:
            raise ValueError("Paper order entry index does not match raw execution.")

        if _signal_key(raw_trade) != _signal_key_from_order(order):
            raise ValueError("Paper order signal does not match raw execution.")

        if self._positions:
            if self.account_policy.overlap_policy is OverlapPolicy.RAISE:
                raise ValueError(
                    f"Overlapping paper position detected at entry index {raw_trade.entry_index}."
                )

            self._reject_order(
                order_id,
                PaperOrderReason.OVERLAPPING_POSITION,
            )
            return None

        provisional_stop_trade = replace(
            raw_trade,
            exit_index=raw_trade.entry_index,
            exit_time=raw_trade.entry_time,
            exit_price=raw_trade.stop_loss,
            exit_reason=ExitReason.STOP_LOSS,
            exit_fill_type=ExitFillType.LEVEL,
        )

        stop_adjustment = apply_trading_costs(
            provisional_stop_trade,
            policy=self.cost_policy,
        )

        requested_risk_amount = self._balance * self.account_policy.risk_fraction

        raw_quantity = requested_risk_amount / stop_adjustment.risk_per_unit

        if self.contract_specification is None:
            quantity = raw_quantity
            lots = None
            actual_risk_amount = requested_risk_amount
        else:
            position_size = calculate_position_size(
                risk_amount=requested_risk_amount,
                risk_per_unit=stop_adjustment.risk_per_unit,
                specification=self.contract_specification,
            )

            if position_size is None:
                self._reject_order(
                    order_id,
                    PaperOrderReason.BELOW_MINIMUM_LOT,
                )
                return None

            quantity = position_size.quantity
            lots = position_size.lots
            actual_risk_amount = position_size.actual_risk_amount

        margin_check = None

        if self.margin_policy is not None:
            margin_check = calculate_margin(
                equity=self._balance,
                quantity=quantity,
                entry_price=stop_adjustment.effective_entry_price,
                policy=self.margin_policy,
            )

            if not margin_check.is_sufficient:
                if self.margin_policy.insufficient_margin_policy is InsufficientMarginPolicy.RAISE:
                    raise ValueError(
                        "Paper order has insufficient margin at "
                        f"entry index {raw_trade.entry_index}."
                    )

                self._reject_order(
                    order_id,
                    PaperOrderReason.INSUFFICIENT_MARGIN,
                )
                return None

        self._position_counter += 1
        position_id = f"POS-{self._position_counter:06d}"

        position = PaperPosition(
            position_id=position_id,
            order_id=order_id,
            symbol=order.symbol,
            signal=order.signal,
            side=order.side,
            entry_index=raw_trade.entry_index,
            entry_time=raw_trade.entry_time,
            raw_entry_price=raw_trade.entry_price,
            effective_entry_price=(stop_adjustment.effective_entry_price),
            stop_loss=raw_trade.stop_loss,
            take_profit=raw_trade.take_profit,
            requested_risk_amount=requested_risk_amount,
            actual_risk_amount=actual_risk_amount,
            quantity=quantity,
            lots=lots,
            margin_check=margin_check,
        )

        self._positions[position_id] = position
        self._orders[order_id] = replace(
            order,
            status=PaperOrderStatus.OPEN,
            filled_index=raw_trade.entry_index,
            filled_time=raw_trade.entry_time,
        )

        return position

    def close_position(
        self,
        *,
        position_id: str,
        raw_trade: ExecutedTrade,
    ) -> PaperClosedTrade:
        try:
            position = self._positions[position_id]
        except KeyError as error:
            raise ValueError(f"Unknown open paper position: {position_id}") from error

        if raw_trade.exit_reason is ExitReason.END_OF_DATA:
            raise ValueError("An END_OF_DATA execution cannot close a paper position.")

        if _signal_key(raw_trade) != _signal_key_from_position(position):
            raise ValueError("Paper position signal does not match raw execution.")

        adjustment = apply_trading_costs(
            raw_trade,
            policy=self.cost_policy,
        )

        quantity = position.quantity
        gross_monetary_pnl = adjustment.gross_pnl_per_unit * quantity
        spread_slippage_cost = adjustment.spread_slippage_cost_per_unit * quantity
        commission_amount = adjustment.total_commission_per_unit * quantity
        total_cost_amount = spread_slippage_cost + commission_amount
        net_monetary_pnl = adjustment.net_pnl_per_unit * quantity
        balance_before = self._balance
        balance_after = balance_before + net_monetary_pnl

        if balance_after <= 0:
            raise ValueError("Paper trade would reduce account balance to zero or below.")

        self._trade_counter += 1
        closed_trade = PaperClosedTrade(
            trade_id=f"TRD-{self._trade_counter:06d}",
            position=position,
            raw_trade=raw_trade,
            cost_adjustment=adjustment,
            balance_before=balance_before,
            gross_monetary_pnl=gross_monetary_pnl,
            spread_slippage_cost=spread_slippage_cost,
            commission_amount=commission_amount,
            total_cost_amount=total_cost_amount,
            net_monetary_pnl=net_monetary_pnl,
            balance_after=balance_after,
        )

        self._closed_trades.append(closed_trade)
        del self._positions[position_id]

        order = self._get_order(position.order_id)
        self._orders[position.order_id] = replace(
            order,
            status=PaperOrderStatus.CLOSED,
            closed_index=raw_trade.exit_index,
            closed_time=raw_trade.exit_time,
        )

        self._balance = balance_after
        self._peak_balance = max(self._peak_balance, self._balance)
        drawdown_amount = self._peak_balance - self._balance
        drawdown_fraction = drawdown_amount / self._peak_balance

        self._equity_curve.append(
            PaperEquityPoint(
                event_number=len(self._closed_trades),
                time=raw_trade.exit_time,
                balance=self._balance,
                peak_balance=self._peak_balance,
                drawdown_amount=drawdown_amount,
                drawdown_fraction=drawdown_fraction,
            )
        )

        return closed_trade

    def cancel_pending_orders(self) -> None:
        for order_id, order in tuple(self._orders.items()):
            if order.status is PaperOrderStatus.PENDING:
                self._orders[order_id] = replace(
                    order,
                    status=PaperOrderStatus.CANCELLED,
                    status_reason=PaperOrderReason.NO_ENTRY_CANDLE.value,
                )

    def _reject_order(
        self,
        order_id: str,
        reason: PaperOrderReason,
    ) -> None:
        order = self._get_order(order_id)
        self._orders[order_id] = replace(
            order,
            status=PaperOrderStatus.REJECTED,
            status_reason=reason.value,
        )

    def _get_order(self, order_id: str) -> PaperOrder:
        try:
            return self._orders[order_id]
        except KeyError as error:
            raise ValueError(f"Unknown paper order: {order_id}") from error


def _signal_key(trade: ExecutedTrade) -> tuple[object, ...]:
    signal = trade.signal
    return (
        signal.side,
        signal.generated_at_index,
        signal.cycle_indexes,
    )


def _signal_key_from_order(order: PaperOrder) -> tuple[object, ...]:
    signal = order.signal
    return (
        signal.side,
        signal.generated_at_index,
        signal.cycle_indexes,
    )


def _signal_key_from_position(
    position: PaperPosition,
) -> tuple[object, ...]:
    signal = position.signal
    return (
        signal.side,
        signal.generated_at_index,
        signal.cycle_indexes,
    )
