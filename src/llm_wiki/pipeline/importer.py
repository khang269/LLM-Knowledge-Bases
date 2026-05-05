from pathlib import Path
from datetime import datetime
from typing import Optional
from markitdown import MarkItDown
from ..config import WikiConfig
from ..llm import LLMClient
from ..storage import sanitize_filename, write_note

class MarkItDownVisionShim:
    """
    A shim to map MarkItDown's OpenAI-specific chat.completions.create calls
    into our tool-agnostic LLMClient based on the current provider.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    class Chat:
        def __init__(self, parent):
            self.parent = parent
            self.completions = self.Completions(parent)

        class Completions:
            def __init__(self, parent):
                self.parent = parent

            def create(self, model: str, messages: list, **kwargs):
                # Parse the specific OpenAI Vision format MarkItDown uses:
                # messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}]}]
                
                content_blocks = messages[0].get("content", [])
                text_prompt = ""
                b64_data = None
                mime_type = ""
                
                for block in content_blocks:
                    if block.get("type") == "text":
                        text_prompt = block.get("text", "")
                    elif block.get("type") == "image_url":
                        url_data = block.get("image_url", {}).get("url", "")
                        if url_data.startswith("data:"):
                            # Format: data:image/jpeg;base64,.....
                            mime_type = url_data.split(";")[0].replace("data:", "")
                            b64_data = url_data.split(",")[1]

                provider = self.parent.llm_client.provider_impl.__class__.__name__

                class MockResponse:
                    class Choice:
                        class Message:
                            def __init__(self, content):
                                self.content = content
                        def __init__(self, content):
                            self.message = self.Message(content)
                    def __init__(self, content):
                        self.choices = [self.Choice(content)]

                if not b64_data:
                    # Fallback to standard text generation if no image found
                    resp = self.parent.llm_client.generate_text(prompt=text_prompt)
                    return MockResponse(resp)

                # Route the base64 vision request to the specific provider
                if provider == "GeminiProvider":
                    from google.genai import types
                    import base64
                    raw_bytes = base64.b64decode(b64_data)
                    part = types.Part.from_bytes(data=raw_bytes, mime_type=mime_type)
                    
                    config = types.GenerateContentConfig(temperature=0.2)
                    response = self.parent.llm_client.provider_impl.client.models.generate_content(
                        model=model,
                        contents=[text_prompt, part],
                        config=config
                    )
                    return MockResponse(response.text)
                    
                elif provider == "AnthropicProvider":
                    resp = self.parent.llm_client.provider_impl.client.client.messages.create(
                        model=model,
                        temperature=0.2,
                        max_tokens=1024,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": text_prompt},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": mime_type,
                                        "data": b64_data
                                    }
                                }
                            ]
                        }]
                    )
                    return MockResponse(resp.content[0].text)
                    
                elif provider in ["OpenAIProvider", "GroqProvider"]:
                    # Pass the original message array straight through
                    resp = self.parent.llm_client.provider_impl.client.client.chat.completions.create(
                        model=model,
                        temperature=0.2,
                        messages=messages
                    )
                    return MockResponse(resp.choices[0].message.content)

                return MockResponse("[Image OCR failed: Unsupported provider]")

    @property
    def chat(self):
        return self.Chat(self)

def import_source(source: str, dest: str, config: WikiConfig, llm: LLMClient, subfolder: Optional[str] = None) -> Path:
    """
    Downloads/Reads a source (PDF, Web URL, YouTube) and converts it to Markdown using MarkItDown.
    Routes it to either wiki/raw/[subfolder] or wiki/daily/YYYY-MM-DD/.
    """
    shim = MarkItDownVisionShim(llm)
    md = MarkItDown(
        llm_client=shim,
        llm_model=llm.provider_impl.model,
        enable_plugins=True
    )
    
    print(f"Running MarkItDown conversion for: {source}")
    result = md.convert(source)
    content = result.text_content
    
    # Determine Title
    title = result.title if hasattr(result, 'title') and result.title else None
    if not title:
        if source.startswith("http"):
            title = source.split("/")[-1] or "Web Import"
        else:
            title = Path(source).stem
            
    safe_title = sanitize_filename(title)
    if not safe_title:
        safe_title = "Imported_Document"

    # Routing
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    
    if dest.lower() == "daily":
        target_dir = config.daily_dir / date_str
        tags = ["imported", "daily"]
    else:
        target_dir = config.raw_path
        if subfolder:
            target_dir = target_dir / subfolder
        tags = ["imported", "raw"]
        
    out_path = target_dir / f"{safe_title}.md"
    
    meta = {
        "title": title,
        "imported_from": source,
        "imported_at": now.strftime("%Y-%m-%d %H:%M"),
        "tags": tags
    }
    
    write_note(out_path, meta, content)
    print(f"Import saved to: {out_path}")
    return out_path
