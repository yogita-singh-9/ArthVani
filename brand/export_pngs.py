import os
import math
from PIL import Image, ImageDraw, ImageFont

os.makedirs("brand/png", exist_ok=True)

MAROON = (42, 14, 34)       # #2A0E22
ACCENT = (184, 51, 106)     # #B8336A
WHITE = (255, 255, 255)
MUTED = (210, 180, 198)     # #D2B4C6
ACCENT_LT = (251, 207, 232) # #FBCFE8

def draw_bubble_and_rupee(draw, scale=1.0, offset=(0, 0), stroke_color=(255,255,255), stroke_w=28):
    ox, oy = offset
    w = stroke_w * scale
    
    # We can draw smooth cubic bezier and lines by stepping t
    def bezier_point(p0, p1, p2, p3, t):
        return (
            (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0],
            (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
        )

    def arc_points(cx, cy, r, a_start, a_end, steps=30):
        pts = []
        for i in range(steps + 1):
            theta = math.radians(a_start + (a_end - a_start) * (i / steps))
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
        return pts

    # Speech bubble polyline
    bubble_pts = []
    # Top straight: (172, 102) to (338, 102)
    bubble_pts.extend([(172, 102), (338, 102)])
    # Top-right arc: cx=338, cy=178, r=76, from -90 to 0
    bubble_pts.extend(arc_points(338, 178, 76, -90, 0))
    # Right straight: (414, 178) to (414, 306)
    bubble_pts.append((414, 306))
    # Bottom-right arc: cx=338, cy=306, r=76, from 0 to 90
    bubble_pts.extend(arc_points(338, 306, 76, 0, 90))
    # Bottom straight to tail join: (338, 382) to (214, 382)
    bubble_pts.append((214, 382))
    # Tail diagonal down: (214, 382) to (156, 442)
    bubble_pts.append((156, 442))
    # Tail tip arc to (140, 434)
    bubble_pts.extend([(148, 444), (140, 434)])
    # Tail straight up to (140, 376)
    bubble_pts.append((140, 376))
    # Curve back to left wall: C (140, 342), (96, 332), (96, 296)
    for i in range(21):
        t = i / 20.0
        bubble_pts.append(bezier_point((140, 376), (140, 342), (96, 332), (96, 296), t))
    # Left straight: (96, 296) to (96, 178)
    bubble_pts.append((96, 178))
    # Top-left arc: cx=172, cy=178, r=76, from 180 to 270
    bubble_pts.extend(arc_points(172, 178, 76, 180, 270))
    bubble_pts.append((172, 102))

    # Scale and translate bubble points
    scaled_bubble = [(ox + x * scale, oy + y * scale) for x, y in bubble_pts]
    for i in range(len(scaled_bubble) - 1):
        p1 = scaled_bubble[i]
        p2 = scaled_bubble[i+1]
        draw.line([p1, p2], fill=stroke_color, width=int(round(w)))
        # rounded joints
        r_half = w / 2.0
        draw.ellipse([p1[0]-r_half, p1[1]-r_half, p1[0]+r_half, p1[1]+r_half], fill=stroke_color)

    # Rupee Symbol
    # Bar 1
    p1 = (ox + 168 * scale, oy + 166 * scale)
    p2 = (ox + 346 * scale, oy + 166 * scale)
    draw.line([p1, p2], fill=stroke_color, width=int(round(w)))
    r_half = w / 2.0
    draw.ellipse([p1[0]-r_half, p1[1]-r_half, p1[0]+r_half, p1[1]+r_half], fill=stroke_color)
    draw.ellipse([p2[0]-r_half, p2[1]-r_half, p2[0]+r_half, p2[1]+r_half], fill=stroke_color)

    # Bar 2
    p1 = (ox + 168 * scale, oy + 215 * scale)
    p2 = (ox + 346 * scale, oy + 215 * scale)
    draw.line([p1, p2], fill=stroke_color, width=int(round(w)))
    draw.ellipse([p1[0]-r_half, p1[1]-r_half, p1[0]+r_half, p1[1]+r_half], fill=stroke_color)
    draw.ellipse([p2[0]-r_half, p2[1]-r_half, p2[0]+r_half, p2[1]+r_half], fill=stroke_color)

    # Bowl
    bowl_pts = []
    # (256, 166) -> C (298, 166), (298, 220), (286, 240)
    for i in range(21):
        t = i / 20.0
        bowl_pts.append(bezier_point((256, 166), (298, 166), (298, 220), (286, 240), t))
    # -> C (274, 260), (230, 264), (186, 264)
    for i in range(1, 21):
        t = i / 20.0
        bowl_pts.append(bezier_point((286, 240), (274, 260), (230, 264), (186, 264), t))

    scaled_bowl = [(ox + x * scale, oy + y * scale) for x, y in bowl_pts]
    for i in range(len(scaled_bowl) - 1):
        bp1 = scaled_bowl[i]
        bp2 = scaled_bowl[i+1]
        draw.line([bp1, bp2], fill=stroke_color, width=int(round(w)))
        draw.ellipse([bp1[0]-r_half, bp1[1]-r_half, bp1[0]+r_half, bp1[1]+r_half], fill=stroke_color)

    # Leg
    p1 = (ox + 186 * scale, oy + 264 * scale)
    p2 = (ox + 276 * scale, oy + 345 * scale)
    draw.line([p1, p2], fill=stroke_color, width=int(round(w)))
    draw.ellipse([p1[0]-r_half, p1[1]-r_half, p1[0]+r_half, p1[1]+r_half], fill=stroke_color)
    draw.ellipse([p2[0]-r_half, p2[1]-r_half, p2[0]+r_half, p2[1]+r_half], fill=stroke_color)

# 1. Render App Icon (512x512)
def make_app_icon(size=512):
    scale_fac = 4
    canvas_s = size * scale_fac
    img = Image.new("RGBA", (canvas_s, canvas_s), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    # Rounded rect background
    r = int(112 * scale_fac)
    draw.rounded_rectangle([0, 0, canvas_s, canvas_s], radius=r, fill=MAROON)
    # Centered mark (0.7 scale)
    inner_s = 512 * scale_fac * 0.7
    offset = ((canvas_s - inner_s)/2, (canvas_s - inner_s)/2)
    draw_bubble_and_rupee(draw, scale=scale_fac * 0.7, offset=offset, stroke_color=WHITE, stroke_w=28)
    return img.resize((size, size), Image.Resampling.LANCZOS)

# 2. Render Favicon (Filled silhouette with knockout)
def make_favicon(size=32):
    scale_fac = 16
    canvas_s = size * scale_fac
    img = Image.new("RGBA", (canvas_s, canvas_s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw filled bubble in ACCENT
    s = canvas_s / 512.0
    # First solid bubble
    bubble_poly = []
    def arc_pts(cx, cy, rad, a1, a2, steps=30):
        return [(cx + rad*math.cos(math.radians(a1 + (a2-a1)*(i/steps))),
                 cy + rad*math.sin(math.radians(a1 + (a2-a1)*(i/steps)))) for i in range(steps+1)]
    bubble_poly.extend([(172*s, 102*s), (338*s, 102*s)])
    bubble_poly.extend([(x*s, y*s) for x, y in arc_pts(338, 178, 76, -90, 0)])
    bubble_poly.append((414*s, 306*s))
    bubble_poly.extend([(x*s, y*s) for x, y in arc_pts(338, 306, 76, 0, 90)])
    bubble_poly.append((214*s, 382*s))
    bubble_poly.append((156*s, 442*s))
    bubble_poly.extend([(148*s, 444*s), (140*s, 434*s)])
    bubble_poly.append((140*s, 376*s))
    def bez_pt(p0, p1, p2, p3, t):
        return ((1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t**2*p2[0] + t**3*p3[0],
                (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t**2*p2[1] + t**3*p3[1])
    for i in range(21):
        t = i / 20.0
        p = bez_pt((140, 376), (140, 342), (96, 332), (96, 296), t)
        bubble_poly.append((p[0]*s, p[1]*s))
    bubble_poly.append((96*s, 178*s))
    bubble_poly.extend([(x*s, y*s) for x, y in arc_pts(172, 178, 76, 180, 270)])
    
    # Fill body
    draw.polygon(bubble_poly, fill=ACCENT)
    # Stroke contour to match stroke thickness
    draw_bubble_and_rupee(draw, scale=s, offset=(0,0), stroke_color=ACCENT, stroke_w=28)
    # Knockout rupee in transparent
    mask_img = Image.new("L", (canvas_s, canvas_s), 255)
    mask_draw = ImageDraw.Draw(mask_img)
    # Draw rupee on mask with black
    w = 34 * s
    r_h = w / 2.0
    # bar 1
    p1 = (168*s, 166*s); p2 = (346*s, 166*s)
    mask_draw.line([p1, p2], fill=0, width=int(round(w)))
    mask_draw.ellipse([p1[0]-r_h, p1[1]-r_h, p1[0]+r_h, p1[1]+r_h], fill=0)
    mask_draw.ellipse([p2[0]-r_h, p2[1]-r_h, p2[0]+r_h, p2[1]+r_h], fill=0)
    # bar 2
    p1 = (168*s, 215*s); p2 = (346*s, 215*s)
    mask_draw.line([p1, p2], fill=0, width=int(round(w)))
    mask_draw.ellipse([p1[0]-r_h, p1[1]-r_h, p1[0]+r_h, p1[1]+r_h], fill=0)
    mask_draw.ellipse([p2[0]-r_h, p2[1]-r_h, p2[0]+r_h, p2[1]+r_h], fill=0)
    # bowl
    bowl_pts = []
    for i in range(21):
        t = i / 20.0
        p = bez_pt((256, 166), (298, 166), (298, 220), (286, 240), t)
        bowl_pts.append((p[0]*s, p[1]*s))
    for i in range(1, 21):
        t = i / 20.0
        p = bez_pt((286, 240), (274, 260), (230, 264), (186, 264), t)
        bowl_pts.append((p[0]*s, p[1]*s))
    for i in range(len(bowl_pts)-1):
        mask_draw.line([bowl_pts[i], bowl_pts[i+1]], fill=0, width=int(round(w)))
        mask_draw.ellipse([bowl_pts[i][0]-r_h, bowl_pts[i][1]-r_h, bowl_pts[i][0]+r_h, bowl_pts[i][1]+r_h], fill=0)
    # leg
    p1 = (186*s, 264*s); p2 = (276*s, 345*s)
    mask_draw.line([p1, p2], fill=0, width=int(round(w)))
    mask_draw.ellipse([p1[0]-r_h, p1[1]-r_h, p1[0]+r_h, p1[1]+r_h], fill=0)
    mask_draw.ellipse([p2[0]-r_h, p2[1]-r_h, p2[0]+r_h, p2[1]+r_h], fill=0)

    # Apply mask to alpha channel
    r_ch, g_ch, b_ch, a_ch = img.split()
    final_a = Image.composite(a_ch, Image.new("L", (canvas_s, canvas_s), 0), mask_img)
    img.putalpha(final_a)
    return img.resize((size, size), Image.Resampling.LANCZOS)

# 3. Social Card (1200x630)
def make_social_card():
    W, H = 1200, 630
    scale_fac = 2
    canvas_w, canvas_h = W * scale_fac, H * scale_fac
    img = Image.new("RGB", (canvas_w, canvas_h), MAROON)
    draw = ImageDraw.Draw(img)

    # Mark at (120, 205), size 220x220
    mark_scale = (220.0 / 512.0) * scale_fac
    draw_bubble_and_rupee(draw, scale=mark_scale, offset=(120*scale_fac, 205*scale_fac), stroke_color=WHITE, stroke_w=28)

    # Typography
    try:
        font_large = ImageFont.truetype("arialbd.ttf", 88 * scale_fac)
        font_sub = ImageFont.truetype("arial.ttf", 34 * scale_fac)
    except:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.text((380*scale_fac, 235*scale_fac), "ArthVani", fill=WHITE, font=font_large)
    draw.text((385*scale_fac, 350*scale_fac), "Speak, and the ledger is done.", fill=MUTED, font=font_sub)

    return img.resize((W, H), Image.Resampling.LANCZOS)

# Generate and save all requested PNG exports
print("Generating PNG exports...")
fav16 = make_favicon(16)
fav16.save("brand/png/favicon-16.png")
print("  - brand/png/favicon-16.png")

fav32 = make_favicon(32)
fav32.save("brand/png/favicon-32.png")
print("  - brand/png/favicon-32.png")

apple180 = make_app_icon(180)
apple180.save("brand/png/apple-touch-icon.png")
print("  - brand/png/apple-touch-icon.png")

app512 = make_app_icon(512)
app512.save("brand/png/app-icon.png")
print("  - brand/png/app-icon.png")

social = make_social_card()
social.save("brand/png/social-card.png")
print("  - brand/png/social-card.png")
print("Done!")

