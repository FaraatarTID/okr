import { beforeAll, describe, expect, it } from "vitest";
import { exportJWK, generateKeyPair, SignJWT, type JWK } from "jose";
import { createOidcTokenVerifier } from "../src/oidc-token-verifier.js";

const ISSUER = "https://issuer.test";
const AUDIENCE = "spa-client-test";
const NONCE = "nonce-value-for-this-authentication";
const NOW = new Date("2026-09-23T12:00:00.000Z");

let rsaPrivate: CryptoKey;
let rsaPublicJwk: JWK;
let rsaPrivateJwk: JWK;
let psPrivate: CryptoKey;
let psPublicJwk: JWK;
let ecPrivate: CryptoKey;
let ecPublicJwk: JWK;

beforeAll(async () => {
  const rsa = await generateKeyPair("RS256", { modulusLength: 2048, extractable: true });
  rsaPrivate = rsa.privateKey;
  rsaPublicJwk = { ...(await exportJWK(rsa.publicKey)), kid: "rsa-key", alg: "RS256", use: "sig", key_ops: ["verify"] };
  rsaPrivateJwk = { ...(await exportJWK(rsa.privateKey)), kid: "rsa-key", alg: "RS256", use: "sig", key_ops: ["verify"] };

  const ps = await generateKeyPair("PS256", { modulusLength: 2048 });
  psPrivate = ps.privateKey;
  psPublicJwk = { ...(await exportJWK(ps.publicKey)), kid: "ps-key", alg: "PS256", use: "sig", key_ops: ["verify"] };

  const ec = await generateKeyPair("ES256");
  ecPrivate = ec.privateKey;
  ecPublicJwk = { ...(await exportJWK(ec.publicKey)), kid: "ec-key", alg: "ES256", use: "sig", key_ops: ["verify"] };
});

async function signedToken(options: {
  privateKey?: CryptoKey;
  kid?: string;
  alg?: string;
  issuer?: string;
  audience?: string | string[];
  nonce?: string;
  includeNonce?: boolean;
  includeSubject?: boolean;
  azp?: string;
  issuedAt?: number;
  expiresAt?: number;
  subject?: string;
} = {}): Promise<string> {
  const privateKey = options.privateKey ?? rsaPrivate;
  const alg = options.alg ?? "RS256";
  const claims: Record<string, unknown> = options.includeNonce === false ? {} : { nonce: options.nonce ?? NONCE };
  if (options.includeSubject !== false) claims.sub = options.subject ?? "user-123";
  if (options.azp !== undefined) claims.azp = options.azp;
  return new SignJWT(claims)
    .setProtectedHeader({ alg, kid: options.kid ?? "rsa-key" })
    .setIssuer(options.issuer ?? ISSUER)
    .setAudience(options.audience ?? AUDIENCE)
    .setIssuedAt(options.issuedAt ?? Math.floor(NOW.getTime() / 1000) - 5)
    .setExpirationTime(options.expiresAt ?? Math.floor(NOW.getTime() / 1000) + 300)
    .sign(privateKey);
}

function verifierFor(keys: JWK[], now = NOW, fetcher?: () => Promise<{ keys: JWK[] }>) {
  let calls = 0;
  const verifier = createOidcTokenVerifier({
    issuer: ISSUER,
    audience: AUDIENCE,
    fetchJwks: fetcher ?? (async () => {
      calls += 1;
      return { keys };
    }),
    now: () => now,
    cacheTtlMs: 60_000,
    unknownKidRefreshCooldownMs: 30_000,
  });
  return { verifier, calls: () => calls };
}

