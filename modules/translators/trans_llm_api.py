import re
import time
import json
import traceback
import os
from typing import List, Dict, Optional, Type

import httpx
import openai
from pydantic import BaseModel, Field, ValidationError

from .base import BaseTranslator, register_translator


class InvalidNumTranslations(Exception):
    """Exception raised when the number of translations does not match the number of sources."""

    pass


class TranslationElement(BaseModel):
    id: int = Field(..., description="The original numeric ID of the text snippet.")
    translation: str = Field(
        ..., description="The translated text corresponding to the id."
    )


class TranslationResponse(BaseModel):
    translations: List[TranslationElement] = Field(
        ..., description="A list of all translated elements."
    )


@register_translator("LLM_API_Translator")
class LLM_API_Translator(BaseTranslator):
    concate_text = False
    cht_require_convert = True
    params: Dict = {
        "provider": {
            "type": "selector",
            "options": ["OpenAI", "Google", "Grok", "OpenRouter", "LLM Studio", "Ollama", "Vertex AI"],
            "value": "OpenAI",
            "description": "Select the LLM provider.",
        },
        "apikey": {
            "value": "",
            "description": "Single API key to use if multiple keys are not provided.",
        },
        "multiple_keys": {
            "type": "editor",
            "value": "",
            "description": "API keys separated by semicolons (;). Requests will rotate through these keys.",
        },
        "model": {
            "type": "selector",
            "options": [
                "OAI: gpt-4o",
                "OAI: gpt-4-turbo",
                "OAI: gpt-3.5-turbo",
                "GGL: gemini-3.1-pro-preview",
                "GGL: gemini-3.1-flash-lite-preview",
                "GGL: gemini-3-pro-preview",
                "GGL: gemini-3-flash-preview",
                "GGL: gemini-1.5-pro-latest",
                "XAI: grok-4",
                "XAI: grok-3",
                "XAI: grok-3-mini",
                "LLMS: (override model field)",
                "OLLAMA: (override model field)",
            ],
            "value": "OAI: gpt-4o",
            "description": "Select a model that supports JSON Mode for structured output.",
        },
        "override model": {
            "value": "",
            "description": "Specify a custom model name to override the selected model.",
        },
        "endpoint": {
            "value": "",
            "description": "Base URL for the API. Leave empty for provider default.",
        },
        "vertex_location": {
            "type": "selector",
            "options": [
                "us-central1",
                "us-east4",
                "us-west1",
                "us-west4",
                "europe-west1",
                "europe-west2",
                "europe-west3",
                "europe-west4",
                "europe-west9",
                "europe-north1",
                "asia-northeast1",
                "asia-northeast2",
                "asia-northeast3",
                "asia-southeast1",
                "asia-south1",
                "australia-southeast1",
                "southamerica-east1",
                "northamerica-northeast1",
            ],
            "value": "us-central1",
            "description": "Vertex AI region.",
        },
        "vertex_project": {
            "value": "",
            "description": "GCP Project ID for Vertex AI. Required when provider is Vertex AI.",
        },
        "vertex_credentials": {
            "type": "line_editor",
            "value": "",
            "description": "Path to the Vertex AI service account JSON key file.",
            "path_selector": True,
            "path_filter": "JSON Files (*.json)",
        },
        "system_prompt": {
            "type": "editor",
            "value": 'You are an expert translator. Your task is to accurately translate the given text snippets. You MUST provide the output strictly in the specified JSON format, without any additional explanations or markdown formatting. The JSON object must have a single key \'translations\', which is a list of objects, each with an \'id\' (integer) and a \'translation\' (string).\n\nExample Output Schema:\n{"translations": [{"id": 1, "translation": "Translated text here."}]}',
            "description": "System message to instruct the LLM on its role and required output format.",
        },
        "invalid repeat count": {
            "value": 2,
            "description": "Number of retries if the count of translations mismatches the source count.",
        },
        "max requests per minute": {
            "value": 20,
            "description": "Maximum requests per minute for EACH API key.",
        },
        "delay": {
            "value": 0.3,
            "description": "Global delay in seconds between requests.",
        },
        "max tokens": {
            "value": 4096,
            "description": "Maximum tokens for the response.",
        },
        "temperature": {
            "value": 0.1,
            "description": "Sampling temperature. Lower values are recommended for structured output.",
        },
        "top p": {
            "value": 1.0,
            "description": "Top P for sampling.",
        },
        "retry attempts": {
            "value": 3,
            "description": "Number of retry attempts on API connection or parsing failures.",
        },
        "retry timeout": {
            "value": 15,
            "description": "Timeout between retry attempts (seconds).",
        },
        "proxy": {
            "value": "",
            "description": "Proxy address (e.g., http(s)://user:password@host:port or socks4/5://user:password@host:port)",
        },
        "frequency penalty": {
            "value": 0.0,
            "description": "Frequency penalty (OpenAI).",
        },
        "presence penalty": {"value": 0.0, "description": "Presence penalty (OpenAI)."},
        "low vram mode": {
            'value': False,
            'description': 'check it if you\'re running it locally on a single device and encountered a crash due to vram OOM',
            'type': 'checkbox',
        },
        "__provider_configs": {
            "value": {
                "OpenAI": {"apikey": "", "multiple_keys": ""},
                "Google": {"apikey": "", "multiple_keys": ""},
                "Grok": {"apikey": "", "multiple_keys": ""},
                "OpenRouter": {"apikey": "", "multiple_keys": ""},
                "LLM Studio": {"apikey": "", "multiple_keys": ""},
                "Ollama": {"apikey": "", "multiple_keys": ""},
                "Vertex AI": {"apikey": "", "multiple_keys": ""},
            },
        },
        "description": "Translator using various LLM APIs.",
    }

    def _setup_translator(self):
        self.lang_map = {
            "简体中文": "Simplified Chinese",
            "繁體中文": "Traditional Chinese",
            "日本語": "Japanese",
            "English": "English",
            "한국어": "Korean",
            "Tiếng Việt": "Vietnamese",
            "čeština": "Czech",
            "Français": "French",
            "Deutsch": "German",
            "magyar nyelv": "Hungarian",
            "Italiano": "Italian",
            "Polski": "Polish",
            "Português": "Portuguese",
            "limba română": "Romanian",
            "русский язык": "Russian",
            "Español": "Spanish",
            "Türk dili": "Turkish",
            "украї́нська мо́ва": "Ukrainian",
            "Thai": "Thai",
            "Arabic": "Arabic",
            "Malayalam": "Malayalam",
            "Tamil": "Tamil",
            "Hindi": "Hindi",
        }
        self.token_count = 0
        self.token_count_last = 0
        self.current_key_index = 0
        self.last_request_time = 0
        self.request_count_minute = 0
        self.minute_start_time = time.time()
        self.key_usage = {}
        self.client = None
        # Restore config for current provider on startup
        self._restore_provider_config(self.provider)
        self._update_model_options(self.provider)

    def _restore_provider_config(self, provider: str):
        configs = self.get_param_value("__provider_configs")
        if provider in configs:
            config = configs[provider]
            self.set_param_value("apikey", config.get("apikey", ""))
            self.set_param_value("multiple_keys", config.get("multiple_keys", ""))

    def _update_model_options(self, provider: str):
        all_models = [
            "OAI: gpt-4o", "OAI: gpt-4-turbo", "OAI: gpt-3.5-turbo",
            "GGL: gemini-3.1-pro-preview", "GGL: gemini-3.1-flash-lite-preview",
            "GGL: gemini-3-pro-preview", "GGL: gemini-3-flash-preview",
            "GGL: gemini-2.5-pro", "GGL: gemini-2.5-flash", "GGL: gemini-2.5-flash-lite", "GGL: gemini-2.0-flash",
            "GGL: gemini-1.5-pro-latest",
            "VAI: gemini-3.1-pro-preview", "VAI: gemini-3.1-flash-lite-preview",
            "VAI: gemini-3-pro-preview", "VAI: gemini-3-flash-preview",
            "VAI: gemini-2.5-pro", "VAI: gemini-2.5-flash", "VAI: gemini-2.0-flash", "VAI: gemini-1.5-pro",
            "XAI: grok-4", "XAI: grok-3", "XAI: grok-3-mini",
            "LLMS: (override model field)", "OLLAMA: (override model field)",
        ]
        if provider == "Vertex AI":
            filtered_models = [m for m in all_models if m.startswith("VAI:") or m.startswith("LLMS:")]
        else:
            filtered_models = [m for m in all_models if not m.startswith("VAI:")]
        self.params["model"]["options"] = filtered_models

    def _initialize_client(self, api_key_to_use: str) -> bool:
        provider = self.provider
        if provider == "Vertex AI":
            # Vertex AI uses native Gemini REST API, not OpenAI compat
            self.client = None
            return True

        endpoint = self.endpoint
        if not endpoint:
            if provider == "Google":
                endpoint = "https://generativelanguage.googleapis.com/v1beta/openai"
            elif provider == "OpenAI":
                endpoint = "https://api.openai.com/v1"
            elif provider == "OpenRouter":
                endpoint = "https://openrouter.ai/api/v1"
            elif provider == "Grok":
                endpoint = "https://api.x.ai/v1"
            elif provider == "Ollama":
                endpoint = "http://localhost:11434/v1"

        proxy = self.proxy
        http_client = None
        if proxy:
            try:
                proxy_mounts = {
                    "http://": httpx.HTTPTransport(proxy=proxy),
                    "https://": httpx.HTTPTransport(proxy=proxy),
                }
                http_client = httpx.Client(mounts=proxy_mounts)
            except Exception as e:
                self.logger.error(
                    f"Failed to initialize proxy '{proxy}': {e}. Proceeding without proxy."
                )
                http_client = httpx.Client()
        else:
            http_client = httpx.Client()

        masked_key = (
            api_key_to_use[:4] + "..." + api_key_to_use[-4:]
            if len(api_key_to_use) > 8
            else api_key_to_use
        )
        self.logger.debug(
            f"Initializing client for {provider} with key {masked_key} at endpoint {endpoint}"
        )

        try:
            self.client = openai.OpenAI(
                api_key=api_key_to_use, base_url=endpoint, http_client=http_client
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None
            return False

    # --- Property getters ---
    @property
    def provider(self) -> str:
        return self.get_param_value("provider")

    @property
    def apikey(self) -> str:
        return self.get_param_value("apikey")

    @property
    def multiple_keys_list(self) -> List[str]:
        keys_str = self.get_param_value("multiple_keys")
        if not isinstance(keys_str, str):
            return []
        return [
            key.strip()
            for key in keys_str.strip().replace("\n", ";").split(";")
            if key.strip()
        ]

    @property
    def model(self) -> str:
        return self.get_param_value("model")

    @property
    def override_model(self) -> Optional[str]:
        return self.get_param_value("override model") or None

    @property
    def endpoint(self) -> Optional[str]:
        return self.get_param_value("endpoint") or None

    @property
    def vertex_location(self) -> str:
        return self.get_param_value("vertex_location") or "us-central1"

    @property
    def vertex_project(self) -> str:
        return self.get_param_value("vertex_project") or ""

    @property
    def vertex_credentials(self) -> str:
        return self.get_param_value("vertex_credentials") or ""

    @property
    def temperature(self) -> float:
        return float(self.get_param_value("temperature"))

    @property
    def top_p(self) -> float:
        return float(self.get_param_value("top p"))

    @property
    def max_tokens(self) -> int:
        return int(self.get_param_value("max tokens"))

    @property
    def retry_attempts(self) -> int:
        return int(self.get_param_value("retry attempts"))

    @property
    def retry_timeout(self) -> int:
        return int(self.get_param_value("retry timeout"))

    @property
    def proxy(self) -> str:
        return self.get_param_value("proxy")

    @property
    def system_prompt(self) -> str:
        return self.get_param_value("system_prompt")

    @property
    def invalid_repeat_count(self) -> int:
        return int(self.get_param_value("invalid repeat count"))

    @property
    def frequency_penalty(self) -> float:
        return float(self.get_param_value("frequency penalty"))

    @property
    def presence_penalty(self) -> float:
        return float(self.get_param_value("presence penalty"))

    @property
    def max_rpm(self) -> int:
        return int(self.get_param_value("max requests per minute"))

    @property
    def global_delay(self) -> float:
        return float(self.get_param_value("delay"))

    def _assemble_prompts(self, queries: List[str], to_lang: str):
        from_lang = self.lang_map.get(self.lang_source, self.lang_source)

        input_elements = [
            {"id": i + 1, "source": query} for i, query in enumerate(queries)
        ]
        input_json_str = json.dumps(input_elements, ensure_ascii=False, indent=2)

        prompt = (
            f"Please translate the following text snippets from {from_lang} to {to_lang}. "
            f"The input is provided as a JSON array. Respond with a JSON object in the specified format.\n\n"
            f"INPUT:\n{input_json_str}"
        )

        yield prompt, len(queries)

    def _respect_delay(self):
        current_time = time.time()
        rpm = self.max_rpm
        delay = self.global_delay
        if rpm > 0:
            if current_time - self.minute_start_time >= 60:
                self.request_count_minute = 0
                self.minute_start_time = current_time
            if self.request_count_minute >= rpm:
                wait_time = 60.1 - (current_time - self.minute_start_time)
                if wait_time > 0:
                    self.logger.warning(
                        f"Global RPM limit ({rpm}) reached. Waiting {wait_time:.2f} seconds."
                    )
                    time.sleep(wait_time)
                self.request_count_minute = 0
                self.minute_start_time = time.time()

        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < delay:
            sleep_time = delay - time_since_last_request
            if hasattr(self, "debug_mode") and self.debug_mode:
                self.logger.debug(f"Global delay: Waiting {sleep_time:.3f} seconds.")
            time.sleep(sleep_time)

        self.last_request_time = time.time()
        self.request_count_minute += 1

    def _respect_key_limit(self, key: str) -> bool:
        rpm = self.max_rpm
        if rpm <= 0:
            return True
        now = time.time()
        count, start_time = self.key_usage.get(key, (0, now))
        if now - start_time >= 60:
            count, start_time = 0, now
            self.key_usage[key] = (count, start_time)
        if count >= rpm:
            wait_time = 60.1 - (now - start_time)
            if wait_time > 0:
                self.logger.warning(
                    f"RPM limit ({rpm}) reached for key {key[:6]}... Waiting {wait_time:.2f} seconds."
                )
                time.sleep(wait_time)
            self.key_usage[key] = (0, time.time())
            return False
        return True

    def _select_api_key(self) -> Optional[str]:
        api_keys = self.multiple_keys_list
        single_key = self.apikey
        if not api_keys and not single_key:
            self.logger.error("No API keys provided in parameters.")
            return None

        if not api_keys:
            if self._respect_key_limit(single_key):
                now = time.time()
                count, start_time = self.key_usage.get(single_key, (0, now))
                if now - start_time >= 60:
                    count = 0
                    start_time = now
                self.key_usage[single_key] = (count + 1, start_time)
                return single_key
            return None

        start_index = self.current_key_index
        for i in range(len(api_keys)):
            index = (start_index + i) % len(api_keys)
            key = api_keys[index]
            if self._respect_key_limit(key):
                now = time.time()
                count, start_time = self.key_usage.get(key, (0, now))
                self.key_usage[key] = (count + 1, start_time)
                self.current_key_index = (index + 1) % len(api_keys)
                return key
        self.logger.error("All available API keys are currently rate-limited.")
        return None

    def _get_vertex_token(self) -> Optional[str]:
        """Get OAuth2 access token from Vertex AI service account credentials."""
        vertex_credentials = self.get_param_value("vertex_credentials") or ""
        if not vertex_credentials:
            return None

        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests

            creds_path = vertex_credentials.strip()
            if os.path.isfile(creds_path):
                credentials = service_account.Credentials.from_service_account_file(
                    creds_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            else:
                self.logger.error(f"Vertex AI credentials file not found: {creds_path}")
                return None

            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            return credentials.token
        except Exception as e:
            self.logger.error(f"Failed to load Vertex AI credentials: {e}")
            return None

    def _request_vertex_translation(self, api_key: str, prompt: str) -> Optional[TranslationResponse]:
        """Make a direct REST API call to Vertex AI Gemini (generateContent)."""
        vertex_project = self.get_param_value("vertex_project") or ""
        vertex_location = self.get_param_value("vertex_location") or "us-central1"

        if not vertex_project:
            raise ValueError("vertex_project must be set for Vertex AI provider.")

        token = self._get_vertex_token()
        if not token:
            raise ConnectionError("Failed to obtain Vertex AI access token. Check your credentials file path/content.")

        model_name = self.override_model or self.model
        if ": " in model_name:
            model_name = model_name.split(": ", 1)[1]

        url = (
            f"https://{vertex_location}-aiplatform.googleapis.com/v1"
            f"/projects/{vertex_project}/locations/{vertex_location}"
            f"/publishers/google/models/{model_name}:generateContent"
        )

        contents = []
        if self.system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": self.system_prompt}]
            })
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "topP": self.top_p,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
            },
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        proxy = self.proxy
        http_client = None
        if proxy:
            try:
                proxy_mounts = {
                    "http://": httpx.HTTPTransport(proxy=proxy),
                    "https://": httpx.HTTPTransport(proxy=proxy),
                }
                http_client = httpx.Client(mounts=proxy_mounts)
            except Exception:
                http_client = httpx.Client()
        else:
            http_client = httpx.Client()

        self.logger.debug(f"Vertex AI request to model: {model_name}")
        response = http_client.post(url, headers=headers, json=body, timeout=60.0)

        if response.status_code != 200:
            self.logger.error(f"Vertex AI API error ({response.status_code}): {response.text}")
            raise httpx.HTTPStatusError(
                f"Vertex AI API error: {response.status_code}",
                request=response.request,
                response=response,
            )

        data = response.json()

        # Extract text from Gemini response
        text_content = ""
        if "candidates" in data and data["candidates"]:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                for part in parts:
                    if "text" in part:
                        text_content += part["text"]

        if not text_content:
            self.logger.warning("No text content in Vertex AI response.")
            return None

        # Extract usage info
        if "usageMetadata" in data:
            usage = data["usageMetadata"]
            total_tokens = usage.get("totalTokenCount", 0)
            self.token_count += total_tokens
            self.token_count_last = total_tokens
        else:
            self.token_count_last = 0

        # Parse JSON response
        json_to_parse = text_content.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", json_to_parse, re.DOTALL)
        if match:
            json_to_parse = match.group(1)
        else:
            start = json_to_parse.find("{")
            end = json_to_parse.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_to_parse = json_to_parse[start : end + 1]

        try:
            parsed = json.loads(json_to_parse)
            return TranslationResponse.model_validate(parsed)
        except (ValidationError, json.JSONDecodeError) as e:
            self.logger.warning(f"Initial parsing failed: {e}. Trying flexible format fix.")
            try:
                simple_data = json.loads(json_to_parse)
                fixed_translations = []

                # Case 1: {"result": [{"id": 1, "translation": "..."}, ...]}
                if isinstance(simple_data, dict):
                    for key in ("translations", "result", "items", "data"):
                        if key in simple_data and isinstance(simple_data[key], list):
                            fixed_translations = simple_data[key]
                            break

                    # Case 2: {"1": "...", "2": "..."}
                    if not fixed_translations and all(k.isdigit() for k in simple_data.keys()):
                        fixed_translations = [
                            {"id": int(k), "translation": v} for k, v in simple_data.items()
                        ]

                # Case 3: [{"id": 1, "translation": "..."}, ...]
                elif isinstance(simple_data, list):
                    fixed_translations = simple_data

                if fixed_translations:
                    return TranslationResponse.model_validate({"translations": fixed_translations})
                raise e
            except Exception as final_e:
                self.logger.error(f"Parse failed after fix attempt: {final_e}")
                self.logger.debug(f"Raw content: {text_content}")
                raise

    def _request_translation(self, prompt: str) -> Optional[TranslationResponse]:
        current_api_key = self._select_api_key()
        
        if not current_api_key:
            if self.provider in ["LLM Studio", "Ollama"]:
                current_api_key = "dummy-key"
            else:
                raise ConnectionError("No available API key found.")

        if self.provider == "LLM Studio" and not self.endpoint:
            raise ValueError(
                "Endpoint must be specified when using the LLM Studio provider (e.g., http://localhost:1234/v1)."
            )

        if not self._initialize_client(current_api_key):
            raise ConnectionError("Failed to initialize API client.")

        self._respect_delay()

        # Vertex AI uses native REST API
        if self.provider == "Vertex AI":
            return self._request_vertex_translation(current_api_key, prompt)

        model_name = self.override_model or self.model
        if ": " in model_name:
            model_name = model_name.split(": ", 1)[1]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        api_args = {
            "model": model_name,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

        if self.provider == "LLM Studio":
            self.logger.debug("Using 'json_schema' mode for LLM Studio.")
            api_args["response_format"] = {
                "type": "json_schema",
                "json_schema": {"schema": TranslationResponse.model_json_schema()},
            }
        elif self.provider in ["OpenAI", "Grok", "Google", "OpenRouter", "Ollama", "Vertex AI"]:
            self.logger.debug(f"Using 'json_object' mode for {self.provider}.")
            api_args["response_format"] = {"type": "json_object"}

        if self.provider == "OpenAI":
            api_args["frequency_penalty"] = self.frequency_penalty
            api_args["presence_penalty"] = self.presence_penalty

        try:
            completion = self.client.chat.completions.create(**api_args)
        except Exception as e:
            self.logger.error(f"API request failed: {e}")
            raise

        if (
            completion.choices
            and completion.choices[0].message
            and completion.choices[0].message.content
        ):
            raw_content = completion.choices[0].message.content
            json_to_parse = raw_content.strip()

            match = re.search(
                r"```(?:json)?\s*(\{.*?\})\s*```", json_to_parse, re.DOTALL
            )
            if match:
                self.logger.debug(
                    "Markdown code block detected. Extracting JSON content."
                )
                json_to_parse = match.group(1)
            else:
                start = json_to_parse.find("{")
                end = json_to_parse.rfind("}")
                if start != -1 and end != -1 and end > start:
                    json_to_parse = json_to_parse[start : end + 1]
            try:
                data_to_validate = json.loads(json_to_parse)
                validated_response = TranslationResponse.model_validate(
                    data_to_validate
                )
            except (ValidationError, json.JSONDecodeError) as e:
                self.logger.warning(
                    f"Initial Pydantic validation failed: {e}. Attempting to fix simple dictionary or list format."
                )
                try:
                    simple_data = json.loads(json_to_parse)
                    fixed_translations = []

                    if isinstance(simple_data, dict) and all(
                        k.isdigit() for k in simple_data.keys()
                    ):
                        fixed_translations = [
                            {"id": int(k), "translation": v}
                            for k, v in simple_data.items()
                        ]
                    elif isinstance(simple_data, list):
                        fixed_translations = simple_data

                    if fixed_translations:
                        fixed_data = {"translations": fixed_translations}
                        self.logger.debug(
                            f"Transformed simple response to: {fixed_data}"
                        )
                        validated_response = TranslationResponse.model_validate(
                            fixed_data
                        )
                        self.logger.info(
                            "Successfully parsed response after fixing simple format."
                        )
                    else:
                        raise e
                except (ValidationError, json.JSONDecodeError, Exception) as final_e:
                    self.logger.error(
                        f"Pydantic validation or JSON parsing failed even after attempting fix: {final_e}"
                    )
                    self.logger.debug(f"Raw JSON content from API: {raw_content}")
                    raise
        else:
            self.logger.warning("No valid message content in API response.")
            return None

        if hasattr(completion, "usage") and completion.usage:
            self.token_count += completion.usage.total_tokens
            self.token_count_last = completion.usage.total_tokens
        else:
            self.token_count_last = 0

        return validated_response

    def _translate(self, src_list: List[str]) -> List[str]:
        if not src_list:
            return []

        RETRYABLE_EXCEPTIONS = (
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.APIStatusError,
            httpx.RequestError,
            httpx.HTTPStatusError,
            httpx.ConnectError,
            httpx.ReadTimeout,
        )

        translations = []
        to_lang = self.lang_map.get(self.lang_target, self.lang_target)

        for prompt, num_src in self._assemble_prompts(src_list, to_lang=to_lang):
            api_retry_attempt = 0
            mismatch_retry_attempt = 0

            while True:
                try:
                    parsed_response = self._request_translation(prompt)

                    if not parsed_response or not parsed_response.translations:
                        raise ValueError(
                            "Received empty or invalid parsed response from API."
                        )

                    if len(parsed_response.translations) != num_src:
                        raise InvalidNumTranslations(
                            f"Expected {num_src}, got {len(parsed_response.translations)}"
                        )

                    translations_dict = {
                        item.id: item.translation
                        for item in parsed_response.translations
                    }
                    ordered_translations = [
                        translations_dict.get(i, "") for i in range(1, num_src + 1)
                    ]

                    translations.extend(ordered_translations)
                    self.logger.info(
                        f"Successfully translated batch of {num_src}. Tokens used: {self.token_count_last}"
                    )
                    break

                except InvalidNumTranslations as e:
                    mismatch_retry_attempt += 1
                    self.logger.warning(
                        f"Translation structure mismatch: {e}. Attempt {mismatch_retry_attempt}/{self.invalid_repeat_count}."
                    )
                    if mismatch_retry_attempt >= self.invalid_repeat_count:
                        self.logger.error(
                            "Fatal Error: Failed to get correct translation structure after retries."
                        )
                        translations.extend(["[ERROR: Structure Mismatch]"] * num_src)
                        break
                    time.sleep(self.retry_timeout / 2)

                except RETRYABLE_EXCEPTIONS as e:
                    api_retry_attempt += 1
                    self.logger.warning(
                        f"API Error (retryable): {type(e).__name__} - {e}. Attempt {api_retry_attempt}/{self.retry_attempts}."
                    )
                    if api_retry_attempt >= self.retry_attempts:
                        self.logger.error(
                            f"Fatal Error: Failed to connect to API after {self.retry_attempts} attempts."
                        )
                        translations.extend([f"[ERROR: API Failed]"] * num_src)
                        break
                    time.sleep(self.retry_timeout)

                except (
                    ValidationError,
                    json.JSONDecodeError,
                    openai.BadRequestError,
                    openai.AuthenticationError,
                    ValueError,
                ) as e:
                    self.logger.error(
                        f"Fatal Error: An unrecoverable error occurred: {type(e).__name__} - {e}"
                    )
                    self.logger.debug(traceback.format_exc())
                    translations.extend([f"[ERROR: {type(e).__name__}]"] * num_src)
                    break

        return translations

    def updateParam(self, param_key: str, param_content):
        if param_key == "provider":
            old_provider = self.get_param_value("provider")
            new_provider = param_content
            if old_provider != new_provider:
                configs = self.get_param_value("__provider_configs")
                # Save current keys to old provider
                configs[old_provider] = {
                    "apikey": self.get_param_value("apikey"),
                    "multiple_keys": self.get_param_value("multiple_keys")
                }
                # Restore keys for new provider
                if new_provider in configs:
                    new_config = configs[new_provider]
                    self.set_param_value("apikey", new_config.get("apikey", ""))
                    self.set_param_value("multiple_keys", new_config.get("multiple_keys", ""))
                else:
                    self.set_param_value("apikey", "")
                    self.set_param_value("multiple_keys", "")

                # Update model options based on provider
                self._update_model_options(new_provider)

        super().updateParam(param_key, param_content)

        if param_key in ["apikey", "multiple_keys"]:
            provider = self.provider
            configs = self.get_param_value("__provider_configs")
            if provider not in configs:
                configs[provider] = {}
            configs[provider][param_key] = param_content

        if param_key in ["proxy", "multiple_keys", "apikey", "provider", "endpoint", "vertex_location", "vertex_project", "vertex_credentials"]:
            self.client = None
