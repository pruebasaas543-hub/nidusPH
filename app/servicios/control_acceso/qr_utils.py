"""
Generación de QR como imagen PNG en base64 — sin archivos temporales.
Usa qrcode + Pillow (ya instalados).
"""
import io, base64
import qrcode
from qrcode.image.pil import PilImage


def generar_qr_base64(contenido: str, box_size: int = 8, border: int = 3) -> str:
    """Devuelve la imagen QR como data:image/png;base64,... lista para <img src="">."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(contenido)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#042243", back_color="white", image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"
