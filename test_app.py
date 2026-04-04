import app


def test_import():
    assert app is not None


def test_fmt_currency():
    assert app.fmt_currency(1234.5) == "$1,234.50"
    assert app.fmt_currency(None) == "$0.00"
    assert app.fmt_currency("bad") == "$0.00"


def test_fmt_pct():
    assert app.fmt_pct(0.8) == "80.0%"
    assert app.fmt_pct(80) == "80.0%"
    assert app.fmt_pct(None) == "0.0%"


def test_as_pct():
    assert app.as_pct(0.5) == 50.0
    assert app.as_pct(75) == 75.0
    assert app.as_pct(None) == 0.0


def test_page_routes_registered():
    expected = {"dashboard", "reports", "invoices", "time_cost", "scenarios", "settings"}
    assert expected == set(app._PAGE_ROUTES.keys())


if __name__ == "__main__":
    test_import()
    test_fmt_currency()
    test_fmt_pct()
    test_as_pct()
    test_page_routes_registered()
