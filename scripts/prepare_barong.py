"""One-time preparation of the restored login mascot, not a runtime dependency."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFilter

root = Path('/app/frontend/public/assets')
image = Image.open(root / 'barong-complete.webp').convert('RGBA')
# Remove neutral checker pixels left in small negative spaces by the matting tool.
pixels = image.load()
for box in [(90, 448, 162, 530), (171, 467, 211, 532), (694, 437, 753, 521), (752, 478, 820, 548)]:
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            r, g, b, a = pixels[x, y]
            if min(r, g, b) > 145 and max(r, g, b) - min(r, g, b) < 26:
                pixels[x, y] = (r, g, b, 0)
image.save(root / 'barong-complete.webp', quality=96)
# Extract real photographic iris/pupil textures. The base eye underneath is
# reconstructed from its amber ring, avoiding duplicate pupils during gaze.
base = image.copy()
for name, cx, cy in [('left', 339, 669), ('right', 516, 669)]:
    radius = 27
    crop = image.crop((cx-radius, cy-radius, cx+radius, cy+radius))
    mask = Image.new('L', crop.size)
    ImageDraw.Draw(mask).ellipse((1, 1, radius*2-2, radius*2-2), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1))
    crop.putalpha(mask)
    crop.save(root / f'barong-eye-{name}.webp', quality=98)
    bp = base.load()
    for y in range(cy-radius, cy+radius):
        for x in range(cx-radius, cx+radius):
            distance = math.hypot(x-cx, y-cy)
            if distance < radius:
                angle = math.atan2(y-cy, x-cx)
                sample = pixels[round(cx+math.cos(angle)*31), round(cy+math.sin(angle)*31)]
                bp[x,y] = sample
base.save(root / 'barong-gaze-base.webp', quality=96)
print('Prepared complete crown, clean alpha and two textured eye layers.')