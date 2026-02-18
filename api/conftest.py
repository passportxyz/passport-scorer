import pytest


@pytest.fixture(autouse=True)
def enable_v2_api(settings):
    settings.FF_V2_API = "on"


@pytest.fixture(autouse=True)
def enable_multi_nullifier(settings):
    settings.FF_MULTI_NULLIFIER = "on"


# Test RSA keys for SIWE JWT signing (RS256)
# These are only used for testing - NOT production keys
TEST_SIWE_JWT_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC8Xqih4D89gZ/M
1UO68ucszoqYGxpeSPc5F+xCRfsA+yQhw24kUqL87Uey6v6yg21pJAxGuWCxzKMl
Yef2DdVusybG9t9wiuEdwrro+02hp3b5osZeeybuw0IS2efWYZ/oHmMgsskSID4h
NtpStz/2+/yrBEbRUVXGNkS4ISJu1QCG+oN4Y6toNxC6PKxqGjhDXaBnR/iOiUvS
X4vnmPG/wpF4fxiN7eLZ1BkFC27c0dwF9uCVMtOZVHJHIWKFuOHOsj4o1hi77Zm4
bBLHxPne4K83H+09dyQR3e6KqMhpyVRN34yS9Z14YXxUrO7grXQDO2NnOoUU83LO
1MyLZOKRAgMBAAECggEAH1+2v4ttjQ1/c6rbppIZfeWCwPXWrPiDML+yypEETvQF
XxhBSox2+CB/LiYkuM/aE8Z8wvTSTZrTW4EUlO9V6qOtJDtvGLwQ5ZeO8QoWMoQF
dWuulYL2h5L++MvRaOwGqa8R/Jq6kanMH1UXBOrfnP/4Y/WI5Akje6mDRZXDOek4
D0w8W76u6hDYxTvGw/deZ52nNZLbbktHp6sjpS1llOTPm+ZeHbYr42iUj9HEHNiy
3L8BbNffJU4vLduVRt0qLPB/hPjdAapeg+5DTTDAVW+lOukHFyCylYWKU4cjLv9Y
IDPY281w9VhNUKOZwH0j0vlX3AWXIwjC4afyVnbViQKBgQDds3KE3XjYIB4XeHbi
Np4kg9xUrOQVdNmD4bhmhGPzukTye2Yuk9HoO/Yp78FoDzJP8+iUjNf693qIdPuv
42WzwBPVE1tzO6jF3d/LUV7GVEiWWdKfki5xWE+abKRvvQ09YO6gYbhcbtStlCmP
6w69cUzZTfFSB0UYvysIAxwNnQKBgQDZgx220Pmn0U10DerMbGbU9AzGNJoEKlVQ
DNMc4+Faa0RcWqPENEoGwGztR5aCDqaaALot4DJR5CgSCqadexbws7AYTRaw1wAk
Oz/aO1T2gDd6o2QHe4/0bEaZ+1e9adiv/V7YSf+dHky7B43PXfbjgMuoPSiGnPgH
8V21y1gQhQKBgGwtJVHjZxW+BjDZnNigYeXbWWUPv3Mgwwnw17NeIg9I8l+HCsLr
ad7xcxnfXPXThG8yymfBmZlhrC5tNmoKgROGQ6cSfOrrT1zM+GgS2jXX5ltGlNk7
0OGJf74QCORk0NMEOyuSwwyHH8taojURMu4JHMBjob6uwW5jyTFtowCZAoGBAKu+
hqDKQsZKUnDXaFT/JvbwuIFsGUw+rNwnNC50lISTfAe8HeEXNHg+SgPU6bdJoCyr
dFYy1yioESelt0dTYJqwFtQpUkhRizAQhGtpO73jIWs5RgtOei0RrXF57x6FS+4y
DkiTrTw/J3DqFwPservJ/4SYvb4EhSeoYkjgBWoNAoGAbX/K2Nnj3nHqdsvhPhoZ
MYacwEmmfcdzI5QFQp56Uc8t5ySr6vgKcA5Ed4oVmHoLEo22Uvv5ZmPmvBvoRDrR
QsLn5zaAu9dw3GV7QMqm/Aq9tC4z3GFN341KBnNTQuarNEzZvSDRV2lfdtgU7mfG
FvzBat5ZWMlA2s2xE+j5D3A=
-----END PRIVATE KEY-----"""

TEST_SIWE_JWT_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvF6ooeA/PYGfzNVDuvLn
LM6KmBsaXkj3ORfsQkX7APskIcNuJFKi/O1Hsur+soNtaSQMRrlgscyjJWHn9g3V
brMmxvbfcIrhHcK66PtNoad2+aLGXnsm7sNCEtnn1mGf6B5jILLJEiA+ITbaUrc/
9vv8qwRG0VFVxjZEuCEibtUAhvqDeGOraDcQujysaho4Q12gZ0f4jolL0l+L55jx
v8KReH8Yje3i2dQZBQtu3NHcBfbglTLTmVRyRyFihbjhzrI+KNYYu+2ZuGwSx8T5
3uCvNx/tPXckEd3uiqjIaclUTd+MkvWdeGF8VKzu4K10AztjZzqFFPNyztTMi2Ti
kQIDAQAB
-----END PUBLIC KEY-----"""


@pytest.fixture(autouse=True)
def setup_siwe_jwt_keys(settings):
    """Setup test RSA keys for SIWE JWT signing"""
    settings.SIWE_JWT_PRIVATE_KEY = TEST_SIWE_JWT_PRIVATE_KEY
    settings.SIWE_JWT_PUBLIC_KEY = TEST_SIWE_JWT_PUBLIC_KEY


@pytest.fixture(autouse=True)
def setup_alchemy_api_key(settings):
    """Setup test Alchemy API key for ERC-6492 verification"""
    settings.ALCHEMY_API_KEY = "test-alchemy-key"


@pytest.fixture(autouse=True)
def enable_api_analytics(settings):
    """Enable API analytics tracking for tests"""
    settings.FF_API_ANALYTICS = "on"


@pytest.fixture(autouse=True)
def siwe_domain_settings(settings):
    """Set default SIWE allowed domains for tests.

    Ceramic cache tests use 'app.passport.xyz' (see create_siwe_message in test_authenticate_v2.py).
    Account tests use 'localhost' (see authenticate.py SIWE messages).
    Without this, the default empty allowlist rejects all domains and breaks existing tests.
    """
    settings.SIWE_ALLOWED_DOMAINS_CERAMIC_CACHE = ["app.passport.xyz"]
    settings.SIWE_ALLOWED_DOMAINS_ACCOUNT = ["localhost", "localhost:3000"]