describe("createOidcTokenVerifier", () => {
  it("verifies RS256 and ES256 signatures and only returns claims after verification", async () => {
    const { verifier } = verifierFor([rsaPublicJwk, ecPublicJwk]);
    const rsa = await verifier.verify(await signedToken(), NONCE);
    const ec = await verifier.verify(await signedToken({
      privateKey: ecPrivate,
      kid: "ec-key",
      alg: "ES256",
      subject: "ec-user",
    }), NONCE);

    expect(rsa.sub).toBe("user-123");
    expect(ec.sub).toBe("ec-user");
  });

  it("verifies PS256 with a generated RSA fixture", async () => {
    const token = await signedToken({ privateKey: psPrivate, alg: "PS256", kid: "ps-key" });
    const { verifier } = verifierFor([psPublicJwk]);
    await expect(verifier.verify(token, NONCE)).resolves.toMatchObject({ sub: "user-123" });
  });

  it.each([
    ["malformed compact token", "not.a.valid.token"],
    ["missing token segments", "one.two"],
  ])("rejects %s", async (_label, token) => {
    const { verifier } = verifierFor([rsaPublicJwk]);
    await expect(verifier.verify(token, NONCE)).rejects.toThrow();
  });

  it("rejects unsecured, HMAC, and unsupported algorithms", async () => {
    const { verifier } = verifierFor([rsaPublicJwk]);
    const none = `${Buffer.from(JSON.stringify({ alg: "none", kid: "rsa-key" })).toString("base64url")}.${Buffer.from("{}").toString("base64url")}.`;
    const hs = await new SignJWT({ nonce: NONCE })
      .setProtectedHeader({ alg: "HS256", kid: "rsa-key" })
      .setIssuer(ISSUER).setAudience(AUDIENCE).setIssuedAt(Math.floor(NOW.getTime() / 1000) - 5)
      .setExpirationTime(Math.floor(NOW.getTime() / 1000) + 300).sign(new Uint8Array(32).fill(7));
    const supported = await signedToken();
    const [, supportedPayload, supportedSignature] = supported.split(".");
    const unsupported = `${Buffer.from(JSON.stringify({ alg: "RS384", kid: "rsa-key" })).toString("base64url")}.${supportedPayload}.${supportedSignature}`;

    for (const token of [none, hs, unsupported]) {
      await expect(verifier.verify(token, NONCE)).rejects.toThrow();
    }
  });

  it("rejects invalid signatures and a key with the wrong type", async () => {
    const { verifier } = verifierFor([rsaPublicJwk, ecPublicJwk]);
    const token = await signedToken();
    const [header, payload, signature] = token.split(".");
    const tampered = `${header}.${payload}.${signature!.startsWith("A") ? "B" : "A"}${signature!.slice(1)}`;
    await expect(verifier.verify(tampered, NONCE)).rejects.toThrow();

    const wrongType = { ...ecPublicJwk, kid: "rsa-key", alg: "RS256" };
    const wrongTypeVerifier = verifierFor([wrongType]).verifier;
    await expect(wrongTypeVerifier.verify(token, NONCE)).rejects.toThrow();
  });

  it("rejects unknown and ambiguous signing keys", async () => {
    const unknown = verifierFor([rsaPublicJwk]).verifier;
    await expect(unknown.verify(await signedToken({ kid: "missing-key" }), NONCE)).rejects.toThrow();

    const ambiguous = verifierFor([rsaPublicJwk, { ...rsaPublicJwk }]).verifier;
    await expect(ambiguous.verify(await signedToken(), NONCE)).rejects.toThrow();
  });

  it("rejects private, encryption-only, and signing-only JWKS entries", async () => {
    const token = await signedToken();
    const privateJwk = { ...rsaPrivateJwk };
    delete privateJwk.key_ops;
    for (const key of [
      privateJwk,
      { ...rsaPublicJwk, use: "enc" },
      { ...rsaPublicJwk, key_ops: ["sign"] },
    ] as JWK[]) {
      const { verifier } = verifierFor([key]);
      await expect(verifier.verify(token, NONCE)).rejects.toThrow();
    }
  });

  it("requires exact issuer and configured audience", async () => {
    const { verifier } = verifierFor([rsaPublicJwk]);
    await expect(verifier.verify(await signedToken({ issuer: `${ISSUER}/other` }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ audience: "another-client" }), NONCE)).rejects.toThrow();
  });

  it("requires a non-empty subject and validates multi-audience authorized party", async () => {
    const { verifier } = verifierFor([rsaPublicJwk]);
    await expect(verifier.verify(await signedToken({ includeSubject: false }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ subject: "" }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ subject: "s".repeat(256) }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ subject: "é" }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ subject: "s".repeat(255) }), NONCE)).resolves.toMatchObject({
      sub: "s".repeat(255),
    });
    await expect(verifier.verify(await signedToken({ audience: [AUDIENCE, "other-client"] }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({
      audience: [AUDIENCE, "other-client"],
      azp: "other-client",
    }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({
      audience: [AUDIENCE, "other-client"],
      azp: AUDIENCE,
    }), NONCE)).resolves.toMatchObject({ sub: "user-123", aud: [AUDIENCE, "other-client"] });
  });

  it("requires expiry and issued-at claims and rejects expired or future-issued tokens outside 60 seconds", async () => {
    const { verifier } = verifierFor([rsaPublicJwk]);
    await expect(verifier.verify(await signedToken({ expiresAt: Math.floor(NOW.getTime() / 1000) - 61 }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ expiresAt: Math.floor(NOW.getTime() / 1000) - 30 }), NONCE)).resolves.toMatchObject({ sub: "user-123" });
    await expect(verifier.verify(await signedToken({ issuedAt: Math.floor(NOW.getTime() / 1000) + 61 }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ issuedAt: Math.floor(NOW.getTime() / 1000) + 30 }), NONCE)).resolves.toMatchObject({ sub: "user-123" });
  });

  it("fails closed for missing, mismatched, or absent expected nonce", async () => {
    const { verifier } = verifierFor([rsaPublicJwk]);
    await expect(verifier.verify(await signedToken({ includeNonce: false }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken({ nonce: "different" }), NONCE)).rejects.toThrow();
    await expect(verifier.verify(await signedToken(), "")).rejects.toThrow();
  });

  it("caches JWKS until TTL expiry and refreshes once for an unknown kid", async () => {
    let now = NOW;
    let calls = 0;
    const rotatedRsa = await generateKeyPair("RS256", { modulusLength: 2048 });
    const rotatedToken = await new SignJWT({ nonce: NONCE })
      .setProtectedHeader({ alg: "RS256", kid: "rotated-key" })
      .setIssuer(ISSUER).setAudience(AUDIENCE).setSubject("rotated-user")
      .setIssuedAt(Math.floor(NOW.getTime() / 1000) - 5)
      .setExpirationTime(Math.floor(NOW.getTime() / 1000) + 300).sign(rotatedRsa.privateKey);
    const rotatedJwk = { ...(await exportJWK(rotatedRsa.publicKey)), kid: "rotated-key", alg: "RS256", use: "sig" } as JWK;
    const verifier = createOidcTokenVerifier({
      issuer: ISSUER,
      audience: AUDIENCE,
      now: () => now,
      cacheTtlMs: 1_000,
      unknownKidRefreshCooldownMs: 30_000,
      fetchJwks: async () => {
        calls += 1;
        return { keys: calls === 1 ? [rsaPublicJwk] : [rsaPublicJwk, rotatedJwk] };
      },
    });

    await verifier.verify(await signedToken(), NONCE);
    await verifier.verify(await signedToken(), NONCE);
    expect(calls).toBe(1);
    await expect(verifier.verify(rotatedToken, NONCE)).resolves.toMatchObject({ sub: "rotated-user" });
    expect(calls).toBe(2);
    now = new Date(NOW.getTime() + 1_001);
    await verifier.verify(await signedToken(), NONCE);
    expect(calls).toBe(3);
  });

  it("coalesces simultaneous unknown-kid refreshes", async () => {
    let calls = 0;
    let releaseRefresh!: () => void;
    const refreshGate = new Promise<void>((resolve) => { releaseRefresh = resolve; });
    const verifier = createOidcTokenVerifier({
      issuer: ISSUER,
      audience: AUDIENCE,
      now: () => NOW,
      cacheTtlMs: 60_000,
      unknownKidRefreshCooldownMs: 30_000,
      fetchJwks: async () => {
        calls += 1;
        if (calls === 2) await refreshGate;
        return { keys: [rsaPublicJwk] };
      },
    });
    await verifier.verify(await signedToken(), NONCE);
    const unknown = await signedToken({ kid: "not-in-jwks" });
    const one = verifier.verify(unknown, NONCE);
    const two = verifier.verify(unknown, NONCE);
    await Promise.resolve();
    releaseRefresh();
    await Promise.all([expect(one).rejects.toThrow(), expect(two).rejects.toThrow()]);
    expect(calls).toBe(2);
  });

  it("aborts a JWKS fetch that exceeds its configured timeout", async () => {
    let aborted = false;
    const verifier = createOidcTokenVerifier({
      issuer: ISSUER,
      audience: AUDIENCE,
      fetchTimeoutMs: 5,
      fetchJwks: (signal) => new Promise((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          aborted = true;
          reject(new Error("aborted"));
        }, { once: true });
      }),
    });
    const finished = verifier.verify(await signedToken(), NONCE).then(() => true, () => true);
    const settled = await Promise.race([
      finished,
      new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 100)),
    ]);

    expect(settled).toBe(true);
    expect(aborted).toBe(true);
  });

  it("rejects a JWKS cache TTL outside the bounded range", () => {
    expect(() => createOidcTokenVerifier({
      issuer: ISSUER,
      audience: AUDIENCE,
      fetchJwks: async () => ({ keys: [] }),
      cacheTtlMs: 300_001,
    })).toThrow();
  });
});
