#!/usr/bin/env python3
"""Decodes base64 data URI images via an interactive menu."""

import base64
import io
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required. Install it with:\n    pip install Pillow")

# ── Constants ────────────────────────────────────────────────────────────────

DATA_URI_RE = re.compile(
    r"\[(?P<name>[^\]]+)\]:\s*<?data:image/(?P<ext>[a-zA-Z0-9.+-]+);base64,"
    r"(?P<data>[A-Za-z0-9+/=\s]+?)(?:>|$|\[)",
    re.DOTALL,
)

PIL_FORMAT: dict[str, str] = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "png": "PNG",
}

INPUT_FILENAME = "decode_input.txt"
INPUT_TEMPLATE = """\
# Paste your data URIs below and save the file:
#
#   [image_name]: <data:image/png;base64,iVBORw0KGgo...>
#   [other_image]: <data:image/jpeg;base64,/9j/4AAQSkZ...>
#
# The name in brackets will be used as the output filename.
# You can paste multiple blocks one after another.

"""


# ── Data model ───────────────────────────────────────────────────────────────


@dataclass
class ExportOptions:
    fmt: str
    quality: int
    max_size: int | None
    out_dir: Path


# ── UI helpers ───────────────────────────────────────────────────────────────


def _read(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(0)


def choose(question: str, options: list[str], default: str) -> str:
    """Numbered menu. Returns the selected option string."""
    print(f"  {question}:")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if opt == default else ""
        print(f"    {i}. {opt}{marker}")
    default_idx = options.index(default) + 1
    while True:
        raw = _read(f"  > [{default_idx}] ")
        if not raw:
            return default
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print(f"    Enter a number between 1 and {len(options)}.")


def confirm(question: str, default: bool = True) -> bool:
    """y/n prompt."""
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        raw = _read(f"  {question} {hint}: ").lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False


def ask(question: str, default: str = "") -> str:
    """Free-text prompt with an optional default."""
    hint = f" [{default}]" if default else ""
    while True:
        raw = _read(f"  {question}{hint}: ")
        if raw:
            return raw
        if default is not None:
            return default


def wait_for_input(path: Path) -> None:
    print(f"  File created: {path}")
    print("  Open it, paste the data URIs, save it, then come back here.")
    print()
    _read("  Press Enter when ready...")


# ── Image processing ─────────────────────────────────────────────────────────


def _fix_padding(b64: str) -> str:
    missing = len(b64) % 4
    return b64 + "=" * (4 - missing) if missing else b64


def _flatten_alpha(img: "Image.Image") -> "Image.Image":
    """Composite an RGBA/LA/P image onto a white background for JPEG output."""
    img = img.convert("RGBA")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[-1])
    return bg


def iter_images(text: str) -> Iterator[tuple[str, bytes]]:
    for match in DATA_URI_RE.finditer(text):
        name = match.group("name").strip()
        b64 = _fix_padding(re.sub(r"\s+", "", match.group("data")))
        try:
            yield name, base64.b64decode(b64)
        except Exception as exc:
            print(f"  ! Could not decode '{name}': {exc}", file=sys.stderr)


def save_image(name: str, raw: bytes, opts: ExportOptions) -> Path | None:
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        print(f"  ! '{name}' is not a valid image: {exc}", file=sys.stderr)
        return None

    pil_fmt = PIL_FORMAT[opts.fmt]
    ext = "jpg" if pil_fmt == "JPEG" else opts.fmt

    if pil_fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
        img = _flatten_alpha(img)
    elif img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")

    if opts.max_size and max(img.size) > opts.max_size:
        img.thumbnail((opts.max_size, opts.max_size), Image.Resampling.LANCZOS)

    opts.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = opts.out_dir / f"{name}.{ext}"

    extra = {"quality": opts.quality, "optimize": True} if pil_fmt in ("JPEG", "WEBP") else {}
    img.save(out_path, pil_fmt, **extra)
    return out_path


# ── Workflow steps ───────────────────────────────────────────────────────────


def prepare_input_file(path: Path) -> None:
    if not path.exists():
        path.write_text(INPUT_TEMPLATE, encoding="utf-8")
    print()
    wait_for_input(path)


def collect_options(cwd: Path) -> ExportOptions:
    print()
    print("  ── Export options ───────────────────────")
    print()

    fmt = choose("Output format", ["jpeg", "webp", "png"], default="jpeg")
    print()

    quality = 80
    if fmt != "png":
        try:
            quality = max(1, min(100, int(ask("Quality (1-100)", default="80"))))
        except ValueError:
            pass

    max_size: int | None = None
    try:
        ms = int(ask("Max size in pixels (0 = no limit)", default="0"))
        max_size = ms or None
    except ValueError:
        pass

    subfolder = ask("Output subfolder (Enter = current directory)")
    out_dir = (cwd / subfolder) if subfolder else cwd

    return ExportOptions(fmt=fmt, quality=quality, max_size=max_size, out_dir=out_dir)


def process_images(input_file: Path, opts: ExportOptions, cwd: Path) -> int:
    print()
    print("  Processing...")
    print()

    text = input_file.read_text(encoding="utf-8", errors="ignore")
    count = 0
    for name, raw in iter_images(text):
        path = save_image(name, raw, opts)
        if path:
            kb = path.stat().st_size / 1024
            print(f"  ✓  {name}  →  {path.relative_to(cwd)}  ({kb:.1f} KB)")
            count += 1
    return count


def cleanup(input_file: Path) -> None:
    if confirm(f"Delete '{INPUT_FILENAME}'?", default=True):
        input_file.unlink(missing_ok=True)
        print(f"  '{INPUT_FILENAME}' deleted.")


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    cwd = Path.cwd()
    input_file = cwd / INPUT_FILENAME

    print()
    print("╔══════════════════════════════════╗")
    print("║        Image Decoder             ║")
    print("╚══════════════════════════════════╝")
    print()

    prepare_input_file(input_file)
    opts = collect_options(cwd)
    count = process_images(input_file, opts, cwd)

    print()
    if count == 0:
        print("  No valid images found in the input file.", file=sys.stderr)
        sys.exit(1)

    label = "image" if count == 1 else "images"
    dest = opts.out_dir.relative_to(cwd) if opts.out_dir != cwd else "current directory"
    print(f"  Done: {count} {label} saved to {dest}")

    print()
    cleanup(input_file)
    print()


if __name__ == "__main__":
    main()
