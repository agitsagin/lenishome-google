#!/usr/bin/env python3
"""Google Search Console haftalık raporu.

Sorduğumuz soru şu: insanlar bizi hangi aramada görüyor, görüp de neden
tıklamıyor, ve tıklayıp da neden almıyor. Son ikisini Shopify tarafında
ölçüyoruz; ilk ikisi yalnızca Search Console'da var.

Rapor dört şeye bakıyor:
  1. Son 28 günün özeti ve bir önceki 28 güne göre değişim.
  2. En çok tıklanan aramalar ve sayfalar.
  3. "Sayfa 2" fırsatları: çok gösterilen ama 8-20. sırada kalan aramalar.
     Bunlar en ucuz kazanç; sayfayı biraz iyileştirmek ilk sayfaya taşır.
  4. Gösterilip hiç tıklanmayan aramalar: burada sorun sıralama değil,
     başlık ve açıklama metni.

Kurulum:
  Merchant raporuyla AYNI hizmet hesabını kullanır. Tek fark, hizmet
  hesabının e-postasının Search Console'da da kullanıcı olarak eklenmesi
  (Ayarlar > Kullanıcılar ve izinler > Kullanıcı ekle > "Kısıtlı").
  Google Cloud'da "Google Search Console API" de etkinleştirilmeli.

Çıktılar:
  arama_rapor.md / arama_baslik.txt  -> GitHub kaydı (e-posta)
  arama_sorgular.csv                 -> tüm sorgular
"""

import csv
import json
import os
import sys
from datetime import date, timedelta
from urllib.parse import quote

import requests

KAPSAM = "https://www.googleapis.com/auth/webmasters.readonly"
KOK = "https://www.googleapis.com/webmasters/v3/sites"

# Domain mülkü için "sc-domain:" öneki zorunlu; URL öneki mülküyse
# "https://lenishome.com/" biçiminde verilir.
SITE = (os.getenv("SEARCH_CONSOLE_SITE") or "sc-domain:lenishome.com").strip()
GUN = int(os.getenv("ARAMA_GUN") or "28")
# Search Console verisi 2-3 gün gecikmeli; bugünü istemek yarım veri verir.
GECIKME = int(os.getenv("ARAMA_GECIKME") or "3")
SATIR = int(os.getenv("ARAMA_SATIR") or "25000")

KAYIT = []


def yaz(m):
    print(m, flush=True)
    KAYIT.append(m)


def jeton():
    ham = os.getenv("GOOGLE_ARAMA_KEY") or os.getenv("GOOGLE_MERCHANT_KEY")
    if not ham:
        sys.exit("GOOGLE_MERCHANT_KEY (ya da GOOGLE_ARAMA_KEY) tanımlı değil.")
    try:
        bilgi = json.loads(ham)
    except json.JSONDecodeError:
        sys.exit("Anahtar geçerli bir JSON değil. Dosyanın tamamını yapıştırın.")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        sys.exit("google-auth kurulu değil (requirements.txt).")
    kimlik = service_account.Credentials.from_service_account_info(bilgi, scopes=[KAPSAM])
    kimlik.refresh(Request())
    return kimlik.token


def sorgula(tok, bas, bit, boyutlar):
    """searchAnalytics.query — sayfalayarak tüm satırları toplar."""
    url = f"{KOK}/{quote(SITE, safe='')}/searchAnalytics/query"
    basliklar = {"Authorization": f"Bearer {tok}"}
    hepsi, adim = [], 0
    while True:
        govde = {"startDate": bas, "endDate": bit, "dimensions": boyutlar,
                 "rowLimit": SATIR, "startRow": adim * SATIR, "type": "web"}
        r = requests.post(url, headers=basliklar, json=govde, timeout=120)
        if r.status_code == 403:
            sys.exit("Search Console erişimi reddedildi (403). Hizmet hesabı mülke "
                     "kullanıcı olarak ekli mi ve Search Console API etkin mi?")
        if r.status_code == 404:
            sys.exit(f"Mülk bulunamadı (404). SEARCH_CONSOLE_SITE doğru mu? Verilen: {SITE}")
        r.raise_for_status()
        satirlar = r.json().get("rows") or []
        hepsi += satirlar
        if len(satirlar) < SATIR:
            break
        adim += 1
    return hepsi


def topla(satirlar):
    tik = sum(s.get("clicks", 0) for s in satirlar)
    gos = sum(s.get("impressions", 0) for s in satirlar)
    # Ortalama sıra gösterimle ağırlıklandırılmalı; düz ortalama,
    # bir kez görünen bir sorguyu binlerce kez görünenle eşitler.
    agirlik = sum(s.get("position", 0) * s.get("impressions", 0) for s in satirlar)
    sira = agirlik / gos if gos else 0
    return tik, gos, (tik / gos if gos else 0), sira


def fark(yeni, eski):
    if not eski:
        return "—"
    o = (yeni - eski) / eski * 100
    return f"{o:+.0f}%"


