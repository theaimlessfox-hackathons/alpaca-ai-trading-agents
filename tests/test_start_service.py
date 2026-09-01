from pathlib import Path


def test_railway_starts_dashboard_and_trader_supervisor():
    railway = Path("railway.toml").read_text()
    source = Path("scripts/start_service.py").read_text()
    assert "scripts/start_service.py" in railway
    assert "scheduler.cycle_loop" in source
    assert '"--live"' in source
    assert "dashboard/app.py" in source
