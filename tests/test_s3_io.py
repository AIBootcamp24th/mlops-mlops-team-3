from src.data import s3_io


class DummyS3Client:
    def __init__(self) -> None:
        self.download_called = False
        self.upload_called = False

    def download_file(self, bucket: str, key: str, local_path: str) -> None:
        self.download_called = True

    def upload_file(self, local_path: str, bucket: str, key: str) -> None:
        self.upload_called = True


class DummySession:
    def __init__(self, client: DummyS3Client) -> None:
        self._client = client

    def client(self, service_name: str) -> DummyS3Client:
        assert service_name == "s3"
        return self._client


def test_s3_upload_download(monkeypatch) -> None:
    client = DummyS3Client()
    monkeypatch.setattr(s3_io, "get_boto3_session", lambda: DummySession(client))

    _ = s3_io.download_file("bucket", "key", "tmp/test.csv")
    uri = s3_io.upload_file("tmp/test.csv", "bucket", "model/key.pt")

    assert client.download_called
    assert client.upload_called
    assert uri == "s3://bucket/model/key.pt"
