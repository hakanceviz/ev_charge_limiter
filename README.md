# EV Charge Limiter

Home Assistant için HACS uyumlu özel entegrasyon.

Bu entegrasyon, araçtan gerçek batarya yüzdesi okunamadığı durumlarda şarj cihazının verdiği kWh değerini kullanarak tahmini hedef SoC'ye ulaşınca şarjı otomatik durdurur.

v0.3.0 ile OCPP `charger_maximum_current` / maksimum şarj akımı entity desteği eklendi. Entegrasyon artık hedef amper değerini kendi slider'ında gösterir; yeni oturum başlatılırken önce şarj cihazına bu amper limitini yazar, sonra şarjı başlatır ve kWh takibini yapar.

v0.2.0 ile opsiyonel anlık güç sensörü desteği eklenmişti. Güç sensörü seçilirse entegrasyon kalan süreyi tahmin eder ve sensör gecikmesinde akabilecek enerjiyi hesaplayarak dinamik erken kesme tamponu uygular.

Örnek kullanım:

- Araç batarya kapasitesi: `60 kWh`
- Başlangıç SoC: `%35`
- Hedef SoC: `%80`
- AC şarj verimi: `%90`
- Anlık güç: `10 kW`
- Güç sensörü gecikmesi: `60 sn`

Hesap:

```text
Gerekli enerji = 60 × (80 - 35) / 100 / 0.90 = 30 kWh
Dinamik tampon = 10 kW × 60 sn / 3600 = 0.167 kWh
Kesme eşiği = gerekli enerji - manuel tampon - dinamik tampon
```

Yani şarj gücü 4 kW'dan 10 kW'a yükselirse kalan süre tahmini ve dinamik tampon otomatik değişir. Durdurma kararı yine toplam verilen `kWh` üzerinden verilir; bu yüzden güç değişimlerinde süre değişir ama hedef enerji mantığı bozulmaz.

> Bu entegrasyon aracın BMS verisini okumaz. Sonuç tahminidir. İlk birkaç şarjdan sonra verim, manuel tampon ve güç sensörü gecikmesi ayarlanmalıdır.

## Özellikler

- UI üzerinden kurulum.
- OCPP enerji sensörü ve şarj durdurma entity'si seçimi.
- Opsiyonel anlık güç sensörü seçimi.
- Opsiyonel `charger_maximum_current` / maksimum akım entity seçimi.
- Şarj başlatılırken seçilen amper değerini OCPP akım entity'sine otomatik yazma.
- Şarj başlatma entity'si seçimi; switch ise `turn_on`, button ise `press` yapılır.
- Batarya kapasitesi, başlangıç yüzdesi, hedef yüzde, AC verimi, charger maximum current, manuel erken durdurma tamponu ve güç sensörü gecikmesi için `number` entity'leri.
- Otomatik durdurmayı aç/kapatmak için `switch` entity'si.
- Dinamik güç tamponunu aç/kapatmak için ayrı `switch` entity'si.
- Yeni oturum başlatma ve hemen durdurma için `button` entity'leri.
- Gerekli enerji, kesme eşiği, verilen enerji, kalan enerji, anlık güç, tahmini kalan süre ve tahmini bitiş zamanı sensörleri.
- `Session`, `Cumulative` ve `Interval delta` enerji sensörü modu.
- Hedefe ulaşınca `persistent_notification` bildirimi.
- Entegrasyon ayarlarından sensörleri sonradan değiştirme desteği.

## Kurulum - HACS custom repository

1. Bu klasörü GitHub'da yeni bir repository olarak yayınlayın.
2. Home Assistant > HACS > üç nokta > Custom repositories.
3. Repository URL'sini ekleyin.
4. Category olarak `Integration` seçin.
5. EV Charge Limiter'ı kurun.
6. Home Assistant'ı yeniden başlatın.
7. Ayarlar > Cihazlar ve Hizmetler > Entegrasyon Ekle > EV Charge Limiter.

## Manuel kurulum

1. `custom_components/ev_charge_limiter` klasörünü Home Assistant config klasörünüzdeki `custom_components/` içine kopyalayın.
2. Home Assistant'ı yeniden başlatın.
3. Ayarlar > Cihazlar ve Hizmetler > Entegrasyon Ekle > EV Charge Limiter.

## Kurulumda seçilecek alanlar

### Energy sensor

OCPP entegrasyonunda genelde şu tarz sensörlerden biri seçilir:

- `Energy Active Import Register`
- `Energy Active Import Interval`
- `Energy Session`

Tavsiye: Oturum başında sıfırlanan kWh sensörünü seçin.

### Power sensor

Opsiyoneldir ama önerilir. OCPP entegrasyonunda genelde şu tarz sensörlerden biri seçilir:

- `Power Active Import`
- `Charging Power`
- `Current Power`

Bu sensör `kW` veya `W` olabilir. Entegrasyon otomatik olarak `kW` değerine çevirir.

### Charger maximum current entity

Opsiyoneldir ama bu sürümde önerilir. OCPP entegrasyonunda genelde şu tarz bir `number` entity olur:

- `number.xxx_charger_maximum_current`
- `number.xxx_maximum_current`
- `number.xxx_current_limit`

Birim `A` olmalıdır. Günlük kullanımda entegrasyonun oluşturduğu `Charger Maximum Current` slider'ını örneğin `6`, `10`, `16`, `20`, `32` amper gibi ayarlarsınız. `Start New Session` basılınca bu değer önce OCPP entity'sine yazılır.

### Start entity

Opsiyoneldir. Genelde `Stop entity` ile aynı `switch.xxx_charge_control` seçilebilir. Entegrasyon yeni oturum başlatırken:

