"""Signed knowledge updates: with a public key in the package an update must carry a valid Ed25519 signature over the manifest."""
import base64
import json
import os

import pytest
from test_knowledge import URL, Remote, newer_spec

from device_bus_analyzer import cli, knowledge


@pytest.fixture(autouse=True)
def isolated(tmp_path):
    knowledge.configure(tmp_path / "knowledge")
    knowledge.MIN_INTERVAL = 0
    yield
    knowledge.MIN_INTERVAL = 60
    knowledge.configure(None)


class Signed(Remote):
    def __init__(self, priv_pem, **kw):
        super().__init__(**kw)
        from cryptography.hazmat.primitives import serialization as ser
        self.key = ser.load_pem_private_key(priv_pem, password=None)
        self.sign = True

    def __call__(self, url):
        if url == URL:
            self.calls.append(url)
            return json.dumps(self.manifest).encode()
        if url == URL + ".sig":
            if not self.sign:
                raise OSError("404")
            return base64.b64encode(self.key.sign(json.dumps(self.manifest).encode()))
        return super().__call__(url)


@pytest.fixture
def keys(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "PUBKEY", "knowledge-pubkey.test")                     # never touch the packaged key file
    priv = tmp_path / "k" / "signing.pem"
    pub = knowledge.generate_keypair(priv, write_public=False)
    monkeypatch.setattr(knowledge, "pubkey", lambda: pub)
    return priv.read_bytes(), pub


def test_valid_signature_is_accepted_and_reported(keys):
    r = Signed(keys[0], change=newer_spec)
    assert knowledge.update(URL, r)["status"] == "updated" and knowledge.info()["signed"] is True


def test_missing_wrong_or_tampered_signature_is_refused(keys, tmp_path):
    r = Signed(keys[0], change=newer_spec)
    r.sign = False
    assert "signature" in knowledge.update(URL, r)["message"]                              # unsigned manifest
    other = tmp_path / "other.pem"
    knowledge.generate_keypair(other, write_public=False)
    wrong = Signed(other.read_bytes(), change=newer_spec)
    assert "signature" in knowledge.update(URL, wrong)["message"]                          # signed by somebody else
    t = Signed(keys[0], change=newer_spec)
    good = t.__call__

    def tamper(url):
        out = good(url)
        return out.replace(b"2099", b"2098") if url == URL else out                        # manifest changed after signing
    assert "signature" in knowledge.update(URL, tamper)["message"]
    assert knowledge.info()["source"] == "bundled"                                         # nothing was activated


def test_without_a_packaged_key_updates_still_work_unsigned(monkeypatch):
    monkeypatch.setattr(knowledge, "pubkey", lambda: None)
    assert knowledge.update(URL, Remote(change=newer_spec))["status"] == "updated" and knowledge.info()["signed"] is False


def test_cli_keygen_and_sign_roundtrip(tmp_path, monkeypatch, capsys):
    pubfile = tmp_path / "pkg-pub.txt"
    mani = tmp_path / "m.json"
    mani.write_text('{"a": 1}\n')
    monkeypatch.setattr(knowledge, "write_manifest", lambda: {"version": "x"})
    pk = tmp_path / "priv.pem"
    pub = knowledge.generate_keypair(pk, write_public=False)
    with pytest.raises(FileExistsError):
        knowledge.generate_keypair(pk, write_public=False)                                 # never overwrite an existing private key
    assert (pk.stat().st_mode & 0o777) == 0o600
    sig = base64.b64encode(__import__("cryptography.hazmat.primitives.serialization", fromlist=["x"]).load_pem_private_key(pk.read_bytes(), None).sign(mani.read_bytes()))
    assert knowledge.verify_signature(mani.read_bytes(), sig, pub) and not knowledge.verify_signature(b"other", sig, pub)
    assert not knowledge.verify_signature(mani.read_bytes(), b"@@@", pub) and not pubfile.exists()


@pytest.mark.skipif(os.environ.get("DBA_MANIFEST_BY_CI") == "1", reason="signed by the knowledge-sign workflow after the push")
def test_committed_signature_matches_the_manifest_when_a_key_is_shipped():
    key = knowledge.pubkey()
    if not key:
        pytest.skip("no signing key committed yet (dba knowledge-keygen)")
    from importlib import resources
    base = resources.files("device_bus_analyzer")
    sig = base.joinpath(knowledge.SIGNATURE).read_text()
    assert knowledge.verify_signature(base.joinpath(knowledge.MANIFEST).read_bytes(), sig, key), "run: dba build-knowledge --sign <key>"


def test_sign_workflow_is_wired_up():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / ".github" / "workflows"
    wf = yaml.safe_load((root / "knowledge-sign.yml").read_text())
    text = (root / "knowledge-sign.yml").read_text()
    on = wf.get("on", wf.get(True))
    assert "src/device_bus_analyzer/catalog.yaml" in on["push"]["paths"] and not any("manifest" in p for p in on["push"]["paths"])   # no loop
    assert "secrets.DBA_SIGNING_KEY" in text and "--sign" in text and "image.yml" in text and wf["concurrency"] == "knowledge-sign"
    assert "DBA_SIGNING_KEY" not in (root / "ci.yml").read_text()                                                                       # key never reaches the PR/test workflow
