"""Support for Moonraker camera."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from urllib.parse import urlparse

from homeassistant.components.camera import Camera
from homeassistant.components.mjpeg.camera import MjpegCamera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_OPTION_CAMERA_PORT,
    CONF_OPTION_CAMERA_SNAPSHOT,
    CONF_OPTION_CAMERA_STREAM,
    CONF_OPTION_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL,
    CONF_OPTION_THUMBNAIL_PORT,
    CONF_URL,
    DEFAULT_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL,
    DOMAIN,
    METHODS,
    PRINTSTATES,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_PORT = 80
SNAPMAKER_U1_CAMERA_MONITOR_PATH = "/server/files/camera/monitor.jpg"
SNAPMAKER_U1_MACHINE_TYPE = "snapmaker u1"

hardcoded_camera = {
    "name": "webcam",
    "location": "printer",
    "service": "mjpegstreamer-adaptive",
    "target_fps": "15",
    "stream_url": "/webcam/?action=stream",
    "snapshot_url": "/webcam/?action=snapshot",
    "flip_horizontal": False,
    "flip_vertical": False,
    "rotation": 0,
    "source": "database",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available Moonraker camera."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    camera_cnt = 0

    try:
        if (
            config_entry.options.get(CONF_OPTION_CAMERA_STREAM) is not None
            and config_entry.options.get(CONF_OPTION_CAMERA_STREAM) != ""
        ):
            hardcoded_camera["stream_url"] = config_entry.options.get(
                CONF_OPTION_CAMERA_STREAM
            )
            hardcoded_camera["snapshot_url"] = config_entry.options.get(
                CONF_OPTION_CAMERA_SNAPSHOT
            )
            async_add_entities(
                [MoonrakerCamera(config_entry, coordinator, hardcoded_camera, 100)]
            )
            camera_cnt += 1
        else:
            cameras = await coordinator.async_fetch_data(METHODS.SERVER_WEBCAMS_LIST)
            for camera_id, camera in enumerate(cameras["webcams"]):
                async_add_entities(
                    [MoonrakerCamera(config_entry, coordinator, camera, camera_id)]
                )
                camera_cnt += 1
    except Exception:
        _LOGGER.info("Could not add any cameras from the API list")

    if camera_cnt == 0:
        _LOGGER.info("No Camera in the list, trying hardcoded")
        async_add_entities(
            [MoonrakerCamera(config_entry, coordinator, hardcoded_camera, 0)]
        )

    async_add_entities(
        [
            PreviewCamera(
                config_entry,
                coordinator,
                async_get_clientsession(hass, verify_ssl=False),
            )
        ]
    )


class MoonrakerCamera(MjpegCamera):
    """Representation of an Moonraker Camera Stream."""

    def __init__(self, config_entry, coordinator, camera, camera_id) -> None:
        """Initialize as a subclass of MjpegCamera."""

        self.camera = camera
        self.coordinator = coordinator
        self._remove_snapmaker_monitor_interval = None
        self._snapmaker_monitor_enabled = False
        self._snapmaker_monitor_interval = config_entry.options.get(
            CONF_OPTION_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL,
            DEFAULT_SNAPMAKER_U1_CAMERA_HEARTBEAT_INTERVAL,
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)}
        )
        if (
            config_entry.options.get(CONF_OPTION_CAMERA_PORT) is not None
            and config_entry.options.get(CONF_OPTION_CAMERA_PORT) != ""
        ):
            self.port = config_entry.options.get(CONF_OPTION_CAMERA_PORT)
        else:
            self.port = DEFAULT_PORT

        if camera["stream_url"].startswith("http"):
            self.url = ""
        else:
            self.url = f"http://{config_entry.data.get(CONF_URL)}:{self.port}"

        _LOGGER.info(f"Connecting to camera: {self.url}{camera['stream_url']}")

        super().__init__(
            device_info=self._attr_device_info,
            mjpeg_url=f"{self.url}{camera['stream_url']}",
            name=f"{coordinator.api_device_name} {camera['name']}",
            still_image_url=f"{self.url}{camera['snapshot_url']}",
            unique_id=f"{config_entry.entry_id}_{camera['name']}_{camera_id}",
        )

    async def async_added_to_hass(self) -> None:
        """Start the Snapmaker U1 camera monitor heartbeat if needed."""
        await super().async_added_to_hass()

        if not self._uses_snapmaker_monitor_path():
            return

        if not await self._async_is_snapmaker_u1():
            return

        self._snapmaker_monitor_enabled = True
        await self._async_send_snapmaker_monitor(METHODS.CAMERA_START_MONITOR)
        self._remove_snapmaker_monitor_interval = async_track_time_interval(
            self.hass,
            self._async_snapmaker_monitor_tick,
            timedelta(seconds=self._snapmaker_monitor_interval),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop the Snapmaker U1 camera monitor heartbeat."""
        if self._remove_snapmaker_monitor_interval is not None:
            self._remove_snapmaker_monitor_interval()
            self._remove_snapmaker_monitor_interval = None

        if self._snapmaker_monitor_enabled:
            await self._async_send_snapmaker_monitor(METHODS.CAMERA_STOP_MONITOR)
            self._snapmaker_monitor_enabled = False

        await super().async_will_remove_from_hass()

    def _uses_snapmaker_monitor_path(self) -> bool:
        """Return true when this camera uses the Snapmaker monitor image path."""
        for key in ("stream_url", "snapshot_url"):
            raw_url = str(self.camera.get(key) or "")
            if not raw_url:
                continue
            path = urlparse(raw_url).path if raw_url.startswith("http") else raw_url
            path = path.split("?", 1)[0].rstrip("/")
            if path == SNAPMAKER_U1_CAMERA_MONITOR_PATH:
                return True
        return False

    async def _async_is_snapmaker_u1(self) -> bool:
        """Return true when machine.system_info identifies a Snapmaker U1."""
        cached = getattr(self.coordinator, "_snapmaker_u1", None)
        if cached is not None:
            return cached

        system_info = self.coordinator.data.get("system_info")
        if not system_info:
            try:
                response = await self.coordinator.async_fetch_data(
                    METHODS.MACHINE_SYSTEM_INFO, quiet=True
                )
            except Exception:
                _LOGGER.debug(
                    "Unable to read machine.system_info for Snapmaker U1 detection",
                    exc_info=True,
                )
                self.coordinator._snapmaker_u1 = False
                return False

            system_info = response.get("system_info") or {}

        product_info = system_info.get("product_info") or {}
        machine_type = str(product_info.get("machine_type", "")).casefold()
        self.coordinator._snapmaker_u1 = machine_type == SNAPMAKER_U1_MACHINE_TYPE
        return self.coordinator._snapmaker_u1

    async def _async_snapmaker_monitor_tick(self, _now) -> None:
        """Keep the Snapmaker U1 camera monitor active."""
        await self._async_send_snapmaker_monitor(METHODS.CAMERA_START_MONITOR)

    async def _async_send_snapmaker_monitor(self, method: METHODS) -> None:
        """Send a Snapmaker U1 camera monitor RPC call."""
        try:
            await self.coordinator.async_send_data(
                method,
                {"req_id": int(time.time() * 1000)},
            )
        except Exception:
            _LOGGER.debug(
                "Unable to send Snapmaker U1 camera monitor request: %s",
                method.value,
                exc_info=True,
            )


