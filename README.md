# lenishome-google

[Le Nish Home](https://lenishome.com) için Google Merchant Center ve Google
Search Console raporları.

İki script var:

| Dosya | Ne yapar |
|---|---|
| `merchant_rapor.py` | Merchant API'den tüm ürünlerin onay durumunu ve ürün ürün hata listesini çeker, hata koduna göre gruplar. |
| `arama_konsolu.py` | Search Console'dan son 28 günün arama verisini çeker; en çok tıklananları, "sayfa 2" fırsatlarını ve gösterilip tıklanmayan aramaları ayırır. |

## Bu depo neden genel

GitHub Actions genel depolarda ücretsiz çalışıyor. Bu iki script yalnızca
Google'dan veri çekip tablo yazıyor; içinde ticari sır yok — fiyat, maliyet,
marj ya da tedarikçi bilgisi geçmiyor. Bu yüzden kodu açık tutmanın bir
sakıncası yok ve karşılığında raporlar dakika kotası harcamadan çalışıyor.

**Üretilen verinin kendisi burada tutulmaz.** Arama sorguları ve ürün hata
listeleri özel bir depoya gönderilir; rapor kayıtları da orada açılır. Burada
açılsa sitenin hangi aramada kaçıncı sırada olduğu herkese görünürdü.

## Kurulum

Depo ayarlarında (`Settings → Secrets and variables → Actions`):

**Secrets**
| Ad | Nedir |
|---|---|
| `GOOGLE_MERCHANT_KEY` | Google Cloud hizmet hesabının JSON anahtarının tamamı. Aynı hesap hem Merchant API hem Search Console API için kullanılır. |
| `VERI_TOKEN` | Özel depoya yazma yetkisi olan GitHub erişim anahtarı (PAT). Veri ve rapor oraya bununla gönderilir. |

**Variables** (isteğe bağlı)
| Ad | Varsayılan |
|---|---|
| `OZEL_DEPO` | `agitsagin/eletrend-sync` |
| `SEARCH_CONSOLE_SITE` | `sc-domain:lenishome.com` |

Google tarafında bir kerelik:

1. Google Cloud'da proje açın, **Merchant API** ve **Google Search Console
   API**'yi etkinleştirin.
2. Hizmet hesabı oluşturup JSON anahtarını indirin.
3. Hizmet hesabının e-postasını **Merchant Center → Ayarlar → Kullanıcılar**
   altına ekleyin.
4. Aynı e-postayı **Search Console → Ayarlar → Kullanıcılar ve izinler**
   altına "Kısıtlı" yetkiyle ekleyin.

JSON anahtarını hiçbir yere yapıştırmayın; yalnızca GitHub Secrets'a girin.

## Çalışma zamanı

Her ikisi de Pazartesi sabahı çalışır (09:15 ve 09:40, Türkiye saati) ve elle
de tetiklenebilir. Çıktılar özel depoda `veri` dalına düşer:
`merchant_ozet.csv`, `merchant_hatalar.csv`, `arama_sorgular.csv`.
