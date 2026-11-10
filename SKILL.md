---
name: video-montaj
description: Video, rasm(lar), kollaj, matn yoki audio asosida har safar YANGI g'oyali, shablonga o'xshamaydigan premium vertikal montaj yaratish (ovoz asl manbadan, effekt ovozsiz). Foydalanuvchi "montaj qiling", "animatsiya qiling", "dizayn qiling", "video yasang", "rasmlardan video qiling", "kreativ qiling" desa ishlating.
---

# Cheksiz g'oyali premium montaj — yo'riqnoma

**Asosiy falsafa: har video — yangi film.** Oldingi videoning sahnalari, kompozitsiyasi,
effektlar to'plami yoki o'tishlar ketma-ketligi takrorlanmaydi. `render.py` — bu
shablon emas, **asboblar qutisi (dvigatel)**: undan istalgan g'oyani yig'ish mumkin.
Sahnalar har safar matn ma'nosidan, rasmlarning o'zidan va ovoz ritmidan kelib
chiqib **noldan** o'ylab topiladi. Namuna loyiha (`projects/oddiy_baxt.py`) faqat
SIFAT darajasini ko'rsatadi — undan sahna ko'chirish taqiqlanadi.

## Qat'iy qoidalar
- Ovoz faqat asl manbadan, o'zgartirilmasdan (`-c:a copy`). Effekt ovoz va musiqa qo'shilmaydi.
- Foydalanuvchi rasm bergan bo'lsa, asosiy vizual — o'sha rasmlar. Rasmni fon qilib,
  ostiga matn qo'yib qo'yish **taqiqlanadi**: har kadrda rasm bilan nimadir sodir
  bo'ladi (kamera, niqob, zarralar, matn bilan o'zaro ta'sir, kadrlararo bog'lanish).
- Har sahnaning o'z vizual metaforasi va doimiy harakati bor. Qotib qolgan kadr bo'lmaydi.
- Matn **harfma-harf** ko'chiriladi: o‘ g‘ (U+2018), ’ (U+2019), uzun tire —, katta-kichik
  harflar ham asl matndagidek. Yangi matn to'qilmaydi. Foydalanuvchi matnidagi iborani
  yakunda takrorlash (callback) mumkin — buni javobda ochiq ayting.
- Video oxirida muallif yozuvi: **Instagram belgisi + Dilmurod_Sabriy** (`render.HANDLE`,
  `handle()` — Instagram belgisi va nom birga chiziladi). Reels xavfsiz zonasida joylang:
  pastki izoh (y > 1480) va o'ngdagi tugmalar ostiga tushmasin.
- Foydalanuvchi bilan o'zbek tilida, qisqa va aniq. Uzoq ish paytida vaqti-vaqti bilan
  1 qatorli holat xabari bering.

---

## 1-qadam. Materialni tahlil qilish

### A) Video yuborilgan bo'lsa
1. `ffprobe` — o'lcham, fps, davomiylik, audio. Chiqish: shu davomiylik va fps; o'lcham
   9:16 bo'lsa 1080×1920 (matn tiniq chiqadi) — javobda ayting.
2. Kontakt varaq: `ffmpeg -i in.mp4 -vf "fps=1/2,scale=180:-1,tile=8x3" -frames:v 1 contact.jpg`.
3. Ekrandagi matnni to'liq o'lchamdagi kadrlardan harfma-harf ko'chiring. Matn bo'lmasa va
   foydalanuvchi matn bergan bo'lsa — o'sha matn ishlatiladi.
