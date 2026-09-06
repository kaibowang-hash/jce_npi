from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Sequence


_VERSION = 6
_SIZE = 17 + 4 * _VERSION
_DATA_CODEWORDS = 136
_BLOCK_DATA_CODEWORDS = 68
_ECC_CODEWORDS_PER_BLOCK = 18
_TOTAL_CODEWORDS = 172
_PAYLOAD = re.compile(
    r"^urn:npi:controlled-print:"
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}:"
    r"[a-f0-9]{64}$"
)


def verification_qr_matrix(payload: str) -> tuple[tuple[bool, ...], ...]:
    """Encode the bounded verification URN as a deterministic QR Model 2 symbol.

    The implementation is deliberately fixed to Version 6-L, byte mode, two
    equal Reed-Solomon blocks. That is sufficient for the 126-byte controlled
    print payload and avoids a runtime package or external service.
    """

    data = _verification_payload_bytes(payload)
    codewords = _add_error_correction(_encode_data_codewords(data))
    base, functions = _function_modules()
    candidates: list[tuple[int, int, list[list[bool]]]] = []
    for mask in range(8):
        modules = [row.copy() for row in base]
        _place_codewords(modules, functions, codewords, mask)
        _draw_format(modules, mask)
        candidates.append((_penalty(modules), mask, modules))
    _score, _mask, selected = min(candidates, key=lambda item: (item[0], item[1]))
    return tuple(tuple(row) for row in selected)


def verification_qr_svg(payload: str, *, quiet_zone: int = 4) -> str:
    """Return a self-contained, payload-free SVG representation of the QR."""

    if type(quiet_zone) is not int or not 4 <= quiet_zone <= 16:
        raise ValueError("QR quiet zone must be between 4 and 16 modules.")
    matrix = verification_qr_matrix(payload)
    extent = _SIZE + quiet_zone * 2
    paths: list[str] = []
    for y, row in enumerate(matrix, start=quiet_zone):
        start: int | None = None
        for x, dark in enumerate((*row, False), start=quiet_zone):
            if dark and start is None:
                start = x
            elif not dark and start is not None:
                width = x - start
                paths.append(f"M{start} {y}h{width}v1h-{width}z")
                start = None
    path = "".join(paths)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {extent} {extent}" '
        'shape-rendering="crispEdges">'
        f'<rect width="{extent}" height="{extent}" fill="#fff"/>'
        f'<path d="{path}" fill="#000"/></svg>'
    )


def verification_qr_data_uri(payload: str) -> str:
    svg = verification_qr_svg(payload).encode("utf-8")
    encoded = base64.b64encode(svg).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def verification_qr_digest(payload: str) -> str:
    """Return a stable digest for retained render evidence and fixed vectors."""

    return hashlib.sha256(verification_qr_svg(payload).encode("utf-8")).hexdigest()


def _verification_payload_bytes(payload: str) -> bytes:
    if not isinstance(payload, str) or _PAYLOAD.fullmatch(payload) is None:
        raise ValueError("Controlled print QR payload is invalid.")
    encoded = payload.encode("ascii")
    if len(encoded) > 134:
        raise ValueError("Controlled print QR payload exceeds Version 6-L capacity.")
    return encoded


