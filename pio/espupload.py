#!/usr/bin/env python3
"""Upload an ESP8266 image; credentials stay out of command lines and logs."""
import argparse
import getpass
import os
from pathlib import Path
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def upload(host, filename, username="admin", password=None, timeout=30):
    base = urllib.parse.urlsplit(host if "://" in host else "http://" + host)
    if (base.scheme not in ("http", "https") or not base.hostname or base.username
            or base.password or base.path not in ("", "/") or base.query or base.fragment):
        raise ValueError("Specify a device IP/hostname, optionally with http(s) and a port")
    url = urllib.parse.urlunsplit((base.scheme, base.netloc, "/firmware", "", ""))
    image = Path(filename).read_bytes()
    if not image or len(image) > 1048576:
        raise ValueError("Firmware must be non-empty and no larger than 1 MiB")
    boundary = "WThermostat" + secrets.token_hex(16)
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            'filename="firmware.bin"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
    data += image + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(url, data=data, headers={
        "Content-Type": "multipart/form-data; boundary=" + boundary,
    })
    opener = urllib.request.build_opener(NoRedirect())
    # Obtain the Digest challenge with GET, before sending any firmware bytes.
    try:
        with opener.open(url, timeout=timeout) as response:
            response.read(65536)
    except urllib.error.HTTPError as error:
        challenge = error.headers.get("WWW-Authenticate", "")
        error.close()
        if error.code != 401 or not challenge.lower().startswith("digest "):
            raise
        if password is None:
            password = os.environ.get("WTHERMOSTAT_PASSWORD")
        if password is None:
            password = getpass.getpass(f"WiFi password for {username}@{base.netloc}: ")
        manager = urllib.request.HTTPPasswordMgr()
        fields = urllib.request.parse_keqv_list(urllib.request.parse_http_list(challenge[7:]))
        manager.add_password(fields.get("realm"), url, username, password)
        handler = urllib.request.HTTPDigestAuthHandler(manager)
        authorization = handler.get_authorization(request, fields)
        if not authorization:
            raise ValueError("Device did not offer a supported Digest authentication challenge")
        request.add_header("Authorization", "Digest " + authorization)
    with opener.open(request, timeout=timeout) as response:
        body = response.read(65537)
        if response.status != 200 or len(body) > 65536 or b"Update successful." not in body:
            raise ValueError("Device did not confirm a successful firmware update")
    return True


def parser(argv=None):
    options = argparse.ArgumentParser(description=__doc__)
    options.add_argument("-u", "--host", required=True)
    options.add_argument("-f", "--file", dest="image", required=True)
    options.add_argument("--username", default="admin")
    options.add_argument("--timeout", type=float, default=30)
    options.add_argument("-d", "--debug", action="store_true", help="Print the destination, never credentials")
    return options.parse_args(argv)


def main(argv=None):
    options = parser(argv)
    try:
        if options.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if options.debug:
            print(f"Uploading {Path(options.image).name} to {options.host}")
        upload(options.host, options.image, username=options.username, timeout=options.timeout)
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"Upload failed: {error}", file=sys.stderr)
        return 1
    print("Update successful.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
