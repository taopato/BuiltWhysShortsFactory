# GitHub yayını için güvenli kapsam

Bu çalışma klasörü şu anda Git deposu değildir. Ayrı bir **private** `BuiltWhysShortsFactory` deposu kurulmadan `git add .` / `push` yapılmamalıdır.

## Gönderilecekler

- Uygulama ve `automation/` kaynak kodu, testler, örnek yapılandırma, `deploy/` betikleri, lisans ve belgeler.
- 3D pilotların Blender/FFmpeg **kaynak betikleri**: hem ilk hem ikinci kilit sürümü.
- Açık atıf: MoneyPrinterTurbo kaynak projesi ve MIT lisansı.

## Gönderilmeyecekler

- `.env.automation`, `config.toml`, `*.secrets.clixml`, OAuth yenileme anahtarları, API tokenları, SSH özel anahtarları veya parolalar.
- `storage/`: ham/bitmiş videolar, SQLite veritabanı, arşiv, günlükler, kişisel medya ve referans üreticinin videoları.
- `audit-evidence/`: hesap/kanal verisi ve kişisel ekran görüntüleri; dosya bazında incelenmeden yayımlanmaz.
- Geçici render kareleri, `.blend` ve büyük medya; ancak ayrı lisans/yayın kararıyla eklenir.

## Yayın öncesi kontrol

1. Doğru GitHub hesabında yeni **private** repo doğrulanır. Şu an yerel `gh auth status` geçersiz oturum gösteriyor; bağlı GitHub aracı yeni depo oluşturma işlemi sunmuyor.
2. Kaynak paketinde sırlar ve kişisel veriler taranır. `.gitignore` tek başına yeterli değildir; commit geçmişi de incelenir.
3. Dış lisanslar ve medya hakları kontrol edilir.
4. İlk commit'te yalnızca onaylı kaynak/README/diagram/test bulunur; gerçek ortam dosyaları örnekle değiştirilir.
5. Private repoya push edilir; URL ve commit SHA doğrulanır. Public yapılacaksa kapsam ayrıca gözden geçirilir.

Bu belge push yapıldığı anlamına gelmez. GitHub URL'si ve commit SHA'sı olmadan “yayımlandı” denmemelidir.
