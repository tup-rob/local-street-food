"""
Upload all vendor photos from imgix → Cloudinary.

Strategy: download each image from imgix using browser headers
(GitHub Actions servers can do this; Cloudinary's fetch cannot),
then upload the raw bytes to Cloudinary. No custom-header restrictions.

Resumes safely: skips vendors already on Cloudinary URLs.
Updates vendors.json in place after each vendor.
"""

import json
import os
import sys
import time
import requests
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True,
)

VENDORS_FILE = "vendors.json"
FOLDER = "localstreetfood"

DOWNLOAD_HEADERS = {
    "Referer": "https://feast-it.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def is_cloudinary(url):
    return bool(url and "res.cloudinary.com" in url)


def fetch_image(url):
    """Download image bytes from imgix with browser headers. Returns bytes or None."""
    try:
        r = requests.get(url, headers=DOWNLOAD_HEADERS, timeout=20)
        if r.status_code == 200 and r.content:
            return r.content
        print(f"    HTTP {r.status_code} for {url}", flush=True)
        return None
    except Exception as e:
        print(f"    Download error: {e}", flush=True)
        return None


def upload_bytes(data, public_id):
    """Upload raw image bytes to Cloudinary. Returns secure_url or None."""
    try:
        result = cloudinary.uploader.upload(
            data,
            public_id=public_id,
            overwrite=False,
            resource_type="image",
        )
        return result["secure_url"]
    except Exception as e:
        print(f"    Cloudinary error {public_id}: {e}", flush=True)
        return None


def main():
    with open(VENDORS_FILE, encoding="utf-8") as f:
        vendors = json.load(f)

    total = len(vendors)
    uploaded = 0
    skipped = 0
    failed = 0

    for i, v in enumerate(vendors):
        slug = v.get("slug") or f"vendor-{v['id']}"
        name = v.get("name", slug)

        # Build list of (field_key, url) pairs
        all_photos = []
        if v.get("photo"):
            all_photos.append(("photo", v["photo"]))
        for j, p in enumerate(v.get("photos", [])):
            if p:
                all_photos.append((f"photos.{j}", p))

        # Skip if every photo is already on Cloudinary
        if all(is_cloudinary(url) for _, url in all_photos):
            skipped += 1
            continue

        # Skip if no imgix photos to migrate
        has_imgix = any("imgix.net" in (url or "") for _, url in all_photos)
        if not has_imgix:
            skipped += 1
            continue

        print(f"[{i+1}/{total}] {name}", flush=True)
        vendor_changed = False

        for idx, (field, src_url) in enumerate(all_photos):
            if not src_url or is_cloudinary(src_url) or "imgix.net" not in src_url:
                continue

            public_id = f"{FOLDER}/{slug}/{idx}"

            img_bytes = fetch_image(src_url)
            if img_bytes is None:
                failed += 1
                time.sleep(1)
                continue

            new_url = upload_bytes(img_bytes, public_id)
            if new_url:
                if field == "photo":
                    v["photo"] = new_url
                else:
                    photo_idx = int(field.split(".")[1])
                    v["photos"][photo_idx] = new_url
                vendor_changed = True
                uploaded += 1
                print(f"    ✓ {field} ({len(img_bytes)//1024}KB)", flush=True)
            else:
                failed += 1
                time.sleep(2)

        # Save progress after each vendor so a timeout doesn't lose work
        if vendor_changed:
            with open(VENDORS_FILE, "w", encoding="utf-8") as f:
                json.dump(vendors, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nDone. uploaded={uploaded}, skipped={skipped}, failed={failed}", flush=True)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
