from app.knowledge.terminology import key, normalise

T = {"brg": "bearing", "vib": "vibration", "hot": "overheating"}


def test_case_and_punctuation_insensitive():
    assert normalise("BRG, Vib. HOT!", T) == "bearing, vibration. overheating!"
    assert key(" B.R-G ") == "b r g"


def test_unknown_passes_through():
    assert normalise("Pump P-104 Seized", T) == "Pump P-104 Seized"
