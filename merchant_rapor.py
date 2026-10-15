#!/usr/bin/env python3
"""
Google Merchant Center ürün hatalarını çeker ve raporlar.

Merchant Center'daki "İşlem gerekiyor" listesini tek tek okumak yerine
Merchant API'den tüm ürünlerin durumunu alır, hataları koda göre gruplar.

Üretilen dosyalar:
  merchant_ozet.csv    -> hata kodu başına kaç ürün etkileniyor
  merchant_hatalar.csv -> ürün ürün hata listesi (stok kodu, başlık, hata, çözüm)

Kurulum (tek seferlik):
1. Google Cloud Console'da bir proje açın, "Merchant API"yi etkinleştirin.
2. Hizmet hesabı (service account) oluşturup JSON anahtarını indirin.
3. Merchant Center > Ayarlar > Kullanıcılar'dan hizmet hesabının e-postasını
   (...iam.gserviceaccount.com) kullanıcı olarak ekleyin.
4. GitHub deposunda iki gizli anahtar tanımlayın:
     GOOGLE_MERCHANT_KEY -> indirdiğiniz JSON dosyasının tamamı
     MERCHANT_ID         -> Merchant Center hesap numaranız

JSON anahtarını sohbete, dosyaya ya da koda yazmayın; yalnızca GitHub
Secrets'a girin.

Content API for Shopping v2.1 18 Ağustos 2026'da kapandığı için Merchant API
v1 kullanılır: https://developers.google.com/merchant/api
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

import requests

KAPSAM = "https://www.googleapis.com/auth/content"
KOK = "https://merchantapi.googleapis.com/products/v1"
HESAP = (os.getenv("MERCHANT_ID") or "").strip().replace("accounts/", "")
SAYFA_BOY = int(os.getenv("MERCHANT_SAYFA_BOY") or "250")
MAKS = int(os.getenv("MERCHANT_MAKS") or "20000")
KAYIT = []


def yaz(m):
    print(m, flush=True)
    KAYIT.append(m)


def ozet_yaz():
    yol = os.getenv("GITHUB_STEP_SUMMARY")
    if not yol or not KAYIT:
        return
    try:
        with open(yol, "a", encoding="utf-8") as f:
            f.write("## Merchant Center raporu\n\n```\n" + "\n".join(KAYIT) + "\n```\n")
    except OSError:
        pass


def jeton():
    ham = os.getenv("GOOGLE_MERCHANT_KEY")
    if not ham:
        sys.exit("GOOGLE_MERCHANT_KEY tanımlı değil (GitHub Secrets).")
    try:
        bilgi = json.loads(ham)
    except json.JSONDecodeError:
        sys.exit("GOOGLE_MERCHANT_KEY geçerli bir JSON değil. Anahtar dosyasının tamamını yapıştırın.")
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError:
        sys.exit("google-auth kurulu değil (requirements.txt).")
    kimlik = service_account.Credentials.from_service_account_info(bilgi, scopes=[KAPSAM])
    kimlik.refresh(Request())
    return kimlik.token


def urunler(tok):
    basliklar = {"Authorization": f"Bearer {tok}"}
    sayfa, hepsi = None, []
    while True:
        p = {"pageSize": SAYFA_BOY}
        if sayfa:
            p["pageToken"] = sayfa
        r = requests.get(f"{KOK}/accounts/{HESAP}/products", headers=basliklar, params=p, timeout=120)
        if r.status_code >= 400:
            # Google'ın yanıt gövdesi sebebi açıkça yazıyor; durum kodunu
            # yorumlamaya çalışmak yerine onu gösteriyoruz. Gövdede anahtar
            # ya da müşteri verisi bulunmaz.
            ipucu = {
                401: "Jeton kabul edilmedi. Genellikle Merchant API projede etkin "
                     "değildir ya da anahtar başka bir projeye aittir.",
                403: "Erişim reddedildi. Hizmet hesabı Merchant Center'da kullanıcı "
                     "olarak ekli mi?",
                404: f"Hesap bulunamadı. MERCHANT_ID doğru mu? Verilen: {HESAP}",
            }.get(r.status_code, "")
            sys.exit(f"Merchant API {r.status_code} döndü. {ipucu}\n"
                     f"Google'ın açıklaması:\n{r.text[:1200]}")
        d = r.json()
        hepsi += d.get("products", [])
        sayfa = d.get("nextPageToken")
        yaz(f"  {len(hepsi)} ürün okundu...")
        if not sayfa or len(hepsi) >= MAKS:
            break
    return hepsi[:MAKS]


def main():
    if not HESAP:
        sys.exit("MERCHANT_ID tanımlı değil (GitHub Secrets).")
    liste = urunler(jeton())
    yaz(f"Merchant Center'da {len(liste)} ürün var.")

    satirlar, say, ciddiyet = [], Counter(), defaultdict(set)
    onay = Counter()
    for u in liste:
        durum = u.get("productStatus") or {}
        for d in durum.get("destinationStatuses") or []:
            baglam = d.get("reportingContext") or "?"
            if d.get("disapprovedCountries"):
                onay[f"{baglam}: onaylanmadı"] += 1
            elif d.get("approvedCountries"):
                onay[f"{baglam}: onaylandı"] += 1
            else:
                onay[f"{baglam}: beklemede"] += 1
        for h in durum.get("itemLevelIssues") or []:
            kod = h.get("code") or "?"
            say[kod] += 1
            ciddiyet[kod].add(h.get("severity") or "")
            satirlar.append({
                "Stok Kodu": u.get("offerId") or "",
                "Ürün": (u.get("productAttributes") or {}).get("title") or u.get("name") or "",
                "Hata kodu": kod,
                "Ciddiyet": h.get("severity") or "",
                "Açıklama": h.get("description") or "",
                "Alan": h.get("attribute") or "",
                "Çözüm": h.get("resolution") or "",
                "Kanal": h.get("reportingContext") or "",
                "Belge": h.get("documentation") or "",
            })

    with open("merchant_hatalar.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()) if satirlar else
                           ["Stok Kodu", "Ürün", "Hata kodu", "Ciddiyet", "Açıklama",
                            "Alan", "Çözüm", "Kanal", "Belge"], delimiter=";")
        w.writeheader()
        w.writerows(satirlar)

    ornek = {}
    for s in satirlar:
        ornek.setdefault(s["Hata kodu"], s)
    with open("merchant_ozet.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Hata kodu", "Kaç ürün", "Ciddiyet", "Açıklama", "Alan", "Çözüm", "Belge"])
        for kod, n in say.most_common():
            o = ornek.get(kod, {})
            w.writerow([kod, n, ", ".join(sorted(x for x in ciddiyet[kod] if x)),
                        o.get("Açıklama", ""), o.get("Alan", ""), o.get("Çözüm", ""), o.get("Belge", "")])

    yaz("")
    yaz("Onay durumu:")
    for k, n in onay.most_common():
        yaz(f"  {n:>6}  {k}")
    yaz("")
    yaz(f"Toplam {len(satirlar)} hata kaydı, {len(say)} farklı hata kodu:")
    for kod, n in say.most_common(25):
        o = ornek.get(kod, {})
        yaz(f"  {n:>6}  {kod} — {o.get('Açıklama', '')[:70]}")
    ozet_yaz()
    md_yaz(liste, onay, say, ciddiyet, ornek, satirlar)


def md_yaz(liste, onay, say, ciddiyet, ornek, satirlar):
    """Raporu e-posta olarak gönderilebilir bir metne çevirir.

    CSV'yi açmak için bilgisayar başına geçmek gerekiyor; asıl soru
    ("hangi ürün neden reddedildi") tek bakışta görünmeli.
    """
    p = [f"Merchant Center'da **{len(liste):,} ürün** var.".replace(",", ".")]
    p.append("")
    p.append("## Onay durumu")
    p.append("| Durum | Ürün |")
    p.append("|---|---|")
    for k, n in onay.most_common():
        p.append(f"| {k} | {n} |")

    if say:
        p.append("")
        p.append(f"## Hatalar ({len(satirlar)} kayıt, {len(say)} farklı kod)")
        p.append("| Hata kodu | Ürün | Ciddiyet | Açıklama |")
        p.append("|---|---|---|---|")
        for kod, n in say.most_common(25):
            o = ornek.get(kod, {})
            cid = ", ".join(sorted(x for x in ciddiyet[kod] if x))
            p.append(f"| `{kod}` | {n} | {cid} | {o.get('Açıklama','')[:90]} |")

        # En sık hatanın hangi ürünlerde olduğunu da göster: kodu bilmek
        # yetmiyor, hangi ürüne bakılacağı lazım.
        ilk_kod = say.most_common(1)[0][0]
        orneklem = [s for s in satirlar if s["Hata kodu"] == ilk_kod][:15]
        if orneklem:
            p.append("")
            p.append(f"### `{ilk_kod}` hatasının görüldüğü ürünler (ilk {len(orneklem)})")
            p.append("| Stok kodu | Ürün |")
            p.append("|---|---|")
            for s in orneklem:
                p.append(f"| {s.get('Stok Kodu','')} | {s.get('Ürün','')[:60]} |")
    else:
        p.append("")
        p.append("_Hiçbir üründe hata yok._")

    with open("merchant_rapor.md", "w", encoding="utf-8") as f:
        f.write("\n".join(p) + "\n")

    hatali = sum(n for _, n in say.most_common())
    with open("merchant_baslik.txt", "w", encoding="utf-8") as f:
        f.write(f"Merchant Center raporu — {len(liste)} ürün, {hatali} hata kaydı\n")


if __name__ == "__main__":
    main()
