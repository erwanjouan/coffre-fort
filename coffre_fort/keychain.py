"""macOS Keychain with Touch ID gate via LocalAuthentication."""

import ctypes
import ctypes.util
import subprocess
import sys

if sys.platform != "darwin":
    raise ImportError("keychain module requires macOS")

_CF  = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
_SEC = ctypes.CDLL(ctypes.util.find_library("Security"))

# --- CoreFoundation ---
_CF.CFStringCreateWithCString.restype = ctypes.c_void_p
_CF.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
_CF.CFDataCreate.restype = ctypes.c_void_p
_CF.CFDataCreate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_ssize_t]
_CF.CFDataGetLength.restype = ctypes.c_ssize_t
_CF.CFDataGetLength.argtypes = [ctypes.c_void_p]
_CF.CFDataGetBytePtr.restype = ctypes.c_char_p
_CF.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
_CF.CFDictionaryCreateMutable.restype = ctypes.c_void_p
_CF.CFDictionaryCreateMutable.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_void_p]
_CF.CFDictionarySetValue.restype = None
_CF.CFDictionarySetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_CF.CFRelease.restype = None
_CF.CFRelease.argtypes = [ctypes.c_void_p]

# --- Security ---
_SEC.SecItemAdd.restype = ctypes.c_int32
_SEC.SecItemAdd.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_SEC.SecItemDelete.restype = ctypes.c_int32
_SEC.SecItemDelete.argtypes = [ctypes.c_void_p]
_SEC.SecItemCopyMatching.restype = ctypes.c_int32
_SEC.SecItemCopyMatching.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]

kCFStringEncodingUTF8 = 0x08000100
errSecSuccess      = 0
errSecItemNotFound = -25300

_key_cbs = ctypes.addressof(ctypes.c_byte.in_dll(_CF, "kCFTypeDictionaryKeyCallBacks"))
_val_cbs = ctypes.addressof(ctypes.c_byte.in_dll(_CF, "kCFTypeDictionaryValueCallBacks"))


def _const(lib, name: str) -> int:
    """
    Read a named constant exported by a system library.

    macOS system libraries (CoreFoundation, Security) expose special constant
    values — like kSecClass or kCFBooleanTrue — as global variables in their
    compiled code.  ctypes lets us look them up by name and read their memory
    address, which is how we pass them to C functions without needing a C
    compiler.

    Args:
        lib:  The loaded library object (e.g. _CF or _SEC).
        name: The exact name of the constant as it appears in the library
              (e.g. "kSecClass").

    Returns:
        The integer memory address of that constant, which C functions treat
        as a pointer to the value.
    """
    return ctypes.c_void_p.in_dll(lib, name).value


_kCFBooleanTrue         = _const(_CF,  "kCFBooleanTrue")
_kSecClass              = _const(_SEC, "kSecClass")
_kSecClassGenericPassword = _const(_SEC, "kSecClassGenericPassword")
_kSecAttrService        = _const(_SEC, "kSecAttrService")
_kSecAttrAccount        = _const(_SEC, "kSecAttrAccount")
_kSecValueData          = _const(_SEC, "kSecValueData")
_kSecReturnData         = _const(_SEC, "kSecReturnData")

SERVICE = "coffre-fort"
ACCOUNT = "coffre-fort"

# Inline Swift script — calls LAContext.evaluatePolicy with biometrics, exits 0 on
# success or 1 on failure/cancel.  No entitlement is required to call LA directly.
_TOUCH_ID_SCRIPT = """\
import LocalAuthentication
import Foundation

let ctx = LAContext()
var canErr: NSError?
guard ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &canErr) else {
    let msg = canErr?.localizedDescription ?? "biometrics not available"
    fputs(msg + "\\n", stderr)
    exit(1)
}
let sem = DispatchSemaphore(value: 0)
var authOK = false
ctx.evaluatePolicy(
    .deviceOwnerAuthenticationWithBiometrics,
    localizedReason: "decrypt coffre-fort"
) { success, _ in
    authOK = success
    sem.signal()
}
sem.wait()
exit(authOK ? 0 : 1)
"""


def _cfstr(s: str) -> int:
    """
    Convert a Python string into a CoreFoundation CFString object.

    The macOS Security framework does not understand Python strings — it
    expects its own CFString type.  This function hands the text to
    CoreFoundation (the low-level Apple library that manages memory and
    basic types) and gets back an opaque reference (just a number that
    acts as a pointer) that we can pass to Security API calls.

    Important: every CFString created here must eventually be released with
    CFRelease() to avoid a memory leak.

    Args:
        s: The Python string to convert (e.g. a service name like "coffre-fort").

    Returns:
        An integer acting as a pointer to the new CFString object.

    Raises:
        MemoryError: If CoreFoundation could not allocate the object.
    """
    ref = _CF.CFStringCreateWithCString(None, s.encode("utf-8"), kCFStringEncodingUTF8)
    if not ref:
        raise MemoryError(f"CFStringCreateWithCString failed for {s!r}")
    return ref


