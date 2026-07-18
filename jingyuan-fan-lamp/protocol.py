from __future__ import annotations

from dataclasses import dataclass

END_PACKET: list[int] = [0xCDAB, 0x7856]

BURST_INTERVAL_S = 0.2
BURST_DURATION_S = 2.5
END_HOLD_S = 0.25


@dataclass(frozen=True)
class Command:
    name: str
    packet_a: tuple[int, ...]
    packet_b: tuple[int, ...]


COMMANDS: dict[str, Command] = {
    "fan-on": Command(
        name="fan-on",
        packet_a=(
            0x08F0,
            0x8230,
            0xFEFD,
            0x5993,
            0xFD35,
            0x8C2A,
            0xC6D9,
            0x5208,
            0xEC92,
            0x3571,
            0x696E,
            0x573F,
            0x9881,
        ),
        packet_b=(
            0xF877,
            0x5FB6,
            0x5E2B,
            0xFC00,
            0x5131,
            0x6394,
            0x6812,
            0x0A44,
            0xFCFB,
            0x58EE,
            0xAEF4,
            0x7994,
            0x3A42,
        ),
    ),
    "fan-off": Command(
        name="fan-off",
        packet_a=(
            0x08F0,
            0x8230,
            0xFFFD,
            0x5993,
            0xFD35,
            0x8C2A,
            0xC6D9,
            0x5208,
            0xEA92,
            0x0C71,
            0x6935,
            0x573F,
            0x280D,
        ),
        packet_b=(
            0xF877,
            0x5FB6,
            0x5E2B,
            0xFC00,
            0x5131,
            0x6354,
            0x0812,
            0x0A24,
            0xFC1B,
            0x7FC9,
            0x89F4,
            0x80E1,
            0x97A1,
        ),
    ),
    "light-on": Command(
        name="light-on",
        packet_a=(
            0x08F0,
            0x8230,
            0xFEFD,
            0x5993,
            0xFD35,
            0x8C2A,
            0xE7D9,
            0x5208,
            0xEAB2,
            0x2271,
            0x69B1,
            0x573F,
            0x2F9C,
        ),
        packet_b=(
            0xF877,
            0x5FB6,
            0x5E2B,
            0xFC00,
            0x5131,
            0x63D0,
            0x0812,
            0x0A24,
            0xFCFB,
            0x07B1,
            0xF1F4,
            0x4D6C,
            0x36E8,
        ),
    ),
    "light-off": Command(
        name="light-off",
        packet_a=(
            0x08F0,
            0x8230,
            0xFFFD,
            0x5993,
            0xFD35,
            0x8C2A,
            0xE6D9,
            0x5208,
            0xEAB2,
            0xBC71,
            0x6979,
            0x573F,
            0xF68F,
        ),
        packet_b=(
            0xF877,
            0x5FB6,
            0x5E2B,
            0xFC00,
            0x5131,
            0x6350,
            0x0812,
            0x0A24,
            0xFC1B,
            0xB80E,
            0x4EF4,
            0x22BB,
            0x2A11,
        ),
    ),
}


def parse_command(raw: str) -> Command:
    aliases = {
        "on": "fan-on",
        "off": "fan-off",
    }
    key = aliases.get(raw, raw)
    if key not in COMMANDS:
        known = ", ".join(sorted(COMMANDS))
        raise ValueError(f"Unknown command {raw!r}. Expected one of: {known}")
    return COMMANDS[key]


def burst_steps(
    command: Command,
    interval_s: float = BURST_INTERVAL_S,
    duration_s: float = BURST_DURATION_S,
    end_hold_s: float = END_HOLD_S,
) -> list[tuple[tuple[int, ...], float]]:
    steps: list[tuple[tuple[int, ...], float]] = []
    elapsed = 0.0
    use_a = True
    while elapsed < duration_s:
        words = command.packet_a if use_a else command.packet_b
        steps.append((words, interval_s))
        elapsed += interval_s
        use_a = not use_a
    steps.append((tuple(END_PACKET), end_hold_s))
    return steps
