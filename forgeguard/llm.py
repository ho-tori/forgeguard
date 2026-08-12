import json
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


class LLM:
    def complete(self, messages):
        raise NotImplementedError


class MockLLM(LLM):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages):
        self.calls.append(json.loads(json.dumps(messages)))
        if not self.responses:
            raise LLMError("Mock LLM has no scripted response remaining")
        response = self.responses.pop(0)
        if callable(response):
            return response(messages)
        return response


class OpenAICompatibleLLM(LLM):
    def __init__(self, endpoint, model, api_key_provider, timeout=60, max_output_chars=20000):
        self.endpoint = endpoint
        self.model = model
        self.api_key_provider = api_key_provider
        self.timeout = timeout
        self.max_output_chars = max_output_chars

    def complete(self, messages):
        key = self.api_key_provider()
        if not key:
            raise LLMError("No API key configured; run `forgeguard credential set`")
        body = json.dumps({"model": self.model, "messages": messages}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise LLMError("Provider returned a non-text response")
            if len(content) > self.max_output_chars:
                raise LLMError("Provider response exceeds configured limit")
            return content
        except urllib.error.HTTPError as exc:
            raise LLMError("Provider returned HTTP %s" % exc.code)
        except urllib.error.URLError as exc:
            raise LLMError("Provider request failed: %s" % exc.reason)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("Provider returned an invalid response: %s" % exc)
