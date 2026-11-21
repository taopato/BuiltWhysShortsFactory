# BuiltWhys yeniden başlatma: kontrollü 3D pilot

Durum: 21 Kasım 2026. Bu belge bir yayın onayı değildir; yeni format canlı
otomasyona bağlanmadan önce ölçülecek kapıları tanımlar.

## Canlı sistemde doğrulanan durum

- 34 YouTube Short, yaklaşık 13.725 toplam izlenme, 7 abone. Son yayın 26 Ekim.
- Onay bekleyen 29 video var; otomatik onay ölçütlerinin tamamını geçen sıfır.
- Onaylı yedek sıfır. `pending_target=25` olduğundan üretici 29 eski videoyu
  yeterli stok sayıyor ve yeni fikir aramıyor. Eski videoları eşikleri düşürüp
  otomatik onaylamak kalite sorununu çözüyor gibi görünür, ama çözmez.
- 1.704 tarihsel başarısız iş, üretim hattının konu/görsel seçimi ve retry
  stratejisinin ayrıca incelenmesini gerektiriyor.
- Sunucudaki Python kodu GitHub `main`'den ileride; doğrudan eski kodu
  yayımlamak canlı düzeltmeleri geri alır. Yedekler sunucudaki
  `/opt/builtwhys/storage/backups/` dizinindedir.
- CPU-only sunucuda eski sinematik kilit sahnesi 64 örneklemde yaklaşık 100
  saniye/kare sürüyor. Tamamını bu ayarla render etmek yaklaşık 24 saat.
- Aynı `.blend` dosyasında ve iki düşük öncelikli CPU iş parçacığıyla ölçülen
  tek-kare deneyi: yüzde 50 çözünürlük/64 örneklem 87,17 saniye; tam
  çözünürlük/16 örneklem 28,73 saniye; tam çözünürlük/8 örneklem 15,45 saniye.
  Tepe RAM yaklaşık 600 MB. Üç kareyi de görsel olarak inceledik: 8 örneklem
  kullanılabilir şema görünümü veriyor, ancak materyal ve gerçekçilik sorunu
  devam ediyor. Bu tek kareden tüm videonun süresini kesin kabul etmiyoruz.

## Sıra

1. Yeni formatı mevcut stok-video üreticisinden ayrı, yayın yapmayan pilot
   hattında doğrula. Şimdiki iki şablon: pimli kilit ve emniyet kemeri
   sarıcısı. Konu yalnızca doğrulanmış bir 3D şablon ve kaynaklı teknik iddia
   varsa kabul edilir. Rastgele konuya aynı çizimi giydirme yok.
2. Her pilot için açılışta gerçek bir insan/nesne bağlamı, ardından hareketli
   3D mekanizma yakın planı, net sebep-sonuç açıklaması ve fiziksel sonuç
   göster. Ses, altyazı ve ekrandaki hareket aynı olaydan söz etmeli.
3. Ön doğrulama: `automation/pilots_3d/story_contract.py` sahne sürelerini,
   eylemleri, kaynakları ve ses hızını denetler. Bu yalnızca mekanik ön
   kontroldür; iddianın doğruluğunu veya estetik kaliteyi otomatik kanıtlamaz.
4. Sunucuda kısa 3D çekimleri bir kez render edip önbelleğe al; hareketli
   açıklama katmanlarını ve altyazıları daha hafif bir compositor ile üret.
   Tam EEVEE render, tüm 30–40 saniye için varsayılan olmamalı. Başlangıç
   deneyi 8 örneklem/tam çözünürlük; hareketli sahnelerde titreme ve gürültü
   incelenmeden üretim ayarı olarak sabitlenmemeli.
5. İki pilotun MP4 çıktısını telefonda ve bilgisayarda izle: ilk iki saniye,
   mekanik doğruluk, söylenenle görülenin uyumu, okunabilir altyazı, ses,
   telif kaydı, render süresi ve disk tepe kullanımı. Kullanıcı kabul etmeden
   video havuzuna veya yayıncıya bağlama.
6. Canlı sunucu kodunu GitHub ile güvenle uzlaştır. Yeni format için ayrı
   `format_version`/şablon işareti ve format bazlı stok hesabı ekle. Eski 29
   aday yeni formatın stokunu doldurmuş sayılmamalı; yeni format dışındaki
   eski videolar da otomatik yayına gitmemeli.
7. Önce haftada üç ayrı gün tekil yayınla. Birkaç haftalık veri ve üretim
   kararlılığı görülürse dörde çıkar. Toplu yükleme yok. Kullanıcı onayı ve
   YouTube API/kanal görünürlük kısıtları aynen korunur.

## Ölçüm ve karar

YouTube Studio'daki *gösterildiğinde izlemeyi seçme oranı* (viewed vs swiped),
ilk saniyelerde tutma, ortalama izleme süresi/yüzdesi ve tekrar izleme önce;
izlenme ve beğeni sonra değerlendirilir. Aynı şablondan ve aynı konudan
tekrarlı seri üretim yapılmaz. İki pilot yeterince iyi değilse yayın başlamaz;
önce sahneler iyileştirilir. İzlenme veya para kazanma garantisi verilmez.
