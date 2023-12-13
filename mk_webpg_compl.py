#!/usr/bin/python3

import bs4
import os
import os.path
import random
import re
import requests
import requests.exceptions
import shutil
import sys
import tempfile

from re import Pattern
from typing import BinaryIO, Type

from bs4 import Tag, NavigableString
from requests import Response
from requests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    InvalidSchema,
    MissingSchema,
    ReadTimeout,
    SSLError,
    TooManyRedirects,
)

status_code_msgs: dict[int, str] = {
    100: "100 Continue",
    101: "101 Switching Protocols",
    102: "102 Processing",
    103: "103 Early Hints",
    200: "200 OK",
    201: "201 Created",
    202: "202 Accepted",
    203: "203 Non-Authoritative Information",
    204: "204 No Content",
    205: "205 Reset Content",
    206: "206 Partial Content",
    207: "207 Multi-Status",
    208: "208 Already Reported",
    226: "226 IM Used",
    300: "300 Multiple Choices",
    301: "301 Moved Permanently",
    302: "302 Found",
    303: "303 See Other",
    304: "304 Not Modified",
    305: "305 Use Proxy",
    307: "307 Temporary Redirect",
    308: "308 Permanent Redirect",
    400: "400 Bad Request",
    401: "401 Unauthorized",
    402: "402 Payment Required",
    403: "403 Forbidden",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    406: "406 Not Acceptable",
    407: "407 Proxy Authentication Required",
    408: "408 Request Timeout",
    409: "409 Conflict",
    410: "410 Gone",
    411: "411 Length Required",
    412: "412 Precondition Failed",
    413: "413 Payload Too Large",
    414: "414 Request-URI Too Long",
    415: "415 Unsupported Media Type",
    416: "416 Request Range Not Satisfiable",
    417: "417 Expectation Failed",
    418: "418 I’m a teapot",
    420: "420 Enhance Your Calm",
    421: "421 Misdirected Request",
    422: "422 Unprocessable Entity",
    423: "423 Locked",
    424: "424 Failed Dependency",
    425: "425 Too Early",
    426: "426 Upgrade Required",
    428: "428 Precondition Required",
    429: "429 Too Many Requests",
    431: "431 Request Header Fields Too Large",
    444: "444 No Response",
    450: "450 Blocked by Windows Parental Controls",
    451: "451 Unavailable For Legal Reasons",
    497: "497 HTTP Request Sent to HTTPS Port",
    498: "498 Token expired/invalid",
    499: "499 Client Closed Request",
    500: "500 Internal Server Error",
    501: "501 Not Implemented",
    502: "502 Bad Gateway",
    503: "503 Service Unavailable",
    504: "504 Gateway Timeout",
    506: "506 Variant Also Negotiates",
    507: "507 Insufficient Storage",
    508: "508 Loop Detected",
    509: "509 Bandwidth Limit Exceeded",
    510: "510 Not Extended",
    511: "511 Network Authentication Required",
    521: "521 Web Server Is Down",
    522: "522 Connection Timed Out",
    523: "523 Origin Is Unreachable",
    525: "525 SSL Handshake Failed",
    530: "530 Site Frozen",
    599: "599 Network Connect Timeout Error",
}

req_excpt_msgs: dict[Type[OSError], str] = {
    ConnectionError: "connection error",
    ConnectTimeout: "connection timeout",
    InvalidSchema: "malformed url",
    IOError: "connection error",
    MissingSchema: "malformed url",
    ReadTimeout: "connection timeout",
    SSLError: "SSL error",
    TooManyRedirects: "too many redirects",
}

url_re: Pattern[str] = re.compile(r"^(https?:)?//[^/]+\.[a-z]+/.*$", re.IGNORECASE)
schema_re: Pattern[str] = re.compile("^https?:", re.IGNORECASE)
abs_path_re: Pattern[str] = re.compile(r"^/.*/[^/]\+$")

url_to_scheme = lambda url: url.split(":", 1)[0] + ":"
is_url = lambda url: url_re.match(url)
is_absolute_url = lambda url: schema_re.match(url)
is_scheme_relative_url = lambda strval: strval.startswith("//")


