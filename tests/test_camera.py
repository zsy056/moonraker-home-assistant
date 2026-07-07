"""test moonraker camera."""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components import camera
from homeassistant.helpers import entity_registry as er
from PIL import Image
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.moonraker.const import DOMAIN, PRINTSTATES
from custom_components.moonraker.camera import MoonrakerCamera

from .const import MOCK_CONFIG, MOCK_OPTIONS
from custom_components.moonraker.const import (
    CONF_OPTION_CAMERA_STREAM,
    CONF_OPTION_CAMERA_SNAPSHOT,
    CONF_OPTION_CAMERA_PORT,
    CONF_OPTION_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL,
    CONF_OPTION_THUMBNAIL_PORT,
    METHODS,
)


@pytest.fixture(name="bypass_connect_client", autouse=True)
def bypass_connect_client_fixture():
    """Skip calls to get data from API."""
    with patch("custom_components.moonraker.MoonrakerApiClient.start"):
        yield


async def test_camera_services(hass, caplog):
    """Test camera services."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_webcam")

    assert entry is not None
    assert (
        "Connecting to camera: http://1.2.3.4:80/webcam/?action=stream" in caplog.text
    )


async def test_camera_services_full_path(hass, get_camera_info, caplog):
    """Test camera services."""
    get_camera_info["webcams"][0][
        "stream_url"
    ] = "http://1.2.3.4/webcam/?action=2stream"
    get_camera_info["webcams"][0][
        "snapshot_url"
    ] = "http://1.2.3.4/webcam/?action=2snapshot"
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_webcam")

    assert entry is not None
    assert "Connecting to camera: http://1.2.3.4/webcam/?action=2stream" in caplog.text


async def test_two_cameras_services(hass, get_camera_info):
    """Test cameras Services."""
    get_camera_info["webcams"].append(
        {
            "name": "webcam2",
            "stream_url": "/webcam2/?action=stream",
            "snapshot_url": "/webcam2/?action=snapshot",
        }
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get("camera.mainsail_webcam") is not None
    assert entity_registry.async_get("camera.mainsail_webcam2") is not None


async def test_two_cameras_same_name_services(hass, get_camera_info):
    """Test two cameras same name."""
    get_camera_info["webcams"].append(
        {
            "name": "webcam",
            "stream_url": "/webcam/?action=stream",
            "snapshot_url": "/webcam/?action=snapshot",
        }
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get("camera.mainsail_webcam") is not None
    assert entity_registry.async_get("camera.mainsail_webcam_2") is not None


async def test_setup_thumbnail_camera(hass, get_data):
    """Test setup thumbnail camera."""
    get_data["status"]["print_stats"]["filename"] = "CE3E3V2_picture_frame_holder.gcode"

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_thumbnail")

    assert entry is not None


async def test_hardcoded_camera_empty_list(hass, get_default_api_response):
    """Test hardcoded camera."""
    get_default_api_response["webcams"] = []

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_webcam")

    assert entry is not None


async def test_hardcoded_camera_API_error(hass, get_default_api_response):
    """Test hardcoded camera."""
    get_default_api_response["webcams"] = None

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_webcam")

    assert entry is not None


async def test_thumbnail_camera_image(
    hass, aioclient_mock, get_data, _moonraker_default_mock
):
    """Test thumbnail camera image."""

    get_data["status"]["print_stats"]["filename"] = "CE3E3V2_picture_frame_holder.gcode"

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = (
        "http://1.2.3.4/server/files/gcodes/.thumbs/CE3E3V2_picture_frame_holder.png"
    )

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    await camera.async_get_image(hass, "camera.mainsail_thumbnail")
    await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_thumbnail_camera_from_img_to_none(hass):
    """Test thumbnail camera from img to none."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(Exception):
        await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_thumbnail_no_thumbnail(hass, get_data):
    """Test setup thumbnail camera."""
    get_data["status"]["print_stats"]["filename"] = ""

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_thumbnail")

    assert entry is not None


