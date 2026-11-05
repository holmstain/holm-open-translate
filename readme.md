# Holm Translate

Holm Translate is a Flask application for translating JSON localization files with the NVIDIA NIM translation API. Upload one or more JSON files, choose target languages, and download the translated files in a ZIP archive.

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
- `Flask`, `openai`, and `python-dotenv`

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

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Run tests

The focused translation-target tests use a mocked translator and do not require API access:

```bash
python -m pytest -q test_language_targets.py
```

The translator test suite includes a live NVIDIA API request. Configure `NVIDIA_API_KEY` before running it:

```bash
python -m unittest test_translator.py
```

## Project files

| File | Description |
| --- | --- |
| `app.py` | Flask application, web interface, and JSON translation workflow |
| `test_language_targets.py` | Tests for translation targets and ZIP output |
| `test_translator.py` | Translator, output JSON, and placeholder checks |
| `test.py` | Simple NVIDIA API connectivity check |
| `.env.example` | Example environment variable configuration |

## License

This project is distributed under the MIT License.

<a id="turkce"></a>

---

# 🇹🇷 Holm Translate — Türkçe

Holm Translate, JSON yerelleştirme dosyalarını NVIDIA NIM çeviri API’siyle çevirmek için geliştirilmiş bir Flask uygulamasıdır. Bir veya daha fazla JSON dosyası yükleyin, hedef dilleri seçin ve çevrilmiş dosyaları ZIP arşivi olarak indirin.

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

