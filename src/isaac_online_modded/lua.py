"""Line based Lua document handling that preserves BOM and newline style."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .common import PatchError, write_file_atomic


@dataclass
class LuaDocument:
    """Line based Lua file that keeps its original newline style and BOM."""

    path: Path
    lines: list[str]
    newline: str
    has_bom: bool

    @classmethod
    def read(cls, path: Path) -> "LuaDocument":
        raw = path.read_bytes()
        has_bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw[3:].decode("utf-8") if has_bom else raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PatchError(f"Lua file is not valid UTF-8: {path}") from exc
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.replace("\r\n", "\n").split("\n")
        return cls(path=path, lines=lines, newline=newline, has_bom=has_bom)

    def render(self) -> bytes:
        text = self.newline.join(self.lines)
        prefix = b"\xef\xbb\xbf" if self.has_bom else b""
        return prefix + text.encode("utf-8")

    def write(self) -> None:
        write_file_atomic(self.path, self.render())