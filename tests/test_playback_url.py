from __future__ import annotations

import sys
import types
import unittest
import base64
import hashlib
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin.video.nextembycon"))


class FakeAddon:
    settings: dict[str, str] = {
        "protocol": "1",
        "verify_cert": "true",
        "ipaddress": "media.example.test",
        "port": "443",
        "deviceName": "Kodi",
        "allow_direct_file_play": "false",
        "audio_playback_bitrate": "384",
        "playback_max_width": "1920",
        "http_timeout": "10",
        "suppressErrors": "true",
        "username": "user",
        "password": "pass",
        "save_user_to_settings": "true",
        "logLevel": "0",
        "max_image_width": "500",
    }

    def getSetting(self, key: str) -> str:
        return self.settings.get(key, "")

    def setSetting(self, key: str, value: str) -> None:
        self.settings[key] = value

    def getAddonInfo(self, key: str) -> str:
        return {"version": "test", "path": str(ROOT)}.get(key, "")

    def getLocalizedString(self, string_id: int) -> str:
        return str(string_id)


class FakeHomeWindow:
    props: dict[str, str] = {"userid": "user-id", "userimage": "DefaultUser.png"}

    def get_property(self, key: str) -> str:
        return self.props.get(key, "")

    def set_property(self, key: str, value: str) -> None:
        self.props[key] = value

    def clear_property(self, key: str) -> None:
        self.props.pop(key, None)


class FakeDownloadUtils:
    def set_host_domain(self) -> None:
        pass

    def get_server(self, add_user_id: bool = False) -> str:
        assert add_user_id is False
        return "https://media.example.test/proxy"

    def authenticate(self) -> str:
        return "token-123"


class FakeClientInformation:
    @staticmethod
    def get_device_id() -> str:
        return "device-456"

    @staticmethod
    def get_version() -> str:
        return "test-version"

    @staticmethod
    def get_client() -> str:
        return "Test Client"

    @staticmethod
    def get_user_agent() -> str:
        return "Kodi/test-version"


class FakePlaybackDownloadUtils:
    calls: list[dict[str, object]] = []

    def download_url(
        self,
        url: str,
        suppress: bool = False,
        post_body: str | dict | None = None,
        method: str = "GET",
        authenticate: bool = True,
        headers: dict[str, str] | None = None,
    ) -> str:
        self.calls.append(
            {
                "url": url,
                "suppress": suppress,
                "post_body": post_body,
                "method": method,
                "authenticate": authenticate,
                "headers": headers,
            }
        )
        return "null"


class FakeListItem:
    def __init__(self) -> None:
        self.subtitles: list[str] = []

    def setSubtitles(self, subtitles: list[str]) -> None:
        self.subtitles = subtitles


class FakeKodiListItem:
    def __init__(
        self,
        label: str = "",
        label2: str | None = None,
        path: str | None = None,
        offscreen: bool = False,
    ) -> None:
        self.label = label
        self.label2 = label2
        self.path = path
        self.offscreen = offscreen
        self.art: dict[str, str] = {}
        self.properties: dict[str, str] = {}

    def setArt(self, art: dict[str, str]) -> None:
        self.art = art

    def setProperty(self, key: str, value: str) -> None:
        self.properties[key] = value

    def setPath(self, value: str) -> None:
        self.path = value

    def getProperty(self, key: str) -> str:
        return self.properties.get(key, "")

    def setLabel2(self, value: str) -> None:
        self.label2 = value

    def getLabel(self) -> str:
        return self.label


class FakeDialog:
    select_calls: list[dict[str, object]] = []
    select_results: list[int] = []
    notifications: list[dict[str, object]] = []

    def notification(self, *args, **kwargs) -> None:
        self.notifications.append({"args": args, "kwargs": kwargs})

    def select(self, *args, **kwargs) -> int:
        self.select_calls.append({"args": args, "kwargs": kwargs})
        if self.select_results:
            return self.select_results.pop(0)
        return -1


class FakeHTTPResponse:
    def __init__(
        self, status: int, reason: str, body: bytes = b"null", headers=None
    ) -> None:
        self.status = status
        self.reason = reason
        self._body = body
        self._headers = headers or []

    def read(self) -> bytes:
        return self._body

    def getheaders(self):
        return self._headers

    def getheader(self, name: str):
        for key, value in self._headers:
            if key.lower() == name.lower():
                return value
        return None


