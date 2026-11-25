"""ParamValidator unit tests."""

from __future__ import annotations

import pytest

from source_extract.params.param_spec import ParamSpec
from source_extract.params.param_type import ParamType
from source_extract.params.param_validator import ParamValidator


def test_applies_defaults() -> None:
    specs = [
        ParamSpec(name="step", param_type=ParamType.NUMBER, default=100.0),
        ParamSpec(name="system", param_type=ParamType.STRING, required=True),
    ]
    out = ParamValidator.validate(specs, {"system": "mgo-sio2"})
    assert out["system"] == "mgo-sio2"
    assert out["step"] == 100.0


def test_missing_required() -> None:
    specs = [ParamSpec(name="system", param_type=ParamType.STRING, required=True)]
    with pytest.raises(ValueError, match="Missing required"):
        ParamValidator.validate(specs, {})
