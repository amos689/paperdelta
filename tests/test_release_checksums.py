from hashlib import sha256

import pytest

from tools.verify_release import validate_checksums


def test_release_assets_require_exact_manifest_and_matching_bytes(tmp_path):
    data = b"the verified distribution"
    (tmp_path / "package.whl").write_bytes(data)
    checksum = sha256(data).hexdigest()
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{checksum}  package.whl\n", "utf-8")
    assert validate_checksums(tmp_path, ["package.whl"]) == {"package.whl": checksum}
    with pytest.raises(ValueError, match="expected"):
        validate_checksums(tmp_path, ["different.whl"])
    (tmp_path / "package.whl").write_bytes(b"changed")
    with pytest.raises(ValueError, match="mismatch"):
        validate_checksums(tmp_path, ["package.whl"])
    for line in (f"{checksum}  ../package.whl\n", f"{checksum}  package.whl\n" * 2):
        sums.write_text(line, "utf-8")
        with pytest.raises(ValueError, match="Invalid"):
            validate_checksums(tmp_path, ["package.whl"])
