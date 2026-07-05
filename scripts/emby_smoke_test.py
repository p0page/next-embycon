from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEVICE_ID = "codex-next-embycon-smoke"


@dataclass
class SmokeClient:
    server: str
    username: str
    password: str
    timeout: int
    verify_tls: bool
    token: str = ""
    user_id: str = ""

    @property
    def base_url(self) -> str:
        return self.server.rstrip("/")

    @property
    def ssl_context(self):
        if self.verify_tls:
            return None
        return ssl._create_unverified_context()

    def authorization_header(self, authenticated: bool = True) -> str:
        if authenticated:
            return (
                'MediaBrowser UserId="{user_id}",Client="Next EmbyCon Smoke",'
                'Device="Codex",DeviceId="{device_id}",Version="test"'
            ).format(user_id=self.user_id, device_id=DEVICE_ID)
        return (
            'MediaBrowser Client="Next EmbyCon Smoke",Device="Codex",'
            'DeviceId="{device_id}",Version="test"'
        ).format(device_id=DEVICE_ID)

    def request_json(
        self,
        path: str,
        method: str = "GET",
        data: bytes | None = None,
        content_type: str | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Accept-Charset": "UTF-8,*",
            "User-Agent": "Kodi/test-version",
            "X-Emby-Authorization": self.authorization_header(authenticated),
        }
        if self.token:
            headers["X-MediaBrowser-Token"] = self.token
        if content_type:
            headers["Content-Type"] = content_type

        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(
            request, timeout=self.timeout, context=self.ssl_context
        ) as response:
            body = response.read()
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def authenticate(self) -> None:
        body = urllib.parse.urlencode(
            {"Username": self.username, "Pw": self.password}
        ).encode("utf-8")
        result = self.request_json(
            "/emby/Users/AuthenticateByName?format=json",
            method="POST",
            data=body,
            content_type="application/x-www-form-urlencoded",
            authenticated=False,
        )
        self.token = result["AccessToken"]
        self.user_id = result["User"]["Id"]

    def get_video_items(self) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(
            {
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Fields": "MediaSources,UserData,Chapters",
                "SortBy": "DatePlayed,DateCreated",
                "SortOrder": "Descending",
                "Limit": "10",
                "format": "json",
            }
        )
        result = self.request_json(f"/emby/Users/{self.user_id}/Items?{query}")
        return result.get("Items", [])

    def get_resume_items(self) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(
            {
                "Recursive": "true",
                "Fields": "MediaSources,UserData,Chapters",
                "Limit": "10",
                "format": "json",
            }
        )
        result = self.request_json(f"/emby/Users/{self.user_id}/Items/Resume?{query}")
        return result.get("Items", [])

    def get_playback_info(self, item_id: str) -> dict[str, Any]:
        profile = {
            "Name": "Kodi",
            "MaxStaticBitrate": 120000000,
            "MaxStreamingBitrate": 120000000,
            "MusicStreamingTranscodingBitrate": 384000,
            "TimelineOffsetSeconds": 5,
            "TranscodingProfiles": [
                {
                    "Container": "ts",
                    "Protocol": "hls",
                    "Type": "Video",
                    "AudioCodec": "aac",
                    "VideoCodec": "h264",
                    "MaxAudioChannels": "6",
                }
            ],
            "DirectPlayProfiles": [{"Type": "Video"}, {"Type": "Audio"}],
            "ResponseProfiles": [],
            "ContainerProfiles": [],
            "CodecProfiles": [],
            "SubtitleProfiles": [
                {"Format": "srt", "Method": "External"},
                {"Format": "ass", "Method": "External"},
                {"Format": "subrip", "Method": "Embed"},
            ],
        }
        body = json.dumps(
            {"UserId": self.user_id, "DeviceProfile": profile, "AutoOpenLiveStream": True}
        ).encode("utf-8")
        return self.request_json(
            f"/emby/Items/{item_id}/PlaybackInfo?MaxStreamingBitrate=120000000",
            method="POST",
            data=body,
            content_type="application/json",
        )

    def build_probe_url(self, item_id: str, playback_info: dict[str, Any]) -> str:
        media_sources = playback_info.get("MediaSources") or []
        if not media_sources:
            raise RuntimeError("PlaybackInfo returned no MediaSources")

        source = media_sources[0]
        play_session_id = playback_info.get("PlaySessionId", "")
        if source.get("DirectStreamUrl"):
            path = source["DirectStreamUrl"]
        elif source.get("SupportsDirectPlay") or source.get("SupportsDirectStream"):
            path = f"/emby/Videos/{item_id}/stream?static=true"
        elif source.get("TranscodingUrl"):
            path = source["TranscodingUrl"]
        else:
            raise RuntimeError("MediaSource has no streamable URL")

        url = urllib.parse.urljoin(self.base_url + "/", path.lstrip("/"))
        separator = "&" if "?" in url else "?"
        params = urllib.parse.urlencode(
            {
                "api_key": self.token,
                "DeviceId": DEVICE_ID,
                "MediaSourceId": source.get("Id", ""),
                "PlaySessionId": play_session_id,
            }
        )
        return url + separator + params

    def probe_stream_url(self, url: str) -> tuple[int, str]:
        request = urllib.request.Request(
            url,
            headers={
                "Range": "bytes=0-0",
                "User-Agent": "Kodi/test-version",
            },
        )
        with urllib.request.urlopen(
            request, timeout=self.timeout, context=self.ssl_context
        ) as response:
            response.read(1)
            return response.status, response.reason


def env_or_arg(value: str | None, env_name: str) -> str:
    resolved = value or os.environ.get(env_name, "")
    if not resolved:
        raise SystemExit(f"Missing --{env_name.lower()} or {env_name}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test an Emby server.")
    parser.add_argument("--server", default=os.environ.get("EMBY_SERVER"))
    parser.add_argument("--username", default=os.environ.get("EMBY_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("EMBY_PASSWORD"))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--skip-stream-probe", action="store_true")
    args = parser.parse_args()

    client = SmokeClient(
        server=env_or_arg(args.server, "EMBY_SERVER"),
        username=env_or_arg(args.username, "EMBY_USERNAME"),
        password=env_or_arg(args.password, "EMBY_PASSWORD"),
        timeout=args.timeout,
        verify_tls=not args.insecure,
    )

    try:
        client.authenticate()
        print("auth ok")

        resume_items = client.get_resume_items()
        print(f"resume items: {len(resume_items)}")

        video_items = client.get_video_items()
        print(f"video items: {len(video_items)}")
        if not video_items:
            raise RuntimeError("No Movie/Episode items found")

        item = video_items[0]
        playback_info = client.get_playback_info(item["Id"])
        media_sources = playback_info.get("MediaSources") or []
        print(f"playback media sources: {len(media_sources)}")
        if not media_sources:
            raise RuntimeError("PlaybackInfo returned no media sources")

        if not args.skip_stream_probe:
            probe_url = client.build_probe_url(item["Id"], playback_info)
            status, reason = client.probe_stream_url(probe_url)
            print(f"stream probe: {status} {reason}")
            if status >= 400:
                raise RuntimeError(f"Stream probe failed: {status} {reason}")

    except urllib.error.HTTPError as error:
        print(f"http error: {error.code} {error.reason}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"smoke failed: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
