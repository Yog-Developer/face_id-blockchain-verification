import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

MAX_IMAGE_SIZE_BYTES = 500 * 1024
TARGET_IMAGE_SIZE_BYTES = 480 * 1024


class FaceSearchError(Exception):
    pass


def get_api_key():
    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        raise FaceSearchError("SERPAPI_KEY is missing from .env")

    return api_key.strip()


def get_platform(url):
    try:
        domain = urlparse(url).netloc

        if not domain:
            return "unknown"

        return domain.replace("www.", "")

    except Exception:
        return "unknown"


def prepare_image(image_path):
    path = Path(image_path)

    if not path.exists():
        raise FaceSearchError(f"Image not found: {image_path}")

    if path.stat().st_size <= MAX_IMAGE_SIZE_BYTES:
        return str(path), None

    print("Image is larger than 500 KB. Compressing temporarily...")

    try:
        image = Image.open(path)
        image = image.convert("RGB")

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False
        )

        temp_path = temp_file.name
        temp_file.close()

        quality = 85

        image.save(
            temp_path,
            "JPEG",
            optimize=True,
            quality=quality
        )

        while (
            os.path.getsize(temp_path) > TARGET_IMAGE_SIZE_BYTES
            and quality > 30
        ):
            quality -= 10

            image.save(
                temp_path,
                "JPEG",
                optimize=True,
                quality=quality
            )

        if os.path.getsize(temp_path) > MAX_IMAGE_SIZE_BYTES:
            width, height = image.size

            while (
                os.path.getsize(temp_path) > TARGET_IMAGE_SIZE_BYTES
                and width > 300
                and height > 300
            ):
                width = int(width * 0.8)
                height = int(height * 0.8)

                resized = image.resize(
                    (width, height)
                )

                resized.save(
                    temp_path,
                    "JPEG",
                    optimize=True,
                    quality=70
                )

        if os.path.getsize(temp_path) > MAX_IMAGE_SIZE_BYTES:
            raise FaceSearchError(
                "Could not compress image below 500 KB."
            )

        print(
            f"Compressed image size: "
            f"{os.path.getsize(temp_path) / 1024:.1f} KB"
        )

        return temp_path, temp_path

    except FaceSearchError:
        raise

    except Exception as error:
        raise FaceSearchError(
            f"Could not prepare image: {error}"
        ) from error


def upload_image(image_path, api_key):
    prepared_path, temporary_path = prepare_image(
        image_path
    )

    print("Uploading image to SerpApi...")

    try:
        with open(prepared_path, "rb") as image_file:
            response = requests.post(
                "https://serpapi.com/image",
                data={"api_key": api_key},
                files={"image": image_file},
                timeout=60
            )

    except requests.RequestException as error:
        raise FaceSearchError(
            f"Upload request failed: {error}"
        ) from error

    finally:
        if temporary_path and os.path.exists(
            temporary_path
        ):
            os.remove(temporary_path)

    try:
        data = response.json()

    except ValueError:
        raise FaceSearchError(
            f"Invalid response from SerpApi: "
            f"{response.text[:500]}"
        )

    if response.status_code != 200:
        raise FaceSearchError(
            f"Upload failed: {data}"
        )

    image_id = data.get("image_id")

    if not image_id:
        raise FaceSearchError(
            f"No image_id returned: {data}"
        )

    return image_id


def search_google_lens(image_id, api_key):
    print("Searching Google Lens...")

    try:
        response = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_lens",
                "image_id": image_id,
                "api_key": api_key
            },
            timeout=60
        )

    except requests.RequestException as error:
        raise FaceSearchError(
            f"Search request failed: {error}"
        ) from error

    try:
        data = response.json()

    except ValueError:
        raise FaceSearchError(
            f"Invalid response from SerpApi: "
            f"{response.text[:500]}"
        )

    if response.status_code != 200:
        raise FaceSearchError(
            f"Google Lens search failed: {data}"
        )

    return data


def search_by_face(
    image_path: str,
    testing_mode: bool = True
):
    _ = testing_mode

    api_key = get_api_key()

    image_id = upload_image(
        image_path,
        api_key
    )

    data = search_google_lens(
        image_id,
        api_key
    )

    candidates = []
    seen_urls = set()

    for match in data.get(
        "visual_matches",
        []
    )[:20]:

        url = match.get("link", "")
        thumbnail = match.get("thumbnail", "")

        if not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        candidates.append(
            {
                "url": url,
                "thumbnail_url": thumbnail,
                "platform": get_platform(url),
                "api_confidence": 0.7
            }
        )

    print(
        f"Found {len(candidates)} candidates."
    )

    return candidates
