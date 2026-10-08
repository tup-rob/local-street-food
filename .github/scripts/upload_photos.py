"""
Upload all vendor photos from imgix → Cloudinary.
Cloudinary fetches from imgix server-to-server (no Referer, no IP block).
Photos stored permanently under localstreetfood/{slug}/{index}.
Resumes safely: skips vendors whose photos are already Cloudinary URLs.
Updates vendors.json in place with new URLs.
"""

import json
import os
import sys
import time
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


def is_cloudinary(url):
    return url and "res.cloudinary.com" in url


def upload_url(url, public_id):
    """Upload a remote URL to Cloudinary. Returns the secure_url or None on failure."""
    try:
        result = cloudinary.uploader.upload(
            url,
            public_id=public_id,
            overwrite=False,           # skip if already uploaded
            resource_type="image",
            timeout=30,
        )
        return result["secure_url"]
    except Exception as e:
        print(f"    FAIL {public_id}: {e}", flush=True)
        return None


def main():
    with open(VENDORS_FILE, encoding="utf-8") as f:
        vendors = json.load(f)

    total = len(vendors)
    changed = 0
    skipped = 0
    failed = 0

    for i, v in enumerate(vendors):
        slug = v.get("slug") or f"vendor-{v['id']}"
        name = v.get("name", slug)

        # Collect all photos to upload
        all_photos = []
        if v.get("photo"):
            all_photos.append(("photo", v["photo"]))
        for j, p in enumerate(v.get("photos", [])):
            all_photos.append((f"photos.{j}", p))

        # Check if already done (all photos are Cloudinary URLs)
        if all(is_cloudinary(url) for _, url in all_photos if url):
            skipped += 1
            continue

        has_imgix = any("imgix.net" in (url or "") for _, url in all_photos)
        if not has_imgix:
            skipped += 1
            continue

        print(f"[{i+1}/{total}] {name}", flush=True)
        vendor_changed = False

        for idx, (field, src_url) in enumerate(all_photos):
            if not src_url or is_cloudinary(src_url):
                continue
            if "imgix.net" not in src_url:
                continue

            public_id = f"{FOLDER}/{slug}/{idx}"
            new_url = upload_url(src_url, public_id)

            if new_url:
                if field == "photo":
                    v["photo"] = new_url
                else:
                    photo_idx = int(field.split(".")[1])
                    v["photos"][photo_idx] = new_url
                vendor_changed = True
                changed += 1
                print(f"    ✓ {field}", flush=True)
            else:
                failed += 1
                # Small back-off on failure to avoid hammering the API
                time.sleep(2)

        # Save after every vendor so we don't lose progress if the job times out
        if vendor_changed:
            with open(VENDORS_FILE, "w", encoding="utf-8") as f:
                json.dump(vendors, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nDone. uploaded={changed}, skipped={skipped}, failed={failed}", flush=True)
    if failed > 0:
        sys.exit(1)  # non-zero so the action is marked failed (will show in UI)


if __name__ == "__main__":
    main()
