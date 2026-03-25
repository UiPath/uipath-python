# type: ignore
import json

import pytest

from uipath.platform.common import GenericResourceOverwrite, ResourceOverwriteParser
from uipath.platform.common._bindings import _resource_overwrites
from uipath.platform.common._bindings_service import BindingsService

SAMPLE_BINDINGS = {
    "version": "2.1",
    "resources": [
        {
            "resource": "Property",
            "key": "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder",
            "value": {
                "FullName": {
                    "defaultValue": "Invoices",
                    "isExpression": False,
                    "displayName": "File or folder",
                    "description": "Select a file or folder",
                    "propertyName": "BrowserItemFriendlyName",
                },
                "ID": {
                    "defaultValue": "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M",
                    "isExpression": False,
                    "displayName": "File or folder",
                    "description": "The file or folder of interest",
                    "propertyName": "BrowserItemId",
                },
                "ParentDriveID": {
                    "defaultValue": "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt",
                    "isExpression": False,
                    "displayName": "Drive",
                    "description": "The drive (OneDrive/SharePoint) of file or folder",
                    "propertyName": "BrowserDriveId",
                },
            },
            "metadata": {
                "ActivityName": "SharePoint Invoices folder",
                "BindingsVersion": "2.1",
                "ObjectName": "CuratedFile",
                "DisplayLabel": "FullName",
                "ParentResourceKey": "Connection.775694d9-4c5b-430f-bf47-6079b0ce8623",
            },
        }
    ],
}


@pytest.fixture
def bindings_file(tmp_path):
    path = tmp_path / "bindings.json"
    path.write_text(json.dumps(SAMPLE_BINDINGS))
    return path


@pytest.fixture
def service(bindings_file):
    return BindingsService(bindings_file_path=bindings_file)


class TestBindingsServiceGetProperty:
    def test_get_single_sub_property(self, service):
        result = service.get_property(
            "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder", "ID"
        )
        assert result == "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M"

    def test_get_all_sub_properties(self, service):
        result = service.get_property(
            "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder"
        )
        assert result == {
            "FullName": "Invoices",
            "ID": "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M",
            "ParentDriveID": "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt",
        }

    def test_suffix_key_match(self, service):
        """Key ending with the user-supplied string should resolve correctly."""
        result = service.get_property("SharePoint Invoices folder", "FullName")
        assert result == "Invoices"

    def test_suffix_key_all_properties(self, service):
        result = service.get_property("SharePoint Invoices folder")
        assert "ID" in result
        assert "FullName" in result
        assert "ParentDriveID" in result

    def test_key_not_found_raises(self, service):
        with pytest.raises(KeyError, match="nonexistent"):
            service.get_property("nonexistent.key", "ID")

    def test_sub_property_not_found_raises(self, service):
        with pytest.raises(KeyError, match="NoSuchField"):
            service.get_property("SharePoint Invoices folder", "NoSuchField")

    def test_missing_bindings_file_raises(self, tmp_path):
        service = BindingsService(bindings_file_path=tmp_path / "missing.json")
        with pytest.raises(KeyError):
            service.get_property("some.key", "ID")


class TestBindingsServiceWithRuntimeOverwrite:
    def test_overwrite_single_sub_property(self, service):
        overwrite = GenericResourceOverwrite(
            resource_type="property",
            ID="OVERWRITTEN_ID",
            ParentDriveID="OVERWRITTEN_DRIVE",
        )
        key = "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder"
        token = _resource_overwrites.set({f"property.{key}": overwrite})
        try:
            result = service.get_property(key, "ID")
            assert result == "OVERWRITTEN_ID"
        finally:
            _resource_overwrites.reset(token)

    def test_overwrite_all_sub_properties(self, service):
        overwrite = GenericResourceOverwrite(
            resource_type="property",
            ID="OVERWRITTEN_ID",
            ParentDriveID="OVERWRITTEN_DRIVE",
        )
        key = "SharePoint Invoices folder"
        token = _resource_overwrites.set({f"property.{key}": overwrite})
        try:
            result = service.get_property(key)
            assert result == {
                "ID": "OVERWRITTEN_ID",
                "ParentDriveID": "OVERWRITTEN_DRIVE",
            }
        finally:
            _resource_overwrites.reset(token)

    def test_overwrite_missing_sub_property_raises(self, service):
        overwrite = GenericResourceOverwrite(
            resource_type="property",
            ID="OVERWRITTEN_ID",
        )
        key = "SharePoint Invoices folder"
        token = _resource_overwrites.set({f"property.{key}": overwrite})
        try:
            with pytest.raises(KeyError, match="NoSuchField"):
                service.get_property(key, "NoSuchField")
        finally:
            _resource_overwrites.reset(token)

    def test_suffix_match_against_fully_qualified_contextvar_key(self, service):
        """Short label resolves against a fully-qualified key stored by the Studio path."""
        overwrite = GenericResourceOverwrite(
            resource_type="property",
            ID="STUDIO_ID",
            ParentDriveID="STUDIO_DRIVE",
        )
        # Studio stores keys as "property.<full-key>" — e.g. after ResourceOverwriteParser
        full_key = "775694d9-4c5b-430f-bf47-6079b0ce8623.SharePoint Invoices folder"
        token = _resource_overwrites.set({f"property.{full_key}": overwrite})
        try:
            # Caller uses only the label suffix, not the full UUID-prefixed key
            result = service.get_property("SharePoint Invoices folder", "ID")
            assert result == "STUDIO_ID"
        finally:
            _resource_overwrites.reset(token)

    def test_no_overwrite_falls_back_to_file(self, service):
        result = service.get_property("SharePoint Invoices folder", "ParentDriveID")
        assert (
            result
            == "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt"
        )


