from __future__ import annotations
from datetime import datetime

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
JALALI_MONTHS = ("فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند")

def gregorian_to_jalali(gy: int, gm: int, gd: int):
    gdim = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    jdim = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    gy2 = gy - 1600
    j_day = 365 * gy2 + (gy2 + 3)//4 - (gy2 + 99)//100 + (gy2 + 399)//400
    for i in range(gm - 1):
        j_day += gdim[i]
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        j_day += 1
    j_day += gd - 1
    j_day -= 79
    j_np, j_day = divmod(j_day, 12053)
    jy = 979 + 33*j_np + 4*(j_day // 1461)
    j_day %= 1461
    if j_day >= 366:
        jy += (j_day - 1) // 365
        j_day = (j_day - 1) % 365
    jm = 0
    while jm < 11 and j_day >= jdim[jm]:
        j_day -= jdim[jm]
        jm += 1
    return jy, jm + 1, j_day + 1

def format_dual_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    dt = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(text, fmt)
            break
        except ValueError:
            pass
    if not dt:
        return f"🟦 <b>تاریخ:</b> {text}"
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    jalali = f"{jd:02d} {JALALI_MONTHS[jm-1]} {jy}".translate(PERSIAN_DIGITS)
    greg = dt.strftime("%d %b %Y")
    return f"🟦 <b>{jalali}</b>  <i>• {greg}</i>"
