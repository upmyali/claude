import json
import os
import re
from playwright.sync_api import sync_playwright

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
HTML_FILE = '/home/user/claude/insider_pix_may2.html'
OUT_DIR = '/home/user/claude/screenshots'
os.makedirs(OUT_DIR, exist_ok=True)

# Top URLs to screenshot (url_fragment -> label, filename)
TARGETS = [
    ('moralmachine.net', 'Moral Machine (hidden gem)', 'moral_machine'),
    ('pix-media.com/books/LfgLEQAAQBAJ', 'Why Nothing Works (book)', 'book_why_nothing_works'),
    ('pix-media.com/movies/85350', 'Boyhood (movie)', 'movie_boyhood'),
    ('americaninequality.substack.com/subscribe', 'American Inequality Subscribe', 'ai_subscribe'),
    ('pix-media.com/shows/1407', 'Homeland (show)', 'show_homeland'),
    ('pix-media.com/podcasts/354668519', 'Freakonomics Podcast', 'podcast_freakonomics'),
]

with open(HTML_FILE, 'r') as f:
    html = f.read()

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path=CHROMIUM,
        args=['--no-sandbox', '--disable-setuid-sandbox']
    )
    ctx = browser.new_context(viewport={'width': 650, 'height': 12000})
    page = ctx.new_page()
    page.set_content(html, wait_until='networkidle')
    page.wait_for_timeout(2000)

    # Diagnostic: full page screenshot
    full_path = f'{OUT_DIR}/full_page.png'
    page.screenshot(path=full_path, full_page=True)
    print(f'Full page screenshot: {full_path}')

    for url_fragment, label, fname in TARGETS:
        print(f'\n--- {label} ({url_fragment}) ---')
        try:
            # Find anchors matching the URL fragment
            anchors = page.query_selector_all(f'a[href*="{url_fragment}"]')
            if not anchors:
                print(f'  No anchors found for {url_fragment}')
                continue
            print(f'  Found {len(anchors)} anchor(s)')

            # Get bounding boxes for all anchors (union)
            boxes = []
            for a in anchors:
                bb = a.bounding_box()
                if bb:
                    boxes.append(bb)

            if not boxes:
                print(f'  No bounding boxes found')
                continue

            # Strategy A: walk up DOM from first anchor to find a good table
            el = anchors[0]
            best_el = el
            for _ in range(15):
                parent = el.evaluate_handle('el => el.parentElement')
                if not parent:
                    break
                tag = parent.evaluate('el => el.tagName')
                bb = parent.bounding_box()
                if tag and tag.upper() == 'TABLE' and bb:
                    h = bb['height']
                    if 80 < h < 700:
                        best_el = parent
                        print(f'  Strategy A: found TABLE height={h:.0f}')
                        break
                    elif h >= 700:
                        # Too big, use previous best
                        break
                el = parent

            bb = best_el.bounding_box()
            if not bb:
                print(f'  No bounding box for best_el, falling back to anchor union')
                # Union of all anchor boxes
                x = min(b['x'] for b in boxes)
                y = min(b['y'] for b in boxes) - 20
                w = max(b['x'] + b['width'] for b in boxes) - x
                h = max(b['y'] + b['height'] for b in boxes) - y + 20
                bb = {'x': x, 'y': y, 'width': w, 'height': h}

            # Add padding
            pad = 20
            clip = {
                'x': max(0, bb['x'] - pad),
                'y': max(0, bb['y'] - pad),
                'width': bb['width'] + pad * 2,
                'height': bb['height'] + pad * 2,
            }
            print(f'  Clip: x={clip["x"]:.0f} y={clip["y"]:.0f} w={clip["width"]:.0f} h={clip["height"]:.0f}')

            out_path = f'{OUT_DIR}/{fname}.png'
            page.screenshot(path=out_path, clip=clip)
            print(f'  Saved: {out_path}')

        except Exception as e:
            print(f'  ERROR: {e}')

    browser.close()
print('\nDone!')
