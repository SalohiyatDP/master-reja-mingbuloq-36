# Mingbuloq c-36 — Lotlar master rejasi

Bu loyiha `SHP_migbuloq_wgs84.zip` shapefile ichidagi **62 ta lotni** har birini alohida
master reja qilib ajratadi. Lotlarning **aniq shakli va o'lchami** shapefile'dagi
vektor koordinatalardan **aynan** olingan — hech qanday qayta chizish yoki taxmin yo'q.

## Nega bu yondashuv?

Oddiy AI'lar (ChatGPT va h.k.) chizmani rasm sifatida ko'rgani uchun lotning aniq
o'lchamini buzib qo'yadi. Bu yerda esa geometriya to'g'ridan-to'g'ri shapefile'dagi
koordinatalardan olinadi, shuning uchun o'lchamlar **100% saqlanadi**.

## ⚠️ Muhim: maydon o'lchami tuzatildi

Shapefile **WGS84 Web Mercator (EPSG:3857)** koordinata tizimida. Bu tizim Mingbuloq
kengligida (~40.8° shimoliy) maydonni taxminan **1.75 barobar katta** ko'rsatadi.
Shuning uchun har bir nuqta haqiqiy geografik koordinataga qaytarilib, keyin
**lokal tekislik (ENU) proyeksiyasi** orqali yer yuzidagi **haqiqiy metrga** o'tkazildi.

Buning to'g'riligi shundan bilinadi — hisoblangan maydonlar aniq yumaloq raqamlar
chiqdi (loyihalashda maqsad qilingan o'lchamlar): 20, 25, 30, 35, 40, 45 sotix va h.k.

- **Umumiy maydon:** ~17.43 ga (1742.6 sotix)
- **Lotlar soni:** 62 ta

## Natijalar (`output/` papkasi)

| Fayl / papka | Tavsif |
|--------------|--------|
| `output/dxf/lot_XX.dxf` | Har bir lot uchun alohida **DXF** — AutoCAD/LibreCAD'da ochiladi. Haqiqiy metrda, tomon uzunliklari va maydon yozuvi bilan. |
| `output/svg/lot_XX.svg` | Har bir lot uchun bezatilgan **chizma** — tomon uzunliklari, maydon, lot raqami, shimol strelkasi va masshtab bilan. Brauzerda ochib, PDF'ga chop etish mumkin. |
| `output/combined_all.dxf` | Barcha 62 lot bitta faylda, **haqiqiy o'zaro joylashuvi** bilan (umumiy master reja). |
| `output/lots_report.csv` | To'liq jadval: raqam, maydon (m²/sotix), perimetr, burchaklar soni, o'lchamlar, markaz koordinatasi. Excel'da ochiladi. |
| `output/index.html` | Barcha lotlarni ko'rish uchun **galereya** — brauzerda oching. |

## Ko'rish

1. **Galereya:** `output/index.html` faylini brauzerda oching — barcha 62 lot
   chizmasi va har biri uchun DXF yuklab olish tugmasi.
2. **AutoCAD'da:** `output/dxf/lot_XX.dxf` yoki `output/combined_all.dxf` faylini oching.
3. **Jadval:** `output/lots_report.csv` faylini Excel/Google Sheets'da oching.

## Qayta generatsiya qilish

Agar shapefile o'zgarsa yoki chizma uslubini o'zgartirmoqchi bo'lsangiz:

```bash
cd master-reja-mingbuloq-36
python3 tools/generate.py
```

## Texnik tafsilotlar (`tools/` papkasi)

Barcha kod **sof Python** (tashqi kutubxonasiz) — sandbox'da internet yopiq bo'lgani uchun
shapefile parseri qo'lda yozilgan.

| Fayl | Vazifasi |
|------|----------|
| `tools/shp_reader.py` | ESRI Shapefile (.shp) va DBF (.dbf) o'qish |
| `tools/geo.py` | Proyeksiyalar: Web Mercator → lon/lat → haqiqiy metr (ENU) |
| `tools/analyze.py` | Lotlar tahlili: atributlar va haqiqiy maydonlar |
| `tools/generate.py` | Barcha natijalarni (DXF, SVG, CSV, HTML) generatsiya qilish |

## Eslatma: lot raqamlari

Shapefile'dagi `id` va `cadNum` atributlari **bo'sh**. Shuning uchun lotlar shapefile'dagi
tartib bo'yicha **1 dan 62 gacha** raqamlangan. Agar sizda haqiqiy lot yoki kadastr
raqamlari ro'yxati bo'lsa, ularni bog'lash mumkin — `tools/generate.py` da nomlashni
osongina o'zgartirsa bo'ladi.