Tarayıcınızda [http://localhost:5000](http://localhost:5000) adresini açın.

## Testleri çalıştırma

Odaklı hedef dil testleri taklitçi çeviri kullanır ve API erişimi gerektirmez:

```bash
python -m pytest -q test_language_targets.py
```

Çevirmen test paketi NVIDIA API'sine canlı bir istek gönderir. Çalıştırmadan önce `NVIDIA_API_KEY` değerini yapılandırın:

```bash
python -m unittest test_translator.py
```

## Proje dosyaları

| Dosya | Açıklama |
| --- | --- |
| `app.py` | Flask uygulaması, web arayüzü ve JSON çeviri akışı |
| `test_language_targets.py` | Çeviri hedefleri ve ZIP çıktısı testleri |
| `test_translator.py` | Çevirmen, çıktı JSON'u ve yer tutucu kontrolleri |
| `test.py` | NVIDIA API bağlantı kontrolü |
| `.env.example` | Örnek ortam değişkeni yapılandırması |

## Lisans

Bu proje MIT Lisansı ile dağıtılır.

<a id="espanol"></a>

---

# 🇪🇸 Holm Translate — Español

Holm Translate es una aplicación Flask para traducir archivos de localización JSON mediante la API de traducción NVIDIA NIM. Sube uno o varios archivos JSON, elige los idiomas de destino y descarga los archivos traducidos en un archivo ZIP.

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

Abre [http://localhost:5000](http://localhost:5000) en el navegador.

## Ejecutar las pruebas

Las pruebas específicas de los idiomas utilizan un traductor simulado y no requieren acceso a la API:

```bash
python -m pytest -q test_language_targets.py
```

La suite del traductor realiza una solicitud real a la API de NVIDIA. Configura `NVIDIA_API_KEY` antes de ejecutarla:

```bash
python -m unittest test_translator.py
```

## Archivos del proyecto

| Archivo | Descripción |
| --- | --- |
| `app.py` | Aplicación Flask, interfaz web y flujo de traducción JSON |
| `test_language_targets.py` | Pruebas de idiomas de destino y archivos ZIP |
| `test_translator.py` | Pruebas del traductor, JSON de salida y marcadores de posición |
| `test.py` | Comprobación de conexión con la API de NVIDIA |
| `.env.example` | Configuración de ejemplo para las variables de entorno |

## Licencia

Este proyecto se distribuye bajo la licencia MIT.

<a id="polski"></a>

---

# 🇵🇱 Holm Translate — Polski

Holm Translate to aplikacja Flask do tłumaczenia plików lokalizacyjnych JSON za pomocą API tłumaczeniowego NVIDIA NIM. Prześlij jeden lub więcej plików JSON, wybierz języki docelowe i pobierz przetłumaczone pliki w archiwum ZIP.

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

Otwórz w przeglądarce adres [http://localhost:5000](http://localhost:5000).

## Uruchamianie testów

Testy języków docelowych korzystają z translatora zastępczego i nie wymagają dostępu do API:

```bash
python -m pytest -q test_language_targets.py
```

Testy translatora wysyłają rzeczywiste żądanie do API NVIDIA. Przed ich uruchomieniem skonfiguruj `NVIDIA_API_KEY`:

```bash
python -m unittest test_translator.py
```

## Pliki projektu

| Plik | Opis |
| --- | --- |
| `app.py` | Aplikacja Flask, interfejs WWW i proces tłumaczenia JSON |
| `test_language_targets.py` | Testy języków docelowych i archiwum ZIP |
| `test_translator.py` | Testy translatora, wyjściowego JSON i symboli zastępczych |
| `test.py` | Test połączenia z API NVIDIA |
| `.env.example` | Przykładowa konfiguracja zmiennych środowiskowych |

## Licencja

Projekt jest rozpowszechniany na licencji MIT.

<a id="portugues"></a>

---

# 🇵🇹 Holm Translate — Português

Holm Translate é uma aplicação Flask para traduzir ficheiros de localização JSON através da API de tradução NVIDIA NIM. Carregue um ou mais ficheiros JSON, escolha os idiomas de destino e transfira os ficheiros traduzidos num arquivo ZIP.

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

Abra [http://localhost:5000](http://localhost:5000) no navegador.

## Executar os testes

Os testes específicos dos idiomas utilizam um tradutor simulado e não precisam de acesso à API:

```bash
python -m pytest -q test_language_targets.py
```

A suite do tradutor envia um pedido real à API NVIDIA. Configure `NVIDIA_API_KEY` antes de a executar:

```bash
python -m unittest test_translator.py
```

## Ficheiros do projeto

| Ficheiro | Descrição |
| --- | --- |
| `app.py` | Aplicação Flask, interface Web e fluxo de tradução JSON |
| `test_language_targets.py` | Testes dos idiomas de destino e do arquivo ZIP |
| `test_translator.py` | Testes do tradutor, do JSON de saída e dos marcadores de posição |
| `test.py` | Verificação da ligação à API NVIDIA |
| `.env.example` | Configuração de exemplo das variáveis de ambiente |

## Licença

Este projeto é distribuído ao abrigo da licença MIT.

<a id="chinese"></a>

---

# 🇹🇼 Holm Translate — 繁體中文

Holm Translate 是一個使用 Flask 建置的應用程式，透過 NVIDIA NIM 翻譯 API 翻譯 JSON 在地化檔案。您可以上傳一個或多個 JSON 檔案、選擇目標語言，並將翻譯結果下載為 ZIP 封存檔。

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

在瀏覽器中開啟 [http://localhost:5000](http://localhost:5000)。

## 執行測試

目標語言測試使用模擬翻譯器，不需要存取 API：

```bash
python -m pytest -q test_language_targets.py
```

翻譯器測試會對 NVIDIA API 發出實際請求。執行前請先設定 `NVIDIA_API_KEY`：

```bash
python -m unittest test_translator.py
```

## 專案檔案

| 檔案 | 說明 |
| --- | --- |
| `app.py` | Flask 應用程式、網頁介面與 JSON 翻譯流程 |
| `test_language_targets.py` | 目標語言與 ZIP 輸出測試 |
| `test_translator.py` | 翻譯器、輸出 JSON 與佔位符測試 |
| `test.py` | NVIDIA API 連線測試 |
| `.env.example` | 環境變數設定範例 |

## 授權條款

本專案依 MIT 授權條款發布。

<a id="japanese"></a>

---

# 🇯🇵 Holm Translate — 日本語

Holm Translateは、NVIDIA NIM翻訳APIを使用してJSONローカライズファイルを翻訳するFlaskアプリケーションです。1つ以上のJSONファイルをアップロードし、翻訳先の言語を選択すると、翻訳済みファイルをZIPアーカイブとしてダウンロードできます。

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

ブラウザーで[http://localhost:5000](http://localhost:5000)を開きます。

## テストの実行

対象言語のテストではモック翻訳器を使用するため、APIアクセスは不要です。

```bash
python -m pytest -q test_language_targets.py
```

翻訳器のテストではNVIDIA APIに実際のリクエストを送信します。実行前に`NVIDIA_API_KEY`を設定してください。

```bash
python -m unittest test_translator.py
```

## プロジェクトファイル

| ファイル | 説明 |
| --- | --- |
| `app.py` | Flaskアプリケーション、Webインターフェース、JSON翻訳処理 |
| `test_language_targets.py` | 翻訳先言語とZIP出力のテスト |
| `test_translator.py` | 翻訳器、出力JSON、プレースホルダーのテスト |
| `test.py` | NVIDIA API接続テスト |
| `.env.example` | 環境変数設定のサンプル |

## ライセンス

本プロジェクトはMITライセンスのもとで配布されています。
