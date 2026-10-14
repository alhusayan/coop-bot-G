const keys='title teaser intro begin cost free depth products layout render verify ready estimate error missing demo'.split(' ');
const copy={
 en:'Design & furnish|An optional design using real store pieces|Enter the room’s length and width. We’ll choose up to three main pieces with listed measurements.|Furnish with store pieces|Up to {count} new searches · {count} credits|Uses saved searches · no new search credits|Reading the room’s depth|Checking products and measurements|Planning the furniture layout|Creating your furnished preview|Checking the room and chosen pieces|Your furnished preview|Approximate preview. Confirm measurements before buying. Delivery and installation are not included.|We couldn’t verify a suitable layout. Your original design is unchanged.|We need at least two suitable pieces with clear dimensions and confirmed availability.|Upload your own room to try this option.',
 ar:'التصميم والتنفيذ|خيار إضافي لتأثيث غرفتك بقطع من المتاجر|أدخل طول الغرفة وعرضها. سنختار حتى ثلاث قطع رئيسية بمقاسات موثقة.|أثّث بقطع من المتاجر|حتى {count} عمليات بحث جديدة · {count} أرصدة|باستخدام البحث المحفوظ · دون أرصدة بحث إضافية|جارٍ تحليل عمق الغرفة|جارٍ فحص القطع ومقاساتها|جارٍ تخطيط توزيع الأثاث|جارٍ إعداد صورة التأثيث|جارٍ التحقق من الغرفة والقطع|تصوّر التأثيث المقترح|تصوّر تقريبي. تحقق من المقاسات قبل الشراء. لا يشمل التوصيل أو التركيب.|تعذّر التحقق من توزيع مناسب. بقي تصميمك الأصلي كما هو.|نحتاج إلى قطعتين مناسبتين على الأقل بمقاسات واضحة وتوفّر مؤكد.|أضف صورة غرفتك لتجربة هذا الخيار.',
 fr:'Concevoir et meubler|Une option avec de vrais meubles en magasin|Indiquez la longueur et la largeur de la pièce. Nous choisirons jusqu’à trois meubles aux dimensions renseignées.|Meubler avec des produits en magasin|Jusqu’à {count} nouvelles recherches · {count} crédits|Recherches enregistrées · aucun crédit supplémentaire|Analyse de la profondeur de la pièce|Vérification des produits et dimensions|Préparation de l’agencement|Création de votre aperçu meublé|Vérification de la pièce et des meubles|Votre aperçu meublé|Aperçu approximatif. Vérifiez les mesures avant achat. Livraison et montage non compris.|Nous n’avons pas pu valider un agencement adapté. Votre projet original est conservé.|Il faut au moins deux meubles adaptés avec des dimensions précises et une disponibilité confirmée.|Ajoutez une photo de votre pièce pour essayer.',
 de:'Gestalten und einrichten|Optional mit echten Möbeln aus dem Handel|Geben Sie Länge und Breite des Raums ein. Wir wählen bis zu drei Möbel mit angegebenen Maßen.|Mit echten Möbeln einrichten|Bis zu {count} neue Suchen · {count} Credits|Gespeicherte Suchen · keine zusätzlichen Such-Credits|Raumtiefe wird analysiert|Produkte und Maße werden geprüft|Möbelanordnung wird geplant|Einrichtungsvorschau wird erstellt|Raum und Möbel werden geprüft|Ihre Einrichtungsvorschau|Ungefähre Vorschau. Maße vor dem Kauf prüfen. Ohne Lieferung und Montage.|Eine passende Anordnung konnte nicht bestätigt werden. Ihr ursprünglicher Entwurf bleibt erhalten.|Mindestens zwei passende Möbel mit eindeutigen Maßen und bestätigter Verfügbarkeit sind nötig.|Laden Sie ein Foto Ihres Raums hoch, um diese Option zu testen.',
 es:'Diseñar y amueblar|Una opción con muebles reales de tiendas|Indica el largo y el ancho de la habitación. Elegiremos hasta tres muebles con medidas publicadas.|Amueblar con productos de tiendas|Hasta {count} búsquedas nuevas · {count} créditos|Búsquedas guardadas · sin créditos adicionales|Analizando la profundidad de la habitación|Comprobando productos y medidas|Planificando la distribución|Creando tu vista amueblada|Comprobando la habitación y los muebles|Tu propuesta de mobiliario|Vista aproximada. Confirma las medidas antes de comprar. No incluye entrega ni montaje.|No pudimos validar una distribución adecuada. Tu diseño original se conserva.|Necesitamos al menos dos muebles adecuados con medidas claras y disponibilidad confirmada.|Sube una foto de tu habitación para probar esta opción.',
 it:'Progetta e arreda|Un’opzione con mobili reali dei negozi|Inserisci lunghezza e larghezza della stanza. Sceglieremo fino a tre mobili con misure dichiarate.|Arreda con prodotti dei negozi|Fino a {count} nuove ricerche · {count} crediti|Ricerche salvate · nessun credito aggiuntivo|Analisi della profondità della stanza|Verifica di prodotti e misure|Pianificazione della disposizione|Creazione dell’anteprima arredata|Verifica della stanza e dei mobili|La tua proposta d’arredo|Anteprima approssimativa. Verifica le misure prima dell’acquisto. Consegna e montaggio esclusi.|Non siamo riusciti a convalidare una disposizione adatta. Il progetto originale è conservato.|Servono almeno due mobili adatti con misure chiare e disponibilità confermata.|Carica una foto della tua stanza per provare.',
 pt:'Projetar e mobilar|Uma opção com móveis reais de lojas|Indique o comprimento e a largura da divisão. Escolheremos até três móveis com medidas publicadas.|Mobilar com produtos de lojas|Até {count} novas pesquisas · {count} créditos|Pesquisas guardadas · sem créditos adicionais|A analisar a profundidade da divisão|A verificar produtos e medidas|A planear a disposição dos móveis|A criar a pré-visualização mobilada|A verificar a divisão e os móveis|A sua proposta de mobiliário|Pré-visualização aproximada. Confirme as medidas antes de comprar. Entrega e montagem não incluídas.|Não foi possível validar uma disposição adequada. O projeto original foi mantido.|Precisamos de pelo menos dois móveis adequados com medidas claras e disponibilidade confirmada.|Carregue uma foto da sua divisão para experimentar.',
 nl:'Ontwerpen en inrichten|Optioneel met echte meubels uit winkels|Vul de lengte en breedte van de kamer in. We kiezen maximaal drie meubels met vermelde afmetingen.|Inrichten met winkelproducten|Maximaal {count} nieuwe zoekopdrachten · {count} credits|Opgeslagen zoekopdrachten · geen extra zoekcredits|Diepte van de kamer analyseren|Producten en afmetingen controleren|Meubelindeling plannen|Inrichtingsvoorbeeld maken|Kamer en meubels controleren|Uw inrichtingsvoorstel|Globale indruk. Controleer de maten vóór aankoop. Zonder levering of montage.|We konden geen passende indeling bevestigen. Uw oorspronkelijke ontwerp blijft behouden.|Er zijn minstens twee geschikte meubels nodig met duidelijke maten en bevestigde beschikbaarheid.|Upload een foto van uw kamer om dit te proberen.',
 tr:'Tasarla ve döşe|Mağazalardaki gerçek mobilyalarla ek seçenek|Odanın uzunluğunu ve genişliğini girin. Ölçüleri belirtilmiş en fazla üç ana mobilya seçeceğiz.|Mağaza ürünleriyle döşe|En fazla {count} yeni arama · {count} kredi|Kayıtlı aramalar · ek arama kredisi yok|Odanın derinliği analiz ediliyor|Ürünler ve ölçüler kontrol ediliyor|Mobilya yerleşimi planlanıyor|Döşenmiş oda önizlemesi hazırlanıyor|Oda ve mobilyalar kontrol ediliyor|Mobilya yerleşimi öneriniz|Yaklaşık önizleme. Satın almadan önce ölçüleri doğrulayın. Teslimat ve kurulum dahil değildir.|Uygun bir yerleşim doğrulanamadı. İlk tasarımınız korundu.|Net ölçülere ve doğrulanmış stok bilgisine sahip en az iki uygun mobilya gerekiyor.|Bu seçeneği denemek için odanızın fotoğrafını yükleyin.',
 ru:'Дизайн и меблировка|Дополнительный вариант с мебелью из магазинов|Укажите длину и ширину комнаты. Мы подберём до трёх основных предметов с указанными размерами.|Обставить мебелью из магазинов|До {count} новых поисков · {count} кредитов|Сохранённые поиски · без дополнительных кредитов|Анализируем глубину комнаты|Проверяем товары и размеры|Планируем расстановку мебели|Создаём предварительный вид комнаты|Проверяем комнату и выбранную мебель|Предложенный вариант меблировки|Примерная визуализация. Уточните размеры перед покупкой. Доставка и сборка не включены.|Не удалось подтвердить подходящую расстановку. Исходный дизайн сохранён.|Нужны как минимум два подходящих предмета с точными размерами и подтверждённым наличием.|Загрузите фото своей комнаты, чтобы попробовать.',
 zh:'设计与配家具|可选功能：使用商店里的真实家具|请输入房间的长度和宽度。我们将选择最多三件有明确尺寸的主要家具。|使用商店家具布置|最多 {count} 次新搜索 · {count} 点数|使用已保存搜索 · 无需额外搜索点数|正在分析房间深度|正在核对商品与尺寸|正在规划家具布局|正在生成布置效果图|正在核对房间与家具|您的家具布置方案|此为近似效果图。购买前请核实尺寸。不含配送和安装。|未能确认合适的布局，原设计已保留。|需要至少两件尺寸明确且确认有货的合适家具。|上传您房间的照片即可尝试。',
 ja:'デザインと家具配置|実際に販売されている家具を使う追加機能|部屋の縦と横の長さを入力してください。寸法が明記された主な家具を最大3点選びます。|お店の家具で配置する|新しい検索は最大 {count} 回 · {count} クレジット|保存済みの検索を使用 · 追加の検索クレジット不要|部屋の奥行きを分析中|商品と寸法を確認中|家具の配置を計画中|家具配置のイメージを作成中|部屋と家具を確認中|家具配置のご提案|概算のイメージです。購入前に寸法をご確認ください。配送・組立は含まれません。|適切な配置を確認できませんでした。元のデザインは保持されています。|寸法と在庫が確認できる適切な家具が2点以上必要です。|お部屋の写真をアップロードしてお試しください。',
 ko:'디자인과 가구 배치|매장에서 판매하는 실제 가구를 활용하는 추가 옵션|방의 가로와 세로 길이를 입력하세요. 치수가 명시된 주요 가구를 최대 3개 선택합니다.|매장 가구로 꾸미기|새 검색 최대 {count}회 · {count} 크레딧|저장된 검색 사용 · 추가 검색 크레딧 없음|방의 깊이를 분석하는 중|제품과 치수를 확인하는 중|가구 배치를 계획하는 중|가구 배치 미리보기를 만드는 중|방과 가구를 확인하는 중|추천 가구 배치|대략적인 미리보기입니다. 구매 전 치수를 확인하세요. 배송과 설치는 포함되지 않습니다.|적합한 배치를 확인하지 못했습니다. 원래 디자인은 유지됩니다.|치수와 재고가 확인된 적합한 가구가 최소 2개 필요합니다.|방 사진을 업로드하여 사용해 보세요.',
 hi:'डिज़ाइन और फ़र्निशिंग|दुकानों के असली फ़र्नीचर के साथ एक अतिरिक्त विकल्प|कमरे की लंबाई और चौड़ाई दर्ज करें। हम बताए गए माप वाले अधिकतम तीन मुख्य फ़र्नीचर चुनेंगे।|दुकान के फ़र्नीचर से सजाएँ|अधिकतम {count} नई खोजें · {count} क्रेडिट|सहेजी गई खोजें · अतिरिक्त खोज क्रेडिट नहीं|कमरे की गहराई का विश्लेषण हो रहा है|उत्पादों और मापों की जाँच हो रही है|फ़र्नीचर की जगह तय हो रही है|सजे हुए कमरे का पूर्वावलोकन बन रहा है|कमरे और फ़र्नीचर की जाँच हो रही है|आपके कमरे की फ़र्निशिंग का सुझाव|यह अनुमानित पूर्वावलोकन है। खरीदने से पहले माप जाँचें। डिलीवरी और असेंबली शामिल नहीं हैं।|उपयुक्त व्यवस्था की पुष्टि नहीं हुई। आपका मूल डिज़ाइन सुरक्षित है।|स्पष्ट माप और उपलब्धता की पुष्टि वाले कम से कम दो उपयुक्त फ़र्नीचर चाहिए।|यह विकल्प आज़माने के लिए अपने कमरे की फ़ोटो अपलोड करें।',
 ur:'ڈیزائن اور فرنیچر کی ترتیب|دکانوں کے حقیقی فرنیچر کے ساتھ ایک اضافی اختیار|کمرے کی لمبائی اور چوڑائی درج کریں۔ ہم درج شدہ پیمائش والے تین تک اہم فرنیچر منتخب کریں گے۔|دکان کے فرنیچر سے سجائیں|زیادہ سے زیادہ {count} نئی تلاشیں · {count} کریڈٹس|محفوظ تلاشیں · اضافی تلاش کریڈٹس نہیں|کمرے کی گہرائی کا جائزہ لیا جا رہا ہے|مصنوعات اور پیمائش کی جانچ جاری ہے|فرنیچر کی ترتیب بنائی جا رہی ہے|سجے ہوئے کمرے کا پیش منظر بن رہا ہے|کمرے اور فرنیچر کی جانچ جاری ہے|آپ کے کمرے کی مجوزہ ترتیب|یہ اندازاً پیش منظر ہے۔ خریدنے سے پہلے پیمائش کی تصدیق کریں۔ ترسیل اور تنصیب شامل نہیں۔|مناسب ترتیب کی تصدیق نہ ہو سکی۔ آپ کا اصل ڈیزائن محفوظ ہے۔|واضح پیمائش اور تصدیق شدہ دستیابی والے کم از کم دو مناسب فرنیچر درکار ہیں۔|یہ اختیار آزمانے کے لیے اپنے کمرے کی تصویر اپ لوڈ کریں۔',
 id:'Desain dan tata furnitur|Pilihan tambahan dengan furnitur nyata dari toko|Masukkan panjang dan lebar ruangan. Kami akan memilih hingga tiga furnitur utama dengan ukuran tercantum.|Tata dengan furnitur toko|Hingga {count} pencarian baru · {count} kredit|Memakai pencarian tersimpan · tanpa kredit tambahan|Menganalisis kedalaman ruangan|Memeriksa produk dan ukuran|Merencanakan tata letak furnitur|Membuat pratinjau ruangan berfurnitur|Memeriksa ruangan dan furnitur|Usulan penataan furnitur Anda|Pratinjau perkiraan. Pastikan ukuran sebelum membeli. Pengiriman dan pemasangan tidak termasuk.|Tata letak yang sesuai belum dapat dipastikan. Desain awal Anda tetap tersimpan.|Diperlukan sedikitnya dua furnitur yang sesuai dengan ukuran jelas dan ketersediaan terkonfirmasi.|Unggah foto ruangan Anda untuk mencoba.',
 ms:'Reka bentuk dan perabot|Pilihan tambahan dengan perabot sebenar dari kedai|Masukkan panjang dan lebar bilik. Kami akan memilih sehingga tiga perabot utama dengan ukuran yang dinyatakan.|Lengkapkan dengan perabot kedai|Sehingga {count} carian baharu · {count} kredit|Menggunakan carian tersimpan · tiada kredit tambahan|Menganalisis kedalaman bilik|Menyemak produk dan ukuran|Merancang susun atur perabot|Menghasilkan pratonton bilik berperabot|Menyemak bilik dan perabot|Cadangan susun atur perabot anda|Pratonton anggaran. Sahkan ukuran sebelum membeli. Penghantaran dan pemasangan tidak termasuk.|Susun atur yang sesuai tidak dapat disahkan. Reka bentuk asal anda dikekalkan.|Sekurang-kurangnya dua perabot sesuai dengan ukuran jelas dan ketersediaan disahkan diperlukan.|Muat naik foto bilik anda untuk mencuba.'
};
export const furnishingLanguages=Object.keys(copy);
const measurementKeys=['areaLabel','invalidMeasurements','depthTitle','depthNote','layoutTitle'];
const measurements={
 en:'Area from your measurements|Enter both measurements in metres, between 1.5 and 15.|View the AI depth analysis|The AI reads near and far surfaces. Metre measurements come from the dimensions you entered, not from this depth image.|Estimated furniture layout',
 ar:'المساحة حسب قياساتك|أدخل الطول والعرض بالمتر، بين ١٫٥ و١٥ لكل منهما.|عرض تحليل العمق بالذكاء الاصطناعي|يحلّل الذكاء قرب الأسطح وبعدها. الأبعاد بالمتر مصدرها القياسات التي أدخلتها، وليست قياسًا مستخرجًا من خريطة العمق.|التوزيع التقديري للأثاث',
 fr:'Surface selon vos mesures|Saisissez les deux mesures en mètres, entre 1,5 et 15.|Voir l’analyse de profondeur par IA|L’IA distingue les surfaces proches et éloignées. Les mesures en mètres viennent des dimensions saisies, pas de cette image de profondeur.|Disposition estimée des meubles',
 de:'Fläche aus Ihren Maßen|Geben Sie beide Maße in Metern zwischen 1,5 und 15 ein.|KI-Tiefenanalyse ansehen|Die KI erkennt nahe und entfernte Flächen. Die Meterangaben stammen aus Ihren eingegebenen Maßen, nicht aus diesem Tiefenbild.|Geschätzte Möbelanordnung',
 es:'Superficie según tus medidas|Introduce ambas medidas en metros, entre 1,5 y 15.|Ver el análisis de profundidad con IA|La IA identifica superficies cercanas y lejanas. Las medidas en metros proceden de los datos que introdujiste, no de esta imagen de profundidad.|Distribución estimada de muebles',
 it:'Superficie dalle tue misure|Inserisci entrambe le misure in metri, tra 1,5 e 15.|Visualizza l’analisi della profondità con IA|L’IA distingue le superfici vicine e lontane. Le misure in metri derivano dai dati inseriti, non da questa immagine di profondità.|Disposizione stimata dei mobili',
 pt:'Área calculada com as suas medidas|Introduza as duas medidas em metros, entre 1,5 e 15.|Ver a análise de profundidade por IA|A IA identifica superfícies próximas e distantes. As medidas em metros vêm das dimensões introduzidas, não desta imagem de profundidade.|Disposição estimada dos móveis',
 nl:'Oppervlakte op basis van uw maten|Vul beide maten in meters in, tussen 1,5 en 15.|AI-diepteanalyse bekijken|De AI herkent oppervlakken dichtbij en veraf. De maten in meters komen uit uw invoer, niet uit dit dieptebeeld.|Geschatte meubelindeling',
 tr:'Girdiğiniz ölçülere göre alan|Her iki ölçüyü de metre olarak 1,5 ile 15 arasında girin.|Yapay zekâ derinlik analizini göster|Yapay zekâ yakın ve uzak yüzeyleri belirler. Metre ölçüleri bu derinlik görüntüsünden değil, girdiğiniz boyutlardan alınır.|Tahmini mobilya yerleşimi',
 ru:'Площадь по вашим размерам|Введите оба размера в метрах, от 1,5 до 15.|Посмотреть анализ глубины с ИИ|ИИ распознаёт близкие и дальние поверхности. Размеры в метрах взяты из введённых вами данных, а не из этой карты глубины.|Примерная расстановка мебели',
 zh:'根据您输入的尺寸计算的面积|请输入长和宽，单位为米，范围为1.5至15。|查看AI深度分析|AI识别表面的远近。以米为单位的尺寸来自您的输入，并非从此深度图测得。|估算的家具布局',
 ja:'入力した寸法に基づく面積|縦と横の寸法を1.5〜15メートルで入力してください。|AIの奥行き分析を見る|AIが面の近さと遠さを分析します。メートル単位の寸法は入力値に基づき、この奥行き画像からの実測値ではありません。|家具配置の概算',
 ko:'입력한 치수로 계산한 면적|가로와 세로를 각각 1.5~15미터 사이로 입력하세요.|AI 깊이 분석 보기|AI가 표면의 가깝고 먼 정도를 분석합니다. 미터 단위 치수는 이 깊이 이미지가 아니라 입력한 값에서 가져옵니다.|예상 가구 배치',
 hi:'आपके मापों से निकला क्षेत्रफल|दोनों माप मीटर में 1.5 से 15 के बीच दर्ज करें।|AI की गहराई का विश्लेषण देखें|AI पास और दूर की सतहों को पहचानता है। मीटर में माप आपके दर्ज किए गए आयामों से आते हैं, इस गहराई वाली छवि से नहीं।|फ़र्नीचर की अनुमानित व्यवस्था',
 ur:'آپ کی پیمائش سے حاصل شدہ رقبہ|دونوں پیمائشیں میٹر میں 1.5 سے 15 کے درمیان درج کریں۔|مصنوعی ذہانت کا گہرائی کا تجزیہ دیکھیں|مصنوعی ذہانت قریب اور دور کی سطحوں کو پہچانتی ہے۔ میٹر میں پیمائش آپ کی درج کردہ معلومات سے آتی ہے، گہرائی کی اس تصویر سے نہیں۔|فرنیچر کی اندازاً ترتیب',
 id:'Luas berdasarkan ukuran Anda|Masukkan kedua ukuran dalam meter, antara 1,5 dan 15.|Lihat analisis kedalaman AI|AI mengenali permukaan yang dekat dan jauh. Ukuran dalam meter berasal dari dimensi yang Anda masukkan, bukan dari gambar kedalaman ini.|Perkiraan tata letak furnitur',
 ms:'Luas berdasarkan ukuran anda|Masukkan kedua-dua ukuran dalam meter, antara 1.5 hingga 15.|Lihat analisis kedalaman AI|AI mengenal pasti permukaan dekat dan jauh. Ukuran dalam meter berasal daripada dimensi yang anda masukkan, bukan imej kedalaman ini.|Anggaran susun atur perabot'
};
const resultCopy={
 en:['No suitable store furniture with confirmed dimensions and availability was found.','Preview using the verified store pieces listed below. Other furniture is inspiration. Measurements and fit are approximate.'],
 ar:['لم نعثر على أثاث مناسب بمقاسات وتوفّر مؤكّدين لدى المتاجر.','التصور مبني على قطع المتاجر الموثقة أدناه. بقية الأثاث للاستلهام، والمقاسات والتوزيع تقريبيان.'],
 fr:['Aucun meuble adapté avec dimensions et disponibilité confirmées n’a été trouvé.','Aperçu avec les meubles vérifiés ci-dessous. Les autres meubles sont une inspiration. Dimensions et disposition approximatives.'],
 de:['Keine passenden Möbel mit bestätigten Maßen und Verfügbarkeit gefunden.','Vorschau mit den unten geprüften Möbeln. Weitere Möbel dienen als Inspiration. Maße und Platzierung sind ungefähr.'],
 es:['No se encontraron muebles adecuados con medidas y disponibilidad confirmadas.','Vista previa con los muebles verificados de abajo. El resto sirve de inspiración. Medidas y distribución aproximadas.'],
 it:['Nessun mobile adatto con dimensioni e disponibilità confermate.','Anteprima con i mobili verificati elencati sotto. Gli altri sono d’ispirazione. Misure e disposizione approssimative.'],
 pt:['Não foram encontrados móveis adequados com medidas e disponibilidade confirmadas.','Prévia com os móveis verificados abaixo. Os demais servem de inspiração. Medidas e disposição aproximadas.'],
 nl:['Geen geschikte meubels met bevestigde maten en beschikbaarheid gevonden.','Voorbeeld met de gecontroleerde meubels hieronder. Overige meubels zijn inspiratie. Maten en plaatsing zijn bij benadering.'],
 tr:['Ölçüleri ve bulunabilirliği doğrulanmış uygun mobilya bulunamadı.','Aşağıdaki doğrulanmış mağaza ürünleriyle önizleme. Diğer mobilyalar fikir amaçlıdır. Ölçüler ve yerleşim yaklaşıktır.'],
 ru:['Подходящая мебель с подтверждёнными размерами и наличием не найдена.','Предпросмотр с проверенными товарами ниже. Остальная мебель — для вдохновения. Размеры и расстановка приблизительные.'],
 zh:['未找到尺寸和库存均已确认的合适家具。','预览采用下方已核实的商店商品。其他家具仅供灵感参考，尺寸与布局均为估算。'],
 ja:['寸法と在庫が確認できる適切な家具が見つかりませんでした。','下記の確認済み商品を使ったイメージです。他の家具は参考です。寸法と配置は概算です。'],
 ko:['치수와 재고가 확인된 적합한 가구를 찾지 못했습니다.','아래 확인된 매장 상품으로 만든 미리보기입니다. 다른 가구는 참고용이며 치수와 배치는 대략적입니다.'],
 hi:['पुष्टि किए गए माप और उपलब्धता वाला उपयुक्त फ़र्नीचर नहीं मिला।','नीचे दिए गए सत्यापित उत्पादों का पूर्वावलोकन। अन्य फ़र्नीचर प्रेरणा के लिए है। माप और व्यवस्था अनुमानित हैं।'],
 ur:['تصدیق شدہ پیمائش اور دستیابی والا مناسب فرنیچر نہیں ملا۔','نیچے درج تصدیق شدہ مصنوعات کا پیش منظر۔ باقی فرنیچر صرف ترغیب کے لیے ہے۔ پیمائش اور ترتیب اندازاً ہیں۔'],
 id:['Tidak ditemukan furnitur sesuai dengan ukuran dan ketersediaan terkonfirmasi.','Pratinjau memakai produk toko terverifikasi di bawah. Furnitur lain hanya inspirasi. Ukuran dan tata letak merupakan perkiraan.'],
 ms:['Tiada perabot sesuai dengan ukuran dan ketersediaan yang disahkan ditemui.','Pratonton menggunakan produk kedai yang disahkan di bawah. Perabot lain ialah inspirasi. Ukuran dan susun atur adalah anggaran.']
};
const incompatibleCopy={
 en:'We found pieces with confirmed dimensions and availability, but could not verify their compatibility with this design. You can try another design.',
 ar:'وجدنا قطعًا بمقاسات وتوفّر مؤكّدين، لكن لم نتمكّن من تأكيد توافقها مع هذا التصميم. يمكنك تجربة تصميم آخر.',
 fr:'Des meubles aux dimensions et à la disponibilité confirmées ont été trouvés, mais leur compatibilité avec ce projet n’a pas pu être validée. Essayez un autre projet.',
 de:'Möbel mit bestätigten Maßen und Verfügbarkeit wurden gefunden, passen aber nicht nachweislich zu diesem Entwurf. Versuchen Sie einen anderen Entwurf.',
 es:'Encontramos muebles con medidas y disponibilidad confirmadas, pero no pudimos verificar su compatibilidad con este diseño. Prueba otro diseño.',
 it:'Abbiamo trovato mobili con dimensioni e disponibilità confermate, ma non ne abbiamo verificato la compatibilità con questo progetto. Prova un altro progetto.',
 pt:'Encontrámos móveis com medidas e disponibilidade confirmadas, mas não conseguimos verificar a compatibilidade com este projeto. Experimente outro projeto.',
 nl:'We vonden meubels met bevestigde maten en beschikbaarheid, maar konden niet bevestigen dat ze bij dit ontwerp passen. Probeer een ander ontwerp.',
 tr:'Ölçüleri ve bulunabilirliği doğrulanmış ürünler bulduk ancak bu tasarıma uygunluklarını doğrulayamadık. Başka bir tasarım deneyebilirsiniz.',
 ru:'Найдены товары с подтверждёнными размерами и наличием, но их совместимость с этим дизайном не подтверждена. Попробуйте другой дизайн.',
 zh:'已找到尺寸和库存均已确认的商品，但无法确认它们与此设计相配。您可以尝试其他设计。',
 ja:'寸法と在庫が確認できる商品は見つかりましたが、このデザインとの適合性を確認できませんでした。別のデザインをお試しください。',
 ko:'치수와 재고가 확인된 제품을 찾았지만 이 디자인과의 조화를 확인하지 못했습니다. 다른 디자인을 시도해 보세요.',
 hi:'पुष्टि किए गए माप और उपलब्धता वाले उत्पाद मिले, लेकिन इस डिज़ाइन के साथ उनकी अनुकूलता की पुष्टि नहीं हो सकी। दूसरा डिज़ाइन आज़मा सकते हैं।',
 ur:'تصدیق شدہ پیمائش اور دستیابی والی مصنوعات ملیں، مگر اس ڈیزائن کے ساتھ ان کی مناسبت کی تصدیق نہیں ہو سکی۔ دوسرا ڈیزائن آزما سکتے ہیں۔',
 id:'Produk dengan ukuran dan ketersediaan terkonfirmasi ditemukan, tetapi kesesuaiannya dengan desain ini belum dapat dipastikan. Coba desain lain.',
 ms:'Produk dengan ukuran dan ketersediaan yang disahkan ditemui, tetapi kesesuaiannya dengan reka bentuk ini tidak dapat dipastikan. Cuba reka bentuk lain.'
};
const completeRoomCopy={
 "en": {
  "intro": "Enter length and width. We’ll source the furniture, coordinate the set, then redesign your room around the real pieces.",
  "curate": "Coordinating the furniture collection",
  "missing": "The furniture collection is not complete yet. These pieces still need a suitable store option.",
  "incompatible": "We could not complete a compatible furniture collection. The missing pieces are listed below.",
  "completeNote": "Designed around the store furniture below, in the quantities shown. Small decorative details are styling. Layout and fit are approximate.",
  "legacy": "This earlier preview used only some store pieces. Start Design & furnish to create a complete furniture collection.",
  "schedule": "Planned furniture: {count} pieces",
  "packs": "{count} packs to buy",
  "unitsPerPack": "{count} pieces per pack",
  "ready": "Your design with store furniture",
  "begin": "Create the complete design"
 },
 "ar": {
  "intro": "أدخل الطول والعرض. نبحث عن الأثاث، ننسّق القطع مع بعض، ثم نعيد تصميم غرفتك على قطع السوق الفعلية.",
  "curate": "تنسيق مجموعة الأثاث",
  "missing": "لم تكتمل مجموعة الأثاث بعد. القطع التالية تحتاج خيارات مناسبة من المتاجر.",
  "incompatible": "لم نكمل مجموعة أثاث متناسقة. القطع الناقصة موضحة أدناه.",
  "completeNote": "تصميم مبني على أثاث المتاجر أدناه وبالكميات الموضحة. التفاصيل الزخرفية الصغيرة للتنسيق. التوزيع والملاءمة تقريبيان.",
  "legacy": "هذا تصور سابق استخدم بعض قطع السوق فقط. ابدأ «التصميم والتنفيذ» لإنشاء مجموعة أثاث متكاملة.",
  "schedule": "الأثاث المطلوب: {count} قطعة",
  "packs": "عدد العبوات للشراء: {count}",
  "unitsPerPack": "{count} قطعة في العبوة",
  "ready": "تصميمك بأثاث السوق",
  "begin": "إنشاء التصميم المتكامل"
 },
 "fr": {
  "intro": "Saisissez longueur et largeur. Nous cherchons les meubles, harmonisons la sélection et repensons la pièce autour des produits réels.",
  "curate": "Harmonisation des meubles",
  "missing": "La sélection est incomplète. Ces meubles nécessitent encore une offre adaptée.",
  "incompatible": "La sélection de meubles compatibles est incomplète. Les pièces manquantes sont indiquées ci-dessous.",
  "completeNote": "Design fondé sur les meubles ci-dessous, dans les quantités indiquées. Les petits décors sont une mise en scène. Implantation approximative.",
  "legacy": "Cet ancien aperçu utilisait seulement quelques produits. Relancez Design et ameublement pour une sélection complète.",
  "schedule": "Mobilier prévu : {count} pièces",
  "packs": "{count} lots à acheter",
  "unitsPerPack": "{count} pièces par lot",
  "ready": "Votre design avec des meubles en vente",
  "begin": "Créer le design complet"
 },
 "de": {
  "intro": "Länge und Breite eingeben. Wir suchen Möbel, stimmen sie aufeinander ab und gestalten den Raum mit den echten Produkten neu.",
  "curate": "Möbel aufeinander abstimmen",
  "missing": "Die Möbelauswahl ist noch unvollständig. Für diese Stücke fehlen passende Angebote.",
  "incompatible": "Eine stimmige Möbelauswahl konnte nicht vervollständigt werden. Fehlende Stücke stehen unten.",
  "completeNote": "Gestaltet mit den unten aufgeführten Möbeln und Mengen. Kleine Dekorationen dienen der Gestaltung. Platzierung und Passform sind ungefähr.",
  "legacy": "Diese ältere Vorschau nutzte nur einige echte Produkte. Starten Sie Design und Einrichtung für eine vollständige Auswahl.",
  "schedule": "Geplante Möbel: {count} Stück",
  "packs": "{count} Packungen kaufen",
  "unitsPerPack": "{count} Stück je Packung",
  "ready": "Ihr Design mit Möbeln aus dem Handel",
  "begin": "Vollständiges Design erstellen"
 },
 "es": {
  "intro": "Introduce largo y ancho. Buscamos los muebles, coordinamos el conjunto y rediseñamos la habitación con productos reales.",
  "curate": "Coordinando el conjunto de muebles",
  "missing": "El conjunto aún está incompleto. Estas piezas necesitan una opción adecuada.",
  "incompatible": "No pudimos completar un conjunto compatible. Las piezas que faltan aparecen abajo.",
  "completeNote": "Diseño basado en los muebles y cantidades indicados abajo. Los pequeños detalles son decorativos. Distribución y ajuste aproximados.",
  "legacy": "Esta vista anterior usaba solo algunas piezas de tiendas. Inicia Diseño y mobiliario para crear un conjunto completo.",
  "schedule": "Mobiliario previsto: {count} piezas",
  "packs": "{count} paquetes para comprar",
  "unitsPerPack": "{count} piezas por paquete",
  "ready": "Tu diseño con muebles de tiendas",
  "begin": "Crear el diseño completo"
 },
 "it": {
  "intro": "Inserisci lunghezza e larghezza. Cerchiamo i mobili, coordiniamo la selezione e riprogettiamo la stanza con i prodotti reali.",
  "curate": "Coordinamento dei mobili",
  "missing": "La selezione non è ancora completa. Per questi mobili serve un’offerta adatta.",
  "incompatible": "Non siamo riusciti a completare un insieme coordinato. I pezzi mancanti sono elencati sotto.",
  "completeNote": "Design basato sui mobili e sulle quantità indicati sotto. I piccoli dettagli sono decorativi. Disposizione e ingombri approssimativi.",
  "legacy": "Questa vecchia anteprima usava solo alcuni prodotti. Avvia Design e arredo per una selezione completa.",
  "schedule": "Mobili previsti: {count} pezzi",
  "packs": "{count} confezioni da acquistare",
  "unitsPerPack": "{count} pezzi per confezione",
  "ready": "Il tuo design con mobili reali",
  "begin": "Crea il design completo"
 },
 "pt": {
  "intro": "Introduza comprimento e largura. Procuramos os móveis, coordenamos o conjunto e redesenhamos a divisão com produtos reais.",
  "curate": "A coordenar o conjunto de móveis",
  "missing": "O conjunto ainda está incompleto. Estas peças precisam de uma opção adequada.",
  "incompatible": "Não conseguimos completar um conjunto compatível. As peças em falta aparecem abaixo.",
  "completeNote": "Design baseado nos móveis e quantidades abaixo. Os pequenos detalhes são decorativos. Disposição e ajuste aproximados.",
  "legacy": "Esta prévia anterior usava apenas alguns produtos. Inicie Design e mobiliário para um conjunto completo.",
  "schedule": "Mobiliário previsto: {count} peças",
  "packs": "{count} embalagens para comprar",
  "unitsPerPack": "{count} peças por embalagem",
  "ready": "O seu design com móveis de lojas",
  "begin": "Criar o design completo"
 },
 "nl": {
  "intro": "Vul lengte en breedte in. We zoeken meubels, stemmen de collectie af en ontwerpen de kamer opnieuw met echte producten.",
  "curate": "De meubelcollectie afstemmen",
  "missing": "De collectie is nog niet compleet. Voor deze meubels ontbreekt een passende winkeloptie.",
  "incompatible": "We konden geen complete passende collectie samenstellen. Ontbrekende meubels staan hieronder.",
  "completeNote": "Ontworpen met de meubels en aantallen hieronder. Kleine decoraties zijn styling. Indeling en pasvorm zijn bij benadering.",
  "legacy": "Dit eerdere voorbeeld gebruikte slechts enkele winkelproducten. Start Ontwerp en inrichting voor een complete collectie.",
  "schedule": "Geplande meubels: {count} stuks",
  "packs": "{count} pakketten kopen",
  "unitsPerPack": "{count} stuks per pakket",
  "ready": "Uw ontwerp met winkelmeubels",
  "begin": "Compleet ontwerp maken"
 },
 "tr": {
  "intro": "Uzunluk ve genişliği girin. Mobilyaları bulur, birbiriyle uyumlu seçer ve odayı gerçek ürünlerle yeniden tasarlarız.",
  "curate": "Mobilya koleksiyonu uyumlandırılıyor",
  "missing": "Koleksiyon henüz tamamlanmadı. Bu parçalar için uygun mağaza ürünü gerekiyor.",
  "incompatible": "Uyumlu koleksiyon tamamlanamadı. Eksik parçalar aşağıda listelenmiştir.",
  "completeNote": "Aşağıdaki mobilya ve adetlerle tasarlandı. Küçük dekoratif ayrıntılar stil amaçlıdır. Yerleşim ve uyum yaklaşık değerlerdir.",
  "legacy": "Bu eski önizleme yalnızca bazı gerçek ürünleri kullandı. Tam koleksiyon için Tasarım ve döşeme işlemini başlatın.",
  "schedule": "Planlanan mobilya: {count} parça",
  "packs": "Satın alınacak paket: {count}",
  "unitsPerPack": "Paket başına {count} parça",
  "ready": "Mağaza mobilyalarıyla tasarımınız",
  "begin": "Tam tasarımı oluştur"
 },
 "ru": {
  "intro": "Введите длину и ширину. Мы найдём мебель, согласуем подборку и создадим новый дизайн с реальными товарами.",
  "curate": "Согласовываем подборку мебели",
  "missing": "Подборка пока не завершена. Для этих предметов нужны подходящие предложения.",
  "incompatible": "Не удалось завершить согласованную подборку. Недостающие предметы указаны ниже.",
  "completeNote": "Дизайн основан на товарах и количествах ниже. Мелкие декоративные детали — оформление. Расстановка и размеры приблизительны.",
  "legacy": "В этом старом варианте использовалась лишь часть товаров. Запустите дизайн и меблировку для полной подборки.",
  "schedule": "Запланировано предметов: {count}",
  "packs": "Купить упаковок: {count}",
  "unitsPerPack": "{count} шт. в упаковке",
  "ready": "Ваш дизайн с мебелью из магазинов",
  "begin": "Создать полный дизайн"
 },
 "zh": {
  "intro": "输入长和宽。我们寻找家具、协调搭配，再围绕真实商品重新设计房间。",
  "curate": "正在协调家具搭配",
  "missing": "家具尚未配齐。以下物品仍需合适的商店商品。",
  "incompatible": "未能完成协调的家具组合。缺少的物品列在下方。",
  "completeNote": "设计基于下方列出的家具和数量。小型装饰细节仅为布置效果，布局和适配为估算。",
  "legacy": "旧预览仅使用了部分真实商品。启动设计与布置以创建完整家具组合。",
  "schedule": "计划家具：{count} 件",
  "packs": "需购买 {count} 包",
  "unitsPerPack": "每包 {count} 件",
  "ready": "采用商店家具的设计",
  "begin": "创建完整设计"
 },
 "ja": {
  "intro": "縦と横の寸法を入力してください。家具を探して組み合わせ、実際の商品で部屋を再設計します。",
  "curate": "家具の組み合わせを調整中",
  "missing": "家具がまだ揃っていません。以下の商品に適した候補が必要です。",
  "incompatible": "調和する家具一式を揃えられませんでした。不足する家具は以下の通りです。",
  "completeNote": "下記の商品と数量に基づくデザインです。小さな装飾は演出です。配置とサイズの適合は概算です。",
  "legacy": "この以前の画像は一部の商品のみを使用しています。デザインと家具配置を開始して家具一式を選んでください。",
  "schedule": "予定する家具：{count} 点",
  "packs": "購入するセット数：{count}",
  "unitsPerPack": "1セット {count} 点",
  "ready": "実際の販売家具によるデザイン",
  "begin": "全体デザインを作成"
 },
 "ko": {
  "intro": "가로와 세로를 입력하세요. 가구를 찾고 조화롭게 골라 실제 제품으로 방을 다시 디자인합니다.",
  "curate": "가구 조합을 조율하는 중",
  "missing": "아직 가구 구성이 완성되지 않았습니다. 다음 품목에 적합한 매장 제품이 필요합니다.",
  "incompatible": "조화로운 가구 구성을 완성하지 못했습니다. 누락된 품목은 아래에 표시됩니다.",
  "completeNote": "아래 제품과 수량을 기반으로 한 디자인입니다. 작은 장식은 스타일링이며 배치와 크기 적합성은 대략적입니다.",
  "legacy": "이전 미리보기에는 일부 매장 제품만 사용되었습니다. 디자인과 가구 배치를 시작해 전체 구성을 만드세요.",
  "schedule": "예정 가구: {count}개",
  "packs": "구매할 묶음: {count}개",
  "unitsPerPack": "묶음당 {count}개",
  "ready": "매장 가구로 만든 디자인",
  "begin": "전체 디자인 만들기"
 },
 "hi": {
  "intro": "लंबाई और चौड़ाई दर्ज करें। हम फ़र्नीचर खोजकर उसका तालमेल चुनेंगे और असली उत्पादों से कमरा फिर डिज़ाइन करेंगे।",
  "curate": "फ़र्नीचर का तालमेल बनाया जा रहा है",
  "missing": "फ़र्नीचर का चयन अभी अधूरा है। इन वस्तुओं के लिए उपयुक्त दुकान विकल्प चाहिए।",
  "incompatible": "अनुकूल फ़र्नीचर का पूरा चयन नहीं हो सका। बाकी वस्तुएँ नीचे दी गई हैं।",
  "completeNote": "डिज़ाइन नीचे के उत्पादों और उनकी संख्या पर आधारित है। छोटे सजावटी विवरण केवल शैली के लिए हैं। व्यवस्था और फिट अनुमानित हैं।",
  "legacy": "इस पुराने पूर्वावलोकन में कुछ ही असली उत्पाद थे। पूरा चयन बनाने के लिए डिज़ाइन और फ़र्निशिंग शुरू करें।",
  "schedule": "नियोजित फ़र्नीचर: {count} वस्तुएँ",
  "packs": "खरीदने के पैक: {count}",
  "unitsPerPack": "हर पैक में {count} वस्तुएँ",
  "ready": "दुकान के फ़र्नीचर से आपका डिज़ाइन",
  "begin": "पूरा डिज़ाइन बनाएँ"
 },
 "ur": {
  "intro": "لمبائی اور چوڑائی درج کریں۔ ہم فرنیچر تلاش کر کے ہم آہنگ انتخاب کریں گے اور اصل مصنوعات سے کمرے کو دوبارہ ڈیزائن کریں گے۔",
  "curate": "فرنیچر کو ہم آہنگ کیا جا رہا ہے",
  "missing": "فرنیچر کا انتخاب ابھی نامکمل ہے۔ ان اشیا کے لیے مناسب دکان کی مصنوعات درکار ہیں۔",
  "incompatible": "ہم آہنگ فرنیچر کا مکمل انتخاب نہ ہو سکا۔ باقی اشیا نیچے درج ہیں۔",
  "completeNote": "ڈیزائن نیچے درج مصنوعات اور تعداد پر مبنی ہے۔ چھوٹی آرائشی تفصیلات صرف سجاوٹ ہیں۔ ترتیب اور موزونیت اندازاً ہیں۔",
  "legacy": "اس پرانے پیش منظر میں صرف چند اصل مصنوعات تھیں۔ مکمل انتخاب کے لیے ڈیزائن اور فرنیچر شروع کریں۔",
  "schedule": "منصوبہ شدہ فرنیچر: {count} اشیا",
  "packs": "خریدنے کے پیک: {count}",
  "unitsPerPack": "ہر پیک میں {count} اشیا",
  "ready": "دکان کے فرنیچر سے آپ کا ڈیزائن",
  "begin": "مکمل ڈیزائن بنائیں"
 },
 "id": {
  "intro": "Masukkan panjang dan lebar. Kami mencari furnitur, memadukan pilihannya, lalu mendesain ulang ruangan dengan produk nyata.",
  "curate": "Memadukan koleksi furnitur",
  "missing": "Koleksi belum lengkap. Barang berikut masih memerlukan pilihan toko yang sesuai.",
  "incompatible": "Koleksi yang serasi belum dapat dilengkapi. Barang yang belum tersedia tercantum di bawah.",
  "completeNote": "Desain berdasarkan furnitur dan jumlah di bawah. Detail dekorasi kecil hanya penataan. Tata letak dan kecocokan bersifat perkiraan.",
  "legacy": "Pratinjau lama ini hanya memakai sebagian produk nyata. Mulai Desain dan tata furnitur untuk koleksi lengkap.",
  "schedule": "Rencana furnitur: {count} buah",
  "packs": "Beli {count} paket",
  "unitsPerPack": "{count} buah per paket",
  "ready": "Desain Anda dengan furnitur toko",
  "begin": "Buat desain lengkap"
 },
 "ms": {
  "intro": "Masukkan panjang dan lebar. Kami mencari perabot, menyelaraskan pilihan dan mereka semula bilik dengan produk sebenar.",
  "curate": "Menyelaraskan koleksi perabot",
  "missing": "Koleksi belum lengkap. Barangan berikut masih memerlukan pilihan kedai yang sesuai.",
  "incompatible": "Koleksi yang sepadan belum dapat dilengkapkan. Barangan yang tiada disenaraikan di bawah.",
  "completeNote": "Reka bentuk berdasarkan perabot dan kuantiti di bawah. Hiasan kecil hanya penggayaan. Susun atur dan kesesuaian adalah anggaran.",
  "legacy": "Pratonton lama ini hanya menggunakan sebahagian produk sebenar. Mulakan Reka bentuk dan perabot untuk koleksi lengkap.",
  "schedule": "Perabot dirancang: {count} unit",
  "packs": "Beli {count} pek",
  "unitsPerPack": "{count} unit setiap pek",
  "ready": "Reka bentuk anda dengan perabot kedai",
  "begin": "Cipta reka bentuk lengkap"
 }
};
const adaptiveCopy={"en": ["We’ll prioritize the essential furniture and reuse matching pieces in the required quantities. Unavailable accents are left out of the final design.", "The composition was adapted to available products; unavailable accents from the concept were removed.", "Search credits ran out. Suitable products are saved; the essential pieces below still need an option."], "ar": ["نعطي الأولوية للأثاث الأساسي ونستخدم القطعة المتطابقة بالعدد المطلوب. نعيد تنسيق التصميم دون الإضافات غير المتوفرة.", "أعدنا تنسيق التصميم حسب القطع المتوفرة، وحذفنا الإضافات التي لم نجد لها خيارًا مناسبًا.", "انتهى رصيد البحث. حُفظت القطع المناسبة، وما زالت القطع الأساسية التالية تحتاج خيارًا مناسبًا."], "fr": ["Priorité aux meubles essentiels et aux quantités nécessaires. Les accessoires indisponibles seront retirés.", "La composition a été adaptée aux produits disponibles ; les accessoires introuvables ont été retirés.", "Les crédits de recherche sont épuisés. Les produits adaptés sont sauvegardés ; les meubles essentiels ci-dessous restent à trouver."], "de": ["Wesentliche Möbel haben Vorrang. Gleiche Stücke werden in der benötigten Menge verwendet; nicht verfügbare Akzente entfallen.", "Der Entwurf wurde an verfügbare Produkte angepasst; nicht verfügbare Akzente wurden entfernt.", "Die Such-Credits sind aufgebraucht. Passende Produkte sind gespeichert; die folgenden wesentlichen Möbel fehlen noch."], "es": ["Priorizaremos los muebles esenciales y las cantidades necesarias. Los complementos no disponibles se eliminarán.", "La composición se adaptó a los productos disponibles; se retiraron los complementos no disponibles.", "Se agotaron los créditos de búsqueda. Los productos adecuados están guardados; faltan opciones para los muebles esenciales indicados."], "it": ["Diamo priorità ai mobili essenziali e alle quantità necessarie. I complementi non disponibili saranno esclusi.", "La composizione è stata adattata ai prodotti disponibili, eliminando i complementi non reperibili.", "Crediti di ricerca esauriti. I prodotti adatti sono salvati; mancano ancora opzioni per i mobili essenziali elencati."], "pt": ["Priorizamos os móveis essenciais e as quantidades necessárias. Os complementos indisponíveis serão retirados.", "A composição foi adaptada aos produtos disponíveis; os complementos indisponíveis foram retirados.", "Os créditos de pesquisa esgotaram-se. Os produtos adequados estão guardados; faltam opções para os móveis essenciais indicados."], "nl": ["Essentiële meubels en de benodigde aantallen krijgen voorrang. Niet beschikbare accenten vervallen.", "Het ontwerp is aangepast aan beschikbare producten; niet beschikbare accenten zijn verwijderd.", "De zoekcredits zijn op. Geschikte producten zijn opgeslagen; voor onderstaande essentiële meubels ontbreken nog opties."], "tr": ["Temel mobilyalara ve gerekli adetlere öncelik veriyoruz. Bulunamayan tamamlayıcı parçalar çıkarılacak.", "Tasarım mevcut ürünlere uyarlandı; bulunamayan tamamlayıcı parçalar çıkarıldı.", "Arama kredileri bitti. Uygun ürünler kaydedildi; aşağıdaki temel parçalar için hâlâ ürün gerekiyor."], "ru": ["Приоритет — основная мебель и нужное количество одинаковых предметов. Недоступные дополнительные предметы будут убраны.", "Дизайн адаптирован к доступным товарам; недоступные дополнительные предметы убраны.", "Кредиты поиска закончились. Подходящие товары сохранены; для указанной основной мебели ещё нужны варианты."], "zh": ["优先寻找必需家具，并按所需数量使用相同商品。无法购买的点缀家具将从设计中移除。", "设计已根据可购买商品调整，并移除了无法找到合适商品的点缀家具。", "搜索点数已用完。合适商品已保存，下列必需家具仍需寻找商品。"], "ja": ["主要な家具と必要な数量を優先します。入手できない補助的な家具は配置から除きます。", "入手可能な商品に合わせて構成を調整し、見つからなかった補助的な家具を除きました。", "検索クレジットを使い切りました。適切な商品は保存済みですが、以下の主要家具はまだ必要です。"], "ko": ["필수 가구와 필요한 수량을 우선합니다. 구할 수 없는 보조 가구는 디자인에서 제외합니다.", "구매 가능한 제품에 맞춰 구성을 조정하고 구할 수 없는 보조 가구를 제외했습니다.", "검색 크레딧이 소진되었습니다. 적합한 제품은 저장되었으며 아래 필수 가구는 아직 찾아야 합니다."], "hi": ["ज़रूरी फ़र्नीचर और आवश्यक संख्या को प्राथमिकता देंगे। उपलब्ध न होने वाले अतिरिक्त सामान को डिज़ाइन से हटा देंगे।", "डिज़ाइन उपलब्ध उत्पादों के अनुसार बदला गया और अनुपलब्ध अतिरिक्त सामान हटाया गया।", "खोज क्रेडिट समाप्त हो गए। उपयुक्त उत्पाद सहेजे गए हैं; नीचे के आवश्यक फ़र्नीचर के विकल्प अभी चाहिए।"], "ur": ["ضروری فرنیچر اور مطلوبہ تعداد کو ترجیح دیں گے۔ غیر دستیاب اضافی اشیا ڈیزائن سے ہٹا دیں گے۔", "ڈیزائن دستیاب مصنوعات کے مطابق بدلا گیا اور غیر دستیاب اضافی اشیا ہٹا دی گئیں۔", "تلاش کے کریڈٹ ختم ہو گئے۔ موزوں مصنوعات محفوظ ہیں؛ نیچے درج ضروری فرنیچر کے متبادل ابھی درکار ہیں۔"], "id": ["Kami mengutamakan furnitur pokok dan jumlah yang dibutuhkan. Pelengkap yang tidak tersedia akan dihapus.", "Komposisi disesuaikan dengan produk yang tersedia; pelengkap yang tidak ditemukan telah dihapus.", "Kredit pencarian habis. Produk yang sesuai tersimpan; furnitur pokok berikut masih memerlukan pilihan."], "ms": ["Kami mengutamakan perabot utama dan kuantiti yang diperlukan. Pelengkap yang tiada akan dikeluarkan.", "Susunan disesuaikan dengan produk tersedia; pelengkap yang tiada telah dikeluarkan.", "Kredit carian habis. Produk sesuai telah disimpan; perabot utama berikut masih memerlukan pilihan."]};
const planCopy={"en": ["Your furnishing plan", "Your furniture selection and approximate layout are ready. The room image could not be verified against every product, so it is not shown."], "ar": ["خطة تأثيث غرفتك", "قائمة الأثاث والمخطط التقريبي جاهزان. تعذّر تأكيد تطابق صورة الغرفة مع كل المنتجات، لذلك لم نعرضها."], "fr": ["Votre plan d’ameublement", "Les meubles sélectionnés et le plan approximatif sont prêts. L’image ne correspondait pas de façon vérifiable à tous les produits et n’est donc pas affichée."], "de": ["Ihr Einrichtungsplan", "Möbelauswahl und ungefähre Anordnung sind fertig. Das Raumbild konnte nicht für alle Produkte bestätigt werden und wird deshalb nicht angezeigt."], "es": ["Tu plan de mobiliario", "La selección de muebles y la distribución aproximada están listas. No se pudo verificar cada producto de la imagen, por lo que no se muestra."], "it": ["Il tuo piano d’arredo", "La selezione dei mobili e la disposizione indicativa sono pronte. Non è stato possibile verificare ogni prodotto nell’immagine, che quindi non viene mostrata."], "pt": ["O seu plano de mobiliário", "A seleção de móveis e a disposição aproximada estão prontas. Não foi possível confirmar todos os produtos na imagem, por isso não é apresentada."], "nl": ["Je inrichtingsplan", "De meubelselectie en geschatte indeling zijn klaar. Niet elk product in de kamerafbeelding kon worden bevestigd, daarom wordt die niet getoond."], "ru": ["Ваш план меблировки", "Подбор мебели и примерная расстановка готовы. Соответствие изображения всем товарам не удалось подтвердить, поэтому оно не показано."], "tr": ["Mobilya planınız", "Mobilya seçimi ve yaklaşık yerleşim hazır. Oda görselindeki her ürün doğrulanamadığı için görsel gösterilmiyor."], "zh": ["您的家具布置方案", "家具清单和大致布局已准备好。房间图片无法逐一确认与所有商品一致，因此未展示。"], "ja": ["家具配置プラン", "家具リストとおおよその配置ができました。室内画像で全商品の一致を確認できなかったため、画像は表示していません。"], "ko": ["가구 배치 계획", "가구 목록과 대략적인 배치가 준비되었습니다. 방 이미지의 모든 제품을 확인할 수 없어 이미지는 표시하지 않습니다."], "hi": ["आपकी फ़र्नीचर योजना", "फ़र्नीचर सूची और अनुमानित व्यवस्था तैयार हैं। कमरे की तस्वीर में हर उत्पाद की पुष्टि नहीं हुई, इसलिए तस्वीर नहीं दिखाई गई है।"], "ur": ["آپ کا فرنیچر منصوبہ", "فرنیچر کی فہرست اور اندازاً ترتیب تیار ہیں۔ کمرے کی تصویر میں ہر مصنوعات کی مطابقت کی تصدیق نہیں ہو سکی، اس لیے تصویر نہیں دکھائی گئی۔"], "id": ["Rencana furnitur Anda", "Pilihan furnitur dan perkiraan tata letak siap. Semua produk pada gambar ruangan belum dapat diverifikasi, sehingga gambar tidak ditampilkan."], "ms": ["Pelan perabot anda", "Pilihan perabot dan anggaran susun atur siap. Semua produk dalam imej bilik tidak dapat disahkan, jadi imej tidak dipaparkan."]};
export function furnishingText(language,key,count){
 const plan=["planReady","planNote"].indexOf(key);if(plan>=0)return (planCopy[language]||planCopy.en)[plan];
 const adaptive=["adaptivePlan","adapted","credits"].indexOf(key);if(adaptive>=0)return (adaptiveCopy[language]||adaptiveCopy.en)[adaptive];
 if(completeRoomCopy[language||'en']?.[key]||completeRoomCopy.en[key])return (completeRoomCopy[language]?.[key]||completeRoomCopy.en[key]).replaceAll('{count}',String(count??''));
 if(key==='incompatible')return incompatibleCopy[language]||incompatibleCopy.en;
 const outcome=['missing','partial'].indexOf(key);
 const value=outcome>=0?(resultCopy[language]||resultCopy.en)[outcome]:measurementKeys.includes(key)?(measurements[language]||measurements.en).split('|')[measurementKeys.indexOf(key)]:(copy[language]||copy.en).split('|')[keys.indexOf(key)]||key;
 return value.replaceAll('{count}',String(count??''));
}