def _cfdict(pairs) -> int:
    """
    Build a CoreFoundation CFDictionary from a list of key-value pairs.

    The Security framework takes its arguments as dictionaries — for example,
    "search for a Keychain item where class=GenericPassword AND service=coffre-fort".
    Python dicts cannot be passed directly to C functions, so we build a
    CFMutableDictionary (Apple's C-level dictionary type) instead.

    Like CFString objects, this dictionary must be released with CFRelease()
    when we are done with it.

    Args:
        pairs: A list of (key, value) tuples where each key and value is an
               integer pointer to a CoreFoundation object (CFString, CFData,
               or a system constant).

    Returns:
        An integer acting as a pointer to the new CFDictionary object.

    Raises:
        MemoryError: If CoreFoundation could not allocate the dictionary.
    """
    d = _CF.CFDictionaryCreateMutable(None, 0, _key_cbs, _val_cbs)
    if not d:
        raise MemoryError("CFDictionaryCreateMutable failed")
    for k, v in pairs:
        _CF.CFDictionarySetValue(d, k, v)
    return d


def _require_touch_id() -> None:
    """
    Show the Touch ID prompt and block until the user authenticates.

    This function runs a small Swift program on the fly (passed as text to the
    'swift -' command) that calls Apple's LocalAuthentication framework.  That
    framework is the same one used by apps like 1Password — it displays the
    "Touch ID" dialog and waits for a fingerprint scan.

    We use Swift here because Python has no direct binding to LocalAuthentication,
    but macOS ships with the Swift compiler so no installation is required.

    The Swift script exits with code 0 on success and code 1 on failure or
    cancellation.  We translate a non-zero exit into a Python exception so the
    caller never receives the password unless authentication succeeded.

    Raises:
        RuntimeError: If Touch ID is not available, the scan fails, or the
                      user cancels the prompt.
    """
    result = subprocess.run(
        ["swift", "-"],
        input=_TOUCH_ID_SCRIPT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or "authentication cancelled or denied"
        raise RuntimeError(f"Touch ID required: {msg}")


def get_password() -> bytes:
    """
    Authenticate with Touch ID and return the master password stored in the Keychain.

    This is the main function called every time a command needs the password
    (encrypt, decrypt, serve).  It has two steps:

    1. Touch ID — calls _require_touch_id() which shows the fingerprint prompt.
       If the scan fails or is cancelled, we stop here and raise an error.

    2. Keychain lookup — once authenticated, we call Apple's SecItemCopyMatching()
       to retrieve the password bytes that were saved earlier by store_password().
       The result comes back as a CFData object; we copy the raw bytes out of it
       and return them as a Python bytes value.

    Returns:
        The master password as raw bytes, ready to be passed to decrypt() or encrypt().

    Raises:
        RuntimeError: If Touch ID fails, or if no Keychain entry exists yet
                      (in which case the user needs to run 'coffre-fort keychain-store').
    """
    _require_touch_id()

    svc = _cfstr(SERVICE)
    acc = _cfstr(ACCOUNT)
    query = _cfdict([
        (_kSecClass,    _kSecClassGenericPassword),
        (_kSecAttrService, svc),
        (_kSecAttrAccount, acc),
        (_kSecReturnData,  _kCFBooleanTrue),
    ])
    result_ref = ctypes.c_void_p(0)
    status = _SEC.SecItemCopyMatching(query, ctypes.byref(result_ref))
    _CF.CFRelease(query)
    _CF.CFRelease(svc)
    _CF.CFRelease(acc)

    if status == errSecItemNotFound:
        raise RuntimeError(
            f"Keychain entry '{SERVICE}' not found — "
            "run 'coffre-fort keychain-store' to save the password first"
        )
    if status != errSecSuccess:
        raise RuntimeError(f"Keychain lookup failed (OSStatus {status})")

    length = _CF.CFDataGetLength(result_ref.value)
    ptr    = _CF.CFDataGetBytePtr(result_ref.value)
    data   = ctypes.string_at(ptr, length)
    _CF.CFRelease(result_ref.value)
    return data


def store_password(password: bytes) -> None:
    """Store the master password in the macOS Keychain.

    Every subsequent call to get_password() will require Touch ID before the
    secret is revealed.  The password is never written to disk in plaintext and
    never passed as a command-line argument.
    """
    svc  = _cfstr(SERVICE)
    acc  = _cfstr(ACCOUNT)
    blob = _CF.CFDataCreate(None, password, len(password))
    if not blob:
        raise MemoryError("CFDataCreate failed")

    try:
        del_q = _cfdict([
            (_kSecClass,       _kSecClassGenericPassword),
            (_kSecAttrService, svc),
            (_kSecAttrAccount, acc),
        ])
        _SEC.SecItemDelete(del_q)
        _CF.CFRelease(del_q)

        add_q = _cfdict([
            (_kSecClass,       _kSecClassGenericPassword),
            (_kSecAttrService, svc),
            (_kSecAttrAccount, acc),
            (_kSecValueData,   blob),
        ])
        status = _SEC.SecItemAdd(add_q, None)
        _CF.CFRelease(add_q)

        if status != errSecSuccess:
            raise RuntimeError(f"SecItemAdd failed (OSStatus {status})")
    finally:
        _CF.CFRelease(blob)
        _CF.CFRelease(svc)
        _CF.CFRelease(acc)
