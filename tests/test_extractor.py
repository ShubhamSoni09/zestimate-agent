from zestimate_agent.extractor import extract_zestimate


def test_extract_from_jsonld() -> None:
    html = """
    <html>
      <body>
        <script type="application/ld+json">
          {"@context":"https://schema.org","zestimate":"$1,234,567"}
        </script>
      </body>
    </html>
    """
    value, source = extract_zestimate(html)
    assert value == 1234567
    assert source.startswith("jsonld")


def test_extract_from_next_data() -> None:
    html = """
    <html>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
          {"props":{"pageProps":{"property":{"zestimate": 765432}}}}
        </script>
      </body>
    </html>
    """
    value, source = extract_zestimate(html)
    assert value == 765432
    assert source.startswith("next_data")


def test_extract_zestimate_null_returns_not_available() -> None:
    html = """
    <html>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
          {"props":{"pageProps":{"property":{"zestimate":null,"price":64706}}}}
        </script>
      </body>
    </html>
    """
    value, source = extract_zestimate(html)
    assert value == "not available"
    assert "next_data" in source


def test_extract_no_zestimate_key_only_price_returns_not_available() -> None:
    html = """
    <html>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
          {"props":{"pageProps":{"property":{"price":999000}}}}
        </script>
      </body>
    </html>
    """
    value, source = extract_zestimate(html)
    assert value == "not available"
    assert source == "no_zestimate_field"
