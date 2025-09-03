"""LLM Client Manager for external LLM API integration with OAuth support."""

import logging
import asyncio
import json
from typing import Dict, Any, Optional, List, Union, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import httpx

from .oauth_manager import OAuthManager
from .credential_manager import CredentialManager
from .auth_detector import AuthDetector

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    COHERE = "cohere"
    REPLICATE = "replicate"
    HUGGINGFACE = "huggingface"
    MISTRAL = "mistral"
    CUSTOM = "custom"


class AuthMethod(Enum):
    """Authentication methods for LLM APIs."""
    API_KEY = "api_key"
    OAUTH = "oauth"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    provider: LLMProvider
    name: str
    base_url: str
    auth_method: AuthMethod
    preferred_auth_method: Optional[AuthMethod] = None
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer"
    auth_config: Dict[str, Any] = field(default_factory=dict)
    model_mapping: Dict[str, str] = field(default_factory=dict)
    default_model: Optional[str] = None
    max_tokens: int = 4096
    timeout: int = 30
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider.value,
            "name": self.name,
            "base_url": self.base_url,
            "auth_method": self.auth_method.value,
            "preferred_auth_method": self.preferred_auth_method.value if self.preferred_auth_method else None,
            "api_key_header": self.api_key_header,
            "api_key_prefix": self.api_key_prefix,
            "auth_config": self.auth_config,
            "model_mapping": self.model_mapping,
            "default_model": self.default_model,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "rate_limit_requests": self.rate_limit_requests,
            "rate_limit_window": self.rate_limit_window,
            "enabled": self.enabled
        }


@dataclass
class LLMRequest:
    """Request to an LLM provider."""
    model: str
    messages: List[Dict[str, str]]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = False
    additional_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str
    usage: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class RateLimitInfo:
    """Rate limiting information."""
    requests_made: int = 0
    window_start: datetime = field(default_factory=datetime.now)
    
    def reset_if_needed(self, window_seconds: int):
        """Reset if window has passed."""
        if datetime.now() - self.window_start > timedelta(seconds=window_seconds):
            self.requests_made = 0
            self.window_start = datetime.now()
    
    def can_make_request(self, limit: int, window_seconds: int) -> bool:
        """Check if request can be made."""
        self.reset_if_needed(window_seconds)
        return self.requests_made < limit
    
    def record_request(self):
        """Record a request."""
        self.requests_made += 1


