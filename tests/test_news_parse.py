from tools.news_parse import news_items


def test_news_items_reads_alpaca_shape():
    raw = {
        "news": [
            {
                "headline": "NVDA rises",
                "url": "https://example.com/a",
                "source": "benzinga",
            },
            {"title": "No url here"},
        ]
    }
    rows = news_items(raw)
    assert rows[0]["headline"] == "NVDA rises"
    assert rows[0]["url"] == "https://example.com/a"
    assert rows[1]["headline"] == "No url here"


def test_news_items_caps_and_skips_empty():
    raw = {"news": [{"headline": ""}, {"headline": "one"}, {"headline": "two"}, {"headline": "three"}]}
    assert [r["headline"] for r in news_items(raw, limit=2)] == ["one", "two"]