async def test_thumbnail_not_printing(hass, aioclient_mock, get_data):
    """Test setup thumbnail camera."""
    get_data["status"]["print_stats"]["state"] = PRINTSTATES.STANDBY.value

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = (
        "http://1.2.3.4/server/files/gcodes/.thumbs/CE3E3V2_picture_frame_holder.png"
    )

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    with pytest.raises(Exception):
        await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_thumbnail_no_thumbnail_after_update(
    hass,
    aioclient_mock,
    get_data,
):
    """Test setup thumbnail camera."""

    get_data["status"]["print_stats"]["filename"] = "CE3E3V2_picture_frame_holder.gcode"

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = (
        "http://1.2.3.4/server/files/gcodes/.thumbs/CE3E3V2_picture_frame_holder.png"
    )

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    await camera.async_get_image(hass, "camera.mainsail_thumbnail")

    get_data["status"]["print_stats"]["filename"] = ""

    async_fire_time_changed(
        hass,
        dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5),
    )
    await hass.async_block_till_done()

    with pytest.raises(Exception):
        await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_thumbnail_data_failing(
    hass, get_data, get_printer_info, get_camera_info
):
    """Test setup thumbnail camera."""

    get_data["status"]["print_stats"]["filename"] = "CE3E3V2_picture_frame_holder.gcode"
    del get_data["thumbnails"]
    with patch(
        "moonraker_api.MoonrakerClient.call_method",
        return_value={**get_data, **get_printer_info, **get_camera_info},
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_thumbnail")

    assert entry is not None


async def test_thumbnail_on_subfolder(hass, get_data, aioclient_mock):
    """Test thumbnail on subfolder."""

    get_data["status"]["print_stats"][
        "filename"
    ] = "subfolder/CE3E3V2_picture_frame_holder.gcode"

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = "http://1.2.3.4/server/files/gcodes/subfolder/.thumbs/CE3E3V2_picture_frame_holder.png"

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    await camera.async_get_image(hass, "camera.mainsail_thumbnail")
    await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_thumbnail_with_gcodes_prefix(hass, get_data, aioclient_mock):
    """Test thumbnail path when filename includes gcodes root."""
    get_data["status"]["print_stats"][
        "filename"
    ] = "gcodes/subfolder/CE3E3V2_picture_frame_holder.gcode"

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = "http://1.2.3.4/server/files/gcodes/subfolder/.thumbs/CE3E3V2_picture_frame_holder.png"

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_thumbnail_space_in_path(hass, get_data, aioclient_mock):
    """Test thumbnail with space in URL."""

    get_data["thumbnails"][1][
        "relative_path"
    ] = ".thumbs/CE3E3V2_picture frame_holder-32x32.png"

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = "http://1.2.3.4/server/files/gcodes/.thumbs/CE3E3V2_picture%20frame_holder-32x32.png"

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_thumbnail_uses_virtual_sdcard_path(hass, get_data, aioclient_mock):
    """Use virtual_sdcard.file_path when print_stats filename is empty."""
    get_data["status"]["print_stats"]["filename"] = ""
    get_data["status"]["virtual_sdcard"] = {
        "file_path": "subfolder/CE3E3V2_picture_frame_holder.gcode"
    }

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = "http://1.2.3.4/server/files/gcodes/subfolder/.thumbs/CE3E3V2_picture_frame_holder.png"

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_option_config_camera_services(hass, caplog):
    """Test camera services."""

    custom_options = {
        key: MOCK_OPTIONS[key]
        for key in [CONF_OPTION_CAMERA_STREAM, CONF_OPTION_CAMERA_SNAPSHOT]
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=custom_options, entry_id="test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_webcam")

    assert entry is not None
    assert "Connecting to camera: http://1.2.3.4/stream" in caplog.text


async def test_option_config_camera_port(hass, caplog):
    """Test camera services."""

    custom_options = {key: MOCK_OPTIONS[key] for key in [CONF_OPTION_CAMERA_PORT]}

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=custom_options, entry_id="test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_webcam")

    assert entry is not None
    assert (
        "Connecting to camera: http://1.2.3.4:1234/webcam/?action=stream" in caplog.text
    )


