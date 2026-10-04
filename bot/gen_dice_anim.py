"""
Generate animated dice roll GIFs.
Each GIF: die appears small (far away), tumbles with random faces while
scaling up, slows down, then locks onto the final result face.
Output: assets/dice/dice_roll_1.gif ... dice_roll_6.gif
"""
import random
import os
from PIL import Image, ImageFilter, ImageEnhance

DICE_DIR = os.path.join(os.path.dirname(__file__), "assets", "dice")
random.seed(42)  # reproducible random sequences

def make_roll_gif(result: int):
    # Load all 6 face images
    faces = {}
    for i in range(1, 7):
        path = os.path.join(DICE_DIR, f"dice_{i}.png")
        img = Image.open(path).convert("RGBA")
        faces[i] = img

    W, H = faces[1].size
    # Discord dark bg color
    BG = (43, 45, 49, 255)

    # --- Build frame sequence ---
    # (scale, face, duration_ms, blur)
    sequence = []

    # Phase 1: tumbling in — small & fast, random faces
    tumble_scales  = [0.18, 0.26, 0.36, 0.48, 0.60, 0.72]
    tumble_durations = [70,   70,   80,   90,  100,  110]
    for scale, dur in zip(tumble_scales, tumble_durations):
        face = random.choice([f for f in range(1, 7) if f != result])
        sequence.append((scale, face, dur, 1.2))  # slight blur when small

    # Phase 2: slowing down — approaching faces
    approach_scales   = [0.82, 0.90, 0.97]
    approach_durations = [130,  160,  200]
    for scale, dur in zip(approach_scales, approach_durations):
        face = random.choice([f for f in range(1, 7) if f != result])
        sequence.append((scale, face, dur, 0))

    # Phase 3: land — final result, full size, hold
    sequence.append((1.02, result, 180, 0))   # slight overshoot
    sequence.append((0.97, result, 80, 0))    # bounce back
    sequence.append((1.00, result, 900, 0))   # hold result

    frames = []
    durations = []

    for scale, face_id, dur, blur_r in sequence:
        bg = Image.new("RGBA", (W, H), BG)
        face_img = faces[face_id].copy()

        new_w = max(1, int(W * scale))
        new_h = max(1, int(H * scale))
        resized = face_img.resize((new_w, new_h), Image.LANCZOS)

        # Optional motion blur for early frames
        if blur_r > 0:
            resized = resized.filter(ImageFilter.GaussianBlur(radius=blur_r))

        x = (W - new_w) // 2
        y = (H - new_h) // 2
        bg.paste(resized, (x, y), resized)

        # Convert to P (palette) for GIF — quantize preserving RGBA
        rgb_frame = bg.convert("RGB")
        frames.append(rgb_frame)
        durations.append(dur)

    out_path = os.path.join(DICE_DIR, f"dice_roll_{result}.gif")
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"  Generated {out_path}  ({len(frames)} frames)")


if __name__ == "__main__":
    print("Generating dice roll animations...")
    for i in range(1, 7):
        make_roll_gif(i)
    print("Done!")