class LLMClient:
    """Client for a specific LLM provider."""
    
    def __init__(self, config: LLMConfig, oauth_manager: OAuthManager, credential_manager: CredentialManager, client_manager: 'LLMClientManager'):
        self.config = config
        self.oauth_manager = oauth_manager
        self.credential_manager = credential_manager
        self.client_manager = client_manager
        self.rate_limit = RateLimitInfo()
        
        # Create HTTP client
        self.client = httpx.AsyncClient(
            timeout=config.timeout,
            headers={"User-Agent": "Hive-MCP-Gateway/0.3.0"}
        )
        
        logger.info(f"Initialized LLM client for {config.name} ({config.provider.value})")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests."""
        headers = {}
        
        if self.config.auth_method == AuthMethod.API_KEY:
            # Get API key from credentials
            credentials = self.client_manager.get_llm_credentials(self.config.name)
            
            if not credentials or "api_key" not in credentials:
                raise ValueError(f"API key not found for {self.config.name}. Please configure.")
            
            headers[self.config.api_key_header] = f"{self.config.api_key_prefix} {credentials['api_key']}"
            
        elif self.config.auth_method == AuthMethod.OAUTH:
            # Get OAuth token
            credentials = self.client_manager.get_llm_credentials(self.config.name)
            
            if not credentials or "access_token" not in credentials:
                raise ValueError(f"OAuth token not available for {self.config.name}. Please authenticate.")
            
            headers["Authorization"] = f"Bearer {credentials['access_token']}"
            
        elif self.config.auth_method == AuthMethod.BEARER_TOKEN:
            # Get bearer token from credentials
            token_name = f"{self.config.name}_token"
            credential = self.credential_manager.get_credential(token_name)
            
            if not credential:
                raise ValueError(f"Bearer token not found for {self.config.name}. Please configure: {token_name}")
            
            headers["Authorization"] = f"Bearer {credential.value}"
            
        elif self.config.auth_method == AuthMethod.BASIC_AUTH:
            # Get username/password from credentials
            username_name = f"{self.config.name}_username"
            password_name = f"{self.config.name}_password"
            
            username_cred = self.credential_manager.get_credential(username_name)
            password_cred = self.credential_manager.get_credential(password_name)
            
            if not username_cred or not password_cred:
                raise ValueError(f"Username/password not found for {self.config.name}")
            
            import base64
            credentials = base64.b64encode(f"{username_cred.value}:{password_cred.value}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        
        return headers
    
    async def _check_rate_limit(self):
        """Check and enforce rate limits."""
        if not self.rate_limit.can_make_request(
            self.config.rate_limit_requests, 
            self.config.rate_limit_window
        ):
            wait_time = self.config.rate_limit_window - (datetime.now() - self.rate_limit.window_start).seconds
            raise ValueError(f"Rate limit exceeded for {self.config.name}. Try again in {wait_time} seconds.")
    
    def _map_model(self, model: str) -> str:
        """Map model name to provider-specific model."""
        return self.config.model_mapping.get(model, model)
    
    def _format_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Format request for the specific provider."""
        mapped_model = self._map_model(request.model)
        
        if self.config.provider == LLMProvider.OPENAI:
            return {
                "model": mapped_model,
                "messages": request.messages,
                "max_tokens": request.max_tokens or self.config.max_tokens,
                "temperature": request.temperature,
                "stream": request.stream,
                **request.additional_params
            }
        
        elif self.config.provider == LLMProvider.ANTHROPIC:
            # Convert OpenAI format to Anthropic format
            system_message = ""
            messages = []
            
            for msg in request.messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    messages.append(msg)
            
            payload = {
                "model": mapped_model,
                "messages": messages,
                "max_tokens": request.max_tokens or self.config.max_tokens,
                "stream": request.stream,
                **request.additional_params
            }
            
            if system_message:
                payload["system"] = system_message
            
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            
            return payload
        
        elif self.config.provider == LLMProvider.GOOGLE:
            # Convert to Google/Gemini format
            contents = []
            
            for msg in request.messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
            
            return {
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": request.max_tokens or self.config.max_tokens,
                    "temperature": request.temperature,
                    **request.additional_params
                }
            }
        
        else:
            # Generic format
            return {
                "model": mapped_model,
                "messages": request.messages,
                "max_tokens": request.max_tokens or self.config.max_tokens,
                "temperature": request.temperature,
                "stream": request.stream,
                **request.additional_params
            }
    
    def _get_endpoint(self, request: LLMRequest) -> str:
        """Get the appropriate endpoint for the request."""
        if self.config.provider == LLMProvider.OPENAI:
            return f"{self.config.base_url}/chat/completions"
        elif self.config.provider == LLMProvider.ANTHROPIC:
            return f"{self.config.base_url}/messages"
        elif self.config.provider == LLMProvider.GOOGLE:
            model = self._map_model(request.model)
            if request.stream:
                return f"{self.config.base_url}/models/{model}:streamGenerateContent"
            else:
                return f"{self.config.base_url}/models/{model}:generateContent"
        else:
            return f"{self.config.base_url}/chat/completions"
    
    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse response from provider into standard format."""
        if self.config.provider == LLMProvider.OPENAI:
            return LLMResponse(
                content=response_data["choices"][0]["message"]["content"],
                model=response_data["model"],
                provider=self.config.name,
                usage=response_data.get("usage", {}),
                metadata={"raw_response": response_data}
            )
        
        elif self.config.provider == LLMProvider.ANTHROPIC:
            return LLMResponse(
                content=response_data["content"][0]["text"],
                model=response_data["model"],
                provider=self.config.name,
                usage=response_data.get("usage", {}),
                metadata={"raw_response": response_data}
            )
        
        elif self.config.provider == LLMProvider.GOOGLE:
            content = response_data["candidates"][0]["content"]["parts"][0]["text"]
            return LLMResponse(
                content=content,
                model=self.config.default_model or "gemini",
                provider=self.config.name,
                usage=response_data.get("usageMetadata", {}),
                metadata={"raw_response": response_data}
            )
        
        else:
            # Generic parsing
            return LLMResponse(
                content=response_data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                model=response_data.get("model", self.config.default_model or "unknown"),
                provider=self.config.name,
                usage=response_data.get("usage", {}),
                metadata={"raw_response": response_data}
            )
    
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Complete a text generation request."""
        try:
            # Check rate limit
            await self._check_rate_limit()
            
            # Get authentication headers
            headers = await self._get_auth_headers()
            headers["Content-Type"] = "application/json"
            
            # Format request
            payload = self._format_request(request)
            endpoint = self._get_endpoint(request)
            
            logger.debug(f"Making request to {self.config.name}: {endpoint}")
            
            # Make request
            response = await self.client.post(
                endpoint,
                json=payload,
                headers=headers
            )
            
            # Record request for rate limiting
            self.rate_limit.record_request()
            
            # Check response
            response.raise_for_status()
            response_data = response.json()
            
            # Parse response
            llm_response = self._parse_response(response_data)
            
            logger.info(f"Completed request to {self.config.name} - tokens: {llm_response.usage}")
            return llm_response
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code} from {self.config.name}: {e.response.text}"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=request.model,
                provider=self.config.name,
                usage={},
                error=error_msg
            )
        
        except Exception as e:
            error_msg = f"Error calling {self.config.name}: {str(e)}"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=request.model,
                provider=self.config.name,
                usage={},
                error=error_msg
            )
    
    async def stream_complete(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Stream a text generation request."""
        try:
            # Check rate limit
            await self._check_rate_limit()
            
            # Get authentication headers
            headers = await self._get_auth_headers()
            headers["Content-Type"] = "application/json"
            
            # Format request with streaming
            request.stream = True
            payload = self._format_request(request)
            endpoint = self._get_endpoint(request)
            
            logger.debug(f"Making streaming request to {self.config.name}: {endpoint}")
            
            # Make streaming request
            async with self.client.stream("POST", endpoint, json=payload, headers=headers) as response:
                response.raise_for_status()
                
                # Record request for rate limiting
                self.rate_limit.record_request()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        
                        if data == "[DONE]":
                            break
                        
                        try:
                            chunk_data = json.loads(data)
                            
                            # Extract content based on provider
                            if self.config.provider == LLMProvider.OPENAI:
                                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                            elif self.config.provider == LLMProvider.ANTHROPIC:
                                if chunk_data.get("type") == "content_block_delta":
                                    content = chunk_data.get("delta", {}).get("text", "")
                                else:
                                    content = ""
                            else:
                                # Generic streaming format
                                content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            
                            if content:
                                yield content
                                
                        except json.JSONDecodeError:
                            continue
            
            logger.info(f"Completed streaming request to {self.config.name}")
            
        except Exception as e:
            error_msg = f"Streaming error from {self.config.name}: {str(e)}"
            logger.error(error_msg)
            yield f"[ERROR: {error_msg}]"
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class LLMClientManager:
    """Manager for multiple LLM clients with unified interface."""
    
    def __init__(self, oauth_manager: OAuthManager, credential_manager: CredentialManager):
        self.oauth_manager = oauth_manager
        self.credential_manager = credential_manager
        self.auth_detector = AuthDetector()
        
        self.clients: Dict[str, LLMClient] = {}
        self.configs: Dict[str, LLMConfig] = {}
        
        # Load default configurations
        self._load_default_configs()
        
        logger.info("Initialized LLM Client Manager")

    def get_llm_credentials(self, provider: str) -> Optional[Dict[str, Any]]:
        """Get LLM credentials with fallback strategy"""
        config = self.configs.get(provider)
        if not config:
            return None

        prefer_piggyback = config.preferred_auth_method == AuthMethod.OAUTH
        
        # First try piggybacking if preferred and available
        if prefer_piggyback:
            piggyback_creds = self._get_piggyback_credentials(provider)
            if piggyback_creds:
                return piggyback_creds
        
        # Fallback to direct API key configuration
        return self._get_direct_api_credentials(provider)

    def _get_piggyback_credentials(self, provider: str) -> Optional[Dict[str, Any]]:
        """Attempt to piggyback on existing desktop client credentials"""
        if provider == "claude_code":
            from .claude_code_sdk import ClaudeCodeSDK
            claude_sdk = ClaudeCodeSDK(self.credential_manager)
            credentials = claude_sdk.get_credentials()
            return credentials.to_dict() if credentials else None
        elif provider == "gemini_cli":
            from .gemini_cli_sdk import GeminiCLISDK
            gemini_sdk = GeminiCLISDK(self.credential_manager)
            credentials = gemini_sdk.get_credentials()
            return credentials.to_dict() if credentials else None
        return None

    def _get_direct_api_credentials(self, provider: str) -> Optional[Dict[str, Any]]:
        """Get directly configured API keys"""
        config = self.configs.get(provider)
        if config and config.auth_method == AuthMethod.API_KEY:
            api_key_name = f"{config.name}_api_key"
            credential = self.credential_manager.get_credential(api_key_name)
            if credential:
                return {"api_key": credential.value}
        return None
    
    def _load_default_configs(self):
        """Load default LLM provider configurations."""
        defaults = {
            "openai": LLMConfig(
                provider=LLMProvider.OPENAI,
                name="openai",
                base_url="https://api.openai.com/v1",
                auth_method=AuthMethod.API_KEY,
                api_key_header="Authorization",
                api_key_prefix="Bearer",
                model_mapping={
                    "gpt-4": "gpt-4",
                    "gpt-3.5": "gpt-3.5-turbo",
                    "gpt-4-turbo": "gpt-4-turbo-preview"
                },
                default_model="gpt-3.5-turbo"
            ),
            
            "anthropic": LLMConfig(
                provider=LLMProvider.ANTHROPIC,
                name="anthropic",
                base_url="https://api.anthropic.com/v1",
                auth_method=AuthMethod.API_KEY,
                api_key_header="x-api-key",
                api_key_prefix="",
                model_mapping={
                    "claude-3": "claude-3-sonnet-20240229",
                    "claude-3-opus": "claude-3-opus-20240229",
                    "claude-3-haiku": "claude-3-haiku-20240307"
                },
                default_model="claude-3-sonnet-20240229"
            ),
            
            "google": LLMConfig(
                provider=LLMProvider.GOOGLE,
                name="google",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                auth_method=AuthMethod.API_KEY,
                api_key_header="x-goog-api-key",
                api_key_prefix="",
                model_mapping={
                    "gemini-pro": "gemini-1.5-pro",
                    "gemini": "gemini-1.5-flash"
                },
                default_model="gemini-1.5-pro"
            )
        }
        
        for name, config in defaults.items():
            self.configs[name] = config
    
    def add_provider(self, config: LLMConfig) -> bool:
        """Add a new LLM provider configuration."""
        try:
            self.configs[config.name] = config
            
            # Initialize client if enabled
            if config.enabled:
                self.clients[config.name] = LLMClient(config, self.oauth_manager, self.credential_manager, self)
            
            logger.info(f"Added LLM provider: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add LLM provider {config.name}: {e}")
            return False
    
    def remove_provider(self, name: str) -> bool:
        """Remove an LLM provider."""
        try:
            if name in self.clients:
                asyncio.create_task(self.clients[name].close())
                del self.clients[name]
            
            if name in self.configs:
                del self.configs[name]
            
            logger.info(f"Removed LLM provider: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove LLM provider {name}: {e}")
            return False
    
    def get_provider(self, name: str) -> Optional[LLMClient]:
        """Get an LLM client by name."""
        return self.clients.get(name)
    
    def get_client(self, name: str) -> Optional[LLMClient]:
        """Alias for get_provider for GUI compatibility."""
        return self.get_provider(name)
    
    def get_all_configs(self) -> List[LLMConfig]:
        """Get all LLM provider configurations."""
        return list(self.configs.values())
    
    def update_provider(self, old_name: str, new_config: LLMConfig) -> bool:
        """Update an existing LLM provider configuration."""
        try:
            # Remove old configuration
            if old_name in self.clients:
                asyncio.create_task(self.clients[old_name].close())
                del self.clients[old_name]
            
            if old_name in self.configs:
                del self.configs[old_name]
            
            # Add new configuration
            self.configs[new_config.name] = new_config
            
            # Initialize client if enabled
            if new_config.enabled:
                self.clients[new_config.name] = LLMClient(new_config, self.oauth_manager, self.credential_manager, self)
            
            logger.info(f"Updated LLM provider: {old_name} -> {new_config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update LLM provider {old_name}: {e}")
            return False
    
    def list_providers(self) -> List[str]:
        """List available LLM providers."""
        return list(self.configs.keys())
    
    def list_enabled_providers(self) -> List[str]:
        """List enabled LLM providers."""
        return [name for name, config in self.configs.items() if config.enabled]
    
    def get_provider_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get provider information."""
        config = self.configs.get(name)
        if not config:
            return None
        
        client = self.clients.get(name)
        
        return {
            "name": config.name,
            "provider": config.provider.value,
            "auth_method": config.auth_method.value,
            "enabled": config.enabled,
            "available": client is not None,
            "models": list(config.model_mapping.keys()) or [config.default_model],
            "default_model": config.default_model,
            "max_tokens": config.max_tokens,
            "rate_limit": {
                "requests": config.rate_limit_requests,
                "window": config.rate_limit_window
            }
        }
    
    async def complete(self, provider_name: str, request: LLMRequest) -> LLMResponse:
        """Complete a request using a specific provider."""
        client = self.get_provider(provider_name)
        if not client:
            # Record auth failure for monitoring
            self.auth_detector.analyze_error(
                provider_name, 
                f"Provider {provider_name} not available or not configured"
            )
            
            return LLMResponse(
                content="",
                model=request.model,
                provider=provider_name,
                usage={},
                error=f"Provider {provider_name} not available"
            )
        
        try:
            response = await client.complete(request)
            
            # Record success if no error
            if not response.error:
                self.auth_detector.record_success(provider_name, {
                    "model": response.model,
                    "usage": response.usage
                })
            else:
                # Analyze authentication errors
                self.auth_detector.analyze_error(provider_name, response.error)
            
            return response
            
        except Exception as e:
            error_msg = f"Error completing request with {provider_name}: {str(e)}"
            logger.error(error_msg)
            
            # Record failure
            self.auth_detector.analyze_error(provider_name, error_msg)
            
            return LLMResponse(
                content="",
                model=request.model,
                provider=provider_name,
                usage={},
                error=error_msg
            )
    
    async def stream_complete(self, provider_name: str, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Stream complete a request using a specific provider."""
        client = self.get_provider(provider_name)
        if not client:
            yield f"[ERROR: Provider {provider_name} not available]"
            return
        
        try:
            async for chunk in client.stream_complete(request):
                yield chunk
                
        except Exception as e:
            error_msg = f"Error streaming with {provider_name}: {str(e)}"
            logger.error(error_msg)
            
            # Record failure
            self.auth_detector.analyze_error(provider_name, error_msg)
            
            yield f"[ERROR: {error_msg}]"
    
    def get_auth_requirements(self) -> Dict[str, Dict[str, Any]]:
        """Get authentication requirements for all providers."""
        requirements = {}
        
        for name, config in self.configs.items():
            auth_info = self.auth_detector.get_server_auth_info(name)
            
            requirements[name] = {
                "auth_method": config.auth_method.value,
                "required_credentials": self._get_required_credentials(config),
                "auth_status": auth_info.auth_status.value if auth_info else "unknown",
                "oauth_url": auth_info.oauth_url if auth_info else None,
                "setup_instructions": self._get_setup_instructions(config)
            }
        
        return requirements
    
    def _get_required_credentials(self, config: LLMConfig) -> List[str]:
        """Get list of required credentials for a provider."""
        if config.auth_method == AuthMethod.API_KEY:
            return [f"{config.name}_api_key"]
        elif config.auth_method == AuthMethod.OAUTH:
            return []  # OAuth handled by OAuth manager
        elif config.auth_method == AuthMethod.BEARER_TOKEN:
            return [f"{config.name}_token"]
        elif config.auth_method == AuthMethod.BASIC_AUTH:
            return [f"{config.name}_username", f"{config.name}_password"]
        else:
            return []
    
    def _get_setup_instructions(self, config: LLMConfig) -> str:
        """Get setup instructions for a provider."""
        if config.auth_method == AuthMethod.API_KEY:
            return f"Configure API key in credentials manager as '{config.name}_api_key'"
        elif config.auth_method == AuthMethod.OAUTH:
            return f"Complete OAuth authentication for {config.name}"
        elif config.auth_method == AuthMethod.BEARER_TOKEN:
            return f"Configure bearer token in credentials manager as '{config.name}_token'"
        elif config.auth_method == AuthMethod.BASIC_AUTH:
            return f"Configure username and password in credentials manager as '{config.name}_username' and '{config.name}_password'"
        else:
            return "Custom authentication - check provider documentation"
    
    async def test_provider(self, name: str) -> Dict[str, Any]:
        """Test a provider with a simple request."""
        try:
            test_request = LLMRequest(
                model=self.configs[name].default_model or "default",
                messages=[{"role": "user", "content": "Hello! This is a test. Please respond with 'Test successful'."}],
                max_tokens=50
            )
            
            response = await self.complete(name, test_request)
            
            return {
                "success": not bool(response.error),
                "response": response.content[:100] if response.content else None,
                "error": response.error,
                "usage": response.usage
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": None,
                "error": str(e),
                "usage": {}
            }
    
    async def close_all(self):
        """Close all LLM clients."""
        for client in self.clients.values():
            await client.close()
        
        self.clients.clear()
        logger.info("Closed all LLM clients")