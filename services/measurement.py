from PyQt5.QtCore import QLineF


def format_length_points(start_point, end_point, pixels_per_meter=100, zero_text="0,00 m"):
    """Formate la longueur entre deux points en texte (m ou cm)."""
    if start_point is None or end_point is None:
        return zero_text

    line = QLineF(start_point, end_point)
    length_px = line.length()
    if length_px <= 0.01:
        return zero_text

    ppm = pixels_per_meter or 100
    if ppm <= 0:
        ppm = 100
    length_m = length_px / ppm
    return f"{length_m:.2f} m" if length_m >= 1 else f"{length_m*100:.1f} cm"


def format_area_m2(value):
    """Formate une aire en m² avec séparateur français."""
    if value is None:
        return "0,00 m²"
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", " ").replace(".", ",")
    return f"{formatted} m²"

