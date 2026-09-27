import json
from pathlib import Path

from jd_stock_monitor import cli
from jd_stock_monitor.website import StockState, WebObservation


def test_cli_outputs_a_single_sanitized_observation(tmp_path: Path, monkeypatch, capsys):
    config = tmp_path / "config.toml"
    config.write_text(
        '''[product]\nid = "100414877908"\nurl = "https://mitem.jd.hk/product/100414877908.html"\nvariant = "iPhone 18 Pro Max|256GB|布根地紅色"\n[location]\nregion = "HK"\ndistrict = "Wan Chai"\n[fetch]\nproxy_url = "http://127.0.0.1:1181"\n''',
        encoding="utf-8",
    )
    expected = WebObservation(
        product_id="100414877908",
        url="https://mitem.jd.hk/product/100414877908.html",
        district="Wan Chai",
        destination="港澳中国香港湾仔区湾仔",
        state=StockState.UNAVAILABLE_IN_REGION,
        reason="not_available_in_selected_region",
        page_title="JD product",
        checked_at="2026-09-24T15:00:00+08:00",
        http_status=200,
    )
    monkeypatch.setattr(cli, "fetch_web_observation", lambda **kwargs: expected)

    exit_code = cli.main(["--config", str(config)])
    output = capsys.readouterr()

    assert exit_code == 0
    result = json.loads(output.out)
    assert result["state"] == "unavailable_in_region"
    assert result["destination"] == "港澳中国香港湾仔区湾仔"
    assert result["region"] == "HK"
    assert result["district"] == "Wan Chai"
    assert result["proxy_enabled"] is True
    assert "cookies" not in output.out.lower()
    assert output.err == ""