def _encode_data_codewords(data: bytes) -> bytes:
    bits: list[int] = []
    _append_bits(bits, 0b0100, 4)
    _append_bits(bits, len(data), 8)
    for value in data:
        _append_bits(bits, value, 8)
    capacity = _DATA_CODEWORDS * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    bits.extend([0] * (-len(bits) % 8))
    result = bytearray(
        sum(bits[index + offset] << (7 - offset) for offset in range(8))
        for index in range(0, len(bits), 8)
    )
    pads = (0xEC, 0x11)
    while len(result) < _DATA_CODEWORDS:
        result.append(pads[(len(result) - len(bits) // 8) % 2])
    if len(result) != _DATA_CODEWORDS:
        raise AssertionError("QR data capacity calculation failed.")
    return bytes(result)


def _append_bits(target: list[int], value: int, length: int) -> None:
    target.extend((value >> shift) & 1 for shift in range(length - 1, -1, -1))


def _add_error_correction(data: bytes) -> bytes:
    if len(data) != _DATA_CODEWORDS:
        raise AssertionError("QR data block length is invalid.")
    generator = _reed_solomon_generator(_ECC_CODEWORDS_PER_BLOCK)
    blocks = (
        data[:_BLOCK_DATA_CODEWORDS],
        data[_BLOCK_DATA_CODEWORDS:],
    )
    ecc = tuple(_reed_solomon_remainder(block, generator) for block in blocks)
    interleaved = bytearray()
    for index in range(_BLOCK_DATA_CODEWORDS):
        interleaved.extend(block[index] for block in blocks)
    for index in range(_ECC_CODEWORDS_PER_BLOCK):
        interleaved.extend(block[index] for block in ecc)
    if len(interleaved) != _TOTAL_CODEWORDS:
        raise AssertionError("QR interleaved codeword length is invalid.")
    return bytes(interleaved)


def _reed_solomon_generator(degree: int) -> bytes:
    coefficients = bytearray(degree)
    coefficients[-1] = 1
    root = 1
    for _ in range(degree):
        for index in range(degree):
            coefficients[index] = _gf_multiply(coefficients[index], root)
            if index + 1 < degree:
                coefficients[index] ^= coefficients[index + 1]
        root = _gf_multiply(root, 0x02)
    return bytes(coefficients)


def _reed_solomon_remainder(data: bytes, generator: bytes) -> bytes:
    remainder = bytearray(len(generator))
    for value in data:
        factor = value ^ remainder[0]
        remainder[:-1] = remainder[1:]
        remainder[-1] = 0
        for index, coefficient in enumerate(generator):
            remainder[index] ^= _gf_multiply(coefficient, factor)
    return bytes(remainder)


def _gf_multiply(left: int, right: int) -> int:
    result = 0
    value = left
    factor = right
    for _ in range(8):
        if factor & 1:
            result ^= value
        carry = value & 0x80
        value = (value << 1) & 0xFF
        if carry:
            value ^= 0x1D
        factor >>= 1
    return result


def _function_modules() -> tuple[list[list[bool]], list[list[bool]]]:
    modules = [[False] * _SIZE for _ in range(_SIZE)]
    functions = [[False] * _SIZE for _ in range(_SIZE)]

    def set_function(x: int, y: int, dark: bool) -> None:
        if 0 <= x < _SIZE and 0 <= y < _SIZE:
            modules[y][x] = dark
            functions[y][x] = True

    for center_x, center_y in ((3, 3), (_SIZE - 4, 3), (3, _SIZE - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                distance = max(abs(dx), abs(dy))
                set_function(
                    center_x + dx,
                    center_y + dy,
                    distance not in {2, 4},
                )
    for index in range(_SIZE):
        if not functions[6][index]:
            set_function(index, 6, index % 2 == 0)
        if not functions[index][6]:
            set_function(6, index, index % 2 == 0)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            set_function(34 + dx, 34 + dy, max(abs(dx), abs(dy)) != 1)

    _draw_format(modules, 0, functions=functions)
    return modules, functions


def _draw_format(
    modules: list[list[bool]],
    mask: int,
    *,
    functions: list[list[bool]] | None = None,
) -> None:
    data = (0b01 << 3) | mask
    remainder = data
    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
    bits = ((data << 10) | remainder) ^ 0x5412

    def put(x: int, y: int, bit: int | bool) -> None:
        modules[y][x] = bool(bit)
        if functions is not None:
            functions[y][x] = True

    for index in range(6):
        put(8, index, (bits >> index) & 1)
    put(8, 7, (bits >> 6) & 1)
    put(8, 8, (bits >> 7) & 1)
    put(7, 8, (bits >> 8) & 1)
    for index in range(9, 15):
        put(14 - index, 8, (bits >> index) & 1)
    for index in range(8):
        put(_SIZE - 1 - index, 8, (bits >> index) & 1)
    for index in range(8, 15):
        put(8, _SIZE - 15 + index, (bits >> index) & 1)
    put(8, _SIZE - 8, True)


def _place_codewords(
    modules: list[list[bool]],
    functions: Sequence[Sequence[bool]],
    codewords: bytes,
    mask: int,
) -> None:
    bit_index = 0
    total_bits = len(codewords) * 8
    right = _SIZE - 1
    while right >= 1:
        if right == 6:
            right = 5
        upward = ((right + 1) & 2) == 0
        for vertical in range(_SIZE):
            y = _SIZE - 1 - vertical if upward else vertical
            for offset in range(2):
                x = right - offset
                if functions[y][x]:
                    continue
                dark = (
                    ((codewords[bit_index >> 3] >> (7 - (bit_index & 7))) & 1)
                    if bit_index < total_bits
                    else 0
                )
                modules[y][x] = bool(dark) ^ _mask_bit(mask, x, y)
                bit_index += 1
        right -= 2
    if bit_index != total_bits + 7:
        raise AssertionError("QR remainder-bit placement failed.")


def _mask_bit(mask: int, x: int, y: int) -> bool:
    product = x * y
    formulas = (
        (x + y) % 2,
        y % 2,
        x % 3,
        (x + y) % 3,
        (x // 3 + y // 2) % 2,
        product % 2 + product % 3,
        (product % 2 + product % 3) % 2,
        ((x + y) % 2 + product % 3) % 2,
    )
    return formulas[mask] == 0


def _penalty(modules: Sequence[Sequence[bool]]) -> int:
    score = 0
    for line in (*modules, *zip(*modules, strict=True)):
        run_color = line[0]
        run_length = 1
        for value in line[1:]:
            if value == run_color:
                run_length += 1
            else:
                if run_length >= 5:
                    score += 3 + run_length - 5
                run_color = value
                run_length = 1
        if run_length >= 5:
            score += 3 + run_length - 5
        text = "".join("1" if value else "0" for value in line)
        score += 40 * (text.count("10111010000") + text.count("00001011101"))
    for y in range(_SIZE - 1):
        for x in range(_SIZE - 1):
            color = modules[y][x]
            if (
                modules[y][x + 1] == color
                and modules[y + 1][x] == color
                and modules[y + 1][x + 1] == color
            ):
                score += 3
    dark = sum(value for row in modules for value in row)
    deviation = abs(dark * 20 - _SIZE * _SIZE * 10) // (_SIZE * _SIZE)
    return score + deviation * 10
