# BuiltWhys Control Center

Bu proje tek sunucuda calisan, insan onayli bir Shorts uretim ve dagitim sistemidir. Varsayilan olarak gercek yayin kapali gelir. Bir video ancak Control Center'da onaylandiktan ve takvime girdikten sonra yayinlanabilir.

## Calisan akis

1. Yerel `qwen3:4b` konu paketini, ozgun senaryoyu, basligi ve Pexels aramalarini hazirlar.
2. Sistem 6 farkli Pexels videosu ve 2 ozgun teknik diyagram toplar. Klipler video icinde veya yakin gecmiste tekrar kullanilmaz.
3. Edge TTS seslendirir; MoneyPrinterTurbo 1080x1920 videoyu altyazi ve BuiltWhys filigraniyla render eder. Stok videolarda global zoom uygulanmaz.
4. Video Control Center havuzuna `Inceleme` durumunda gelir. Buradan onaylanir, reddedilir veya gorsel/hook/senaryo/ses/altyazi/metadata/tam revizyona gonderilir. Her revizyon yeni bir surumdur; onceki dosya korunur.
5. Onayli video yedek havuza girer. Elle plan yoksa Pazartesi 22:30, Carsamba 23:00, Cuma 22:00 ve Pazar 21:30 (Istanbul) slotlari kalite puanina gore otomatik dolar.
6. Zaman geldiginde ayni onayli master YouTube Shorts, Instagram Reels ve Facebook Reels'e gider. Platform bazinda kimlik ve hata kaydi tutulur; basarili platform ikinci kez yuklenmez.
7. Analitik worker izlenme, begeni ve yorumlari toplar. Yayin paketi Google Drive'a arsivlenir; SQLite her gun yerel yedeklenir.
8. Telegram artik video sikistirmaz ve onay arayuzu degildir; sadece ariza, yeni video ve yayin sonucu bildirimi ile Control Center linki yollar.

## Panel bolumleri

- Genel Bakis: onay bekleyenler, onayli yedek sayisi, siradaki yayin, toplam metrikler ve olaylar.
- Video Havuzu: mobil 9:16 onizleme, arama/filtre, metadata, dil, platform, kalite puani, onay/red/revizyon/yedek islemleri.
- Yayin Takvimi: varsayilan haftalik slotlar, elle planlama, bos slotlar ve uc platform secimi.
- Analitik: platform toplamlari ve en iyi videolar.
- Sistem: disk doluluk orani, worker heartbeatleri, hata ve yedek durumu.
- Ayarlar: hedef havuz, minimum yedek, takvim ufku, otomatik doldurma, Telegram ve cift kilitli gercek yayin.

## Guvenlik ve para kazanma kurallari

- Control Center tek yonetici e-postasi ve parola formuyla acilir. Parola duz metin tutulmaz; rastgele tuzlu PBKDF2-SHA256 ozeti `.env.automation` icinde saklanir.
- Oturum cerezleri HMAC imzali, `HttpOnly`, `Secure` ve `SameSite=Strict` olarak yedi gun gecerlidir.
- `PUBLISH_ENABLED=false` sunucu kilididir. Paneldeki `publishing_enabled=false` ikinci kilittir. Ikisi birden acilmadan yayin olmaz.
- Onaysiz video yayinlanmaz. Havuz biterse sistem bos slotu atlar ve uyari verir.
- Telif manifestinde her Pexels URL'si/katkicisi ve her ozgun diyagram kayitlidir.
- Film, podcast, baska creator klibi, meshur ses klonlama ve kaynaksiz riskli iddialar kullanilmaz.
- YouTube'da daha once elle yuklenen ilk ucak videosu veritabaninda `YouTube published` olarak isaretlenir; tekrar YouTube'a yuklenmez.

## Ingilizce ve Turkce

Panel ve uretici `en-US` ile `tr-TR` destekler; uygun Edge TTS sesi otomatik secilir. Turkce kanal acildiginda ayri YouTube OAuth kimligi ve gerekiyorsa ayri Meta hesaplari eklenmelidir. Ayni Pexels paketi farkli dil seslendirmelerinde kullanilabilir; iki kanalda ayni anda otomatik yayin acilmadan once kanal-kimlik eslemesi yapilmalidir.

## Dosyalar

- `docker-compose.production.yml`: izole `builtwhys` Docker projesi.
- `Caddyfile.control-center`: otomatik HTTPS ve ters proxy.
- `automation/control_center_api.py`: panel/API.
- `automation/producer_worker.py`: arastirma, senaryo, stok paket ve render orkestrasyonu.
- `automation/publisher_worker.py`: idempotent uc platform yayinlama.
- `automation/preflight.py`: canli oncesi yapilandirma ve baglanti kontrolu.
- `deploy/bootstrap-ubuntu.sh`, `deploy/deploy.sh`: Ubuntu sunucu kurulumu ve yayin.

## Canliya gecis ozeti

1. Domain ve sunucu belirlendikten sonra Google Cloud'da ikinci bir OAuth istemcisi `Web application` turunde olusturulur. Authorized redirect URI tam olarak `https://CONTROL_CENTER_DOMAIN/auth/callback` olur.
2. Windows'ta `automation/prepare_server_env.ps1` calistirilir. Domain, izinli Google e-postasi ve Web OAuth bilgileri girilir. Mevcut sifreli Telegram, Pexels ve Meta anahtarlari `.env.automation` dosyasina aktarilir; dosya Git'e girmez.
3. Google Cloud'da YouTube Data API v3, YouTube Analytics API ve Google Drive API acilir. Yayin icin ayri bir Desktop OAuth istemcisi olusturulur ve `python automation/setup_google_oauth.py` calistirilir.
4. Domainin A kaydi sunucu IP'sine verilir.
5. Proje ve `.env.automation` sunucudaki `/opt/builtwhys` klasorune aktarilir.
6. `sudo bash deploy/bootstrap-ubuntu.sh`, sonra `bash deploy/deploy.sh` calistirilir.
7. Control Center'da servisler yesil, Meta/Google/Pexels testleri basarili ve bir gizli test yayin dogru gorundukten sonra `.env.automation` icinde `PUBLISH_ENABLED=true` yapilir; containerlar yeniden olusturulur. Son olarak panelde gercek yayin anahtari acilir.

Mevcut diger Docker projeleri durdurulmaz; compose proje adi ve agi ayridir.
