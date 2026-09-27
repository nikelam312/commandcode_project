from pathlib import Path

import pytest

from jd_stock_monitor.config import ConfigError, load_config


def test_loads_hong_kong_wan_chai_product_config(tmp_path: Path):
    config_file = tmp_path / "monitor.toml"
    config_file.write_text(
        '''[product]\nid = "100414877908"\nurl = "https://mitem.jd.hk/product/100414877908.html"\nvariant = "iPhone 18 Pro Max|256GB|布根地紅色"\n[location]\nregion = "HK"\ndistrict = "Wan Chai"\n[fetch]\nproxy_url = "http://127.0.0.1:1181"\n''',
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.product_id == "100414877908"
    assert config.region == "HK"
    assert config.district == "Wan Chai"
    assert config.proxy_url == "http://127.0.0.1:1181"


def test_rejects_a_url_for_a_different_product(tmp_path: Path):
    config_file = tmp_path / "monitor.toml"
    config_file.write_text(
        '''[product]\nid = "100414877908"\nurl = "https://mitem.jd.hk/product/other.html"\nvariant = "iPhone 18 Pro Max|256GB|布根地紅色"\n[location]\nregion = "HK"\ndistrict = "Wan Chai"\n[fetch]\nproxy_url = "http://127.0.0.1:1181"\n''',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="product ID"):
        load_config(config_file)


def test_requires_proxy_to_prevent_direct_fallback(tmp_path: Path):
    config_file = tmp_path / "monitor.toml"
    config_file.write_text(
        '''[product]\nid = "100414877908"\nurl = "https://mitem.jd.hk/product/100414877908.html"\nvariant = "iPhone 18 Pro Max|256GB|布根地紅色"\n[location]\nregion = "HK"\ndistrict = "Wan Chai"\n''',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="proxy_url is required"):
        load_config(config_file)


def test_rejects_unrequested_region(tmp_path: Path):
    config_file = tmp_path / "monitor.toml"
    config_file.write_text(
        '''[product]\nid = "100414877908"\nurl = "https://mitem.jd.hk/product/100414877908.html"\nvariant = "iPhone 18 Pro Max|256GB|布根地紅色"\n[location]\nregion = "US"\ndistrict = "Atlanta"\n[fetch]\nproxy_url = "http://127.0.0.1:1181"\n''',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="HK"):
        load_config(config_file)