class PreviewCamera(Camera):
    """Representation of the gcode thumnail."""

    _attr_is_streaming = False

    def __init__(self, config_entry, coordinator, session) -> None:
        """Initialize as a subclass of Camera for the Thumbnail Preview."""

        super().__init__()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)}
        )
        self.url = config_entry.data.get(CONF_URL)
        self.coordinator = coordinator
        self._attr_name = f"{coordinator.api_device_name} Thumbnail"
        self._attr_unique_id = f"{config_entry.entry_id}_thumbnail"
        self._session = session
        self._current_pic = None
        self._current_path = ""

        if (
            config_entry.options.get(CONF_OPTION_THUMBNAIL_PORT) is not None
            and config_entry.options.get(CONF_OPTION_THUMBNAIL_PORT) != ""
        ):
            self.port = config_entry.options.get(CONF_OPTION_THUMBNAIL_PORT)
        else:
            self.port = DEFAULT_PORT

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return current camera image."""
        _LOGGER.debug("Trying to get thumbnail ")
        if (
            self.coordinator.data["status"]["print_stats"]["state"]
            != PRINTSTATES.PRINTING.value
        ):
            _LOGGER.debug("Not printing, no thumbnail")
            return None

        del width, height

        new_path = self.coordinator.data["thumbnails_path"]

        _LOGGER.debug(f"Thumbnail new_path: {new_path}")
        if self._current_path == new_path and self._current_pic is not None:
            _LOGGER.debug("no change in thumbnail, returning cached")
            return self._current_pic

        if new_path == "" or new_path is None:
            self._current_pic = None
            self._current_path = ""
            _LOGGER.debug("Empty path, no thumbnail")
            return None

        new_path = new_path.replace(" ", "%20")

        _LOGGER.debug(
            f"Fetching new thumbnail: http://{self.url}:{self.port}/server/files/gcodes/{new_path}"
        )
        response = await self._session.get(
            f"http://{self.url}:{self.port}/server/files/gcodes/{new_path}"
        )

        self._current_path = new_path
        self._current_pic = await response.read()

        return self._current_pic
