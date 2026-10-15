#!/usr/bin/env python3

import time

from rich.console import Console
from rich.live import Live
from rich.progress import ProgressColumn
from rich.text import Text


COLORS = [
    (255,  90,  80),
    (255, 170,  70),
    (245, 220,  80),
    (105, 210, 120),
    ( 75, 200, 210),
    (105, 145, 240),
    (190, 105, 230),
    (245, 105, 185),
]


def interpolate(a, b, t):
    """Linearly interpolate between two RGB colors."""
    return tuple(
        round(x + (y - x) * t)
        for x, y in zip(a, b)
    )


def gradient_color(position):
    """Return a color from the continuous cyclic gradient."""
    position %= len(COLORS)

    i = int(position)
    t = position - i

    return interpolate(
        COLORS[i],
        COLORS[(i + 1) % len(COLORS)],
        t,
    )


def animated_text(text, offset=0.0, spacing=0.35, style="bold"):
    """Apply a continuous color gradient across text."""
    result = Text()

    for i, character in enumerate(text):
        r, g, b = gradient_color(offset + i * spacing)

        result.append(
            character,
            style=f"{style} rgb({r},{g},{b})",
        )

    return result


class AnimatedTextColumn(ProgressColumn):
    """Progress column with a continuously moving color gradient."""

    def __init__(
        self,
        speed=3.0,
        spacing=0.35,
        style="bold",
    ):
        super().__init__()
        self.speed = speed
        self.spacing = spacing
        self.style = style
        self.start_time = time.monotonic()

    def render(self, task):
        elapsed = time.monotonic() - self.start_time

        return animated_text(
            task.description,
            offset=elapsed * self.speed,
            spacing=self.spacing,
            style=self.style,
        )


def animate_demo(
    text="UNRAVEL",
    fps=30,
    speed=3.0,
    spacing=0.35,
):
    """Continuously animate text until Ctrl+C."""
    console = Console()
    start_time = time.monotonic()

    with Live(
        "",
        console=console,
        refresh_per_second=fps,
        transient=False,
    ) as live:
        try:
            while True:
                elapsed = time.monotonic() - start_time

                live.update(
                    animated_text(
                        text,
                        offset=elapsed * speed,
                        spacing=spacing,
                    )
                )

                time.sleep(1 / fps)

        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    animate_demo("UNRAVEL")