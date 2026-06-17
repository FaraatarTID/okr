"""
Tests for Phase 4: Strategic Analysis & Reporting Engine.
"""

from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 1. Burnout Risk Tests
# ---------------------------------------------------------------------------


class TestBurnoutRisk:
    """Tests for calculate_burnout_risk logic."""

    @patch("src.domain.analysis.get_session_context")
    def test_healthy_risk_with_no_data(self, mock_ctx):
        """With no work logs, risk should be 0 (Healthy)."""
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        mock_session.exec.return_value.one.return_value = 0
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from src.domain.analysis import calculate_burnout_risk

        result = calculate_burnout_risk(user_id=1, days=14)

        assert result["risk_label"] == "Healthy"
        assert result["risk_score"] == 0
        assert result["completed_tasks"] == 0


# ---------------------------------------------------------------------------
# 2. Strategy Gap Tests
# ---------------------------------------------------------------------------


class TestStrategyGaps:
    """Tests for detect_strategy_gaps logic."""

    @patch("src.domain.analysis.get_session_context")
    def test_no_gaps_with_empty_cycle(self, mock_ctx):
        """An empty cycle should return no gaps."""
        mock_session = MagicMock()
        # The query chain: select().join().where().where() -> exec -> .all() -> []
        mock_session.exec.return_value.all.return_value = []
        ctx_instance = MagicMock()
        ctx_instance.__enter__ = MagicMock(return_value=mock_session)
        ctx_instance.__exit__ = MagicMock(return_value=False)
        mock_ctx.return_value = ctx_instance

        from src.domain.analysis import detect_strategy_gaps

        result = detect_strategy_gaps(cycle_id=1)

        assert isinstance(result, list)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 3. Achievement Aggregation Tests
# ---------------------------------------------------------------------------


class TestAchievementAggregation:
    """Tests for aggregate_achievements logic."""

    @patch("src.domain.analysis.get_session_context")
    def test_no_achievements_when_no_tasks(self, mock_ctx):
        """With no DONE tasks, achievements should be empty."""
        mock_session = MagicMock()
        mock_session.exec.return_value.all.return_value = []
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from src.domain.analysis import aggregate_achievements

        result = aggregate_achievements(user_id=1, cycle_id=1)

        assert isinstance(result, list)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 4. Reporting Tests
# ---------------------------------------------------------------------------


class TestReporting:
    """Tests for reporting.py portfolio generation."""

    @patch("src.domain.reporting.aggregate_achievements")
    @patch("src.domain.reporting.calculate_burnout_risk")
    def test_portfolio_structure(self, mock_burnout, mock_achievements):
        """Portfolio should have all required fields."""
        mock_achievements.return_value = []
        mock_burnout.return_value = {
            "risk_score": 10,
            "risk_label": "Healthy",
            "avg_daily_minutes": 120,
            "completed_tasks": 5,
            "work_days": 10,
        }

        from src.domain.reporting import generate_achievement_portfolio

        portfolio = generate_achievement_portfolio(
            user_id=1, cycle_id=1, user_display_name="Test User"
        )

        assert portfolio["user"] == "Test User"
        assert "generated_at" in portfolio
        assert portfolio["total_achievements"] == 0
        assert "burnout_snapshot" in portfolio
        assert "summary_text" in portfolio

    @patch("src.domain.reporting.aggregate_achievements")
    @patch("src.domain.reporting.calculate_burnout_risk")
    def test_markdown_format(self, mock_burnout, mock_achievements):
        """Portfolio Markdown should contain key sections."""
        mock_achievements.return_value = [
            {
                "task_id": 1,
                "task_title": "Implement Feature X",
                "time_spent": 120,
                "kr_title": "Ship 3 features",
                "kr_score": 0.85,
                "kr_score_label": "On Track",
                "objective_title": "Product Growth",
            }
        ]
        mock_burnout.return_value = {
            "risk_score": 15,
            "risk_label": "Healthy",
            "avg_daily_minutes": 180,
            "completed_tasks": 8,
            "work_days": 12,
        }

        from src.domain.reporting import (
            generate_achievement_portfolio,
            format_portfolio_as_markdown,
        )

        portfolio = generate_achievement_portfolio(
            user_id=1, cycle_id=1, user_display_name="Test User"
        )
        md = format_portfolio_as_markdown(portfolio)

        assert "# Achievement Portfolio" in md
        assert "Implement Feature X" in md
        assert "Health Snapshot" in md
        assert "Healthy" in md
