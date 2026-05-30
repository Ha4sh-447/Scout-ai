from __future__ import annotations

import logging
import os
import re
import sys


_ANSI_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",
}

_LEVEL_COLORS = {
    logging.DEBUG: "cyan",
    logging.INFO: "blue",
    logging.WARNING: "yellow",
    logging.ERROR: "red",
    logging.CRITICAL: "magenta",
}

_LABEL_RE = re.compile(r"^\[(?P<label>[^\]]+)\]\s*(?P<body>.*)$")


def supports_color(stream=None) -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if stream is None:
        stream = sys.stdout
    return bool(getattr(stream, "isatty", None) and stream.isatty())


def color_text(text: object, color: str | None = None, *, bold: bool = False, dim: bool = False, stream=None) -> str:
    rendered = str(text)
    if not supports_color(stream) or not color:
        return rendered

    codes: list[str] = []
    if bold:
        codes.append(_ANSI_CODES["bold"])
    if dim:
        codes.append(_ANSI_CODES["dim"])
    codes.append(_ANSI_CODES.get(color, ""))
    codes = [code for code in codes if code]
    if not codes:
        return rendered
    return f"{''.join(codes)}{rendered}{_ANSI_CODES['reset']}"


def colored_label(label: str, color: str = "cyan", *, stream=None) -> str:
    return color_text(f"[{label}]", color, bold=True, stream=stream)


def status_line(label: str, message: str, color: str, *, stream=None) -> str:
    return f"{colored_label(label, color, stream=stream)} {color_text(message, color, stream=stream)}"


def print_status(label: str, message: str, color: str, *, stream=None) -> None:
    print(status_line(label, message, color, stream=stream))


class ColorFormatter(logging.Formatter):
    def __init__(self, datefmt: str = "%Y-%m-%d %H:%M:%S") -> None:
        super().__init__(datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        timestamp = color_text(self.formatTime(record, self.datefmt), "gray", dim=True)
        level_color = _LEVEL_COLORS.get(record.levelno, "white")
        level = color_text(record.levelname, level_color, bold=True)

        message = record.getMessage()
        label_match = _LABEL_RE.match(message)
        if label_match:
            label = colored_label(label_match.group("label"), "cyan")
            body = label_match.group("body")
            message = f"{label} {color_text(body, level_color)}" if body else label
        else:
            message = color_text(message, level_color)

        rendered = f"{timestamp} | {level} | {message}"
        if record.exc_info:
            rendered = f"{rendered}\n{color_text(self.formatException(record.exc_info), 'gray')}"
        return rendered