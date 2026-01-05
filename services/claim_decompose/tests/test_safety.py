from main import decompose

def test_empty_input_safe():
    r = decompose({"text": ""})
    assert "atoms" in r

def test_long_input_bounded():
    text = "x " * 10_000
    r = decompose({"text": text})
    assert len(r["atoms"]) <= 10  # whatever bound you enforce

