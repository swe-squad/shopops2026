import asyncio

import pytest


def test_fixture_auth():
    from app.auth.fixture import FixtureAuthenticator

    auth = FixtureAuthenticator()
    identity = asyncio.run(auth.authenticate("local-alice"))
    assert identity.user_id == "alice"
    assert identity.shop_ids == {"shop-a", "shop-b"}
    with pytest.raises(Exception, match="unauthorized"):
        asyncio.run(auth.authenticate("unknown"))


def test_fixture_cannot_start_in_production():
    from app.auth.fixture import FixtureAuthenticator

    with pytest.raises(ValueError):
        FixtureAuthenticator(app_env="production")


@pytest.fixture
def jwt_material():
    import time

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid="local", use="sig", alg="RS256")
    claims = dict(
        iss="issuer",
        aud="audience",
        exp=int(time.time()) + 60,
        tenant_id="tenant-a",
        sub="alice",
        shop_ids=["shop-a"],
        permissions=["history:read"],
    )
    return key, jwk, claims


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"iss": "wrong"},
        {"aud": "wrong"},
        {"exp": 1},
        {"shop_ids": "shop-a"},
        {"permissions": [1]},
        {"tenant_id": ""},
        {"sub": None},
    ],
)
def test_jwt_claims(jwt_material, change):
    import jwt

    from app.auth.dependencies import Unauthorized
    from app.auth.jwt import JWTAuthenticator

    key, jwk, claims = jwt_material
    claims.update(change)
    adapter = JWTAuthenticator(
        jwks_url="https://identity.example/jwks",
        issuer="issuer",
        audience="audience",
        jwks_loader=lambda: {"keys": [jwk]},
    )
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "local"})
    if change:
        with pytest.raises(Unauthorized):
            asyncio.run(adapter.authenticate(token))
    else:
        assert asyncio.run(adapter.authenticate(token)).user_id == "alice"


def test_jwt_signature_and_missing_claim(jwt_material):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.auth.dependencies import Unauthorized
    from app.auth.jwt import JWTAuthenticator

    key, jwk, claims = jwt_material
    adapter = JWTAuthenticator(
        jwks_url="https://identity.example/jwks",
        issuer="issuer",
        audience="audience",
        jwks_loader=lambda: {"keys": [jwk]},
    )
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for token in [
        jwt.encode(claims, other_key, algorithm="RS256", headers={"kid": "local"}),
        jwt.encode(
            {k: v for k, v in claims.items() if k != "exp"},
            key,
            algorithm="RS256",
            headers={"kid": "local"},
        ),
        jwt.encode(claims, "x" * 32, algorithm="HS256", headers={"kid": "local"}),
    ]:
        with pytest.raises(Unauthorized):
            asyncio.run(adapter.authenticate(token))
