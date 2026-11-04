import re
import time
import json
import traceback
import os
import os.path as osp
import datetime
from typing import List, Dict, Optional, Type, Any

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
                "GGL: gemini-3.8-flash",
                "GGL: gemini-3.7-pro",
                "GGL: gemini-3.7-flash",
                "GGL: gemini-3.6-flash",
                "GGL: gemini-3.5-flash",
                "GGL: gemini-3.5-flash-lite",
                "GGL: gemini-2.5-pro",
                "GGL: gemini-2.5-flash",
                "GGL: gemini-2.5-flash-lite",
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
                "global",
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
            "GGL: gemini-3.8-flash", "GGL: gemini-3.7-pro", "GGL: gemini-3.7-flash", "GGL: gemini-3.6-flash",
            "GGL: gemini-3.5-flash", "GGL: gemini-3.5-flash-lite",
            "GGL: gemini-2.5-pro", "GGL: gemini-2.5-flash", "GGL: gemini-2.5-flash-lite",
            "VAI: gemini-3.8-flash", "VAI: gemini-3.7-pro", "VAI: gemini-3.7-flash", "VAI: gemini-3.6-flash",
            "VAI: gemini-3.5-flash", "VAI: gemini-3.5-flash-lite",
            "VAI: gemini-2.5-pro", "VAI: gemini-2.5-flash",
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
        batch_size = 25  # Split into batches of 25 to prevent output token truncation on dense pages

        for chunk_idx in range(0, len(queries), batch_size):
            chunk = queries[chunk_idx : chunk_idx + batch_size]
            input_elements = [
                {"id": i + 1, "source": query} for i, query in enumerate(chunk)
            ]
            input_json_str = json.dumps(input_elements, ensure_ascii=False, indent=2)

            prompt = (
                f"Please translate the following text snippets from {from_lang} to {to_lang}. "
                f"The input is provided as a JSON array. Respond with a JSON object in the specified format.\n\n"
                f"INPUT:\n{input_json_str}"
            )

            yield prompt, len(chunk)

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

    @staticmethod
    def _check_safety_refusal(text: str) -> Optional[str]:
        """Detect whether the response is an AI content safety / policy refusal message."""
        if not text:
            return None
        lower = text.lower()
        refusal_patterns = [
            "cannot fulfill this request",
            "unable to process or translate",
            "unable to fulfill this request",
            "sexually explicit content",
            "safety guidelines",
            "content policy",
            "violates our policies",
            "as an ai language model, i cannot",
            "as a responsible ai",
        ]
        for pat in refusal_patterns:
            if pat in lower:
                return text.strip()
        return None

    def _save_failed_response(
        self,
        prompt: str,
        raw_content: str,
        error_info: str,
        is_safety_refusal: bool = False
    ) -> str:
        """Save failed LLM response and prompt to a log file for diagnosis."""
        try:
            log_dir = osp.abspath("logs/llm_parse_errors")
            os.makedirs(log_dir, exist_ok=True)

            now = datetime.datetime.now()
            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            prefix = "safety_refusal" if is_safety_refusal else "parse_error"
            model_name = self.override_model or self.model or "unknown"
            safe_model = re.sub(r'[^a-zA-Z0-9_]', '_', model_name)
            filename = f"{prefix}_{safe_model}_{timestamp_str}.txt"
            file_path = osp.join(log_dir, filename)

            report = [
                "=" * 80,
                f"LLM TRANSLATION {'SAFETY REFUSAL' if is_safety_refusal else 'PARSE ERROR'} REPORT",
                "=" * 80,
                f"Timestamp   : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Provider    : {self.provider}",
                f"Model       : {model_name}",
                f"Error Info  : {error_info}",
                "-" * 80,
                "PROMPT SENT TO LLM:",
                "-" * 80,
                prompt or "(No prompt recorded)",
                "-" * 80,
                "RAW LLM RESPONSE:",
                "-" * 80,
                raw_content or "(Empty response)",
                "=" * 80,
            ]

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report))

            return file_path
        except Exception as e:
            self.logger.error(f"Failed to save error report to file: {e}")
            return ""

    @staticmethod
    def _extract_json_text(text: str) -> str:
        """Extract JSON substring from raw response, supporting both objects and arrays."""
        cleaned = text.strip()

        # 1. Look for markdown code blocks (supports object {} or array [])
        # Handles case where closing ``` is missing (truncated output)
        match = re.search(r"```(?:json)?\s*([\{\[].*?)(?:```|$)", cleaned, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 2. Find boundary of first { or [ and last } or ]
        brace_idx = cleaned.find("{")
        bracket_idx = cleaned.find("[")

        start_idx = -1
        if brace_idx != -1 and bracket_idx != -1:
            start_idx = min(brace_idx, bracket_idx)
        elif brace_idx != -1:
            start_idx = brace_idx
        elif bracket_idx != -1:
            start_idx = bracket_idx

        rbrace_idx = cleaned.rfind("}")
        rbracket_idx = cleaned.rfind("]")
        end_idx = max(rbrace_idx, rbracket_idx)

        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            return cleaned[start_idx : end_idx + 1].strip()

        return cleaned

    @staticmethod
    def _repair_truncated_json(text: str) -> Optional[Any]:
        """Attempt to close open strings, brackets, and braces to salvage truncated JSON."""
        cleaned = text.strip()
        if not cleaned:
            return None

        in_string = False
        escape = False
        stack = []

        for char in cleaned:
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in ('{', '['):
                    stack.append(char)
                elif char == '}' and stack and stack[-1] == '{':
                    stack.pop()
                elif char == ']' and stack and stack[-1] == '[':
                    stack.pop()

        closing = ""
        if in_string:
            closing += '"'
        for char in reversed(stack):
            if char == '{':
                closing += '}'
            elif char == '[':
                closing += ']'

        repaired = cleaned + closing
        try:
            return json.loads(repaired, strict=False)
        except Exception:
            pass

        # Try removing trailing incomplete element if last attempt failed
        last_comma = cleaned.rfind(",")
        if last_comma != -1:
            sub = cleaned[:last_comma].strip()
            in_string = False
            escape = False
            stack = []
            for char in sub:
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if char in ('{', '['):
                        stack.append(char)
                    elif char == '}' and stack and stack[-1] == '{':
                        stack.pop()
                    elif char == ']' and stack and stack[-1] == '[':
                        stack.pop()
            closing = ""
            if in_string:
                closing += '"'
            for char in reversed(stack):
                if char == '{':
                    closing += '}'
                elif char == '[':
                    closing += ']'
            try:
                return json.loads(sub + closing, strict=False)
            except Exception:
                pass

        return None

    @staticmethod
    def _regex_fallback_extract(text: str) -> List[Dict[str, Any]]:
        """Last-resort fallback: regex extraction of id and translation pairs."""
        results = []
        # Pattern 1: id: 1 ... translation: "..."
        pattern = r'["\']?id["\']?\s*:\s*(\d+).*?["\']?translation["\']?\s*:\s*["\'](.*?)(?:["\']\s*\}|(?=["\']?\s*,?\s*["\']?id["\']?\s*:)|$)'
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            try:
                val = m[1].rstrip('"\', ')
                results.append({"id": int(m[0]), "translation": val})
            except Exception:
                pass

        # Pattern 2: "1": "translation"
        if not results:
            pattern_kv = r'["\'](\d+)["\']\s*:\s*["\'](.*?)["\'](?:\s*[,}\]])'
            matches_kv = re.findall(pattern_kv, text, re.DOTALL)
            for m in matches_kv:
                try:
                    results.append({"id": int(m[0]), "translation": m[1]})
                except Exception:
                    pass

        return results

    @staticmethod
    def _normalize_translation_data(parsed_data: Any) -> List[Dict[str, Any]]:
        """Normalize various JSON structures into standard list of dicts [{'id': ..., 'translation': ...}]."""
        fixed_translations = []

        if isinstance(parsed_data, dict):
            # Case 1: {"translations": [...]} or {"result": [...]} or {"items": [...]} or {"data": [...]}
            for key in ("translations", "result", "items", "data"):
                if key in parsed_data and isinstance(parsed_data[key], list):
                    fixed_translations = parsed_data[key]
                    break

            # Case 2: {"1": "...", "2": "..."}
            if not fixed_translations and all(k.isdigit() for k in parsed_data.keys()):
                fixed_translations = [
                    {"id": int(k), "translation": str(v)} for k, v in parsed_data.items()
                ]

            # Case 3: Single item {"id": 1, "translation": "..."}
            if not fixed_translations and "id" in parsed_data and "translation" in parsed_data:
                fixed_translations = [parsed_data]

        elif isinstance(parsed_data, list):
            # Case 4: [{"id": 1, "translation": "..."}, ...]
            if all(isinstance(item, dict) for item in parsed_data):
                fixed_translations = parsed_data
            # Case 5: ["translation 1", "translation 2", ...]
            elif all(isinstance(item, str) for item in parsed_data):
                fixed_translations = [
                    {"id": i + 1, "translation": item} for i, item in enumerate(parsed_data)
                ]

        return fixed_translations

    def _parse_and_validate_response(
        self,
        raw_content: str,
        prompt: str = "",
        candidate_info: Optional[dict] = None
    ) -> TranslationResponse:
        """Robustly parse and validate translation response from LLM."""
        raw_content_clean = raw_content.strip() if raw_content else ""

        # 1. Check for AI Safety Refusal
        is_safety = False
        refusal_reason = ""
        if candidate_info and candidate_info.get("finishReason") in ("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"):
            is_safety = True
            refusal_reason = f"Candidate finishReason: {candidate_info.get('finishReason')}"
        else:
            refusal_msg = self._check_safety_refusal(raw_content_clean)
            if refusal_msg:
                is_safety = True
                refusal_reason = refusal_msg

        if is_safety:
            error_msg = f"AI Safety Policy Refusal: {refusal_reason}"
            self.logger.error(error_msg)
            saved_file = self._save_failed_response(
                prompt=prompt,
                raw_content=raw_content,
                error_info=error_msg,
                is_safety_refusal=True
            )
            if saved_file:
                self.logger.error(f"Saved safety refusal response to: {saved_file}")
            raise ValueError(error_msg)

        if not raw_content_clean:
            error_msg = "Received empty response from AI model."
            saved_file = self._save_failed_response(
                prompt=prompt,
                raw_content=raw_content,
                error_info=error_msg,
                is_safety_refusal=False
            )
            raise ValueError(error_msg)

        # 2. Extract JSON text
        json_to_parse = self._extract_json_text(raw_content_clean)

        # 3. Attempt 1: Direct JSON parsing with strict=False (handles unescaped newlines/tabs)
        parsed_data = None
        try:
            parsed_data = json.loads(json_to_parse, strict=False)
        except Exception as e1:
            self.logger.warning(f"Initial JSON parse failed: {e1}. Attempting repair...")

            # 4. Attempt 2: Repair truncated / unclosed JSON
            repaired_data = self._repair_truncated_json(json_to_parse)
            if repaired_data is not None:
                parsed_data = repaired_data
                self.logger.info("Successfully repaired and parsed truncated JSON.")
            else:
                # 5. Attempt 3: Regex fallback extraction of (id, translation) pairs
                regex_translations = self._regex_fallback_extract(raw_content_clean)
                if regex_translations:
                    parsed_data = {"translations": regex_translations}
                    self.logger.info(f"Successfully extracted {len(regex_translations)} translations using regex fallback.")
                else:
                    error_msg = f"JSONDecodeError: {e1}"
                    saved_file = self._save_failed_response(
                        prompt=prompt,
                        raw_content=raw_content,
                        error_info=error_msg,
                        is_safety_refusal=False
                    )
                    self.logger.error(f"Failed to parse LLM response. Saved to: {saved_file}")
                    raise e1

        # 6. Normalize and validate data structure
        fixed_translations = self._normalize_translation_data(parsed_data)
        if not fixed_translations:
            error_msg = f"Could not find valid translations in response structure: {parsed_data}"
            saved_file = self._save_failed_response(
                prompt=prompt,
                raw_content=raw_content,
                error_info=error_msg,
                is_safety_refusal=False
            )
            raise ValueError(error_msg)

        return TranslationResponse.model_validate({"translations": fixed_translations})

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

        if vertex_location == "global":
            host = "aiplatform.googleapis.com"
        else:
            host = f"{vertex_location}-aiplatform.googleapis.com"

        url = (
            f"https://{host}/v1"
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

        # Extract text and candidate info from Gemini response
        text_content = ""
        candidate = None
        if "candidates" in data and data["candidates"]:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                for part in parts:
                    if "text" in part:
                        text_content += part["text"]

        # Extract usage info
        if "usageMetadata" in data:
            usage = data["usageMetadata"]
            total_tokens = usage.get("totalTokenCount", 0)
            self.token_count += total_tokens
            self.token_count_last = total_tokens
        else:
            self.token_count_last = 0

        # Parse & Validate response with full error recovery, safety check, and error logging
        return self._parse_and_validate_response(
            raw_content=text_content,
            prompt=prompt,
            candidate_info=candidate
        )

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
            choice = completion.choices[0]
            candidate_info = {"finishReason": getattr(choice, "finish_reason", "")}
            validated_response = self._parse_and_validate_response(
                raw_content=raw_content,
                prompt=prompt,
                candidate_info=candidate_info
            )
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