class TestPropertyResourceOverwrite:
    def test_construction(self):
        overwrite = GenericResourceOverwrite(
            resource_type="property",
            ID="abc",
            DriveID="xyz",
        )
        assert overwrite.resource_type == "property"
        assert overwrite.properties == {"ID": "abc", "DriveID": "xyz"}
        assert overwrite.resource_identifier == ""
        assert overwrite.folder_identifier == ""

    def test_parse_property_overwrite(self):
        overwrite = ResourceOverwriteParser.parse(
            key="property.some-connection.My Folder",
            value={"ID": "parsed_id", "DriveID": "parsed_drive"},
        )
        assert isinstance(overwrite, GenericResourceOverwrite)
        assert overwrite.resource_type == "property"
        assert overwrite.properties["ID"] == "parsed_id"
        assert overwrite.properties["DriveID"] == "parsed_drive"


RUNTIME_CONFIG = {
    "runtime": {
        "internalArguments": {
            "resourceOverwrites": {
                # Real runtime format: capital-P key prefix, extra fields on
                # connections, and flat sub-property values (no "values" wrapper).
                "connection.coupa-connection": {
                    "connectionId": "61de4895-f6e8-4252-90b7-8e7add4bfea8",
                    "elementInstanceId": "397548",
                    "folderKey": "19559fcf-166b-49ef-bbb8-bd672d679c76",
                    "ConnectionId": "61de4895-f6e8-4252-90b7-8e7add4bfea8",
                },
                "connection.sharepoint-connection": {
                    "connectionId": "359b25d6-79a2-43de-88fb-d7eb4230988a",
                    "elementInstanceId": "398411",
                    "folderKey": "19559fcf-166b-49ef-bbb8-bd672d679c76",
                    "ConnectionId": "359b25d6-79a2-43de-88fb-d7eb4230988a",
                },
                "Property.sharepoint-connection.SharePoint Invoices folder": {
                    "FullName": "Invoices",
                    "ID": "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M",
                    "ParentDriveID": "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt",
                },
            }
        }
    }
}


def _parse_runtime_overwrites(config: dict) -> dict:
    """Mirror what _common.py does when loading a runtime config file."""
    raw = (
        config.get("runtime", {})
        .get("internalArguments", {})
        .get("resourceOverwrites", {})
    )
    return {
        key: ResourceOverwriteParser.parse(key, value) for key, value in raw.items()
    }


class TestRuntimeConfigOverwrites:
    """End-to-end tests using the synthetic runtime config payload."""

    def test_parse_produces_three_overwrites(self):
        overwrites = _parse_runtime_overwrites(RUNTIME_CONFIG)
        assert len(overwrites) == 3

    def test_connection_overwrites_parsed(self):
        from uipath.platform.common import ConnectionResourceOverwrite

        overwrites = _parse_runtime_overwrites(RUNTIME_CONFIG)
        coupa = overwrites["connection.coupa-connection"]
        assert isinstance(coupa, ConnectionResourceOverwrite)
        assert coupa.connection_id == "61de4895-f6e8-4252-90b7-8e7add4bfea8"
        assert coupa.folder_key == "19559fcf-166b-49ef-bbb8-bd672d679c76"

        sp = overwrites["connection.sharepoint-connection"]
        assert isinstance(sp, ConnectionResourceOverwrite)
        assert sp.connection_id == "359b25d6-79a2-43de-88fb-d7eb4230988a"

    def test_property_overwrite_parsed(self):
        overwrites = _parse_runtime_overwrites(RUNTIME_CONFIG)
        # Key is stored with the original casing but normalised to lowercase resource_type
        prop = overwrites["Property.sharepoint-connection.SharePoint Invoices folder"]
        assert isinstance(prop, GenericResourceOverwrite)
        assert prop.resource_type == "property"
        assert prop.properties["ID"] == "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M"
        assert prop.properties["FullName"] == "Invoices"

    def test_get_property_full_key(self, bindings_file):
        overwrites = _parse_runtime_overwrites(RUNTIME_CONFIG)
        token = _resource_overwrites.set(overwrites)
        try:
            svc = BindingsService(bindings_file_path=bindings_file)
            result = svc.get_property(
                "sharepoint-connection.SharePoint Invoices folder", "ID"
            )
            assert result == "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M"
        finally:
            _resource_overwrites.reset(token)

    def test_get_property_suffix_key(self, bindings_file):
        """Short label should resolve against the fully-qualified stored key."""
        overwrites = _parse_runtime_overwrites(RUNTIME_CONFIG)
        token = _resource_overwrites.set(overwrites)
        try:
            svc = BindingsService(bindings_file_path=bindings_file)
            result = svc.get_property("SharePoint Invoices folder", "ParentDriveID")
            assert (
                result
                == "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt"
            )
        finally:
            _resource_overwrites.reset(token)

    def test_get_property_all_values(self, bindings_file):
        overwrites = _parse_runtime_overwrites(RUNTIME_CONFIG)
        token = _resource_overwrites.set(overwrites)
        try:
            svc = BindingsService(bindings_file_path=bindings_file)
            result = svc.get_property("SharePoint Invoices folder")
            assert result == {
                "FullName": "Invoices",
                "ID": "017NI543GXSYR5TZEZOBHJQNL6I2H4VA3M",
                "ParentDriveID": "b!fFiPzsQBgk2xGTJUTRo5jryva9eCrqNPowK3pN2kXWKF90cVuHqnS4RUsG9j1cRt",
            }
        finally:
            _resource_overwrites.reset(token)
