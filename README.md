# BallonsTranslator (Vertex AI & Enhanced LLM Edition)

## 🇰🇷 한국어 (Korean)

### 주요 업데이트 사항
본 저장소는 원본 프로젝트에 다음의 핵심 기능들을 추가한 강화 버전입니다.

1. **Vertex AI 지원**: 번역 및 OCR 모듈에서 Google Vertex AI를 공식 지원합니다.
   - 프로젝트 ID, 지역(Location), 서비스 계정 JSON 키 설정을 통해 기업용 인프라 사용 가능.
2. **프로바이더별 API 키 개별 관리**: 
   - 이제 각 LLM 프로바이더(OpenAI, Google, Vertex AI, Ollama 등)마다 API 키를 따로 저장합니다.
   - 프로바이더를 전환할 때마다 해당 프로바이더의 키가 자동으로 복구되어 표시됩니다.
   - 프로그램 종료 후 다시 시작해도 모든 프로바이더의 설정이 그대로 유지됩니다.
3. **Gemini 3.0, 3.1 지원**: Google의 최신 모델인 Gemini 3.0 및 3.1 버전을 공식 지원합니다.

### 사용 방법
- **설정 패널**에서 `LLM_API_Translator`를 선택합니다.
- 원하는 프로바이더(예: Vertex AI)를 선택하고 관련 키를 입력합니다.
- 다른 프로바이더로 바꿨다가 다시 돌아와도 이전에 입력한 키가 그대로 남아있는 것을 확인할 수 있습니다.

---

## 🇺🇸 English

### Major Updates
This repository is an enhanced version with the following key features added:

1. **Vertex AI Support**: Official support for Google Vertex AI in both Translation and OCR modules.
   - Supports Project ID, Location, and Service Account JSON key authentication.
2. **Provider-Specific API Key Management**:
   - Each LLM provider (OpenAI, Google, Vertex AI, Ollama, etc.) now has its own dedicated API key storage.
   - Switching between providers automatically restores and displays the corresponding API key.
   - All provider settings are persisted even after restarting the application.
3. **Gemini 3.0 & 3.1 Support**: Official support for Google's latest Gemini 3.0 and 3.1 models.

### How to Use
- Select `LLM_API_Translator` in the **Config Panel**.
- Choose your preferred provider (e.g., Vertex AI) and enter the required credentials.
- Notice that switching providers now preserves the individual API keys you've entered for each.

---

## 🇯🇵 日本語 (Japanese)

### 主な更新内容
このリポジトリは、元のプロジェクトに以下の主要機能を追加した強化版です。

1. **Vertex AI サポート**: 翻訳およびOCRモジュールでGoogle Vertex AIを公式にサポートしました。
   - プロジェクトID、ロケーション、サービスアカウントのJSONキー設定により、企業向けインフラの利用が可能。
2. **プロバイダー別APIキーの個別管理**:
   - 各LLMプロバイダー（OpenAI、Google、Vertex AI、Ollamaなど）ごとにAPIキーを個別に保存します。
   - プロバイダーを切り替えるたびに、該当するキーが自動的に復元され表示されます。
   - アプリを再起動しても、すべてのプロバイダーの設定が維持されます。
3. **Gemini 3.0, 3.1 サポート**: Googleの最新モデルであるGemini 3.0および3.1バージョンを公式にサポートしました。

### 使用方法
- **設定パネル**で `LLM_API_Translator` を選択します。
- 任意のプロバイ더（例：Vertex AI）を選択し、キーを入力します。
- プロバイダーを切り替えても、各プロバイダーごとに入力した設定が保持されていることが確認できます。

---

## 🇨🇳 中国语 (Chinese)

### 主要更新
本仓库是原项目的增强版本，添加了以下核心功能：

1. **支持 Vertex AI**: 在翻译和 OCR 模块中正式支持 Google Vertex AI。
   - 支持通过项目 ID、位置（Location）和服务账号 JSON 密钥进行身份验证。
2. **多提供商 API 密钥独立 management**:
   - 现为每个 LLM 提供商（OpenAI, Google, Vertex AI, Ollama 等）提供独立的 API 密钥存储。
   - 切换提供商时，系统会自动恢复并显示该提供商对应的密钥。
   - 即使重启程序，所有提供商的设置也会被完整保留。
3. **支持 Gemini 3.0, 3.1**: 官方支持 Google 的最新模型 Gemini 3.0 和 3.1 版本。

### 使用方法
- 在**配置面板**中选择 `LLM_API_Translator`。
- 选择所需的提供商（如 Vertex AI）并输入相关密钥。
- 您会发现，即使在不同提供商之间切换，之前输入的每个密钥都会被妥善保存。

---

**Original Project:** [dmMaze/BallonsTranslator](https://github.com/dmMaze/BallonsTranslator)
