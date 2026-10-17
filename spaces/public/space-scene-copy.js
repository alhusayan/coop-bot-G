// Short, pretranslated controls. No live translation or generated UI copy.
const keys=['title','add','example','create','options','working','choose','tap','cost','take','photos','done'];
const rows={
 en:['Design your space.','Add a photo','Try an example','Create designs','Options','Designing your space…','Open design','Tap a piece to find it in stores','3 designs · 3 credits','Take a photo','Choose a photo','Done'],
 ar:['صمّم مساحتك.','أضف صورة','جرّب مثال','صمّم','خيارات','نصمّم مساحتك…','افتح التصميم','اضغط على أي قطعة لنبحث عنها بالمتاجر','٣ تصاميم · ٣ أرصدة','التقط صورة','اختر من الصور','تم'],
 fr:['Créez votre espace.','Ajouter une photo','Voir un exemple','Créer les designs','Options','Création de votre espace…','Ouvrir le design','Touchez un objet pour le trouver en magasin','3 designs · 3 crédits','Prendre une photo','Choisir une photo','Terminé'],
 de:['Gestalten Sie Ihren Raum.','Foto hinzufügen','Beispiel ansehen','Designs erstellen','Optionen','Ihr Raum wird gestaltet…','Design öffnen','Tippen Sie auf ein Möbelstück, um es im Handel zu finden','3 Designs · 3 Guthaben','Foto aufnehmen','Foto auswählen','Fertig'],
 es:['Diseña tu espacio.','Añadir foto','Ver un ejemplo','Crear diseños','Opciones','Diseñando tu espacio…','Abrir diseño','Toca una pieza para encontrarla en tiendas','3 diseños · 3 créditos','Hacer una foto','Elegir una foto','Listo'],
 it:['Progetta il tuo spazio.','Aggiungi una foto','Vedi un esempio','Crea i progetti','Opzioni','Progettazione in corso…','Apri progetto','Tocca un oggetto per trovarlo nei negozi','3 progetti · 3 crediti','Scatta una foto','Scegli una foto','Fatto'],
 pt:['Crie seu espaço.','Adicionar foto','Ver um exemplo','Criar designs','Opções','Criando seu espaço…','Abrir design','Toque em uma peça para encontrá-la nas lojas','3 designs · 3 créditos','Tirar uma foto','Escolher uma foto','Pronto'],
 ru:['Создайте свой интерьер.','Добавить фото','Посмотреть пример','Создать дизайны','Параметры','Создаём ваш интерьер…','Открыть дизайн','Нажмите на предмет, чтобы найти его в магазинах','3 дизайна · 3 кредита','Сделать фото','Выбрать фото','Готово'],
 zh:['设计你的空间。','添加照片','查看示例','创建设计','选项','正在设计你的空间…','打开设计','点击物品，在商店中查找','3个设计 · 3积分','拍照','选择照片','完成'],
 ja:['あなたの空間をデザイン。','写真を追加','実例を見る','デザインを作成','オプション','空間をデザイン中…','デザインを開く','家具をタップしてお店で探す','3案 · 3クレジット','写真を撮る','写真を選ぶ','完了'],
 ko:['내 공간을 디자인하세요.','사진 추가','예시 보기','디자인 만들기','옵션','공간을 디자인하는 중…','디자인 열기','가구를 눌러 판매 매장을 찾아보세요','디자인 3개 · 3크레딧','사진 촬영','사진 선택','완료'],
 hi:['अपनी जगह सजाएँ।','तस्वीर जोड़ें','उदाहरण देखें','डिज़ाइन बनाएँ','विकल्प','आपकी जगह डिज़ाइन हो रही है…','डिज़ाइन खोलें','दुकानों में खोजने के लिए किसी वस्तु पर टैप करें','3 डिज़ाइन · 3 क्रेडिट','तस्वीर लें','तस्वीर चुनें','हो गया'],
 ur:['اپنی جگہ سجائیں۔','تصویر شامل کریں','مثال دیکھیں','ڈیزائن بنائیں','اختیارات','آپ کی جگہ ڈیزائن ہو رہی ہے…','ڈیزائن کھولیں','دکانوں میں تلاش کرنے کے لیے کسی چیز کو دبائیں','3 ڈیزائن · 3 کریڈٹ','تصویر لیں','تصویر منتخب کریں','مکمل'],
 id:['Desain ruang Anda.','Tambahkan foto','Lihat contoh','Buat desain','Opsi','Mendesain ruang Anda…','Buka desain','Ketuk barang untuk mencarinya di toko','3 desain · 3 kredit','Ambil foto','Pilih foto','Selesai'],
 ms:['Reka ruang anda.','Tambah foto','Lihat contoh','Cipta rekaan','Pilihan','Mereka ruang anda…','Buka rekaan','Ketik barangan untuk mencarinya di kedai','3 rekaan · 3 kredit','Ambil foto','Pilih foto','Selesai'],
 nl:['Ontwerp je ruimte.','Foto toevoegen','Bekijk voorbeeld','Ontwerpen maken','Opties','Je ruimte wordt ontworpen…','Open ontwerp','Tik op een item om het in winkels te vinden','3 ontwerpen · 3 credits','Foto maken','Foto kiezen','Klaar'],
 tr:['Alanını tasarla.','Fotoğraf ekle','Örneği gör','Tasarımlar oluştur','Seçenekler','Alanınız tasarlanıyor…','Tasarımı aç','Mağazalarda bulmak için bir parçaya dokun','3 tasarım · 3 kredi','Fotoğraf çek','Fotoğraf seç','Bitti']
};
const navigation={
 en:['Redesign','New design'],ar:['أعد التصميم','تصميم جديد'],fr:['Recréer','Nouveau projet'],de:['Neu gestalten','Neuer Entwurf'],es:['Rediseñar','Nuevo diseño'],it:['Ridisegna','Nuovo progetto'],pt:['Redesenhar','Novo design'],ru:['Переделать','Новый дизайн'],zh:['重新设计','新设计'],ja:['再デザイン','新しいデザイン'],ko:['다시 디자인','새 디자인'],hi:['फिर डिज़ाइन करें','नया डिज़ाइन'],ur:['دوبارہ ڈیزائن','نیا ڈیزائن'],id:['Desain ulang','Desain baru'],ms:['Reka semula','Rekaan baharu'],nl:['Opnieuw ontwerpen','Nieuw ontwerp'],tr:['Yeniden tasarla','Yeni tasarım']
};
keys.push('redesign','newDesign');for(const language of Object.keys(rows))rows[language].push(...navigation[language]);
export const sceneLanguages=Object.keys(rows);
export const sceneText=(language,key)=>(rows[language]||rows.en)[keys.indexOf(key)]||key;
