# Kilit pilotları: ne iyileşti, ne eksik?

## Sürüm geçmişi

1. `lock_story.py` + `compose_lock.py`: ilk basit kesit. Parçalar kapı kilidinden kopuk ve oyuncak benzeriydi.
2. `lock_realistic_story.py` + `compose_lock_realistic.py`: rozet, anahtar deliği, dişli anahtar, beş pim çifti, yaylar, dönme çizgisi, göbek ve sürgü. Yerel çıktı `storage/3d-pilots/builtwhys-lock-realistic-pilot.mp4`; `storage/` Git'e alınmaz.

## Dürüst kalite değerlendirmesi

İkinci sürüm daha iyi bir teknik prototip ama referans düzeyinde bir Short değil. “Anahtar girince hangi diş hangi alt pimi ne kadar kaldırdı, üst pim neden göbeği artık bloke etmiyor?” sorusunu tek bakışta açıklamıyor. Anahtarın ilerlemesi ile pinlerin hareketi aynı kesintisiz yakın planda görünmeli; bugünkü kesmeler neden–sonuç ilişkisini zayıflatıyor. Kesit hâlâ şematik; malzeme/ölçek/anahtar deliği profili gerçek ürün çekimi düzeyinde değil. İlk saniyedeki merak kancası zayıf. İngilizce konuşmalı anlatım yok.

Bu nedenle “çok izlenir” beklentisiyle yayımlamak doğru olmaz. İzlenmeyi önceden garanti edemeyiz. Yayınlanabilir sürümden sonra YouTube Studio'da *Shorts feed'de gösterim*, *izlemeyi seçme/kaydırma oranı*, ilk saniyelerde tutma ve ortalama izlenme süresi ölçülmelidir. Bunlar YouTube'un [resmî Shorts analiz ölçüleridir](https://support.google.com/youtube/answer/12942217?co=YOUTUBE._YTVideoType%3Dshorts&hl=en).

## Üçüncü deneme için sahne planı

| Zaman | Tek görsel iddia | Fiziksel hareket |
| --- | --- | --- |
| 0–2 sn | “Yanlış anahtar neden dönmez?” | Gerçekçi yüz, yanlış anahtar girer, dönme denemesi mekanik olarak durur. |
| 2–6 sn | Bloke eden parça | Aynı kilide kesit geçişi; **bir** üst pim göbek çizgisini kestiği için dönme durur. |
| 6–13 sn | Doğru anahtarın her dişi | Doğru anahtar ilerlerken 1→5 alt pimler sırayla farklı yüksekliğe çıkar. Her pim temas ettiği anahtar dişiyle hareket eder. |
| 13–18 sn | Dönme çizgisi | Beş pim birleşimi çizgiye ayrı ayrı gelir, sonra beşi geniş planda aynı anda görünür. |
| 18–23 sn | Sonuç | Göbek döner, kam sürgüyü geri çeker, kapı açılır. |
| 23–27 sn | Özet | Kısa İngilizce kapanış, sade marka işareti. |

**Geçme koşulu:** Ses kapalıyken bile anahtar dişi → alt pim → üst pim → dönme çizgisi → sürgü ilişkisi anlaşılmalı. Mekanik olarak yanlış pin hareketi veya ilişkisiz sahne varsa pilot reddedilir. Güvenilir bir kesit referansıyla profil/ölçü kontrol edilir; amaç kilit atlatma değil normal anahtar işleyişini açıklamaktır.

## “Bunu AI ile yapmışlar” varsayımı

Referans videonun üreticisinin kullandığı araçları doğrulayan proje dosyası/açıklama elimizde yok. Tamamının tek komutla yapay zekâ tarafından üretildiğini söyleyemeyiz. Kaliteli sonuç AI fikir/senaryo/sahne planı, doğrulanmış 3D varlık, kontrollü animasyon, TTS, ses tasarımı ve kare incelemesinin birleşimi olabilir. Modelin “kilit açılıyor” yazması, temas fiziğini doğru canlandırdığı anlamına gelmez. Bizim eksik halkamız yalnızca render gücü değil; doğrulanmış varlık/rig ve sahne yönetimi.

Pilot Blender + FFmpeg ile yerelde oluşturuldu. Konuşma yok, yalnızca özgün mekanik sesler var. Sunucuya veya otomatik yayın sırasına alınmadı.