class FakeHTTPConnection:
    instances: list["FakeHTTPConnection"] = []
    response = FakeHTTPResponse(200, "OK", b"{}")

    def __init__(
        self, host: str, port=None, timeout=None, context=None
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.requests: list[dict[str, object]] = []
        self.instances.append(self)

    @property
    def address(self) -> str:
        if self.port is None:
            return self.host
        return "%s:%s" % (self.host, self.port)

    def request(self, method: str, url: str, body=None, headers=None) -> None:
        self.requests.append(
            {"method": method, "url": url, "body": body, "headers": headers}
        )

    def getresponse(self) -> FakeHTTPResponse:
        return self.response

    def close(self) -> None:
        pass


class FakeMonitor:
    def waitForAbort(self, timeout: int) -> bool:
        return False

    def abortRequested(self) -> bool:
        return True


def install_kodi_stubs() -> None:
    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = lambda: FakeAddon()
    sys.modules["xbmcaddon"] = xbmcaddon

    xbmc = types.ModuleType("xbmc")
    xbmc.LOGINFO = 1
    xbmc.LOGERROR = 4
    xbmc.PLAYLIST_VIDEO = 1
    xbmc.log = lambda *args, **kwargs: None
    xbmc.executebuiltin = lambda *args, **kwargs: None
    xbmc.executeJSONRPC = lambda *args, **kwargs: '{"result": {}}'
    xbmc.getCondVisibility = lambda *args, **kwargs: False
    xbmc.Player = type("Player", (), {})
    xbmc.Monitor = FakeMonitor
    xbmc.PlayList = lambda _playlist_type: types.SimpleNamespace(
        clear=lambda: None,
        add=lambda *a, **k: None,
        getposition=lambda: -1,
        size=lambda: 0,
    )
    sys.modules["xbmc"] = xbmc

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.exists = lambda path: False
    xbmcvfs.translatePath = lambda path: path
    xbmcvfs.mkdirs = lambda path: True
    sys.modules["xbmcvfs"] = xbmcvfs

    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.WindowXMLDialog = type("WindowXMLDialog", (), {})
    xbmcgui.ListItem = FakeKodiListItem
    xbmcgui.Dialog = FakeDialog
    sys.modules["xbmcgui"] = xbmcgui

    xbmcplugin = types.ModuleType("xbmcplugin")
    xbmcplugin.added_items = []
    xbmcplugin.content_calls = []
    xbmcplugin.ended_handles = []
    xbmcplugin.addDirectoryItem = lambda handle, url, listitem, isFolder=True: xbmcplugin.added_items.append(
        {
            "handle": handle,
            "url": url,
            "listitem": listitem,
            "isFolder": isFolder,
        }
    )
    xbmcplugin.setContent = lambda handle, content: xbmcplugin.content_calls.append(
        {"handle": handle, "content": content}
    )
    xbmcplugin.endOfDirectory = lambda handle, **kwargs: xbmcplugin.ended_handles.append(
        {"handle": handle, **kwargs}
    )
    sys.modules["xbmcplugin"] = xbmcplugin


install_kodi_stubs()

from resources.lib.downloadutils import DownloadUtils  # noqa: E402
from resources.lib import downloadutils as downloadutils_module  # noqa: E402
from resources.lib import datamanager  # noqa: E402
from resources.lib import play_utils  # noqa: E402
from resources.lib import menu_functions  # noqa: E402
from resources.lib import websocket_client  # noqa: E402
from resources.lib import utils  # noqa: E402
from resources.lib import server_detect  # noqa: E402


class PlaybackUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAddon.settings = {
            **FakeAddon.settings,
            "protocol": "1",
            "verify_cert": "true",
            "ipaddress": "media.example.test",
            "port": "443",
        }
        FakeHomeWindow.props = {"userid": "user-id", "userimage": "DefaultUser.png"}
        DownloadUtils._instance = None
        downloadutils_module.HomeWindow = FakeHomeWindow
        utils.DownloadUtils = FakeDownloadUtils
        utils.ClientInformation = FakeClientInformation

    def test_authenticate_uses_current_emby_form_field_names(self) -> None:
        captured = {}

        def fake_download_url(
            url: str,
            suppress: bool = False,
            post_body: str | dict | None = None,
            method: str = "GET",
            authenticate: bool = True,
            headers: dict[str, str] | None = None,
        ) -> str:
            if "AuthenticateByName" in url:
                captured["url"] = url
                captured["post_body"] = post_body
                captured["method"] = method
                captured["authenticate"] = authenticate
            return (
                '{"AccessToken":"token-123",'
                '"User":{"Id":"user-id","Name":"test-user"}}'
            )

        download_utils = DownloadUtils()
        download_utils.download_url = fake_download_url

        self.assertEqual(download_utils.authenticate(), "token-123")
        self.assertEqual(
            captured["post_body"],
            "Username=user&Pw=pass",
        )
        self.assertEqual(captured["method"], "POST")
        self.assertFalse(captured["authenticate"])

    def test_server_url_preserves_reverse_proxy_path(self) -> None:
        FakeAddon.settings.update(
            {
                "ipaddress": "https://media.example.test/proxy",
                "port": "",
                "protocol": "0",
            }
        )

        download_utils = DownloadUtils()
        download_utils.set_host_domain()

        self.assertEqual(
            download_utils.get_server(),
            "https://media.example.test:443/proxy",
        )

    def test_server_url_refreshes_when_settings_change(self) -> None:
        download_utils = DownloadUtils()
        self.assertEqual(download_utils.get_server(), "https://media.example.test:443")

        FakeAddon.settings.update(
            {
                "ipaddress": "https://changed.example.test/proxy",
                "port": "",
                "protocol": "0",
            }
        )

        self.assertEqual(
            download_utils.get_server(),
            "https://changed.example.test:443/proxy",
        )

    def test_direct_stream_url_authenticates_player_request(self) -> None:
        media_source = {
            "Id": "media-source-1",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": True,
            "SupportsTranscoding": False,
            "DirectStreamUrl": "/Videos/item-1/stream.mkv?static=true",
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-789")
        parsed = urlsplit(result.playurl or "")
        query = parse_qs(parsed.query)

        self.assertEqual(
            result.playurl,
            "https://media.example.test/proxy/emby/Videos/item-1/stream.mkv"
            "?static=true&api_key=token-123&DeviceId=device-456"
            "&MediaSourceId=media-source-1&PlaySessionId=play-session-789",
        )
        self.assertEqual(result.playback_type, "1")
        self.assertEqual(query["api_key"], ["token-123"])
        self.assertEqual(query["DeviceId"], ["device-456"])
        self.assertEqual(query["MediaSourceId"], ["media-source-1"])
        self.assertEqual(query["PlaySessionId"], ["play-session-789"])

    def test_direct_stream_url_does_not_duplicate_emby_prefix(self) -> None:
        media_source = {
            "Id": "media-source-1",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": True,
            "SupportsTranscoding": False,
            "DirectStreamUrl": "/emby/Videos/item-1/stream.mkv?static=true",
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-789")
        parsed = urlsplit(result.playurl or "")

        self.assertEqual(parsed.path, "/proxy/emby/Videos/item-1/stream.mkv")
        self.assertNotIn("/emby/emby/", result.playurl or "")

    def test_direct_stream_absolute_url_is_not_prefixed(self) -> None:
        media_source = {
            "Id": "media-source-1",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": True,
            "SupportsTranscoding": False,
            "DirectStreamUrl": (
                "https://cdn.example.test/Videos/item-1/stream.mkv?static=true"
            ),
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-789")
        parsed = urlsplit(result.playurl or "")

        self.assertEqual(parsed.netloc, "cdn.example.test")
        self.assertEqual(parsed.path, "/Videos/item-1/stream.mkv")
        self.assertNotIn("media.example.test", parsed.netloc)

    def test_transcode_url_authenticates_player_request(self) -> None:
        media_source = {
            "Id": "media-source-2",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": False,
            "SupportsTranscoding": True,
            "TranscodingUrl": (
                "/Videos/item-2/master.m3u8?VideoCodec=h264"
                "&AudioBitrate=128000&AudioStreamIndex=1"
            ),
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-abc")
        parsed = urlsplit(result.playurl or "")
        query = parse_qs(parsed.query)

        self.assertEqual(result.playback_type, "2")
        self.assertEqual(query["api_key"], ["token-123"])
        self.assertEqual(query["DeviceId"], ["device-456"])
        self.assertEqual(query["MediaSourceId"], ["media-source-2"])
        self.assertEqual(query["PlaySessionId"], ["play-session-abc"])
        self.assertEqual(query["AudioBitrate"], ["384000"])
        self.assertEqual(query["MaxWidth"], ["1920"])
        self.assertNotIn("AudioStreamIndex", query)

    def test_transcode_url_does_not_duplicate_emby_prefix(self) -> None:
        media_source = {
            "Id": "media-source-2",
            "Container": "mkv",
            "SupportsDirectPlay": False,
            "SupportsDirectStream": False,
            "SupportsTranscoding": True,
            "TranscodingUrl": (
                "/emby/Videos/item-2/master.m3u8?VideoCodec=h264"
                "&AudioBitrate=128000&AudioStreamIndex=1"
            ),
        }

        result = utils.PlayUtils.get_play_url(media_source, "play-session-abc")
        parsed = urlsplit(result.playurl or "")

        self.assertEqual(parsed.path, "/proxy/emby/Videos/item-2/master.m3u8")
        self.assertNotIn("/emby/emby/", result.playurl or "")

    def test_direct_play_without_direct_stream_url_uses_http_stream(self) -> None:
        media_source = {
            "Id": "media-source-3",
            "Container": "mkv",
            "SupportsDirectPlay": True,
            "SupportsDirectStream": False,
            "SupportsTranscoding": False,
            "Path": r"\\nas\movies\movie.mkv",
        }

        result = utils.PlayUtils.get_play_url(
            media_source, "play-session-def", "item-3"
        )
        parsed = urlsplit(result.playurl or "")
        query = parse_qs(parsed.query)

        self.assertEqual(
            parsed.path,
            "/proxy/emby/Videos/item-3/stream",
        )
        self.assertEqual(result.playback_type, "1")
        self.assertEqual(query["static"], ["true"])
        self.assertEqual(query["api_key"], ["token-123"])
        self.assertEqual(query["MediaSourceId"], ["media-source-3"])
        self.assertEqual(query["PlaySessionId"], ["play-session-def"])


class DownloadUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAddon.settings = {
            **FakeAddon.settings,
            "protocol": "1",
            "verify_cert": "true",
            "ipaddress": "media.example.test",
            "port": "443",
            "username": "user",
            "password": "pass",
            "suppressErrors": "false",
        }
        FakeHomeWindow.props = {
            "AccessToken": "token-123",
            "userid": "user-id",
            "userimage": "DefaultUser.png",
        }
        DownloadUtils._instance = None
        downloadutils_module.HomeWindow = FakeHomeWindow
        downloadutils_module.ClientInformation = FakeClientInformation
        self.original_https_connection = (
            downloadutils_module.http.client.HTTPSConnection
        )
        self.original_http_connection = downloadutils_module.http.client.HTTPConnection
        downloadutils_module.http.client.HTTPSConnection = FakeHTTPConnection
        downloadutils_module.http.client.HTTPConnection = FakeHTTPConnection
        FakeHTTPConnection.instances = []
        FakeHTTPConnection.response = FakeHTTPResponse(200, "OK", b"{}")

    def tearDown(self) -> None:
        downloadutils_module.http.client.HTTPSConnection = (
            self.original_https_connection
        )
        downloadutils_module.http.client.HTTPConnection = self.original_http_connection

    def test_download_url_uses_default_https_port_when_url_omits_port(self) -> None:
        download_utils = DownloadUtils()

        result = download_utils.download_url(
            "https://media.example.test/emby/System/Info/Public?format=json",
            authenticate=False,
        )

        self.assertEqual(result, "{}")
        self.assertEqual(
            FakeHTTPConnection.instances[0].address, "media.example.test:443"
        )
        self.assertEqual(
            FakeHTTPConnection.instances[0].requests[0]["url"],
            "/emby/System/Info/Public?format=json",
        )

    def test_download_url_does_not_clear_saved_password_for_regular_401(self) -> None:
        hashed_username = hashlib.md5(b"user").hexdigest()
        saved_password_key = "saved_user_password_" + hashed_username
        FakeAddon.settings[saved_password_key] = "stored-password"
        FakeHTTPConnection.response = FakeHTTPResponse(401, "Unauthorized", b"")
        download_utils = DownloadUtils()

        download_utils.download_url(
            "https://media.example.test/emby/Sessions/Playing/Progress",
            post_body={"ItemId": "item-1"},
            method="POST",
        )

        self.assertEqual(FakeAddon.settings[saved_password_key], "stored-password")
        self.assertFalse(FakeHomeWindow.props.get("AccessToken"))

    def test_suppressed_401_does_not_clear_playback_token(self) -> None:
        FakeHomeWindow.props["AccessToken"] = "token-123"
        FakeHTTPConnection.response = FakeHTTPResponse(401, "Unauthorized", b"")
        download_utils = DownloadUtils()

        download_utils.download_url(
            "https://media.example.test/emby/Sessions/Playing/Progress",
            suppress=True,
            post_body={"ItemId": "item-1"},
            method="POST",
        )

        self.assertEqual(FakeHomeWindow.props.get("AccessToken"), "token-123")

    def test_download_url_applies_basic_auth_for_url_credentials(self) -> None:
        expected = base64.b64encode(b"proxy-user:proxy-pass").decode("ascii")
        download_utils = DownloadUtils()

        result = download_utils.download_url(
            "https://proxy-user:proxy-pass@media.example.test/emby/Users/Public",
            authenticate=False,
        )

        self.assertEqual(result, "{}")
        headers = FakeHTTPConnection.instances[0].requests[0]["headers"]
        self.assertEqual(headers["Authorization"], "Basic " + expected)

    def test_download_url_uses_kodi_user_agent(self) -> None:
        download_utils = DownloadUtils()

        download_utils.download_url(
            "https://media.example.test/emby/System/Info/Public?format=json",
            authenticate=False,
        )

        headers = FakeHTTPConnection.instances[0].requests[0]["headers"]
        self.assertEqual(headers["User-Agent"], "Kodi/test-version")
        self.assertNotIn("EmbyCon", headers["User-Agent"])

    def test_auth_header_uses_next_embycon_client_and_device_fallback(self) -> None:
        class NextEmbyConClientInformation(FakeClientInformation):
            @staticmethod
            def get_client() -> str:
                return "Kodi Next EmbyCon"

        FakeAddon.settings["deviceName"] = ""
        downloadutils_module.ClientInformation = NextEmbyConClientInformation
        download_utils = DownloadUtils()

        headers = download_utils.get_auth_header(authenticate=False)

        self.assertEqual(
            headers["X-Emby-Authorization"],
            (
                'MediaBrowser Client="Kodi Next EmbyCon",'
                'Device="Next EmbyCon",DeviceId="device-456",Version="test-version"'
            ),
        )

    def test_redacts_sensitive_data_for_logs(self) -> None:
        value = {
            "X-MediaBrowser-Token": "token-123",
            "url": "https://example.test/stream?api_key=token-123&DeviceId=device-1",
            "body": "Username=test-user&Pw=secret-password",
            "response": '{"AccessToken":"token-123"}',
            "headers": [("X-MediaBrowser-Token", "token-123")],
        }

        redacted = str(downloadutils_module.redact_sensitive_data(value))

        self.assertNotIn("token-123", redacted)
        self.assertNotIn("secret-password", redacted)
        self.assertIn("<redacted>", redacted)


class SessionTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        FakePlaybackDownloadUtils.calls = []
        DownloadUtils._instance = None
        downloadutils_module.HomeWindow = FakeHomeWindow
        downloadutils_module.ClientInformation = FakeClientInformation

    def test_post_capabilities_suppresses_unsupported_session_endpoint_errors(
        self,
    ) -> None:
        download_utils = DownloadUtils()
        calls = []

        def fake_download_url(
            url: str,
            suppress: bool = False,
            post_body: str | dict | None = None,
            method: str = "GET",
            authenticate: bool = True,
            headers: dict[str, str] | None = None,
        ) -> str:
            calls.append(
                {
                    "url": url,
                    "suppress": suppress,
                    "post_body": post_body,
                    "method": method,
                    "authenticate": authenticate,
                    "headers": headers,
                }
            )
            return "null"

        download_utils.download_url = fake_download_url

        download_utils.post_capabilities()

        self.assertEqual(calls[0]["url"], "{server}/emby/Sessions/Capabilities/Full?format=json")
        self.assertEqual(calls[0]["method"], "POST")
        self.assertTrue(calls[0]["suppress"])
        self.assertNotIn("IconUrl", calls[0]["post_body"])
        self.assertTrue(calls[0]["post_body"]["SupportsMediaControl"])
        self.assertEqual(calls[0]["post_body"]["PlayableMediaTypes"], ["Video", "Audio"])
        self.assertIn("PlayMediaSource", calls[0]["post_body"]["SupportedCommands"])

    def test_playback_session_updates_are_suppressed(self) -> None:
        class FakePlayer:
            def isPlaying(self) -> bool:
                return True

            def getPlayingFile(self) -> str:
                return "playing-file"

            def getTime(self) -> int:
                return 12

            def getTotalTime(self) -> int:
                return 100

        original_player = play_utils.xbmc.Player
        play_utils.xbmc.Player = lambda: FakePlayer()
        play_utils.DownloadUtils = FakePlaybackDownloadUtils
        play_utils.HomeWindow = FakeHomeWindow

        try:
            monitor = play_utils.PlaybackMonitorService()
            monitor.played_information = {
                "playing-file": {
                    "currently_playing": False,
                    "currentPossition": 0,
                    "duration": 100,
                    "item_id": "item-1",
                    "source_id": "source-1",
                    "play_session_id": "play-session-1",
                    "live_stream_id": "",
                    "playback_type": "DirectStream",
                    "play_action_type": "play_all",
                    "intro_start": 0,
                    "intro_end": 0,
                }
            }

            monitor.onPlayBackStarted()
            play_utils.send_progress(monitor)
            play_utils.stop_all_playback(monitor.played_information)
        finally:
            play_utils.xbmc.Player = original_player

        session_calls = [
            call
            for call in FakePlaybackDownloadUtils.calls
            if str(call["url"]).startswith("{server}/emby/Sessions/Playing")
        ]
        self.assertEqual(len(session_calls), 3)
        self.assertTrue(all(call["suppress"] for call in session_calls))


class NotificationNamespaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_execute_builtin = utils.xbmc.executebuiltin
        self.original_play_file = play_utils.play_file
        self.played_items: list[dict[str, object]] = []
        play_utils.play_file = (
            lambda play_info, play_monitor: self.played_items.append(play_info)
        )

    def tearDown(self) -> None:
        utils.xbmc.executebuiltin = self.original_execute_builtin
        play_utils.play_file = self.original_play_file

    def test_event_notifications_use_next_embycon_namespace(self) -> None:
        commands = []
        utils.xbmc.executebuiltin = lambda command: commands.append(command)

        utils.send_event_notification("nextembycon_play_action", {"item_id": "item-1"})

        self.assertEqual(len(commands), 1)
        self.assertIn("NotifyAll(plugin.video.nextembycon.SIGNAL,", commands[0])
        self.assertIn("nextembycon_play_action", commands[0])

    def test_monitor_ignores_upstream_embycon_signal_namespace(self) -> None:
        payload = base64.b64encode(b'{"item_id":"item-1"}').decode("utf-8")
        monitor = play_utils.MonitoringService(play_utils.PlaybackMonitorService())

        monitor.onNotification(
            "embycon.SIGNAL",
            "Other.nextembycon_play_action",
            '["%s"]' % payload,
        )

        self.assertEqual(self.played_items, [])

    def test_monitor_accepts_next_embycon_signal_namespace(self) -> None:
        payload = base64.b64encode(b'{"item_id":"item-1"}').decode("utf-8")
        monitor = play_utils.MonitoringService(play_utils.PlaybackMonitorService())

        monitor.onNotification(
            "plugin.video.nextembycon.SIGNAL",
            "Other.nextembycon_play_action",
            '["%s"]' % payload,
        )

        self.assertEqual(self.played_items, [{"item_id": "item-1"}])


class BackgroundRequestTests(unittest.TestCase):
    def test_data_manager_can_suppress_background_download_errors(self) -> None:
        calls = []

        class FakeSuppressedDownloadUtils:
            def set_host_domain(self) -> None:
                pass

            def download_url(self, url: str, suppress: bool = False) -> str:
                calls.append({"url": url, "suppress": suppress})
                return '{"Items":[]}'

        original_download_utils = datamanager.DownloadUtils
        datamanager.DownloadUtils = FakeSuppressedDownloadUtils
        try:
            result = datamanager.DataManager().get_content(
                "{server}/emby/Users/{userid}/Views", suppress=True
            )
        finally:
            datamanager.DownloadUtils = original_download_utils

        self.assertEqual(result["Items"], [])
        self.assertEqual(
            calls,
            [{"url": "{server}/emby/Users/{userid}/Views", "suppress": True}],
        )

    def test_library_window_values_suppresses_view_refresh_errors(self) -> None:
        calls = []

        class FakeDataManager:
            def get_content(self, url: str, suppress: bool = False):
                calls.append({"url": url, "suppress": suppress})
                return None

        original_data_manager = menu_functions.DataManager
        original_home_window = menu_functions.HomeWindow
        menu_functions.DataManager = FakeDataManager
        menu_functions.HomeWindow = FakeHomeWindow
        FakeHomeWindow.props = {}
        try:
            menu_functions.set_library_window_values(force=True)
        finally:
            menu_functions.DataManager = original_data_manager
            menu_functions.HomeWindow = original_home_window

        self.assertEqual(
            calls,
            [{"url": "{server}/emby/Users/{userid}/Views", "suppress": True}],
        )


class WebSocketClientTests(unittest.TestCase):
    def test_websocket_trace_is_disabled_and_logged_url_is_redacted(self) -> None:
        created_websockets = []
        trace_values = []

        class FakeWebSocketApp:
            def __init__(self, url: str, **kwargs) -> None:
                created_websockets.append({"url": url, **kwargs})

            def run_forever(self, ping_interval: int) -> None:
                pass

            def close(self) -> None:
                pass

        class CapturingLogger:
            messages: list[str] = []

            def debug(self, fmt: str, *args: object) -> None:
                self.messages.append(fmt.format(*args))

            def error(self, fmt: str, *args: object) -> None:
                self.messages.append(fmt.format(*args))

        original_download_utils = websocket_client.downloadutils.DownloadUtils
        original_client_information = websocket_client.clientinfo.ClientInformation
        original_websocket_app = websocket_client.WebSocketApp
        original_enable_trace = websocket_client.enableTrace
        original_log = websocket_client.log
        logger = CapturingLogger()
        websocket_client.downloadutils.DownloadUtils = FakeDownloadUtils
        websocket_client.clientinfo.ClientInformation = FakeClientInformation
        websocket_client.WebSocketApp = FakeWebSocketApp
        websocket_client.enableTrace = lambda enabled: trace_values.append(enabled)
        websocket_client.log = logger

        try:
            client = websocket_client.WebSocketClient(None)
            client.run()
        finally:
            websocket_client.downloadutils.DownloadUtils = original_download_utils
            websocket_client.clientinfo.ClientInformation = original_client_information
            websocket_client.WebSocketApp = original_websocket_app
            websocket_client.enableTrace = original_enable_trace
            websocket_client.log = original_log

        self.assertEqual(trace_values, [False])
        self.assertEqual(
            created_websockets[0]["url"],
            "wss://media.example.test/proxy/embywebsocket"
            "?api_key=token-123&deviceId=device-456",
        )
        joined_logs = "\n".join(logger.messages)
        self.assertIn("api_key=%3Credacted%3E", joined_logs)
        self.assertNotIn("token-123", joined_logs)


class MenuStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_argv = sys.argv[:]
        self.original_string_load = menu_functions.string_load
        sys.argv = ["plugin://plugin.video.nextembycon/", "1", ""]

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.added_items = []
        xbmcplugin.content_calls = []
        xbmcplugin.ended_handles = []

        labels = {
            30406: "Libraries",
            30407: "Media",
            30408: "Discover",
            30409: "Settings",
            30459: "Continue Watching",
            30460: "Movies",
            30461: "TV Shows",
            30462: "Search",
            30463: "Discover",
            30464: "Settings & Tools",
            30465: "Favorites",
            30466: "Favorite Movies",
            30467: "Favorite TV Shows",
            30468: "Favorite Collections",
        }
        menu_functions.string_load = lambda string_id: labels.get(
            string_id, str(string_id)
        )

    def tearDown(self) -> None:
        sys.argv = self.original_argv
        menu_functions.string_load = self.original_string_load

    def test_main_menu_starts_with_continue_watching_resume_entry(self) -> None:
        menu_functions.display_main_menu()

        added_items = sys.modules["xbmcplugin"].added_items
        labels = [item["listitem"].label for item in added_items]
        urls = [item["url"] for item in added_items]

        self.assertEqual(labels[0], "Continue Watching")
        self.assertEqual(
            labels[1:6], ["Movies", "TV Shows", "Favorites", "Libraries", "Discover"]
        )

        query = parse_qs(urlsplit(urls[0]).query)
        self.assertEqual(query["mode"], ["GET_CONTENT"])
        self.assertEqual(query["media_type"], ["videos"])
        self.assertEqual(query["sort"], ["none"])
        self.assertIn("/emby/Users/{userid}/Items/Resume?", query["url"][0])

    def test_favorites_menu_exposes_favorite_content_lists(self) -> None:
        menu_functions.display_menu({"type": "favorites"})

        added_items = sys.modules["xbmcplugin"].added_items
        labels = [item["listitem"].label for item in added_items]
        urls = [item["url"] for item in added_items]

        self.assertEqual(
            labels,
            ["Favorite Movies", "Favorite TV Shows", "Favorite Collections"],
        )

        media_types = []
        include_item_types = []
        for url in urls:
            query = parse_qs(urlsplit(url).query)
            media_types.append(query["media_type"][0])
            emby_query = parse_qs(urlsplit(query["url"][0]).query)
            self.assertEqual(emby_query["Filters"], ["IsFavorite"])
            include_item_types.append(emby_query["IncludeItemTypes"][0])

        self.assertEqual(media_types, ["movies", "tvshows", "boxsets"])
        self.assertEqual(include_item_types, ["Movie", "Series", "Boxset"])


class ClonedSkinFocusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_settings = FakeAddon.settings.copy()
        self.original_get_skin_dir = getattr(menu_functions.xbmc, "getSkinDir", None)
        self.original_execute_builtin = menu_functions.xbmc.executebuiltin
        self.original_dialog = menu_functions.xbmcgui.Dialog
        self.original_download_utils = menu_functions.DownloadUtils
        self.original_home_window = menu_functions.HomeWindow

    def tearDown(self) -> None:
        FakeAddon.settings = self.original_settings
        if self.original_get_skin_dir is None:
            delattr(menu_functions.xbmc, "getSkinDir")
        else:
            menu_functions.xbmc.getSkinDir = self.original_get_skin_dir
        menu_functions.xbmc.executebuiltin = self.original_execute_builtin
        menu_functions.xbmcgui.Dialog = self.original_dialog
        menu_functions.DownloadUtils = self.original_download_utils
        menu_functions.HomeWindow = self.original_home_window

    def test_change_user_restores_focus_for_next_embycon_cloned_skin(self) -> None:
        class FakeDialogForUserChange:
            def select(self, *args, **kwargs) -> int:
                return 0

            def input(self, *args, **kwargs) -> str:
                return ""

        class FakeDownloadUtilsForUserChange:
            def get_server(self) -> str:
                return "https://media.example.test"

            def download_url(self, url: str, authenticate: bool = True) -> str:
                return (
                    '[{"Name":"cyber","Id":"user-id","HasPassword":false}]'
                )

            def authenticate(self) -> str:
                return "token-123"

            def get_user_id(self) -> str:
                return "user-id"

        commands = []
        menu_functions.xbmc.getSkinDir = lambda: "skin.estuary_nextembycon"
        menu_functions.xbmc.executebuiltin = lambda command: commands.append(command)
        menu_functions.xbmcgui.Dialog = lambda: FakeDialogForUserChange()
        menu_functions.DownloadUtils = FakeDownloadUtilsForUserChange
        menu_functions.HomeWindow = FakeHomeWindow
        FakeHomeWindow.props = {}
        FakeAddon.settings = {
            **FakeAddon.settings,
            "save_user_to_settings": "true",
            "username": "",
            "password": "",
        }

        menu_functions.do_user_change({"user": "cyber", "userid": "user-id"})

        self.assertIn("SetFocus(9000, 0, absolute)", commands)


class PlaybackSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeDialog.select_calls = []
        FakeDialog.select_results = []
        FakeDialog.notifications = []

    def test_sort_media_sources_by_quality_orders_highest_bitrate_first(self) -> None:
        sources = [
            {"Id": "source-low", "Bitrate": 2_000_000},
            {"Id": "source-high", "Bitrate": 12_000_000},
            {"Id": "source-mid", "Bitrate": 6_000_000},
        ]

        sorted_sources = play_utils.sort_media_sources_by_quality(sources)

        self.assertEqual(
            [source["Id"] for source in sorted_sources],
            ["source-high", "source-mid", "source-low"],
        )

    def test_sort_media_sources_by_quality_uses_video_stream_bitrate(self) -> None:
        sources = [
            {
                "Id": "source-low",
                "MediaStreams": [{"Type": "Video", "BitRate": 2_000_000}],
            },
            {
                "Id": "source-high",
                "MediaStreams": [{"Type": "Video", "BitRate": 20_000_000}],
            },
        ]

        sorted_sources = play_utils.sort_media_sources_by_quality(sources)

        self.assertEqual(
            [source["Id"] for source in sorted_sources],
            ["source-high", "source-low"],
        )

    def test_resume_jump_back_never_seeks_before_start(self) -> None:
        self.assertEqual(play_utils.apply_resume_jump_back(2, 15), 0)

    def test_resume_jump_back_keeps_later_resume_position(self) -> None:
        self.assertEqual(play_utils.apply_resume_jump_back(120, 15), 105)


class PlayFileMediaSourceSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_settings = FakeAddon.settings.copy()
        self.original_dialog_calls = FakeDialog.select_calls
        self.original_dialog_results = FakeDialog.select_results
        self.original_dialog_notifications = FakeDialog.notifications
        self.original_download_utils = play_utils.DownloadUtils
        self.original_data_manager = play_utils.DataManager
        self.original_play_utils = play_utils.PlayUtils
        self.original_extract_item_info = play_utils.extract_item_info
        self.original_add_gui_item = play_utils.add_gui_item
        self.original_set_list_item_props = play_utils.set_list_item_props
        self.original_get_next_episode = play_utils.get_next_episode
        self.original_send_next_episode_details = play_utils.send_next_episode_details
        self.original_get_playback_intros = play_utils.get_playback_intros
        self.original_home_window = play_utils.HomeWindow
        self.original_player = play_utils.xbmc.Player
        self.original_playlist = play_utils.xbmc.PlayList

        FakeAddon.settings = {
            **FakeAddon.settings,
            "forceAutoResume": "false",
            "jump_back_amount": "0",
            "play_cinema_intros": "false",
            "auto_play_first_version": "false",
            "use_prem_date_for_added": "false",
        }
        FakeDialog.select_calls = []
        FakeDialog.select_results = []
        FakeDialog.notifications = []
        FakeHomeWindow.props = {"userid": "user-id"}

    def tearDown(self) -> None:
        FakeAddon.settings = self.original_settings
        FakeDialog.select_calls = self.original_dialog_calls
        FakeDialog.select_results = self.original_dialog_results
        FakeDialog.notifications = self.original_dialog_notifications
        play_utils.DownloadUtils = self.original_download_utils
        play_utils.DataManager = self.original_data_manager
        play_utils.PlayUtils = self.original_play_utils
        play_utils.extract_item_info = self.original_extract_item_info
        play_utils.add_gui_item = self.original_add_gui_item
        play_utils.set_list_item_props = self.original_set_list_item_props
        play_utils.get_next_episode = self.original_get_next_episode
        play_utils.send_next_episode_details = self.original_send_next_episode_details
        play_utils.get_playback_intros = self.original_get_playback_intros
        play_utils.HomeWindow = self.original_home_window
        play_utils.xbmc.Player = self.original_player
        play_utils.xbmc.PlayList = self.original_playlist

    def test_play_file_uses_preselected_media_source_without_prompting_again(
        self,
    ) -> None:
        selected_sources = []
        playlist_items = []
        test_case = self

        class FakePlaybackInfoDownloadUtils:
            def get_server(self) -> str:
                return "https://media.example.test/proxy"

            def get_item_playback_info(self, item_id: str, force_transcode: bool):
                test_case.assertEqual(item_id, "item-1")
                test_case.assertFalse(force_transcode)
                return {
                    "PlaySessionId": "session-1",
                    "MediaSources": [
                        {"Id": "source-high", "Name": "4K", "Bitrate": 20_000_000},
                        {"Id": "source-low", "Name": "720p", "Bitrate": 2_000_000},
                    ],
                }

        class FakeDataManager:
            def get_content(self, url: str):
                return {
                    "Id": "item-1",
                    "Type": "Movie",
                    "Name": "Movie",
                    "UserData": {"PlaybackPositionTicks": 0},
                    "Chapters": [],
                }

        class CapturingPlayUtils:
            def get_play_url(
                self, media_source: dict, play_session_id: str, item_id: str
            ):
                selected_sources.append(media_source["Id"])
                return types.SimpleNamespace(
                    playurl="https://media.example.test/video-low",
                    playback_type="0",
                    listitem_props={},
                )

        class CapturingPlaylist:
            def clear(self) -> None:
                playlist_items.clear()

            def add(self, url: str, list_item) -> None:
                playlist_items.append(url)

        class CapturingPlayer:
            def play(self, playlist) -> None:
                self.playlist = playlist

        play_utils.DownloadUtils = FakePlaybackInfoDownloadUtils
        play_utils.DataManager = FakeDataManager
        play_utils.PlayUtils = CapturingPlayUtils
        play_utils.extract_item_info = lambda *args, **kwargs: types.SimpleNamespace()
        play_utils.add_gui_item = lambda *args, **kwargs: types.SimpleNamespace(
            list_item=FakeKodiListItem()
        )
        play_utils.set_list_item_props = lambda *args, **kwargs: args[1]
        play_utils.get_next_episode = lambda result: None
        play_utils.send_next_episode_details = lambda *args, **kwargs: None
        play_utils.get_playback_intros = lambda item_id: []
        play_utils.HomeWindow = FakeHomeWindow
        play_utils.xbmc.Player = CapturingPlayer
        play_utils.xbmc.PlayList = lambda playlist_type: CapturingPlaylist()

        monitor = types.SimpleNamespace(played_information={})

        play_utils.play_file(
            {"item_id": "item-1", "media_source_id": "source-low"},
            monitor,
        )

        self.assertEqual(FakeDialog.select_calls, [])
        self.assertEqual(selected_sources, ["source-low"])
        self.assertEqual(playlist_items, ["https://media.example.test/video-low"])


class ScreensaverPlaybackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_settings = FakeAddon.settings.copy()
        self.original_home_window = play_utils.HomeWindow
        self.original_player = play_utils.xbmc.Player
        self.original_get_cond_visibility = play_utils.xbmc.getCondVisibility
        self.original_execute_builtin = play_utils.xbmc.executebuiltin
        self.original_clear_old_cache_data = play_utils.clear_old_cache_data

        FakeAddon.settings = {
            **FakeAddon.settings,
            "stopPlaybackOnScreensaver": "true",
            "changeUserOnScreenSaver": "true",
            "cacheImagesOnScreenSaver": "false",
        }
        FakeHomeWindow.props = {}
        play_utils.HomeWindow = FakeHomeWindow
        play_utils.clear_old_cache_data = lambda: None

    def tearDown(self) -> None:
        FakeAddon.settings = self.original_settings
        play_utils.HomeWindow = self.original_home_window
        play_utils.xbmc.Player = self.original_player
        play_utils.xbmc.getCondVisibility = self.original_get_cond_visibility
        play_utils.xbmc.executebuiltin = self.original_execute_builtin
        play_utils.clear_old_cache_data = self.original_clear_old_cache_data

    def test_paused_emby_playback_does_not_stop_or_open_login_on_screensaver(
        self,
    ) -> None:
        executed_commands = []

        class PausedPlayer:
            stop_calls = 0

            def isPlayingVideo(self) -> bool:
                return True

            def getPlayingFile(self) -> str:
                return "playing-file"

            def stop(self) -> None:
                self.stop_calls += 1

        player = PausedPlayer()
        play_utils.xbmc.Player = lambda: player
        play_utils.xbmc.getCondVisibility = lambda condition: condition == "Player.Paused"
        play_utils.xbmc.executebuiltin = lambda command: executed_commands.append(command)

        play_monitor = play_utils.PlaybackMonitorService()
        play_monitor.played_information = {
            "playing-file": {
                "item_id": "item-1",
            }
        }
        monitor = play_utils.MonitoringService(play_monitor)

        monitor.screensaver_activated()
        monitor.screensaver_deactivated()

        self.assertEqual(player.stop_calls, 0)
        self.assertEqual(executed_commands, [])
        self.assertEqual(FakeHomeWindow.props.get("skip_select_user"), "true")

    def test_screensaver_deactivate_never_opens_change_user_automatically(
        self,
    ) -> None:
        executed_commands = []
        play_utils.xbmc.executebuiltin = lambda command: executed_commands.append(command)

        play_monitor = play_utils.PlaybackMonitorService()
        monitor = play_utils.MonitoringService(play_monitor)

        monitor.screensaver_deactivated()

        self.assertEqual(executed_commands, [])


class PlaybackSubtitleTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAddon.settings = {
            **FakeAddon.settings,
            "protocol": "1",
            "verify_cert": "true",
            "audio_playback_bitrate": "384",
            "playback_max_width": "1920",
            "direct_stream_sub_select": "0",
        }
        play_utils.DownloadUtils = FakeDownloadUtils

    def test_external_subs_uses_delivery_url_with_emby_prefix(self) -> None:
        list_item = FakeListItem()
        media_source = {
            "Id": "media-source-1",
            "MediaStreams": [
                {
                    "Type": "Subtitle",
                    "IsExternal": True,
                    "IsTextSubtitleStream": True,
                    "SupportsExternalStream": True,
                    "Index": 3,
                    "Codec": "ass",
                    "Language": "chi",
                    "IsDefault": False,
                    "IsForced": False,
                    "DeliveryUrl": (
                        "/emby/Videos/item-1/Subtitles/sub-id/Stream.ass"
                        "?api_key=existing-token"
                    ),
                }
            ],
        }

        play_utils.external_subs(media_source, list_item, "item-1")

        self.assertEqual(
            list_item.subtitles,
            [
                "https://media.example.test/proxy/emby/Videos/item-1/"
                "Subtitles/sub-id/Stream.ass?api_key=existing-token"
            ],
        )

    def test_transcode_selected_external_subtitle_uses_delivery_url(self) -> None:
        list_item = FakeListItem()
        media_source = {
            "Id": "media-source-2",
            "DefaultAudioStreamIndex": 1,
            "DefaultSubtitleStreamIndex": "",
            "MediaStreams": [
                {
                    "Type": "Audio",
                    "Index": 1,
                    "Codec": "aac",
                    "Language": "eng",
                    "ChannelLayout": "stereo",
                },
                {
                    "Type": "Subtitle",
                    "Index": 3,
                    "Codec": "ass",
                    "Language": "chi",
                    "IsDefault": False,
                    "IsForced": False,
                    "IsTextSubtitleStream": True,
                    "IsExternal": True,
                    "SupportsExternalStream": True,
                    "DeliveryUrl": (
                        "/Videos/item-2/Subtitles/sub-id/Stream.ass"
                        "?api_key=existing-token"
                    ),
                },
            ],
        }

        result = play_utils.audio_subs_pref(
            "https://media.example.test/proxy/emby/Videos/item-2/master.m3u8",
            list_item,
            media_source,
            "item-2",
            "",
            "3",
        )

        self.assertEqual(
            list_item.subtitles,
            [
                "https://media.example.test/proxy/emby/Videos/item-2/"
                "Subtitles/sub-id/Stream.ass?api_key=existing-token"
            ],
        )
        self.assertNotIn("SubtitleStreamIndex=3", result)


class PlaybackStopTests(unittest.TestCase):
    def setUp(self) -> None:
        FakePlaybackDownloadUtils.calls = []
        play_utils.DownloadUtils = FakePlaybackDownloadUtils
        play_utils.HomeWindow = FakeHomeWindow
        play_utils.ClientInformation = FakeClientInformation
        self.marked_items: list[tuple[str, bool]] = []
        self.original_mark_item_watched = play_utils.mark_item_watched
        play_utils.mark_item_watched = (
            lambda item_id, refresh=True: self.marked_items.append((item_id, refresh))
        )

    def tearDown(self) -> None:
        play_utils.mark_item_watched = self.original_mark_item_watched

    def test_direct_stream_stop_does_not_delete_active_encodings(self) -> None:
        played_information = {
            "https://media.example.test/proxy/emby/Videos/item-1/stream": {
                "currently_playing": True,
                "currentPossition": 12,
                "duration": 100,
                "item_id": "item-1",
                "source_id": "source-1",
                "play_session_id": "play-session-1",
                "live_stream_id": "",
                "playback_type": "DirectStream",
                "play_action_type": "play_all",
            }
        }

        play_utils.stop_all_playback(played_information)

        urls = [call["url"] for call in FakePlaybackDownloadUtils.calls]
        self.assertIn("{server}/emby/Sessions/Playing/Stopped", urls)
        self.assertFalse(any("ActiveEncodings" in str(url) for url in urls))

    def test_transcode_stop_suppresses_active_encoding_cleanup_errors(self) -> None:
        played_information = {
            "https://media.example.test/proxy/emby/Videos/item-2/master.m3u8": {
                "currently_playing": True,
                "currentPossition": 12,
                "duration": 100,
                "item_id": "item-2",
                "source_id": "source-2",
                "play_session_id": "play-session-2",
                "live_stream_id": "",
                "playback_type": "Transcode",
                "play_action_type": "play_all",
            }
        }

        play_utils.stop_all_playback(played_information)

        cleanup_calls = [
            call
            for call in FakePlaybackDownloadUtils.calls
            if "ActiveEncodings" in str(call["url"])
        ]
        self.assertEqual(len(cleanup_calls), 1)
        self.assertEqual(cleanup_calls[0]["method"], "DELETE")
        self.assertTrue(cleanup_calls[0]["suppress"])

    def test_playback_ended_does_not_mark_watched_before_threshold(self) -> None:
        monitor = play_utils.PlaybackMonitorService()
        monitor.currently_playing_id = "item-1"
        monitor.played_information = {
            "https://media.example.test/proxy/emby/Videos/item-1/stream": {
                "currently_playing": True,
                "currentPossition": 12,
                "duration": 100,
                "item_id": "item-1",
                "source_id": "source-1",
                "play_session_id": "play-session-1",
                "live_stream_id": "",
                "playback_type": "DirectStream",
                "play_action_type": "play_all",
            }
        }

        monitor.onPlayBackEnded()

        self.assertEqual(self.marked_items, [])

    def test_playback_ended_marks_watched_after_threshold(self) -> None:
        monitor = play_utils.PlaybackMonitorService()
        monitor.currently_playing_id = "item-1"
        monitor.played_information = {
            "https://media.example.test/proxy/emby/Videos/item-1/stream": {
                "currently_playing": True,
                "currentPossition": 92,
                "duration": 100,
                "item_id": "item-1",
                "source_id": "source-1",
                "play_session_id": "play-session-1",
                "live_stream_id": "",
                "playback_type": "DirectStream",
                "play_action_type": "play_all",
            }
        }

        monitor.onPlayBackEnded()

        self.assertEqual(self.marked_items, [("item-1", False)])


if __name__ == "__main__":
    unittest.main()
