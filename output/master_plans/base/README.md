# ControlNet uchun asos planlar (base images)

Bu papkadagi fayllar fotorealistik render qilishda **lot shaklini buzmaslik** uchun
tasvir generatsiya qiluvchi AI'ga (Stable Diffusion + ControlNet) "control image"
sifatida beriladi.

## Fayllar

| Fayl | Vazifasi |
|------|----------|
| `lot_XX_base.svg` | **Toza chiziqli** asos — ControlNet ga beriladi (Canny / Lineart / Segmentation) |
| `lot_XX_base_annot.svg` | O'lchamlar, burchaklar (P1..Pn), DARYO/YO'L bilan — **inson uchun** ma'lumotnoma |

Har bir lot chegarasi (qizil/qora chiziq) shapefile'dan **aynan** olingan — shakl 1:1.

## SVG → PNG aylantirish

ControlNet PNG kutadi. SVG'ni PNG'ga aylantirish:
- **Brauzerda:** SVG'ni oching → chop etish → "PDF/Rasm sifatida saqlash".
- **Inkscape:** `inkscape lot_01_base.svg --export-type=png -w 1200`
- **Onlayn:** istalgan "SVG to PNG" xizmati (1200×1200 yoki kattaroq).

## Stable Diffusion + ControlNet sozlamalari

1. **Model:** realistik model (masalan Realistic Vision, Juggernaut) yoki SDXL.
2. **ControlNet:**
   - Tur: **Canny** yoki **Lineart** (aniq shakl uchun eng yaxshi).
   - Control image: `lot_XX_base.png`.
   - Control weight: **0.9–1.2** (balandroq = shaklga qattiqroq rioya).
   - "Resize mode": *Just resize* yoki *Crop and resize*.
3. **Prompt (nusxa oling):**

```
aerial top-down architectural master plan, riverside glamping resort at dusk,
warm ambient lighting, parking at entrance, wooden river terrace, swimming pool,
felt yurts, fire pit lounge, summer and winter kitchen pavilions, basketball court,
lush trees and gardens, stone walking paths, photorealistic, ultra detailed, 4k
```

4. **Negative prompt:**

```
distorted boundary, changed shape, extra buildings outside plot, text, watermark,
blurry, low quality, deformed geometry
```

5. **--ar / o'lcham:** lot proporsiyasiga mos (masalan 3:4 vertikal).

## Muhim

- ControlNet weight'ni pasaytirmang — aks holda AI shaklni "ijodiy" o'zgartiradi.
- Render tayyor bo'lgach, uni bizning `lot_XX_base_annot.svg` bilan solishtiring:
  chegara va o'lchamlar mos kelishi kerak.
- Agar chegara biroz "suzsa", Canny + weight 1.2 bilan qayta render qiling.
