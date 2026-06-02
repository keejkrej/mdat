from mdat.core.io.sources import is_remote_input, location_suffix


def test_smb_path_suffix() -> None:
    path = "smb:session-1/project/file.nd2"
    assert is_remote_input(path)
    assert location_suffix(path) == ".nd2"