async def test_option_config_bypass_custom_port(hass, caplog):
    """Test camera services."""

    custom_options = {
        key: MOCK_OPTIONS[key]
        for key in [
            CONF_OPTION_CAMERA_PORT,
            CONF_OPTION_CAMERA_STREAM,
            CONF_OPTION_CAMERA_SNAPSHOT,
        ]
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=custom_options, entry_id="test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.mainsail_webcam")

    assert entry is not None
    assert "Connecting to camera: http://1.2.3.4/stream" in caplog.text


async def test_option_config_thumbnail_port(hass, aioclient_mock, get_data):
    """Test camera services."""

    custom_options = {key: MOCK_OPTIONS[key] for key in [CONF_OPTION_THUMBNAIL_PORT]}

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=custom_options, entry_id="test"
    )

    get_data["status"]["print_stats"]["filename"] = "CE3E3V2_picture_frame_holder.gcode"

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    test_path = "http://1.2.3.4:5678/server/files/gcodes/.thumbs/CE3E3V2_picture_frame_holder.png"

    aioclient_mock.get(test_path, content=Image.new("RGB", (30, 30)))

    await camera.async_get_image(hass, "camera.mainsail_thumbnail")
    await camera.async_get_image(hass, "camera.mainsail_thumbnail")


async def test_snapmaker_u1_camera_monitor_heartbeat(
    hass, get_camera_info, get_system_info, get_default_api_response
):
    """Start and stop the Snapmaker U1 camera monitor heartbeat."""
    get_camera_info["webcams"][0]["stream_url"] = "/server/files/camera/monitor.jpg"
    get_camera_info["webcams"][0]["snapshot_url"] = "/server/files/camera/monitor.jpg"
    get_system_info["system_info"]["product_info"] = {
        "machine_type": "Snapmaker U1",
    }
    calls = []

    async def call_method(method, **kwargs):
        calls.append((method, kwargs))
        return get_default_api_response

    remove_interval = Mock()
    options = {
        CONF_OPTION_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL: MOCK_OPTIONS[
            CONF_OPTION_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL
        ],
    }

    with (
        patch("moonraker_api.MoonrakerClient.call_method", side_effect=call_method),
        patch(
            "custom_components.moonraker.camera.async_track_time_interval",
            return_value=remove_interval,
        ) as track_interval,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, options=options, entry_id="test"
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        start_monitor_seen = any(
            method == "camera.start_monitor" and "req_id" in kwargs
            for method, kwargs in calls
        )

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    track_interval.assert_called_once()
    assert track_interval.call_args.args[2] == dt.timedelta(
        seconds=MOCK_OPTIONS[CONF_OPTION_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL]
    )
    remove_interval.assert_called_once()
    assert start_monitor_seen
    assert any(
        method == "camera.stop_monitor" and "req_id" in kwargs
        for method, kwargs in calls
    )


async def test_snapmaker_u1_camera_monitor_not_started_for_other_printers(
    hass, get_camera_info, get_system_info, get_default_api_response
):
    """Do not start the Snapmaker monitor heartbeat on non-U1 printers."""
    get_camera_info["webcams"][0]["stream_url"] = "/server/files/camera/monitor.jpg"
    get_camera_info["webcams"][0]["snapshot_url"] = "/server/files/camera/monitor.jpg"
    get_system_info["system_info"]["product_info"] = {
        "machine_type": "Raspberry Pi",
    }
    calls = []

    async def call_method(method, **kwargs):
        calls.append((method, kwargs))
        return get_default_api_response

    with patch("moonraker_api.MoonrakerClient.call_method", side_effect=call_method):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert not any(method == "camera.start_monitor" for method, _kwargs in calls)
    assert not any(method == "camera.stop_monitor" for method, _kwargs in calls)


def _make_moonraker_camera(coordinator, camera_data):
    """Create a Moonraker camera entity for direct helper tests."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    return MoonrakerCamera(config_entry, coordinator, camera_data, 0)


def test_snapmaker_monitor_path_skips_empty_urls():
    """Skip empty camera URLs while checking for the Snapmaker monitor path."""
    coordinator = SimpleNamespace(api_device_name="mainsail", data={})
    moonraker_camera = _make_moonraker_camera(
        coordinator,
        {
            "name": "webcam",
            "stream_url": "",
            "snapshot_url": "/webcam/?action=snapshot",
        },
    )

    assert not moonraker_camera._uses_snapmaker_monitor_path()


async def test_snapmaker_u1_detection_uses_cached_value():
    """Use cached Snapmaker U1 detection results."""
    coordinator = SimpleNamespace(
        api_device_name="mainsail",
        data={},
        _snapmaker_u1=True,
    )
    moonraker_camera = _make_moonraker_camera(
        coordinator,
        {
            "name": "webcam",
            "stream_url": "/server/files/camera/monitor.jpg",
            "snapshot_url": "/server/files/camera/monitor.jpg",
        },
    )

    assert await moonraker_camera._async_is_snapmaker_u1()


async def test_snapmaker_u1_detection_fetches_system_info():
    """Fetch machine system info when it has not been cached yet."""
    coordinator = SimpleNamespace(
        api_device_name="mainsail",
        data={},
        async_fetch_data=AsyncMock(
            return_value={
                "system_info": {
                    "product_info": {
                        "machine_type": "Snapmaker U1",
                    },
                },
            }
        ),
    )
    moonraker_camera = _make_moonraker_camera(
        coordinator,
        {
            "name": "webcam",
            "stream_url": "/server/files/camera/monitor.jpg",
            "snapshot_url": "/server/files/camera/monitor.jpg",
        },
    )

    assert await moonraker_camera._async_is_snapmaker_u1()
    coordinator.async_fetch_data.assert_awaited_once_with(
        METHODS.MACHINE_SYSTEM_INFO, quiet=True
    )


async def test_snapmaker_u1_detection_handles_fetch_error():
    """Disable Snapmaker monitor support when machine info cannot be fetched."""
    coordinator = SimpleNamespace(
        api_device_name="mainsail",
        data={},
        async_fetch_data=AsyncMock(side_effect=Exception),
    )
    moonraker_camera = _make_moonraker_camera(
        coordinator,
        {
            "name": "webcam",
            "stream_url": "/server/files/camera/monitor.jpg",
            "snapshot_url": "/server/files/camera/monitor.jpg",
        },
    )

    assert not await moonraker_camera._async_is_snapmaker_u1()


async def test_snapmaker_monitor_tick_sends_start_request():
    """Send a start-monitor request from the scheduled monitor tick."""
    coordinator = SimpleNamespace(
        api_device_name="mainsail",
        data={},
        async_send_data=AsyncMock(),
    )
    moonraker_camera = _make_moonraker_camera(
        coordinator,
        {
            "name": "webcam",
            "stream_url": "/server/files/camera/monitor.jpg",
            "snapshot_url": "/server/files/camera/monitor.jpg",
        },
    )

    await moonraker_camera._async_snapmaker_monitor_tick(None)

    method, payload = coordinator.async_send_data.await_args.args
    assert method == METHODS.CAMERA_START_MONITOR
    assert "req_id" in payload


async def test_snapmaker_monitor_send_handles_error():
    """Do not fail entity setup when the monitor RPC call fails."""
    coordinator = SimpleNamespace(
        api_device_name="mainsail",
        data={},
        async_send_data=AsyncMock(side_effect=Exception),
    )
    moonraker_camera = _make_moonraker_camera(
        coordinator,
        {
            "name": "webcam",
            "stream_url": "/server/files/camera/monitor.jpg",
            "snapshot_url": "/server/files/camera/monitor.jpg",
        },
    )

    await moonraker_camera._async_send_snapmaker_monitor(METHODS.CAMERA_START_MONITOR)
