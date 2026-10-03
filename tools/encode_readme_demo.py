"""Encode recorded PNG frames as small looping GIFs (optional dependency: Pillow).

python tools/encode_readme_demo.py build/readme-demo docs/assets/v0.3
Run tools/record_readme_demo.cjs first. Neither tool is a runtime dependency.
"""

import argparse
import json
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for language in ("en", "zh-CN"):
        directory = args.recording / language
        recording = json.loads((directory / "frames.json").read_text("utf-8"))
        frames = []
        for frame in recording["frames"]:
            with Image.open(directory / frame["file"]) as image:
                assert image.size == tuple(recording["size"])
                frames.append(
                    image.convert("RGB").quantize(
                        colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
                    )
                )
        target = args.output / f"demo.{language}.gif"
        durations = [frame["duration"] for frame in recording["frames"]]
        frames[0].save(
            target,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True,
            disposal=1,
        )
        with Image.open(target) as gif:
            assert gif.info["loop"] == 0
            assert gif.n_frames > 1
            actual_duration = 0
            for index in range(gif.n_frames):
                gif.seek(index)
                gif.load()
                actual_duration += gif.info["duration"]
            assert actual_duration == sum(durations)
            assert target.stat().st_size < 3 * 1024 * 1024, "Keep README downloads under 3 MiB"
            results.append(
                {
                    "file": target.name,
                    "bytes": target.stat().st_size,
                    "size": gif.size,
                    "frames": gif.n_frames,
                    "duration_ms": actual_duration,
                }
            )
    (args.recording / "encoding.json").write_text(json.dumps(results, indent=2) + "\n", "utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
