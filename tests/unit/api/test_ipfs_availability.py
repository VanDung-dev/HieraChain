"""CID checks use the supported files/stat RPC, including failure responses."""

import httpx
import pytest

from hierachain.api.storage.ipfs_client import IPFSClient


@pytest.mark.parametrize("status_code", [200, 404, 500])
def test_availability_uses_files_stat(status_code: int) -> None:
    cid = "Qm" + "a" * 44

    def rpc(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v0/files/stat"
        assert request.url.params["arg"] == f"/ipfs/{cid}"
        return httpx.Response(status_code)

    with IPFSClient() as client:
        client._client = httpx.Client(base_url="http://test", transport=httpx.MockTransport(rpc))
        assert client.is_available(cid) is (status_code == 200)
