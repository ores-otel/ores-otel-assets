"""IHDR integrity regression tests; standard library only."""

import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts.validate import PNG_SIGNATURE, png_size, root


def ihdr(width=64, height=64):
    fields = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = b"IHDR" + fields
    return PNG_SIGNATURE + struct.pack(">I", 13) + chunk + struct.pack(">I", zlib.crc32(chunk))


class PngHeaderTests(unittest.TestCase):
    def check(self, data, valid):
        with tempfile.TemporaryDirectory(dir=root) as d:
            path = Path(d) / "fixture.png"
            path.write_bytes(data)
            if valid:
                self.assertEqual(png_size(path), (64, 64))
            else:
                with self.assertRaises(AssertionError):
                    png_size(path)

    def test_valid_ihdr(self):
        self.check(ihdr(), True)

    def test_corrupted_crc(self):
        damaged = bytearray(ihdr())
        damaged[24] ^= 1
        self.check(bytes(damaged), False)

    def test_invalid_chunk_length(self):
        damaged = bytearray(ihdr())
        damaged[11] = 12
        self.check(bytes(damaged), False)

    def test_truncated_header(self):
        self.check(ihdr()[:-1], False)

    def test_zero_dimensions(self):
        self.check(ihdr(width=0), False)

    def test_oversized_dimensions(self):
        self.check(ihdr(width=16385), False)


if __name__ == "__main__":
    unittest.main()
