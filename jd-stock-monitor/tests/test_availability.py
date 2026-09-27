from jd_stock_monitor.website import StockState, classify_stock


VARIANT = "iPhone 18 Pro Max|256GB|布根地紅色"
DISTRICT = "Wan Chai"


def test_explicit_in_stock_requires_matching_variant_and_district():
    text = "Apple iPhone 18 Pro Max 256GB 布根地紅色；配送至 香港 灣仔；有貨"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.IN_STOCK


def test_explicit_sold_out_requires_matching_variant_and_district():
    text = "Apple iPhone 18 Pro Max 256GB 布根地紅色；配送至 香港 灣仔；暫時無貨"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.OUT_OF_STOCK


def test_missing_wan_chai_context_is_unknown_even_with_stock_wording():
    text = "Apple iPhone 18 Pro Max 256GB 布根地紅色；有貨"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.UNKNOWN


def test_wrong_variant_is_unknown_even_if_page_mentions_in_stock():
    text = "Apple iPhone 18 Pro Max 512GB；香港 灣仔；有貨"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.UNKNOWN


def test_conflicting_stock_markers_are_unknown():
    text = "iPhone 18 Pro Max 256GB；香港 灣仔；有貨；暫時無貨"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.UNKNOWN


def test_no_explicit_stock_marker_is_unknown():
    text = "iPhone 18 Pro Max 256GB 布根地紅色；香港 灣仔；選擇門店後可確認價格"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.UNKNOWN


def test_region_restriction_is_not_mislabeled_as_sold_out():
    text = "iPhone 18 Pro Max 256GB 布根地紅色；港澳中国香港湾仔区湾仔；此商品在所选区域暂不支持销售"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.UNAVAILABLE_IN_REGION
    assert result.reason == "not_available_in_selected_region"


def test_region_restriction_conflicting_with_stock_is_unknown():
    text = "iPhone 18 Pro Max 256GB 布根地紅色；香港 湾仔；有货；此商品在所选区域暂不支持销售"

    result = classify_stock(text, variant=VARIANT, district=DISTRICT)

    assert result.state is StockState.UNKNOWN
    assert result.reason == "conflicting_availability_markers"