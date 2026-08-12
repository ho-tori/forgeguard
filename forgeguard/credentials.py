import ctypes
import os
from ctypes import wintypes


TARGET_NAME = "ForgeGuard/OpenAICompatible"


class CredentialError(RuntimeError):
    pass


class InMemoryCredentialBackend:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value

    def get(self):
        return self.value

    def clear(self):
        self.value = None


class SecretFileBackend:
    def __init__(self, path):
        self.path = path

    def get(self):
        stat = os.stat(self.path)
        if os.name != "nt" and stat.st_mode & 0o077:
            raise PermissionError("Secret file must not be accessible by group or others (use chmod 600)")
        with open(self.path, "r", encoding="utf-8") as handle:
            value = handle.read().strip()
        if not value:
            raise CredentialError("Secret file is empty")
        return value


if os.name == "nt":
    LPBYTE = ctypes.POINTER(wintypes.BYTE)

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", LPBYTE),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]


class WindowsCredentialBackend:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    def __init__(self, target=TARGET_NAME):
        if os.name != "nt":
            raise CredentialError("Windows Credential Manager is unavailable on this platform")
        self.target = target
        self.advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self.advapi.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
        self.advapi.CredWriteW.restype = wintypes.BOOL
        self.advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
        self.advapi.CredReadW.restype = wintypes.BOOL
        self.advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.advapi.CredDeleteW.restype = wintypes.BOOL
        self.advapi.CredFree.argtypes = [ctypes.c_void_p]

    def set(self, value):
        blob = value.encode("utf-16-le")
        buffer = ctypes.create_string_buffer(blob)
        credential = CREDENTIALW()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = self.target
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(buffer, LPBYTE)
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "ForgeGuard"
        if not self.advapi.CredWriteW(ctypes.byref(credential), 0):
            raise CredentialError("Credential Manager write failed (%s)" % ctypes.get_last_error())

    def get(self):
        pointer = ctypes.POINTER(CREDENTIALW)()
        if not self.advapi.CredReadW(self.target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == 1168:
                return None
            raise CredentialError("Credential Manager read failed (%s)" % error)
        try:
            credential = pointer.contents
            blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return blob.decode("utf-16-le")
        finally:
            self.advapi.CredFree(pointer)

    def clear(self):
        if not self.advapi.CredDeleteW(self.target, self.CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()
            if error != 1168:
                raise CredentialError("Credential Manager delete failed (%s)" % error)


class UnavailableCredentialBackend:
    def set(self, value):
        raise CredentialError("No OS credential backend is available; use FORGEGUARD_API_KEY_FILE with mode 600")

    def get(self):
        return None

    def clear(self):
        return None


class CredentialManager:
    def __init__(self, backend=None, environ=None):
        self.backend = backend or (WindowsCredentialBackend() if os.name == "nt" else UnavailableCredentialBackend())
        self.environ = os.environ if environ is None else environ

    def set(self, value):
        if not isinstance(value, str) or len(value.strip()) < 8:
            raise CredentialError("Credential must contain at least 8 non-whitespace characters")
        self.backend.set(value.strip())

    def get_with_source(self):
        secret_path = self.environ.get("FORGEGUARD_API_KEY_FILE")
        if secret_path and os.path.isfile(secret_path):
            return SecretFileBackend(secret_path).get(), "secret_file"
        value = self.backend.get()
        if value:
            return value, "secure_store"
        environment_value = self.environ.get("FORGEGUARD_API_KEY")
        if environment_value:
            return environment_value, "environment"
        return None, None

    def get(self):
        return self.get_with_source()[0]

    def status(self):
        value, source = self.get_with_source()
        return {"configured": bool(value), "source": source}

    def clear(self):
        self.backend.clear()
