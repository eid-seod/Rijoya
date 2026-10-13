import re
import unicodedata
from pathlib import Path
from uuid import uuid4
from werkzeug.utils import secure_filename
from flask import current_app

EGYPT_GOVERNORATES = [
    "القاهرة", "الجيزة", "الإسكندرية", "القليوبية", "البحيرة", "مطروح",
    "دمياط", "الدقهلية", "كفر الشيخ", "الغربية", "المنوفية", "الشرقية",
    "بورسعيد", "الإسماعيلية", "السويس", "شمال سيناء", "جنوب سيناء",
    "بني سويف", "الفيوم", "المنيا", "أسيوط", "سوهاج", "قنا", "الأقصر",
    "أسوان", "البحر الأحمر", "الوادي الجديد",
]


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value or f"item-{uuid4().hex[:8]}"


def save_image(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    original = secure_filename(file_storage.filename)
    ext = Path(original).suffix.lower().lstrip(".")
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        raise ValueError("صيغة الصورة غير مدعومة. استخدم PNG أو JPG أو WEBP أو GIF.")
    header = file_storage.stream.read(12)
    file_storage.stream.seek(0)
    valid = {
        "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": header.startswith(b"\xff\xd8\xff"),
        "jpeg": header.startswith(b"\xff\xd8\xff"),
        "gif": header.startswith((b"GIF87a", b"GIF89a")),
        "webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
    }.get(ext, False)
    if not valid:
        raise ValueError("محتوى الملف لا يبدو صورة صالحة بالصيغة المحددة.")
    name = f"{uuid4().hex}.{ext}"
    target = Path(current_app.config["UPLOAD_FOLDER"]) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(target)
    return name


def shipping_fee(governorate, city="", area=""):
    from models.models import ShippingRate
    rows = ShippingRate.query.filter_by(governorate=governorate, is_active=True).all()
    if not rows:
        return None
    city = (city or "").strip()
    area = (area or "").strip()
    for row in rows:
        if row.area and row.city and row.city == city and row.area == area:
            return row.fee
    for row in rows:
        if row.city and not row.area and row.city == city:
            return row.fee
    for row in rows:
        if not row.city and not row.area:
            return row.fee
    return None
