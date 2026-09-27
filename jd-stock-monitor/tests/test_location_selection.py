from playwright.sync_api import sync_playwright

from jd_stock_monitor.website import select_hk_wan_chai


HTML = """
<div id="addrArea" onclick="document.querySelector('.plato-ui-addressLayer').style.display='block'">
  <span id="addrName">北京朝阳区</span>
</div>
<div class="plato-ui-addressLayer" style="display:none">
  <div class="plato-ui-tabsItem">中国大陆</div>
  <div class="plato-ui-tabsItem" onclick="showCountries()">港澳台及海外</div>
  <div id="options"></div>
</div>
<script>
function showCountries(){document.querySelector('#options').innerHTML='<div class="plato-ui-cityItem" onclick="showDistricts()">中国香港</div>';}
function showDistricts(){document.querySelector('#options').innerHTML='<div class="plato-ui-cityItem" onclick="showSubareas()">湾仔区</div>';}
function showSubareas(){document.querySelector('#options').innerHTML='<div class="plato-ui-cityItem" onclick="finish()">湾仔</div>';}
function finish(){document.querySelector('#addrName').innerText='港澳中国香港湾仔区湾仔';document.querySelector('.plato-ui-addressLayer').style.display='none';}
</script>
"""


def test_selects_hong_kong_wan_chai_using_visible_location_controls():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(HTML)

        selected, destination, reason = select_hk_wan_chai(page)

        assert selected is True
        assert destination == "港澳中国香港湾仔区湾仔"
        assert reason == "selected"
        browser.close()


def test_fails_closed_when_hong_kong_option_is_missing():
    html = HTML.replace(
        '<div class="plato-ui-cityItem" onclick="showDistricts()">中国香港</div>',
        '<div class="plato-ui-cityItem">中国澳门</div>',
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)

        selected, destination, reason = select_hk_wan_chai(page)

        assert selected is False
        assert destination == "北京朝阳区"
        assert reason == "hong_kong_option_missing"
        browser.close()


def test_waits_for_asynchronous_location_options():
    delayed_html = (
        HTML.replace('onclick="showCountries()"', 'onclick="setTimeout(showCountries, 500)"')
        .replace('onclick="showDistricts()"', 'onclick="setTimeout(showDistricts, 500)"')
        .replace('onclick="showSubareas()"', 'onclick="setTimeout(showSubareas, 500)"')
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(delayed_html)

        selected, destination, reason = select_hk_wan_chai(page)

        assert selected is True
        assert destination == "港澳中国香港湾仔区湾仔"
        assert reason == "selected"
        browser.close()
