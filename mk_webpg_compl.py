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
import io

from requests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    InvalidSchema,
    MissingSchema,
    ReadTimeout,
    SSLError,
    TooManyRedirects,
)


url_re = re.compile(r"^(https?:)?//[^/]+\.[a-z]+/.*$", re.IGNORECASE)
schema_re = re.compile("^https?:", re.IGNORECASE)

url_to_scheme = lambda url: url.split(":", 1)[0] + ":"
is_url = lambda url: url_re.match(url)
is_absolute_url = lambda url: schema_re.match(url)
is_scheme_relative_url = lambda strval: strval.startswith("//")


def main():
    file_path = filename_from_args(sys.argv)
    file_name = mktmpd_with_file_and_chdir(file_path)

    with open(file_name) as fh:
        html = "".join(fh.readlines())
        soup = bs4.BeautifulSoup(markup=html, features="lxml")

    title_text = soup.find("title").text.replace("/", "\\")
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


def fix_url(url):
    if not is_url(url):
        raise RuntimeError(f"Invalid url: '{url}'")
    elif is_scheme_relative_url(url):
        return "https:" + url
    elif is_absolute_url(url):
        return url
    else:
        raise RuntimeError(f"Could not resolve relative url '{url}'")


def filename_from_args(argv):
    if len(sys.argv) == 1:
        print(
            "Please specify a file to convert to a Web Page, Complete on the commandline."
        )
        exit(1)
    elif len(sys.argv) > 2:
        print("Please specify just one file to convert to a Web Page, Complete.")
        exit(1)
    file_name = sys.argv[1]
    if not os.path.exists(file_name):
        print(f"The file '{file_name}' does not exist.")
        exit(1)
    return os.path.abspath(file_name)


def mktmpd_with_file_and_chdir(old_file_path):
    tempdir = tempfile.mkdtemp()
    os.chdir(tempdir)
    _, file_name = os.path.split(old_file_path)
    new_file_path = os.path.join(tempdir, file_name)
    shutil.copy(old_file_path, new_file_path)
    return file_name


def retrieve_url_into_file(url, file_path):
    file_handle = None
    try:
        bytes_output_count = 0
        file_handle = open(file_path, "wb")
        http_response = requests.get(url, timeout=10)
        if http_response.status_code != 200:
            raise RuntimeError(
                f"Request not successful: got HTTP status code {http_response.status_code}."
            )
        for chunk in http_response.iter_content(chunk_size=1024):
            bytes_output_count += file_handle.write(chunk)
    except OSError as exception:
        raise RuntimeError(
            f"Could not open output file '{file_path}' for writing: {exception}"
        ) from exception
    except (InvalidSchema, MissingSchema) as exception:
        raise RuntimeError(
            f"Could not load '{url}' due to malformed url: {exception}"
        ) from exception
    except SSLError as exception:
        # An error in the SSL handshake, or an expired cert.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to SSL error: {exception}"
        ) from exception
    except TooManyRedirects as exception:
        # The remote host put the client through too many redirects.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to too many redirects: {exception}"
        ) from exception
    except (ConnectTimeout, ReadTimeout) as exception:
        # The connection timed out.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to connection timeout: {exception}"
        ) from exception
    except (ConnectionError, IOError) as exception:
        # There was a generic connection error.
        raise RuntimeError(
            f"Could not load resource at '{url}' due to connection error: {exception}"
        ) from exception
    finally:
        if isinstance(file_handle, io.IOBase):
            file_handle.close()
    return bytes_output_count


def url_to_permuted_filename(url):
    if not url_re.match(url):
        raise RuntimeError(f"string '{url}' does not match the pattern for a url")
    _, file_name_w_suffix = url.rsplit("/", 1)
    file_name, type_suffix = file_name_w_suffix.rsplit(".")
    random_suffix = hex(random.randint(4096, 65535)).removeprefix("0x")
    return file_name + "_" + random_suffix + "." + type_suffix


if __name__ == "__main__":
    main()
