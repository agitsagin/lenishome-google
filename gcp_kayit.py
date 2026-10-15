#!/usr/bin/env python3
"""Google Cloud projesini Merchant Center hesabına kaydeder — tek seferlik.

Merchant API, çağrıyı yapan Cloud projesinin merchant hesabıyla
ilişkilendirilmiş olmasını şart koşuyor. Bu adım ne Cloud Console'dan ne de
Merchant Center arayüzünden yapılabiliyor; yalnızca bu API çağrısıyla.
Kayıt yoksa her istek 401 / GCP_NOT_REGISTERED ile döner.

Kayıt bir kez yapılır, kalıcıdır. Bu betiği tekrar çalıştırmak zarar vermez.

Gerekli:
  GOOGLE_MERCHANT_KEY   -> hizmet hesabı JSON anahtarı
  MERCHANT_ID           -> Merchant Center hesap numarası
  GELISTIRICI_EPOSTA    -> Merchant Center'da kullanıcı olan bir e-posta
"""

import json
import os
import sys

import requests

KAPSAM = "https://www.googleapis.com/auth/content"
KOK = "https://merchantapi.googleapis.com/accounts/v1"
HESAP = (os.getenv("MERCHANT_ID") or "").strip().replace("accounts/", "")
EPOSTA = (os.getenv("GELISTIRICI_EPOSTA") or "").strip()


def jeton():
    ham = os.getenv("GOOGLE_MERCHANT_KEY")
    if not ham:
        sys.exit("GOOGLE_MERCHANT_KEY tanımlı değil.")
    try:
        bilgi = json.loads(ham)
    except json.JSONDecodeError:
        sys.exit("GOOGLE_MERCHANT_KEY geçerli bir JSON değil.")
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    kimlik = service_account.Credentials.from_service_account_info(bilgi, scopes=[KAPSAM])
    kimlik.refresh(Request())
    return kimlik.token


def main():
    if not HESAP:
        sys.exit("MERCHANT_ID tanımlı değil.")
    if not EPOSTA:
        sys.exit("GELISTIRICI_EPOSTA tanımlı değil.")

    url = f"{KOK}/accounts/{HESAP}/developerRegistration:registerGcp"
    r = requests.post(url, headers={"Authorization": f"Bearer {jeton()}"},
                      json={"developerEmail": EPOSTA}, timeout=60)
    print(f"HTTP {r.status_code}")
    print(r.text[:1500])

    if r.status_code >= 400:
        sys.exit("Kayıt başarısız. Google'ın açıklaması yukarıda.")

    d = r.json()
    print()
    print(f"Kayıt tamam: {d.get('name', '(ad yok)')}")
    if d.get("gcpIds"):
        print(f"Bağlanan proje numaraları: {', '.join(str(x) for x in d['gcpIds'])}")
    print("Merchant raporu birkaç dakika içinde çalışabilir hale gelir.")


if __name__ == "__main__":
    main()