def main() -> None:
    file_path: str = filename_from_args(sys.argv)
    file_name = mktmpd_with_file_and_chdir(file_path)

    with open(file_name) as fh:
        html = "".join(fh.readlines())
        soup = bs4.BeautifulSoup(markup=html, features="lxml")

    title_tag: Tag | NavigableString | None = soup.find("title")
    if not isinstance(title_tag, Tag):
        raise RuntimeError("Failed to find <title> tag")
    title_text = title_tag.text.replace("/", "\\")
    files_dir_name = title_text + "_files"
    final_html_file_name = title_text + ".html"
    os.mkdir(files_dir_name)

    img_tags = soup.find_all("img", src=True)
    script_tags = soup.find_all("script", src=True)
    link_tags = soup.find_all("link", rel="stylesheet", href=True)
    tags = list(img_tags) + list(script_tags) + list(link_tags)

    for tag in tags:
        attrname = "href" if tag.name == "link" else "src"
        url = getattr(tag, attrname)
        resource_file_path = os.path.join(files_dir_name, url_to_permuted_filename(url))
        retrieve_url_into_file(url, resource_file_path)
        setattr(tag, attrname, resource_file_path)

    with open(final_html_file_name, "w") as fh:
        fh.write(str(soup))


def fix_url(url: str) -> str:
    if not is_url(url):
        raise RuntimeError(f"Invalid url: '{url}'")
    elif is_scheme_relative_url(url):
        return "https:" + url
    elif is_absolute_url(url):
        return url
    else:
        raise RuntimeError(f"Could not resolve relative url '{url}'")


def filename_from_args(argv: list[str]) -> str:
    if len(argv) == 1:
        print(
            "Please specify a file to convert to a Web Page, Complete on the commandline."
        )
        exit(1)
    elif len(argv) > 2:
        print("Please specify just one file to convert to a Web Page, Complete.")
        exit(1)
    file_name = argv[1]
    if not os.path.exists(file_name):
        print(f"The file '{file_name}' does not exist.")
        exit(1)
    return os.path.abspath(file_name)


def mktmpd_with_file_and_chdir(old_file_path: str) -> str:
    if not isinstance(old_file_path, str) or not abs_path_re.match(old_file_path):
        raise ValueError(
            f"Argument old_file_path was an absolute path; got '{old_file_path}' instead."
        )
    tempdir: str = tempfile.mkdtemp()
    os.chdir(tempdir)
    file_name: str = os.path.split(old_file_path)[1]
    new_file_path: str = os.path.join(tempdir, file_name)
    shutil.copy(old_file_path, new_file_path)
    return file_name


def retrieve_url_into_file(url: str, file_path: str) -> int:
    global status_code_msgs
    bytes_output_count: int = 0

    try:
        http_response: Response = requests.get(url, timeout=10)
        assert http_response.status_code == 200, status_code_msgs[http_response.status_code]
        file_handle: BinaryIO = open(file_path, "wb")
        chunk: bytes
        for chunk in http_response.iter_content(chunk_size=1024):
            bytes_output_count += file_handle.write(chunk)
    except AssertionError as exception:
        raise RuntimeError(f"Request not successful: got status {exception}")
    except (ConnectionError, ConnectTimeout, InvalidSchema, MissingSchema, ReadTimeout, SSLError,
            TooManyRedirects) as exception:
        source_msg = f" due to {req_excpt_msgs[type(exception)]}" if type(exception) in req_excpt_msgs else ""
        raise RuntimeError(f"Could not load '{url}'{source_msg}: {exception}") from exception
    # All the above exceptions are subclass OSError, but so are the I/O errors
    # that writing to a file can throw, so this block comes second
    except OSError as exception:
        raise RuntimeError(f"Could not write to file '{file_path}': {exception}") from exception
    finally:
        file_handle.close()

    return bytes_output_count


def url_to_permuted_filename(url: str) -> str:
    if not url_re.match(url):
        raise RuntimeError(f"string '{url}' does not match the pattern for a url")
    file_name_w_suffix: str = url.rsplit("/", 1)[1]
    file_name: str
    type_suffix: str
    file_name, type_suffix = file_name_w_suffix.rsplit(".", 1)
    random_suffix: str = hex(random.randint(4096, 65535)).removeprefix("0x")
    return file_name + "_" + random_suffix + "." + type_suffix


if __name__ == "__main__":
    main()