4. **Ovoz:** `python3 tools/analyze_audio.py in.mp4 --png spec.png` — pauzalar (sahna
   chegaralari), bass zarbalari (katta lahzalar), onsetlar. Spektrogrammani ko'zdan kechiring:
   - nutq → matnni nutqqa bog'lang (whisper bo'lsa transkripsiya; bo'lmasa foydalanuvchidan so'rang),
     so'zlar aytilganda yorishadi (read-along);
   - vokal/nashid (titrayotgan garmonikalar, jimlik yo'q) → so'zma-so'z sinxron emas, sahnalar
     jumla pauzalariga, kuchli lahzalar zarbalarga;
   - cholg'u → urg'ularga (beat) kesim.

### B) Rasm(lar) yoki kollaj yuborilgan bo'lsa
1. `python3 tools/split_and_upscale.py kollaj.png models/ assets/images/` — kadrlar orasidagi
   oq/qora chiziqlar avtomatik topiladi, har kadr waifu2x bilan 4x kattalashtiriladi,
   `panels.json` (kollajdagi to'rtburchaklar) yoziladi. Alohida rasmlar ham shu skript bilan.
   Modellar: `raw.githubusercontent.com/nihui/waifu2x-ncnn-vulkan/master/models/models-cunet/`
   (`noise{0,1}_scale2.0x_model.{param,bin}`), `pip install ncnn`.
2. Har kadrga koordinata to'ri chizing (har 200 px) va yozib oling: yuzlar, quyosh/yorug'lik
   manbai, bo'sh/qorong'i joylar (matn uchun), osmon fonidagi subyekt (cutout uchun).
3. Har rasm nimani "aytadi" — bitta jumla bilan yozing. Rasm ↔ matn bo'lagi moslashtirish
   jadvalini tuzing. Bitta rasmni ikki xil "shot" (umumiy + yaqin) sifatida ishlatish mumkin.

### C) Faqat matn bo'lsa
1. Matnni ma'noli bo'laklarga ajrating (hook → bo'laklar → xulosa → yakun/CTA).
2. Davomiylik: `1.5 s + so'zlar/2.5 + 1.0 s`, sahna 3–12 s. Vizuallar vektorda (Cairo) chiziladi.
3. Ovoz bo'lmasa — video ovozsiz; alohida audio berilsa — o'sha.

---

## 2-qadam. G'OYALAR BOSQICHI (eng muhim — o'tkazib yubormang)

1. **Har matn bo'lagi uchun kamida 3 ta turli g'oya** yozing, har biri boshqa o'qdan:
   - *so'zma-so'z metafora* — so'zni tom ma'noda ko'rsatish ("tor doira" → iris doira;
     "qadamma-qadam" → zinapoya bo'lib ko'tariladigan matn; "dunyo" → panorama);
   - *kontrast / hissiyot* — rang va ritm bilan ("soxtalik" → sovuq glitch, so'ng iliq sokinlik);
   - *kamera / montaj hiylasi* — kollaj ichiga sho'ng'ish, whip, split-screen, match-cut;
   - *tipografiya hiylasi* — so'z subyekt ortida, ustidan chizib o'chirish, slam, kontur so'z;
   - *kutilmagan "signature" lahza* — tomoshabin "qanday qilingan?" deb so'raydigan joy.
   Eng **kutilmagan, lekin ma'noga 100% mos** g'oyani tanlang.
2. Ilhom kerak bo'lsa: `python3 tools/ideas.py --scenes N --mood sokin|dramatik|energiya|nostalji`
   — katalogdan tasodifiy kombinatsiyalar beradi va `projects/ideas_log.json` dagi oldingi
   videolarda ishlatilganlarini kam taklif qiladi. Taklifni ko'r-ko'rona olmang — ma'noga moslang.
3. **Anti-shablon tekshiruvi** (ssenariyni yozgach, renderdan oldin):
   - [ ] bitta videoda ikki sahna bir xil *kompozitsiya + kamera + o'tish* kombinatsiyasida emas;
   - [ ] o'tishlar kamida 4 xil turda; hech bir o'tish 2 martadan ko'p emas;
   - [ ] matn joylashuvi sahnadan sahnaga o'zgaradi (tepada / pastda / ramka ichida / split orasida / obyekt ortida);
   - [ ] rang hikoyasi bor (masalan sovuq → iliq, oq-qora → rang, tun → tong);
   - [ ] kamida 1 ta signature lahza, u `ideas_log.json` dagi oldingi videolarda yo'q;
   - [ ] har sahnada matndagi kalit so'z bilan sinxron voqea bor (zarba, raqam, aytilgan so'z);
   - [ ] oldingi video bilan solishtiring: "bu o'sha video, rasmi boshqa" degan taassurot bo'lmasin.
4. **Ssenariy jadvali** (renderdan oldin javobga yoki faylga yozing):

| # | Vaqt | Matn | Rasm/vizual | G'oya (metafora) | Kamera | Effekt/zarra | Tipografiya | O'tish | Sinxron voqea |
|---|------|------|-------------|------------------|--------|--------------|-------------|--------|---------------|

---

## 3-qadam. Texnikalar katalogi (menyu, cheklov emas)

`python3 tools/ideas.py --catalog` to'liq ro'yxatni chiqaradi. Asosiylari va `render.py` asboblari:

- **Kompozitsiya:** full-bleed (`cam_cover`), mozaika/kollaj (`Mosaic`), split-screen
  (`clip` + `cam_cover(box=...)`), iris doira, ravoq/deraza niqobi (`arch_path`), polaroid
  (`polaroid`), triptix, film lentasi, letterbox (`letterbox`), karta + blur fon (`blurred`),
  so'z ichida rasm (matn-niqob), ekran ichida ekran.
- **Kamera:** push-in / pull-out (`cam_cover z`), sho'ng'ish (`zoom_between`), panorama,
  punch-in, whip, shake + zoom punch, rack focus, tilt, orbit, parallaks/dolly-zoom (`cutout_luma`).
- **Yorug'lik va zarralar:** `god_rays`, `flare`, `light_leak`, `add_glow`, `flash`, `shockwave`,
  `sparks`, `flying_glyphs` (uchuvchi harflar), `fall` (gul bargi/qor/yomg'ir/konfetti), `flock`
  (qushlar), `steam`, `bokeh`, `stars`, `dust`, `social_icons`, `camera_flashes`.
- **Tekstura/rang:** `grade` (oldindan hisoblangan variantlar), `duotone`, `tint`
  (OVERLAY/SOFT_LIGHT/SCREEN), `glitch`, `scanlines`, `vignette`, grain (`POST`).
- **Tipografiya:** `words_in` (blur-in), `chars_in`, `text_rise`, `scatter_in`, `typewriter`,
  `counter`, `marker`, `strike`, `glitch_text`, `outline_text`, obyekt ortidagi so'z
  (matn → `cutout_luma` qatlami ustidan), slam (`text(scale=...)`), tracking ochilishi.
- **O'tishlar (`TRANS`):** `fade`, `burn`, `zoom`, `cut`, `dissolve`, `whip`(dir), `flare`, `iris`(x,y),
  `blinds`, `push`(dir), `luma`(angle), `glitchcut`, `spin`. Yangisi kerak bo'lsa — loyihada
  `TRANSITIONS["nom"] = funksiya` qilib qo'shing.
- Katalogda yo'q g'oya tug'ilsa — **yangi asbob yozing** va uni `render.py` ga qo'shing
  (umumiy bo'lsa) — dvigatel har videodan boyib boradi.

---

## 4-qadam. Dizayn tizimi (moslashuvchan)

- **Kompozitsiya 1080×1920:** yon chekinish 70–110 px; pastdan 150 px xavfsiz zona;
  matn rasmning qorong'i/bo'sh joyiga yoki qorong'ilashtirish gradienti (`vgrad`) ustiga.
- **Shriftlar:** Inter (Thin…Black) — neytral/tuzilma; Playfair Display Italic — hissiy kalit
  so'zlar. Oltin matn uchun yorqin gradient `GG` (to'q `GOLD_D` gradient qorong'ida xira ko'rinadi).
  Uzun so'zlar `fit()` bilan ≤ 900–940 px.
- **Palitra:** rasm bo'lsa — palitra rasmdan olinadi, `grade`/`tint` bilan hikoya qilinadi.
  Rasm bo'lmasa — mavzuga qarab:

| Mavzu | Fon | Aksent |
|-------|-----|--------|
| Kirish / xulosa | `#060608 → #0b0a08` | oltin `#e3c47c` |
| Din, ma'naviyat | zumrad `#021512 → #06352c` | `#e6c98a` |
| Ilm, kitob | sepiya `#120a06 → #2a1608` | qahrabo `#f2b860` |
| Sport, energiya | `#0d0505 → #2b0a05` | `#ff4b2b → #ffb347` |
| Pul, karyera | navy `#03060f → #0a1a3c` | `#4f8dff`, `#64d8ff` |
| Sog'liq, tinchlik | `#03141a → #08303a` | `#5fe0c8` |
| Oila, mehr | `#160809 → #2e1015` | `#ff8fa3` |
| Texnologiya | `#07051a → #160b3a` | `#9b7bff`, `#55e6ff` |
| Tabiat | `#04120a → #0d2e18` | `#8fe07a` |
| Soxtalik, shovqin | sovuq, desaturatsiya | neon `#ff4f8b`, `#55e6ff` |

  Bu jadval — boshlang'ich nuqta. Har videoda kamida bitta kutilmagan rang qarori qiling.
- Raqamli ro'yxat bo'lsa: `progress_bar(idx, n, ...)`, yorliq `0N / 0M`, katta raqam.

---

## 5-qadam. Animatsiya qoidalari
- **Easing:** kirish — `e_out`/`e_out5`; pop — `e_back`/`e_elastic`; harakat/chizish — `e_io`;
  keskin — `e_expo`. Linear faqat doimiy sikllarda.
- **Ketma-ketlik:** yorliq → asosiy so'z → qolgan matn; so'zlar orasida 0.08–0.3 s; hissiy so'z
  sekinroq (0.9–1.6 s), zarbadagi so'z tez (0.3–0.5 s).
- **Sinxron voqealar:** zarbada — smash-cut, chaqnash, shockwave, slam; pauzada — sahna almashuvi;
  raqam aytilganda — hisoblagich; kalit so'z — illyustratsiya reaksiyasi.
- **Doimiy hayot:** har kadrda sekin kamera + zarralar/yorug'lik "nafasi".
- **O'tishlar:** 0.4–1.0 s, sahna mazmuniga mos (sokinlikka dissolve, xaosga glitch/cut, harakatga whip/push).
- **Boshi va oxiri:** 0.5 s qoradan ochilish, 0.7 s qoraga so'nish (`POST`). Muallif yozuvi oxirgi 1.5–2 s da ko'rinib turadi.

---

## 6-qadam. Texnik amalga oshirish
- Kutubxonalar: `pip install pycairo pillow numpy` (+ ffmpeg). Shriftlar `assets/fonts/`.
- **Yangi video = yangi fayl:** `projects/<nom>.py`. Tuzilma:
  ```python
  import render as R
  R.configure(size=(1080, 1920), fps=30, dur=44.766)
  from render import *
  OUTPUT = "output/<nom>.mp4"
  def prepare(): ...                   # Pic(load_rgb(...)), grade, blurred, cutout_luma, Mosaic
  def scene0(ctx, lt, t): ...          # lt — sahna ichidagi vaqt, t — umumiy vaqt
  SCENES = [(0.0, scene0), (8.55, scene1), ...]
  TRANS = {1: ("burn", 0.9), 2: ("iris", 0.7, {"x": 540, "y": 600}), ...}
  ```
  Oldingi loyihadan faqat shu **tuzilma** olinadi, sahna funksiyalari emas.
- Buyruqlar:
  - preview: `python3 render.py projects/<nom>.py asl.mp4 --preview 3.5 12 20.1` → `previews/`
  - kontakt: `python3 tools/sheet.py sheet.jpg 6 previews/*.png`
  - to'liq tekshiruv: `--check` (barcha kadrlar, kodlashsiz)
  - render: `python3 render.py projects/<nom>.py asl.mp4` (4 parallel bo'lak, libx264 crf 17, audio copy)
- **Ma'lum tuzoqlar:**
  - `ctx.scale()` ga ~0 → Cairo `NO_MEMORY`; `e_back`/`e_elastic` p≤1e-3 da 0 qaytaradi, chizishdan oldin `if p > 0`.
  - Cover rasmlarda `EXTEND_PAD` (`paint_pic` default) — chetida shaffof chiziq chiqmasin.
  - `vgrad` to'liq kadr bo'yicha ishlaydi (y1 < y0 — tepani qorong'ilashtiradi); qo'lda to'rtburchak chizsangiz qattiq chegara qoladi.
  - Bir nuqtadan chiqadigan zarralar to'planib qoladi — boshlang'ich nuqtaga tarqoqlik (`offs`) bering.
  - Whip blur — 18 tap running average (`tr_whip`), kam tapda zinapoya ko'rinadi.
  - Kichik mozaika kadrlari uchun mip-darajalar (`Mosaic`), aks holda miltillaydi.
  - Rasmlarni `prepare()` da yuklang — fork qilingan workerlar xotirani bo'lishadi.
  - Worker exit code'lari tekshiriladi; bir bo'lak yiqilsa render to'xtaydi.

---

## 7-qadam. Sifat nazorati (topshirishdan oldin)
1. Har sahnaning boshi/o'rtasi/oxiri va **har o'tishning o'rtasidan** preview; kontakt varaqni ko'ring.
   Kalit kadrlarni to'liq o'lchamda ham tekshiring (matn kontrasti, yuzlar kesilmagani).
2. Yakuniy videodan kontakt: `ffmpeg -i out.mp4 -vf "fps=1/2.5,scale=200:-1,tile=9x2" -frames:v 1 c.jpg`.
3. Tekshiruv ro'yxati:
   - [ ] matnlar bir-birini va yuzlarni to'smaydi, xavfsiz zonada, o'qiladi;
   - [ ] o'zbekcha belgilar va imlo asl matn bilan bir xil;
   - [ ] kadrlar soni = davomiylik × fps; davomiylik asl bilan bir xil;
   - [ ] audio md5 asl bilan teng: `ffmpeg -i X -map 0:a -c copy -f md5 -`;
   - [ ] har sahnada metafora + doimiy harakat; rasmlar "ostiga matn" uslubida emas;
   - [ ] 2-qadamdagi anti-shablon tekshiruvi bajarilgan;
   - [ ] oxirida Instagram belgisi + `Dilmurod_Sabriy` (xavfsiz zonada).
4. Videoni yuboring (SendUserFile). `output/` ga commit va push qiling.
5. `projects/ideas_log.json` ga shu videoning signature lahzalari va texnikalarini qo'shing.
6. Javobda o'zbek tilida qisqa jadval: sahna → vaqt → g'oya. Taxminiy qismlarni ochiq ayting
   (sinxron avtomatik tahlilga asoslangani, upscale, cutout niqobi, callback matn va h.k.).
