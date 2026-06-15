from uipath.platform.mcp_jobs import (
    JOB_META_KEY,
    UiPathJobHandle,
    build_fetch_meta,
    build_start_meta,
    read_job_handle,
    read_job_version,
)


def test_build_start_meta_default_version() -> None:
    assert build_start_meta() == {JOB_META_KEY: {"version": 1}}


def test_build_start_meta_explicit_version() -> None:
    assert build_start_meta(2) == {JOB_META_KEY: {"version": 2}}


def test_build_fetch_meta() -> None:
    handle = UiPathJobHandle(job_key="job-1", folder_key="folder-1")
    assert build_fetch_meta(handle) == {
        JOB_META_KEY: {"key": "job-1", "folderKey": "folder-1"}
    }


def test_read_job_handle_present() -> None:
    meta = {JOB_META_KEY: {"key": "job-1", "folderKey": "folder-1"}}
    assert read_job_handle(meta) == UiPathJobHandle(
        job_key="job-1", folder_key="folder-1"
    )


def test_read_job_handle_version_only_is_none() -> None:
    # A START opt-in echoed back has no key -> not a handle.
    assert read_job_handle({JOB_META_KEY: {"version": 1}}) is None


def test_read_job_handle_partial_is_none() -> None:
    assert read_job_handle({JOB_META_KEY: {"key": "job-1"}}) is None
    assert read_job_handle({JOB_META_KEY: {"folderKey": "folder-1"}}) is None
    assert read_job_handle({JOB_META_KEY: {"key": "", "folderKey": ""}}) is None


def test_read_job_handle_missing_or_empty() -> None:
    assert read_job_handle(None) is None
    assert read_job_handle({}) is None
    assert read_job_handle({"other": {"key": "x"}}) is None


def test_read_job_handle_non_mapping_section() -> None:
    assert read_job_handle({JOB_META_KEY: "not-a-mapping"}) is None


def test_read_job_version() -> None:
    assert read_job_version({JOB_META_KEY: {"version": 3}}) == 3
    assert read_job_version({JOB_META_KEY: {"key": "k", "folderKey": "f"}}) is None
    assert read_job_version(None) is None
    assert read_job_version({JOB_META_KEY: {"version": "1"}}) is None


def test_fetch_meta_round_trips_through_read_job_handle() -> None:
    handle = UiPathJobHandle(job_key="job-9", folder_key="folder-9")
    assert read_job_handle(build_fetch_meta(handle)) == handle