- `switch` / `input_boolean` seçildiyse `turn_on` çağırır.
- `button` seçildiyse `button.press` çağırır.
- Boş bırakılırsa cihazın zaten otomatik şarja başladığı varsayılır.

### Stop entity

Genelde OCPP cihazında şu entity seçilir:

- `switch.xxx_charge_control`
- `switch.xxx_charge_control_connector_1`
- Bazı kurulumlarda `button.xxx_stop` gibi bir buton

Bu entity kapatıldığında veya basıldığında şarj durmalıdır.

### Energy sensor mode

- `Session register`: Enerji sensörü her şarj oturumunda sıfırlanıyorsa bunu seçin. OCPP'de çoğu zaman doğru seçenek budur.
- `Cumulative meter`: Enerji sensörü toplam sayaç gibi sürekli artıyorsa bunu seçin. Oturum başlatıldığında o anki değer baseline alınır.
- `Interval delta`: Enerji sensörü her güncellemede sadece son aralığın tüketimini veriyorsa bunu seçin. Entegrasyon değerleri toplayarak oturum enerjisini hesaplar.

## Günlük kullanım

1. Aracı takın.
2. `Start SoC` değerine aracın ekrandaki mevcut yüzdesini girin.
3. `Target SoC` değerini örneğin `%80` yapın.
4. `Battery Capacity` değerini aracın kullanılabilir batarya kapasitesine yakın girin.
5. `Charging Efficiency` için ilk denemede `%90` kullanın.
6. `Charger Maximum Current` değerini istediğiniz amper yapın; örneğin `10 A`, `16 A` veya `32 A`.
7. `Manual Early Stop Buffer` için ilk denemede `0.10 - 0.30 kWh` kullanın.
8. `Power Sensor Lag` için enerji/güç sensörünüz dakikada bir güncelleniyorsa `60 sn` kullanın.
9. `Apply Current On Start` açık kalsın.
10. `Start Charger On Session Start` açık kalsın.
11. `Dynamic Power Buffer Enabled` açık kalsın.
12. `Start New Session` butonuna basın veya `Auto Stop Enabled` switch'ini açın. Entegrasyon önce amper limitini yazar, sonra şarjı başlatır.
13. Hedef enerjiye ulaşınca entegrasyon şarjı durdurur.

## Yeni sensörler

- `Required Grid Energy`: Başlangıç yüzdesinden hedef yüzdesine gitmek için gereken brüt enerji.
- `Stop Threshold Energy`: Manuel + dinamik tampon düşüldükten sonra şarjın kesileceği enerji.
- `Delivered Energy`: Bu oturumda verilen enerji.
- `Remaining Energy To Stop`: Durdurma eşiğine kalan enerji.
- `Remaining Energy To Target`: Tam hedef enerjiye kalan enerji.
- `Charger Maximum Current`: Entegrasyonun başlatırken uygulayacağı hedef amper.
- `Actual Charger Maximum Current`: OCPP akım entity'sinden okunan mevcut amper limiti.
- `Current Charging Power`: Seçilen güç sensörünün kW değeri.
- `Dynamic Power Buffer`: Anlık güce ve sensör gecikmesine göre hesaplanan tampon.
- `Estimated Time Remaining`: Mevcut güç değişmezse kalan süre.
- `Estimated Finish Time`: Mevcut güç değişmezse tahmini bitiş zamanı.
- `Estimated SoC`: Girilen başlangıç yüzdesi, batarya kapasitesi ve verimle hesaplanan tahmini SoC.

## Dinamik tampon nasıl çalışır?

Dinamik tampon şu formülle hesaplanır:

```text
Dinamik tampon kWh = anlık güç kW × sensör gecikmesi saniye / 3600
```

Örnek:

- 4 kW ve 60 saniye gecikme: `0.067 kWh`
- 10 kW ve 60 saniye gecikme: `0.167 kWh`
- 11 kW ve 90 saniye gecikme: `0.275 kWh`

Bu tampon hedefe yaklaşınca daha erken durdurma sağlar. Böylece sensör geç güncelleniyorsa hedefi daha az aşarsınız.

## Kalibrasyon

Eğer araç hedeflediğinizden daha yüksek yüzdeye çıkıyorsa:

- `Manual Early Stop Buffer` değerini artırın.
- `Power Sensor Lag` değerini artırın.
- Ya da `Charging Efficiency` değerini biraz düşürün.

Eğer araç hedeflediğinizden düşük kalıyorsa:

- `Manual Early Stop Buffer` değerini azaltın.
- `Power Sensor Lag` değerini azaltın.
- Ya da `Charging Efficiency` değerini biraz yükseltin.

## Servisler

### `ev_charge_limiter.start_session`

Yeni oturum başlatır ve otomatik durdurmayı aktif eder.

### `ev_charge_limiter.stop_now`

Şarjı hemen durdurur.

### `ev_charge_limiter.set_charger_current`

Hedef maksimum şarj akımını amper olarak ayarlar. Aktif oturum varsa ve akım entity'si seçiliyse değeri cihaza hemen uygular.

Örnek:

```yaml
service: ev_charge_limiter.set_charger_current
data:
  current: 16
```

### `ev_charge_limiter.set_start_soc`

Başlangıç yüzdesini ayarlar, baseline alır ve oturumu başlatır.

Örnek:

```yaml
service: ev_charge_limiter.set_start_soc
data:
  start_soc: 35
```

Birden fazla EV Charge Limiter entry varsa `entry_id` ekleyin.

## Güvenlik notu

Bu entegrasyon şarj durdurmayı Home Assistant ve OCPP bağlantısına bağlı olarak yapar. Ağ bağlantısı koparsa veya OCPP entity'leri unavailable olursa şarj kesilemeyebilir. Araç ve şarj cihazı üzerindeki kendi limitlerini de mümkünse aktif kullanın.
