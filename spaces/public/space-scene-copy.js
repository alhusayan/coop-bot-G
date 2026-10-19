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
const workspace={
 en:['Your space','Change photo','Back to design','Make it yours.','One photo. Three ideas for your space.','Anything in mind? (optional)','Before','After','All pieces'],
 ar:['مساحتك','غيّر الصورة','ارجع للتصميم','على ذوقك.','صورة واحدة، وثلاث أفكار لمساحتك.','في بالك شيء؟ (اختياري)','قبل','بعد','كل القطع'],
 fr:['Votre espace','Changer la photo','Retour au design','À votre image.','Une photo. Trois idées pour votre espace.','Une envie ? (facultatif)','Avant','Après','Tous les objets'],
 de:['Ihr Raum','Foto ändern','Zurück zum Design','Ganz nach Ihrem Geschmack.','Ein Foto. Drei Ideen für Ihren Raum.','Besondere Wünsche? (optional)','Vorher','Nachher','Alle Objekte'],
 es:['Tu espacio','Cambiar foto','Volver al diseño','A tu gusto.','Una foto. Tres ideas para tu espacio.','¿Alguna idea? (opcional)','Antes','Después','Todas las piezas'],
 it:['Il tuo spazio','Cambia foto','Torna al progetto','A modo tuo.','Una foto. Tre idee per il tuo spazio.','Qualche desiderio? (facoltativo)','Prima','Dopo','Tutti gli oggetti'],
 pt:['Seu espaço','Alterar foto','Voltar ao design','Do seu jeito.','Uma foto. Três ideias para seu espaço.','Alguma ideia? (opcional)','Antes','Depois','Todas as peças'],
 ru:['Ваше пространство','Изменить фото','Вернуться к дизайну','В вашем стиле.','Одно фото. Три идеи для вашего пространства.','Есть пожелания? (необязательно)','До','После','Все предметы'],
 zh:['你的空间','更换照片','返回设计','打造你的风格。','一张照片，三种空间灵感。','有什么想法？（选填）','改造前','改造后','所有物品'],
 ja:['あなたの空間','写真を変更','デザインに戻る','あなたらしく。','1枚の写真から、3つのアイデア。','ご希望は？（任意）','変更前','変更後','すべての家具'],
 ko:['내 공간','사진 변경','디자인으로 돌아가기','내 취향대로.','사진 한 장, 내 공간을 위한 세 가지 아이디어.','원하는 것이 있나요? (선택)','이전','이후','모든 가구'],
 hi:['आपकी जगह','तस्वीर बदलें','डिज़ाइन पर वापस जाएँ','अपनी पसंद से।','एक तस्वीर। आपकी जगह के लिए तीन विचार।','कोई इच्छा? (वैकल्पिक)','पहले','बाद में','सभी वस्तुएँ'],
 ur:['آپ کی جگہ','تصویر بدلیں','ڈیزائن پر واپس جائیں','اپنی پسند کے مطابق۔','ایک تصویر۔ آپ کی جگہ کے لیے تین تجاویز۔','کوئی خواہش؟ (اختیاری)','پہلے','بعد','تمام اشیا'],
 id:['Ruang Anda','Ganti foto','Kembali ke desain','Sesuai selera Anda.','Satu foto. Tiga ide untuk ruang Anda.','Ada keinginan? (opsional)','Sebelum','Sesudah','Semua barang'],
 ms:['Ruang anda','Tukar foto','Kembali ke rekaan','Mengikut cita rasa anda.','Satu foto. Tiga idea untuk ruang anda.','Ada keinginan? (pilihan)','Sebelum','Selepas','Semua barangan'],
 nl:['Jouw ruimte','Foto wijzigen','Terug naar ontwerp','Helemaal jouw stijl.','Eén foto. Drie ideeën voor jouw ruimte.','Speciale wensen? (optioneel)','Voor','Na','Alle items'],
 tr:['Alanınız','Fotoğrafı değiştir','Tasarıma dön','Sizin tarzınız.','Bir fotoğraf. Alanınız için üç fikir.','Bir isteğiniz var mı? (isteğe bağlı)','Önce','Sonra','Tüm parçalar']
};
keys.push('yourPhoto','changePhoto','backToDesign','makeItYours','setupHint','wishes','before','after','allPieces');
for(const language of Object.keys(rows))rows[language].push(...workspace[language]);
export const sceneLanguages=Object.keys(rows);
export const sceneText=(language,key)=>(rows[language]||rows.en)[keys.indexOf(key)]||key;
