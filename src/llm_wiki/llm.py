import os
from typing import Optional, Any
from pydantic import BaseModel

class LLMProvider:
    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        raise NotImplementedError

    def generate_structured(self, prompt: str, response_schema: type[BaseModel], system_instruction: Optional[str] = None) -> BaseModel:
        raise NotImplementedError

class GeminiProvider(LLMProvider):
    def __init__(self, client: Any, model: str):
        from google.genai import types
        self.client = client
        self.model = model
        self.types = types

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        config = self.types.GenerateContentConfig(temperature=0.2)
        if system_instruction:
            config.system_instruction = system_instruction
            
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )
        return response.text

    def generate_structured(self, prompt: str, response_schema: type[BaseModel], system_instruction: Optional[str] = None) -> BaseModel:
        config = self.types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        if system_instruction:
            config.system_instruction = system_instruction
            
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )
        return response_schema.model_validate_json(response.text)


class OpenAIProvider(LLMProvider):
    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content

    def generate_structured(self, prompt: str, response_schema: type[BaseModel], system_instruction: Optional[str] = None) -> BaseModel:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        return self.client.chat.completions.create(
            model=self.model,
            response_model=response_schema,
            messages=messages,
            temperature=0.1,
        )


class AnthropicProvider(LLMProvider):
    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if system_instruction:
            kwargs["system"] = system_instruction
            
        response = self.client.client.messages.create(**kwargs)
        return response.content[0].text

    def generate_structured(self, prompt: str, response_schema: type[BaseModel], system_instruction: Optional[str] = None) -> BaseModel:
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "response_model": response_schema,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        # instructor handles system prompt appropriately when passed as system parameter for anthropic
        if system_instruction:
            kwargs["system"] = system_instruction
            
        return self.client.messages.create(**kwargs)


class GroqProvider(LLMProvider):
    def __init__(self, client: Any, model: str):
        self.client = client
        self.model = model

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content

    def generate_structured(self, prompt: str, response_schema: type[BaseModel], system_instruction: Optional[str] = None) -> BaseModel:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        return self.client.chat.completions.create(
            model=self.model,
            response_model=response_schema,
            messages=messages,
            temperature=0.1,
        )


class LLMClient:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """Initialize the LLM client by detecting the provider."""
        provider = provider or os.environ.get("LLM_PROVIDER", "gemini").lower()
        model = model or os.environ.get("LLM_MODEL")
        
        print(f"Initializing LLMClient with provider: {provider}")

        if provider == "openai":
            import instructor
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            client = instructor.from_openai(OpenAI(api_key=api_key))
            self.provider_impl = OpenAIProvider(client, model or "gpt-4o-mini")
            
        elif provider == "anthropic":
            import instructor
            from anthropic import Anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            client = instructor.from_anthropic(Anthropic(api_key=api_key))
            self.provider_impl = AnthropicProvider(client, model or "claude-3-5-sonnet-latest")
            
        elif provider == "groq":
            import instructor
            from groq import Groq
            api_key = os.environ.get("GROQ_API_KEY")
            client = instructor.from_groq(Groq(api_key=api_key))
            self.provider_impl = GroqProvider(client, model or "llama-3.3-70b-versatile")
            
        else: # default to gemini
            from google import genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                print("Warning: GEMINI_API_KEY is not set.")
            client = genai.Client(api_key=api_key)
            self.provider_impl = GeminiProvider(client, model or "gemini-2.5-flash")

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate text from a prompt, optionally with system instructions."""
        return self.provider_impl.generate_text(prompt, system_instruction)

    def generate_structured(self, prompt: str, response_schema: type[BaseModel], system_instruction: Optional[str] = None) -> BaseModel:
        """Generate structured data adhering to a Pydantic schema."""
        return self.provider_impl.generate_structured(prompt, response_schema, system_instruction)
