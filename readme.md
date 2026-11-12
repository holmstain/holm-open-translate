# Holm Open Translate

Holm Open Translate is a Flask application for translating JSON localization files with the NVIDIA NIM translation API. Upload one or more JSON files, choose target languages, and download the translated files in a ZIP archive.

## Translation contract and verification

Select the **source language** of the uploaded JSON. It defaults to English; language detection is not automatic. All listed source → target combinations are supported. English → Turkish and Turkish → English use one native provider step; Turkish → German uses Turkish → English → German. The English intermediate is generated once per uploaded file and reused across the selected targets within that request. An identical source/target selection copies the original JSON values without an API call. Two-step translation may increase latency, API usage and translation drift; quality for every pair has not been verified live. The interface language selector changes display text only. Latin American Spanish remains `es-419` in output filenames and maps to NVIDIA's `es-us` code.

The app sends the provider a system message containing the language pair (for example `en-tr`) and a user message containing only the source text, following the [NVIDIA Riva Translate model card](https://huggingface.co/nvidia/riva-translate-4b-instruct-v2). Every nonblank JSON string is translated; keys, lists, numbers, booleans, null and whitespace-only strings are retained. Common brace placeholders (`{name}`, `{{name}}`, `${name}`) and printf placeholders (`%s`, `%d`, `%1$s`, `%(name)s`) are checked for identical spelling and counts. Other localization grammars, including complex ICU message syntax, require separate validation.

Invalid files and unknown source or target languages return HTTP 400. A provider exception, empty/incomplete response, or changed supported placeholder returns HTTP 502; partial archives are not saved or presented as success. The browser sends the request immediately, shows a busy state and starts the ZIP download only after receiving the actual successful response. A download link remains available after completion; refresh to see it in session history. Inputs remain available to retry after an error.

Run offline regressions with the commands below. They replace only the external provider and block socket connections:

```bash
venv/bin/python -m unittest discover -v
node test_ui_flow.js
```

The existing asset/security tests use pytest-style functions. To run the complete Python suite in an environment with pytest installed:

```bash
python -m pip install pytest
python -m pytest -q
```

`test.py` is safe to import and makes no request unless explicitly run with `--live`. That smoke check performs one logical translation of a synthetic `Hello` string to Turkish using the configured key (up to three HTTP attempts under the same retry policy); it prints only a pass/fail status. It does not establish translation quality across all languages.

Local `python app.py` currently listens on port **5001**. Docker/Gunicorn uses container port **5000**; see `docker-compose.yml` for the published port. Requests are synchronous. File/language tasks may run concurrently, but provider calls are serialized within each app process to avoid request bursts; strings within each task remain sequential. Each HTTP attempt keeps the 30-second SDK timeout (a phase/inactivity timeout, not a hard total request deadline). A logical provider call makes at most three attempts for connection/timeouts or HTTP 429/500/502/503/504, with 0.5 then 1 second backoff. A numeric or HTTP-date `Retry-After` may replace a wait up to 5 seconds; a longer server-directed wait ends the request without retrying early. Thus each call has at most three HTTP attempts and two waits of at most 5 seconds; there is no guaranteed 90/100-second wall-clock bound. Successful strings and completed English pivot steps are retained within the running request and are not repeated by a later string retry. HTTP 400/401/403 (and other non-allowlisted statuses), empty/truncated translations and changed placeholders are not retried. Persistent temporary failures return a distinct HTTP 502 message and publish no partial archive. Nothing is cached across separate requests. The Docker Gunicorn worker's configured 120-second request timeout can interrupt larger files; this has not been reproduced against a live container. Use small uploads until deployment request limits are verified; no background queue or progress percentage API exists.

## Çeviri sözleşmesi

Geçici bağlantı/zaman aşımı ve HTTP 429/500/502/503/504 hatalarında yalnız başarısız API çağrısı en fazla üç kez denenir. Beklemeler 0,5 ve 1 saniyedir; `Retry-After` en fazla 5 saniye olabilir, daha uzunsa erken yeniden çağırmak yerine işlem durur. Her HTTP denemesinin zaman aşımı 30 saniyedir; bu toplam işlem süresi garantisi değildir. Başarılı metinler aynı istek içinde yeniden çevrilmez. Kimlik doğrulama/geçersiz istek ve bozuk çeviri sonuçları yeniden denenmez; kalıcı hatada kısmi arşiv oluşturulmaz.

JSON dosyasının gerçek **kaynak dilini** seçin (varsayılan İngilizce). Otomatik dil algılama yoktur. Listelenen tüm kaynak → hedef dil çiftleri desteklenir. İngilizce içeren çiftler doğrudan; Türkçe → Almanca gibi çiftler kaynak → İngilizce → hedef olarak iki adımda çevrilir. İngilizce ara JSON her dosya için bir kez üretilip aynı isteğin hedefleri arasında paylaşılır. Aynı kaynak/hedef dili API çağrısı olmadan özgün JSON değerlerini kopyalar. İki adım süreyi, API kullanımını ve anlam kayması olasılığını artırabilir; tüm çiftlerin kalitesi canlı doğrulanmamıştır. Bilinmeyen dil kodları 400 döndürür. Arayüz dili kaynak dilini değiştirmez. Geçersiz JSON 400, eksik/boş/başarısız API yanıtı veya desteklenen yer tutucunun bozulması 502 döndürür; eksik arşiv yayımlanmaz. Gerçek başarılı yanıttan sonra indirme başlar; hata durumunda seçilen dosyalar korunur ve yeniden denenebilir.

## Languages

[🇬🇧 English](#english) · [🇹🇷 Türkçe](#turkce) · [🇪🇸 Español](#espanol) · [🇵🇱 Polski](#polski) · [🇵🇹 Português](#portugues) · [🇹🇼 繁體中文](#chinese) · [🇯🇵 日本語](#japanese)

<a id="english"></a>

## Features

- Upload multiple JSON files in one request.
- Translate string values recursively while keeping JSON keys and data structure unchanged.
- Preserve non-string values such as numbers, booleans, and `null`.
- Select one or more output languages. The interface and translation targets include English, Turkish, German, French, Spanish, Polish, Portuguese, Japanese, and Traditional Chinese, alongside Arabic, Italian, Korean, Dutch, Russian, and Chinese.
- Download translated files as a ZIP archive. Output filenames include the target language code, such as `common_en.json` or `common_zh-TW.json`.
- Keep translation archives organized by browser session.
- Use the interface in light or dark mode.

Placeholders in text, such as `{name}`, `%s`, and `%d`, are intended to remain intact during translation.

## Requirements

- Python 3.10 or later
- A NVIDIA NIM API key
- `Flask`, `openai`, and `python-dotenv` (Node.js is only needed for the UI handler tests)

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
python -m pip install Flask openai python-dotenv
```

### 3. Configure the API key

Copy the example environment file:

```bash
cp .env.example .env
```

Add your NVIDIA NIM API key to `.env`:

```dotenv
NVIDIA_API_KEY=your_nvidia_api_key_here
```

Keep `.env` private and do not commit it to source control.

## Run the application

```bash
python app.py
```

Open [http://localhost:5001](http://localhost:5001) in your browser.

## Run tests

The focused translation-target tests use a mocked translator and do not require API access:

```bash
python -m unittest test_translation_flow -v
node test_ui_flow.js
```

The translator test suite includes a live NVIDIA API request. Configure `NVIDIA_API_KEY` before running it:

```bash
python test.py --live
```

## Project files

| File | Description |
| --- | --- |
| `app.py` | Flask application, web interface, and JSON translation workflow |
| `test_translation_flow.py` | Tests for translation targets and ZIP output |
| `test_ui_flow.js` | Offline UI submission, loading, success and error checks (Node.js) |
| `test.py` | Simple NVIDIA API connectivity check |
| `.env.example` | Example environment variable configuration |

## License

This project is distributed under the MIT License.

<a id="turkce"></a>

---

# 🇹🇷 Holm Open Translate — Türkçe

Holm Open Translate, JSON yerelleştirme dosyalarını NVIDIA NIM çeviri API’siyle çevirmek için geliştirilmiş bir Flask uygulamasıdır. Bir veya daha fazla JSON dosyası yükleyin, hedef dilleri seçin ve çevrilmiş dosyaları ZIP arşivi olarak indirin.

## Özellikler

- Tek istekte birden fazla JSON dosyası yükleme.
- JSON anahtarlarını ve veri yapısını koruyarak metin değerlerini iç içe yapılar boyunca çevirme.
- Sayı, boolean ve `null` gibi metin dışı değerleri koruma.
- Bir veya daha fazla hedef dil seçme. Arayüz ve çeviri hedefleri İngilizce, Türkçe, Almanca, Fransızca, İspanyolca, Lehçe, Portekizce, Japonca ve Geleneksel Çince’nin yanı sıra Arapça, İtalyanca, Korece, Felemenkçe, Rusça ve Çinceyi destekler.
- Çevrilmiş dosyaları ZIP arşivi olarak indirme. Dosya adlarına hedef dil kodu eklenir; örneğin `common_en.json` veya `common_zh-TW.json`.
- Çeviri arşivlerini tarayıcı oturumuna göre düzenleme.
- Açık ve koyu tema seçenekleri.

`{name}`, `%s` ve `%d` gibi yer tutucuların çeviri sırasında korunması amaçlanır.

## Gereksinimler

- Python 3.10 veya üzeri
- NVIDIA NIM API anahtarı
- `Flask`, `openai` ve `python-dotenv`

## Kurulum

### 1. Sanal ortam oluşturun ve etkinleştirin

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows PowerShell'de etkinleştirmek için:

```powershell
venv\Scripts\Activate.ps1
```

### 2. Bağımlılıkları yükleyin

```bash
python -m pip install Flask openai python-dotenv
```

### 3. API anahtarını yapılandırın

Örnek ortam dosyasını kopyalayın:

```bash
cp .env.example .env
```

NVIDIA NIM API anahtarınızı `.env` dosyasına ekleyin:

```dotenv
NVIDIA_API_KEY=your_nvidia_api_key_here
```

`.env` dosyasını gizli tutun ve kaynak kod deposuna eklemeyin.

## Uygulamayı çalıştırma

```bash
python app.py
```

Tarayıcınızda [http://localhost:5001](http://localhost:5001) adresini açın.

## Testleri çalıştırma

Odaklı hedef dil testleri taklitçi çeviri kullanır ve API erişimi gerektirmez:

```bash
python -m unittest test_translation_flow -v
node test_ui_flow.js
```

Çevirmen test paketi NVIDIA API'sine canlı bir istek gönderir. Çalıştırmadan önce `NVIDIA_API_KEY` değerini yapılandırın:

```bash
python test.py --live
```

## Proje dosyaları

| Dosya | Açıklama |
| --- | --- |
| `app.py` | Flask uygulaması, web arayüzü ve JSON çeviri akışı |
| `test_translation_flow.py` | Çeviri hedefleri ve ZIP çıktısı testleri |
| `test_ui_flow.js` | Offline UI submission, loading, success and error checks (Node.js) |
| `test.py` | NVIDIA API bağlantı kontrolü |
| `.env.example` | Örnek ortam değişkeni yapılandırması |

## Lisans

Bu proje MIT Lisansı ile dağıtılır.

<a id="espanol"></a>

---

# 🇪🇸 Holm Open Translate — Español

Holm Open Translate es una aplicación Flask para traducir archivos de localización JSON mediante la API de traducción NVIDIA NIM. Sube uno o varios archivos JSON, elige los idiomas de destino y descarga los archivos traducidos en un archivo ZIP.

## Funciones

- Carga varios archivos JSON en una sola solicitud.
- Traduce recursivamente los valores de texto sin modificar las claves ni la estructura JSON.
- Conserva los valores que no son texto, como números, booleanos y `null`.
- Permite elegir uno o varios idiomas de destino. La interfaz y las traducciones admiten inglés, turco, alemán, francés, español, polaco, portugués, japonés y chino tradicional, además de árabe, italiano, coreano, neerlandés, ruso y chino.
- Descarga los archivos traducidos como un archivo ZIP. Los nombres incluyen el código del idioma de destino, por ejemplo, `common_en.json` o `common_zh-TW.json`.
- Organiza los archivos de traducción por sesión del navegador.
- Ofrece temas claro y oscuro.

Se espera que los marcadores de posición como `{name}`, `%s` y `%d` se mantengan intactos durante la traducción.

## Requisitos

- Python 3.10 o posterior
- Una clave de API de NVIDIA NIM
- `Flask`, `openai` y `python-dotenv`

## Instalación

### 1. Crear y activar un entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

En Windows PowerShell, actívalo con:

```powershell
venv\Scripts\Activate.ps1
```

### 2. Instalar las dependencias

```bash
python -m pip install Flask openai python-dotenv
```

### 3. Configurar la clave de API

Copia el archivo de entorno de ejemplo:

```bash
cp .env.example .env
```

Añade tu clave de API de NVIDIA NIM a `.env`:

```dotenv
NVIDIA_API_KEY=your_nvidia_api_key_here
```

Mantén `.env` privado y no lo incluyas en el control de versiones.

## Ejecutar la aplicación

```bash
python app.py
```

Abre [http://localhost:5001](http://localhost:5001) en el navegador.

## Ejecutar las pruebas

Las pruebas específicas de los idiomas utilizan un traductor simulado y no requieren acceso a la API:

```bash
python -m unittest test_translation_flow -v
node test_ui_flow.js
```

La suite del traductor realiza una solicitud real a la API de NVIDIA. Configura `NVIDIA_API_KEY` antes de ejecutarla:

```bash
python test.py --live
```

## Archivos del proyecto

| Archivo | Descripción |
| --- | --- |
| `app.py` | Aplicación Flask, interfaz web y flujo de traducción JSON |
| `test_translation_flow.py` | Pruebas de idiomas de destino y archivos ZIP |
| `test_ui_flow.js` | Offline UI submission, loading, success and error checks (Node.js) |
| `test.py` | Comprobación de conexión con la API de NVIDIA |
| `.env.example` | Configuración de ejemplo para las variables de entorno |

## Licencia

Este proyecto se distribuye bajo la licencia MIT.

<a id="polski"></a>

---

# 🇵🇱 Holm Open Translate — Polski

Holm Open Translate to aplikacja Flask do tłumaczenia plików lokalizacyjnych JSON za pomocą API tłumaczeniowego NVIDIA NIM. Prześlij jeden lub więcej plików JSON, wybierz języki docelowe i pobierz przetłumaczone pliki w archiwum ZIP.

## Funkcje

- Przesyłanie wielu plików JSON w jednym żądaniu.
- Rekurencyjne tłumaczenie wartości tekstowych z zachowaniem kluczy i struktury JSON.
- Zachowanie wartości innych niż tekst, takich jak liczby, wartości logiczne i `null`.
- Wybór jednego lub wielu języków docelowych. Interfejs i tłumaczenia obsługują język angielski, turecki, niemiecki, francuski, hiszpański, polski, portugalski, japoński i chiński tradycyjny, a także arabski, włoski, koreański, niderlandzki, rosyjski i chiński.
- Pobieranie przetłumaczonych plików jako archiwum ZIP. Nazwy plików zawierają kod języka docelowego, na przykład `common_en.json` lub `common_zh-TW.json`.
- Organizowanie archiwów tłumaczeń według sesji przeglądarki.
- Jasny i ciemny motyw interfejsu.

Zakłada się, że symbole zastępcze, takie jak `{name}`, `%s` i `%d`, pozostaną niezmienione podczas tłumaczenia.

## Wymagania

- Python 3.10 lub nowszy
- Klucz API NVIDIA NIM
- `Flask`, `openai` i `python-dotenv`

## Konfiguracja

### 1. Utwórz i aktywuj środowisko wirtualne

```bash
python3 -m venv venv
source venv/bin/activate
```

W Windows PowerShell aktywuj je poleceniem:

```powershell
venv\Scripts\Activate.ps1
```

### 2. Zainstaluj zależności

```bash
python -m pip install Flask openai python-dotenv
```

### 3. Skonfiguruj klucz API

Skopiuj przykładowy plik środowiskowy:

```bash
cp .env.example .env
```

Dodaj klucz API NVIDIA NIM do pliku `.env`:

```dotenv
NVIDIA_API_KEY=your_nvidia_api_key_here
```

Nie udostępniaj pliku `.env` ani nie dodawaj go do repozytorium.

## Uruchamianie aplikacji

```bash
python app.py
```

Otwórz w przeglądarce adres [http://localhost:5001](http://localhost:5001).

## Uruchamianie testów

Testy języków docelowych korzystają z translatora zastępczego i nie wymagają dostępu do API:

```bash
python -m unittest test_translation_flow -v
node test_ui_flow.js
```

Testy translatora wysyłają rzeczywiste żądanie do API NVIDIA. Przed ich uruchomieniem skonfiguruj `NVIDIA_API_KEY`:

```bash
python test.py --live
```

## Pliki projektu

| Plik | Opis |
| --- | --- |
| `app.py` | Aplikacja Flask, interfejs WWW i proces tłumaczenia JSON |
| `test_translation_flow.py` | Testy języków docelowych i archiwum ZIP |
| `test_ui_flow.js` | Offline UI submission, loading, success and error checks (Node.js) |
| `test.py` | Test połączenia z API NVIDIA |
| `.env.example` | Przykładowa konfiguracja zmiennych środowiskowych |

## Licencja

Projekt jest rozpowszechniany na licencji MIT.

<a id="portugues"></a>

---

# 🇵🇹 Holm Open Translate — Português

Holm Open Translate é uma aplicação Flask para traduzir ficheiros de localização JSON através da API de tradução NVIDIA NIM. Carregue um ou mais ficheiros JSON, escolha os idiomas de destino e transfira os ficheiros traduzidos num arquivo ZIP.

## Funcionalidades

- Carregar vários ficheiros JSON num único pedido.
- Traduzir recursivamente os valores de texto, mantendo as chaves e a estrutura JSON.
- Preservar valores que não sejam texto, como números, booleanos e `null`.
- Escolher um ou mais idiomas de destino. A interface e as traduções suportam inglês, turco, alemão, francês, espanhol, polaco, português, japonês e chinês tradicional, além de árabe, italiano, coreano, neerlandês, russo e chinês.
- Transferir os ficheiros traduzidos num arquivo ZIP. Os nomes incluem o código do idioma de destino, por exemplo, `common_en.json` ou `common_zh-TW.json`.
- Organizar os arquivos de tradução por sessão do navegador.
- Usar os temas claro e escuro.

Os marcadores de posição, como `{name}`, `%s` e `%d`, devem ser mantidos durante a tradução.

## Requisitos

- Python 3.10 ou posterior
- Uma chave de API NVIDIA NIM
- `Flask`, `openai` e `python-dotenv`

## Instalação

### 1. Criar e ativar um ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

No Windows PowerShell, ative-o com:

```powershell
venv\Scripts\Activate.ps1
```

### 2. Instalar as dependências

```bash
python -m pip install Flask openai python-dotenv
```

### 3. Configurar a chave de API

Copie o ficheiro de ambiente de exemplo:

```bash
cp .env.example .env
```

Adicione a sua chave de API NVIDIA NIM ao ficheiro `.env`:

```dotenv
NVIDIA_API_KEY=your_nvidia_api_key_here
```

Mantenha o ficheiro `.env` privado e não o inclua no controlo de versões.

## Executar a aplicação

```bash
python app.py
```

Abra [http://localhost:5001](http://localhost:5001) no navegador.

## Executar os testes

Os testes específicos dos idiomas utilizam um tradutor simulado e não precisam de acesso à API:

```bash
python -m unittest test_translation_flow -v
node test_ui_flow.js
```

A suite do tradutor envia um pedido real à API NVIDIA. Configure `NVIDIA_API_KEY` antes de a executar:

```bash
python test.py --live
```

## Ficheiros do projeto

| Ficheiro | Descrição |
| --- | --- |
| `app.py` | Aplicação Flask, interface Web e fluxo de tradução JSON |
| `test_translation_flow.py` | Testes dos idiomas de destino e do arquivo ZIP |
| `test_ui_flow.js` | Offline UI submission, loading, success and error checks (Node.js) |
| `test.py` | Verificação da ligação à API NVIDIA |
| `.env.example` | Configuração de exemplo das variáveis de ambiente |

## Licença

Este projeto é distribuído ao abrigo da licença MIT.

<a id="chinese"></a>

---

# 🇹🇼 Holm Open Translate — 繁體中文

Holm Open Translate 是一個使用 Flask 建置的應用程式，透過 NVIDIA NIM 翻譯 API 翻譯 JSON 在地化檔案。您可以上傳一個或多個 JSON 檔案、選擇目標語言，並將翻譯結果下載為 ZIP 封存檔。

## 功能

- 在同一個請求中上傳多個 JSON 檔案。
- 遞迴翻譯文字值，同時保留 JSON 索引鍵與資料結構。
- 保留數字、布林值和 `null` 等非文字值。
- 可選擇一種或多種目標語言。介面與翻譯目標支援英文、土耳其文、德文、法文、西班牙文、波蘭文、葡萄牙文、日文及繁體中文，另支援阿拉伯文、義大利文、韓文、荷蘭文、俄文及簡體中文。
- 將翻譯檔案下載為 ZIP 封存檔。檔名會加入目標語言代碼，例如 `common_en.json` 或 `common_zh-TW.json`。
- 依瀏覽器工作階段整理翻譯封存檔。
- 提供淺色與深色主題。

翻譯時預期會保留 `{name}`、`%s` 和 `%d` 等佔位符。

## 需求

- Python 3.10 或更新版本
- NVIDIA NIM API 金鑰
- `Flask`、`openai` 和 `python-dotenv`

## 安裝

### 1. 建立並啟用虛擬環境

```bash
python3 -m venv venv
source venv/bin/activate
```

在 Windows PowerShell 中，請使用以下指令啟用：

```powershell
venv\Scripts\Activate.ps1
```

### 2. 安裝相依套件

```bash
python -m pip install Flask openai python-dotenv
```

### 3. 設定 API 金鑰

複製環境變數範例檔：

```bash
cp .env.example .env
```

將 NVIDIA NIM API 金鑰加入 `.env`：

```dotenv
NVIDIA_API_KEY=your_nvidia_api_key_here
```

請妥善保管 `.env`，不要將其提交至原始碼版本庫。

## 執行應用程式

```bash
python app.py
```

在瀏覽器中開啟 [http://localhost:5001](http://localhost:5001)。

## 執行測試

目標語言測試使用模擬翻譯器，不需要存取 API：

```bash
python -m unittest test_translation_flow -v
node test_ui_flow.js
```

翻譯器測試會對 NVIDIA API 發出實際請求。執行前請先設定 `NVIDIA_API_KEY`：

```bash
python test.py --live
```

## 專案檔案

| 檔案 | 說明 |
| --- | --- |
| `app.py` | Flask 應用程式、網頁介面與 JSON 翻譯流程 |
| `test_translation_flow.py` | 目標語言與 ZIP 輸出測試 |
| `test_ui_flow.js` | Offline UI submission, loading, success and error checks (Node.js) |
| `test.py` | NVIDIA API 連線測試 |
| `.env.example` | 環境變數設定範例 |

## 授權條款

本專案依 MIT 授權條款發布。

<a id="japanese"></a>

---

# 🇯🇵 Holm Open Translate — 日本語

Holm Open Translateは、NVIDIA NIM翻訳APIを使用してJSONローカライズファイルを翻訳するFlaskアプリケーションです。1つ以上のJSONファイルをアップロードし、翻訳先の言語を選択すると、翻訳済みファイルをZIPアーカイブとしてダウンロードできます。

## 機能

- 1回のリクエストで複数のJSONファイルをアップロードできます。
- JSONのキーとデータ構造を維持したまま、文字列値を再帰的に翻訳します。
- 数値、真偽値、`null`などの文字列以外の値を保持します。
- 1つ以上の翻訳先言語を選択できます。インターフェースと翻訳先は、英語、トルコ語、ドイツ語、フランス語、スペイン語、ポーランド語、ポルトガル語、日本語、繁体字中国語に加え、アラビア語、イタリア語、韓国語、オランダ語、ロシア語、中国語に対応しています。
- 翻訳済みファイルをZIPアーカイブとしてダウンロードできます。ファイル名には翻訳先の言語コードが含まれます（例：`common_en.json`、`common_zh-TW.json`）。
- 翻訳アーカイブをブラウザーのセッションごとに管理します。
- ライトテーマとダークテーマを利用できます。

`{name}`、`%s`、`%d`などのプレースホルダーは翻訳後も保持される想定です。

## 必要条件

- Python 3.10以降
- NVIDIA NIM APIキー
- `Flask`、`openai`、`python-dotenv`

## セットアップ

### 1. 仮想環境を作成して有効化する

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows PowerShellでは、次のコマンドで有効化します。

```powershell
venv\Scripts\Activate.ps1
```

### 2. 依存関係をインストールする

```bash
python -m pip install Flask openai python-dotenv
```

### 3. APIキーを設定する

環境変数のサンプルファイルをコピーします。

```bash
cp .env.example .env
```

NVIDIA NIM APIキーを`.env`に追加します。

```dotenv
NVIDIA_API_KEY=your_nvidia_api_key_here
```

`.env`は安全に管理し、ソース管理に含めないでください。

## アプリケーションの起動

```bash
python app.py
```

ブラウザーで[http://localhost:5001](http://localhost:5001)を開きます。

## テストの実行

対象言語のテストではモック翻訳器を使用するため、APIアクセスは不要です。

```bash
python -m unittest test_translation_flow -v
node test_ui_flow.js
```

翻訳器のテストではNVIDIA APIに実際のリクエストを送信します。実行前に`NVIDIA_API_KEY`を設定してください。

```bash
python test.py --live
```

## プロジェクトファイル

| ファイル | 説明 |
| --- | --- |
| `app.py` | Flaskアプリケーション、Webインターフェース、JSON翻訳処理 |
| `test_translation_flow.py` | 翻訳先言語とZIP出力のテスト |
| `test_ui_flow.js` | Offline UI submission, loading, success and error checks (Node.js) |
| `test.py` | NVIDIA API接続テスト |
| `.env.example` | 環境変数設定のサンプル |

## ライセンス

本プロジェクトはMITライセンスのもとで配布されています。
