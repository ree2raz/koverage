"""Verify that configure_logging() produces structured JSON on each log record."""

from __future__ import annotations

import json
import logging
import io

from beacon.logging_config import JSONFormatter, configure_logging


def _capture(level=logging.DEBUG) -> tuple[logging.Logger, io.StringIO]:
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger(f"test_{id(buf)}")
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger, buf


def test_output_is_valid_json():
    logger, buf = _capture()
    logger.info("hello world")
    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert isinstance(obj, dict)


def test_required_fields_present():
    logger, buf = _capture()
    logger.warning("something happened")
    obj = json.loads(buf.getvalue().strip())
    assert "ts" in obj
    assert "level" in obj
    assert "logger" in obj
    assert "msg" in obj


def test_level_name_matches():
    logger, buf = _capture()
    logger.error("oops")
    obj = json.loads(buf.getvalue().strip())
    assert obj["level"] == "ERROR"
    assert obj["msg"] == "oops"


def test_exception_included_on_exc_info():
    logger, buf = _capture()
    try:
        raise ValueError("test-error")
    except ValueError:
        logger.exception("caught")
    obj = json.loads(buf.getvalue().strip())
    assert "exc" in obj
    assert "ValueError" in obj["exc"]


def test_configure_logging_does_not_raise():
    configure_logging(level="DEBUG")