def md_yaz(simdi, onceki, sorgular, sayfalar, bas, bit):
    t1, g1, c1, s1 = topla(simdi)
    t0, g0, c0, s0 = topla(onceki)

    p = [f"**{bas} – {bit}** · son {GUN} gün, bir önceki {GUN} günle karşılaştırmalı", ""]
    p.append("| | Bu dönem | Değişim |")
    p.append("|---|---|---|")
    p.append(f"| Tıklama | **{t1:,}** | {fark(t1, t0)} |".replace(",", "."))
    p.append(f"| Gösterim | {g1:,} | {fark(g1, g0)} |".replace(",", "."))
    p.append(f"| Tıklama oranı | %{c1*100:.2f} | {fark(c1, c0)} |")
    # Sırada yüzde değişim yanıltıcı: 20. sıradan 15'e çıkmak %25 ama
    # 4'ten 3'e çıkmak da %25. Net farkı gösteriyoruz, yön de belli olsun.
    delta = s0 - s1 if s0 else 0
    yon = "iyileşti" if delta > 0 else ("geriledi" if delta < 0 else "aynı")
    p.append(f"| Ortalama sıra | {s1:.1f} | {abs(delta):.1f} sıra {yon} |")

    def tablo(baslik, satirlar, anahtar_ad, n=20):
        if not satirlar:
            return
        p.append("")
        p.append(f"## {baslik}")
        p.append(f"| {anahtar_ad} | Tıklama | Gösterim | Sıra |")
        p.append("|---|---|---|---|")
        for s in satirlar[:n]:
            ad = s["keys"][0]
            p.append(f"| {ad[:70]} | {s.get('clicks',0)} | {s.get('impressions',0)} "
                     f"| {s.get('position',0):.1f} |")

    tablo("En çok tıklanan aramalar", sorted(sorgular, key=lambda s: -s.get("clicks", 0)), "Arama")
    tablo("En çok tıklanan sayfalar",
          sorted(sayfalar, key=lambda s: -s.get("clicks", 0)), "Sayfa", 15)

    # Sayfa 2 fırsatları: ilk sayfanın hemen dışında, gösterimi yüksek.
    firsat = [s for s in sorgular
              if 8 <= s.get("position", 99) <= 20 and s.get("impressions", 0) >= 20]
    firsat.sort(key=lambda s: -s.get("impressions", 0))
    if firsat:
        p.append("")
        p.append("## Sayfa 2 fırsatları")
        p.append("_Çok gösteriliyor ama ilk sayfanın hemen dışında. En ucuz kazanç burada:"
                 " sayfayı biraz iyileştirmek ilk sayfaya taşıyabilir._")
        p.append("| Arama | Gösterim | Tıklama | Sıra |")
        p.append("|---|---|---|---|")
        for s in firsat[:20]:
            p.append(f"| {s['keys'][0][:70]} | {s.get('impressions',0)} "
                     f"| {s.get('clicks',0)} | {s.get('position',0):.1f} |")

    # Görünüyor ama tıklanmıyor: sorun sıralama değil, başlık/açıklama.
    # Eşik ilk sayfa (<=8), böylece yukarıdaki "sayfa 2" listesiyle
    # çakışmıyor; iki tabloda aynı aramayı görmek rapora güveni azaltır.
    sessiz = [s for s in sorgular
              if s.get("clicks", 0) == 0 and s.get("impressions", 0) >= 50
              and s.get("position", 99) < 8]
    sessiz.sort(key=lambda s: -s.get("impressions", 0))
    if sessiz:
        p.append("")
        p.append("## Görünüyor ama tıklanmıyor")
        p.append("_İlk 15 sırada çıkıyor, çok gösteriliyor, hiç tıklanmıyor. Burada sorun"
                 " sıralama değil; arama sonucundaki başlık ve açıklama metni._")
        p.append("| Arama | Gösterim | Sıra |")
        p.append("|---|---|---|")
        for s in sessiz[:15]:
            p.append(f"| {s['keys'][0][:70]} | {s.get('impressions',0)} "
                     f"| {s.get('position',0):.1f} |")

    with open("arama_rapor.md", "w", encoding="utf-8") as f:
        f.write("\n".join(p) + "\n")
    with open("arama_baslik.txt", "w", encoding="utf-8") as f:
        f.write(f"Search Console — {t1} tıklama, {g1} gösterim "
                f"(tıklama {fark(t1, t0)})\n")


def main():
    bit = date.today() - timedelta(days=GECIKME)
    bas = bit - timedelta(days=GUN - 1)
    o_bit = bas - timedelta(days=1)
    o_bas = o_bit - timedelta(days=GUN - 1)

    tok = jeton()
    yaz(f"Mülk: {SITE}")
    yaz(f"Dönem: {bas} – {bit} (önceki: {o_bas} – {o_bit})")

    sorgular = sorgula(tok, str(bas), str(bit), ["query"])
    sayfalar = sorgula(tok, str(bas), str(bit), ["page"])
    simdi = sorgula(tok, str(bas), str(bit), ["date"])
    onceki = sorgula(tok, str(o_bas), str(o_bit), ["date"])

    yaz(f"{len(sorgular)} arama, {len(sayfalar)} sayfa okundu.")
    if not sorgular:
        yaz("Hiç veri yok. Mülk yeni eklendiyse birkaç gün beklemek gerekir.")

    with open("arama_sorgular.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Arama", "Tıklama", "Gösterim", "Tıklama oranı", "Sıra"])
        for s in sorted(sorgular, key=lambda x: -x.get("impressions", 0)):
            w.writerow([s["keys"][0], s.get("clicks", 0), s.get("impressions", 0),
                        f"{s.get('ctr',0)*100:.2f}", f"{s.get('position',0):.1f}"])

    md_yaz(simdi, onceki, sorgular, sayfalar, str(bas), str(bit))
    t, g, _, _ = topla(simdi)
    yaz(f"Bitti: {t} tıklama, {g} gösterim.")


if __name__ == "__main__":
    main()
